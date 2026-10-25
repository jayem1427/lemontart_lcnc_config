# PWM coolant (Modbus)

Machine-side PWM coolant: **frequency, duty cycle, optional pressure**. Fusion still
emits stock **M7 / M8 / M9**. The mill owns the analog setpoints.

This is **not** Probe Basic’s programmable nozzle aimer (`program_coolant.ngc`,
`#3000`–`#3003`, `M68 E0` angle). Leave that off (`#3000 = 0`). It would collide
with the laser mailbox on E0.

---

## Pipeline

```
Fusion flood/mist          mill table (coolant_tools.ini)
  M8 / M7 / M9               T3 → 20000 Hz, 35 %, 0 psi
        │                            │
        │                            │ M600 / M102
        │                            ▼
        │                     M68 E4/E5/E6  (setpoints)
        ▼                            │
 iocontrol coolant-flood/mist        │
        │                            │
        └──────── enable gate ───────┤
                                     ▼
                    coolant.hal scale + mux
                                     ▼
              mb2hal.coolant_{freq,duty,psi}.00.float
                                     ▼
              RS-485  /dev/ttyUSB0  slave 2  (same dongle as H100)
```

G-code never contains Modbus. `M68` pokes HAL floats; `mb2hal` writes registers,
same pattern as the H100 VFD (`S`/`M3` → `custom.hal` → register 513).

---

## G-code

| Code | Role |
|------|------|
| **M101 P Q R** | Set freq (Hz), duty (%), pressure (psi). Any word may be omitted. |
| **M102** | Load the recipe for the current tool (`#5400`) from `probe_basic/coolant_tools.ini` |
| **M8 / M7** | Enable (flood and/or mist). HAL ORs them. |
| **M9** | Disable. HAL forces **duty and pressure to 0**; frequency stays latched. |

Examples:

```
M101 P20000 Q35 R80
M8
...
M9
```

MDI override mid-program is `M101` with only the words you want to change.

`on_abort.ngc` already issues `M9`.

---

## Analog channels

`num_aio=7`. Laser and coolant must not share pins.

| E | Pin | Owner |
|---|-----|--------|
| 0 | `motion.analog-out-00` | Laser result (length / diameter) |
| 1 | `motion.analog-out-01` | Laser success flag |
| 2 | `motion.analog-out-02` | Laser per-hit X |
| 3 | `motion.analog-out-03` | Laser packed hit event |
| **4** | `motion.analog-out-04` | **Coolant frequency (Hz)** |
| **5** | `motion.analog-out-05` | **Coolant duty (%)** |
| **6** | `motion.analog-out-06` | **Coolant pressure (psi)** |

---

## Per-tool table

Edit [`probe_basic/coolant_tools.ini`](../probe_basic/coolant_tools.ini). Do not hijack
tool-table I/J (lathe leftover fields; Probe Basic columns are `TDZR`).

```ini
[DEFAULT]
FREQ = 20000
DUTY = 30
PRESSURE = 0

[T3]
DUTY = 35
```

Unspecified keys inherit `[DEFAULT]`. Tool 0 (empty spindle) always writes zeros.
T99 is listed dry so the probe never sprays.

M102 runs at the end of **M600**, Probe Basic load-spindle / M6 helpers, and
carousel `toolchange.ngc`. The Fusion post emits **M102** immediately before M7/M8
(`applyToolCoolant`, on by default).

---

## Wiring (RS-485)

One USB–RS-485 dongle. Daisy-chain **A/A, B/B, GND/GND** — not a star, not a ring.

```
USB dongle ──── H100 VFD (slave 1) ──── coolant box (slave 2)
 /dev/ttyUSB0      38400 8N1               38400 8N1
```

Terminate 120 Ω at the far end of the whole cable. Unique slave IDs. Match baud
with the VFD (`h100.mb2hal`).

A second dongle is only needed if baud/parity cannot match, the pressure device
is analog (4–20 mA) rather than Modbus, or you want a separate master.

---

## Registers (placeholders)

`h100.mb2hal` **TRANSACTION_04–06** write holding registers **100 / 101 / 102** on
**slave 2** as stand-ins. Replace `FIRST_ELEMENT` and `MB_SLAVE_ID` from the
coolant manual. Scale in `[COOLANT]` if the device wants 0.1 Hz or 0–1000 duty:

```ini
[COOLANT]
FREQ_SCALE = 1.0
DUTY_SCALE = 1.0
PRESSURE_SCALE = 1.0
```

Function code is `06` (single register), matching the H100 writes. Slow update
(2 Hz) so VFD 10 Hz freq-set is not starved.

**No coolant box on the bus yet?** Failed slave-2 transactions are noisy and add
a little bus latency. To disable: comment TRANSACTION_04–06, set
`TOTAL_TRANSACTIONS = 4`, comment `HALFILE = coolant.hal`.

---

## Bring-up

1. Land RS-485 on slave 2 (or disable txs as above).
2. Set real register addresses in `h100.mb2hal`.
3. Restart LinuxCNC.
4. MDI: `M101 P20000 Q10` then `M8`. Confirm with
   `halcmd show pin mb2hal.coolant_duty` and `halcmd show pin motion.analog-out-05`.
5. `M9` — gated duty/pressure pins should go to 0; analog-out-05 can stay at 10
   (the mux zeros the Modbus write).
6. `T3 M102` (tool already in spindle) — analog-out-04/05 should match
   `coolant_tools.ini` `[T3]`.
7. Edit recipes; no HAL rebuild needed (M102 re-reads the file).

Pressure: if the box has no pressure register, leave TRANSACTION_06 pointed at a
harmless register or stop netting `coolant-psi-modbus` until an EPR exists.
Closed-loop air EPRs (SMC ITV class) are the usual analog pressure part for
atomizing air; liquid through-tool pressure is usually a pump VFD, not an air
ITV. See the earlier design notes in the agent thread / this file’s “Hardware”
intent: command PSI, device holds PSI.

---

## Files

| Path | Role |
|------|------|
| `ethercat_mill.ini` `[COOLANT]`, `REMAP=M101/M102`, `[PYTHON]` | Setpoints + remap |
| `ethercat_mill.hal` `num_aio=7` | Analog channels E0–E6 |
| `coolant.hal` | Enable mux, scale, nets to mb2hal |
| `h100.mb2hal` TX 04–06 | Coolant register writes |
| `probe_basic/subroutines/m101.ngc` | M101 → M68 E4/E5/E6 |
| `probe_basic/python/coolant_remap.py` | M102 |
| `probe_basic/python/coolant_profiles.py` | INI parser |
| `probe_basic/coolant_tools.ini` | Per-tool recipes |
| `post-processor/linuxcnc-djr.cps` | Optional M102 before M7/M8 |
| `config/logging/signals.json` | Coolant channels in the CSV |

Do not remap M7/M8/M9 — Probe Basic buttons, the pendant, and abort all assume
stock coolant bits.
