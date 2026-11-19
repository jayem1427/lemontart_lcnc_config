# Lemontart LinuxCNC config

This is the complete LinuxCNC config for my Lemontart CNC mill: four EtherCAT
servos, a Probe Basic UI, a Modbus spindle, two tool setters, MQL coolant, and
a servo tuning tab I built along the way.

It is a **real machine config**, not a product. It runs my mill every day, but
your machine will differ. Plan on editing the EtherCAT chain, scales, limits,
serial ports and homing before anything moves. You can copy the whole thing,
lift one feature, or just read it to see how something is wired.

## What's on the machine

| Area | Hardware | How it's driven |
|------|----------|-----------------|
| Motion | 4× StepperOnline A6-EC servos (XYZ 400 W, A 100 W) | EtherCAT (IgH master + linuxcnc-ethercat) |
| UI | [Probe Basic](https://github.com/kcjengr/probe_basic) 0.6.6 | QtPyVCP, plus four custom tabs |
| Spindle | H100 VFD, 24 000 RPM | Modbus RTU over USB-RS485 (`mb2hal`) |
| Coolant | Dan Mills Microject MQL injector | Modbus RTU over a second USB-RS485 |
| Tool length | Contact tool setter | `M600` macro (TooTall18T-style) |
| Tool diameter | Kexin DS-5V-M laser beam sensor | Laser Setter tab + G38 macros |
| Work probe | Touch probe as tool T99 | Shares the probe input with the setter |
| Pendant | XHC WHB04B-6 wireless | `xhc-whb04b-6` driver |
| CAM | Fusion 360 | Custom post in `post-processor/` |

## Where to start

| You want to… | Read |
|--------------|------|
| Build a machine like this from scratch | [docs/SETUP.md](docs/SETUP.md), then [docs/HARDWARE.md](docs/HARDWARE.md) |
| Understand how the files fit together | [docs/CONFIG_TOUR.md](docs/CONFIG_TOUR.md) |
| Copy one feature to your own mill | That feature's page below. Each one has a "copying this to another machine" section |
| Fix something that broke | [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) |

**Feature guides**

| Feature | Page |
|---------|------|
| Tool changes and length probing (`M600`) | [TOOL_CHANGE.md](docs/TOOL_CHANGE.md) |
| Fusion 360 post processor | [CAM.md](docs/CAM.md) |
| Laser diameter measurement | [LASER_TOOL_SETTER.md](docs/LASER_TOOL_SETTER.md) |
| Spindle (H100 VFD) | [SPINDLE.md](docs/SPINDLE.md) |
| MQL coolant (Microject) | [COOLANT.md](docs/COOLANT.md) |
| Modbus basics for both of the above | [MODBUS.md](docs/MODBUS.md) |
| Probe Basic changes and custom tabs | [PROBE_BASIC_UI.md](docs/PROBE_BASIC_UI.md) |
| Servo tuning (manual, AI-assisted, one-click) | [SERVO_TUNING.md](docs/SERVO_TUNING.md) |
| Logging HAL signals to CSV | [SIGNAL_LOGGING.md](docs/SIGNAL_LOGGING.md) |

The full list is in [docs/README.md](docs/README.md).

## Before you copy anything

A few things in this repo are specific to my machine and **will** be wrong on
yours:

- **The EtherCAT NIC** (`/etc/ethercat.conf`) and the slave list in `ethercat-conf.xml`.
- **Scales, limits and homing** in `ethercat_mill.ini`, and the switch wiring in `ethercat_mill.hal`.
- **Serial ports** in `h100.mb2hal` and `microject.mb2hal` (they use my adapters' `/dev/serial/by-id/` names).
- **`PROGRAM_PREFIX`** in the INI points at my G-code folder.
- **The trajectory planner.** This branch (`dev-jerk-testing`) uses an experimental jerk-limited planner build. On stock LinuxCNC 2.9 you need to comment out a few INI lines first. See [SETUP.md](docs/SETUP.md#stock-linuxcnc-vs-the-tpnext-build).

Bring the machine up **one subsystem at a time**, in the order in
[SETUP.md](docs/SETUP.md). Every time I skipped ahead, I lost a weekend.

## Repo layout

```
ethercat_mill.ini        main INI (start here)
ethercat_loadusr.hal     loads the EtherCAT config once
ethercat_mill.hal        joints, homing/limits, probe routing, E-stop
custom.hal               spindle (VFD), servo telemetry for tuning
coolant.hal              MQL coolant
xhc-whb04b-6.hal         pendant
probe_beep.hal           beep when a probe or the laser trips (optional)
ethercat-conf.xml        EtherCAT slaves, PDOs, drive startup settings
h100.mb2hal              spindle Modbus map
microject.mb2hal         coolant Modbus map
probe_basic/             UI config, macros (subroutines/), custom tabs, tool table
post-processor/          Fusion 360 post
config/                  tuning presets, logging channel list
scripts/                 helper scripts (beep, tuning CLI, plotting)
docs/                    everything you're reading
launch.sh                start LinuxCNC with this config
```

## Using an AI assistant with this repo

Most of this config was built with AI coding assistants, and the docs are
written so they can be handed to one. Some useful starting points:

- [CLAUDE.md](CLAUDE.md) is the working brief I give my own assistant: safety
  rules (each one learned from a real incident), machine facts and open issues.
- [docs/agent-skills/](docs/agent-skills/) has two short checklists, one for
  editing HAL and one for G-code macros. They cover the mistakes that most
  often stop LinuxCNC from starting.
- [docs/CURSOR_HISTORY.md](docs/CURSOR_HISTORY.md) is a month-by-month record
  of what was tried, what failed and why. Point your assistant at it before it
  suggests something I already abandoned.
- [docs/SERVO_TUNING_LLM.md](docs/SERVO_TUNING_LLM.md) is a prompt for
  AI-assisted servo tuning.
- [agent/README.md](agent/README.md) describes a self-contained "agent pack"
  (two skills plus a copy of these docs, built into `release/lemontart-agent/`)
  for assistants that can read files but can't see this repo.

Give it several of the config files at once. They reference each other heavily,
and most mistakes come from editing one without the others.

## Safety

Test E-stop, drive enables and the spindle on the bench before you cut. Comments
marked `REVERT:` or `BREAKOUT OFF` in the config are temporary shortcuts and are
**not** safe for unattended running. The INI following-error limits are
deliberately loose (the drives enforce the real limit), so read
[CONFIG_TOUR.md](docs/CONFIG_TOUR.md#following-error) before you rely on them.

## Credits

| Project | What came from it |
|---------|-------------------|
| [TooTall18T/tool_length_probe](https://github.com/TooTall18T/tool_length_probe) | `M600` tool change and setter macros |
| [kcjengr/probe_basic](https://github.com/kcjengr/probe_basic) | The UI and probing routines |
| [linuxcnc-ethercat](https://github.com/linuxcnc-ethercat/linuxcnc-ethercat) | The EtherCAT HAL driver |
| [kalico sota-motion](https://github.com/dderg/kalico/tree/sota-motion) | Tuning A6 drives over SDO |
| Dan Mills | The Microject MQL controller |

Forks and PRs are welcome. If you adapt this, write down *why* you changed
something, not just what. That's the part future-you forgets.
