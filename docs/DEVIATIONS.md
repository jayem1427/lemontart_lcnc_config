# Deviations from stock LinuxCNC and Probe Basic

This document lists deliberate differences between **this config** and typical upstream examples. Use it when something “should work like the docs say” but does not — the answer is often here.

Stock references:

- [Probe Basic INI template](../probe_basic/pb_required_ini_settings.ini)
- Upstream Probe Basic **sim hallib** (not shipped here — this mill uses EtherCAT HAL only)
- [LinuxCNC tool change](https://linuxcnc.org/docs/html/config/ini-config.html#sub:emcio-section)
- [RS274NGC remapping](https://linuxcnc.org/docs/html/remap/remap.html)

---

## Summary table

| Area | Stock / typical | This machine |
|------|----------------|--------------|
| Tool change from CAM | `T M6` with optional `TOOL_CHANGE_AT_G30` | **`T M600`** remapped; built-in M6 motion disabled |
| M6 behavior | May move to G30 / retract | **Dialog only** — no auto `tool-changed` loop |
| Touch probe HAL | Single `motion.probe-input` wire | **Tool-gated mux** (T99 → DI5, else → toolsetter DI2) |
| Probe Basic probe pin | `qtpyvcp.probe-in` ↔ `motion.probe-input` | **Direct HAL only** — PB probe widget disconnected |
| ATC | Carousel tab + `TPDZR` columns | **`POCKETS=1`**, tab hidden, **`TDZR`** columns |
| Geometry | Often XYZ | **XYZA** `trivkins`, table rotary on X |
| Spindle feedback | Encoder or sim `scale_to_rpm` | **VFD Modbus** freq → `spindle.0.speed-in` |
| At-speed | `near` or drive ready bit | **`near` + 5 s `timedelay`** after RPM match |
| Homing required | Default (forced) | **`NO_FORCE_HOMING = 1`** (bench — revert for production) |
| A axis homing | Real switch sequence | **Disabled** — `HOME_SEQUENCE = 3` (after Z/X/Y), zero search vel |
| Z− limit | Usually wired | **Commented out** in HAL (pin free) |
| Feed override max | 100–200% | **250%** (`MAX_FEED_OVERRIDE = 2.5`) |
| Fusion post | Stock `linuxcnc.cps`, `M6`, preload `T` | **`linuxcnc-djr.cps`**, M600 default, no preload |
| `PROGRAM_PREFIX` | Relative to config | **Absolute path** in committed INI — change on clone |
| Joint following error | Tight (e.g. ~2 mm / 1 mm) | **Relaxed** `FERROR = 1270`, `MIN_FERROR = 254` for bench — tighten later |
| M600 collet pause | Often same as setter / G30 | **Separate tool-load XY** (default G53 270, 100) vs taught setter `#5181–#5183` |
| Manual Tool Change dialog | Stock QtPyVCP; Esc cancels | **Custom dialog** with **ABORT**; Esc/close ignored — [PROBE_BASIC_UI.md](PROBE_BASIC_UI.md) |
| Drive position deviation | Drive defaults | **SDO 6065/6066** ≈ 0.5 mm / 0.5° / 250 ms (one-click raises 6065 to 2.0 during moves) — [A6_TUNING](A6_TUNING.md) |
| Probe Basic sim HAL | `probe_basic/hallib/` + `probe_basic.ini` in upstream | **Not shipped** — EtherCAT HAL only; learn on stock LinuxCNC sim first |
| Laser tool setter | M62 P0 mux to `motion.probe-input` for G38 | [LASER_TOOL_SETTER](LASER_TOOL_SETTER.md) |
| Pocket probe traverse feed | `#3017` from Probe Basic | **Local fix** — several `probe_*.ngc` had bare `[3017]` (3017 mm/min literal) |
| PROBE SPINDLE NOSE ZERO | Runs on setter input | **Aborts if T#3014 loaded** — HAL routes touch probe only when that tool is in spindle |

---

## Motion and INI

### `NO_FORCE_HOMING = 1`

```ini
# ethercat_mill.ini [TRAJ]
NO_FORCE_HOMING = 1
```

Stock LinuxCNC blocks motion until all joints with `HOME_SEQUENCE > 0` are homed. This flag relaxes that for bench work.

**Revert for production:** comment out the line and confirm Home All behavior on all four joints.

### REF ALL sequence

`HOME_SEQUENCE`: Z=`0`, X=`1`, Y=`2`, A=`3` — sequential (wait for prior joint).
X/Y search toward the negative end (~33 mm/min); Z search toward **+Z** home
(~33 mm/min). Host `FERROR` stays wide (1270 / 254) for bench homing.

### `[TRAJ] AXES = 4`

Probe Basic macros such as `go_to_zero.ngc` / `go_to_home.ngc` expect `#<_ini[traj]axes>` (axis count). Without it, `#<geometry>` was undefined and those buttons failed. Default fallback is `#<_ini[kins]joints>` when the INI key is missing.

### REF ALL button label

XYZA DRO **REF ALL** always shows `REF ALL` (the old `status:all_axes_homed` → `HOMED` text rule was removed). The button still disables while any joint is homing.

### A axis “virtual homing”

```ini
# ethercat_mill.ini [JOINT_3]
HOME_SEARCH_VEL = 0.0
HOME_LATCH_VEL = 0.0
HOME_SEQUENCE = 3
```

Comment in INI: last in REF ALL; zero search/latch marks A homed at current position (no switch). No physical A home switch is active (`ethercat_mill.hal` has A home net commented out).

### `trivkins coordinates=XYZA`

Standard 4-axis mill table rotary. **Not TCP** — Fusion post uses `optimizeMachineAngles2(1)` (tip mapping, no TCP in LinuxCNC). Do not enable TCP in CAM unless you add matching kinematics.

### Startup G-code

```ini
RS274NGC_STARTUP_CODE = F10 S300 G21 G17 G40 G49 G54 G64 P0.001 G80 G90 G91.1 G94 G97 G98
```

Metric (`G21`), absolute (`G90`), **`G94`** feed per minute default. Simultaneous 4-axis CAM blocks use **`G93`** inverse time from the post — not in startup.

### `MAX_FEED_OVERRIDE = 2.5`

Probe Basic stock template uses `2.0`. Raised to **250%** for pendant and GUI override headroom.

### Relaxed `FERROR` / `MIN_FERROR`

```ini
# ethercat_mill.ini [JOINT_*] — all four joints
FERROR = 1270.0
MIN_FERROR = 254.0
```

Stock servo configs often use ~2 mm / 1 mm. These values are **intentionally wide** so LinuxCNC does not fault during jog / homing / bench bring-up while EtherCAT following error is still being tuned.

**For production:** tighten per axis after drive tuning and confirm no false trips under cutting loads. Drive-side windows (SDO 6065/6066 ≈ **0.5 mm / 0.5° / 250 ms** in `ethercat-conf.xml`) are separate from INI `FERROR` — see [A6_TUNING.md](A6_TUNING.md) and [CiA 402 following error](https://linuxcnc.org/docs/html/config/ini-config.html#sub:joint-section).

---

## HAL architecture

### EtherCAT load (`TWOPASS`)

`ethercat_loadusr.hal` is marked `#NOTWOPASS` and listed **first** in `[HAL]` so `lcec_conf` runs once. Other HAL files use normal TWOPASS discovery.

### CiA 402 + custom limit/home wiring

Unlike a simple stepgen config:

- Position command/feedback passes through `mult2` / `conv_float_s32` / `lcec`
- X **and Y** limit chains suppressed during homing (`joint.N.homing` → `and2.1` / `and2.5`)
- Y also has `HOME_IGNORE_LIMITS = YES` (home at negative end shares the limit DI chain)
- NC switches inverted with `not.*`

### Bench limit gagging (`and2.0`)

```hal
# ethercat_mill.hal — and2.0 inputs tied 0 → output FALSE
net za-lims-gagged and2.0.out => joint.2.pos-lim-sw-in joint.3.home-sw-in ...
```

Z positive limit and all A limit/home inputs see **FALSE** (inactive). Full-machine gagging net `lims-home-all-off` exists but is **commented** — only Z/A are gagged in the current branch.

### Probe input mux (non-stock)

Stock: one probe → `motion.probe-input`.

Here: `halui.tool.number` compared to constant **99** (`probe-tool-num`):

- Equal → touch probe `lcec.0.1.di-5`
- Not equal → toolsetter `lcec.0.1.di-2`

Laser **M62 P0** muxes `laser-beam-broken` onto `motion.probe-input` for G38 measure macros; **M63 P0** restores contact-only routing — [LASER_TOOL_SETTER.md](LASER_TOOL_SETTER.md).

Uses `and2` + `or2`, not `mux2` (float-only). **`#3014` does not update HAL** — renumbering requires editing `setp probe-tool-num.value`.

See [README.md](../README.md#contact-probe-vs-toolsetter-hal) and [TOOLSETTER.md](TOOLSETTER.md#touch-probe-tool-number-setup-and-renumbering).

### Tool change HAL loop broken on purpose

```hal
net tool-change-request <= iocontrol.0.tool-change
net tool-change-confirmed => iocontrol.0.tool-changed
```

No `tool-change => tool-changed` wire. Operator must confirm **Manual Tool Change** dialog (M6 or M600 flow). Matches TooTall18T + Probe Basic manual change pattern.

### E-stop

Physical master estop cuts mains. Software NC estop on Slave 3 DI1 gates `iocontrol.0.emc-enable-in` with UI enable (`and2.2`).

### VFD (`custom.hal`)

| Deviation | Notes |
|-----------|--------|
| M3/M4 ↔ VFD direction **swapped** | Comment `REVERT: fwd->sel0 rev->sel1` |
| At-speed | `near.0` (50 RPM) + **`timedelay.0` 5 s** |
| Critical faults | Modbus fault reg `0x000A` codes 64 / 92 → `halui.estop.activate` |
| `or2.1` reserved | Do not load another `or2` with `names=` — conflicts with probe `or2.0` |

### Pendant homed-gate override

```hal
# xhc-whb04b-6.hal
net machine.is-on ... whb.halui.joint.z.is-homed ...
```

WHB normally requires per-axis homed for MPG jog. Tied to **machine on** so bench mode without Z homing still allows Z jog.

---

## RS274NGC and tool change

### `REMAP=M600` only — not M6

```ini
REMAP=M600 modalgroup=6 ngc=m600
TOOL_CHANGE_AT_G30 = 0
TOOL_CHANGE_QUILL_UP = 0
```

Stock M6 would optionally move to `[EMCIO] TOOL_CHANGE_POSITION`. Here **all motion** is in `tool_touch_off.ngc` / `go_to_g30.ngc` / `abort_tool_change.ngc`.

**Do not** add `REMAP=M6` for the toolsetter — conflicts with Probe Basic M6 dialog.

### Tool-load position vs setter teach

Stock TooTall18T / Probe Basic often pause at the same XY as the setter (`#5181–#5183`).

Here M600 automatic mode uses **two G53 positions**:

| Position | Coordinates | Purpose |
|----------|-------------|---------|
| **Tool-load** (collet change) | Default `270, 100, 0` mm — `#<tool_load_*>` in `tool_touch_off.ngc`, `go_to_g30.ngc` | M6 OK dialog; wrench clearance |
| **Setter** (probe) | `#5181–#5183` from **SET TOOL TOUCH OFF POS** | G38 length measure only |

Flow: retract Z → tool-load XY → **M6 dialog** → retract Z → setter XY → probe. Edit `#<tool_load_*>` if your bench layout differs. Details: [TOOLSETTER.md](TOOLSETTER.md#tool-load-position-collet-change).

### M600 traverse feed override

`tool_touch_off.ngc` sets `#<traverse_xy_fr> = 30000` and `#<traverse_z_fr> = 10000` mm/min for tool-change moves, **independent** of Probe Basic UI traverse `#3006`. Setter/probe feeds still come from `#3004–#3006`.

### `ON_ABORT_COMMAND` vs dialog abort

| Trigger | Subroutine | Motion |
|---------|------------|--------|
| Program **Abort** / estop while enabled | `on_abort.ngc` | **No G0/G1** — machine may be disabled |
| **ABORT** on Manual Tool Change dialog | `abort_tool_change.ngc` (via `toolchange_dialog.py`) | Z retract G53 Z0 → park tool-load XY |

Global abort must not move axes when LinuxCNC is disabled; dialog abort runs while still enabled after `program.abort()`.

### `TOOL_TABLE_COLUMNS = TDZR`

Stock Probe Basic often `TPDZR` (pocket column). Pocket column dropped for manual collet (`P` still in file but not displayed).

### `[ATC] POCKETS = 1` with hidden tab

`ATC_TAB_DISPLAY = 0` hides carousel UI. Subroutines still read `[ATC]` — `POCKETS=1` satisfies ATC-aware NGc without a real carousel.

### `tool_touch_off.ngc` fixes vs stock Probe Basic

Documented in [TOOLSETTER.md](TOOLSETTER.md#probe--length-math-fixes-vs-stock-pb-routine): setter coords from `#5181–#5183`, length formula, abort guards, `M50 P1` before pause, separate tool-load XY, per-axis setter validation, etc.

### Local Probe Basic subroutine patches

Upstream `probe_*.ngc` in this tree include **machine-specific fixes** not in stock Probe Basic:

- **Traverse feed typo** — pocket/valley/calibration macros passed `[3017]` (literal 3017 mm/min) instead of `[#3017]` (Probe Basic traverse param). Fixed in this repo; re-check after merging new PB versions.
- **`probe_spindle_nose.ngc`** — aborts if touch probe `T#3014` is loaded (HAL would listen to wrong sensor). Failed-probe recovery uses `#<z> = #5422` like sibling macros.

### Optional TooTall18T M-codes **not** installed

`m601`, `m300`, `m500` remaps are **not** present.

---

## Probe Basic UI

### `probe_basic_postgui.hal` vs stock Probe Basic sim

Stock Probe Basic sim hallib (upstream package; removed from this repo) differs from our postgui:

| Stock Probe Basic sim | This repo `probe_basic/probe_basic_postgui.hal` |
|-----------------------|--------------------------------------------------|
| `net probe-in => qtpyvcp.probe-in.out` (sim loopback) | **Not connected** — avoids duplicate driver on `motion.probe-input` |
| `scale_to_rpm.out` → spindle RPM widget | **`spindle-speed-in`** from VFD (`custom.hal`) |
| `not.0` on `halui.program.is-idle` | Uses **`pdnt.program.is-idle`** net (shared with WHB) |

No `BASE_PERIOD` / `base-thread` here — those exist only for software stepgen / sim encoders.

### Custom DRO display

`DRO_DISPLAY = XYZA` → [`probe_basic/user_dro_display/xyza_dros/`](../probe_basic/user_dro_display/xyza_dros/) with **SET Z** widget (not in stock Probe Basic). See [PROBE_BASIC_UI.md](PROBE_BASIC_UI.md).

### `custom_config.yml`

Minimal overrides (confirm exit off, backplot defaults) plus **custom Manual Tool Change dialog**:

```yaml
dialogs:
  toolchange:
    provider: toolchange_dialog:ToolChangeDialog
```

Replaces stock QtPyVCP dialog with **ABORT CYCLE** button. See [PROBE_BASIC_UI.md](PROBE_BASIC_UI.md#manual-tool-change-dialog-abort-cycle).

Most PB machine params still live in `linuxcnc.var` / Probe screens.

### `launch.sh`

Forces `QT_QUICK_BACKEND=software` — workaround for some Qt Quick + GPU combinations.

---

## CAM / post processor

`linuxcnc-djr.cps` fork of Autodesk LinuxCNC post:

- Default **`toolChangeMode: "M600"`**
- **`preloadTool: false`**
- **G93** on simultaneous `G1 XYZA`
- Fourth axis **table on X**, non-TCP
- Property groups require Fusion post engine **45702+**

Full property table: [TOOLSETTER.md](TOOLSETTER.md#cam--post-processor-linuxcnc-djrcps).

---

## EtherCAT slave map (this machine)

| Slave | Axis / role | Notes |
|-------|-------------|-------|
| 0 | X + Y IO | Pos cmd/fb for X; DI1–DI5 for X/Y home/limits |
| 1 | Y cmd + Z IO | Y position; Z home DI4; probe DI5; toolsetter DI2 |
| 2 | Z + laser | Z position; laser DI5 → `laser-beam-broken`; DI2 available (Z− limit not wired) |
| 3 | A + estop | A position; DI1 software estop |

This **split** (Y command on slave 1, Z on slave 2) is wiring-specific — not a linuxcnc-ethercat default.

PDO template matches StepperOnline A6 EtherCAT module (`vid/pid` in XML). SDO `2004` subindexes zero inputs per drive config tool.

---

## Files that are intentionally local / ignored

Large manuals, QtPyVCP pickles, and personal scratch notes stay out of git. Keep your own `linuxcnc.var` / `position.txt` backups when you clone.

---

## Reverting to “stock-like” behavior

| Goal | Action |
|------|--------|
| Force homing | Remove `NO_FORCE_HOMING` |
| Real A homing | Uncomment A home in HAL; set `HOME_SEQUENCE` and search/latch vels |
| Full limits on Z/A | Comment `za-lims-gagged`; uncomment `lims-home-all-off` or wire real switches |
| Stock M6 motion | Set `TOOL_CHANGE_AT_G30=1`, wire `tool-change` → `tool-changed`, remove M600 remap |
| Immediate spindle at-speed | Remove `timedelay` in `custom.hal` |
| Single probe input | Remove mux; wire one DI to `motion.probe-input` |
| 200% feed cap | `MAX_FEED_OVERRIDE = 2.0` |
| Tight following error | Restore smaller `FERROR` / `MIN_FERROR` per joint after tuning |
| Stock tool-change dialog | Remove `dialogs.toolchange` override from `custom_config.yml` |
| Single pause position | Set `#<tool_load_*>` equal to `#5181–#5183` or merge paths in `tool_touch_off.ngc` |

Always re-test on air after reverting bench shortcuts.
