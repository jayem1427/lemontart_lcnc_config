# Tool changes and tool length (M600)

This mill has a manual collet spindle and a contact tool setter. When a
program asks for a new tool, the machine parks so you can swap the cutter,
waits for you to confirm, then measures the new tool's length on the setter
and carries on. It's based on
[TooTall18T's tool_length_probe](https://github.com/TooTall18T/tool_length_probe)
(v5.0.2), adapted for Probe Basic.

---

## What happens on `T3 M600`

```
retract Z to G53 Z0  →  stop spindle  →  move to tool-load spot (G53 X270 Y100)
  →  "change tool" dialog  →  you swap the cutter and press RESUME
  →  move over the setter  →  probe down (G38)  →  write length to tool table
  →  G43 H3  →  retract  →  program continues
```

- **If the requested tool is already in the spindle and has a measured length**,
  M600 skips all of that and just applies `G43 H<n>`. No park, no dialog, no
  probe.
- **The tool-load spot and the setter are separate positions.** The load spot
  is where you have room for the collet wrench. The setter position is taught.
- **Tool-change moves are fast:** 30 000 mm/min XY and 10 000 mm/min Z, set in
  `tool_touch_off.ngc`, independent of Probe Basic's traverse setting.
- **Built-in M6 motion is off** (`TOOL_CHANGE_AT_G30 = 0`). Plain `M6` still
  works but only shows the dialog and syncs the tool number. It doesn't move or
  measure. Use it when lengths are already known.

### Cancelling

| You press | What happens |
|-----------|--------------|
| **RESUME** in the dialog | Measures and continues |
| **ABORT** in the dialog | Stops the program, cancels tool length (`G49`), retracts Z, parks at the tool-load spot |
| Esc / closing the dialog | Ignored. Use ABORT or RESUME |
| The main **Stop** button | Stops spindle and coolant, **keeps** `G43`, no motion (see below) |

Use the dialog's ABORT to cancel a tool change. The main Stop button assumes
the cutter in the spindle matches the active tool, which might not be true
halfway through a change.

---

## Teach before first use

1. **Setter position.** Jog over the middle of the setter's plate and press
   **SET TOOL TOUCH OFF POS** on the Tool Setter screen. This saves
   `#5181–#5183`. If you teach Z at home height, M600 approaches from
   `G53 Z0` and probes down. It never rapids to a guessed plate height.
2. **Spindle nose zero.** Load a **cutter, not the touch probe**, and press
   **PROBE SPINDLE NOSE ZERO** (saves `#3010`). The macro refuses to run with
   the probe loaded, because the probe input would be routed to the touch probe
   and the setter would never trip.
3. **Probe feeds and clearances.** Set them on the Tool Setter screen and press
   **UPDATE**.
4. **Tool-load spot.** Check that G53 X270 Y100 is a good place to change
   tools on your machine. To move it, edit `#<tool_load_x_coords>` /
   `#<tool_load_y_coords>` in `tool_touch_off.ngc`, and the same numbers in
   `go_to_g30.ngc` and `abort_tool_change.ngc`.

Then air-test with the spindle off: `T3 M600`, jog away, `T9 M600`, `T10 M600`.
Each one should stop at the load spot, show the dialog, then probe.

---

## Buttons in Probe Basic

| Button | Runs | Does |
|--------|------|------|
| **LOAD SPINDLE** | `load_spindle_safety_2.ngc` | Cutter: full M600. Touch probe: `M6` + `G43` only, no measuring |
| **M6 G43** | `m6_tool_call_*.ngc` | Dialog + `G43` with the length already in the table |
| **TOUCH OFF CURRENT TOOL** | `tool_touch_off.ngc` | Re-measure the tool already in the spindle (no dialog) |
| **SET TOOL TOUCH OFF POS** | | Teach the setter position (`#5181–#5183`) |
| **PROBE SPINDLE NOSE ZERO** | `probe_spindle_nose.ngc` | Teach `#3010` |
| **UPDATE** (Tool Setter screen) | `tool_setter_param_update.ngc` | Save feeds/clearances. Doesn't overwrite the taught position |

---

## Probe routing

The touch probe and the tool setter share LinuxCNC's single probe input.
HAL only listens to the one that makes sense for the tool in the spindle:

| Tool in spindle | Probe input listens to | Ignores |
|-----------------|------------------------|---------|
| **T99** (touch probe) | Touch probe, `lcec.0.1.di-2` | Tool setter |
| Anything else | Tool setter, `lcec.0.1.di-5` | Touch probe |

A third source, the laser, is switched in only during laser G38 moves with
`M62 P0` / `M63 P0` (see [LASER_TOOL_SETTER.md](LASER_TOOL_SETTER.md)).

```
halui.tool.number ─ comp.0 (== 99?) ─┬─ and2.3 ← touch probe (di-2) ─┐
                                     └─ not ─ and2.4 ← setter (di-5) ─┴─ or2.0 ─ and2.8 (off while laser on) ─ or2.3 ─ motion.probe-input
                                                         laser ─ and2.7 (on with M62 P0) ───────────────────────┘
```

### Changing the probe's tool number

The probe tool number lives in **three** places, and they must match:

| Where | Setting |
|-------|---------|
| `probe_basic/tool.tbl` | The row for the probe, e.g. `T99 P5 D+2.000000 ; touch probe` (D = stylus ball diameter) |
| `linuxcnc.var` `#3014` | Probe Basic's probe tool number. Set it on the Probe screen and press **UPDATE PROBE PARAMS** |
| `ethercat_mill.hal` | `setp probe-tool-num.value 99` |

HAL does **not** follow `#3014`. If you only change it in the UI, HAL keeps
routing to the wrong sensor. Restart LinuxCNC after editing the HAL. Symptoms
of a mismatch: "probe tool not in spindle" errors, LOAD SPINDLE running M600 on
the probe, or a probe move that never trips.

---

## Keep G43 on Stop

Stock Probe Basic cancels tool length (`G49`) on startup and on every abort.
On this mill the cutter stays in the collet between jobs, and `G49` made work
Z appear to jump by the tool length after every Stop. So:

| File | Stock | Here |
|------|-------|------|
| `ethercat_mill.ini` startup code | `G40 G49 G54 …` | `G40 G54 …` (no `G49`) |
| `on_abort.ngc` | `G49` | `o<restore_tool_length> call`: re-applies `G43 H#5400` if a tool with a measured length is loaded |
| `abort_tool_change.ngc` | `G49` | Still `G49`: mid-change, the cutter may not match |

After a fresh start or `M30`, LinuxCNC is still in `G49` until something
issues `G43` (M600, MDI, or a Stop).

**The risks of keeping G43.** These are the reasons stock configs don't do it:

- **Stopping mid-change** with the main Stop button can leave the old tool's
  length active for a new cutter. Use the dialog's ABORT instead.
- **Swapping a cutter by hand** without M600/M6/M61 leaves the old length
  active.
- **A stale tool number** with an empty spindle reapplies a length that isn't
  there. Unload with `T0` when the spindle is actually empty.
- **After an E-stop**, check the active G-codes for `G43 H…` before jogging to
  Z0.

**To go back to stock:** put `G49` back after `G40` in
`RS274NGC_STARTUP_CODE`, replace the restore call in `on_abort.ngc` with
`G49`, and restart.

---

## How the length is calculated

`tool_touch_off.ngc` uses Probe Basic's formula:
`length = ABS[spindle_zero + #5063 − probe_start_z]`. On top of the stock
routine it:

- reads the setter position only from `#5181–#5183` (no hard-coded numbers);
- aborts if the setter position is unset or outside the machine limits (each
  axis checked separately), or if spindle zero `#3010` is unset;
- aborts if the computed length is ≤ 0;
- switches to `G94` first (CAM output may be in `G93` inverse time);
- turns feed override on (`M50 P1`) before the dialog.

---

## Files

| File | Role |
|------|------|
| `m600.ngc` | The `M600` remap. Records the requested tool and calls `tool_touch_off` |
| `tool_touch_off.ngc` | The whole sequence: park, dialog, probe, write length |
| `go_to_g30.ngc` | Z-first move to the tool-load spot |
| `abort_tool_change.ngc` | Dialog ABORT: `G49`, retract, park |
| `on_abort.ngc` | Main Stop/abort: spindle and coolant off, laser mux off, restore `G43`. **No motion**: the machine may already be disabled |
| `restore_tool_length.ngc` | `G43 H#5400` when a measured tool is loaded |
| `load_spindle_safety_2.ngc` | LOAD SPINDLE button |
| `tool_setter_param_update.ngc` | Saves setter feeds; keeps the taught position |
| `probe_basic/toolchange_dialog.py` | The dialog with RESUME / ABORT |

---

## Copying this to another machine

This isn't a drop-in tab. It's macros, INI and HAL working together.

1. **Copy the macros** above into your subroutine path.
2. **INI:**

   ```ini
   [RS274NGC]
   SUBROUTINE_PATH = .:probe_basic/subroutines
   USER_M_PATH = .:probe_basic/subroutines
   REMAP=M600 modalgroup=6 ngc=m600
   ON_ABORT_COMMAND = o<on_abort> call

   [EMCIO]
   TOOL_CHANGE_AT_G30 = 0
   TOOL_CHANGE_QUILL_UP = 0
   ```

   Don't remap `M6`. Keep it as the "dialog only" option. Don't put inline `;`
   comments on `REMAP=` lines: the INI parser breaks.
3. **HAL:** don't loop `iocontrol.0.tool-change` straight back to
   `tool-changed`. The dialog has to confirm it. If you have both a touch probe
   and a setter, copy the probe-routing block from `ethercat_mill.hal`.
4. **Dialog:** copy `toolchange_dialog.py`, `toolchange_dialog_pb.ui` and the
   `dialogs:` section of `custom_config.yml`.
5. **Adjust** the tool-load coordinates and probe tool number for your machine.
6. **Teach and air-test** as above.

Optional TooTall18T extras (`m601`, `m300`, `m500`) are not installed here.
