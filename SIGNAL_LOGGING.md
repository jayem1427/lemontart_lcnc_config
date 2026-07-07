# Signal logging

Guide for running and verifying the HAL signal logging framework.

See **[PYTHON_PACKAGES.md](PYTHON_PACKAGES.md)** for Python version and package install policy.

## Overview

| Layer | Path | Purpose |
|-------|------|---------|
| HAL telemetry | `custom.hal`, `ethercat-conf.xml` | Torque/velocity pins for logging |
| Presets | `config/logging/*.json` | Channels, rate, trigger, plot layout |
| Core engine | `probe_basic/python/hal_signal_logger.py` | Sample pins → CSV + summary + live buffers |
| Terminal runner | `scripts/run_signal_logger.py` | Headless logging |
| Probe Basic tab | `probe_basic/user_tabs/signal_monitor/` | Live plots + manual start/stop |
| Offline plot | `scripts/plot_signal_log.py` | Replay a finished CSV |

Logging runs in userspace Python and does not load onto `servo-thread`.

---

## Usage

### Terminal (no extra packages)

```bash
python3 scripts/run_signal_logger.py --list-presets
python3 scripts/run_signal_logger.py --preset tune_idle        # manual trigger
python3 scripts/run_signal_logger.py --preset cut_ferr         # auto on AUTO program
```

### Probe Basic

`ethercat_mill.ini` sets `USER_TABS_PATH = probe_basic/user_tabs/`. Open **Signal Monitor**, pick a preset, start/stop manual presets or let program presets auto-run.

### Offline plot (requires pyqtgraph)

```bash
python3 scripts/plot_signal_log.py logs/cut_ferr/<file>.csv --preset config/logging/cut_ferr.json
```

---

## Best practices

- **CSV logging works without plots** — pyqtgraph is optional.
- **Sample rates:** 50 Hz for cuts (`cut_ferr`, `motor_torque`); 100 Hz for short manual sessions (`tune_idle`) only.
- **Presets:** copy `custom_template.json`; verify pins with `halcmd show pin <name>`.
- **Logs:** written to `logs/<log_subdir>/`; CSV/summary are gitignored.
- **Torque scaling:** verify `tune-torque.N.out` units on the bench before trusting absolute % values.

---

## Test plan

Work top-down. Each phase should pass before the next.

| Phase | Verify |
|-------|--------|
| **0 — Setup** | LinuxCNC starts; [dependency smoke test](PYTHON_PACKAGES.md#smoke-test) passes |
| **1 — HAL** | `tune-torque.N.out`, `tune-velocity.N.out`, `joint.N.f-error` exist and respond to jog |
| **2 — Presets** | `--list-presets` works; each JSON loads; CSV columns populate while jogging |
| **3 — Terminal logger** | Manual session writes `.csv` + `.summary.txt`; row count ≈ rate × duration |
| **4 — Program trigger** | `cut_ferr` auto-starts/stops with AUTO programs; filename includes program name |
| **5 — Probe Basic tab** | Tab loads; preset switch works; manual + program triggers behave |
| **6 — Plots** | Live curves draw; `plot_signal_log.py` replays a CSV (needs pyqtgraph) |
| **7 — Integration** | No motion regression during a real cut; e-stop safe; restart LinuxCNC → still works |

**Quick HAL check (phase 1):**

```bash
halcmd getp tune-torque.0.out
halcmd getp tune-velocity.0.out
halcmd getp joint.0.f-error
```

**Quick logger check (phases 3–4):**

```bash
python3 scripts/run_signal_logger.py --preset tune_idle
# jog, Ctrl+C, inspect logs/tune_idle/
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Empty CSV columns | Bad pin name or HAL not running | `halcmd show pin <name>` |
| Torque always 0 | PDO not mapped | Check `ethercat-conf.xml`, jog axis |
| Logger won't start on program | Not AUTO + running | Check LinuxCNC task state |
| No plots | pyqtgraph missing | See [PYTHON_PACKAGES.md](PYTHON_PACKAGES.md) |
| High CPU | Too many channels × rate | Lower `rate_hz` in preset JSON |
