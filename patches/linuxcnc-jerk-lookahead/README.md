# Closed-form S-curve lookahead queries

Drop-in replacement for the dummy-Ruckig limit queries in
[grandixximo/linuxcnc](https://github.com/grandixximo/linuxcnc) `fork`
(`src/emc/tp/sp_scurve.c`).

The Cartesian interpolator (`tpCalculateSCurveAccel`) already uses Ruckig as
an online generator. These files fix the **lookahead calculator** that tells
that generator how fast each queued segment may enter and leave.

## What changed

| Call | Old | New |
|------|-----|-----|
| `findSCurveVSpeed` | Plan rest-to-rest with a dummy `max_vel`, read peak | Quadratic / triangular closed form |
| `findSCurveMaxStartSpeed` | Feed infinite-jerk `Vs` into Ruckig; on fail return rest-to-rest peak **as success** | Invert `S = (Vs²−Ve²)/(2A) + (Vs−Ve)A/(2J)` (triangular cubic if `Δv < A²/J`) |
| `calcSCurveSpeedWithT` | Incompatible dummy target; fallback `min(AT, sqrt(A²T/J))` | `v = ½ J T²` or `A T − A²/(2J)` |
| `findSCurveVPeak` | On query fail, use `sqrt(A S)` (too fast) | On fail, return `0` |
| `nextSpeed` | Overshoot branch wrote `Δv` as the new velocity | Integrate the jerk-limited step |
| `stoppingDist` | Over-deceleration could return negative distance | Jerk toward 0 until `v = 0`; never negative |

Ruckig is still used to **follow** a segment. It is no longer used to mint
`Vpeak` / `Vs` / `V(T)`.

## Apply onto the LinuxCNC tree

From a checkout of that `fork` branch:

```bash
cp patches/linuxcnc-jerk-lookahead/src/emc/tp/sp_scurve.c \
   /path/to/linuxcnc/src/emc/tp/sp_scurve.c
patch -p1 -d /path/to/linuxcnc < patches/linuxcnc-jerk-lookahead/blendmath.h.patch
```

Rebuild `tpmod` / `motmod` as usual.

## Tests

From this repo:

```bash
python3 tests/test_scurve_queries.py
```

These check the identities the planner relies on (inverse of stopping
distance, rest-to-rest peak, `V(T)`, `nextSpeed` / `stoppingDist` regressions).
They do not rebuild LinuxCNC.
