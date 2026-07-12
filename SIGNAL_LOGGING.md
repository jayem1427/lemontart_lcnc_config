# Signal logging

HAL telemetry, CSV logging, and a live **Logging** tab in Probe Basic for servo tuning and diagnostics.

One CSV per session with all configured channels. See **[PYTHON_PACKAGES.md](PYTHON_PACKAGES.md)** for dependency policy.

---

## Logging tab (Probe Basic)

Open the **Logging** tab (`probe_basic/user_tabs/signal_monitor/`). The tab uses the Probe Basic dark theme (BebasKai, `#2e3436` / `#363b3d`).

### Layout

| Area | Purpose |
|------|---------|
| **Header** | Title + status badge (`IDLE` / `ARMED` / `LOGGING`) |
| **LOGGING panel** | Arm/live controls, axis & signal selectors, Y scale, sample rate |
| **Legend panel** | Fixed color key for X/Y/Z/A (right side of LOGGING panel) |
| **Plot** | Live pyqtgraph trace (~2/3 of tab height) |
| **Stats bar** | Last / RMS / peak for each visible channel |

### Controls

| Control | Behavior |
|---------|----------|
| **LOG NEXT PROGRAM** | Arms logging; starts when the next program runs in **AUTO**, stops when the cycle ends |
| **START LIVE** / **STOP** | Continuous logging while jogging or testing (no G-code required) |
| **AXIS** (X Y Z A) | Checkable toggles — multi-select which axes appear on the plot |
| **SIGNAL** (FERR / DRIVE / TORQUE / VEL) | Exclusive — one signal family at a time on the plot |
| **Y SCALE** | Auto, Symmetric, Fixed ±0.25 (mm ferr), Fixed ±60 (deg ferr), Fixed ±100% (torque) |
| **RATE** | Sample rate: 25 / 50 / 100 / 200 / 500 / **1000** Hz |

CSV logging always records **all** channels from `config/logging/signals.json`. Axis/signal toggles and Y scale affect the **plot only**.

### Sample rate and Nyquist

This machine’s servo thread is **1 kHz** (`SERVO_PERIOD = 1000000` ns in `ethercat_mill.ini`). HAL pins such as `joint.*.f-error` and `tune-drive-ferr.*.out` only **update once per servo period**.

**You do not need to sample at 2 kHz.**

Nyquist says: to reconstruct a *continuous* signal that may contain energy up to frequency \(F\), sample faster than \(2F\). That applies to an analog front-end before digitization. Here the Logging tab is a **userspace poller** reading HAL pins that are already discrete-time at the servo rate:

| Idea | Reality on this stack |
|------|------------------------|
| “2× servo = 2 kHz required” | **False** for HAL logging — pins do not change between servo cycles |
| Useful log rate | ≤ servo rate (≤ ~1 kHz); duplicates if you poll faster than HAL updates |
| Default in this repo | **1000 Hz** (`config/logging/signals.json`); UI offers up to **1000 Hz** |
| When to lower rate | Reduce userspace load or shrink CSV size; still capped by servo updates |

For A6 loop tuning plots (DRIVE FERR, torque), **100–1000 Hz** is useful. At **1000 Hz** the logger aims for one sample per servo update via in-process `hal.get_value` (not slow `halcmd`). Polling faster than the servo thread only duplicates values — it does **not** unlock content that never appeared on the HAL pin.

The Servo Tuning tab’s live FERR strip chart is separate (START PLOT / STOP PLOT, no CSV) and also targets ~1 kHz via `hal.get_value`.

---

## Workflow

The legend panel on the right of the LOGGING box always shows all four axes for the current signal type:

- Color swatch matches the plot line (from `signals.json`)
- Channel label and units (e.g. `X FErr (mm)`)
- **Selected** axes: white text + white swatch border
- **Unselected** axes: dimmed gray text

The legend title updates with the signal family: `FERR`, `DRIVE FERR`, `TORQUE`, or `VELOCITY`.

Y scale auto-suggests when you change axis or signal (e.g. FERR with only A → Fixed ±60; linear axes → Fixed ±0.25).

---

## Workflow

### Program logging (CAM or tuning G-code)

1. Open **Logging** in Probe Basic.
2. Check **LOG NEXT PROGRAM**.
3. Run your `.ngc` in AUTO.
4. Logger starts when the interpreter leaves idle and stops when the program finishes.
5. A dialog and status line show the saved CSV path.

### Live logging (jog / MDI / bench)

1. Click **START LIVE**.
2. Jog or run short moves — all channels log to one CSV.
3. Click **STOP** when done.

Logs are written to `logs/signals/` as one `.csv` + `.summary.txt` per session.

---

## HAL telemetry chain

Torque, velocity, and **drive following error** come from CiA 402 PDOs on each A6 drive, converted in `custom.hal`:

```
lcec.0.N.torque-fb (6077, 0.1% per count)
  → conv-s32-float → mult2 (×0.1) → tune-torque.N.out  (% rated torque)

lcec.0.N.vel-fb (606C, drive units)
  → conv-s32-float → tune-velocity.N.out  (mm/s or deg/s after scale)

lcec.0.N.ferr-fb (60F4, encoder counts)
  → conv-s32-float → div2 (÷ joint SCALE) → tune-drive-ferr.N.out  (mm or deg)
```

Drive **60F4** is the primary metric for loop tuning: computed inside the A6 at its servo rate (internal demand vs encoder), not inflated by host cmd−fb lag. Plot it as **DRIVE** on the Logging tab.

LinuxCNC following error is left alone (no HAL rewiring of `motor-pos-fb`):

```
joint.N.f-error  →  cmd − fb   (INI FERROR / soft limits only)
```

See **[A6_TUNING.md](A6_TUNING.md)** for SDO gain defaults, Servo Tuning GUI, and revert workflow.

### `custom.hal` loadrt note

`conv_s32_float` and `mult2` are already loaded with `count=` in `ethercat_mill.hal`. Additional instances use extra `loadrt … count=4` lines — **you cannot mix `count=` and `names=` on the same module**. Named `scale` components are loaded as:

```
loadrt scale names=tune-torque.0,…,tune-velocity.3
```

Instance numbers for the telemetry converters start at `conv-s32-float.4` / `mult2.12` (after existing HAL loads). Drive following error uses `conv-s32-float.12`–`.15` and `div2.4`–`.7`.

Verify after LinuxCNC start:

```bash
halcmd getp tune-torque.0.out
halcmd getp tune-velocity.0.out
halcmd getp tune-drive-ferr.0.out
halcmd getp joint.0.f-error
```

If LinuxCNC fails to reach OP with the new PDO mapping, verify the A6 exposes **60F4** on your firmware:

```bash
sudo ethercat upload -p 0 -t int32 0x60F4 0
sudo ethercat pdos -p 0
```

---

## Drive following-error limits (SDO)

Configured in `ethercat-conf.xml` per slave via EtherCAT SDO at startup (no StepperOnline software required):

| SDO | Meaning | XYZ value | A value |
|-----|---------|-----------|---------|
| **6065h** | Max position deviation (encoder counts) | `0x3333` = 13107 counts ≈ **1.0 mm** @ 13107.2 counts/mm | `0x016C` = 364 counts ≈ **1.0°** @ 364.09 counts/deg |
| **6066h** | Fault delay (ms deviation must persist) | `0x00FA` = **250 ms** | same |

Drive fault **Er47.0** compares internal position demand vs feedback (CiA 6062 vs 6064). This is **separate** from LinuxCNC `joint.N.f-error` and the INI `FERROR` limit (2.0 mm on this machine).

> **Note:** Startup defaults are intentionally loose for tuning (1.0 mm / 1.0°). Tighten 6065h later once loops are stable if you want earlier Er47.0 protection.

---

## Tuning G-code

`nc_files/x_tuning.ngc` — 10 oscillation cycles on X between 0 and 80 mm at F1000 (mm/min), 0.5 s dwell each end. Same 10-cycle pattern for `y_tuning.ngc`, `y_tuning_85.ngc`, and `a_tuning.ngc`. `z_tuning.ngc` is **1 cycle** 0↔15 mm @ F10000 (same dwell). Use with **LOG NEXT PROGRAM** and **DRIVE** (or FERR / TORQUE) on the plot.

`ethercat_mill.ini` sets:

```ini
PROGRAM_PREFIX = /home/jon/linuxcnc/nc_files:nc_files
```

so programs in the config `nc_files/` directory are found alongside the system path.

---

## Config

Edit `config/logging/signals.json` to add or remove HAL pins.

Default channels (1000 Hz):

| Group | Pins | Units |
|-------|------|-------|
| Following error (LinuxCNC) | `joint.0..3.f-error` | mm / deg |
| Following error (drive 60F4) | `tune-drive-ferr.0..3.out` | mm / deg |
| Torque | `tune-torque.0..3.out` | % rated |
| Velocity | `tune-velocity.0..3.out` | mm/s / deg/s |

Context columns in each CSV row: `line`, `feed`, `enabled`.

---

## Files

| Path | Role |
|------|------|
| `probe_basic/python/hal_signal_logger.py` | Poll HAL, write CSV, live buffers |
| `probe_basic/python/signal_plot_widget.py` | Live plot widget |
| `probe_basic/user_tabs/signal_monitor/` | Logging tab (`.py`, `.ui`, `.qss`) |
| `config/logging/signals.json` | Channel definitions |
| `custom.hal` | Torque/velocity/drive-ferr conversion → `tune-*` pins |
| `A6_TUNING.md` | A6 SDO gain defaults + Servo Tuning GUI / revert |
| `INSTALL_SERVO_TUNING.md` | How to install Servo Tuning + Logging on another machine |
| `ethercat-conf.xml` | PDO 606C/6077/60F4 + SDO 6065/6066 + loop gains |
| `nc_files/x_tuning.ngc` | Example axis tuning program |
| `scripts/run_signal_logger.py` | Headless CLI logger (optional) |

---

## Test plan

| Phase | Verify |
|-------|--------|
| **0 — Setup** | LinuxCNC starts without HAL loadrt errors; [smoke test](PYTHON_PACKAGES.md#smoke-test) passes |
| **1 — HAL** | `tune-torque.*`, `tune-velocity.*`, `joint.*.f-error` respond to jog |
| **2 — Tab** | Logging tab loads; axis toggles, signal buttons, legend, and plot update |
| **3 — Program log** | Arm → run `x_tuning.ngc` in AUTO → CSV created, dialog on finish |
| **4 — Live log** | Start/stop live → CSV written while jogging |
| **5 — Rate** | Change rate dropdown; CSV row spacing matches selection |
| **6 — CSV content** | One file, all channel columns populated |
| **7 — Integration** | No motion regression; e-stop safe |

```bash
# HAL pins
halcmd getp tune-torque.0.out
halcmd getp joint.0.f-error

# Headless live log (Ctrl+C to stop)
python3 scripts/run_signal_logger.py --live
ls -lt logs/signals/
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| HAL error mixing `count=` and `names=` | See `custom.hal` — use separate `loadrt count=` for extra conv/mult instances |
| `lcec.0.N.torque-fb` not found | Confirm PDO entries 606C + 6077 in `ethercat-conf.xml` for each slave |
| Empty CSV columns | `halcmd show pin <name>` — check pin name in `signals.json` |
| Never starts on program | Must be AUTO; program must be running (`MODE_AUTO` + interpreter not idle) |
| No dialog on save | Check status line; look in `logs/signals/` |
| No plots | `sudo apt install python3-pyqtgraph` |
| Drive Er47.0 on fast moves | Tight 6065h limit — increase counts or 6066h delay in `ethercat-conf.xml` |
| Legend colors wrong | Edit `color` fields in `signals.json` |

---

## Branch

Development branch: `servo-tuning-gui`. See also **[A6_TUNING.md](A6_TUNING.md)**.
