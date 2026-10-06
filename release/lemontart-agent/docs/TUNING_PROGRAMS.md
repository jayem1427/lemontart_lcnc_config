# Example tuning and test G-code

Semi-auto servo tuning and M600 validation need **frozen** G-code programs under
your `PROGRAM_PREFIX` directory. This repo no longer ships an `nc_files/` tree
(personal paths differ per machine) — copy the examples below into **your** NC
folder and point `PROGRAM_PREFIX` in `ethercat_mill.ini` at it.

**Related:** [SEMI_AUTO_TUNING.md](SEMI_AUTO_TUNING.md) · [ONE_CLICK_TUNING.md](ONE_CLICK_TUNING.md) ·
[TOOLSETTER.md](TOOLSETTER.md)

---

## Setup

1. Create a directory for part programs, e.g. `~/linuxcnc/nc_files/`.
2. In `ethercat_mill.ini`, set:

   ```ini
   PROGRAM_PREFIX = /home/you/linuxcnc/nc_files
   ```

3. Save each example below as the named file in that directory.
4. In Probe Basic, **File → Open** can use `OPEN_FILE` in
   `probe_basic/pb_required_ini_settings.ini` (edit for your path).

One-click auto-tune **does not** need these files — it generates motion from
`a6_auto_tune.py`. You only need frozen NGC for **semi-auto** (START PLOT → run
program) and optional **signal logging** campaigns.

---

## Frozen tuning stimuli

**Rule:** pick one envelope per axis and do not edit it mid-campaign, or FERR
plots and LLM comparisons lie. Adjust stroke/feed to your machine envelope before
the first session.

### `x_tuning.ngc` — X axis

10× 0 ↔ 80 mm @ F1000, 0.5 s dwell each end.

```ngc
; Frozen semi-auto tuning stimulus — do not edit mid-campaign.
; Servo Tuning → START PLOT → run this program (see SEMI_AUTO_TUNING.md).
G21
G90
G0 X0

#1 = 10
o100 while [#1 gt 0]
  G1 X80 F1000
  G4 P0.5
  G1 X0 F1000
  G4 P0.5
  #1 = [#1 - 1]
o100 endwhile

M2
```

### `y_tuning.ngc` — Y axis

10× 0 ↔ 15 mm @ F30000 (short Y travel on this mill).

```ngc
G21
G90
G0 Y0

#1 = 10
o100 while [#1 gt 0]
  G1 Y15 F30000
  G4 P0.5
  G1 Y0 F30000
  G4 P0.5
  #1 = [#1 - 1]
o100 endwhile

M2
```

### `z_tuning.ngc` — Z axis

Single 0 ↔ 15 mm cycle @ F10000 (Z moves are conservative).

```ngc
(z tuning - frozen semi-auto stimulus)
G21
G90
G0 Z0

#1 = 1
o200 while [#1 GT 0]
  G1 Z15 F10000
  G4 P0.5
  G1 Z0 F10000
  G4 P0.5
  #1 = [#1 - 1]
o200 endwhile

M2
```

### `a_tuning.ngc` — A axis

10× 0 ↔ 90° @ F3600.

```ngc
G90
G0 A0

#1 = 10
o100 while [#1 gt 0]
  G1 A90 F3600
  G4 P0.5
  G1 A0 F3600
  G4 P0.5
  #1 = [#1 - 1]
o100 endwhile

M2
```

### Operator workflow

1. Home / enable. Servo Tuning → select axis → **START PLOT**.
2. AUTO → open `<axis>_tuning.ngc` → Cycle Start.
3. **COPY PLOT** + **COPY TUNING** → paste into LLM with [SERVO_TUNING_LLM.md](SERVO_TUNING_LLM.md).
4. Edit Pending → **APPLY TO DRIVE** → repeat.

Or skip the clipboard loop: **ONE-CLICK TUNE** on the same tab.

---

## M600 air-test program

### `m600_tool_change_test.ngc`

Validates tool-change + probe before trusting CAM. Requires homed machine,
setter taught (`#5181–#5183`), spindle zero (`#3010`), and tools in the table.

```ngc
( M600 tool change test )
( T3 M600 → jog X → T9 M600 → T10 M600 )
( Each M600 pauses at tool-load XY for the OK dialog, then probes on the setter. )

G21 G90 G17 G40 G49
M5

T3 M600

G53 G0 Z0
G91 G0 X-40
G90

T9 M600
T10 M600

M2
```

**Note:** M600 pauses at **tool-load** XY (default G53 270, 100), not the setter.
See [TOOLSETTER.md § tool-load position](TOOLSETTER.md#tool-load-position-collet-change).

### `blank.ngc`

Safe empty program for Probe Basic startup / OPEN_FILE:

```ngc
( blank - safe startup file )
M2
```

---

## Safety

- Confirm soft limits and clearance before first run — especially Y (short stroke)
  and Z (this mill’s Z envelope is tight when unhomed).
- Keep a hand near ESTOP during tuning moves.
- Semi-auto and logging sessions temporarily widen drive SDO **6065** to **2.0 mm /
  2.0°** during moves, then restore **0.5 mm / 0.5°** — see [A6_TUNING.md](A6_TUNING.md).
