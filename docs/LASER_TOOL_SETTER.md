# Laser tool setter (Kexin DS-5V-M)

Probe Basic tab + HAL pin + NGC macros for the **Kexin DS-5V-M** U-slot laser
tool setter on this mill.

**See also:** [README.md](../README.md) (short summary) · [TOOLSETTER.md](TOOLSETTER.md) (contact setter / M600) · [PROBE_BASIC_UI.md](PROBE_BASIC_UI.md)

## Status

| Feature | State |
|---------|--------|
| HAL wiring (Slave 2 DI5 → `laser-beam-broken`) | Live — **not** on `motion.probe-input` |
| Live beam LED on tab | Live (`laser-beam-broken`) |
| **MEASURE DIAMETER** (tip-find → Z-drop → +X break/clear) | Live (HAL step-seek) |
| **CALIBRATE** / **MEASURE LENGTH** | Live (experimental; length ≠ contact TLO yet) |
| Oversize / remaining-travel abort | Live |
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

### HAL chain (`ethercat_mill.hal`)

```
lcec.0.2.di-5 → not.10 → laser-beam-broken
                              ↑
              laser_*.ngc reads #<_hal[laser-beam-broken]>
              tab LED polls the same pin

touch/toolsetter (or2.0) ──→ motion.probe-input   (unchanged, laser never OR'd in)
```

- `not.10` assumes DI is TRUE when the beam is **clear** (typical after high-side
  level shift into a 24 V DI). Invert is correct when broken → pin TRUE.
- If tip-find / diameter **never trips**, polarity is wrong: remove `not.10` and
  net `lcec.0.2.di-5` straight to `laser-beam-broken`.
- Laser measure macros use stepped `G1` seeks watching the HAL pin. They do
  **not** use `G38` / `motion.probe-input`, so contact probe and toolsetter
  cannot false-trip a laser measure (and laser cannot trip contact probing).
- `motmod` is loaded with `num_aio=4` so results publish via
  `M68 E0` (value) / `M68 E1` (success 0/1) → `motion.analog-out-00/01`.

## Files

| Path | Role |
|------|------|
| `probe_basic/user_tabs/laser_setter/` | Tab UI (`.ui` / `.py` / `.qss` / PNG) |
| `probe_basic/subroutines/laser_diameter.ngc` | Diameter sequence (HAL seek) |
| `probe_basic/subroutines/laser_set_diam_params.ngc` | `#5507` Z-drop, `#5508` search |
| `probe_basic/subroutines/laser_length.ngc` | Length seek (optional) |
| `probe_basic/subroutines/laser_set_beam_z.ngc` | Store BEAM Z / approach / travel |
| `probe_basic/subroutines/laser_set_start_xy.ngc` | `#5501–#5503` |
| `probe_basic/subroutines/laser_*.ngc` | Other stubs (runout, broken, air, …) |
| `ethercat_mill.hal` | DI5 → `laser-beam-broken`; contact → `probe-input` |
| `ethercat_mill.ini` | `USER_TABS_PATH`, `SUBROUTINE_PATH` |

Tab loads via `USER_TABS_PATH = probe_basic/user_tabs/` under `[DISPLAY]`.

## Parameters

Laser uses **`#5501+`** so it never stomps G30 / contact toolsetter (`#5181–#5186`)
or ATC `M66` result (`#5399`).

| # | Name | Set by | Notes |
|---|------|--------|-------|
| `#5501` | START X | `laser_set_start_xy` / CAPTURE | Slot **center** (G53 mm) |
| `#5502` | START Y | same | |
| `#5503` | PROBE RPM | same | `0` = no spindle |
| `#5504` | BEAM Z | CALIBRATE / `laser_set_beam_z` | Length only |
| `#5505` | Approach | `laser_set_beam_z` | Length default 10 mm |
| `#5506` | Max travel | `laser_set_beam_z` | Tip-find / length default 30 mm |
| `#5507` | Z DROP | `laser_set_diam_params` | Below tip before cross-feed; UI default **2 mm** |
| `#5508` | Search | `laser_set_diam_params` | Half-travel from START X; default **10 mm** |
| `#5510` | Last tip Z | diameter / length | Machine Z at tip-find |
| `#5511` | Length | length | `beam_z − trip_z` |
| `#5512` | Diameter | diameter | Raw \|X_clear − X_break\| |
| `#5513` | X break | diameter | First edge |
| `#5514` | X clear | diameter | Second edge |
| `#5515` | Success | diameter / length | `1` = measure OK (also `M68 E1`) |
| `#5519` | Z-touched | diameter / length | Gates runout / broken stubs |
| `#3004` / `#3005` | Fast / slow probe FR | `linuxcnc.var` | Used by macros |

Feeds fall back to 200 / 40 mm/min if `#3004`/`#3005` are unset.

UI always syncs **mm** into these params even when the Units combo shows inches.

## MEASURE DIAMETER (primary)

### Operator recipe

1. Restart LinuxCNC after HAL / tab changes.
2. Load a cutter; jog to a **safe Z** above the beam (tip clear).
3. CAPTURE START X/Y over the **slot center**; set **Z DROP** (default 2 mm).
4. Set PROBE RPM (`0` = static; >0 spins during tip-find and cross-feed).
5. Press **MEASURE DIAMETER**.
6. Read **DIAMETER** on the Results column (raw break→clear width). Footer shows
   success or failure text.

Tool **radius must be &lt; search** (default 10 mm → tools under ~Ø20 mm with margin).

### Motion sequence (`o<laser_diameter>`)

1. Force `G21 G90`; clear `#5515` / `M68 E1 Q0`.
2. Retract to approach Z (`#<_abs_z>`), then rapid to START XY.
3. Optional `M3` if RPM > 0.
4. **Tip-find:** stepped `G1 Z−` until `laser-beam-broken` (coarse 0.2 → fine 0.02).
5. Retract to approach Z; rapid to `START X − search`, same Y.
6. Drop to `tip_z − Z_DROP`.
7. Abort if beam already broken at X start.
8. **Edge 1:** stepped `G1 X+` until break → `#5513`.
9. Abort if remaining travel to `x_right` &lt; 0.5 mm (oversize / crash risk).
10. **Edge 2:** stepped `G1 X+` until clear → `#5514`.
11. `#5512 = |X_clear − X_break|`; reject if diameter &gt; `2×search − 0.5`.
12. `#5515 = 1`; `M68 E0 Q#5512`; `M68 E1 Q1`; retract; `M5`.

Every abort path retracts to approach Z and stops the spindle.

Measure axis is **+X through START X**. Y-oriented slots would need a later axis option.

### Result quality

- Value is **raw chord / shadow width**, not yet corrected for beam thickness
  (`BEAM DIA` calibration field is unused).
- Spinning averages flutes somewhat; static measures one orientation.
- Step size (~0.02 mm) bounds edge resolution; slower than G38 but isolated from
  the contact probe path.

## CALIBRATE / MEASURE LENGTH (optional)

Length is **not** a spindle-nose TLO yet. CALIBRATE stores machine Z with the tip
in the beam as `#5504` (requires `laser-beam-broken` TRUE). MEASURE LENGTH seeks Z
onto the beam and reports `beam_z − trip_z` (≈ 0 for the same tool you just
calibrated). Use it for polarity / seek smoke tests, not as a replacement for the
contact toolsetter.

## Tab behavior (`laser_setter.py`)

- Polls `laser-beam-broken` every 200 ms for the header LED.
- No probe-mux arming (laser is not on `motion.probe-input`).
- CAPTURE uses `actual_position` (G53); sync always writes mm.
- Diameter / length results require `M68 E1` success; failures do not set
  `_z_touched` or keep a stale diameter label update.
- Footer `lblStatus` shows BLOCKED / ERROR / DONE / FAILED messages.
- Runout / broken-check still require `_z_touched` (set only on successful measure
  or CALIBRATE).

## Troubleshooting

| Symptom | Check |
|---------|--------|
| LED never changes | `halcmd getp lcec.0.2.di-5` and `laser-beam-broken`; Select tied to GND? 5 V power? |
| Tip-find / diameter never trips | Polarity — remove `not.10`; watch `laser-beam-broken` while blocking the slot |
| “beam already broken at X start” | START XY off center, or search too small for tool |
| Remaining-travel / oversize abort | Tool larger than search window; increase `#5508` or use a smaller tool |
| Never clears on edge 2 | Tool larger than `2 × search`, or still in beam at `x_right` |
| Diameter label empty / FAILED | Watch footer status; DEBUG lines; `halcmd getp motion.analog-out-00/01` |
| Contact probe / toolsetter odd | Laser is **not** on `probe-input` anymore — check contact mux only |

## Roadmap

1. ~~HAL + LED + diameter Z-drop cross-feed~~
2. ~~Decouple laser from `motion.probe-input`; fix param collisions / safety bugs~~
3. Beam-width / master-pin calibration for true diameter
4. Optional measure axis (X vs Y)
5. UI field for search travel
6. Runout (multi-angle or spinning peak-peak)
7. Broken-tool check vs expected diameter / tip Z
8. Length → real TLO vs gauge line (master tool)
9. Air blast DO
10. Controllable Select (instead of hardwired GND)
