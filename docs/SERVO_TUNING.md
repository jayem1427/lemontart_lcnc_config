# Servo tuning (A6-EC drives)

The **Servo Tuning** tab in Probe Basic reads and writes the A6-EC drives'
gain parameters over EtherCAT and plots each drive's following error live. No
StepperOnline software or USB cable needed. It supports three ways of tuning:

| Way | What you do | Good for |
|-----|-------------|----------|
| **One-click** | Press one button per axis. It climbs the gains until the axis starts to ring, backs off, and saves the result | A first tune, or retuning after mechanical changes |
| **AI-assisted** | Run a test move, copy the plot and gains, paste them into an AI chat, apply its suggestion yourself | Judgment calls: filters, notches, "does this look right?" |
| **Manual** | Follow the zone ladder below | Learning how the loops behave |

The approach is based on [kalico sota-motion](https://github.com/dderg/kalico/tree/sota-motion).

---

## Three rules

1. **Tune on the drive's following error, not LinuxCNC's.** The plot shows
   CiA object **60F4**, which the drive computes at its own servo rate.
   LinuxCNC's `joint.N.f-error` includes EtherCAT round-trip lag and is only
   used for fault limits. An earlier attempt to "fix" LinuxCNC's number by
   rewiring HAL was removed. Don't bring it back.
2. **Never put loop gains in `ethercat-conf.xml`.** lcec writes those SDOs on
   every LinuxCNC start, so they'd overwrite your tuning every launch. The XML
   only sets the fault window (6065/6066) and `C01.10`.
3. **APPLY writes to drive RAM only.** A power cycle reverts to what's stored
   in the drive. When you like a result, store it to EEPROM from the drive's
   front panel or the vendor tool.

---

## Before you start

- `ethercat` must work without sudo (the udev rule in
  [SETUP.md](SETUP.md#install-notes)). The tab falls back to `sudo -n`, which
  only works with passwordless sudo.
- `python3-pyqtgraph` for plots, `python3-numpy` for the FFT.
- Set the load inertia ratio (C00.06) first if you can. See
  [INERTIA_TUNING.md](INERTIA_TUNING.md). The factory 100 % is often good
  enough to start.

---

## The tab

| Control | Does |
|---------|------|
| Axis buttons | Choose which axes are plotted. The last one clicked is the one you edit |
| *(auto-read)* | Drive parameters load when you open the tab or pick an unread axis |
| Parameter table | Current (on the drive) and Pending (your edits), with units and ranges |
| **APPLY TO DRIVE** | Turns the machine off if needed, writes the Pending values with read-back checks and retries, turns it back on |
| **START PLOT / STOP PLOT** | Live following-error plot (polls only while on and visible; nothing saved) |
| **MM / PULSES** | Plot units |
| **FERR / FFT** | Switch between the time plot and the spectrum from **ANALYZE** |
| **ANALYZE** | FFT of the captured trace: finds resonances and gives a stable / unstable verdict |
| **USE SUGGESTED NOTCH 3** | Loads the main resonance into notch 3 (C01.46–48) in Pending |
| **COPY TUNING / COPY PLOT / COPY RESONANCE** | Put the gains, plot image or FFT report on the clipboard |
| **PRESET** | Load (into Pending only) / save / delete named gain sets, stored in `config/tuning/presets/<axis>/` |
| **ONE-CLICK TUNE** | See [ONE_CLICK_TUNING.md](ONE_CLICK_TUNING.md) |
| **INERTIA** panel | See [INERTIA_TUNING.md](INERTIA_TUNING.md) |

`C01.10` (speed feedback filter) and `C01.38` (gain switchover mode) are
read-only on this firmware, so APPLY skips them. Set gain switchover to
"fixed 1st set" on the drive panel if you need to.

---

## One-click

Home, clear the axis's travel, machine on, hand near the E-stop. Pick the
axis, pick a profile (**BALANCED** unless you have a reason), press
**ONE-CLICK TUNE**. It journals every step and restores the original gains if
anything goes wrong or you cancel. Full details: [ONE_CLICK_TUNING.md](ONE_CLICK_TUNING.md).

## AI-assisted

1. Open the tab, pick the axis, **START PLOT**.
2. Run that axis's test program (below) in AUTO.
3. **COPY PLOT** and **COPY TUNING**, paste both into an AI chat along with
   [SERVO_TUNING_LLM.md](SERVO_TUNING_LLM.md) (that file tells the AI how to
   read the plot and what to suggest).
4. Type its suggestion into Pending, **APPLY TO DRIVE**, and repeat from step 1.
5. **SAVE AS PRESET** when you have something good.

The AI never writes to the drive. You do. Use the **same test program for a
whole session**. If you change it, earlier plots aren't comparable any more.

---

## Manual tuning: the zone ladder

The drive is a cascade: position loop → speed loop → torque loop. Tune from the
fastest (highest frequency) part to the slowest, one knob at a time, running
the same move and watching the plot after every change.

| Parameter | Role |
|-----------|------|
| C01.03 torque filter / notches | Remove high-frequency buzz and resonances |
| C01.01 speed loop gain (Hz) | Inner stiffness and damping |
| C01.02 speed integral (ms) | Removes steady lag. Lower ms = stronger |
| C01.00 position loop gain (rad/s) | Outer tracking: main lever on following error |
| C00.06 inertia ratio (%) | Scales everything. Set it first |

1. **Prep.** Fixed 1st gain set, soft gains, one repeatable test move.
2. **Filters.** If it already buzzes or rings, lower the torque filter or add a
   notch at the ring frequency (ANALYZE finds it). Don't chase following
   error with filters.
3. **Speed gain.** Raise C01.01 until the plot tracks cleanly. When a tap on
   the axis starts a sustained buzz, back off about 20 %. Then tighten the
   integral (lower C01.02 ms) a little to remove lag. Keep it as weak as works.
4. **Position gain.** Raise C01.00 until peak error stops improving. A good
   ratio is position (rad/s) ≈ 2 × speed (Hz). If overshoot or ringing grows,
   back off 20 %.
5. **Polish.** Notches for leftover rings. Test both directions and real
   cutting loads.

| Symptom | Change |
|---------|--------|
| Big error during acceleration, smooth trace | Raise position, then speed (keep the ratio) |
| Steady offset at rest | Lower integral ms a little |
| Buzz when pushed or after a move | Lower speed gain and/or torque filter |
| High-pitched ring | Lower torque filter, then a notch |
| Soft and laggy after quietening it | Raise speed a little, then position |

**Jagged, growing ringing after a gain increase is a hard stop.** Revert and
treat it as a vibration problem, not a gain problem.

---

## Test programs

The AI-assisted and manual workflows need one fixed back-and-forth program per
axis. Put these in your `PROGRAM_PREFIX` folder. Adjust the stroke to your
travel once, then leave it alone.

| File | Move |
|------|------|
| `x_tuning.ngc` | 10× X 0 ↔ 80 mm at F1000 |
| `y_tuning.ngc` | 10× Y 0 ↔ 15 mm at F30000 |
| `z_tuning.ngc` | 1× Z 0 ↔ 15 mm at F10000 |
| `a_tuning.ngc` | 10× A 0 ↔ 90° at F3600 |

All four follow the same pattern (X shown):

```ngc
(x_tuning.ngc: fixed tuning stimulus, don't edit mid-session)
G21 G90 G61
G0 X0
#1 = 10
o100 while [#1 GT 0]
  G1 X80 F1000
  G4 P0.5
  G1 X0 F1000
  G4 P0.5
  #1 = [#1 - 1]
o100 endwhile
M2
```

The moves are relative to wherever the work offset puts 0, so check clearance
first. One-click doesn't need these. It generates its own moves.

---

## Presets

Presets are JSON files in `config/tuning/presets/<axis>/`. **LOAD** only fills
Pending, so you still have to press APPLY. Validated sets on this mill
(2026-07-12):

| Axis | Preset | Speed / position / integral |
|------|--------|-----------------------------|
| X | `one_click_best_20260712` | 150 Hz / 224.6 rad/s / 5.0 ms |
| Y | `one_click_best_20260712` | 164.6 Hz / 60 rad/s / 3.5 ms |

One-click also saves timestamped `pre_one_click_*` (backup) and
`one_click_*` (result) presets every run.

---

## Drive parameters reference

| SDO | Panel | Meaning |
|-----|-------|---------|
| `0x2000:05` | C00.04 | Gain mode (0 = manual. One-click forces this) |
| `0x2000:07` | C00.06 | Load inertia ratio, % |
| `0x2001:01` | C01.00 | Position loop gain, 0.1 rad/s |
| `0x2001:02` | C01.01 | Speed loop gain, 0.1 Hz |
| `0x2001:03` | C01.02 | Speed integral, 0.01 ms |
| `0x2001:31` | C01.30 | Adaptive notch mode |
| `0x6065` | | Following-error window, counts (6554 = 0.5 mm; A: 182 = 0.5°) |
| `0x6066` | | Following-error time, ms (250) |

Read one by hand (the A6 doesn't describe its own types, so `-t` is required):

```bash
ethercat upload -p 0 -t uint16 0x2001 0x02   # slave 0 speed gain
```

---

## Copying the tabs to another machine

1. **Copy** `probe_basic/user_tabs/servo_tuner/` (and `signal_monitor/` for
   the Logging tab), plus from `probe_basic/python/`: `a6_servo_tune.py`,
   `a6_auto_tune.py`, `a6_auto_tune_sim.py`, `a6_graphical_inertia.py`,
   `resonance_analysis.py`, `tune_trial.py`, `hal_signal_logger.py`,
   `signal_plot_widget.py`. Optionally `scripts/run_auto_tune.py` and
   `config/`.
2. **EtherCAT XML.** Map PDOs 60F4 (`ferr-fb`), 6077 (`torque-fb`) and 606C
   (`vel-fb`) on every slave.
3. **HAL.** Copy the telemetry block at the end of `custom.hal` that makes
   `tune-drive-ferr.N`, `tune-torque.N` and `tune-velocity.N`. Never wire
   these into `joint.N.f-error`. The `tune-velocity.N.gain` values are
   1/SCALE typed in by hand, so recompute them for your scale.
4. **Python.** Edit the `AXES` table in `a6_servo_tune.py`: joint, slave,
   linear or rotary, and `scale`, which **must** match the INI `SCALE`.
   Otherwise the plot units and the 6065 window are wrong.
5. **Test.** `python3 scripts/run_auto_tune.py --axis X --sim` (no hardware),
   then `--dry-run` on the machine, before a real run.

On the machine: the tab's Current column should fill in (not "READ FAIL"), and
`halcmd getp tune-drive-ferr.0.out` should change when you jog.

---

## Files

| File | Role |
|------|------|
| `probe_basic/user_tabs/servo_tuner/` | The tab |
| `probe_basic/python/a6_servo_tune.py` | SDO read/write, presets, axis table |
| `probe_basic/python/a6_auto_tune.py` | One-click engine |
| `probe_basic/python/a6_graphical_inertia.py` | Inertia identification |
| `probe_basic/python/resonance_analysis.py` | FFT stability check |
| `probe_basic/python/tune_trial.py` | Clipboard text and images |
| `custom.hal` (end) | Drive telemetry → `tune-*` pins |
| `config/tuning/presets/` | Saved gain sets |
| `logs/tuning/` | One-click and inertia journals (not in git) |
