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

Probe Basic touch-probe tool number: `#3014` in `linuxcnc.var` (must match the tool table slot and HAL). See **[Touch probe tool number](#touch-probe-tool-number-setup-and-renumbering)** below.

## Touch probe tool number (setup and renumbering)

This config uses **one tool table slot** for the touch probe (default **T99**). That same number must appear in three places — NGc macros read `#3014` (Probe Basic’s probe-tool parameter), but **HAL probe routing** uses its own constant and does **not** follow `#3014` automatically.

### Three places that must agree

| # | Where | What to set | Example (default) |
|---|--------|-------------|-------------------|
| 1 | **`probe_basic/tool.tbl`** | Tool table row: `T<n>`, pocket, **diameter** `D`, optional length `Z` | `T99  P5  D+2.000000 ; touch probe` |
| 2 | **`linuxcnc.var`** → **`#3014`** | Probe Basic “probe tool number” (also set from the Probe screen) | `3014  99.000000` |
| 3 | **`ethercat_mill.hal`** | `setp probe-tool-num.value <n>` — gates DI5 vs DI2 by `halui.tool.number` | `setp probe-tool-num.value 99` |

If any one of these differs from the others, symptoms include: Probe Basic aborts (“probe tool not in spindle”), LOAD SPINDLE runs M600 on the touch probe, or HAL listens to the toolsetter while T99 is loaded (and vice versa).

**You do not need to edit** individual `probe_*.ngc` files — they use `#3014` at runtime. **You must edit HAL** when renumbering; changing only the Probe Basic UI is not enough.

### First-time setup (copying this repo)

1. **Pick a tool number** not used by your cutters (99 is a common convention; any free integer works).
2. **Tool table** — add or edit the row in `probe_basic/tool.tbl`:
   - `T<n>  P<pocket>  D+<probe_diameter_mm>  ; touch probe`
   - Set `D` to the **stylus ball diameter** (Trigger-type probes), not shank size.
3. **Probe Basic UI** — open the Probe / touch-probe settings, set **Probe tool number** to `<n>`, set feeds/clearances as needed, click **UPDATE PROBE PARAMS** (runs `touch_probe_param_update.ngc` → writes `#3014` and related params to `linuxcnc.var`).
4. **HAL** — in `ethercat_mill.hal`, set `setp probe-tool-num.value <n>` to the same number.
5. **Restart LinuxCNC** so HAL reloads the constant.
6. **Verify** — MDI `T<n> M6`, confirm in HAL: `halcmd show pin comp.0.equal` is TRUE when that tool is in the spindle; trip touch probe → `motion.probe-input` TRUE; trip toolsetter → ignored.

Optional: set `#3014` directly in `linuxcnc.var` before first launch if you are not using the Probe Basic UI yet — but still align `tool.tbl` and HAL.

### Changing the probe number later

Example: move from T99 to **T50**.

1. Update **`probe_basic/tool.tbl`** — rename `T99` → `T50` (or add T50 and remove T99).
2. Probe Basic → set probe tool number to **50** → **UPDATE PROBE PARAMS** (or edit `#3014` in `linuxcnc.var`).
3. Edit **`ethercat_mill.hal`**: `setp probe-tool-num.value 50`.
4. Restart LinuxCNC.
5. Re-load the probe with **LOAD SPINDLE** or `T50 M6` and re-run a quick probe test.

Update README cross-references if you document a non-99 default elsewhere.

### Related (not the tool *number*)

| Item | File / param | Notes |
|------|----------------|-------|
| Probe diameter for routines | `#3014` row in tool table `D` column | Used for offset math in probing |
| Skip M600 when loading probe | `load_spindle_safety_2.ngc` | Uses `#3014`; no edit if `#3014` is correct |
| Metrology | `probe_basic/subroutines/metrology/README.md` | Assumes probe loaded and `#3014` matches spindle |

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
2. **PROBE SPINDLE NOSE ZERO** → `#3010` (touch probe `T#3014` must **not** be in the spindle — HAL routes probe input to the touch probe only when that tool is loaded)
3. Set probe feeds / retract in Tool Setter screen → **UPDATE** (`tool_setter_param_update.ngc`)

## CAM / post processor (`linuxcnc-djr.cps`)

Fusion post for this config. Install in Fusion **Posts** folder (replace the old file completely — Fusion caches posts).

**Post engine 45702+ required** (current Fusion). Post dialog groups: **Tool Change**, **Multi-Axis Setup**, etc.

If options still look like the old stock list, Fusion is still using a cached copy: remove `linuxcnc-djr.cps` from Personal Posts, restart Fusion, copy the new file in, and re-select it when posting.

| Setting | Value | Why |
|---------|-------|-----|
| **Tool change command** | **M600 — toolsetter probe** (`toolChangeMode: "M600"`) | Lemontart default — see below |
| **Preload tool** | **Off** (`preloadTool: false`) | Avoids a bare `T` for the next tool after tool change |
| **Fourth axis mounted along** | **Along X** (`fourthAxisAround: "x"`) | **Multi-Axis Setup** — enables A output and kinematics |
| **4th axis is a table** | **On** (`fourthAxisIsTable: true`) | Table rotary on X (Lemontart `trivkins coordinates=XYZA`) |
| **G93 inverse time** | **On** (`useInverseTimeFeed: true`) | Simultaneous `G1 X Y Z A` uses inverse-time `F` |
| Spindle after tool change | Post emits `M3`/`M4` after tool change M-code | M600 stops spindle; CAM must restart it (post does this) |

In Fusion’s post dialog, open **Tool Change** and **Multi-Axis Setup**. If you use a Fusion **Machine Definition** on the setup, its kinematics override the post’s hardcoded A axis (set **Fourth axis mounted along** to **None** only if you intentionally want 3-axis output).

Do **not** end programs with `T0 M600`. Keep touch probe **T99** out of CAM tool-change lists (load via Probe Basic only).

### Tool change command (Fusion post property)

Open the **Tool Change** group when posting. **`toolChangeMode`** selects what the post writes after each `T<n>`:

| Mode | Posted G-code | Who needs it |
|------|---------------|--------------|
| **M600 — toolsetter probe** (default) | `T<n> M600` | **Lemontart / manual collet + toolsetter.** CAM triggers the full cycle: retract, G30 collet-change position, Manual Tool Change OK dialog, probe on the setter, `G10` length update via `m600.ngc` → `tool_touch_off.ngc`. Use for normal multi-tool CAM where each cutter is measured automatically. |
| **M6 — manual OK only** | `T<n> M6` | **Lengths already known.** Tool table is correct (presetter, earlier M600, or single tool). Shows the OK dialog and syncs tool number only — **no** move to G30, **no** setter probe. Dry runs, test air cuts, or when the setter is unavailable. Same idea as Probe Basic **M6 G43** on the tool page. |
| **T only — no M-code** | `T<n>` | **Fully manual workflow.** You load and measure with Probe Basic (**LOAD SPINDLE**, panel touch-off) before running CAM. CAM must not call any tool-change macro. Single-operation or repeat-run jobs where the spindle is already set up. |

**Why M600 exists on this machine:** LinuxCNC built-in M6 tool-change motion is disabled (`TOOL_CHANGE_AT_G30=0`). M600 is a custom `REMAP` that runs the TooTall18T / Lemontart toolsetter sequence from CAM. Without it, Fusion’s default `M6` would only show the OK dialog — it would not probe or update length.

**Spindle note:** M600 stops the spindle during the measure cycle; the post still emits `M3`/`M4` after the tool change block. With **M6** or **T only**, you are responsible for spindle state before the next cut.

### Preload tool (Fusion post property)

When **on**, after each tool change the post also writes a bare **`T<next>`** with no M-code — Fusion’s “preload next tool for ATC” habit.

On a **manual collet** mill that is usually wrong:

- The bare `T` updates **prepared** tool number only; nothing is in the spindle until you physically change and the tool-change macro completes.
- Your HAL probe gating uses **`halui.tool.number`** (spindle tool). An extra prepared `T` does not match what is physically loaded and can confuse debugging.
- There is no carousel to prefetch into.

Leave **`preloadTool: false`** unless you add a real ATC later and know you want prepared-tool lookahead.

### Simultaneous 4th axis (G93 inverse time)

The post outputs standard LinuxCNC blocks for coordinated **X Y Z A** moves:

```ngc
G93 G1 X... Y... Z... A... F...
```

- **Indexing** (tilt A, then 3-axis cut): `G0`/`G1` with A on plane changes — no special token.
- **Simultaneous** (swarf / multi-axis): `onLinear5D` uses **`getMultiaxisFeed`** to compute an inverse-time **`F`** from the combined linear + rotary move length, then posts **`G93 G1`** (not the invalid `linear5D` word).
- **Plain 3-axis** cuts still use **`G94`** and a normal feed-per-minute `F`.

Machine definition in the post: **table A along X** (`fourthAxisAround: "x"`, `fourthAxisIsTable: true`), **`optimizeMachineAngles2(1)`** (map tip, non-TCP) to match **`trivkins coordinates=XYZA`** in `ethercat_mill.ini`. Do not enable TCP in Fusion for this config unless you add TCP kinematics in LinuxCNC.

In Fusion, use **4-axis simultaneous** / multi-axis strategies with this post selected; verify the first program on air with low feed override.

### Operator notes

- After CAM `M600`, post-probe `M00` may pause — press **Cycle Start**; feed override is unlocked before the pause

## ATC compatibility

- `load_spindle_safety*.ngc` default `#<number_of_pockets>=1` when no `[ATC]` section
