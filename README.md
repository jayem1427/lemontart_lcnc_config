# laser-setter

LinuxCNC configuration for a **Lemontart**-class EtherCAT mill:

- 4× Stepperonline A6 Servos (400W for xyz, 100W for A)
- **Probe Basic** (QtPyVCP) UI
- **XHC WHB04B-6** wireless pendant, with low-pass filter for smooth jogging
- **H100 VFD** over Modbus RTU via `mb2hal` (`h100.mb2hal`)

Please treat this repo as a **reference built from examples**, not a guaranteed drop-in. Expect to adjust EtherCAT XML, scales, limits, serial port, and homing before cutting metal.

## Documentation

| Doc | Contents |
|-----|----------|
| **[GETTING_STARTED.md](GETTING_STARTED.md)** | Zero-to-hero path, external links, first boot, troubleshooting |
| **[DEVIATIONS.md](DEVIATIONS.md)** | How this config differs from stock LinuxCNC / Probe Basic |
| **[TOOLSETTER.md](TOOLSETTER.md)** | M600 toolsetter, touch-probe routing, Fusion post |
| **[PROBE_BASIC_UI.md](PROBE_BASIC_UI.md)** | Custom DRO (SET Z), spindle widgets, UI paths |
| [probe_basic/subroutines/metrology/README.md](probe_basic/subroutines/metrology/README.md) | Z repeatability test macros |

New to LinuxCNC? Start with [GETTING_STARTED.md](GETTING_STARTED.md) — do not jump straight to Probe Basic. Something behaves unlike the manual? Check [DEVIATIONS.md](DEVIATIONS.md) first.

## Requirements

- LinuxCNC built with **EtherCAT / LCEC** (`lcec`, `lcec_conf`)
- **Probe Basic** / QtPyVCP stack matching your LinuxCNC version
- Optional: `mb2hal` for the VFD

## Quick start

1. Install LinuxCNC: [linuxcnc.org/downloads](https://linuxcnc.org/downloads/)
2. Install [linuxcnc-ethercat](https://github.com/linuxcnc-ethercat/linuxcnc-ethercat)
3. Set the EtherCAT NIC in `/etc/ethercat.conf` (`ip link` on the dedicated port)
4. Copy a default wizard config; get one axis moving before cloning this repo
5. Edit **`ethercat-conf.xml`** — slave order, PDOs, and A6 SDOs for your chain
6. Edit **`ethercat_mill.ini`** / **`ethercat_mill.hal`** — scales, limits, homing
7. Edit **`h100.mb2hal`** — `SERIAL_PORT` (often `/dev/ttyUSB0`) and VFD registers
8. Launch with **`./launch.sh`** or `linuxcnc ethercat_mill.ini`

Note: **`PROGRAM_PREFIX`** in the committed INI is an absolute developer path. Point it at this repo’s `nc_files/` or your own folder.

Full staged path (sim → EtherCAT → Probe Basic → CAM): **[GETTING_STARTED.md](GETTING_STARTED.md)**.

## Signal logging (servo tuning)

HAL telemetry, CSV logging, and a **Logging** tab in Probe Basic for following error, torque, and velocity on X/Y/Z/A. See **[SIGNAL_LOGGING.md](SIGNAL_LOGGING.md)** for the tab UI, HAL chain, drive SDO limits, tuning G-code, sample rate / Nyquist notes, and test plan.

**A6 loop tuning + Servo Tuning GUI** (plot drive 60F4 separately): **[A6_TUNING.md](A6_TUNING.md)** — active; see Status. **Install on another machine:** **[INSTALL_SERVO_TUNING.md](INSTALL_SERVO_TUNING.md)**. Manual / LLM playbooks: **[SERVO_TUNING.md](SERVO_TUNING.md)**, **[SERVO_TUNING_LLM.md](SERVO_TUNING_LLM.md)**.

Branch: `cursor/a6-tuning-ferror-comp-70f6` (extends signal-logging work).

## Layout

| File | Purpose |
|------|---------|
| `ethercat_mill.ini` | Main INI |
| `ethercat_loadusr.hal` | Loads `lcec_conf` once (TWOPASS-safe) |
| `ethercat_mill.hal` | Joints, CiA 402, limits, E-stop integration |
| `ethercat-conf.xml` | EtherCAT slave layout |
| `custom.hal` | Modbus spindle mux, extras |
| `h100.mb2hal` | Modbus register map for VFD |
| `xhc-whb04b-6.hal` | Pendant |
| `probe_basic/` | Probe Basic YAML, postgui HAL, DROs, macros, `tool.tbl`, Logging tab |
| `nc_files/` | Default program search path |
| `linuxcnc-djr.cps` | Fusion 360 post (M600, XYZA, G93) |
| `GETTING_STARTED.md` | Learning path and troubleshooting |
| `DEVIATIONS.md` | Differences vs stock LinuxCNC / Probe Basic |
| `PROBE_BASIC_UI.md` | SET Z DRO and UI customizations |

Many of these files are connected to each other. Using a tool like Cursor or Claude Code will absolutely make your life easier since you can expand the context window to multiple files, but please always verify any changes that AI makes. Add testable features one-at-a-time, and verify they work before proceeding forward.

## Operator shortcuts (Probe Basic)

| Action | Where |
|--------|--------|
| SET WCO Z (shim / manual touch-off) | XYZA DRO **SET Z** — [PROBE_BASIC_UI.md](PROBE_BASIC_UI.md) |
| Load cutter + probe length | **LOAD SPINDLE** or CAM `T<n> M600` — [TOOLSETTER.md](TOOLSETTER.md) |
| Z repeatability tests | MDI metrology macros — [metrology README](probe_basic/subroutines/metrology/README.md) |

Feed override runs to **250%** (`MAX_FEED_OVERRIDE = 2.5`); pendant WHB knob uses the same limit.

## Toolsetter (semi-auto tool length)

TooTall18T [`tool_length_probe`](https://github.com/TooTall18T/tool_length_probe) + `M600` integration for manual collet tool changes with probing.

- **Install on another machine:** **[INSTALL_TOOL_CHANGE.md](INSTALL_TOOL_CHANGE.md)**
- **Behavior / button map / Fusion:** **[TOOLSETTER.md](TOOLSETTER.md)**

### Touch probe vs toolsetter routing

Both sensors share one LinuxCNC probe input (`motion.probe-input`), but `ethercat_mill.hal` **gates** them by **spindle tool** (`halui.tool.number`) — only one source can assert `motion.probe-input` at a time:

| Spindle tool | Active input | Ignored |
|--------------|--------------|---------|
| **T99** (touch probe) | Touch probe — Slave 1 DI5 | Toolsetter — Slave 1 DI2 |
| **Any other tool** | Toolsetter — Slave 1 DI2 | Touch probe — Slave 1 DI5 |

Both are wired **NC (NPN), direct** (no HAL inversion). Routing compares `halui.tool.number` to **99** with `comp.0.equal` (not `tool-prep-number`, which can disagree with the tool actually in the spindle after M61 or restart).

```
halui.tool.number ──► comp.0.equal (== 99?)
                         │
           ├─ TRUE  ──► touch probe (DI5) ──┐
           └─ FALSE ──► toolsetter (DI2) ────┼── or2.0 ──► motion.probe-input
```

Bit gating uses `and2.3` / `and2.4` and `or2.0` (`mux2` is float-only and cannot mux digital probe inputs). `or2.1` in `custom.hal` is reserved for VFD fault OR (do not `loadrt or2` with `names=` in other HAL files).

This lets you unplug the NC touch probe while running M600/toolsetter with a cutter loaded — the unplugged probe cannot false-trip probing when T99 is not in the spindle.

Default probe tool is **T99**; `#3014`, `tool.tbl`, and HAL must all match. See **[Touch probe tool number](TOOLSETTER.md#touch-probe-tool-number-setup-and-renumbering)** in TOOLSETTER.md for first-time setup and renumbering.

## Current machine behavior (captured config)

- Built-in M6 tool-change motion is **disabled** (`TOOL_CHANGE_AT_G30=0`, `TOOL_CHANGE_QUILL_UP=0`); retract and G30 are handled by `tool_touch_off.ngc` / `M600`.
- Home/limit inputs below are wired active-low NC and inverted in HAL (`not.*`).
- Touch probe (Slave 1 DI5) and contact toolsetter (Slave 1 DI2 / DB15 pin 9) are NC and **gated** to `motion.probe-input` by spindle tool (T99 → probe, else → toolsetter). See **Touch probe vs toolsetter routing** above.
- Software E-stop is wired NC on Slave 3 DI1 / DB15 pin 10 and gates `iocontrol.0.emc-enable-in`.

| Drive / EtherCAT slave | DI input | Signal use |
|------------------------|----------|------------|
| Slave 0 (X/Y drive IO) | DI4 | X home (`joint.0.home-sw-in`) |
| Slave 0 (X/Y drive IO) | DI1 | X limit chain (`joint.0.neg-lim-sw-in`, `joint.0.pos-lim-sw-in`) |
| Slave 0 (X/Y drive IO) | DI5 | Y home (`joint.1.home-sw-in`) |
| Slave 0 (X/Y drive IO) | DI2 | Y limit chain (`joint.1.neg-lim-sw-in`, `joint.1.pos-lim-sw-in`) |
| Slave 1 (Z/probe IO) | DI4 | Z home at +Z (`joint.2.home-sw-in`) |
| Slave 2 (Z/aux IO) | DI2 | Z negative limit (`joint.2.neg-lim-sw-in`) |
| Slave 1 (Z/probe IO) | DI2 / DB15 pin 9 | Contact toolsetter (`toolsetter-in` → `and2.4` when not T99) |
| Slave 1 (Z/probe IO) | DI5 | Touch probe (`touch-probe-in` → `and2.3` when T99) |
| Slave 3 (A axis IO) | DI1 / DB15 pin 10 | Software E-stop NC switch (`iocontrol.0.emc-enable-in`) |
| Slave 3 (A axis IO) | DI3 (planned) | A home (currently commented out in HAL) |

### A6 CN1 / DB15 input map

Each StepperOnline A6 EtherCAT drive exposes the same digital input names in HAL
as `lcec.0.<slave>.di-N`. The current software E-stop switch uses **Slave 3 DI1**,
which is **CN1 / DB15 pin 10**.

| HAL input example on Slave 3 | A6 input | CN1 / DB15 pin | Typical/default input label |
|------------------------------|----------|----------------|-----------------------------|
| `lcec.0.3.di-1` | DI1 | 10 | Positive limit / user input |
| `lcec.0.3.di-2` | DI2 | 9 | Negative limit / user input |
| `lcec.0.3.di-3` | DI3 | 8 | Home input |
| `lcec.0.3.di-4` | DI4 | 7 | TouchProbe2 |
| `lcec.0.3.di-5` | DI5 | 11 | TouchProbe1 |
| - | DI common | 13 | COM+ |
| - | 24 V output | 15 | Internal +24 V supply |

## Spindle at-speed delay

HAL-only change in `custom.hal` (active on `main`) that adds a fixed settle buffer **after** the VFD feedback already matches the commanded RPM. No Python remaps, G-code changes, or post-processor edits.

### Signal flow

1. **Command** — LinuxCNC motion sets `spindle.0.speed-out-abs` (RPM). `custom.hal` scales that to 0.1 Hz and writes it to the VFD via Modbus (`mb2hal.freq_set`).
2. **Feedback** — The VFD reports output frequency on `mb2hal.freq_fb.00` (polled at 5 Hz). `mult2.5` scales it back to RPM on `spindle.0.speed-in`.
3. **Speed compare** — `near.0` is true when |command − feedback| &lt; 50 RPM. This is exposed on net `spindle-at-speed-raw` (unchanged compare logic).
4. **Settle delay** — `timedelay.0` requires `spindle-at-speed-raw` to stay true for **5.0 s** (`on-delay`) before `spindle.0.at-speed` goes true. If the compare drops false, at-speed clears immediately (`off-delay 0.0`).

```
spindle.0.speed-out-abs ──► VFD (freq_set)
VFD (freq_fb) ──► spindle.0.speed-in
         command ──┐
                   ├── near.0 ──► spindle-at-speed-raw ──► timedelay.0 ──► spindle.0.at-speed
         feedback ─┘
```

Total wait before feed moves can proceed ≈ **VFD ramp time** (accel set on the drive) **+ 5 s** after feedback is within tolerance. Mid-program `S` word changes that push feedback outside tolerance will re-arm the 5 s timer.

### HAL pins and nets

| Item | Role |
|------|------|
| `near.0` | Command vs feedback compare (50 RPM tolerance) |
| `spindle-at-speed-raw` | `near.0.out` — electrical speed match |
| `timedelay.0` | 5 s on-delay after raw goes true |
| `spindle-at-speed` | `timedelay.0.out` → `spindle.0.at-speed` |

Tunable in `custom.hal`: `timedelay.0.on-delay` (seconds), `near.0.difference` (RPM tolerance).

### Testing

Restart LinuxCNC after changing HAL (loaded at startup). While running:

```bash
halcmd watchpin spindle-at-speed-raw    # goes true when within 50 RPM
halcmd watchpin spindle.0.at-speed      # goes true ~5 s later
```

MDI: `M3 S2000`, then a small `G1` — the move should wait until `spindle.0.at-speed` is true.

### Disabling the delay

To revert to immediate at-speed (no 5 s settle), edit `custom.hal`: remove the `timedelay` block and wire `near.0.out` directly to `spindle.0.at-speed`. The `feature_spindle-delay` branch is kept for reference.

## H100 VFD fault monitoring

`h100.mb2hal` polls H100 input register `0x000A` with Modbus function `0x04`
(`fnct_04_read_input_registers`). The H100 manual lists this register as
`Current fault`.

`custom.hal` watches the returned decimal code:

| Decimal code | H100 display | Meaning | HAL signal |
|--------------|--------------|---------|------------|
| `64` | `E.OCS` | Overcurrent | `spindle-vfd-overcurrent` |
| `92` | `E.oHS` | Inverter overheating | `spindle-vfd-overtemperature` |

Either fault sets `spindle-vfd-critical-fault`, which triggers
`halui.estop.activate`.

## Laser tool setter (in progress)

Dedicated Probe Basic tab for an upcoming laser tool setter (tool length + diameter + runout + broken-tool detect). Branch: `cursor/laser-setter-1afc`.

**Current state:** UI and setup-parameter plumbing are in place; measure buttons still call skeleton NGC macros (DEBUG + exit). No HAL pins or real probing yet.

### Loading the tab

- `USER_TABS_PATH = probe_basic/user_tabs/` in `ethercat_mill.ini` `[DISPLAY]`
- Tab source: `probe_basic/user_tabs/laser_setter/` (`.ui`, `.py`, `.qss`, `kexin_tool_setter.png`)
- Skeleton macros: `probe_basic/subroutines/laser_*.ngc`

### Setup fields (Measure column)

Before any measure action, the tab syncs three values into LinuxCNC via `o<laser_set_start_xy> call [X] [Y] [RPM]`:

| UI field | NGC parameter | Notes |
|----------|---------------|-------|
| START X | `#5181` | Editable; **CAPTURE CURRENT X/Y** fills from machine position |
| START Y | `#5182` | Same as START X |
| PROBE RPM | `#5183` | Must be &gt; 0; default 1000 |

**CAPTURE CURRENT X/Y** writes the current machine X/Y into the fields, then runs the same sync MDI. Length / diameter / runout / broken-check / calibrate buttons call `_sync_setup_params()` first; invalid X/Y/RPM blocks the MDI with a status error.

### Measure buttons

| Button | MDI macro | Z-touch gate |
|--------|-----------|--------------|
| MEASURE LENGTH | `o<laser_length> call` | Required first (sets `_z_touched`) |
| MEASURE DIAMETER | `o<laser_diameter> call` | After length |
| MEASURE RUNOUT | `o<laser_runout> call` | After length |
| BROKEN TOOL CHECK | `o<laser_broken_check> call` | After length |
| CALIBRATE | `o<laser_calibrate> call` | After length |
| AIR BLAST | `o<laser_air_blast_toggle> call` | No gate |

Removed from earlier skeleton: **MEASURE FULL TOOL**, **UPDATE TOOL TABLE**, footer **ABORT** (use LinuxCNC stop/estop). Header **?** opens a help placeholder dialog.

### UI / theme

- Probe Basic dark palette (`#2e3436` / `#363b3d`), BebasKai font (loaded from `/usr/share/fonts/truetype/BebasKai.ttf`)
- Three-column layout: Measure | Results + tool-setter diagram | Calibration
- `kexin_tool_setter.png` scales with tab resize (`IMAGE_DISPLAY_SCALE = 0.624`)
- Units combo converts START X/Y and all linear readouts between mm and inch

### Roadmap (staged PRs)

Hardware pick → HAL wiring → length-only macro → calibration → diameter measure → broken-tool M-code → per-flute profiling. Each phase on its own branch.

## What was left out of git, but is helpful to keep in the config


Large manual PDFs, simulation logs, QtPyVCP pickles, and personal scratch notes. Any documentation or reference is great to keep in the config. This will be helpful for you, as well as an AI tool as long as you explicitly tell it to rely on documentation you've uploaded to your working directory.

## Safety

Verify estop, drives, and spindle before running any programs. Review **breakout** comments in `ethercat_mill.ini` if you are still on the bench.
