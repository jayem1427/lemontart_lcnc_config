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
| **SIGNAL** | Exclusive — **DRIVE** (CiA 60F4), **TORQUE** (6077), **VEL** (606C), **POS** (actual joint position), **SPINDLE** (H100 VFD). Default **DRIVE**. Host `joint.N.f-error` is not plotted. |
| **Y SCALE** | Auto, Symmetric, Fixed ±0.25 (mm ferr), Fixed ±60 (deg ferr), Fixed ±100% (torque) |
| **RATE** | Sample rate: 25 / 50 / 100 / **200** / 500 / 1000 Hz (default **200** — 1000 Hz is still available but heavy on the GUI) |

| **DRIVE** | Drive CiA 60F4 via raw ``lcec.0.N.ferr-fb`` — **mm** (XYZ) / **deg** (A) |
| **TORQUE** | Drive CiA 6077 via raw ``lcec.0.N.torque-fb`` × 0.1 — **% rated** |
| **VEL** | Drive CiA 606C counts/s ÷ joint ``SCALE`` × 60 — **mm/min** (XYZ) / **deg/min** (A) |
| **POS** | Actual joint position via ``linuxcnc.stat.joint_actual_position`` (``joint.N.pos-fb``) — **mm** / **deg** |
| **SPINDLE** | H100 VFD via mb2hal / ``spindle.0.*`` — toggles become **CMD** / **FB** / **A** / **RDY** (RPM cmd, RPM feedback, amps, at-speed). Fault code + raw VFD freq (0.1 Hz) always go to the CSV even if not plotted. |

### Sample rate and Nyquist

This machine’s servo thread is **1 kHz** (`SERVO_PERIOD = 1000000` ns in `ethercat_mill.ini`). HAL pins such as `joint.*.f-error` and `tune-drive-ferr.*.out` only **update once per servo period**.

**You do not need to sample at 2 kHz.**

Nyquist says: to reconstruct a continuous signal that may contain energy up to
frequency F, sample faster than 2F. That applies to an analog front-end before
digitization. Here the Logging tab is a **userspace poller** reading HAL pins
that are already discrete-time at the servo rate:

| Idea | Reality on this stack |
|------|------------------------|
| “2× servo = 2 kHz required” | **False** for HAL logging — pins do not change between servo cycles |
| Useful log rate | ≤ servo rate (≤ ~1 kHz); duplicates if you poll faster than HAL updates |
| Default in this repo | **200 Hz** (`config/logging/signals.json`); UI offers up to **1000 Hz** |
| When to lower rate | Reduce userspace load or shrink CSV size; still capped by servo updates |
| When to raise rate | Capture near-servo detail for short sessions; keep RATE ≤200 while jogging if the UI feels laggy |

For A6 loop tuning plots (DRIVE FERR, torque), **100–200 Hz** is usually enough while staying responsive. At **1000 Hz** the logger aims for one sample per servo update via in-process `hal.get_value` (not slow `halcmd`), but sampling + CSV + live plot all run on Probe Basic’s Qt main thread — that combination historically starved jog buttons.

The Logging tab samples HAL pins on the **Qt UI thread** (same pattern as
Servo Tuning’s FERR plot — ``hal.get_value`` is not reliable across threads on
this stack). CSV write is optional side work; the live plot is the primary
path. The poll timer only runs while **START LIVE** or **ARMED**; plot redraw
is ~10 Hz and decimated.

The Servo Tuning tab’s live FERR strip chart is separate (START PLOT / STOP PLOT, no CSV). It polls HAL at ~1 kHz **only while START PLOT is on** (and the tab is visible); opening the tab alone does not poll FERR.

---

## Legend

The legend panel on the right of the LOGGING box shows the four toggles for the current signal type:

- Color swatch matches the plot line (from `signals.json`)
- Channel label and units (e.g. `X FErr (mm)` or `S RPM CMD`)
- **Selected**: white text + white swatch border
- **Unselected**: dimmed gray text

The legend title updates with the signal family: `DRIVE FERR`, `TORQUE`, `VELOCITY`, `POSITION`, or `SPINDLE / VFD`.

Y scale auto-suggests when you change axis or signal (e.g. DRIVE with only A → Fixed ±60; linear axes → Fixed ±0.25; SPINDLE → Auto).

In **SPINDLE** mode, default plot is commanded + feedback RPM (same units). Toggle **A** for amps alone or with RPM (mixed Y units — prefer one family at a time).

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
  → conv-s32-float → tune-velocity.N.out  (mm/s or deg/s after HAL scale; Logging UI shows mm/min / deg/min)

lcec.0.N.ferr-fb (60F4, encoder counts)
  → conv-s32-float → div2 (÷ joint SCALE) → tune-drive-ferr.N.out  (mm or deg)
```

**Spindle / H100 VFD** (also `custom.hal` + `h100.mb2hal`):

```
spindle.0.speed-out-abs          → commanded RPM
mb2hal.freq_fb.00 → ×6 → spindle.0.speed-in   → feedback RPM
mb2hal.freq_fb.02 → ×0.01 → mult2.6.out         → output current (A)
spindle.0.at-speed               → at-speed (0/1)
mb2hal.vfd_fault.00.float        → current fault code
mb2hal.freq_set.00 / freq_fb.00  → VFD freq cmd/fb (0.1 Hz register units)
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

`nc_files/x_tuning.ngc` — 10 oscillation cycles on X between 0 and 80 mm at F1000 (mm/min), 0.5 s dwell each end. Same 10-cycle pattern for `y_tuning.ngc`, `y_tuning_85.ngc`, and `a_tuning.ngc`. `z_tuning.ngc` is **1 cycle** 0↔15 mm @ F10000 (same dwell). Use with **LOG NEXT PROGRAM** and **DRIVE** (or TORQUE / VEL) on the plot.

`ethercat_mill.ini` sets:

```ini
PROGRAM_PREFIX = /home/jon/linuxcnc/nc_files:nc_files
```

so programs in the config `nc_files/` directory are found alongside the system path.

---

---

## Config — add / remove signals for your hardware

**Single source of truth:** `config/logging/signals.json`

Everything in that file is sampled into the CSV on every session. The Logging tab only *plots* a subset (per SIGNAL button + AXIS/CMD toggles). Missing HAL pins become empty/`nan` columns — they do **not** crash the logger — but you should still prune channels you do not have so CSVs stay clean.

### Channel entry shape

```json
{
  "id": "spindle_amps",
  "pin": "mult2.6.out",
  "label": "S Amps",
  "units": "A",
  "color": "#f1c40f",
  "group": "spindle"
}
```

| Field | Meaning |
|-------|---------|
| `id` | CSV column name + plot key (unique, snake_case) |
| `pin` | HAL **pin** name (`halcmd getp …`), or `joint.N.f-error` / `joint.N.pos-fb` (read via `linuxcnc.stat`) |
| `label` | Legend / human name |
| `units` | Shown on plot / summary (`mm`, `rpm`, `A`, …) |
| `color` | Hex color for the live trace |
| `group` | Logical family (`ferr_drive`, `torque`, `spindle`, …) — for organization / plot_groups |

Optional `scale` (default `1.0`) multiplies the raw pin value if you need a unit conversion in the logger instead of HAL.

### Plot groups

`plot_groups` only describe suggested Y-scale families for docs/tools. The Probe Basic Logging tab wires plot visibility from its SIGNAL buttons (see below), not by iterating `plot_groups` alone. Keep `plot_groups` in sync when you add channels so headless/docs stay honest.

### What this mill ships with

| Hardware | Channels (examples) | Requires |
|----------|---------------------|----------|
| A6 EtherCAT axes | `tune-drive-ferr.*`, `tune-torque.*`, `tune-velocity.*`, `joint.*.pos-fb` | `ethercat-conf.xml` PDOs + `custom.hal` `tune-*` chain |
| LinuxCNC joints | `joint.*.f-error` | Always present (CSV only; tab does not plot host FERR) |
| H100 VFD (mb2hal) | `spindle_*` RPM/amps/at-speed/fault/freq | `h100.mb2hal` + spindle nets in `custom.hal` |

Default sample rate in JSON is **100 Hz**; the UI default/preferred for interactive use is **200 Hz**.

### Add a signal (checklist)

1. **Confirm the pin exists** while LinuxCNC is running:
   ```bash
   halcmd show pin | grep -i spindle
   halcmd getp mult2.6.out
   halcmd getp spindle.0.speed-out-abs
   ```
2. **Prefer a float pin** already in engineering units (amps, RPM, mm). If you only have raw counts, either:
   - add a HAL `scale` / `mult2` in `custom.hal`, **or**
   - set `"scale": …` on the channel in JSON.
3. **Append a channel** to `channels` in `signals.json` with a unique `id`.
4. **Optionally** add it to a `plot_groups` list.
5. **UI plot (optional):**
   - Axis family (DRIVE/TORQUE/VEL/POS): edit `AXIS_SIGNALS` in `probe_basic/user_tabs/signal_monitor/signal_monitor.py`.
   - Spindle family: edit `SPINDLE_SIGNALS` / button labels in the same file (toggles are CMD/FB/A/RDY, not machine axes).
   - New SIGNAL button: add a button in `_build_controls` plus legend title / Y-default entries.
6. Restart Probe Basic (or reload the tab) so it reloads JSON.

Example — log a hypothetical coolant pressure pin:

```json
{
  "id": "coolant_psi",
  "pin": "analog-in.0.value",
  "label": "Coolant",
  "units": "psi",
  "color": "#00bcd4",
  "group": "aux"
}
```

That alone puts it in every CSV. Plotting it needs a UI mapping (or use the CSV / external plotter).

### Remove a signal

1. Delete (or comment out by removing) the channel object from `channels`.
2. Remove its `id` from any `plot_groups[].channels` lists.
3. If the Logging tab referenced it in `AXIS_SIGNALS` / `SPINDLE_SIGNALS`, remove that mapping or the legend row will skip it.
4. Restart Probe Basic.

**No VFD / different spindle?** Delete all `"group": "spindle"` channels (and the `spindle_*` plot groups). The **SPINDLE** button can stay; plotted lines will simply be empty until you remap pins — or hide the button in `signal_monitor.py`.

**No A axis?** Remove `a_*` channels and drop `"A"` from `AXIS_ORDER` / axis buttons if you want a cleaner UI.

**Different VFD (not H100 mb2hal)?** Keep the channel `id`s if you like the UI labels, but change each `"pin"` to whatever your HAL exports (e.g. `vfdspeed.0.current`, `spindle.0.speed-in`). Re-check units/scale.

### Discover pins on an unknown machine

```bash
halcmd show pin
halcmd show sig
halcmd show pin mb2hal
halcmd show pin spindle
halcmd show pin lcec.0.0
```

Match names carefully: nets (`spindle-current`) are not always readable as pins — use the writer pin (`mult2.6.out`) or a pin connected to that net.

### CSV vs live plot

| | CSV | Logging tab plot |
|--|-----|------------------|
| Source | Every `channels[]` entry | SIGNAL mode + toggles only |
| Missing pin | Column of `nan` / blanks | Line stays flat / empty |
| After JSON edit | New session picks it up | Restart / reopen tab |

Context columns on every row: `line`, `feed`, `enabled`.

---

## Files

| Path | Role |
|------|------|
| `probe_basic/python/hal_signal_logger.py` | Poll HAL, write CSV, live buffers |
| `probe_basic/python/signal_plot_widget.py` | Live plot widget |
| `probe_basic/user_tabs/signal_monitor/` | Logging tab (`.py`, `.ui`, `.qss`) — SIGNAL button ↔ channel maps |
| `config/logging/signals.json` | **Channel definitions (edit this for hardware)** |
| `custom.hal` | Torque/velocity/drive-ferr + H100 spindle scaling → pins |
| `h100.mb2hal` | Modbus map for this mill’s VFD (omit/replace on other hardware) |
| `A6_TUNING.md` | A6 SDO gain defaults + Servo Tuning GUI / revert |
| `INSTALL_SERVO_TUNING.md` | How to install Servo Tuning + Logging on another machine |
| `ethercat-conf.xml` | PDO 606C/6077/60F4 + SDO 6065/6066 |
| `nc_files/x_tuning.ngc` | Example axis tuning program |
| `scripts/run_signal_logger.py` | Headless CLI logger (optional) |

---

## Test plan

| Phase | Verify |
|-------|--------|
| **0 — Setup** | LinuxCNC starts without HAL loadrt errors; [smoke test](PYTHON_PACKAGES.md#smoke-test) passes |
| **1 — HAL** | `tune-torque.*`, `tune-velocity.*`, `joint.*.f-error` respond to jog; spindle pins if configured |
| **2 — Tab** | Logging tab loads; axis/SPINDLE toggles, signal buttons, legend, and plot update |
| **3 — Program log** | Arm → run `x_tuning.ngc` in AUTO → CSV created, dialog on finish |
| **4 — Live log** | Start/stop live → CSV written while jogging / spindle on |
| **5 — Rate** | Change rate dropdown; CSV row spacing matches selection |
| **6 — CSV content** | One file; expected channel columns present (no surprise empty hardware) |
| **7 — Integration** | No motion regression; e-stop safe |

```bash
# HAL pins (axis + spindle examples)
halcmd getp tune-torque.0.out
halcmd getp joint.0.f-error
halcmd getp spindle.0.speed-out-abs
halcmd getp mult2.6.out

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
| Empty CSV columns | `halcmd show pin <name>` — fix or remove the pin in `signals.json` |
| SPINDLE lines empty | No mb2hal / wrong pin names — remap or delete `spindle_*` channels |
| Never starts on program | Must be AUTO; program must be running (`MODE_AUTO` + interpreter not idle) |
| No dialog on save | Check status line; look in `logs/signals/` |
| No plots | `sudo apt install python3-pyqtgraph` |
| Drive Er47.0 on fast moves | Tight 6065h limit — increase counts or 6066h delay in `ethercat-conf.xml` |
| Legend colors wrong | Edit `color` fields in `signals.json` |
| Mixed RPM + amps on one Y axis | In SPINDLE mode plot one unit family at a time (CMD/FB **or** A) |

---

## Related

Servo Tuning + Logging install: **[INSTALL_SERVO_TUNING.md](INSTALL_SERVO_TUNING.md)**. Drive tuning: **[A6_TUNING.md](A6_TUNING.md)**.
