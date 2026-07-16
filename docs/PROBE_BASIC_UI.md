# Probe Basic UI customizations

Stock [Probe Basic](https://github.com/kcjengr/probe_basic) is the shell; this repo adds machine-specific HAL, DRO widgets, and operator shortcuts. For toolsetter / M600 / probe routing, see [TOOLSETTER.md](TOOLSETTER.md).

---

## Display configuration (`ethercat_mill.ini`)

| Setting | Value | vs stock PB template |
|---------|-------|----------------------|
| `DISPLAY` | `probe_basic` | Same |
| `DRO_DISPLAY` | `XYZA` | Custom folder below |
| `GEOMETRY` | `XYZA` | Template often XYZ |
| `[TRAJ] AXES` | `4` | Needed by `go_to_zero` / `go_to_home` macros |
| `TOOL_TABLE_COLUMNS` | `TDZR` | Template `TZDR` / `TPDZR` |
| `ATC_TAB_DISPLAY` | `0` | ATC tab hidden |
| `MAX_FEED_OVERRIDE` | `2.5` (250%) | Template `2.0` |
| `CONFIG_FILE` | `probe_basic/custom_config.yml` | Minimal overrides |
| `USER_DROS_PATH` | `probe_basic/user_dro_display/` | Custom SET Z DRO |
| `USER_BUTTONS_PATH` | `probe_basic/user_buttons/` | Template placeholder |

Required INI keys for Probe Basic compatibility: [`probe_basic/pb_required_ini_settings.ini`](../probe_basic/pb_required_ini_settings.ini) — compare when merging upgrades.

---

## Custom XYZA DRO — SET Z / REF ALL

**Files:** [`probe_basic/user_dro_display/xyza_dros/dros_xyza.py`](../probe_basic/user_dro_display/xyza_dros/dros_xyza.py), [`dros_xyza.ui`](../probe_basic/user_dro_display/xyza_dros/dros_xyza.ui)

The main DRO panel includes a **SET Z** button (left) and mm entry field (right). This is a Lemontart-specific shortcut not present in upstream Probe Basic.

**REF ALL** always shows the label `REF ALL` (does not flip to `HOMED`). It still runs `machine.home.all` and disables while any joint is homing. Homing order is Z → X → Y → A — see [DEVIATIONS.md](DEVIATIONS.md#ref-all-sequence).

### What it does

Sets the **active work offset Z** so the current tool position equals the value you enter — without running a full probe cycle.

Implementation: MDI `o<set_wco_z> call [<value>]` → [`probe_basic/subroutines/set_wco_z.ngc`](../probe_basic/subroutines/set_wco_z.ngc):

```ngc
G92.1
G10 L20 P0 Z#<z_value>
```

### When to use

| Entry | Meaning |
|-------|---------|
| `0` | Current tip is exactly at WCO Z zero |
| `0.05` | Tip is 0.05 mm **above** zero (e.g. after feeling a 50 µm shim) |
| `-5` | Tip is 5 mm **below** the WCO plane you want as Z=0 |

Press **Enter** in the field or click **SET Z**. Empty field opens a numeric dialog (default 0).

### Constraints

- Machine must not be estopped; runs in MDI mode.
- Clears G92 with `G92.1` before `G10 L20` (matches startup intent).
- Does **not** update tool length (`G43` / tool table) — only WCS offset.
- For automatic Z from probing, use Probe tab **Z minus WCO** routines instead.

---

## Spindle RPM and load (postgui HAL)

[`probe_basic/probe_basic_postgui.hal`](../probe_basic/probe_basic_postgui.hal) wires:

```hal
net spindle-speed-in => qtpyvcp.spindle-encoder-rpm.in
net spindle-current => mult2.7.in0
net spindle-load-percent mult2.7.out => qtpyvcp.spindle-load-indicator.in-f
```

- **RPM** comes from VFD feedback (`custom.hal` → `spindle-speed-in`), not from the sim hallib `scale_to_rpm` block.
- **Load %** assumes ~4.2 A max motor current (`mult2.7.in1 = 23.81`). Tune if your spindle current scale differs.

Stock hallib also loops `probe-in` through QtPyVCP for simulation. This config **leaves that disconnected** so only `ethercat_mill.hal` drives `motion.probe-input`.

---

## Manual tool change dialog (ABORT CYCLE)

Stock Probe Basic uses the QtPyVCP `ToolChangeDialog`. This repo **replaces** it via [`probe_basic/custom_config.yml`](../probe_basic/custom_config.yml):

```yaml
dialogs:
  toolchange:
    provider: toolchange_dialog:ToolChangeDialog
    kwargs:
      ui_file: {{ file.dir }}/toolchange_dialog_pb.ui
```

**Files:** [`toolchange_dialog.py`](../probe_basic/toolchange_dialog.py), [`toolchange_dialog_pb.ui`](../probe_basic/toolchange_dialog_pb.ui)

### Behavior vs stock

| | Stock PB | This machine |
|---|----------|--------------|
| Resume | OK / change button | **ONCE TOOL IS LOADED - PRESS TO RESUME** |
| Cancel mid-change | Often Esc / window close | **ABORT** button only — Esc and close are **ignored** |
| After ABORT | Interpreter stuck or ambiguous | `program.abort()` → MDI `o<abort_tool_change> call` → G53 Z0 → tool-load XY (270, 100) |
| After estop during dialog | — | Park skipped (machine disabled); `on_abort.ngc` handles spindle/coolant only |

HAL contract is unchanged: same `qtpyvcp_manualtoolchange` pins (`change`, `changed`, `number`). Postgui wiring stays stock.

Used by `M6` (manual OK mode), **M6 G43**, and **M600** collet pause in `tool_touch_off.ngc`. Full flow: [TOOLSETTER.md](TOOLSETTER.md#abort--cancel-during-m600).

---

## User buttons

[`probe_basic/user_buttons/template_user_buttons/`](../probe_basic/user_buttons/template_user_buttons/) is the stock template (empty shell). Machine actions live on **Probe Basic built-in tabs** (Tool Setter, Probe, Tool Change) mapped to subroutines in `probe_basic/subroutines/`.

Key mappings (full table in [TOOLSETTER.md](TOOLSETTER.md#probe-basic-ui--which-button-does-what)):

| Control | Subroutine |
|---------|------------|
| LOAD SPINDLE | `load_spindle_safety_2.ngc` |
| TOUCH OFF CURRENT TOOL | `tool_touch_off.ngc` |
| SET TOOL TOUCH OFF POS | teaches `#5181–#5183` |
| UPDATE (tool setter) | `tool_setter_param_update.ngc` |
| UPDATE PROBE PARAMS | `touch_probe_param_update.ngc` |

---

## Other DRO variants in repo

| Folder | Purpose |
|--------|---------|
| `xyza_dros/` | **Active** — 4-axis + SET Z |
| `xyzac_dros/` | Alternate 5-axis-style layout (not selected in INI) |
| `xyzbc_dros/` | Alternate BC layout (not selected in INI) |

Only the path named by `DRO_DISPLAY` in the INI is loaded.

---

## Cycle timer

`time` component in postgui drives Probe Basic run timer widgets. Idle detection uses `pdnt.program.is-idle` (shared net with WHB pendant) inverted to `time.0.start`.

---

## Launch note

[`launch.sh`](../launch.sh) sets `QT_QUICK_BACKEND=software`. Use it if Probe Basic fails to render on your GPU driver.

---

## Upgrading Probe Basic

1. Diff your INI against new `pb_required_ini_settings.ini`.
2. Preserve: `SUBROUTINE_PATH`, `REMAP=M600`, `TOOL_CHANGE_*`, `ON_ABORT_COMMAND`, custom `USER_DROS_PATH`.
3. Merge `probe_basic_postgui.hal` carefully — keep spindle and probe deviations above.
4. Re-run teach steps for toolsetter (`#5181–#5183`, `#3010`) if `linuxcnc.var` is reset.

Upstream docs: [Probe Basic wiki / README](https://github.com/kcjengr/probe_basic).
