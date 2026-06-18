# lemontart_lcnc_config

LinuxCNC configuration for a **Lemontart**-class EtherCAT mill:

- 4× Stepperonline A6 Servos (400W for xyz, 100W for A)
- **Probe Basic** (QtPyVCP) UI
- **XHC WHB04B-6** wireless pendant
- **H100 VFD** over Modbus RTU via `mb2hal` (`h100.mb2hal`)

This is a working bench reference, not a guaranteed drop-in. Expect to adjust EtherCAT XML, scales, limits, serial port, and homing before cutting metal.

## Requirements

- LinuxCNC built with **EtherCAT / LCEC** (`lcec`, `lcec_conf`)
- **Probe Basic** / QtPyVCP stack matching your LinuxCNC version
- Optional: `mb2hal` for the VFD

## Quick start

1. Clone this repository to a path of your choice, e.g. `~/linuxcnc/configs/lemontart_lcnc_config`.
2. Edit **`ethercat-conf.xml`** so slave types, positions, and PDOs match your chain (and your A6 drive tuning).
3. Edit **`h100.mb2hal`** — set `SERIAL_PORT` (often `/dev/ttyUSB0`) and confirm register addresses match your VFD manual.

**`PROGRAM_PREFIX`** points at `nc_files/` (next to the INI). Put your G-code there or change it in `ethercat_mill.ini`.

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
| `probe_basic/` | Probe Basic YAML, postgui HAL, DROs, macros, `tool.tbl` |
| `nc_files/` | Default program search path |

## Current machine behavior (captured config)

- Manual tool changes are **retract-only**: `TOOL_CHANGE_QUILL_UP = 1` and no `TOOL_CHANGE_POSITION`, so LinuxCNC does not command an X/Y move for tool change.
- Inputs below are wired as active-low NC and inverted in HAL (`not.*`) before going to joint/home/limit pins.

| Drive / EtherCAT slave | DI input | Signal use |
|------------------------|----------|------------|
| Slave 0 (X/Y drive IO) | DI4 | X home (`joint.0.home-sw-in`) |
| Slave 0 (X/Y drive IO) | DI1 | X limit chain (`joint.0.neg-lim-sw-in`, `joint.0.pos-lim-sw-in`) |
| Slave 0 (X/Y drive IO) | DI5 | Y home (`joint.1.home-sw-in`) |
| Slave 0 (X/Y drive IO) | DI2 | Y limit chain (`joint.1.neg-lim-sw-in`, `joint.1.pos-lim-sw-in`) |
| Slave 1 (Z/probe IO) | DI4 | Z home at +Z (`joint.2.home-sw-in`) |
| Slave 2 (Z/aux IO) | DI2 | Z negative limit (`joint.2.neg-lim-sw-in`) |
| Slave 1 (Z/probe IO) | DI5 | Touch probe (`motion.probe-input`) |
| Slave 3 (A axis IO) | DI3 (planned) | A home (currently commented out in HAL) |

## What was left out of git 

Large servo manual PDFs, simulation logs, QtPyVCP pickles, duplicate `user_dro_display/` at repo root (unused — the INI uses `probe_basic/user_dro_display/`), and personal scratch notes. Add your own vendor PDFs locally.

## Safety

Verify estop, drives, and spindle before running any programs. Review **breakout** comments in `ethercat_mill.ini` if you are still on the bench.
