# Laser tool setter (Kexin DS-5V-M)

Probe Basic tab + HAL mux + NGC macros for the **Kexin DS-5V-M** U-slot laser
tool setter on this mill.

**See also:** [README.md](../README.md) (short summary) · [TOOLSETTER.md](TOOLSETTER.md) (contact setter / M600) · [PROBE_BASIC_UI.md](PROBE_BASIC_UI.md)

## Status

| Feature | State |
|---------|--------|
| HAL wiring (Slave 2 DI5 → probe mux) | Live |
| Live beam LED on tab | Live (`laser-beam-broken`) |
| **MEASURE DIAMETER** (tip-find → Z-drop → +X break/clear) | Live |
| **CALIBRATE** / **MEASURE LENGTH** | Live (experimental; length ≠ contact TLO yet) |
| MEASURE RUNOUT | Skeleton |
| BROKEN TOOL CHECK | Skeleton |
| AIR BLAST | Skeleton |

## Hardware

| Item | Spec / note |
|------|-------------|
| Sensor | Kexin **DS-5V-M** beam-break U-slot |
| Tool range (spec) | Ø 0.05–8 mm (larger tools may still trip; search travel limits diameter measure) |
| Output | HCMOS **5 V push-pull** — clear ≈ 5 V, broken ≈ 0 V |
| Select | Separate from power: **0 V = ON**, float/5 V = OFF → **tie Select to GND** (or drive later) |
| Power | **5 V** / 0 V (do **not** feed A6 24 V into the sensor) |
| Level shift | Required 5 V → 24 V before the A6 digital input |

Factory body LED: red ON when clear, OFF when broken. The tab LED mirrors HAL
state only (clear vs broken) — do not treat body LED colors as the UI contract.

## Wiring (this mill)

| Signal | Connection |
|--------|------------|
| Sensor signal | Slave **2** `lcec.0.2.di-5` — CN1 **DB15 pin 11** |
| Select (enable) | Tie to **GND** |
| Power | **5 V** / 0 V |
| Probe mux arm | Userspace `setp and2.6.in0 1` while a laser measure runs |

### HAL chain (`ethercat_mill.hal`)

```
lcec.0.2.di-5 → not.10 → laser-beam-broken → and2.6.in1
                                      and2.6.in0 ← setp (arm)
                                      and2.6.out → or2.2.in1
touch/toolsetter (or2.0) ─────────────→ or2.2.in0
                                      or2.2.out → motion.probe-input
```

- `not.10` assumes DI is TRUE when the beam is **clear** (typical after high-side
  level shift into a 24 V DI). Invert is correct when broken → probe trip TRUE.
- If tip-find / diameter **never trips**, polarity is wrong: remove `not.10` and
  net `lcec.0.2.di-5` straight to `laser-beam-broken`.
- Laser is OR'd into `motion.probe-input` **only while armed**. Contact touch
  probe / toolsetter routing is unchanged (T99 → DI5, other tools → DI2).
- `motmod` is loaded with `num_aio=4` so diameter can publish the result via
  `M68 E0` → `motion.analog-out-00` / `stat.aout[0]`.

**Do not** use a HAL `constant` for the arm bit — `constant.out` is float and
will type-mismatch into `and2.in0`.

## Files

| Path | Role |
|------|------|
| `probe_basic/user_tabs/laser_setter/` | Tab UI (`.ui` / `.py` / `.qss` / PNG) |
| `probe_basic/subroutines/laser_diameter.ngc` | Diameter sequence |
| `probe_basic/subroutines/laser_set_diam_params.ngc` | `#5187` Z-drop, `#5188` search |
| `probe_basic/subroutines/laser_length.ngc` | Length G38 (optional) |
| `probe_basic/subroutines/laser_set_beam_z.ngc` | Store BEAM Z / approach / travel |
| `probe_basic/subroutines/laser_set_start_xy.ngc` | `#5181–#5183` |
| `probe_basic/subroutines/laser_*.ngc` | Other stubs (runout, broken, air, …) |
| `ethercat_mill.hal` | DI5 + mux nets |
| `ethercat_mill.ini` | `USER_TABS_PATH`, `SUBROUTINE_PATH` |

Tab loads via `USER_TABS_PATH = probe_basic/user_tabs/` under `[DISPLAY]`.

## Parameters

| # | Name | Set by | Notes |
|---|------|--------|-------|
| `#5181` | START X | `laser_set_start_xy` / CAPTURE | Slot **center** (G53 mm) |
| `#5182` | START Y | same | |
| `#5183` | PROBE RPM | same | `0` = no spindle |
| `#5184` | BEAM Z | CALIBRATE / `laser_set_beam_z` | Length only |
| `#5185` | Approach | `laser_set_beam_z` | Length default 10 mm |
| `#5186` | Max travel | `laser_set_beam_z` | Tip-find / length default 30 mm |
| `#5187` | Z DROP | `laser_set_diam_params` | Below tip before cross-feed; UI default **2 mm** |
| `#5188` | Search | `laser_set_diam_params` | Half-travel from START X; default **10 mm** (not on UI yet) |
| `#5390` | Last tip Z | diameter / length | Machine Z at tip-find |
| `#5392` | Diameter | diameter | Raw \|X_clear − X_break\| |
| `#5393` | X break | diameter | First edge |
| `#5394` | X clear | diameter | Second edge |
| `#5399` | Z-touched | diameter / length | Gates runout / broken stubs |
| `#3004` / `#3005` | Fast / slow probe FR | `linuxcnc.var` | Used by macros |

Feeds fall back to 200 / 40 mm/min if `#3004`/`#3005` are unset.

## MEASURE DIAMETER (primary)

### Operator recipe

1. Restart LinuxCNC after HAL / tab changes.
2. Load a cutter; jog to a **safe Z** above the beam (tip clear).
3. CAPTURE START X/Y over the **slot center**; set **Z DROP** (default 2 mm).
4. Set PROBE RPM (`0` = static; &gt;0 spins during tip-find and cross-feed).
5. Press **MEASURE DIAMETER**.
6. Read **DIAMETER** on the Results column (raw break→clear width).

Tool **radius must be &lt; search** (default 10 mm → tools under ~Ø20 mm with margin).

### Motion sequence (`o<laser_diameter>`)

1. Rapid to START XY at current Z (`#<_abs_z>` = approach height).
2. Optional `M3` if RPM &gt; 0.
3. **Tip-find:** `G53 G38.2 Z` down until beam breaks → `#5390` tip Z.
4. Retract to approach Z; rapid to `START X − search`, same Y.
5. Drop to `tip_z − Z_DROP`.
6. Abort if `motion.probe-input` already TRUE (start not clear).
7. **Edge 1:** `G53 G38.3 X` toward `START X + search` until break → `#5393`.
8. **Edge 2:** `G53 G38.5 X` continue until clear → `#5394`.
9. `#5392 = |X_clear − X_break|`; `M68 E0 Q#5392` for the UI; retract; `M5`.

Measure axis is **+X through START X**. Y-oriented slots would need a later axis option.

### Result quality

- Value is **raw chord / shadow width**, not yet corrected for beam thickness
  (`BEAM DIA` calibration field is unused).
- Spinning averages flutes somewhat; static measures one orientation.
- Compare to a known pin later for beam-width / scale calibration — not wired yet.

## CALIBRATE / MEASURE LENGTH (optional)

Length is **not** a spindle-nose TLO yet. CALIBRATE stores machine Z with the tip
in the beam as `#5184`. MEASURE LENGTH seeks Z onto the beam and reports
`beam_z − trip_z` (≈ 0 for the same tool you just calibrated). Use it for
polarity / G38 smoke tests, not as a replacement for the contact toolsetter.

## Tab behavior (`laser_setter.py`)

- Polls `laser-beam-broken` every 200 ms for the header LED.
- Arms `and2.6.in0` around laser measure MDI; always disarms in `finally`.
- Diameter does **not** require prior CALIBRATE (self-contained tip-find).
- Runout / broken-check still require `_z_touched` (set by diameter or length).
- Diameter result: `stat.aout[0]` after `M68`, with `halcmd getp motion.analog-out-00` fallback.

## Troubleshooting

| Symptom | Check |
|---------|--------|
| LinuxCNC fails on load: type mismatch `laser-probe-arm` | Old HAL; arm must be `setp and2.6.in0`, not a float `constant` |
| LED never changes | `halcmd getp lcec.0.2.di-5` and `laser-beam-broken`; Select tied to GND? 5 V power? |
| Tip-find / diameter never trips | Polarity — remove `not.10`; confirm mux armed during measure |
| “beam already broken at X start” | START XY off center, or search too small for tool |
| Never clears on edge 2 | Tool larger than `2 × search`, or still in beam at `x_right` |
| Diameter label empty | `num_aio=4` on `motmod`; watch DEBUG for `#5392` |
| Contact probe / toolsetter odd while testing | Laser mux only active when armed; if stuck armed: `halcmd setp and2.6.in0 0` |

## Roadmap

1. ~~HAL + LED + diameter Z-drop cross-feed~~
2. Beam-width / master-pin calibration for true diameter
3. Optional measure axis (X vs Y)
4. UI field for search travel
5. Runout (multi-angle or spinning peak-peak)
6. Broken-tool check vs expected diameter / tip Z
7. Length → real TLO vs gauge line (master tool)
8. Air blast DO
9. Controllable Select (instead of hardwired GND)
