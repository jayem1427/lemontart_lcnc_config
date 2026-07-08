# Deviations from stock LinuxCNC and Probe Basic

This document lists deliberate differences between **this config** and typical upstream examples. Use it when something “should work like the docs say” but does not — the answer is often here.

Stock references:

- [Probe Basic INI template](probe_basic/pb_required_ini_settings.ini) and [stock hallib](probe_basic/hallib/)
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
| A axis homing | Real switch sequence | **Disabled** — `HOME_SEQUENCE = 0`, zero search vel |
| Z− limit | Usually wired | **Commented out** in HAL (pin free) |
| Feed override max | 100–200% | **250%** (`MAX_FEED_OVERRIDE = 2.5`) |
| Fusion post | Stock `linuxcnc.cps`, `M6`, preload `T` | **`linuxcnc-djr.cps`**, M600 default, no preload |
| `PROGRAM_PREFIX` | Relative to config | **Absolute path** in committed INI — change on clone |

---

## Motion and INI

### `NO_FORCE_HOMING = 1`

```ini
# ethercat_mill.ini [TRAJ]
NO_FORCE_HOMING = 1
```

Stock LinuxCNC blocks motion until all joints with `HOME_SEQUENCE > 0` are homed. This flag relaxes that for bench work.

**Revert for production:** comment out the line and confirm Home All behavior on all four joints.

### A axis “virtual homing”

```ini
# ethercat_mill.ini [JOINT_3]
HOME_SEARCH_VEL = 0.0
HOME_LATCH_VEL = 0.0
HOME_SEQUENCE = 0
```

Comment in INI: `BREAKOUT OFF: Rev All sets homed at position`. No physical A home switch is active (`ethercat_mill.hal` has A home net commented out).

### `trivkins coordinates=XYZA`

Standard 4-axis mill table rotary. **Not TCP** — Fusion post uses `optimizeMachineAngles2(1)` (tip mapping, no TCP in LinuxCNC). Do not enable TCP in CAM unless you add matching kinematics.

### Startup G-code

```ini
RS274NGC_STARTUP_CODE = F10 S300 G21 G17 G40 G49 G54 G64 P0.001 G80 G90 G91.1 G94 G97 G98
```

Metric (`G21`), absolute (`G90`), **`G94`** feed per minute default. Simultaneous 4-axis CAM blocks use **`G93`** inverse time from the post — not in startup.

### `MAX_FEED_OVERRIDE = 2.5`

Probe Basic stock template uses `2.0`. Raised to **250%** for pendant and GUI override headroom.

---

## HAL architecture

### EtherCAT load (`TWOPASS`)

`ethercat_loadusr.hal` is marked `#NOTWOPASS` and listed **first** in `[HAL]` so `lcec_conf` runs once. Other HAL files use normal TWOPASS discovery.

### CiA 402 + custom limit/home wiring

Unlike a simple stepgen config:

- Position command/feedback passes through `mult2` / `conv_float_s32` / `lcec`
- X limit chain suppressed during X homing (`joint.0.homing` → `and2.1`)
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

Uses `and2` + `or2`, not `mux2` (float-only). **`#3014` does not update HAL** — renumbering requires editing `setp probe-tool-num.value`.

See [README.md](README.md#touch-probe-vs-toolsetter-routing) and [TOOLSETTER.md](TOOLSETTER.md#touch-probe-tool-number-setup-and-renumbering).

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

Stock M6 would optionally move to `[EMCIO] TOOL_CHANGE_POSITION`. Here **all motion** is in `tool_touch_off.ngc` / `go_to_g30.ngc` using taught `#5181–#5183`.

**Do not** add `REMAP=M6` for the toolsetter — conflicts with Probe Basic M6 dialog.

### `TOOL_TABLE_COLUMNS = TDZR`

Stock Probe Basic often `TPDZR` (pocket column). Pocket column dropped for manual collet (`P` still in file but not displayed).

### `[ATC] POCKETS = 1` with hidden tab

`ATC_TAB_DISPLAY = 0` hides carousel UI. Subroutines still read `[ATC]` — `POCKETS=1` satisfies ATC-aware NGc without a real carousel.

### `tool_touch_off.ngc` fixes vs stock Probe Basic

Documented in [TOOLSETTER.md](TOOLSETTER.md#probe--length-math-fixes-vs-stock-pb-routine): setter coords from `#5181–#5183`, length formula, abort guards, `M50 P1` before pause, etc.

### Optional TooTall18T M-codes **not** installed

`m601`, `m300`, `m500` remaps are **not** present.

---

## Probe Basic UI

### `probe_basic_postgui.hal` vs stock `hallib/`

| Stock hallib | This repo `probe_basic/probe_basic_postgui.hal` |
|--------------|--------------------------------------------------|
| `net probe-in => qtpyvcp.probe-in.out` (sim loopback) | **Not connected** — avoids duplicate driver on `motion.probe-input` |
| `scale_to_rpm.out` → spindle RPM widget | **`spindle-speed-in`** from VFD (`custom.hal`) |
| `not.0` on `halui.program.is-idle` | Uses **`pdnt.program.is-idle`** net (shared with WHB) |

### Custom DRO display

`DRO_DISPLAY = XYZA` → [`probe_basic/user_dro_display/xyza_dros/`](probe_basic/user_dro_display/xyza_dros/) with **SET Z** widget (not in stock Probe Basic). See [PROBE_BASIC_UI.md](PROBE_BASIC_UI.md).

### `custom_config.yml`

Minimal overrides (confirm exit off, backplot defaults). Most PB machine params live in `linuxcnc.var` / Probe screens.

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
| 2 | Z | Z position; DI2 available (Z− limit not wired) |
| 3 | A + estop | A position; DI1 software estop |

This **split** (Y command on slave 1, Z on slave 2) is wiring-specific — not a linuxcnc-ethercat default.

PDO template matches StepperOnline A6 EtherCAT module (`vid/pid` in XML). SDO `2004` subindexes zero inputs per drive config tool.

---

## Files that are intentionally local / ignored

From [README.md](README.md#what-was-left-out-of-git-but-is-helpful-to-keep-in-the-config): PDFs, pickles, `spindle_warmup.ngc`, personal notes. Clone may need fresh `linuxcnc.var` / `position.txt` from machine backup.

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

Always re-test on air after reverting bench shortcuts.
