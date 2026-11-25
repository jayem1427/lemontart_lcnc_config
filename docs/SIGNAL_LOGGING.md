# Signal logging

The **Logging** tab records HAL signals to CSV and plots them live: drive
following error, torque, velocity and position for each axis, plus the
spindle. Use it to compare tuning runs, catch a spindle that sags under load,
or capture anything else you can name as a HAL pin.

---

## Using the tab

| Control | Does |
|---------|------|
| **LOG NEXT PROGRAM** | Starts logging when the next program runs in AUTO, stops when it ends. **On this machine it re-arms itself after every program** (`AUTO_LOG_EVERY_PROGRAM = True` in `signal_monitor.py`), so every G-code run is logged with no popup. Set it to `False` to go back to arming by hand |
| **START LIVE / STOP** | Logs continuously, e.g. while jogging |
| **AXIS** (X Y Z A) | Which axes to plot (any combination) |
| **SIGNAL** | What to plot: DRIVE (following error, 60F4), TORQUE (6077, % rated), VEL (606C), POS, or SPINDLE |
| **Y SCALE** | Auto, symmetric, or fixed ranges |
| **RATE** | 25–1000 Hz. Default 100 Hz, from `config/logging/signals.json` |

In SPINDLE mode the toggles become CMD / FB / A / RDY: commanded RPM,
measured RPM, current, at-speed.

Each session writes `logs/signals/<time>.csv` and a `.summary.txt` (not in
git). **Every** channel in `signals.json` goes into the CSV. The plot shows
only the ones you select.

From a terminal instead: `python3 scripts/run_signal_logger.py --live`
(`--arm` waits for the next program). Plot a CSV afterwards with
`python3 scripts/plot_signal_log.py <file.csv>`.

### What rate to use

The servo thread runs at 1 kHz, so HAL pins change at most 1000 times a
second. Sampling faster gains nothing, and you don't need 2× for Nyquist:
the pins are already sampled values. 100–200 Hz is plenty for tuning and keeps
Probe Basic responsive. The logger runs on the UI thread, and at 1000 Hz
jogging can start to lag. Use 1000 Hz only for short captures.

---

## Where the signals come from

Torque, velocity and following error come from each drive's PDOs and are
converted to real units at the end of `custom.hal`:

```
lcec.0.N.ferr-fb   (60F4, counts) → ÷ SCALE        → tune-drive-ferr.N.out  (mm or °)
lcec.0.N.torque-fb (6077)         → × 0.1          → tune-torque.N.out      (% rated)
lcec.0.N.vel-fb    (606C)         → × 1/SCALE      → tune-velocity.N.out    (mm/s or °/s)
```

The following-error divider reads `SCALE` from the INI, but the velocity gains
are **typed in** (`setp tune-velocity.N.gain 0.0000762939453125` = 1/13107.2).
If you change `SCALE`, update those too.

Spindle channels read `spindle.0.*` and the `mb2hal.*` pins (see
[SPINDLE.md](SPINDLE.md)). `joint.N.f-error` (LinuxCNC's own following error)
is logged to the CSV but not plotted. Tune from DRIVE instead (see
[SERVO_TUNING.md](SERVO_TUNING.md)).

Check the telemetry with LinuxCNC running:

```bash
halcmd getp tune-drive-ferr.0.out
halcmd getp tune-torque.0.out
```

If the bus won't reach OP after adding the PDOs, check your drive firmware
exposes 60F4: `ethercat upload -p 0 -t int32 0x60F4 0`.

---

## Adding or removing signals

`config/logging/signals.json` is the only list. Each channel:

```json
{"id": "spindle_amps", "pin": "mult2.6.out", "label": "S Amps", "units": "A", "color": "#f1c40f", "group": "spindle"}
```

| Field | Meaning |
|-------|---------|
| `id` | CSV column name (unique) |
| `pin` | A HAL **pin**, as `halcmd getp` takes it. Not a signal name |
| `label`, `units`, `color` | For the plot |
| `group` | Family, e.g. `ferr_drive`, `torque`, `spindle` |
| `scale` | Optional multiplier |

To add one: find the pin (`halcmd show pin | grep …`), add an entry, restart
Probe Basic. It's now in every CSV. Showing it on the live plot also needs an
entry in `AXIS_SIGNALS` or `SPINDLE_SIGNALS` in
`probe_basic/user_tabs/signal_monitor/signal_monitor.py`.

To remove one, delete its entry (and its `id` from any `plot_groups`). No VFD?
Delete the `"group": "spindle"` channels. A missing pin just logs as empty.

---

## Files

| File | Role |
|------|------|
| `probe_basic/user_tabs/signal_monitor/` | The tab |
| `probe_basic/python/hal_signal_logger.py` | Sampling and CSV writing |
| `probe_basic/python/signal_plot_widget.py` | Live plot |
| `config/logging/signals.json` | Channel list and default rate |
| `scripts/run_signal_logger.py`, `scripts/plot_signal_log.py` | Command-line logger and plotter |
| `config/logging/example_session.csv` | Sample capture to try the plotter on |
