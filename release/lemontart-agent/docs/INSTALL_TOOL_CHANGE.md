# Install: Tool change + toolsetter

How to install this mill’s **manual collet tool-change** workflow (TooTall18T-style `M600` + Probe Basic toolsetter panel) on another Probe Basic machine.

This is **not** a Probe Basic UI plugin. Tool change uses **built-in** Probe Basic screens plus your **NGC remaps**, **INI**, and **HAL**. For UI drop-in tabs (Servo Tuning / Logging), see **[INSTALL_SERVO_TUNING.md](INSTALL_SERVO_TUNING.md)**. Full behavior reference: **[TOOLSETTER.md](TOOLSETTER.md)**.

---

## What you get

| Piece | Role |
|-------|------|
| `M600` remap | CAM entry: retract → **tool-load** pause → M6 OK dialog → probe setter → `G10` length |
| `tool_touch_off.ngc` | Core change + measure routine |
| Custom abort dialog | **ABORT** parks at tool-load — [PROBE_BASIC_UI.md](PROBE_BASIC_UI.md) |
| Probe Basic buttons | LOAD SPINDLE / TOUCH OFF / SET TOOL TOUCH OFF POS (built-in panels) |
| HAL probe routing | Touch probe vs contact toolsetter gated by spindle tool number |

Built-in LinuxCNC M6 motion is **disabled**; macros own retract and park. Tool-load XY is separate from the taught setter — [TOOLSETTER.md](TOOLSETTER.md#tool-load-position-collet-change).

---

## Prerequisites

- Probe Basic with manual tool-change dialog (`qtpyvcp_manualtoolchange`)
- A contact toolsetter on `motion.probe-input` (and optionally a separate touch probe)
- Manual collet (or similar) — this config hides the ATC tab (`ATC_TAB_DISPLAY=0`)

---

## 1. Copy macros

Into your config’s subroutine path (this repo uses `probe_basic/subroutines/`):

| File | Required |
|------|----------|
| `m600.ngc` | Yes — CAM / remap entry |
| `tool_touch_off.ngc` | Yes — core routine |
| `go_to_g30.ngc` | Yes — Z-first move to G30 |
| `tool_setter_param_update.ngc` | Yes — sync PB UI params |
| `load_spindle_safety.ngc` / `load_spindle_safety_2.ngc` | Yes if you use PB **LOAD SPINDLE** |

Optional TooTall extras (`m601`, `m300`, `m500`) are **not** remapped here.

---

## 2. INI

Minimum pattern (see `ethercat_mill.ini`):

```ini
[RS274NGC]
SUBROUTINE_PATH = .:probe_basic/subroutines
USER_M_PATH = probe_basic/subroutines
REMAP=M600 modalgroup=6 ngc=m600
# Do NOT remap M6 — keep stock M6 for “OK only” / known lengths

[EMCIO]
TOOL_CHANGE_AT_G30 = 0
TOOL_CHANGE_QUILL_UP = 0

[DISPLAY]
ATC_TAB_DISPLAY = 0

[ATC]
POCKETS = 1
```

Notes:

- Do not put inline `;` comments on `REMAP=` lines (breaks the INI parser).
- `TOOL_TABLE_COLUMNS=TDZR` (no pocket column) is used on this manual mill — optional.

---

## 3. HAL

### Manual tool-change dialog

Wire `qtpyvcp_manualtoolchange` in postgui HAL (this repo: `probe_basic_postgui.hal`) so M6/M600 can show tool number + remark and wait for OK.

Remove any auto `tool-change` → `tool-changed` loop that acknowledges without the operator.

### Touch probe vs toolsetter (if both exist)

Both sensors often share `motion.probe-input`. This mill **gates** by spindle tool:

| Spindle tool | Active input |
|--------------|--------------|
| Probe tool (default **T99**) | Touch probe |
| Any other tool | Contact toolsetter |

Port the `comp` / `and2` / `or2` block from `ethercat_mill.hal`, and keep VFD fault OR on a **separate** `or2` instance (`custom.hal` uses `or2.1` here).

Align **three** places to the same probe tool number:

1. `probe_basic/tool.tbl` row  
2. `#3014` in `linuxcnc.var` (Probe Basic probe tool number)  
3. HAL `setp probe-tool-num.value <n>`

Details: **[Touch probe tool number](TOOLSETTER.md#touch-probe-tool-number-setup-and-renumbering)**.

---

## 4. Teach positions

1. Jog to the collet-change / toolsetter XY (and Z as you use G30).
2. In Probe Basic, use **SET TOOL TOUCH OFF POS** (writes `#5181`–`#5183`).
3. Confirm `tool_touch_off.ngc` uses those parameters (this repo does — no hardcoded setter XYZ).

---

## 5. CAM / Fusion

- Prefer **M600** for multi-tool jobs that should probe the setter after each change.
- Use stock **M6** only when lengths are already known (OK dialog, no setter move).
- Do not end programs with `T0 M600`.
- Keep the touch-probe tool out of CAM tool-change lists.

Post notes: **[TOOLSETTER.md](TOOLSETTER.md)** (Fusion / `post-processor/linuxcnc-djr.cps` section).

---

## 6. Smoke test

1. Restart LinuxCNC after INI/HAL changes.
2. MDI `T<n> M600` (cutter, not probe) → retract → G30 → OK dialog → setter probe → length updates.
3. Load probe tool → touch probe trips `motion.probe-input`; toolsetter ignored (if gating installed).
4. Load cutter → toolsetter trips `motion.probe-input`; touch probe ignored.
5. Probe Basic **TOUCH OFF CURRENT TOOL** re-measures without a full CAM-style pause path.

---

## What this is not

- Not a `user_tabs` drop-in — you cannot “install tool change” by copying one folder alone.
- Not an ATC carousel installer — ATC tab is hidden; `POCKETS=1` only satisfies PB macros.
- Sharing with another machine still requires adapting DI pins, tool numbers, and G30/setter geometry to that hardware.
