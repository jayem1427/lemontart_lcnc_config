# Signal logging — best practices and test plan

Guide for running, maintaining, and verifying the HAL signal logging framework in this config.

## Overview

| Layer | Path | Purpose |
|-------|------|---------|
| HAL telemetry | `custom.hal`, `ethercat-conf.xml` | Expose torque/velocity pins for logging |
| Presets | `config/logging/*.json` | Define channels, sample rate, triggers, plot layout |
| Core engine | `probe_basic/python/hal_signal_logger.py` | Sample pins, write CSV + summary, live buffers |
| Terminal runner | `scripts/run_signal_logger.py` | Headless logging from a second terminal |
| Probe Basic tab | `probe_basic/user_tabs/signal_monitor/` | Live plots + manual start/stop |
| Offline plot | `scripts/plot_signal_log.py` | Replay a finished CSV |

Logging runs in **userspace Python** and does not load components onto `servo-thread`. It should not affect realtime motion timing under normal use.

---

## Dependencies

### What each entry point needs

| Entry point | Required | Optional (plots only) |
|-------------|----------|------------------------|
| `run_signal_logger.py` | LinuxCNC Python (`linuxcnc` module), `halcmd` on PATH | — |
| Signal Monitor tab | Probe Basic stack (`qtpy`, `qtpyvcp`, PyQt5) | `python3-pyqtgraph` |
| `plot_signal_log.py` | — | `python3-pyqtgraph` (+ `numpy` via apt) |

There is **no npm** and no Node dependency chain. Plotting is pure Python.

### Install plotting (recommended: apt)

```bash
sudo apt install python3-pyqtgraph
```

Verify:

```bash
python3 -c "import pyqtgraph; print('ok')"
```

Do **not** mix pip and apt for the same package. If you ever used `pip install pyqtgraph`, remove it before switching to apt:

```bash
pip uninstall pyqtgraph
sudo apt install python3-pyqtgraph
```

### Why not `requirements.txt`?

`requirements.txt` is a poor fit for this repo:

- `linuxcnc` is not on PyPI — it only exists in the LinuxCNC Python environment.
- `qtpyvcp` / `qtpy` ship with Probe Basic, tied to your LinuxCNC build.
- Pip-locking `pyqtgraph` while Probe Basic pins Qt versions can create conflicts.

**Stability comes from pinning the platform**, not a Python venv.

### Platform snapshot (record when verified)

When a config combo is known-good on the mill, record it here or in git tags:

```
LinuxCNC:        2.9.x
Probe Basic:     (version from your install)
OS:              Debian 12 / Ubuntu 22.04 / your ISO
python3-pyqtgraph: (output of apt-cache policy python3-pyqtgraph)
```

Capture versions:

```bash
apt-cache policy python3-pyqtgraph python3-numpy python3-pyqt5
dpkg -l python3-pyqtgraph python3-numpy 2>/dev/null | awk '/^ii/'
```

Tag the repo when stable:

```bash
git tag signal-logging-verified-2026-07
```

Re-test after `apt upgrade` or LinuxCNC/Probe Basic upgrades.

### Optional apt manifest

If you add packages, list them in one place (apt package names only — versions come from the distro):

```
python3-pyqtgraph
```

---

## Best practices

### 1. One install path

| Do | Don't |
|----|-------|
| `sudo apt install python3-pyqtgraph` | `pip install pyqtgraph` on the mill PC |
| Run scripts with LinuxCNC's Python | Use system `python3` on a machine without LinuxCNC |
| Keep presets in git | Accept untrusted preset JSON from the internet |

### 2. Logging works without plots

CSV logging (`run_signal_logger.py`) needs no extra packages. If pyqtgraph breaks after an OS update, terminal logging and CSV analysis still work. Plots are additive.

### 3. Sample rates

| Preset | Rate | Channels | Notes |
|--------|------|----------|-------|
| `cut_ferr` | 50 Hz | 4 | Safe default during cuts |
| `motor_torque` | 50 Hz | 4 | Safe default during cuts |
| `tune_idle` | 100 Hz | 8 | Short manual sessions only |

Each sample spawns one `halcmd getp` subprocess per channel. Higher rates and more channels increase CPU load but do not block the servo thread.

### 4. Preset hygiene

- Copy `config/logging/custom_template.json` for new presets.
- Verify pins exist: `halcmd show pin <pin>` or `halcmd show sig`.
- Keep `log_subdir` unique per preset so logs stay organized under `logs/`.
- Presets are trusted local config — review git diffs like any HAL change.

### 5. Log output

- CSV and summary files land in `logs/<log_subdir>/`.
- `*.csv` and `*.summary.txt` are gitignored; only `.gitkeep` files are tracked.
- Copy logs off the mill for long-term storage if needed.

### 6. Torque / velocity scaling

`custom.hal` scales CiA 6077 (torque) and 606C (velocity) to `tune-torque.N.out` and `tune-velocity.N.out`. Verify units on the bench before trusting absolute torque percentages in production logs. Adjust `torque-pct.N.in1` or `tune-velocity.N.gain` if values look wrong.

### 7. Shop-floor hygiene

- Run the dependency smoke test after OS or config updates (see test plan below).
- Do not install random pip packages on the machine that runs the mill.
- Prefer terminal-only logging during critical first cuts if you want minimum overhead.

---

## Dependency smoke test

Run on the mill PC with LinuxCNC **stopped** (HAL need not be running for import checks; pin reads need LinuxCNC running):

```bash
cd /path/to/lemontart_lcnc_config

# Core logger
python3 scripts/run_signal_logger.py --list-presets

# LinuxCNC module
python3 -c "import linuxcnc; print('linuxcnc ok')"

# Probe Basic stack (only if using Signal Monitor tab)
python3 -c "import qtpy; import qtpyvcp; print('qtpyvcp ok')"

# Optional plots
python3 -c "import pyqtgraph; print('pyqtgraph ok')"

# HAL CLI
which halcmd
```

All checks should pass before relying on logging during a cut.

---

## High-level test plan

Use this checklist to verify the framework is implemented correctly. Work top-down: HAL → presets → terminal logger → UI → plots → integration.

### Phase 0 — Prerequisites

- [ ] LinuxCNC starts cleanly with this config (`./launch.sh` or INI load).
- [ ] Machine is homed and enabled (or in a safe sim/bench setup).
- [ ] Dependency smoke test passes (above).

### Phase 1 — HAL telemetry pins

Confirm drive telemetry is wired and readable.

```bash
halcmd show pin tune-torque.0.out
halcmd show pin tune-velocity.0.out
halcmd getp joint.0.f-error
```

| Test | Action | Pass criteria |
|------|--------|---------------|
| Torque pins exist | `halcmd show pin tune-torque` | `.0`–`.3` listed |
| Velocity pins exist | `halcmd show pin tune-velocity` | `.0`–`.3` listed |
| Torque responds | Jog one axis | `tune-torque.N.out` changes from ~0 |
| Velocity responds | Jog one axis | `tune-velocity.N.out` changes during motion |
| Following error readable | Jog then stop | `joint.N.f-error` near 0 at rest, nonzero during accel |

If torque/velocity stay flat, check `ethercat-conf.xml` PDO mapping and `custom.hal` nets before testing the logger.

### Phase 2 — Preset validation

| Test | Action | Pass criteria |
|------|--------|---------------|
| Presets discoverable | `python3 scripts/run_signal_logger.py --list-presets` | Lists `cut_ferr`, `motor_torque`, `tune_idle`, `custom_template` |
| JSON loads | Start logger with each preset (manual stop after a few seconds) | No traceback; logger prints preset name and log dir |
| Pins in preset resolve | Run `cut_ferr` for 5 s while jogging | CSV columns populated, not all empty |
| Invalid pin handling | Temporarily break a pin name in a copy of a preset | Logger runs; bad channel logs empty/NaN, does not crash |

### Phase 3 — Terminal logger (`run_signal_logger.py`)

Run from a second terminal while LinuxCNC is up:

```bash
python3 scripts/run_signal_logger.py --preset tune_idle
```

| Test | Action | Pass criteria |
|------|--------|---------------|
| Manual start/stop | Start script, Ctrl+C after ~10 s | `logs/tune_idle/` gets `.csv` + `.summary.txt` |
| CSV structure | Open CSV | Header: `t`, context cols, channel ids; rows accumulate |
| Sample rate | Log 10 s, count rows | Row count ≈ `rate_hz × duration` (±10%) |
| Summary file | Open `.summary.txt` | Reports preset, duration, sample count, per-channel max/RMS |
| FERROR comparison | Run `cut_ferr` with motion | Summary includes `vs_limit` % for ferr channels |
| Log naming | Manual session | Files named `YYYYMMDD_HHMMSS_<session>.csv` |

### Phase 4 — Program trigger (`cut_ferr`, `motor_torque`)

| Test | Action | Pass criteria |
|------|--------|---------------|
| Auto-start | Run terminal logger with `cut_ferr`, then run a short NC program in AUTO | Logger state goes to `logging` when program runs |
| Auto-stop | Let program finish | Logger stops; CSV closed; summary written |
| Session name | Run program `test_part.ngc` | CSV filename contains sanitized program name |
| No log when idle | Logger running, machine idle in AUTO | No new CSV until program executes |
| Context columns | Inspect CSV during a cut | `line` and `feed` columns change during motion |

### Phase 5 — Probe Basic Signal Monitor tab

| Test | Action | Pass criteria |
|------|--------|---------------|
| Tab visible | Open Probe Basic → Signal Monitor | Tab loads without Python traceback |
| Preset dropdown | Switch presets | Plot layout updates per preset groups |
| Manual preset | Select `tune_idle`, click Start/Stop | State label shows `logging` / `idle`; files appear in `logs/tune_idle/` |
| Live stats | Log while jogging | Per-channel last/RMS/peak labels update |
| Program preset | Select `cut_ferr`, run NC in AUTO | Logging starts/stops with program (no manual buttons needed) |
| No crash on missing pyqtgraph | (Optional) Test on machine without pyqtgraph | Tab loads; shows install message; manual logging still works |

### Phase 6 — Live plots (requires pyqtgraph)

| Test | Action | Pass criteria |
|------|--------|---------------|
| Curves draw | `tune_idle` + jog | Traces move on torque/velocity plots |
| Plot groups | `cut_ferr` during motion | XYZ and A following-error on separate stacked plots |
| Y-axis modes | Compare `cut_ferr` (fixed) vs `tune_idle` (sym) | Axes behave per preset `y_mode` |
| Offline replay | `python3 scripts/plot_signal_log.py logs/.../file.csv --preset config/logging/cut_ferr.json` | Window opens with matching colors/groups |

### Phase 7 — Integration / non-regression

| Test | Action | Pass criteria |
|------|--------|---------------|
| Motion unaffected | Run a familiar NC program with logger active | No new following-error faults, stalls, or UI freezes |
| E-stop | Trigger e-stop during logging | Machine stops safely; logger stops or can be restarted cleanly |
| Long session | 5+ minute cut with `motor_torque` | CSV grows steadily; no memory blow-up; summary sane at end |
| Disk space | Check `logs/` after several sessions | Old logs can be deleted; `.gitkeep` dirs remain |
| Config reload | Restart LinuxCNC | All Phase 1–5 checks still pass |

### Phase 8 — Custom preset (optional)

- [ ] Copy `custom_template.json` to a new preset.
- [ ] Point at a known HAL pin (e.g. `spindle.0.speed-in`).
- [ ] Run via `--config` and from the Probe Basic dropdown.
- [ ] Confirm CSV captures expected signal shape.

---

## Quick reference

```bash
# List presets
python3 scripts/run_signal_logger.py --list-presets

# Manual logging (terminal)
python3 scripts/run_signal_logger.py --preset tune_idle

# Program-triggered logging (terminal)
python3 scripts/run_signal_logger.py --preset cut_ferr
# then run a program in AUTO

# Plot a finished log
python3 scripts/plot_signal_log.py logs/cut_ferr/<file>.csv --preset config/logging/cut_ferr.json

# Check a HAL pin
halcmd getp tune-torque.0.out
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `ModuleNotFoundError: linuxcnc` | Wrong Python interpreter | Use LinuxCNC's Python / run from mill environment |
| Empty CSV columns | Pin name wrong or HAL not running | `halcmd show pin <name>` |
| Tab loads, no plots | pyqtgraph not installed | `sudo apt install python3-pyqtgraph` |
| Torque always 0 | PDO not mapped or machine idle | Check `ethercat-conf.xml`, jog axis |
| Logger never starts on program | Not in AUTO or exec not ON | Confirm `stat` shows AUTO + running |
| High CPU | Too many channels × rate | Lower `rate_hz` or use fewer channels |
