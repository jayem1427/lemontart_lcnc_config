# PWM coolant (Microject)

Dan Mills **Microject** injector driver: an automotive fuel injector pulsed as
an MQL valve. Fusion still emits stock **M7 / M8 / M9**.

**At the machine:** **[MICROJECT.md](MICROJECT.md)** (wire, `mbpoll`, LinuxCNC, in one page).
**Never configured mb2hal?** **[MB2HAL.md](MB2HAL.md)**. This page is the mill map.

This is **not** Probe Basic’s programmable nozzle aimer (`program_coolant.ngc`).
Leave `#3000 = 0`.

---

## What is live

| Piece | Value |
|-------|--------|
| Serial | 19200 **8E1**, slave **8** (DIP switches can change this) |
| Enable | **Coil N** for injector port N. Default **port 1 → coil 1** |
| Pulse length | Holding register **2N−1** (port 1 → **H1**). Units treated as **ms** |
| Period | Holding register **2N** (port 1 → **H2**). Units treated as **ms** |
| Firmware default | 1 ms on / 100 ms period if you never write Hregs |
| Watchdog | Coil OFF **5 s** after the last valid Modbus message |
| Reads | Opto inputs + analog readable; not wired in HAL yet |
| Second UART | **Yes.** H100 is 38400 8N1. Injector stays on `/dev/ttyUSB1` |

Port map (Dan, testers chat — Richie on port 4 after swapping wires):

| Port | Coil | Pulse Hreg | Period Hreg | Local pot/switch |
|------|------|------------|-------------|------------------|
| 1 | 1 | 1 | 2 | yes |
| 2 | 2 | 3 | 4 | yes |
| 3 | 3 | 5 | 6 | no |
| 4 | 4 | 7 | 8 | no |

Modbus works on every port. Pot/switch mode is channels 1–2 only. This config
is **port 1**. If the injector is on port 4, change `FIRST_ELEMENT` in
[`microject.mb2hal`](../microject.mb2hal) to coil=3, pulse=6, period=7
(0-based).

---

## Pipeline

```
M101 P<Hz> Q<duty%>     (or M102 from coolant_tools.ini)
        │
        ▼
 analog E4 / E5
        │
        ▼
 coolant.hal
   period_ms = 1000 / Hz
   pulse_ms  = period_ms * duty / 100
        │
        ├─ microject.coolant_period.00.float  → Hreg 2
        └─ microject.coolant_pulse.00.float   → Hreg 1  (0 when M9)

M8 / M7  →  microject.coolant_run.00.bit  → coil 1
M9       →  coil 0  and  pulse 0
```

H100 stays on `/dev/ttyUSB0`. Two mb2hal processes, two UARTs.

`M101 P10 Q1` → 100 ms period, 1 ms pulse (firmware default). This is an
**injector pulse**, not 20 kHz servo PWM.

---

## G-code

| Code | Role |
|------|------|
| **M101 P Q** | Hz and duty % → period/pulse ms on the wire |
| **M102** | Load `probe_basic/coolant_tools.ini` for the current tool, then same as M101 |
| **M8 / M7** | Coil 1 ON |
| **M9** | Coil 1 OFF, pulse length 0. Abort already issues M9 |

```
M102
M8
...
M9
```

---

## Analog channels

`num_aio=7`. Laser owns E0–E3.

| E | Pin | Meaning |
|---|-----|---------|
| 4 | `motion.analog-out-04` | Pulse rate (Hz), clamped 1–50 in HAL |
| 5 | `motion.analog-out-05` | Duty (%) |
| 6 | `motion.analog-out-06` | Pressure — **not sent** (no register yet) |

If Hregs are 0.1 ms counts, set `[COOLANT]PULSE_SCALE` / `PERIOD_SCALE` to 10.

---

## Bench (no LinuxCNC)

```bash
# coil 1 on
mbpoll /dev/ttyUSB1 -v -m rtu -a 8 -b 19200 -P even -t 0 -r 1 1
# pulse 1 ms, period 100 ms (port 1)
mbpoll /dev/ttyUSB1 -v -m rtu -a 8 -b 19200 -P even -t 4 -r 1 1
mbpoll /dev/ttyUSB1 -v -m rtu -a 8 -b 19200 -P even -t 4 -r 2 100
```

Windows (free): QModMaster, OpenModScan, Modbus Tester. `modbuslens` does
diagnostics `mbpoll` does not.

LinuxCNC: `M8` then `halcmd getp microject.coolant_run.00.bit` and
`microject.coolant_pulse.00.float` / `coolant_period.00.float`.

---

## Wiring

```
PC
 ├─ USB–RS-485  /dev/ttyUSB0   38400 8N1   H100 VFD slave 1
 └─ USB–RS-485  /dev/ttyUSB1   19200 8E1   Microject slave 8
```

24 V to the PCB. Injector on **port 1** (GM0521994 is a 12 V coil; the board
drives it). udev: two adapters swap tty numbers across reboots unless bound by
serial.

---

## Files

| Path | Role |
|------|------|
| `microject.mb2hal` | Coil 1 + H1 pulse + H2 period |
| `coolant.hal` | Hz/duty → ms, flood/mist → coil |
| `h100.mb2hal` | VFD only |
| `probe_basic/coolant_tools.ini` | Per-tool Hz/duty (default 10 Hz / 1 %) |
