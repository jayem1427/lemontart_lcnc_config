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
| Touch probe HAL | Single `motion.probe-input` wire | **Tool-gated mux** (T99 → probe DI2, else → toolsetter DI5; pins swapped vs older silk, HAL matches wires) |
| Probe Basic probe pin | `qtpyvcp.probe-in` ↔ `motion.probe-input` | **Direct HAL only** — PB probe widget disconnected |
| ATC | Carousel tab + `TPDZR` columns | **`POCKETS=1`**, tab hidden, **`TDZR`** columns |
| Geometry | Often XYZ | **XYZA** `trivkins`, table rotary on X |
| Spindle feedback | Encoder or sim `scale_to_rpm` | **VFD Modbus** freq → `spindle.0.speed-in` |
| At-speed | `near` or drive ready bit | **`near` + 5 s `timedelay`** after RPM match |
| Homing required | Default (forced) | **`NO_FORCE_HOMING = 1`** (jog without home; X/Y/Z still search) |
| A axis homing | Real switch sequence | **Disabled** — `HOME_SEQUENCE = 3` (after Z/X/Y), zero search vel |
| Shared Y/Z home | `HOME_IS_SHARED=1` | **`HOME_IS_SHARED=0`** + HAL ignore-until-open (shared aborts Z) |
| Z− limit | Usually wired | **Gagged** (`and2.0`); Y limit uses former Z− DI |
| Feed override max | 100–200% | **250%** (`MAX_FEED_OVERRIDE = 2.5`) |
| Fusion post | Stock `linuxcnc.cps`, `M6`, preload `T` | **`post-processor/linuxcnc-djr.cps`**, M600 default, no preload |
| `PROGRAM_PREFIX` | Relative to config | **Absolute path** in committed INI — change on clone |
| Joint following error | Tight (e.g. ~2 mm / 1 mm) | **Relaxed** `FERROR = 1270`, `MIN_FERROR = 254` for bench — tighten later |
| M600 collet pause | Often same as setter / G30 | **Separate tool-load XY** (default G53 270, 100) vs taught setter `#5181–#5183` |
| Manual Tool Change dialog | Stock QtPyVCP; Esc cancels | **Custom dialog** with **ABORT**; Esc/close ignored — [PROBE_BASIC_UI.md](PROBE_BASIC_UI.md) |
| Drive position deviation | Drive defaults | **SDO 6065/6066** **0.5 mm / 0.5° / 250 ms** (6065 → **2.0** during one-click / inertia moves) — [A6_TUNING](A6_TUNING.md) |
| Laser tool setter | M62 P0 mux to `motion.probe-input` for G38 | [LASER_TOOL_SETTER](LASER_TOOL_SETTER.md) |
| Pocket probe traverse feed | `#3017` from Probe Basic | **Local fix** — several `probe_*.ngc` had bare `[3017]` (3017 mm/min literal) |
| PROBE SPINDLE NOSE ZERO | Runs on setter input | **Aborts if T#3014 loaded** — HAL routes touch probe only when that tool is in spindle |
| Abort / M30 tool length | Stock `G49` in startup + `on_abort` | **No `G49` in startup**; Stop **keeps `G43`** via `on_abort` — [Keep G43 on Stop](#keep-g43-on-stop) |

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
Y search −Y (~33 mm/s); Z search **+Z only** (~33 mm/s); X search slower (−12 mm/s)
with `HOME_OFFSET=-5` and `HOME_LATCH_DIST=25` so backoff can leave a long home
flag. Host `FERROR` stays wide (1270 / 254) for bench homing.

XYZ home with A still unhomed leaves motion in **joint** mode (not teleop). Home A
(instant, no move) or use the pendant joint-jog nets.

### Shared Y/Z home bus (ignore until open)

Y home and Z home are electrically shorted (`lcec.0.1.di-4`). If that bus is
already closed at REF, LinuxCNC would otherwise backoff the wrong way (Z search
down) or latch Y in place.

`HOME_IS_SHARED=1` aborted Z (`Cannot home while shared home switch is closed`)
and still let Y latch — **do not use it here**.

Instead, `oneshot` + `flipflop` hide the shared input for that joint until the
bus has been seen open (or homing ends), then the next close latches. Debounce
is 5 ms on X home, 8 ms on X/Y limits and the Y/Z home bus.

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
# ethercat_mill.ini [RS274NGC]
RS274NGC_STARTUP_CODE = F10 S300 G21 G17 G40 G54 G64 P0.001 G80 G90 G91.1 G94 G97 G98
```

Metric (`G21`), absolute (`G90`), **`G94`** feed per minute default. Simultaneous 4-axis CAM blocks use **`G93`** inverse time from the post only while the 4th axis is enabled and interpolating — not in startup.

**No `G49` here.** Stock Probe Basic / `pb_required_ini_settings.ini` still has `G40 G49 G54`. This mill leaves a cutter in the collet between jobs; `G49` on Stop cancelled tool length and made work Z jump by `#5403` so G54 looked like it moved.

**No O-words in `RS274NGC_STARTUP_CODE`.** Putting `o<restore_tool_length> call` there fails with `Bad character 'o' used on startup`. Restore runs only from `on_abort.ngc` (that command *can* call a sub). Interpreter default is still `G49` at LinuxCNC launch and after `M30` until something issues `G43` (M600, MDI, or Stop restore).

See [Keep G43 on Stop](#keep-g43-on-stop) for risks and how to revert.

### `MAX_FEED_OVERRIDE = 2.5`

Probe Basic stock template uses `2.0`. Raised to **250%** for pendant and GUI override headroom.

### Relaxed `FERROR` / `MIN_FERROR`

```ini
# ethercat_mill.ini [JOINT_*] — all four joints
FERROR = 1270.0
MIN_FERROR = 254.0
```

Stock servo configs often use ~2 mm / 1 mm. These values are **intentionally wide** so LinuxCNC does not fault during jog / homing / bench bring-up while EtherCAT following error is still being tuned.

**For production:** tighten per axis after drive tuning and confirm no false trips under cutting loads. Drive-side windows (SDO 6065/6066 **0.5 mm / 0.5° / 250 ms** at startup) are separate from INI `FERROR` — see [A6_TUNING.md](A6_TUNING.md) and [CiA 402 following error](https://linuxcnc.org/docs/html/config/ini-config.html#sub:joint-section).

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
- Shared Y/Z home: debounce then ignore-until-open (`oneshot`/`flipflop`) into `joint.1/2.home-sw-in`

### Bench limit gagging (`and2.0`)

```hal
# ethercat_mill.hal — and2.0 inputs tied 0 → output FALSE
net za-lims-gagged and2.0.out => joint.2.pos-lim-sw-in joint.3.home-sw-in ...
```

Z **negative** limit, Z positive limit, and all A limit/home inputs see **FALSE** (inactive). Y limit is live on the former Z− DI (`lcec.0.0.di-1`). Full-machine gagging net `lims-home-all-off` exists but is **commented**.

### Probe input mux (non-stock)

Stock: one probe → `motion.probe-input`.

Here: `halui.tool.number` compared to constant **99** (`probe-tool-num`):

- Equal → touch probe `lcec.0.1.di-5`
- Not equal → toolsetter `lcec.0.1.di-2`

Laser **M62 P0** muxes **raw** `laser-beam-broken` onto `motion.probe-input` for
G38 measure macros (tip-find, coarse locate, slot transit); diameter edges use
a **static-X** RAW peak hunt with the mux off;
**M63 P0** restores contact-only routing —
[LASER_TOOL_SETTER.md](LASER_TOOL_SETTER.md).

Uses `and2` + `or2`, not `mux2` (float-only). **`#3014` does not update HAL** — renumbering requires editing `setp probe-tool-num.value`.

Audible feedback: `probe_beep.hal` watches `probe-in` and `laser-beam-broken`, playing `beep.mp3` via `scripts/probe_beep.py` (userspace; not realtime). Covers touch probe, contact toolsetter, laser G38, and jog/capture beam-block. Optional — comment out the HALFILE to disable.

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
| At-speed | `near.0` (50 RPM) + **`spindle-at-speed-delay` 5 s** |
| Critical faults | Modbus fault reg `0x000A` codes 64 / 92 → `halui.estop.activate` |
| `or2` instances | `or2.0`/`or2.3` probe mux; `or2.1` VFD faults; `or2.2`/`or2.4` shared-home ignore. Do not `loadrt or2 names=` |

### Pendant MPG (joint + teleop)

```hal
# xhc-whb04b-6.hal
net machine.is-on ... whb.halui.joint.z.is-homed ...
net pdnt.axis.x.jog-enable ... axis.x.jog-enable joint.0.jog-enable
```

WHB `is-homed` inputs are tied to **machine on** so the wheel is not gated on real homing (`NO_FORCE_HOMING`).

The wheel also writes **joint** jog pins, not only `axis.*`. After XYZ home with A unhomed, LinuxCNC stays in joint mode and ignores world/axis jog. GUI spindle / MDI leaves Manual — tap **Manual** before expecting the wheel; Lead is spindle override (`-s`), not jog.

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

| Trigger | Subroutine | Motion | Tool length |
|---------|------------|--------|-------------|
| Program **Stop / Abort** / estop while enabled | `on_abort.ngc` | **No G0/G1** — machine may be disabled | **Keep `G43`** via `restore_tool_length.ngc` if `#5400 > 0` and `#5403 > 0` |
| **ABORT** on Manual Tool Change dialog | `abort_tool_change.ngc` (via `toolchange_dialog.py`) | Z retract G53 Z0 → park tool-load XY | **`G49`** — cutter in the collet may not match `H` |

Global abort must not move axes when LinuxCNC is disabled; dialog abort runs while still enabled after `program.abort()`.

### Keep G43 on Stop

Manual collet mill: the operator leaves a tool loaded and expects the same G54 **tip** Z after Stop.

**What changed (vs stock Probe Basic)**

| File | Stock | This machine |
|------|-------|--------------|
| `ethercat_mill.ini` `RS274NGC_STARTUP_CODE` | `G40 G49 G54 …` | `G40 G54 …` — **no `G49`**, **no O-word** (illegal in startup) |
| `on_abort.ngc` | `G49` | `o<restore_tool_length> call` |
| `abort_tool_change.ngc` | `G49` | **`G49` kept** — mid-M600 only |
| `restore_tool_length.ngc` | — | `G43 H#5400` when `#5400 > 0` and `#5403 > 0` |

`G54` select in startup never zeroed the stored offset (`#5223`). The DRO jump was `G49` dropping `H`. M600 full measure still issues its own `G49` before probing, then `G43` after `G10 L1`.

`ON_ABORT_COMMAND = o<on_abort> call` is allowed to call subs. `RS274NGC_STARTUP_CODE` is not — an `o<…>` there is `Bad character 'o' used on startup`. After **M30** or a fresh LinuxCNC start the interp default is still `G49` until M600 / MDI `G43` / a later Stop restore.

**How to revert**

1. `ethercat_mill.ini`: put `G49` back after `G40` in `RS274NGC_STARTUP_CODE`.
2. `probe_basic/subroutines/on_abort.ngc`: replace `o<restore_tool_length> call` with `G49`.
3. Leave `abort_tool_change.ngc` `G49` as-is.
4. `restore_tool_length.ngc` can stay unused or be deleted.
5. Reload LinuxCNC.

Stock one-liner to restore in the INI:

```ini
RS274NGC_STARTUP_CODE = F10 S300 G21 G17 G40 G49 G54 G64 P0.001 G80 G90 G91.1 G94 G97 G98
```

**Risks of keeping G43**

- **Stop mid-M600 after the collet swap, before the setter probe.** `#5400` may already be the new `T` while `#5403` is the *previous* length for that slot, or the old `H` may still be active. Jogging work `Z0` can crash. Use the Manual Tool Change **ABORT** button for a cancelled change — that path still `G49`s and parks at tool-load XY. `abort_tool_change.ngc` does **not** use `M73`, so that `G49` is not undone when the sub returns.
- **Physical tool ≠ LinuxCNC tool number.** Swapping a cutter in the collet without M600 / M61 / M6 leaves `G43 H` for the old tool. Stop will restore that wrong `H`.
- **Empty spindle with a leftover tool number.** If `#5400` / `#5403` are stale and non-zero, Stop reapplies `G43` as if that tool were still in. Unload with `T0` / spindle-empty flow when the collet is actually empty.
- **E-stop then jog before looking at active G-codes.** `G43` is not a move, so restore still runs while disabled. After re-enable, work Z is tip-relative again — confirm **G43 H…** in active codes before jogging to Z0.
- **Length table wrong (`#5403`).** Restore trusts the tool table. A bad length is applied just like during a cut.

These are the reasons stock configs `G49` on abort. This machine prefers the matching-tool case over that generic reset.

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

### Qt Quick rendering

If Probe Basic fails to render on your GPU, launch with
`QT_QUICK_BACKEND=software linuxcnc ethercat_mill.ini`.

---

## CAM / post processor

`post-processor/linuxcnc-djr.cps` fork of Autodesk LinuxCNC post:

- Default **`toolChangeMode: "M600"`**
- **`preloadTool: false`**
- **G93** only on simultaneous `G1 XYZA` while the 4th axis is enabled and moving; otherwise **G94**
- **No `G49` after multi-axis** — non-TCP; would cancel `G43` tool length
- Fourth axis **table on X**, non-TCP
- Property groups require Fusion post engine **45702+**
- M600 **same-tool skip** when spindle tool matches CAM `T` and `#5403 > 0`

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
