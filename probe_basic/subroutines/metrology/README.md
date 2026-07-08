# Metrology Probe Macros

These files document the small test macros used for probing and homing
repeatability checks.

**See also:** [GETTING_STARTED.md](../../../GETTING_STARTED.md) (troubleshooting) · [TOOLSETTER.md](../../../TOOLSETTER.md) (probe tool T99 / `#3014`)

The runnable copies remain one directory up in `probe_basic/subroutines/`
because `ethercat_mill.ini` currently has:

```ini
SUBROUTINE_PATH = .:probe_basic/subroutines
```

LinuxCNC does not search nested subfolders from that entry, so keeping runnable
copies in the parent folder preserves the tested MDI calls.

## Macros

- `probe_z_three_samples.ngc`
  - Run: `o<probe_z_three_samples> call`
  - Takes three Z probe hits.
  - Prints one measured machine Z value per hit.
  - Intended for manual tabulation, especially after manual homing cycles.

- `probe_z_repeat_stats.ngc`
  - Run: `o<probe_z_repeat_stats> call`
  - Optional sample count: `o<probe_z_repeat_stats> call [10]`
  - Repeats Z probing and reports count, mean, sample standard deviation, and
    population standard deviation.

## Required Setup

Before running either macro:

1. Load the touch probe tool. This config uses the Probe Basic probe tool number
   from `#3014`, usually T99.
2. Click Probe Basic **UPDATE PROBE PARAMS** so `#3014..#3030` are populated.
3. Jog to a safe starting height above the surface, within max Z distance
   `#3020`.
4. Confirm the probe input behaves correctly before motion.

Both macros force `#3030 = 1` while running, so they measure only and do not set
or rewrite WCO Z.
