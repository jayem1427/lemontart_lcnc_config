# Docs

Everything about this mill's config, one topic per page. New here? Read them
in this order: **SETUP → HARDWARE → CONFIG_TOUR**, then whichever feature
you're working on.

## Getting started

| Page | What's in it |
|------|--------------|
| [SETUP.md](SETUP.md) | Installing the software, getting the config, step-by-step bring-up, EtherCAT driver choice (native vs generic) and realtime timing |
| [HARDWARE.md](HARDWARE.md) | Parts list, wiring, drive inputs, RS-485, E-stop |
| [CONFIG_TOUR.md](CONFIG_TOUR.md) | How the files fit together, homing, following error, differences from stock |
| [DRIVE_HOMING.md](DRIVE_HOMING.md) | Drive-internal homing (hard stop + Z pulse) via upstream `cia402_homecomp` + lcec 1.49, its test plan. **Branch `dev-drive-homing`, untested on the machine** |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Symptoms and their real causes |

## Features

| Page | What's in it |
|------|--------------|
| [TOOL_CHANGE.md](TOOL_CHANGE.md) | `M600` tool change, tool length, probe routing, Stop behaviour |
| [CAM.md](CAM.md) | The Fusion 360 post |
| [VISE_STOP.md](VISE_STOP.md) | Self-centering vise: WCS fixed at the vise center, a pin in the spindle as the stop |
| [LASER_TOOL_SETTER.md](LASER_TOOL_SETTER.md) | Tool diameter with a laser beam sensor |
| [SPINDLE.md](SPINDLE.md) | H100 VFD over Modbus |
| [COOLANT.md](COOLANT.md) | Microject MQL coolant, `M201`/`M202`, the MQL tab |
| [MODBUS.md](MODBUS.md) | mb2hal basics, adapters, bench testing |
| [PROBE_BASIC_UI.md](PROBE_BASIC_UI.md) | UI settings, SET Z, ABORT dialog, custom tabs, macro fixes |
| [SIGNAL_LOGGING.md](SIGNAL_LOGGING.md) | Logging HAL signals to CSV (and why it's not a 1 kHz recorder) |

## Servo tuning

| Page | What's in it |
|------|--------------|
| [SERVO_TUNING.md](SERVO_TUNING.md) | Start here: the tab, the three ways to tune, current gains and results, test programs, the reversal/clunk test, presets, installing on another machine |
| [ONE_CLICK_TUNING.md](ONE_CLICK_TUNING.md) | How the automatic tuner works and how to read its journal |
| [INERTIA_TUNING.md](INERTIA_TUNING.md) | Measuring the inertia ratio (work in progress) |
| [SERVO_TUNING_LLM.md](SERVO_TUNING_LLM.md) | Prompt to give an AI for tuning help |
| [SERVO_SWAP.md](SERVO_SWAP.md) | Using a different servo drive (e.g. Leadshine EL8-EC): what's A6-specific and what to replace |

## For AI assistants (and the curious)

| Page | What's in it |
|------|--------------|
| [../CLAUDE.md](../CLAUDE.md) | Working brief: safety rules, machine facts, open issues |
| [agent-skills/](agent-skills/) | Checklists for editing HAL and G-code macros without breaking startup |
| [CURSOR_HISTORY.md](CURSOR_HISTORY.md) | How this config evolved, what failed, what was abandoned |
| [../agent/README.md](../agent/README.md) | Agent pack: skills + docs bundle, rebuilt with `scripts/build_agent_release.py` |

## Reference material

- [reference/h100 manual.pdf](reference/h100%20manual.pdf): H100 VFD manual (Modbus registers, fault codes)
- [reference/Sigma II Parameter Calculator Rev 2.42.xls](reference/): Yaskawa worksheet used to cross-check inertia
- [../probe_basic/subroutines/metrology/README.md](../probe_basic/subroutines/metrology/README.md): Z repeatability test macros
- Upstream: [LinuxCNC docs](https://linuxcnc.org/docs/html/) · [Probe Basic](https://github.com/kcjengr/probe_basic) · [linuxcnc-ethercat](https://github.com/linuxcnc-ethercat/linuxcnc-ethercat) · [mb2hal](https://linuxcnc.org/docs/html/drivers/mb2hal.html)
