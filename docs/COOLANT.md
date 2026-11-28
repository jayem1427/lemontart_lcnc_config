# MQL coolant (Microject)

Coolant on this mill is minimum-quantity lubrication: an automotive fuel
injector pulsed by Dan Mills' **Microject** controller. LinuxCNC controls it
over Modbus. You set how often it pulses (Hz) and what fraction of each pulse
the valve is open (duty %). M7/M8/M9 turn it on and off as usual, so CAM output
needs no changes.

New to Modbus in LinuxCNC? Read [MODBUS.md](MODBUS.md) first.

---

## Using it

| G-code | Does |
|--------|------|
| `M201 P<Hz> Q<duty%>` | Set pulse rate (0.1–50 Hz) and duty (0–100 %) |
| `M202` | Load the current tool's recipe from `probe_basic/coolant_tools.ini`, then same as M201 |
| `M7` or `M8` | Injector on |
| `M9` | Injector off. Aborts also issue M9 |

```
T3 M600
M202        (use T3's recipe)
M8
...
M9
```

`M201 P10 Q1` gives a 100 ms period with a 1 ms pulse, the controller's
default. These are custom M-codes in the 200s because LinuxCNC can't remap
M100–M199 (they're reserved for user M-files).

### Per-tool recipes

`probe_basic/coolant_tools.ini` holds a `[T<n>]` section per tool with its Hz
and duty. Tools without a section use `[COOLANT]DEFAULT_FREQ` /
`DEFAULT_DUTY` from the INI (10 Hz, 1 %). M202 re-reads the file every time,
so edits take effect without a restart.

### The MQL tab

Probe Basic's **MQL** tab is a front end for the same commands:

| Control | Does |
|---------|------|
| P slider | Pulse rate 0.1–50 Hz in 0.1 Hz steps. Squared mapping, so the slow end gets more of the travel |
| Q slider | Duty 0–100 % in 0.1 % steps. The first half of the slider covers 0–25 %, where MQL actually runs |
| Pulse preview | Draws the valve timing for the first 500 ms to scale. Blue while spraying |
| APPLY | Sends `M201 P… Q…`. Outlined amber when the screen doesn't match the machine |
| LIVE | Sends M201 automatically about 0.3 s after you let go of a slider |
| REVERT | Reloads what the machine is using now |
| M8 SPRAY ON / M9 OFF | Sends the on-screen M201 and then M8, or M9 |
| Presets | Named Hz/duty pairs, saved in `probe_basic/mql_presets.json` |
| Tool recipe | LOAD / SAVE TO TOOL reads and writes `[T<n>]` in `coolant_tools.ini`, keeping your comments |

The buttons are disabled while a program runs (put M201/M202 in the G-code
instead) and when the machine is off. The pulse-length readout turns amber
under 1 ms as a hint that the injector may not fully open.

---

## How it works

```
M201 P Q  ──►  analog outputs E4 (Hz), E5 (duty %)
                         │
                   coolant.hal
                   clamp Hz to 0.1–50
                   period_ms = 1000 / Hz
                   pulse_ms  = period_ms × duty / 100   (forced to 0 when off)
                         │
                         ├─► microject.coolant_period.00.float ─► holding register 2
                         └─► microject.coolant_pulse.00.float  ─► holding register 1

M7 / M8  ──►  flood OR mist (or2.5)  ──►  microject.coolant_run.00.bit  ──►  coil 1
```

Analog outputs E0–E3 belong to the laser setter. E6 (pressure) is stored but
not sent anywhere yet.

## The Microject controller

| Setting | Value |
|---------|-------|
| Adapter | FTDI USB-RS485, `/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_BG02XIBV-if00-port0` |
| Serial | 19200 8E1 (DIP switches can change this) |
| Slave ID | 8 |
| Power | 24 V to the board. The injector here is a GM0521994 12 V coil, which the board drives |
| Default if never configured | 1 ms pulse every 100 ms |
| Watchdog | Turns the injector off 5 s after the last valid Modbus message. mb2hal rewrites the coil twice a second to keep it alive |

Each of the four injector ports N has its own coil and two holding registers:

| Port | Coil | Pulse register | Period register | Local pot/switch |
|------|------|----------------|-----------------|------------------|
| 1 (used here) | 1 | 1 | 2 | yes |
| 2 | 2 | 3 | 4 | yes |
| 3 | 3 | 5 | 6 | no |
| 4 | 4 | 7 | 8 | no |

The numbers above are 1-based, as the Microject docs and `mbpoll` count.
`microject.mb2hal` uses 0-based addresses, so port 1 is coil 0, pulse 0,
period 1. To use port 4, change them to 3 / 6 / 7.

### Slow pulse rates

The board's firmware (github.com/dan-mills/microJect, `firmware/src/main.rs`)
runs a 1 ms tick with a 16-bit counter per channel: the period register is
whole milliseconds, 1–65535, with no clamp. So rates down to about 0.016 Hz
would work; this config stops at **0.1 Hz** (one shot every 10 s). The board
fires a pulse as soon as the coil turns on, so slow rates don't wait a full
period for the first shot.

At slow rates duty turns into a big shot: at 0.2 Hz the period is 5000 ms, so
1 % is a 50 ms pulse. Use small duties (0.1 % = 5 ms there). Pulses under
1 ms are truncated to 0 (no spray). The tab's pulse-train preview widens its
window (up to 20 s) so at least two periods show.

Registers are treated as milliseconds. If yours turn out to be 0.1 ms units,
set `[COOLANT]PULSE_SCALE` and `PERIOD_SCALE` to 10 in the INI.

## Checking it

With LinuxCNC running: `M201 P10 Q1`, then `M8`.

```bash
halcmd getp microject.coolant_run.00.bit       # TRUE
halcmd getp microject.coolant_period.00.float  # ~100
halcmd getp microject.coolant_pulse.00.float   # ~1
```

`M9` sets the run bit FALSE and the pulse to 0. To test the watchdog, unplug
the FTDI adapter while it's spraying: the injector must stop within about 5 s.

Without LinuxCNC (stop it first), see [MODBUS.md](MODBUS.md#bench-testing).

## Files

| File | Role |
|------|------|
| `microject.mb2hal` | Coil + pulse + period transactions |
| `coolant.hal` | Hz/duty → ms, M7/M8 → coil |
| `probe_basic/subroutines/m201.ngc` | The `M201` remap |
| `probe_basic/python/coolant_remap.py`, `coolant_profiles.py` | The `M202` remap, and the recipe file reader/writer |
| `probe_basic/coolant_tools.ini` | Per-tool recipes |
| `probe_basic/user_tabs/mql_control/` | MQL tab |

This isn't Probe Basic's programmable coolant nozzle feature
(`program_coolant.ngc`). Leave `#3000 = 0`.
