# Documentation index

Guides for the Lemontart EtherCAT mill config. Most of this was assembled from
examples and upstream projects — we link out wherever the canonical docs live.

**New here?** Start with **[GETTING_STARTED.md](GETTING_STARTED.md)** (zero →
hero path), then skim **[DEVIATIONS.md](DEVIATIONS.md)** when something does
not match stock LinuxCNC or Probe Basic.

---

## Learning paths

| Goal | Read in order |
|------|----------------|
| First boot on this repo | [GETTING_STARTED](GETTING_STARTED.md) → [README](../README.md) quick start |
| Understand “why is ours different?” | [DEVIATIONS](DEVIATIONS.md) |
| Tool length + M600 + touch probe | [TOOLSETTER](TOOLSETTER.md) → [PROBE_BASIC_UI](PROBE_BASIC_UI.md) |
| Laser diameter | [LASER_TOOL_SETTER](LASER_TOOL_SETTER.md) |
| Copy tool change to another mill | [INSTALL_TOOL_CHANGE](INSTALL_TOOL_CHANGE.md) |
| Servo bring-up | [A6_TUNING](A6_TUNING.md) → [SIGNAL_LOGGING](SIGNAL_LOGGING.md) → [ONE_CLICK_TUNING](ONE_CLICK_TUNING.md) |
| Manual gain ladder + LLM assist | [SERVO_TUNING](SERVO_TUNING.md) → [SEMI_AUTO_TUNING](SEMI_AUTO_TUNING.md) |
| Inertia ID before one-click | [GRAPHICAL_INERTIA_TUNE](GRAPHICAL_INERTIA_TUNE.md) |

---

## By topic

### Machine bring-up

| Doc | Covers |
|-----|--------|
| [GETTING_STARTED](GETTING_STARTED.md) | Staged path: LinuxCNC sim → EtherCAT → Probe Basic → CAM |
| [DEVIATIONS](DEVIATIONS.md) | Every deliberate difference vs stock LCNC / Probe Basic |
| [README](../README.md) | Hardware tables, layout, operator cheat sheet |

### Tooling & probing

| Doc | Covers |
|-----|--------|
| [TOOLSETTER](TOOLSETTER.md) | M600, contact setter, `#5181–#5183`, HAL probe mux |
| [LASER_TOOL_SETTER](LASER_TOOL_SETTER.md) | Kexin DS-5V-M diameter, M62/M63 mux |
| [PROBE_BASIC_UI](PROBE_BASIC_UI.md) | SET Z DRO, ABORT dialog, postgui HAL |
| [INSTALL_TOOL_CHANGE](INSTALL_TOOL_CHANGE.md) | Porting TooTall18T flow to another config |
| [metrology README](../probe_basic/subroutines/metrology/README.md) | Z repeatability macros |

### Motion & drives

| Doc | Covers |
|-----|--------|
| [A6_TUNING](A6_TUNING.md) | SDO map, Servo Tuning tab, 6065/6066 windows |
| [SIGNAL_LOGGING](SIGNAL_LOGGING.md) | Logging tab, CSV, channel config |
| [ONE_CLICK_TUNING](ONE_CLICK_TUNING.md) | Automated gain ladder per axis |
| [GRAPHICAL_INERTIA_TUNE](GRAPHICAL_INERTIA_TUNE.md) | Sigma II–style inertia ID |
| [SERVO_TUNING](SERVO_TUNING.md) | Manual tuning procedure |
| [SEMI_AUTO_TUNING](SEMI_AUTO_TUNING.md) | Clipboard → LLM workflow |
| [SERVO_TUNING_LLM](SERVO_TUNING_LLM.md) | Prompting notes for models |
| [INSTALL_SERVO_TUNING](INSTALL_SERVO_TUNING.md) | Porting tuning tabs to another mill |
| [PYTHON_PACKAGES](PYTHON_PACKAGES.md) | Qt/pyqtgraph deps for tabs |

---

## Probe Basic custom tabs (`probe_basic/user_tabs/`)

Probe Basic loads **every** folder here at startup — incomplete folders crash
launch. See [README § branch switching](../README.md#dev-notes-switching-feature-branches).

| Tab folder | Doc | Purpose |
|------------|-----|---------|
| `servo_tuner/` | [A6_TUNING](A6_TUNING.md), [ONE_CLICK_TUNING](ONE_CLICK_TUNING.md) | Drive SDO read/apply, FERR plot, one-click tune |
| `signal_monitor/` | [SIGNAL_LOGGING](SIGNAL_LOGGING.md) | Live HAL logging + CSV |
| `laser_setter/` | [LASER_TOOL_SETTER](LASER_TOOL_SETTER.md) | Laser diameter UI |
| `template_*` | — | Upstream placeholders (safe to keep) |

---

## External references (authoritative upstream)

We borrowed heavily from these — prefer their docs when ours stops:

| Resource | URL |
|----------|-----|
| LinuxCNC downloads & docs | https://linuxcnc.org/docs/html/ |
| linuxcnc-ethercat (`lcec`) | https://github.com/linuxcnc-ethercat/linuxcnc-ethercat |
| Probe Basic | https://github.com/kcjengr/probe_basic |
| QtPyVCP | https://github.com/kcjengr/qtpyvcp |
| TooTall18T tool length probe | https://github.com/TooTall18T/tool_length_probe |
| TooTall18T wiki (M600, params) | https://github.com/TooTall18T/tool_length_probe/wiki |
| XHC WHB04B-6 pendant | https://github.com/welter/welder/tree/master/xhc-whb04b-6 |
| StepperOnline manuals | https://www.omc-stepperonline.com/download-manual |
| kalico sota-motion (SDO tuning inspiration) | https://github.com/dderg/kalico/tree/sota-motion |

**Simulation:** this repo does **not** ship Probe Basic sim HAL or `probe_basic.ini`
(removed — the EtherCAT mill never used them). For learning LinuxCNC basics, use
the stock configs under `/usr/share/linuxcnc/` (e.g. `sim/axis/axis.ini`) before
cloning this tree.

---

## Key config files (quick map)

| File | Role |
|------|------|
| `ethercat_mill.ini` | Main INI — display, remaps, joint limits |
| `ethercat_mill.hal` | Joints, limits, probe mux, estop |
| `ethercat-conf.xml` | EtherCAT slaves, PDO, startup SDOs |
| `custom.hal` | H100 VFD Modbus, at-speed, faults |
| `probe_basic/probe_basic_postgui.hal` | Spindle RPM, manual tool change, timer |
| `probe_basic/subroutines/` | M600, probing, laser macros |
| `linuxcnc-djr.cps` | Fusion post (M600, G93, XYZA) |
