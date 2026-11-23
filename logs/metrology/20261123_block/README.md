# Block probe repeat, 2026-11-23

This is a repeat of [20261118_block](../20261118_block/README.md) on the same block, the same G54 and the same hints (X 51, Y 53).

| Item | Value |
|------|-------|
| Coolant / chiller temperature | **14.9 °C** (2.2 °C colder than 11-18) |
| Machine | Power-cycled since 11-18. It had been re-homed and on for about 15 minutes at the start |
| G54 | Unchanged: X 97.013, Y 141.8911 |

The CSVs are LinuxCNC `(LOG,...)` output and are space-separated, with columns `run width_g54 center_g54 minus_edge_g54 plus_edge_g54`.

## Compared with 11-18 (10 runs each)

| | 11-18 | 11-23 | Shift |
|---|---|---|---|
| X width | 50.7416 (sd 1.4 µm) | 50.7465 (sd 1.1 µm) | **+4.9 µm** |
| X center (G54) | −0.0008 (sd 0.5 µm) | +0.0327 (sd 0.7 µm) | **+33.5 µm** |
| Y width | 50.8083 (sd 0.7 µm) | 50.8076 (sd 0.7 µm) | −0.7 µm |
| Y center (G54) | 0.0000 (sd 0.5 µm) | −0.0030 (sd 0.5 µm) | −3.1 µm |

- **The X center moved 33.5 µm.** Y moved only 3 µm. A shift that size is far outside both the probe scatter and anything temperature can explain, which is about 2.5 µm of screw shrinkage at X 97 mm. That leaves the X home position, or the part moving in the vise in X.
- **The X width grew 4.9 µm.** A 2.2 °C colder aluminium block should have shrunk by about 2.6 µm, and that's only partly offset by the steel screw shrinking (+1.3 µm). This is unexplained. Possible causes are debris on an X face or the machine not having warmed up yet.
- **Y matches 11-18** to within a few µm.

## X home checks (same session)

| Run set | X center (G54) | Note |
|---|---|---|
| `ridge_x_rehome1.csv` (3) | +0.0345 | after re-homing X |
| `ridge_x_cleaned.csv` (10), `ridge_y_cleaned.csv` (10) | X +0.0343, Y −0.0054 | after cleaning the X home trigger and sensor and re-homing |

Re-homing repeats to about 2 µm, and cleaning the switch didn't change anything: X stays about +33 µm from 11-18. The vise didn't move, according to Jon. Charts are in `plots.html`.

## Touch probe Z reference (for T99 length)

Touch probe T99, loaded with tool length 0, probed Z five times at G54 X0 Y0 (machine X 97.013, Y 141.8911):
the spindle nose was at machine **Z −17.3502** when the probe tripped (sd 0.3 µm).
Once a setter-measured cutter is touched off on the same spot, the T99 length =
−17.3502 − (G54 Z offset after the touch-off). Store it with `G10 L1 P99 Z<length>`.
