# PWM coolant (Microject)

Dan Mills **Microject** injector driver: an automotive fuel injector pulsed as
an MQL valve. Fusion still emits stock **M7 / M8 / M9**. The mill owns enable
and (later) the pulse recipe.

**Never configured mb2hal?** **[MB2HAL.md](MB2HAL.md)** is the driver tutorial.
This page is the mill-specific map.

This is **not** Probe Basic’s programmable nozzle aimer (`program_coolant.ngc`,
`#3000`–`#3003`, `M68 E0` angle). Leave that off (`#3000 = 0`).

---

## What is live today vs still pending

| Piece | Status |
|-------|--------|
| Serial | **Known:** 19200 **8E1**, slave **8** (DIP switches can change this) |
| Enable | **Known:** coil **#1**. `M8`/`M7` → coil ON, `M9` → coil OFF |
| Firmware default pulse | **Known:** 1 ms on, 100 ms period (10 Hz, 1 % duty) until you write holding registers |
| Watchdog | **Known:** coil drops **5 s** after the last valid Modbus message |
| Holding registers (on-time, period, pressure) | **Not in the first dump** — do not guess. M101/M102 still set analog pins for later |
| Share the H100 dongle | **No, not at defaults.** H100 is 38400 8N1. Second USB–RS-485 adapter (`/dev/ttyUSB1`) |

Bring-up with the PCB in hand: power **24 V**, Modbus on USB1, `M8`. You should
get a 1 % dribble without writing any holding registers.

Bench, LinuxCNC not required (Dan’s command, 8E1 added):

```bash
mbpoll /dev/ttyUSB1 -v -m rtu -a 8 -b 19200 -P even -t 0 -r 1 1
```

`modbuslens` is useful for diagnostics `mbpoll` does not do.

---

## Pipeline

```
Fusion M8 / M7 / M9          mill table (coolant_tools.ini)  [setpoints, later]
        │                            │
        ▼                            ▼
 iocontrol coolant-flood/mist     M101 / M102 → analog E4/E5/E6
        │                            (not on the wire yet)
        ▼
 coolant.hal  or2 (flood OR mist)
        │
        ▼
 microject.coolant_run.00.bit     fnct_05 coil 1
        │
        ▼
 microject.mb2hal   /dev/ttyUSB1   19200 8E1   slave 8
        │
        ▼
 Microject PCB  →  fuel injector
```

The H100 VFD stays on `/dev/ttyUSB0` via `h100.mb2hal`. Two `loadusr mb2hal`
processes, two UARTs, two masters on **two buses** — that is allowed. Two
masters on **one** UART is not.

---

## G-code

| Code | Role |
|------|------|
| **M8 / M7** | Coil 1 ON (firmware default 1 ms / 100 ms pulse) |
| **M9** | Coil 1 OFF. `on_abort.ngc` already issues M9 |
| **M101 P Q R** | Set analog E4/E5/E6 (Hz, duty %, psi). **Not sent to the board** until holding-register addresses exist |
| **M102** | Load `probe_basic/coolant_tools.ini` for the current tool into those analog pins |

```
M8          (spray at firmware default)
...
M9
```

Once on-time/period registers are known, `M101 P10 Q1` will mean 10 Hz / 1 %.
Do **not** use 20 kHz recipes — this is an injector pulse, not a servo PWM.

---

## Analog channels (setpoints, parked until registers land)

`num_aio=7`. Laser owns E0–E3.

| E | Pin | Owner |
|---|-----|--------|
| 0–3 | `motion.analog-out-00` … `03` | Laser mailbox |
| 4 | `motion.analog-out-04` | Injector pulse rate (Hz) — not on the wire yet |
| 5 | `motion.analog-out-05` | Duty (%) — not on the wire yet |
| 6 | `motion.analog-out-06` | Pressure (psi) — board may not have this |

---

## Per-tool table

[`probe_basic/coolant_tools.ini`](../probe_basic/coolant_tools.ini) defaults match
firmware (10 Hz, 1 %). M102 still runs after M600 so the analog pins track the
tool; they just do not reach Modbus yet.

---

## Wiring

```
PC
 ├─ USB–RS-485  /dev/ttyUSB0   38400 8N1   H100 VFD slave 1
 └─ USB–RS-485  /dev/ttyUSB1   19200 8E1   Microject slave 8
```

Microject A/B/GND to the **second** dongle only. 24 V to the PCB. Injector
plug to the board (GM0521994 is a 12 V automotive coil — the PCB drives it;
do not put 24 V across the injector yourself).

udev: two adapters will swap `ttyUSB0`/`ttyUSB1` across reboots unless you
bind by serial. If the VFD suddenly “is” the injector, ports flipped.

**Optional later:** set Microject DIP switches to 38400 8N1 and daisy-chain on
the H100 pair as a second slave. Then one dongle, one `mb2hal` file, two
`MB_SLAVE_ID`s. Not the default.

---

## Files

| Path | Role |
|------|------|
| `microject.mb2hal` | 19200 8E1, slave 8, coil 1 write |
| `coolant.hal` | `loadusr` microject + flood/mist → coil |
| `h100.mb2hal` | VFD only (unchanged serial) |
| `ethercat_mill.ini` `[COOLANT]` | Documented serial / slave 8 |
| `m101.ngc` / `coolant_remap.py` | Analog setpoints for later register writes |
| `probe_basic/coolant_tools.ini` | Per-tool Hz/duty (10 Hz / 1 % default) |

Do not remap M7/M8/M9. Do not add placeholder `fnct_06` writes — timeouts can
starve coil 1 and the 5 s watchdog will shut the injector off.
