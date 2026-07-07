# Signal logging

One CSV per session with all configured HAL signals. See **[PYTHON_PACKAGES.md](PYTHON_PACKAGES.md)** for dependency policy.

## Workflow

### Program logging (CAM cycle)

1. Open **Signal Monitor** in Probe Basic.
2. Check **Log signals for next program**.
3. Run your `.ngc` in AUTO.
4. Logger starts when the cycle starts and stops when it finishes.
5. A dialog and status line show the saved CSV path.

### Live plot (while logging)

The **Signal Monitor** tab shows a single plot with:

- **Quick picks:** All FErr, XYZ FErr, Torque, Velocity, All, Clear
- **Per-signal checkboxes** — e.g. check only `X FErr` for one axis, or all four for every axis
- **Y scale:** Auto, Symmetric, Fixed ±0.25 (mm ferr), Fixed ±60 (deg ferr), Fixed ±100% (torque)

CSV always logs all channels; checkboxes only affect what you see on screen.

All logs go to `logs/signals/` as one `.csv` + `.summary.txt` per session.

### Config

Edit `config/logging/signals.json` to add or remove HAL pins. Default channels: following error, torque, and velocity on X/Y/Z/A.

---

## Test plan

| Phase | Verify |
|-------|--------|
| **0 — Setup** | LinuxCNC starts; [smoke test](PYTHON_PACKAGES.md#smoke-test) passes |
| **1 — HAL** | Torque, velocity, and following-error pins respond to jog |
| **2 — Program log** | Arm checkbox → run `.ngc` → CSV auto-created, dialog on finish |
| **3 — Live log** | Start/stop live → CSV written while jogging, no program needed |
| **4 — CSV content** | One file, all channel columns populated |
| **5 — Integration** | No motion regression; e-stop safe |

```bash
halcmd getp tune-torque.0.out
python3 scripts/run_signal_logger.py --live   # Ctrl+C to stop, check logs/signals/
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Empty CSV columns | `halcmd show pin <name>` — check `signals.json` |
| Never starts on program | Must be AUTO with program running |
| No dialog on save | Check status line; look in `logs/signals/` |
| No plots | `sudo apt install python3-pyqtgraph` |
