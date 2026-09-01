# Lemontart LinuxCNC config

A working Linuxcnc/ethercat config I am currently running on my Lemontart CNC Mill. Highlights include:
Probe Basic UI, 4x Stepperonline A6 servos, XHC-4 axis pendant, modbus-controlled H100 VFD, a contact toolsetter (TooTall18T's custom manual tool change overrides), a non-contact laser tool setter for diameter measuremnts, and a Servo Tuning tab with semi-auto + one-click auto-tune. 

Any deviations from stock configuration of probe basic or the components are captured in docs/DEVIATIONS.md.

Please note that -- for better or for worse -- this is a **my machine config**, not a polished product. Expect to edit EtherCAT
slave order, scales, limits, serial ports, and homing for your hardware. This repo might work better as a reference rather than a starting point for your own machine. 

If you are brand new to LinuxCNC, I'd recommend giving the GETTING STARTED page a read @ **[docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)**. I tried to capture a 1-pager that I wish I would have seen before I started my Linuxcnc journey.

---

## What you get

| Area | What’s in the box |
|------|-------------------|
| Motion | 4× StepperOnline A6 (XYZ 400 W, A 100 W) over EtherCAT / LCEC |
| UI | [Probe Basic](https://github.com/kcjengr/probe_basic) (QtPyVCP) |
| Pendant | XHC WHB04B-6 with jog smoothing |
| Spindle | H100 VFD over Modbus (`mb2hal`) |
| Tool length | Contact toolsetter via **M600** (TooTall18T-style flow) |
| Tool diameter | Kexin DS-5V-M **laser** diameter / length tab |
| Metrics | Signal logging + **Servo Tuning** (semi-auto, one-click, inertia WIP) |

---

## Docs map (pick your path)

| I want to… | Read this |
|------------|-----------|
| Bring the machine up from zero | **[GETTING_STARTED.md](docs/GETTING_STARTED.md)** |
| Understand “why doesn’t this behave like stock?” | **[DEVIATIONS.md](docs/DEVIATIONS.md)** |
| Port this mill to a CODESYS PLC + browser HMI | **[CODESYS_ARCHITECTURE.md](docs/CODESYS_ARCHITECTURE.md)** · plugins: **[CODESYS_PLUGINS.md](docs/CODESYS_PLUGINS.md)** |
| Change tools and probe length (contact setter) | **[TOOLSETTER.md](docs/TOOLSETTER.md)** |
| Measure diameter with the laser | **[LASER_TOOL_SETTER.md](docs/LASER_TOOL_SETTER.md)** |
| Copy tool-change onto another mill | **[INSTALL_TOOL_CHANGE.md](docs/INSTALL_TOOL_CHANGE.md)** |
| Tweak Probe Basic UI / SET Z / abort dialog | **[PROBE_BASIC_UI.md](docs/PROBE_BASIC_UI.md)** |
| Example tuning / M600 test G-code | **[TUNING_PROGRAMS.md](docs/TUNING_PROGRAMS.md)** |
| Log following error / tune servos | **[Servo auto-tuning](#servo-tuning--auto-tune)** · [docs index](docs/README.md) · [TUNING_PROGRAMS](docs/TUNING_PROGRAMS.md) · [SIGNAL_LOGGING](docs/SIGNAL_LOGGING.md) · [A6_TUNING](docs/A6_TUNING.md) · [SEMI_AUTO_TUNING](docs/SEMI_AUTO_TUNING.md) · [ONE_CLICK_TUNING](docs/ONE_CLICK_TUNING.md) · [GRAPHICAL_INERTIA_TUNE](docs/GRAPHICAL_INERTIA_TUNE.md) |

Full list and learning paths: **[docs/README.md](docs/README.md)**. A proposed CODESYS SoftMotion + React HMI architecture (not implemented yet) is in **[docs/CODESYS_ARCHITECTURE.md](docs/CODESYS_ARCHITECTURE.md)**.

---

## Quick start

1. Install [LinuxCNC](https://linuxcnc.org/downloads/) with EtherCAT / LCEC.
2. Point `/etc/ethercat.conf` at your dedicated NIC.
3. Get **one axis** moving with a minimal config before you lean on this repo.
4. Clone this tree and edit:
   - `ethercat-conf.xml` — your slave chain
   - `ethercat_mill.ini` / `ethercat_mill.hal` — scales, limits, homing
   - `h100.mb2hal` — `SERIAL_PORT`
   - `PROGRAM_PREFIX` in the INI — must point at *your* NC programs directory
5. Launch with `linuxcnc ethercat_mill.ini` (set `QT_QUICK_BACKEND=software` if Probe Basic fails to render).

The staged path (sim → EtherCAT → Probe Basic → CAM) is spelled out in
[GETTING_STARTED.md](docs/GETTING_STARTED.md).

---

## Layout

| Path | Role |
|------|------|
| `ethercat_mill.ini` | Main INI |
| `ethercat_loadusr.hal` | Loads `lcec_conf` once (TWOPASS-safe) |
| `ethercat_mill.hal` | Joints, CiA 402, limits, probe mux, laser pin |
| `probe_beep.hal` | Audible beep on probe/toolsetter trip or laser beam-block (`beep.mp3`) |
| `ethercat-conf.xml` | EtherCAT slaves + drive SDOs |
| `custom.hal` | VFD Modbus, at-speed delay, faults |
| `h100.mb2hal` | VFD register map |
| `xhc-whb04b-6.hal` | Pendant |
| `probe_basic/` | UI, macros, tool table, custom tabs + tool-change dialog |
| `post-processor/linuxcnc-djr.cps` | Fusion post (M600, XYZA, G93) |
| `docs/` | Guides |
| `docs/reference/` | Vendor manuals / worksheets (H100, Sigma II calculator) |

These files talk to each other a lot. An AI coding assistant helps when you point
it at several of them at once. Add one feature at a time, and rigorously test before moving on to the next feature.

---

## Day-one operator cheat sheet

| Action | Where |
|--------|--------|
| Set work Z after a shim touch-off | XYZA DRO **SET Z** → [PROBE_BASIC_UI](docs/PROBE_BASIC_UI.md) |
| Load a cutter and probe its length | **LOAD SPINDLE** or CAM `T<n> M600` → [TOOLSETTER](docs/TOOLSETTER.md) |
| Cancel a tool change mid-job | **ABORT** on the Manual Tool Change dialog → [PROBE_BASIC_UI](docs/PROBE_BASIC_UI.md) |
| Measure tool diameter (laser) | Laser Setter tab → [LASER_TOOL_SETTER](docs/LASER_TOOL_SETTER.md) |
| Semi-auto / one-click servo tune | Servo Tuning tab → [section below](#servo-tuning--auto-tune) |
| Z repeatability tests | MDI metrology macros → [metrology README](probe_basic/subroutines/metrology/README.md) |

---

## Contact Tool length setter overview

Manual tool changes use M600 rather than the default M6, as per TooTall18T's suggestion. 
This means that the CAM software has to output M600 instead, that modification has been made in the post processor and is in this repo. 

CAM asks for `T3 M600`. The machine retracts, parks at a **tool-load** spot so
you can change the collet, waits for **OK**, then moves to the **contact
toolsetter**, probes length, writes the tool table, and continues. Touch probe
and toolsetter share one LinuxCNC probe input, but HAL only listens to the
sensor that matches the tool in the spindle (T99 = touch probe, anything else =
toolsetter). Details: [TOOLSETTER.md](docs/TOOLSETTER.md).

---

## Laser tool setter overview

The Kexin DS-5V-M is a U-slot beam-break sensor. The Laser Setter tab measures
diameter by finding the tip in Z, then a coarse G38 plus a **static-X** peak
hunt (park X, wait for any flute, step inward). Measure
macros use **M62 P0** only around each **G38** (never during G0/G1); **M63 P0**
restores the contact probe mux. Capture BEAM XY with the tool blocking the light,
set START OFFSET / MAX TRAVEL / Z DROP, then MEASURE DIAMETER. Optional
**CALIBRATE BEAM** (master pin − raw) stores a beam-width offset applied to later
readings.

You could replace the contact toolsetter entirely, but the U-slot of this sensor accepts a maximum of 9mm tools, which I find too restricting. 
So I have both types on my machine.

**Full guide** (measure flow, **wiring + installation**, HAL mux, params):
[docs/LASER_TOOL_SETTER.md](docs/LASER_TOOL_SETTER.md)

### Tool Diameter Measurement

1. Restart LinuxCNC after HAL / tab changes.
2. Jog Y to slot center, X in the beam (LED broken) → **CAPTURE BEAM**.
3. Set **START OFFSET** (default 15), **MAX TRAVEL** (default 30), **Z DROP**.
4. **MEASURE DIAMETER**.
5. Optional: enter **MASTER PIN** → measure again → **CALIBRATE BEAM**.

---

## Servo tuning / auto-tune

A lot of the work in this repo is around making A6-EC loop gains less painful to
set. Probe Basic has a **Servo Tuning** tab that reads/writes drive SDOs over
EtherCAT, plots CiA **60F4** following error (not LinuxCNC `joint.f-error`), and
supports three related workflows:

| Workflow | What it is | When to use it |
|----------|------------|----------------|
| **Manual** | Edit Pending gains → **APPLY TO DRIVE**; zone ladder in the docs | Learning the loops, or one-off knobs |
| **Semi-auto** | Frozen NGC stimulus → **COPY PLOT** / **COPY TUNING** → paste into an LLM → apply suggestions yourself | Judgment calls, notch placement, “does this look right?” |
| **One-click** | One button per axis runs the full gain ladder (stimulus + FFT stability gate + notch + journaled revert) | First pass on an axis when you want the robot to climb gains |

**Loop gains are not written from `ethercat-conf.xml`** — that used to wipe bench
tuning on every LinuxCNC start. Startup still sets conservative drive
position-deviation windows (6065/6066). APPLY is RAM-only; store to drive
EEPROM yourself when you like a result.

### Semi-auto tune (clipboard → LLM)

Operator-in-the-loop. You run a frozen back-and-forth move, copy the FERR plot
and the live parameter text, paste into an LLM that has the tuning playbook,
then type suggestions into Pending and press **APPLY TO DRIVE**. The LLM never
writes SDOs.

1. Home / enable. Open **Servo Tuning** (parameters auto-read on tab open).
2. Select the edit axis → **START PLOT** → run `<axis>_tuning.ngc` from your
   `PROGRAM_PREFIX` directory (examples in [TUNING_PROGRAMS.md](docs/TUNING_PROGRAMS.md)).
3. **COPY PLOT** + **COPY TUNING** → paste into an LLM with
   [SERVO_TUNING_LLM.md](docs/SERVO_TUNING_LLM.md) in context.
4. Edit Pending from the suggestion → **APPLY TO DRIVE** → repeat.

Full operator guide: **[SEMI_AUTO_TUNING.md](docs/SEMI_AUTO_TUNING.md)**.

### One-click auto-tune

Automated version of the manual gain ladder: one button per axis moves a short
repeatable stroke, watches drive FERR, climbs speed → notch → position →
integral until the FFT stability gate trips, backs off, verifies, and saves a
preset. Every step is journaled under `logs/tuning/one_click/` (cancel /
exception restores baseline SDOs).

1. Home, clear the envelope, machine **ON**. Keep a hand near ESTOP — **the axis moves**.
2. Servo Tuning → pick the axis → profile (**BALANCED** is the default) →
   **ONE-CLICK TUNE**.
3. Read the summary; try the axis; EEPROM-store if you like it.

Same engine runs headless via `scripts/run_auto_tune.py` (`--sim` / `--dry-run`
for desk demos). Details, safety model, and state machine:
**[ONE_CLICK_TUNING.md](docs/ONE_CLICK_TUNING.md)**.

### Inertia auto-tune (still in the works)

There is an **INERTIA** panel on the same tab that tries to identify load/motor
inertia ratio and write **C00.06** (graphical physics fit + Yaskawa Sigma II
cross-check — see [GRAPHICAL_INERTIA_TUNE.md](docs/GRAPHICAL_INERTIA_TUNE.md)).
That path is **still being hardened** and is not something I would treat as
“done” yet.

**Practical caveat:** in many scenarios you can get away with the factory
default inertia (**C00.06 = 100%**) and still get a usable one-click / semi-auto
gain tune. Prefer measuring inertia when the load is heavy vs the motor, or when
gains refuse to settle — but do not block on a perfect C00.06 before you start
tuning.

### Tuning docs map

| Doc | Covers |
|-----|--------|
| [SERVO_TUNING.md](docs/SERVO_TUNING.md) | Manual zone ladder (high → low frequency) |
| [SEMI_AUTO_TUNING.md](docs/SEMI_AUTO_TUNING.md) | Clipboard → LLM loop |
| [ONE_CLICK_TUNING.md](docs/ONE_CLICK_TUNING.md) | Per-axis auto gain ladder |
| [GRAPHICAL_INERTIA_TUNE.md](docs/GRAPHICAL_INERTIA_TUNE.md) | Inertia panel (WIP) |
| [A6_TUNING.md](docs/A6_TUNING.md) | SDO map, APPLY path, branch status |
| [SERVO_TUNING_LLM.md](docs/SERVO_TUNING_LLM.md) | Playbook to paste into an LLM |
| [INSTALL_SERVO_TUNING.md](docs/INSTALL_SERVO_TUNING.md) | Drop the tabs onto another mill |
| [SIGNAL_LOGGING.md](docs/SIGNAL_LOGGING.md) | Multi-channel CSV / plots |

---

## Contact probe vs toolsetter (HAL)

| Spindle tool | Active input | Ignored |
|--------------|--------------|---------|
| **T99** (touch probe) | Touch probe — Slave 1 DI5 | Toolsetter DI2 |
| **Any other tool** | Toolsetter — Slave 1 DI2 | Touch probe DI5 |

Laser (`laser-beam-broken`, Slave 2 DI5) joins `motion.probe-input` only while
**M62 P0** is active around each laser **G38**; **M63 P0** restores the table above
(also on abort).

---

## DEV NOTES: Switching feature branches

Probe Basic loads **every** folder under `probe_basic/user_tabs/`. If you check
out an older branch, leftover empty folders from another feature can crash
startup (`FileNotFoundError` for `something/something.py`).

After switching, make sure each folder under `user_tabs/` has a matching `.py`:

```bash
ls probe_basic/user_tabs/
# delete any folder that is missing {name}/{name}.py
```

`linuxcnc.var` is machine state — stash it before branch hops if git complains:

```bash
git stash push -m "linuxcnc.var" -- linuxcnc.var
git checkout <branch>
```

---

## Current machine notes

- Built-in M6 motion is **off**; macros own retract / park / probe.
- M600 collet pause is at a fixed **tool-load** XY (default G53 **270, 100**),
  not the taught setter. Setter teach still uses `#5181–#5183`.
- Custom Manual Tool Change dialog with **ABORT** (Esc/close ignored).
- REF ALL order: Z → X → Y → A.
- Software E-stop: Slave 3 DI1 (DB15 pin 10).
- Drive position-deviation windows (SDO 6065/6066): **0.5 mm / 0.5° / 250 ms**
  at startup (one-click / inertia tuning temporarily raises 6065 to **2.0** during
  moves) — see [A6_TUNING.md](docs/A6_TUNING.md).
- INI `FERROR` values are intentionally wide for bring-up — tighten for production
  ([DEVIATIONS.md](docs/DEVIATIONS.md)).

Deep hardware notes still live in [DEVIATIONS.md](docs/DEVIATIONS.md) and
[GETTING_STARTED.md](docs/GETTING_STARTED.md).

### Slave / DI wiring (this mill)

Home and limit switches are active-low NC and inverted in HAL (`not.*`). Contact
probe inputs are NC (NPN) and wired direct (no inversion). Source of truth:
[`ethercat_mill.hal`](ethercat_mill.hal).

| Slave | HAL pin | DI | DB15 pin | Signal use |
|-------|---------|----|----------|------------|
| 0 (X/Y IO) | `lcec.0.0.di-4` | DI4 | 7 | X home |
| 0 (X/Y IO) | `lcec.0.0.di-1` | DI1 | 10 | X limit chain (±) |
| 0 (X/Y IO) | `lcec.0.0.di-5` | DI5 | 11 | Y home |
| 0 (X/Y IO) | `lcec.0.0.di-2` | DI2 | 9 | Y limit chain (±) |
| 1 (Z/probe IO) | `lcec.0.1.di-4` | DI4 | 7 | Z home (+Z) |
| 1 (Z/probe IO) | `lcec.0.1.di-2` | DI2 | 9 | Contact toolsetter (gated when not T99) |
| 1 (Z/probe IO) | `lcec.0.1.di-5` | DI5 | 11 | Touch probe (gated when T99) |
| 2 (Z/laser IO) | `lcec.0.2.di-5` | DI5 | 11 | Laser DS-5V-M (`laser-beam-broken`) |
| 2 (Z/laser IO) | `lcec.0.2.di-2` | DI2 | 9 | Free (Z− limit commented out in HAL) |
| 3 (A/estop IO) | `lcec.0.3.di-1` | DI1 | 10 | Software E-stop NC |
| 3 (A/estop IO) | `lcec.0.3.di-3` | DI3 | 8 | A home (planned; commented out in HAL) |

### A6 CN1 / DB15 input map

Every StepperOnline A6 EtherCAT drive uses the same CN1 DB15 pinout. HAL names
are `lcec.0.<slave>.di-N`. The table above is this mill’s assignment; the
connector map below is the same on every slave:

| A6 input | CN1 / DB15 pin | Typical/default label |
|----------|----------------|------------------------|
| DI1 | 10 | Positive limit / user input |
| DI2 | 9 | Negative limit / user input |
| DI3 | 8 | Home input |
| DI4 | 7 | TouchProbe2 |
| DI5 | 11 | TouchProbe1 |
| DI common | 13 | COM+ |
| 24 V output | 15 | Internal +24 V supply |

### Spindle at-speed 

I was finding that the VFD's at-speed signal was triggering early, so I added a fixed delay to guarantee the spindle was actually at speed. 
After the VFD feedback matches commanded RPM (±50), HAL waits an extra **5 s**
before `spindle.0.at-speed` goes true. Tunable in `custom.hal`.

### H100 critical faults

Fault codes `64` (overcurrent) and `92` (overtemp) force a software E-stop.

---

## Safety

Verify E-stop, drives, and spindle before running programs. Review breakout /
limit comments in the INI if you are still on the bench.

---

## Contributing / adapting

PRs and forks welcome. When you adapt this to another mill:

1. Change one subsystem at a time (EtherCAT → motion → spindle → toolsetter → laser).
2. Keep [DEVIATIONS.md](docs/DEVIATIONS.md) honest — that file is how the next person
   (or future you) avoids a weekend of confusion.
3. Prefer documenting “why” next to “what.”
