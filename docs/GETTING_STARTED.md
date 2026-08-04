# Getting started — zero to hero

Welcome. This repo is a **working reference** for a Lemontart-class EtherCAT mill
running Probe Basic. It is not a guaranteed drop-in — most of it was assembled
from examples, forum posts, and trial-and-error. Treat upstream LinuxCNC / Probe
Basic docs as authoritative; use this tree to see how one specific machine wires
things together.

If you only read one other file after this: **[DEVIATIONS.md](DEVIATIONS.md)** —
that is where “why doesn’t this match the manual?” usually lives.

## Before you copy anything

| Expect to change | Why |
|------------------|-----|
| EtherCAT NIC address | Your `ip a` result ≠ ours |
| `ethercat-conf.xml` slave order / PDOs | Chain layout and drive firmware |
| `[JOINT_*] SCALE`, limits, homing | Ball screws, encoders, switch placement |
| `h100.mb2hal` serial port | `/dev/ttyUSB0` is not universal |
| `PROGRAM_PREFIX` in `ethercat_mill.ini` | Currently a developer path; point at your NC programs directory |
| Probe tool number (default T99) | Must match tool table, `#3014`, and HAL — see [TOOLSETTER.md](TOOLSETTER.md) |

## Recommended learning path

Probe Basic adds a lot of moving parts. If LinuxCNC is new to you, **do not start here**. Build confidence on a simpler config first.

```mermaid
flowchart TD
  A[Install LinuxCNC] --> B[Run sim configs — Axis or QtDragon]
  B --> C[Copy a wizard config — understand INI + HAL]
  C --> D[Motor scaling, direction, limits, homing]
  D --> E[Install linuxcnc-ethercat + one drive]
  E --> F[Full XYZA chain + bench testing]
  F --> G[Duplicate working config → Probe Basic]
  G --> H[Toolsetter M600 + touch probe routing]
  H --> I[CAM post + air cuts]
```

### Stage 0 — Install LinuxCNC

- Downloads: [linuxcnc.org/downloads](https://linuxcnc.org/downloads/)
- Official docs: [LinuxCNC documentation](https://linuxcnc.org/docs/html/)
- HAL primer: [HAL introduction](https://linuxcnc.org/docs/html/hal/intro.html)
- INI reference: [INI file parameters](https://linuxcnc.org/docs/html/config/ini-config.html)

### Stage 1 — Simulation and UI

Run a stock sim config (e.g. `sim/axis/axis.ini`) and learn:

- Machine On / Estop / Home All
- Jogging, MDI (`G0`, `G1`, `G53`, `G54`)
- **Show HAL Configuration** — watch pins change when you jog
- **HAL Meter** on `joint.N.motor-pos-cmd` vs `motor-pos-fb`

Probe Basic is QtPyVCP-based. Skim upstream UI docs even if you use Axis first:

- [Probe Basic](https://github.com/kcjengr/probe_basic) (install instructions match your LinuxCNC version)
- [QtPyVCP](https://github.com/kcjengr/qtpyvcp)

### Stage 2 — EtherCAT + StepperOnline A6

This machine uses **linuxcnc-ethercat** (`lcec`) with **CiA 402** drives:

- Project: [linuxcnc-ethercat](https://github.com/linuxcnc-ethercat/linuxcnc-ethercat)
- Our slave layout: [`ethercat-conf.xml`](../ethercat-conf.xml) (4× generic A6-class slaves, VID `00400000` PID `00000715`)
- HAL load order: [`ethercat_loadusr.hal`](../ethercat_loadusr.hal) (`#NOTWOPASS`) then [`ethercat_mill.hal`](../ethercat_mill.hal)

**First-time EtherCAT checklist**

1. Install IgH EtherCAT master + `lcec` per project README.
2. Set master MAC in `/etc/ethercat.conf` (from `ip link` on the dedicated NIC).
3. `ethercat slaves` — confirm 4 slaves, correct order.
4. Start with **one axis** enabled in HAL; verify `halcmd show pin lcec.0.0.pos-fb` moves when you turn the motor by hand.
5. Tune drives in StepperOnline software **before** aggressive homing.

Drive docs (vendor):

- [StepperOnline closed-loop stepper manuals](https://www.omc-stepperonline.com/download-manual)

### Stage 3 — Homing, limits, bench mode

Homing and limit wiring live in [`ethercat_mill.hal`](../ethercat_mill.hal), not the INI. See [README.md](../README.md#current-machine-notes-this-bench) for bench notes.

**Bench / breakout shortcuts** (revert before production — details in [DEVIATIONS.md](DEVIATIONS.md#bench--breakout-shortcuts)):

- `NO_FORCE_HOMING = 1` in `ethercat_mill.ini` — can run without homing
- REF ALL order is Z → X → Y → A (`HOME_SEQUENCE` 0/1/2/3). A uses zero search/latch — marks homed at current position (no switch)
- Z/A limits and A home **gagged** via `and2.0` in HAL while X/Y use real switches

### Stage 4 — Spindle (H100 VFD + Modbus)

- [`h100.mb2hal`](../h100.mb2hal) — register map; set `SERIAL_PORT`
- [`custom.hal`](../custom.hal) — RPM scaling, at-speed compare + 5 s settle, fault → estop

H100 manual: [`reference/h100 manual.pdf`](reference/h100%20manual.pdf) — register `0x0201` (freq set), `0x000A` (current fault).

Modbus HAL: [mb2hal documentation](https://linuxcnc.org/docs/html/man/man1/mb2hal.1.html)

### Stage 5 — Pendant (XHC WHB04B-6)

- [`xhc-whb04b-6.hal`](../xhc-whb04b-6.hal) — MPG jog with `ilowpass` smoothing, feed override to 250%
- Component: [xhc-whb04b-6](https://github.com/welter/welder/tree/master/xhc-whb04b-6) (check your package source)

With bench homing disabled, pendant “axis homed” gates are tied to `halui.machine.is-on` so Z jogging is not blocked.

### Stage 6 — Probe Basic migration

When XYZ motion is trustworthy:

1. Copy this repo’s `probe_basic/` tree and INI `[DISPLAY]` / `[RS274NGC]` sections.
2. Align [`probe_basic/pb_required_ini_settings.ini`](../probe_basic/pb_required_ini_settings.ini) with your INI (geometry, paths, `OWORD_NARGS`, etc.).
3. Launch: `linuxcnc /path/to/ethercat_mill.ini` (optionally `QT_QUICK_BACKEND=software` if Qt Quick fails to render)
4. Teach toolsetter and probe params — [TOOLSETTER.md](TOOLSETTER.md)
5. UI extras — [PROBE_BASIC_UI.md](PROBE_BASIC_UI.md)

### Stage 7 — CAM

- Fusion post: [`post-processor/linuxcnc-djr.cps`](../post-processor/linuxcnc-djr.cps) — see [TOOLSETTER.md § CAM](TOOLSETTER.md#cam--post-processor-linuxcnc-djrcps)
- Default tool change: **`T<n> M600`** (toolsetter probe), not stock `M6` motion

### Stage 8 — Validate M600 and probing

Before trusting CAM:

1. Teach setter (**SET TOOL TOUCH OFF POS**) and spindle zero (**PROBE SPINDLE NOSE ZERO**) — unload touch probe first; see [TOOLSETTER.md](TOOLSETTER.md#teach-before-first-use).
2. Air-cut test: MDI or a short AUTO program with `T3 M600`, jog, then `T9`/`T10 M600`. Each stop is at **tool-load XY** (default 270, 100), not the setter.
3. Confirm **ABORT** on the Manual Tool Change dialog parks cleanly — [PROBE_BASIC_UI.md](PROBE_BASIC_UI.md).
4. MDI metrology: `o<probe_z_repeat_stats> call [10]` — [metrology README](../probe_basic/subroutines/metrology/README.md).
5. Confirm HAL routing: `halcmd show pin halui.tool.number` and trip each sensor.
6. Optional: Laser Setter diameter smoke test — [LASER_TOOL_SETTER.md](LASER_TOOL_SETTER.md).

**EtherCAT note:** committed INI `FERROR` values are wide for bring-up (1270 / 254 mm); drives also set SDO `6065`/`6066` (~1.0 mm / 250 ms). Tighten both after motion is stable — [DEVIATIONS.md](DEVIATIONS.md#relaxed-ferror--min_ferror) and [A6_TUNING.md](A6_TUNING.md).

## How the config fits together

```
ethercat_mill.ini
├── [HAL] TWOPASS load order
│   ├── ethercat_loadusr.hal   → lcec_conf + ethercat-conf.xml (once)
│   ├── ethercat_mill.hal      → joints, limits, probe mux, estop
│   ├── xhc-whb04b-6.hal       → pendant
│   └── custom.hal             → VFD Modbus, at-speed, faults
├── POSTGUI probe_basic/probe_basic_postgui.hal
├── probe_basic/custom_config.yml
├── probe_basic/subroutines/   → probing, M600, tool change
└── PROGRAM_PREFIX             → your NC programs directory (edit path!)
```

| Subsystem | Primary files | Deep dive |
|-----------|---------------|-----------|
| Motion + EtherCAT | `ethercat_mill.ini`, `ethercat_mill.hal`, `ethercat-conf.xml` | [README](../README.md), [DEVIATIONS](DEVIATIONS.md) |
| Toolsetter + touch probe | `tool_touch_off.ngc`, `m600.ngc`, HAL probe gating | [TOOLSETTER.md](TOOLSETTER.md) |
| Laser tool setter | `laser_*.ngc`, Laser Setter tab | [LASER_TOOL_SETTER.md](LASER_TOOL_SETTER.md) |
| Probe Basic UI | `probe_basic/`, custom DRO, abort dialog | [PROBE_BASIC_UI.md](PROBE_BASIC_UI.md) |
| Metrology macros | `probe_z_three_samples.ngc`, etc. | [probe_basic/subroutines/metrology/README.md](../probe_basic/subroutines/metrology/README.md) |
| CAM | `post-processor/linuxcnc-djr.cps` | [TOOLSETTER.md](TOOLSETTER.md) |

## First boot on this repo

1. Clone repo; `cd` into it.
2. Edit `ethercat_mill.ini`:
   - `PROGRAM_PREFIX` → your NC programs directory.
3. Edit `/etc/ethercat.conf` and `ethercat-conf.xml` for your NIC and slaves.
4. Edit `h100.mb2hal` → `SERIAL_PORT`.
5. `linuxcnc ethercat_mill.ini` (use `QT_QUICK_BACKEND=software` if Probe Basic fails to render on your GPU).
6. **Machine On** → if estop loops, check Slave 3 DI1 (software estop NC).
7. Home X/Y (Z/A behavior depends on bench flags — read [DEVIATIONS.md](DEVIATIONS.md)).
8. MDI smoke test: `G0 X10`, `M3 S500`, watch `halcmd show pin spindle.0.at-speed`.

## Day-one operator workflows

| Task | How |
|------|-----|
| Load cutter + measure length | Probe Basic **LOAD SPINDLE** or CAM `T<n> M600` |
| Cancel mid M600 | **ABORT** on Manual Tool Change dialog |
| Multi-tool air test | MDI/AUTO: `T3 M600`, then `T9`/`T10 M600` |
| Measure diameter (laser) | Laser Setter tab — [LASER_TOOL_SETTER.md](LASER_TOOL_SETTER.md) |
| Load touch probe only | **LOAD SPINDLE** with probe tool — skips M600 |
| Set WCO Z after shim touch-off | XYZA DRO **SET Z** field → [PROBE_BASIC_UI.md](PROBE_BASIC_UI.md) |
| Touch-off without CAM | **TOUCH OFF CURRENT TOOL** |
| WCS probing | Probe tab routines (requires T99 / `#3014` aligned) |
| Repeatability check | `o<probe_z_repeat_stats> call [10]` — [metrology README](../probe_basic/subroutines/metrology/README.md) |

## Troubleshooting

| Symptom | Things to check |
|---------|-----------------|
| `lcec_conf` fails / no slaves | `ethercat master`, NIC in `/etc/ethercat.conf`, cable power order |
| Enable drops immediately | Software estop DI1, drive fault `cia402.N.drv-fault`, VFD fault code on `spindle-vfd-fault-code` |
| Probe never trips | Wrong tool in spindle for HAL route (T99 vs cutter), DI wiring, `motion.probe-input` with `halcmd` |
| M600 does not probe | `#5181–#5183` unset, `#3010` spindle zero unset, `TOOL_CHANGE_AT_G30=0` (expected — macro handles motion) |
| M600 pauses at the wrong place | Tool-load XY (`270, 100`) ≠ setter — [TOOLSETTER.md](TOOLSETTER.md#tool-load-position-collet-change) |
| Following error / drive Er47.0 | Wide INI `FERROR` vs drive SDO 6065 — [DEVIATIONS.md](DEVIATIONS.md#relaxed-ferror--min_ferror) / [A6_TUNING](A6_TUNING.md) |
| PROBE SPINDLE NOSE crashes Z | Touch probe T#3014 was loaded — unload and load a cutter first; macro aborts if `#3014` is in the spindle |
| Pocket probe flies too fast | Local `[3017]` vs `[#3017]` typo — fixed in this tree; re-check after PB merges |
| Laser diameter never trips | `laser-beam-broken` polarity / BEAM OFFSET — [LASER_TOOL_SETTER](LASER_TOOL_SETTER.md) |
| Pendant Z jog blocked | Homing flags — see `xhc-whb04b-6.hal` machine.is-on tie-in |
| Spindle runs wrong direction | `custom.hal` M3/M4 swap comment — `REVERT` line |
| Fusion post missing M600 / 4th axis | Cached post — [TOOLSETTER.md](TOOLSETTER.md#cam--post-processor-linuxcnc-djrcps) |
| Probe Basic spindle RPM blank | `probe_basic_postgui.hal` must net `spindle-speed-in` (already done here; stock Probe Basic sim uses `scale_to_rpm`) |

**Useful commands**

```bash
halcmd show pin motion.probe-input
halcmd show pin halui.tool.number
halcmd watchpin spindle-at-speed-raw
ethercat slaves
```

## External examples this config borrowed from

| Source | What we took |
|--------|----------------|
| [TooTall18T/tool_length_probe](https://github.com/TooTall18T/tool_length_probe) v5.0.2 | `tool_touch_off.ngc`, M600 flow, G30 teach |
| [TooTall18T tool_length_probe wiki](https://github.com/TooTall18T/tool_length_probe/wiki) | M600 flow, `#5181–#5183`, parameter meanings |
| [kcjengr/probe_basic](https://github.com/kcjengr/probe_basic) | UI shell, probe routines, `pb_required_ini_settings.ini` |
| [linuxcnc-ethercat](https://github.com/linuxcnc-ethercat/linuxcnc-ethercat) | `lcec` + CiA402 patterns |
| LinuxCNC stock sim configs | HAL/INI structure, `trivkins` |
| Forum / Discord snippets | WHB pendant filter, VFD at-speed delay, probe input mux |

We do **not** claim these integrations are the only correct approach — they are what works on this machine today.

## Safety

Verify estop, drive enables, and spindle interlocks on the bench before cutting. Comments tagged `BREAKOUT OFF` and `REVERT` mark temporary wiring or INI shortcuts that are **unsafe for unattended production**.
