# A6-EC servo tuning (LinuxCNC / lcec)

Conservative drive loop settings pushed over EtherCAT SDO at startup, plus a **Servo Tuning** Probe Basic tab. **LinuxCNC `joint.N.f-error` / INI `FERROR` are left alone** — plot the drive’s own following error (CiA **60F4**) as a separate Logging signal (**DRIVE**).

Based on the [kalico sota-motion](https://github.com/dderg/kalico/tree/sota-motion) approach (SDO object dictionary instead of StepperOnline GUI). This branch builds on **`cursor/signal-logging-framework-0633`**.

---

## Status — parked (pick up later)

**Branch:** `cursor/a6-tuning-ferror-comp-70f6`  
**Intent of this pin:** tooling and docs are in place; real gain tuning is **not finished**. Come back when you want to spend a session on loop gains with Logging + `*_tuning.ngc`.

### Resume checklist

```bash
cd /home/jon/linuxcnc/configs/ethercat_mill
git checkout cursor/a6-tuning-ferror-comp-70f6
# Clear leftover user tabs from other feature branches (Probe Basic loads every folder):
rm -rf probe_basic/user_tabs/laser_setter
ls probe_basic/user_tabs/   # expect: signal_monitor, servo_tuner, templates
./launch.sh
```

Then: **Servo Tuning** → watch live **DRIVE FERR** (toggle **MM/DEG** vs **PULSES**) → READ → edit Pending → APPLY; optionally also **Logging** → **DRIVE** → run `nc_files/x_tuning.ngc`.

### What is done

| Item | State |
|------|--------|
| Drive 60F4 PDO → `tune-drive-ferr.*` | Working — plot as **DRIVE** |
| Torque / velocity telemetry | Working |
| Servo Tuning GUI (read / apply / revert / presets) | Working |
| Live drive FERR plot on Servo Tuning (pulses + mm/deg) | Working |
| Full C00/C01 param table (rigidity, 1st/2nd gains, FF, advanced) | Working |
| SDO `--type` on ethercat CLI | Fixed (`-t uint16` / `uint32`) |
| Startup C00/C01 SDOs in `ethercat-conf.xml` | Present (RAM only) |
| LinuxCNC `motor-pos-fb` | **Direct** — no lag compensation |

### What we deliberately abandoned

**HAL pipeline-delay / “ghost lag” compensation** (`servo_tuning.hal`) was removed. It advanced `motor-pos-fb` by `vel_cmd × ferr-lag` so host `joint.f-error` looked smaller. That couples tuning into LinuxCNC FERROR / soft faults and caused HAL load headaches (`count=` vs `names=` on `mult2`, double-linked `motor-pos-cmd`). **Do not bring it back** unless you have a strong reason and keep it off the FERROR path.

### Machine tweaks made while debugging (still on this branch)

These are operational, not “final tuned gains”:

| Change | Why | Where |
|--------|-----|--------|
| Drive **6065** XYZ **1.0 mm**, A **1.0°**; **6066** **250 ms** | 0.1 mm Er47.0 amp faults during moves | `ethercat-conf.xml`, presets, `a6_servo_tune` defaults |
| Z soft **MAX_LIMIT = 50 mm** | Unhomed Z ~13 mm sat above old 3.048 mm soft max → jog blocked | `ethercat_mill.ini` `[AXIS_Z]` / `[JOINT_2]` |
| Z home slower + looser FERROR | Vertical axis f-error spikes at home search/latch | `HOME_SEARCH_VEL=10`, latch 0.5, `FERROR=5` / `MIN_FERROR=2` |

Tighten 6065 / Z soft max again after loops are stable if you want earlier protection.

### Open / next when you return

1. Per-axis gain ladder with **DRIVE** plots (start C01.01); save presets when happy.
2. Decide whether Z soft max stays at 50 mm or returns near home (~3 mm) after reliable HOME ALL.
3. Optional: inertia ratio (C00.06) after a real load measurement.
4. Optional: feedforward / carrier / system ID (Tier 2 — not started).
5. Confirm Z home speeds feel right under gravity; adjust if still noisy.

### Related branches

| Branch | Role |
|--------|------|
| `cursor/signal-logging-framework-0633` | Logging tab / HAL telemetry baseline |
| `cursor/laser-setter-1afc` | Laser tool setter UI (remove its tab folder when on this branch) |
| `cursor/a6-tuning-ferror-comp-70f6` | **This pin** — A6 SDO + Servo Tuning + drive FERR |

See also branch-switching notes in README when present; otherwise use the `rm -rf` lines in the resume checklist above.

---

## Design rule

| Signal | Source | Used for |
|--------|--------|----------|
| **DRIVE** (`tune-drive-ferr.N.out`) | A6 PDO **60F4** (counts → mm/deg) | Loop tuning plots — primary metric |
| **FERR** (`joint.N.f-error`) | LinuxCNC cmd − fb | Soft limits / faults only — **do not rewire** |

There is **no** HAL pipeline-delay / ghost-lag compensation. Rewiring `motor-pos-fb` to “fix” host lag was removed because it couples tuning into LinuxCNC following-error limits.

---

## What changes on boot

### Drive SDOs (`ethercat-conf.xml`)

Written once per slave when lcec claims the bus (RAM only — not EEPROM unless you explicitly store parameters).

| SDO | Panel param | Value | Meaning |
|-----|-------------|-------|---------|
| `0x2000.0x05` | C00.04 | 0 | Manual gain mode (disable auto/stiffness table) |
| `0x2000.0x07` | C00.06 | 100 | Load inertia ratio 100% — adjust after measurement |
| `0x2001.0x01` | C01.00 | 300 | Position loop gain **30.0 rad/s** (0.1 rad/s units) |
| `0x2001.0x02` | C01.01 | 200 | Speed loop gain **20.0 Hz** (0.1 Hz units) — primary noise lever |
| `0x2001.0x03` | C01.02 | 3184 | Speed integral **31.84 ms** (0.01 ms units) |
| `0x2001.0x31` | C01.30 | 1 | Adaptive notch filter (1st notch auto) |

Drive following-error trip (Er47.0) — loosened for bench tuning:

| SDO | Meaning | XYZ | A |
|-----|---------|-----|---|
| `6065h` | Max position deviation (counts) | 13107 ≈ **1.0 mm** | 364 ≈ **1.0°** |
| `6066h` | Fault persistence (ms) | **250** | **250** |

**Not configured here:** carrier frequency, velocity/torque feedforward (60B1/60B2), kalico-style system ID — see prior discussion for Tier 2+.

---

## Servo Tuning tab (Probe Basic GUI)

Open **Servo Tuning** in Probe Basic (loaded from `probe_basic/user_tabs/servo_tuner/`).

| Control | Action |
|---------|--------|
| **AXIS** | Select X / Y / Z / A (each EtherCAT slave) |
| **CURRENT ON DRIVE** | Live summary of last READ / APPLY values |
| Sliders + spinboxes | Edit C00/C01 gains, adaptive notch, drive 6065 limit |
| **READ FROM DRIVE** | Upload current SDOs into the form **and** store as REVERT baseline |
| **APPLY CHANGES** | Disable motors → write SDOs → re-enable; updates baseline |
| **REVERT** | Re-apply the last READ / APPLY baseline for this axis |
| **LOAD DEFAULT** | Fill form with built-in / XML defaults (not written until APPLY) |
| **AXIS PRESETS** | Save / load / delete JSON presets per axis |

Presets live under `config/tuning/presets/<axis>/*.json`. Shipped examples:

- `default` — matches `ethercat-conf.xml` startup values
- `soft` — C01.01 at 17.6 Hz for less ringing

**Typical workflow**

1. Open tab (auto-READ when EtherCAT is up) or press **READ FROM DRIVE**.
2. Note **CURRENT ON DRIVE** / baseline — that is what **REVERT** restores.
3. Adjust **Speed loop gain (C01.01)** first if you hear whine or see ringing.
4. **APPLY CHANGES** → switch to **Signal Logging** → select **DRIVE** → run `nc_files/x_tuning.ngc`.
5. If worse: **REVERT**. If better: **SAVE** a preset (e.g. `x_after_softening`).
6. Repeat per axis; Z and A can differ from X/Y.

Backend module: `probe_basic/python/a6_servo_tune.py` (also used by the tab).

### Revert paths

| Want | Do |
|------|----|
| Undo edits since last READ/APPLY | **REVERT** (writes baseline back to drive) |
| Known-good named set | Preset **LOAD + APPLY** (`default`, `soft`, or your save) |
| XML boot defaults in the form | **LOAD DEFAULT**, then **APPLY** if you want them on the drive |
| Full power-cycle reset | Power-cycle drives (RAM SDOs reload from `ethercat-conf.xml` at next LinuxCNC start) |

---

## Tuning workflow (with Logging tab)

1. Start LinuxCNC; confirm no HAL errors.
2. Open **Logging** → select **DRIVE** → **LOG NEXT PROGRAM** or **START LIVE**.
3. Run `nc_files/x_tuning.ngc` (or jog). Prefer **DRIVE** (60F4) over **FERR** for loop work.
4. Soften **C01.01** if ringing/whine persists (e.g. `C8 00` → `B0 00` for 17.6 Hz), or use the Servo Tuning tab.
5. Re-run the same move; use CSV in `logs/signals/` to compare peak drive FERR and torque.

### Suggested gain ladder (C01.01 speed gain, u16 hex)

| Step | Hz | SDO `0x2001.0x02` | Notes |
|------|-----|-------------------|-------|
| Current | 20.0 | `C8 00` | Starting point in XML |
| Softer | 17.6 | `B0 00` | −12% |
| Softer | 15.0 | `96 00` | −25% |
| Factory-ish | 25.0 | `FA 00` | kalico cal default |

After changing C01.01, revisit C01.00 / C01.02 if response feels mushy or overshoots.

### Inertia ratio (C00.06)

Default 100% in XML. If accelerations ring but cruise is fine, try 70–130% using the Servo Tuning tab or SDO `0x2000.0x07` and re-log.

---

## Read back parameters

```bash
ethercat slaves -v
sudo ethercat upload -p 0 -t uint16 0x2001 0x02   # speed gain
sudo ethercat upload -p 0 -t uint16 0x2000 0x07   # inertia ratio
```

A6 vendor objects often lack SDO dictionary info, so **`-t uint16` / `-t uint32` is required**. The Servo Tuning tab always passes `--type`.

---

## Files

| Path | Role |
|------|------|
| `ethercat-conf.xml` | SDO tuning + PDO telemetry + 6065/6066 |
| `custom.hal` | Torque / velocity / **drive 60F4** → `tune-*` pins |
| `probe_basic/user_tabs/servo_tuner/` | Servo Tuning GUI tab |
| `probe_basic/python/a6_servo_tune.py` | SDO / preset backend |
| `config/tuning/presets/` | Per-axis JSON tuning presets |
| `config/logging/signals.json` | FERR + DRIVE + torque + velocity channels |
| `SIGNAL_LOGGING.md` | Logging tab + HAL telemetry |
| `nc_files/x_tuning.ngc` | Bench excitation program |

---

## Branch

`cursor/a6-tuning-ferror-comp-70f6` — extends `cursor/signal-logging-framework-0633`.
