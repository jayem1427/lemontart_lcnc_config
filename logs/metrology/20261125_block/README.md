# Probe 0°/180° rotation study, 2026-11-25

**Question:** is the 11-24 center shift (X +59, Y +44 µm against 11-18) the touch probe's tip offset
from the spindle axis, changed when the probe was repaired?

**Predictions if it is:**
1. The 0° and 180° centers differ by twice the tip offset (tens of µm).
2. The 0°/180° average stays put across pairs and across re-seating the probe.
3. Width doesn't flip with rotation. The ~8–9 µm width growth since 11-18 is a separate effect.

**If not:**
- (A) 0° ≈ 180°: the shift is in the machine or the block. Test homing at two latch speeds, or probe a fixed reference.
- (B) flips, but the average is off 11-18: both are real.
- (C) averages wander: the probe is turning in the collet, the stylus is loose, or the spindle has play.
- (D) width differs by orientation: the probe triggers unevenly by direction (lobing).

**Protocol:** interleave 0/180/0/180 (at least 3 pairs). Then pull and re-seat the probe, and do one more pair.
Mark both the probe body and the spindle nose. Record the temperature.

Setup: T99 length 45.0422, G54 X97.013 Y141.8911 Z−62.3905, hints 51/53, travel F5000.

| Set | Temp | X center | X width | Y center | Y width | File |
|-----|------|----------|---------|----------|---------|------|
| 0° #1 (10×) | 17.0 °C | +0.0559 | 50.7485 | +0.0447 | 50.8107 | `ridge_{x,y}_0deg.csv` |
| 180° #1 (10×) | ~17 °C | +0.0635 | 50.7440 | +0.0475 | 50.8118 | `ridge_{x,y}_180deg.csv` |

## Result after the first pair: case A (0° ≈ 180°)

| | 0° | 180° | Split | Average | Tip offset (split / 2) |
|---|---|---|---|---|---|
| X center | +56.0 µm | +63.5 µm | 7.5 µm | **+59.7 µm** | ~3.8 µm |
| Y center | +44.7 µm | +47.5 µm | 2.8 µm | **+46.1 µm** | ~1.4 µm |
| X width | 50.7485 | 50.7440 | −4.5 µm | | |
| Y width | 50.8106 | 50.8118 | +1.2 µm | | |

The probe tip is within about 4 µm of the spindle axis, so tip offset can't explain the 60 / 46 µm
shift. The average sits where the single readings did. **The hypothesis is rejected:** the shift is in
the machine coordinate frame or the block (case A). The top suspect is a change in home latching
after the input-board repair; Y moved about 50 µm between 11-23 and 11-24, across the board failure.
Next: home at two very different latch speeds and see if the center moves, and/or probe a fixed
reference that's independent of the block.

The X width changes 4.5 µm with orientation, a little direction-dependent triggering (case D, mild).
