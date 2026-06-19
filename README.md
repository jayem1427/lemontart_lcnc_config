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

## Spindle at-speed delay (`feature_spindle-delay`)

Experimental HAL-only change in `custom.hal` that adds a fixed settle buffer **after** the VFD feedback already matches the commanded RPM. No Python remaps, G-code changes, or post-processor edits.

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

Restart LinuxCNC after switching branches (HAL is loaded at startup). While running:

```bash
halcmd watchpin spindle-at-speed-raw    # goes true when within 50 RPM
halcmd watchpin spindle.0.at-speed      # goes true ~5 s later
```

MDI: `M3 S2000`, then a small `G1` — the move should wait until `spindle.0.at-speed` is true.

### Branch workflow

- **Try it:** `git checkout feature_spindle-delay`
- **Revert:** `git checkout main` (direct `near.0.out` → `spindle.0.at-speed`, no extra delay)

## What was left out of git on purpose

Large servo manual PDFs, simulation logs, QtPyVCP pickles, duplicate `user_dro_display/` at repo root (unused — the INI uses `probe_basic/user_dro_display/`), and personal scratch notes. Add your own vendor PDFs locally.

## Safety

Verify estop, drives, and spindle before running any programs. Review **breakout** comments in `ethercat_mill.ini` (wide limits / no real homing motion) if you are still on the bench.
