# Block probe session, 2026-11-18 (evening)

Repeatability and surface-map baseline for an aluminium block in the vise.
**Rerun the same measurements on 2026-11-19** to compare after a power-off night.

## Conditions

| Item | Value |
|------|-------|
| Chiller temperature (room-temp proxy) | **17.1 °C**, read at the end of the session |
| Machine | Just restarted after the jog-during-homing crash, homed, then ran about 1 h |
| Probe | Touch probe T99, 2 mm ball, cal offset `#3032 = 0.034271` |
| Probe feeds | fast 200, slow 50, traverse 800 mm/min (`#3015–3017`) |
| Work offsets set from this session | G54 and G55: X **97.013**, Y **141.8911** (machine). Z untouched |

## Results

| Measurement | Mean | Std dev | Spread | File |
|-------------|------|---------|--------|------|
| X width | 50.7416 mm | 1.4 µm | 4.3 µm | `ridge_x.csv` |
| X center | machine 97.0122 | 0.5 µm | 1.8 µm | `ridge_x.csv` |
| Y width | 50.8083 mm | 0.7 µm | 1.9 µm | `ridge_y.csv` |
| Y center | machine 141.8911 | 0.5 µm | 1.5 µm | `ridge_y.csv` |
| Top surface, 16 × 16 | 0.84 mm range, 13.7 µm/mm tilt in Y, 5.0 µm/mm in X; 149 µm P-V / 32 µm RMS with tilt removed | | | `z_grid_16x16.csv` |

Hand-found X center from two edge touches (71.643, 122.383) was 97.013,
1 µm from the probe mean. Y edges drifted about +1 µm together after
Y run 3 (width unchanged), which is thermal or settling, not probe noise.

`plots.html` is the chart page (open in a browser). The published copy is
on claude.ai as "Block Probe Repeatability".

## How it was measured

- **X and Y:** Probe Basic `probe_ridge_x/y.ngc`, measure-only (`#3030 = 1`),
  hint 51 (X) and 53 (Y), max search `#3018 = 10`, started over the center
  about 2 mm above the top. Y center was found first with a coarse pass.
- **Z map:** G54 X/Y −22.5…+22.5 at 3 mm pitch, serpentine by row, travel at
  machine Z −15.37 (about 2 mm above the top) with G38.3, fast touch
  G38.2 Z−4 at F200, back off 0.5, slow touch F50, `z_machine` = probed Z.

## Repeating it

LinuxCNC (tpnext) running, homed, T99 loaded, G54 active and unchanged.
Jog the probe over G54 X0 Y0 about 2 mm above the top first.

```bash
source ~/src/linuxcnc-tpnext/scripts/rip-environment
cd ~/linuxcnc/configs/ethercat_mill
D=logs/metrology/20261119_block; mkdir -p $D
python3 scripts/block_ridge_repeat.py X $PWD/$D/ridge_x.csv --hint 51
python3 scripts/block_ridge_repeat.py Y $PWD/$D/ridge_y.csv --hint 53
python3 scripts/block_z_grid.py $D/z_grid_16x16.csv
```

Write down the chiller temperature, and how long the machine has been on, before you start.
