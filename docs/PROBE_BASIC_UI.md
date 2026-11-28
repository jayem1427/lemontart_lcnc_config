# Probe Basic UI changes

[Probe Basic](https://github.com/kcjengr/probe_basic) 0.6.6 is the UI. This
page covers what's different from a stock install: INI display settings, a
custom DRO with a **SET Z** shortcut, a tool-change dialog with an **ABORT**
button, five custom tabs, and a few fixes to Probe Basic's own macros.

---

## Display settings (`[DISPLAY]` in the INI)

| Setting | Value | Why |
|---------|-------|-----|
| `DRO_DISPLAY` | `XYZA` | Loads the custom DRO below |
| `GEOMETRY` | `XYZA` | 4-axis backplot |
| `TOOL_TABLE_COLUMNS` | `TDZR` | No pocket column. It's a manual mill |
| `ATC_TAB_DISPLAY` | `0` | Hides the ATC tab. `[ATC] POCKETS = 1` is still set because Probe Basic's macros read it |
| `MAX_FEED_OVERRIDE` | `2.5` | 250 % instead of 200 % |
| `USER_TABS_PATH` | `probe_basic/user_tabs/` | Custom tabs |
| `CONFIG_FILE` | `probe_basic/custom_config.yml` | Swaps in the custom tool-change dialog |

`[TRAJ] AXES = 4` is required too. Probe Basic's go-to-zero / go-to-home
macros read it, and without it those buttons fail.

When upgrading Probe Basic, compare your INI with
[`probe_basic/pb_required_ini_settings.ini`](../probe_basic/pb_required_ini_settings.ini).

If Probe Basic doesn't draw properly on your graphics card, start it with
`QT_QUICK_BACKEND=software` (`launch.sh` already does this).

---

## SET Z on the DRO

The XYZA DRO (`probe_basic/user_dro_display/xyza_dros/`) adds a **SET Z**
button and a number field. It sets the active work offset so the current tool
tip reads the number you type:

| Type | Means |
|------|-------|
| `0` | The tip is exactly at work Z zero |
| `0.05` | The tip is 0.05 mm above zero, e.g. resting on a 50 µm shim |
| `-5` | The tip is 5 mm below the Z zero you want |

Press Enter or click SET Z. It runs `o<set_wco_z> call [value]`, which does
`G92.1` then `G10 L20 P0 Z<value>`. It changes only the work offset, never tool
length.

**REF ALL** on this DRO always reads "REF ALL". It doesn't switch to "HOMED".

The `xyzac_dros/` and `xyzbc_dros/` folders are unused alternatives. Only the
one named by `DRO_DISPLAY` loads.

---

## Tool-change dialog with ABORT

`custom_config.yml` replaces QtPyVCP's tool-change dialog with
`probe_basic/toolchange_dialog.py`:

```yaml
dialogs:
  toolchange:
    provider: toolchange_dialog:ToolChangeDialog
    kwargs:
      ui_file: {{ file.dir }}/toolchange_dialog_pb.ui
```

| | Stock | This config |
|---|-------|-------------|
| Continue | OK button | **ONCE TOOL IS LOADED - PRESS TO RESUME** |
| Cancel | Esc or closing the window | **ABORT** button only. Esc and close are ignored |
| After ABORT | Unclear state | Program aborted → `G49` → retract → park at the tool-load spot |

It uses the same HAL pins as stock (`qtpyvcp_manualtoolchange`), so nothing
changes in postgui HAL. Behaviour around it: [TOOL_CHANGE.md](TOOL_CHANGE.md).

---

## Postgui HAL

`probe_basic/probe_basic_postgui.hal` differs from Probe Basic's sim version:

| Stock sim | Here |
|-----------|------|
| Loops `probe-in` through `qtpyvcp.probe-in` | Not connected: `ethercat_mill.hal` already drives the probe signal, and a second writer won't load |
| RPM from a simulated encoder | RPM from the VFD (`spindle-speed-in`) |
| — | Spindle load % from VFD current (`mult2.7`, assumes ~4.2 A full load) |
| Cycle timer idle from `halui.program.is-idle` | Same signal, via the pendant's `pdnt.program.is-idle` net |

---

## Custom tabs

| Tab | Folder | Page |
|-----|--------|------|
| Servo Tuning | `probe_basic/user_tabs/servo_tuner/` | [SERVO_TUNING.md](SERVO_TUNING.md) |
| Logging | `probe_basic/user_tabs/signal_monitor/` | [SIGNAL_LOGGING.md](SIGNAL_LOGGING.md) |
| Laser Setter | `probe_basic/user_tabs/laser_setter/` | [LASER_TOOL_SETTER.md](LASER_TOOL_SETTER.md) |
| MQL | `probe_basic/user_tabs/mql_control/` | [COOLANT.md](COOLANT.md#the-mql-tab) |
| Vise Stop | `probe_basic/user_tabs/vise_stop/` | [VISE_STOP.md](VISE_STOP.md) |

`template_main/` and `template_sidebar/` are Probe Basic's empty templates.

**Probe Basic loads every folder in `user_tabs/`**, and crashes at startup if
a folder doesn't contain `<name>/<name>.py`. That happens after switching git
branches: a tab that exists on one branch leaves a folder with only
`__pycache__` behind. Delete those folders.

```bash
ls probe_basic/user_tabs/*/   # every folder should have its matching .py
```

To add a tab to another machine, copy its folder into your `USER_TABS_PATH`
and restart. Each tab's page lists the HAL and files it depends on.

---

## Local fixes to Probe Basic macros

The `probe_basic/subroutines/` folder holds Probe Basic's macros with a few
machine-specific fixes. Re-apply them if you merge in a newer Probe Basic:

- **Pocket / valley / calibration probe feed.** Several `probe_*.ngc` files
  passed `[3017]` (a literal 3017 mm/min) instead of `[#3017]` (the traverse
  feed parameter). Fixed here.
- **`probe_spindle_nose.ngc`** refuses to run with the touch probe loaded.
  HAL routes the probe input to the touch probe in that state, so a setter
  probe would never trip and Z would crash.
- **`tool_touch_off.ngc`** has many changes. See
  [TOOL_CHANGE.md](TOOL_CHANGE.md#how-the-length-is-calculated).

---

## Upgrading Probe Basic

1. Compare your INI with the new `pb_required_ini_settings.ini`.
2. Keep: `SUBROUTINE_PATH`, `REMAP=M600/M201/M202`, `TOOL_CHANGE_*`,
   `ON_ABORT_COMMAND`, `USER_DROS_PATH`, `USER_TABS_PATH`, `CONFIG_FILE`.
3. Merge `probe_basic_postgui.hal` by hand. Keep the spindle and probe
   differences above.
4. If you take new macros, re-apply the local fixes.
5. If `linuxcnc.var` got reset, re-teach the setter position (`#5181–#5183`)
   and spindle zero (`#3010`).
