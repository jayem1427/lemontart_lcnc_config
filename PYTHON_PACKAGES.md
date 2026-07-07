# Python and package version control

How to keep Python dependencies stable for this LinuxCNC / Probe Basic config — including the signal logging scripts.

## Principle

Stability comes from **pinning the platform** (LinuxCNC + OS image), not a pip `requirements.txt`.

| Package | Source | Notes |
|---------|--------|-------|
| `linuxcnc` | LinuxCNC install | Not on PyPI |
| `qtpy`, `qtpyvcp`, PyQt5 | Probe Basic install | Tied to LinuxCNC build |
| `python3-pyqtgraph` | apt (optional) | Only needed for plots |
| `python3-numpy` | apt (transitive) | Pulled in by pyqtgraph |

Do not use `requirements.txt` for this repo. It cannot lock what actually matters and encourages pip installs that conflict with apt.

---

## Python version

Run all scripts with the **same Python that LinuxCNC / Probe Basic uses** — not a random system interpreter or venv.

```bash
python3 --version
python3 -c "import linuxcnc; print('linuxcnc ok')"
```

Record the Python version in your platform snapshot when you verify a known-good setup. Upgrading LinuxCNC or the OS may change the Python minor version; re-run the smoke test after either.

---

## Package install policy

### Do

```bash
sudo apt install python3-pyqtgraph
```

### Don't

```bash
pip install pyqtgraph          # conflicts with apt
pip install -r requirements.txt
```

If you previously pip-installed pyqtgraph:

```bash
pip uninstall pyqtgraph
sudo apt install python3-pyqtgraph
```

### Optional apt packages

Only one package is added by this config beyond LinuxCNC + Probe Basic:

```
python3-pyqtgraph
```

CSV logging (`scripts/run_signal_logger.py`) needs **no extra apt packages**.

---

## Record a platform snapshot

When a combo works on the mill, capture it once:

```
LinuxCNC:           2.9.x
Probe Basic:        (your install version)
OS:                 Debian 12 / Ubuntu 22.04 / your ISO
Python:             3.x.x
python3-pyqtgraph:  (apt version)
python3-numpy:      (apt version)
```

Commands:

```bash
python3 --version
apt-cache policy python3-pyqtgraph python3-numpy python3-pyqt5
dpkg -l python3-pyqtgraph python3-numpy 2>/dev/null | awk '/^ii/'
```

Tag the repo when verified:

```bash
git tag platform-verified-2026-07
```

Re-run the smoke test after `apt upgrade`, LinuxCNC upgrades, or Probe Basic updates.

---

## Smoke test

Run on the mill PC from the config directory:

```bash
python3 scripts/run_signal_logger.py --list-presets
python3 -c "import linuxcnc; print('linuxcnc ok')"
python3 -c "import qtpy; import qtpyvcp; print('qtpyvcp ok')"
python3 -c "import pyqtgraph; print('pyqtgraph ok')"   # skip if plots not needed
which halcmd
```

| Check | Required for |
|-------|--------------|
| `linuxcnc` | All logging |
| `qtpyvcp` | Signal Monitor tab |
| `pyqtgraph` | Live/offline plots only |
| `halcmd` | Pin reads |

---

## What each script needs

| Script / UI | Extra packages beyond LinuxCNC + Probe Basic |
|-------------|---------------------------------------------|
| `run_signal_logger.py` | None |
| `hal_signal_logger.py` | None |
| Signal Monitor tab | `python3-pyqtgraph` for plots |
| `plot_signal_log.py` | `python3-pyqtgraph` |

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ModuleNotFoundError: linuxcnc` | Use LinuxCNC's Python environment |
| `ModuleNotFoundError: pyqtgraph` | `sudo apt install python3-pyqtgraph` |
| Import works but wrong version | Check you didn't pip-install over apt: `pip list \| grep pyqtgraph` |
| apt vs pip conflict | Uninstall pip copy, reinstall via apt |
