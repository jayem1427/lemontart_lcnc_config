# lemontart_lcnc_config

LinuxCNC configuration for a **Lemontart**-class EtherCAT mill:

- 4× closed-loop steppers (Leadshine A6-EC CiA 402 on EtherCAT-Linux)
- **Probe Basic** (QtPyVCP) UI
- **XHC WHB04B-6** wireless pendant
- **Huanyang H100-class VFD** over Modbus RTU via `mb2hal` (`h100.mb2hal`)

This is a working bench reference, not a guaranteed drop-in. Expect to adjust EtherCAT XML, scales, limits, serial port, and homing before cutting metal.

## Requirements

- LinuxCNC built with **EtherCAT / LCEC** (`lcec`, `lcec_conf`)
- **Probe Basic** / QtPyVCP stack matching your LinuxCNC version
- Optional: `mb2hal` for the VFD; disable Modbus blocks in `custom.hal` if you run open-loop spindle

## Quick start

1. Clone this repository to a path of your choice, e.g. `~/linuxcnc/configs/lemontart_lcnc_config`.
2. Edit **`ethercat-conf.xml`** so slave types, positions, and PDOs match your chain (and your A6 drive tuning).
3. Edit **`h100.mb2hal`** — set `SERIAL_PORT` (often `/dev/ttyUSB0`) and confirm register addresses match your VFD manual.
4. Optionally edit **`Launch_Mill.desktop`**: set `Path=` to the **absolute** directory that contains `ethercat_mill.ini` (see comments in that file). Alternatively run **`./launch.sh`** from the repo root.
5. Launch:
   ```bash
   ./launch.sh
   ```
   or from the config directory:
   ```bash
   linuxcnc ethercat_mill.ini
   ```

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

## What was left out of git on purpose

Large servo manual PDFs, simulation logs, QtPyVCP pickles, duplicate `user_dro_display/` at repo root (unused — the INI uses `probe_basic/user_dro_display/`), and personal scratch notes. Add your own vendor PDFs locally.

## Safety

Verify estop, drives, and spindle before running any programs. Review **breakout** comments in `ethercat_mill.ini` (wide limits / no real homing motion) if you are still on the bench.
