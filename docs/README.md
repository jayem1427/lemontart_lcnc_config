# Documentation index

Guides for the Lemontart EtherCAT mill config. This repo is a **working reference**
assembled from examples — not a polished product. When in doubt, trust upstream
LinuxCNC and Probe Basic docs; use these pages to see how *this* machine wires
things together.

**Start here:** [GETTING_STARTED.md](GETTING_STARTED.md) (zero → hero) ·
[DEVIATIONS.md](DEVIATIONS.md) (vs stock LinuxCNC / Probe Basic) ·
[CODESYS_ARCHITECTURE.md](CODESYS_ARCHITECTURE.md) (CODESYS + browser HMI) ·
[CODESYS_PLUGINS.md](CODESYS_PLUGINS.md) (kernel + feature packs)

---

## Learning paths

### Brand new to LinuxCNC

1. [GETTING_STARTED.md](GETTING_STARTED.md) — staged path (sim → EtherCAT → Probe Basic → CAM)
2. [LinuxCNC documentation](https://linuxcnc.org/docs/html/) — official reference
3. [Probe Basic](https://github.com/kcjengr/probe_basic) — UI install and concepts
4. Return here when motion works and you need toolsetter / laser / tuning specifics

### Operator (day-to-day)

| Task | Doc |
|------|-----|
| Load cutter + probe length | [TOOLSETTER.md](TOOLSETTER.md) |
| Cancel mid M600 | [PROBE_BASIC_UI.md](PROBE_BASIC_UI.md) |
| Set WCO Z after shim touch-off | [PROBE_BASIC_UI.md](PROBE_BASIC_UI.md) |
| Measure tool diameter (laser) | [LASER_TOOL_SETTER.md](LASER_TOOL_SETTER.md) |
| Z repeatability tests | [metrology README](../probe_basic/subroutines/metrology/README.md) |

### Integrator (fork / adapt)

| Task | Doc |
|------|-----|
| Why doesn't this match the manual? | [DEVIATIONS.md](DEVIATIONS.md) |
| Copy tool-change to another mill | [INSTALL_TOOL_CHANGE.md](INSTALL_TOOL_CHANGE.md) |
| Copy servo tuning tabs | [INSTALL_SERVO_TUNING.md](INSTALL_SERVO_TUNING.md) |
| Fusion post (M600, XYZA, G93) | [TOOLSETTER.md § CAM](TOOLSETTER.md#cam--post-processor-linuxcnc-djrcps) |
| Port this mill to CODESYS + a browser HMI | [CODESYS_ARCHITECTURE.md](CODESYS_ARCHITECTURE.md) |
| Kernel + feature packs (plugin model) | [CODESYS_PLUGINS.md](CODESYS_PLUGINS.md) |

### Servo tuning

| Workflow | Doc |
|----------|-----|
| Manual zone ladder | [SERVO_TUNING.md](SERVO_TUNING.md) |
| Clipboard → LLM | [SEMI_AUTO_TUNING.md](SEMI_AUTO_TUNING.md) · [SERVO_TUNING_LLM.md](SERVO_TUNING_LLM.md) |
| One-click per axis | [ONE_CLICK_TUNING.md](ONE_CLICK_TUNING.md) |
| Inertia panel (WIP) | [GRAPHICAL_INERTIA_TUNE.md](GRAPHICAL_INERTIA_TUNE.md) |
| SDO map / APPLY path | [A6_TUNING.md](A6_TUNING.md) |
| Example tuning G-code | [TUNING_PROGRAMS.md](TUNING_PROGRAMS.md) |
| Signal logging | [SIGNAL_LOGGING.md](SIGNAL_LOGGING.md) |

---

## Custom Probe Basic tabs

Probe Basic loads **every** folder under `probe_basic/user_tabs/`. This machine ships:

| Tab folder | Purpose | Doc |
|------------|---------|-----|
| `servo_tuner/` | A6 SDO read/write, FERR plot, semi-auto + one-click tune | [A6_TUNING.md](A6_TUNING.md) |
| `signal_monitor/` | Multi-channel HAL CSV logging + live plots | [SIGNAL_LOGGING.md](SIGNAL_LOGGING.md) |
| `laser_setter/` | Kexin DS-5V-M diameter / beam cal UI | [LASER_TOOL_SETTER.md](LASER_TOOL_SETTER.md) |
| `template_*` | Upstream QtPyVCP scaffolding (safe to ignore) | — |

After switching git branches, delete leftover tab folders that lack a matching
`{name}/{name}.py` — see [README § branch switching](../README.md#dev-notes-switching-feature-branches).

---

## Config file map

| Path | Role |
|------|------|
| `ethercat_mill.ini` | Main INI |
| `ethercat_loadusr.hal` | `lcec_conf` once (TWOPASS-safe) |
| `ethercat_mill.hal` | Joints, CiA 402, limits, probe mux |
| `ethercat-conf.xml` | EtherCAT slaves + fault-window SDOs |
| `custom.hal` | VFD Modbus, at-speed delay, faults |
| `probe_basic/` | UI, macros, tool table, custom tabs |
| `post-processor/linuxcnc-djr.cps` | Fusion post |
| `docs/reference/` | Vendor PDFs / worksheets (H100, Sigma II calculator) |

---

## External sources we leaned on

| Source | What we borrowed |
|--------|------------------|
| [TooTall18T/tool_length_probe](https://github.com/TooTall18T/tool_length_probe) | M600 flow, `tool_touch_off.ngc`, setter teach |
| [kcjengr/probe_basic](https://github.com/kcjengr/probe_basic) | UI shell, probe routines |
| [linuxcnc-ethercat](https://github.com/linuxcnc-ethercat/linuxcnc-ethercat) | `lcec` + CiA 402 patterns |
| [kalico sota-motion](https://github.com/dderg/kalico/tree/sota-motion) | SDO-based servo tuning approach |
| [LinuxCNC docs](https://linuxcnc.org/docs/html/) | INI/HAL/remap reference |

We do not claim these integrations are the only correct approach.

---

## All guides (alphabetical)

| Doc | Covers |
|-----|--------|
| [A6_TUNING.md](A6_TUNING.md) | A6 SDO map, Servo Tuning tab, 6065/6066 windows |
| [CODESYS_ARCHITECTURE.md](CODESYS_ARCHITECTURE.md) | CODESYS SoftMotion + Vue browser HMI architecture and program map |
| [CODESYS_PLUGINS.md](CODESYS_PLUGINS.md) | Base kernel + independent feature packs (manifest, mux sockets) |
| [DEVIATIONS.md](DEVIATIONS.md) | Differences vs stock LinuxCNC / Probe Basic |
| [GETTING_STARTED.md](GETTING_STARTED.md) | Zero-to-hero bring-up path |
| [GRAPHICAL_INERTIA_TUNE.md](GRAPHICAL_INERTIA_TUNE.md) | Inertia identification panel (WIP) |
| [INSTALL_SERVO_TUNING.md](INSTALL_SERVO_TUNING.md) | Drop tuning tabs onto another mill |
| [INSTALL_TOOL_CHANGE.md](INSTALL_TOOL_CHANGE.md) | Copy M600 toolsetter integration |
| [LASER_TOOL_SETTER.md](LASER_TOOL_SETTER.md) | Laser diameter, wiring, HAL mux |
| [ONE_CLICK_TUNING.md](ONE_CLICK_TUNING.md) | Automated per-axis gain ladder |
| [PROBE_BASIC_UI.md](PROBE_BASIC_UI.md) | SET Z DRO, abort dialog, postgui HAL |
| [PYTHON_PACKAGES.md](PYTHON_PACKAGES.md) | Optional Python deps for plots / FFT |
| [SEMI_AUTO_TUNING.md](SEMI_AUTO_TUNING.md) | Clipboard → LLM tuning loop |
| [SEMI_AUTO_TUNING_SCOPE.md](SEMI_AUTO_TUNING_SCOPE.md) | Semi-auto design notes |
| [SERVO_TUNING.md](SERVO_TUNING.md) | Manual gain zone ladder |
| [SERVO_TUNING_LLM.md](SERVO_TUNING_LLM.md) | LLM tuning playbook |
| [SIGNAL_LOGGING.md](SIGNAL_LOGGING.md) | Logging tab, `signals.json` |
| [TOOLSETTER.md](TOOLSETTER.md) | M600, touch probe routing, Fusion post |
| [TUNING_PROGRAMS.md](TUNING_PROGRAMS.md) | Example frozen tuning / test G-code |
