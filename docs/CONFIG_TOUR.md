# Config tour

How the files in this repo fit together, and where this config differs from
a stock LinuxCNC / Probe Basic setup. Read this before editing HAL. Most
"LinuxCNC won't start" problems come from changing one file without
knowing what another one expects.

---

## Startup order

When LinuxCNC starts, it reads `ethercat_mill.ini` and loads the HAL files in
this order:

```
ethercat_mill.ini
 [HAL] (TWOPASS = on)
  1. ethercat_loadusr.hal   starts lcec_conf with ethercat-conf.xml (once only)
  2. ethercat_mill.hal      EtherCAT driver, joints, homing/limits, probe routing, E-stop
  3. probe_beep.hal         beep on probe / laser trip (optional)
  4. xhc-whb04b-6.hal       pendant
  5. custom.hal             spindle over Modbus, at-speed, VFD faults, servo telemetry
  6. coolant.hal            Microject MQL coolant over Modbus
 POSTGUI_HALFILE
  7. probe_basic/probe_basic_postgui.hal   UI widgets (spindle RPM/load, tool change dialog, cycle timer)
```

`TWOPASS` lets several files `loadrt` the same component. It reads every file
once to collect the loads, then runs them. The catch: it can run `loadusr`
twice, and `lcec_conf` must only run once. That's why `ethercat_loadusr.hal`
is a separate file marked `#NOTWOPASS` and listed first.

---

## What each file does

| File | What's in it | Edit it when… |
|------|--------------|---------------|
| `ethercat_mill.ini` | Machine limits, homing, scales, UI settings, remaps, `[HAL]` list | Changing axes, travel, speeds, homing, adding a HAL file |
| `ethercat-conf.xml` | One `<slave>` per drive: PDO map, startup SDOs, DC clock | Different drives, different number of axes |
| `ethercat_mill.hal` | Position scaling to/from the drives, CiA 402 enable, limit/home logic, probe routing, laser input, E-stop, tool-change handshake | Rewiring switches or probes |
| `custom.hal` | Spindle RPM ↔ VFD frequency, run/direction, at-speed delay, VFD fault → E-stop, drive telemetry for tuning | Different spindle, changing at-speed behaviour |
| `coolant.hal` | Hz / duty % → Microject pulse and period, M7/M8 → injector on | Different coolant hardware |
| `xhc-whb04b-6.hal` | Pendant wiring (stock LinuxCNC example, lightly changed) | Different pendant |
| `probe_beep.hal` | Plays `beep.mp3` when the probe input or laser trips | Never, or comment it out |
| `h100.mb2hal`, `microject.mb2hal` | Modbus register maps for the two serial devices | Different VFD / coolant, different adapter |
| `probe_basic/subroutines/` | All G-code macros: M600 tool change, probing, laser, coolant | Changing tool-change behaviour |
| `probe_basic/python/` | Remap Python (`toplevel.py`, coolant profiles) and servo-tuning engines | Rarely |
| `probe_basic/user_tabs/` | The four custom tabs. Probe Basic loads **every** folder here | Adding/removing tabs |
| `probe_basic/custom_config.yml` | Swaps in the custom tool-change dialog | Rarely |
| `linuxcnc.var` | Saved parameters: work offsets, taught positions, probe settings. **Tracked in git** | LinuxCNC writes it; keep it sorted |
| `probe_basic/tool.tbl` | Tool table | LinuxCNC writes it |

---

## EtherCAT

`ethercat-conf.xml` has one `<slave>` block per drive, in bus order. Each block:

- maps the PDOs: control/status word, position command/feedback, velocity
  (606C), torque (6077), drive following error (60F4), and the five digital
  inputs (`0x2040:05`);
- sets CSP mode (`6060 = 8`);
- sets the drive's following-error fault window (`6065` = 0.5 mm / 0.5°,
  `6066` = 250 ms);
- clears the drive's own input functions (`0x2004:01/05/09/0d/11 = 0`);
- sets `C01.10 = 3` (speed observer) via `0x2001:0x11`.

**Never put loop gains (C00/C01 parameters) in this file.** lcec writes these
SDOs every time LinuxCNC starts, so any gains here overwrite your tuning on
every launch (and the drive stores each of those writes in EEPROM, C13.10 = 1).
Tune with the Servo Tuning tab instead; its writes persist the same way. The only exceptions are the two above (`C01.10`, and
the 6065/6066 fault windows).

The DC clock runs in M2R mode (`refClockSyncCycles="-1"`). Don't switch it to
R2M.

---

## Motion and scaling

Positions go through HAL, not straight into lcec:

```
joint.N.motor-pos-cmd (mm) → mult2 (× SCALE) → conv-real-sint → lcec.0.N.pos-cmd (counts)
lcec.0.N.pos-fb (counts) → conv-sint-real → div2 (÷ SCALE) → joint.N.motor-pos-fb (mm)
```

The `SCALE` used in HAL comes from the INI, so changing it in `[JOINT_N]`
is enough.

---

## Homing

> **Branch `dev-drive-homing`:** the drives home themselves (hard stop, then Z pulse;
> A to its Z pulse). LinuxCNC starts and supervises it through the upstream
> `cia402_homecomp` homing module (`[EMCMOT]HOMEMOD`) and lcec ≥ 1.49 `cia402`,
> which also takes over position scaling. The table below is the switch homing on
> `dev-jerk-testing`. See [DRIVE_HOMING.md](DRIVE_HOMING.md).

| Setting | Value | Why |
|---------|-------|-----|
| Order | Z → X → Y → A (`HOME_SEQUENCE` 0/1/2/3) | Z clears first. Y and Z share a switch, so they can't home together |
| X | Search −12 mm/s, latch dist 25 mm, `HOME_OFFSET` −5 | The X home flag is long, so it backs off further |
| Y | Search −33 mm/s, `HOME_OFFSET` −2 | |
| Z | Search **+**33 mm/s (up only), `HOME_OFFSET` +2 | Zero sits 2 mm below the switch |
| Latch | Same direction as search | Gives search → back off → slow re-approach. Opposite-sign latch never re-approaches |
| A | Search and latch velocity 0 | No switch. "Homing" A just marks it homed where it is |
| `HOME_IGNORE_LIMITS` | YES on X/Y/Z | Limit and home share wiring at the negative end |
| `NO_FORCE_HOMING` | 1 | Jog and MDI work before homing. Remove for production if you prefer |

After homing XYZ with A still unhomed, LinuxCNC stays in **joint** mode. The
pendant is wired to both joint and axis jog pins so it keeps working either
way. **REF ALL** on the DRO always reads "REF ALL" (it no longer flips to
"HOMED").

If you need to "home in place" on an axis with no switch, set search, latch
and final velocity and `HOME_OFFSET` all to 0. **Don't** use
`HOME_ABSOLUTE_ENCODER = 1` for this: on this mill it caused a Y runaway.

---

## Following error

Following error is checked in two places, on purpose:

| Where | Limit | Role |
|-------|-------|------|
| LinuxCNC (INI `FERROR` / `MIN_FERROR`) | 1270 / 254 mm | Effectively off |
| Drive (SDO 6065 / 6066) | 0.5 mm (A: 0.5°, widened to 10° while unconnected) for 250 ms → fault Er47.0 → `amp-fault-in` | **The real protection** |

The drive measures following error at its own servo rate, without the
EtherCAT round-trip lag LinuxCNC sees, so it's the better place for the limit.
The tuning tools temporarily raise 6065 during test moves (2.0 mm for inertia
ID, 1.0 mm for one-click) and always restore it.

If you'd rather have LinuxCNC enforce it too, tighten `FERROR` per joint
after tuning, and check you don't get false trips under cutting loads.

---

## Startup G-code

```ini
RS274NGC_STARTUP_CODE = F10 S300 G21 G17 G40 G54 G64 P0.001 G80 G90 G91.1 G94 G97 G98
```

Two deliberate differences from Probe Basic's template:

- **No `G49`.** On a manual-collet mill the cutter stays loaded between jobs.
  `G49` on Stop dropped the tool length, so work Z appeared to jump. See
  [TOOL_CHANGE.md](TOOL_CHANGE.md#keep-g43-on-stop).
- **No O-word calls.** `RS274NGC_STARTUP_CODE` can't call subroutines
  (`Bad character 'o' used on startup`). `ON_ABORT_COMMAND` can, so the
  tool-length restore lives there.

---

## HAL conventions in this config

These rules keep the HAL files loading. Break one and LinuxCNC won't start.

- **One writer per signal.** Two output pins on one `net` is an error.
  Probe Basic's sim config wires `qtpyvcp.probe-in` to the probe signal. This
  config doesn't, because `ethercat_mill.hal` already drives it.
- **Don't mix `count=` and `names=` for the same component.** `or2`, `and2`,
  `not`, `mult2`, `div2`, `conv_*` are loaded with `count=`. To add instances,
  add another `loadrt <comp> count=N` line. The new ones are numbered after the
  existing ones.
- **Check who owns an instance before using it.** For example:

  | Instance | Used by |
  |----------|---------|
  | `or2.0`, `or2.3` | Probe routing (`ethercat_mill.hal`) |
  | `or2.1` | VFD fault → E-stop (`custom.hal`) |
  | `or2.2`, `or2.4` | Shared Y/Z home ignore logic |
  | `or2.5` | Flood OR mist → coolant on (`coolant.hal`) |
  | `not.0` | Reserved by `probe_basic_postgui.hal` |
  | `mult2.4`–`.6`, `near.0`–`.2` | Spindle (`custom.hal`) |

  `grep -n "or2\." *.hal probe_basic/*.hal` before you pick a number.
- **`mux2` is float-only.** Bit routing (like the probe mux) uses `and2` + `or2`.

More detail for AI assistants: [agent-skills/linuxcnc-hal-edits](agent-skills/linuxcnc-hal-edits/SKILL.md).

---

## Differences from stock, at a glance

| Area | Stock | This config | Details |
|------|-------|-------------|---------|
| Tool change from CAM | `T M6` | `T M600` (remap); M6 only shows the dialog | [TOOL_CHANGE.md](TOOL_CHANGE.md) |
| M6 motion | Optional move to G30 | Off (`TOOL_CHANGE_AT_G30 = 0`); macros do all moves | [TOOL_CHANGE.md](TOOL_CHANGE.md) |
| Tool-change dialog | Esc cancels | Custom dialog with an **ABORT** button; Esc is ignored | [PROBE_BASIC_UI.md](PROBE_BASIC_UI.md) |
| Probe input | One sensor | Touch probe or tool setter, chosen by the tool in the spindle | [TOOL_CHANGE.md](TOOL_CHANGE.md#probe-routing) |
| Stop / abort | `G49` | Keeps `G43` for the loaded tool | [TOOL_CHANGE.md](TOOL_CHANGE.md#keep-g43-on-stop) |
| Spindle feedback | Encoder / sim | VFD frequency over Modbus | [SPINDLE.md](SPINDLE.md) |
| At-speed | Immediate | RPM match + 5 s delay | [SPINDLE.md](SPINDLE.md) |
| M3 / M4 | Forward / reverse | Swapped to match VFD wiring | [SPINDLE.md](SPINDLE.md) |
| Coolant | Relay on M7/M8 | Pulsed MQL injector; `M201`/`M202` set rate and duty | [COOLANT.md](COOLANT.md) |
| Homing | Forced | `NO_FORCE_HOMING = 1`; shared Y/Z switch; A homes in place | [Homing](#homing) |
| Following error | Tight INI values | Loose INI, drive enforces | [Following error](#following-error) |
| Feed override max | 200 % | 250 % | |
| ATC | Carousel tab | Hidden; `POCKETS = 1` keeps Probe Basic macros happy | [PROBE_BASIC_UI.md](PROBE_BASIC_UI.md) |
| Kinematics | XYZ | `trivkins coordinates=XYZA` (table rotary on X, no TCP) | [CAM.md](CAM.md) |
| Probe Basic macros | Upstream | A few local fixes (pocket probe feed typo, spindle-nose guard) | [PROBE_BASIC_UI.md](PROBE_BASIC_UI.md#local-fixes-to-probe-basic-macros) |

### Going back toward stock

| To get… | Do |
|---------|----|
| Forced homing | Remove `NO_FORCE_HOMING` |
| Real limits on Z/A | Wire switches; remove them from the `a-lims-gagged` net in `ethercat_mill.hal` |
| Stock M6 with motion | `TOOL_CHANGE_AT_G30 = 1`, drop the `M600` remap, use the stock tool-change dialog |
| Immediate at-speed | Remove the `timedelay` in `custom.hal` |
| One probe input | Replace the probe mux with a single `net` to `motion.probe-input` |
| Tight following error | Lower `FERROR` / `MIN_FERROR` per joint |
| `G49` on abort | See [TOOL_CHANGE.md](TOOL_CHANGE.md#keep-g43-on-stop) |

Air-test after every change.
