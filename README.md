# lemontart_lcnc_config

LinuxCNC configuration for a **Lemontart**-class EtherCAT mill:

- 4× Stepperonline A6 Servos (400W for xyz, 100W for A)
- **Probe Basic** (QtPyVCP) UI
- **XHC WHB04B-6** wireless pendant, with low-pass filter for smooth jogging
- **H100 VFD** over Modbus RTU via `mb2hal` (`h100.mb2hal`)

Please treat this repo as a reference, not a guaranteed drop-in. Expect to adjust EtherCAT XML, scales, limits, serial port, and homing before cutting metal.

If you want to really understand how LinuxCNC works, would HIGHLY recommend starting from a default axis example, and adding features one at a time. Probe Basic will likely give you a headache if you jump straight to it. A road map might look like:

- getting linuxcnc installed
- play around with some of the simulation configs, get familiar in the UI
- copy a built-in config to start as your baseline
- adjusting hal and ini files for motor scaling and direction
- getting linuxcnc-ethercat installed and configured (see my xml example)
- getting familiar within axis, learn how to watch pin states, learn how to jog
- configure homing properly, test carefully
- servo tuning in the StepperOnline software
- once you confirm that's all working, then duplicate your config to convert it to Probe Basic

## Requirements

- LinuxCNC built with **EtherCAT / LCEC** (`lcec`, `lcec_conf`)
- **Probe Basic** / QtPyVCP stack matching your LinuxCNC version
- Optional: `mb2hal` for the VFD

## Quick start

1. Install linuxcnc: https://linuxcnc.org/downloads/
2. Install linuxcnc-ethercat: https://github.com/linuxcnc-ethercat/linuxcnc-ethercat.
3. Find your corresponding ethernet address using the "ip a" command in terminal.
5. Edit etc/ethercat.xml so that ethernet address matches the result of previous command.
6. Copy a default config from the LinuxCNC wizard.
7. Edit .hal files and .ini files to get motors and homing working. Use my examples as reference.
8. Paste and edit **`ethercat-conf.xml`** from this repo so slave types, positions, and PDOs match your chain (and your A6 drive tuning).
9. Paste and edit **`h100.mb2hal`** — set `SERIAL_PORT` (often `/dev/ttyUSB0`) and confirm register addresses match your VFD manual.

Note: **`PROGRAM_PREFIX`** points at `nc_files/` (next to the INI). Put your G-code there or change it in `ethercat_mill.ini`.

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

Many of these files are connected to eachother. Using a tool like Cursor or Claude Code will absolutely make your life easier since you can expand the context window to multiple files, but please always verify any changes that AI makes. Add testable features one-at-a-time, and verify they work before proceeding forward.

## Current machine behavior (captured config)

- Manual tool changes are **retract-only**: `TOOL_CHANGE_QUILL_UP = 1` and no `TOOL_CHANGE_POSITION`, so LinuxCNC does not command an X/Y move for tool change.
- Home/limit inputs below are wired active-low NC and inverted in HAL (`not.*`).
- Touch probe (Slave 1 DI5) and contact toolsetter (Slave 2 DI5 / DB15 pin 11) are NC and OR'd together to `motion.probe-input`.
- Software E-stop is wired NC on Slave 3 DI1 / DB15 pin 10 and gates `iocontrol.0.emc-enable-in`.

| Drive / EtherCAT slave | DI input | Signal use |
|------------------------|----------|------------|
| Slave 0 (X/Y drive IO) | DI4 | X home (`joint.0.home-sw-in`) |
| Slave 0 (X/Y drive IO) | DI1 | X limit chain (`joint.0.neg-lim-sw-in`, `joint.0.pos-lim-sw-in`) |
| Slave 0 (X/Y drive IO) | DI5 | Y home (`joint.1.home-sw-in`) |
| Slave 0 (X/Y drive IO) | DI2 | Y limit chain (`joint.1.neg-lim-sw-in`, `joint.1.pos-lim-sw-in`) |
| Slave 1 (Z/probe IO) | DI4 | Z home at +Z (`joint.2.home-sw-in`) |
| Slave 2 (Z/aux IO) | DI2 | Z negative limit (`joint.2.neg-lim-sw-in`) |
| Slave 1 (Z/probe IO) | DI5 | Touch probe (`touch-probe-in` -> `motion.probe-input`) |
| Slave 2 (Z/aux IO) | DI5 / DB15 pin 11 | Contact toolsetter (`toolsetter-in` -> `motion.probe-input`) |
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

## What was left out of git, but is helpful to keep in the config


Large manual PDFs, simulation logs, QtPyVCP pickles, and personal scratch notes. Any documentation or reference is great to keep in the config. This will be helpful for you, as well as an AI tool as long as you explicitly tell it to rely on documentation you've uploaded to your working directory.

## Safety

Verify estop, drives, and spindle before running any programs. Review **breakout** comments in `ethercat_mill.ini` if you are still on the bench.
