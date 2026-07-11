# Install: Servo Tuning + Logging

How to add this repo’s **Servo Tuning** tab, **Logging** tab, and A6 drive FERR telemetry to another Probe Basic / LinuxCNC machine.

Probe Basic does **not** use pip plugins for UI. Custom tabs are **drop-in folders** under `USER_TABS_PATH`. See also **[A6_TUNING.md](A6_TUNING.md)** (tuning workflow) and **[SIGNAL_LOGGING.md](SIGNAL_LOGGING.md)** (Logging tab details).

---

## What you get

| Piece | Role |
|-------|------|
| **Servo Tuning** tab | Read/edit A6 C00/C01 (+ 6065/6066) over EtherCAT SDO; live 60F4 FERR plot |
| **Logging** tab | CSV + live plots of FERR / DRIVE / TORQUE / VEL |
| HAL `tune-*` pins | Scale drive PDOs (6077 / 606C / 60F4) for plots |
| Presets | Per-axis JSON under `config/tuning/presets/` |

**Not a plugin package.** Copy files into the machine config tree and wire INI/HAL/XML.

---

## Prerequisites

- LinuxCNC with **lcec** EtherCAT and Probe Basic (same stack as this mill)
- A6-EC (or compatible) drives with CiA objects you intend to use
- Passwordless `sudo` for `ethercat` CLI **or** run LinuxCNC as a user that can talk to EtherCAT
- Optional plots: `sudo apt install python3-pyqtgraph` (see **[PYTHON_PACKAGES.md](PYTHON_PACKAGES.md)**)

---

## 1. Copy files

From this repo into your machine config (paths relative to the config root, e.g. `.../configs/ethercat_mill/`):

```text
probe_basic/user_tabs/servo_tuner/          # Servo Tuning tab
probe_basic/user_tabs/signal_monitor/       # Logging tab (optional but recommended)
probe_basic/python/a6_servo_tune.py
probe_basic/python/hal_signal_logger.py
probe_basic/python/signal_plot_widget.py
config/tuning/presets/                      # or start empty and SAVE from the tab
config/logging/signals.json
nc_files/*_tuning.ngc                       # optional oscillation programs
```

Remove leftover tab folders you do not want — Probe Basic loads **every** subfolder under `USER_TABS_PATH`:

```bash
ls probe_basic/user_tabs/
# Keep: servo_tuner, signal_monitor (and templates only if you want them)
# Remove e.g. laser_setter from other branches
```

---

## 2. INI

In `[DISPLAY]`:

```ini
USER_TABS_PATH = probe_basic/user_tabs/
CONFIG_FILE = probe_basic/custom_config.yml
```

No per-tab YAML registration is required. Restart LinuxCNC after adding folders.

---

## 3. EtherCAT XML (`ethercat-conf.xml`)

Per slave, map the PDOs used by logging / FERR (adjust slave layout to your machine):

- **60F4** → `ferr-fb` (s32) — drive following error
- **6077** → torque feedback (if you want TORQUE plots)
- **606C** → velocity feedback (if you want VEL plots)

Optional startup SDOs (RAM until stored in the drive): C00/C01 gains, **6065** / **6066**. Copy the blocks from this repo’s `ethercat-conf.xml` and edit counts for your SCALE.

---

## 4. HAL (`custom.hal`)

Port the telemetry block that builds:

- `tune-torque.N.out`
- `tune-velocity.N.out`
- `tune-drive-ferr.N.out`

from `lcec.0.N.*` via `conv-s32-float`, `div2` / `mult2`, and `scale` components on **servo-thread**.

Match joint SCALE when converting 60F4 counts → mm/deg. Pin names in `config/logging/signals.json` must match what you create.

**Do not** feed `tune-drive-ferr.*` into `joint.N.f-error` / LinuxCNC FERROR.

---

## 5. Per-machine edits in Python

Edit `AXES` in `probe_basic/python/a6_servo_tune.py`:

| Field | Meaning |
|-------|---------|
| `joint` / `slave` | LinuxCNC joint index and EtherCAT slave |
| `linear` | `True` → mm, `False` → deg |
| `scale` | counts per mm (or per deg) — must match INI `SCALE` |

Wrong SCALE makes FERR mm/pulses and 6065 conversion wrong.

---

## 6. Smoke test

1. Start LinuxCNC — no HAL `loadrt` errors.
2. Probe Basic shows **SERVO TUNING** and **SIGNAL LOGGING** tabs.
3. Servo Tuning → **READ FROM DRIVE** → Current column fills (not all `READ FAIL`).
4. Servo Tuning → **START PLOT** → jog or run a tuning NGC → FERR trace moves (no CSV from this tab).
5. `halcmd getp tune-drive-ferr.0.out` changes when you jog (if PDO/HAL wired).
6. Logging → **START LIVE** → plot updates; optional CSV under `logs/signals/`.

---

## Safety notes (APPLY)

- APPLY writes **only SDOs that were successfully READ** (does not invent catalog defaults for failed reads).
- Read-only SDOs on this A6 firmware (C01.10 speed FB filter, C01.38 gain switchover) are **skipped** — they no longer abort the whole APPLY batch.
- SDO writes are **RAM** until you store them in the drive EEPROM (vendor tool).
- Does **not** modify INI / HAL / XML on disk by itself.
- Prefer READ → edit Pending → **APPLY TO DRIVE**. Use preset **LOAD** for known-good sets, then APPLY.
- Do **not** put C00/C01 loop gains in `ethercat-conf.xml` `sdoConfig` — lcec re-downloads them on every bus claim and wipes bench tuning. Keep only mode/limits (6060/6065/6066) in XML if needed. See **[A6_TUNING.md](A6_TUNING.md)**.

---

## Sampling rate (Logging)

This mill uses `SERVO_PERIOD = 1000000` ns → **1 kHz** servo thread. HAL pins update once per servo period.

You do **not** need to log at 2 kHz for Nyquist. See **[Sample rate and Nyquist](SIGNAL_LOGGING.md#sample-rate-and-nyquist)** in SIGNAL_LOGGING.md.

Default Logging rate here is **1000 Hz** (UI allows 25–1000 Hz) via in-process `hal.get_value`. Lower the rate if CSV size or userspace load is an issue.
