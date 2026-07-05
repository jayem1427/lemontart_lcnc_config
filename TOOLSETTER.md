# Toolsetter integration (TooTall18T + Probe Basic)

Semi-automatic tool length measurement for a **manual collet spindle**, based on [TooTall18T/tool_length_probe](https://github.com/TooTall18T/tool_length_probe) v5.0.2, adapted for Probe Basic.

## INI (`ethercat_mill.ini`)

- `REMAP=M600 modalgroup=6 ngc=m600` — CAM entry for change + probe (**do not remap M6**)
- `TOOL_CHANGE_AT_G30=0`, `TOOL_CHANGE_QUILL_UP=0` — LinuxCNC built-in M6 motion disabled; macros handle retract and G30
- `SUBROUTINE_PATH` / `USER_M_PATH` → `probe_basic/subroutines`
- `[ATC] POCKETS=1` — satisfies Probe Basic ATC-aware subroutines; tab hidden via `ATC_TAB_DISPLAY=0`
- `TOOL_TABLE_COLUMNS=TDZR` — drop pocket column on manual mill (was `TPDZR`)
- `REMAP` lines must not use inline `;` comments (breaks INI parser)

## HAL

- `probe_basic_postgui.hal` — `qtpyvcp_manualtoolchange` wired for M6 OK dialog (tool number + remark)
- `ethercat_mill.hal` — removed `tool-change` → `tool-changed` auto-loop; operator must confirm via dialog
- `ethercat_mill.hal` — touch probe (DI5) vs contact toolsetter (DI2) gated onto `motion.probe-input` by `halui.tool.number` (T99 → probe only; any other tool → toolsetter only). See **Touch probe vs toolsetter routing** in [README.md](README.md).
- `custom.hal` — VFD fault OR uses `or2.1`; `or2.0` is probe routing in `ethercat_mill.hal` (`loadrt or2 count=2` — do not add a second `or2` load with `names=`)

Probe Basic touch-probe tool number: `#3014` in `linuxcnc.var` (must match `T99` in `probe_basic/tool.tbl` and `setp probe-tool-num.value 99` in HAL).

## Macros (`probe_basic/subroutines/`)

| File | Role |
|------|------|
| `tool_touch_off.ngc` | Core routine: retract, optional G30, M6 prompt, probe, `G10` length, `G43` |
| `m600.ngc` | Sets `#2000=1`, calls `tool_touch_off` (CAM / panel entry) |
| `go_to_g30.ngc` | Z-first move to G30 (`#5181`–`#5183`) |
| `tool_setter_param_update.ngc` | Syncs Probe Basic UI params to `#3004`–`#3013`; does **not** overwrite `#5181`–`#5183` |

**Not installed:** `m601`, `m300`, `m500` — optional TooTall18T extras, not remapped, not required.

### `tool_touch_off.ngc` — M600 / automatic (`#2000=1`)

- `brake_after_M600=1`, `disable_pre_pos=0` — collet wrench at G30, then probe
- Flow: `G49` → `G53 Z0` → stop spindle → `G53` G30 XY/Z → **M6 OK dialog** → setter XY → probe → `G10 L1` → `T G43` → `G53 Z0`
- G30 and setter position both use `#5181`–`#5183` (teach via **SET TOOL TOUCH OFF POS**)
- Post-probe `M00` when `brake_after_M600=1` (for CAM); skipped when `#2001=1` (panel call)
- `M50 P1` runs **before** any `M00`/`M01` so feed override unlocks even if program pauses

### `tool_touch_off.ngc` — manual touch-off (`#2000=0`, Probe Basic button)

- Uses `#<_current_tool>` when `#<_selected_tool>` is 0 (M61 load quirk)
- No M6 in manual mode — `T#` only to sync tool table
- Single traverse: `G53 G1 Z0` → `G53 G1` setter XY at traverse feed; skips duplicate XY reposition

### Probe / length math (fixes vs stock PB routine)

- Setter coords from `#5181`–`#5183` only (no hardcoded XYZ)
- Abort if setter XY unset or outside machine limits
- Abort if spindle zero `#3010` not configured
- Probe start Z clamped when PB spindle zero is full Z-home→plate distance
- Length: `ABS[spindle_zero + #5063 - offset_z]` (Probe Basic formula); `offset_z = #5422` at probe start
- Abort if computed length ≤ 0; no nested `(` in `ABORT` messages (NGC comment syntax)
- Feed fallbacks when `#3004`–`#3006` are zero in `linuxcnc.var`

### `tool_setter_param_update.ngc`

- Preserves `#5181`–`#5183` on UPDATE (SET TOOL TOUCH OFF POS teach)
- Default spindle zero when `#3010` is 0

## Probe Basic UI — which button does what

| Control | Subroutine | Behavior |
|---------|------------|----------|
| **LOAD SPINDLE** (TOOL CHANGE PANEL) | `load_spindle_safety_2.ngc` | Cutters: `T#` → `#2001=1` → `m600`. Touch probe (`#3014`): `T M6` + `G43` + `M5` only |
| **M6 G43** (tool page / bottom bar) | `m6_tool_call_*.ngc` | `T M6` + `G43` only — OK dialog, no move, no probe; uses existing table length |
| **TOUCH OFF CURRENT TOOL** | `tool_touch_off.ngc` | Re-measure tool already in spindle (manual mode) |

## Teach before first use

1. Jog over setter → **SET TOOL TOUCH OFF POS** (`#5181`–`#5183`)
2. **PROBE SPINDLE NOSE ZERO** → `#3010`
3. Set probe feeds / retract in Tool Setter screen → **UPDATE** (`tool_setter_param_update.ngc`)

## CAM / operator notes

- Use `T<n> M600` in G-code, **not** `M6`; emit `M3 S…` after `M600` (macro does not restart spindle)
- Avoid `T0 M600` at program end (G43/G49 hazard on abort)
- After CAM `M600`, post-probe `M00` may pause — press **Cycle Start**; feed override is unlocked before the pause

## ATC compatibility

- `load_spindle_safety*.ngc` default `#<number_of_pockets>=1` when no `[ATC]` section
