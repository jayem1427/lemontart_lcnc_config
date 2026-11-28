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

**Leave it at 100 Hz. Higher settings don't give real data.** The logger
runs on Probe Basic's UI thread, which wakes every 10 ms (`POLL_MS_LOGGING`
in `signal_monitor.py`). At each wake-up it takes however many samples the
rate says are due, back to back within microseconds, and stamps them as if
they were evenly spaced. So:

- **The values are real.** Each one is a true read of the pin at that moment.
- **The timestamps aren't.** In a 100 Hz job log every gap reads exactly
  10.0 ms, even across a 46 ms UI stall: the stall is hidden and the catch-up
  samples are stamped back into it.
- **At 1000 Hz you get 100 Hz data, ten times bigger.** Each 10 ms wake-up
  reads ~10 nearly identical values. File size is ~23 MB per minute (~1.4 GB
  per hour of program, uncompressed) with nothing gained, and jogging can lag.
- **Short events are missed or under-read.** A following-error spike lasting
  ~20 ms (a direction change on X) can fall between samples, and a 1 ms one
  almost always does. Nothing above ~50 Hz can be trusted.

That's fine for what this tab is for: spindle sag under load, trends over a
job, following error size across a program. For exact peaks, timing or
frequencies use the realtime capture (`rt_capture.py`, `sampler.0`, one row
per servo cycle) as the tuner and the clunk test do. See
[SERVO_TUNING.md](SERVO_TUNING.md#reversal--clunk-test). It can't run at the
same time as the tuner (one FIFO); giving the logger its own realtime sampler
would mean a `sampler.1` block in `custom.hal`.

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
