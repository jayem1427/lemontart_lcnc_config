# Block probe repeat, 2026-11-24

| Item | Value |
|------|-------|
| Spindle/chiller temperature | **15.9 °C** |
| Before this run | The input board failed and was repaired (all DIs read TRUE twice). The touch probe was worked on ("fixed"), and the machine re-homed |
| T99 | Length 45.0422 now set (see `../20261123_block/README.md`, still to be verified) |
| G54 | X 97.013, Y 141.8911, Z −62.3905 (new Z) |

| | 11-18 (17.1 °C) | 11-23 cleaned (14.9 °C) | 11-24 (15.9 °C) |
|---|---|---|---|
| X center | −0.0008 | +0.0343 | **+0.0590** |
| X width | 50.7416 | 50.7467 | **50.7495** |
| Y center | 0.0000 | −0.0054 | **+0.0442** |
| Y width | 50.8083 | 50.8075 | **50.8169** |

Both centers moved (X +25 µm, Y +50 µm since 11-23), and both widths grew by about 8–9 µm.
The probe repair is the most likely cause: stylus or probe position in the collet changed, so
tip runout (shifts centers) and effective tip size (shifts widths) changed together.
