# A6-EC servo tuning (LinuxCNC / lcec)

Conservative **fault-window** SDOs (6065/6066) at EtherCAT startup, plus a **Servo Tuning** Probe Basic tab for C00/C01 loop gains. **Loop gains are NOT written from `ethercat-conf.xml`** — that was wiping bench tuning on every LinuxCNC start. **LinuxCNC `joint.N.f-error` / INI `FERROR` are left alone** — plot the drive’s own following error (CiA **60F4**) as a separate Logging signal (**DRIVE**).

Based on the [kalico sota-motion](https://github.com/dderg/kalico/tree/sota-motion) approach (SDO object dictionary instead of StepperOnline GUI). Logging tab + Servo Tuning live on this branch together.

---

## Status — active tuning branch

**Branch:** `servo-tuning-gui`  
Rebased onto current `main`. Servo Tuning UI + APPLY path hardened; loop gains no longer wiped on every LinuxCNC start.

### Resume checklist

```bash
cd /home/jon/linuxcnc/configs/ethercat_mill
git checkout servo-tuning-gui
# Clear leftover user tabs from other feature branches (Probe Basic loads every folder):
rm -rf probe_basic/user_tabs/laser_setter
ls probe_basic/user_tabs/   # expect: signal_monitor, servo_tuner, templates
./launch.sh
```

Then: **Servo Tuning** → check axis buttons to plot (multi-OK) → parameters auto-read on open → **START PLOT** → **COPY TUNING** / **COPY PLOT** for LLM → edit Pending → **APPLY TO DRIVE**. Optional: **Logging** tab for multi-channel CSV.

Or skip the loop entirely: **ONE-CLICK TUNE** on the same tab runs the whole
gain ladder per axis automatically (stimulus moves + FFT stability gate +
auto notch + journaled revert paths) — see **`ONE_CLICK_TUNING.md`**.

**INERTIA TUNE** tries the drive’s F30.10 offline inertia ID and reads
**C00.06** — see **`INERTIA_TUNE.md`**. Run that *before* one-click when the
load ratio is unknown or wrong.

### Clipboard → LLM

Servo Tuning → **CLIPBOARD** strip:

- **COPY TUNING** — parameter text using the same labels as the table (`C01.00 1st position loop gain`, …)
- **COPY PLOT** — FERR strip-chart image
- **COPY RESONANCE** — FFT / stability-gate report (after **ANALYZE**)
- Docs: `SEMI_AUTO_TUNING.md`, `SERVO_TUNING_LLM.md`

Does **not** auto-apply LLM suggestions. C01.38 gain switchover remains read-only on APPLY.

### Resonance analysis (FFT + notches)

Under the FERR plot:

1. **START PLOT** → run `nc_files/x_resonance.ngc` (short high-accel reversals).
2. **ANALYZE** — Hann-windowed FFT of the edit-axis FERR buffer (~1 kHz → Nyquist ≈ 500 Hz).
3. Stability gate: PASS/FAIL from spectral peaks, HF energy, ring score.
4. **USE SUGGESTED NOTCH 3** — loads dominant peak into Pending `C01.46/47/48` (leaves 1st/2nd for adaptive).
5. **APPLY TO DRIVE** yourself. Or enable `C01.30` adaptive and re-read notch freqs.

Parameter table **Notch** group now exposes:

- `C01.30`–`C01.33` adaptive mode / test diagnostics (`C01.32`/`C01.33` read-only)
- Five torque notches `C01.40`–`C01.4E` (freq / width % / depth %; **8000 Hz = off**)

Backend: `probe_basic/python/resonance_analysis.py`.

### What is done

| Item | State |
|------|--------|
| Drive 60F4 PDO → `tune-drive-ferr.*` | Working |
| Servo Tuning live FERR plot (mm/deg **or** pulses) | Working — multi-axis toggles + **START PLOT** (no CSV). HAL poll only while plotting. |
| Compact presets strip + right-side param table | Working |
| APPLY with per-SDO retry/verify; continues after failures | Working |
| **ONE-CLICK TUNE** per axis (auto gain ladder + notch + journal) | New — sim-tested; see `ONE_CLICK_TUNING.md` for hardware bring-up |
| Read-only SDOs skipped (C01.10, C01.38) | Working — no longer abort the whole APPLY |
| Startup C00/C01 SDOs in `ethercat-conf.xml` | **Removed** — was overwriting RAM tuning every bus claim |
| Startup 6065/6066 fault windows | Still set (1.0 mm / 1.0° / 250 ms) |
| Logging tab default sample rate | **1000 Hz** via in-process `hal.get_value` |
| Bench presets incl. `one_click_best_20260712` (X/Y), `10um`, `20um_y_axis`, `Z/20um`, `Z/no_buzz` | Under `config/tuning/presets/` — combo starts on **(none)** |

### What we deliberately abandoned

**HAL pipeline-delay / “ghost lag” compensation** (`servo_tuning.hal`) was removed. It advanced `motor-pos-fb` by `vel_cmd × ferr-lag` so host `joint.f-error` looked smaller. That couples tuning into LinuxCNC FERROR / soft faults and caused HAL load headaches. **Do not bring it back** unless you have a strong reason and keep it off the FERROR path.

**Servo Tuning CSV logging** — removed from this tab on purpose. Use the **Logging** tab if you want files under `logs/signals/`.

### Machine tweaks made while debugging (still on this branch)

These are operational, not “final tuned gains”:

| Change | Why | Where |
|--------|-----|--------|
| Drive **6065** XYZ **1.0 mm**, A **1.0°**; **6066** **250 ms** | 0.1 mm Er47.0 amp faults during moves | `ethercat-conf.xml`, presets, `a6_servo_tune` defaults |
| Host INI `FERROR` left at main’s relaxed values after rebase | Avoid fighting toolchange / jog | `ethercat_mill.ini` |
| Z soft **MAX_LIMIT = 50 mm** | Unhomed Z sat above old soft max → jog blocked | `ethercat_mill.ini` |

### Open / next when you return

1. Per-axis gain ladder: **ONE-CLICK TUNE** now automates it (`ONE_CLICK_TUNING.md`) — first hardware campaigns should be `--dry-run` then CONSERVATIVE on X; keep the journals. The **COPY PLOT** / **COPY TUNING** + LLM loop (`SERVO_TUNING_LLM.md`) remains for judgment calls (torque filter, FF, 2nd set).
2. Store good tunes to drive **EEPROM** (vendor tool / panel) so they survive power loss — LinuxCNC no longer pushes C00/C01 at bus claim.
3. Optional: inertia ratio (C00.06) after a real load measurement.
4. Optional: feedforward / carrier / system ID (Tier 2 — not started).
5. If push-buzz persists, set gain switchover on the drive panel (C01.38 is read-only over SDO here).
### Related branches

| Branch | Role |
|--------|------|
| `servo-tuning-gui` | **This pin** — Logging tab + A6 SDO Servo Tuning + drive FERR + clipboard LLM flow |
| `cursor/laser-setter-1afc` | Laser tool setter UI (remove its tab folder when on this branch) |

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

Written once per slave when lcec claims the bus (RAM only).

**C00/C01 loop gains are intentionally NOT in XML.** They used to be, and every
`./launch.sh` / bus claim reset pos/speed/integral/inertia back to catalog
defaults — wiping whatever you had just tuned in the Servo Tuning tab.

Tune gains only via **Servo Tuning → APPLY** (or `ethercat download`). If you
want values to survive drive power loss, store them to the A6 EEPROM from the
drive panel / vendor tool after a good tune.

Still written at startup (fault windows only):

| SDO | Meaning | XYZ | A |
|-----|---------|-----|---|
| `6065h` | Max position deviation (counts) | 13107 ≈ **1.0 mm** | 364 ≈ **1.0°** |
| `6066h` | Fault persistence (ms) | **250** | **250** |
| `6060h` | Modes of operation | CSP (8) | CSP (8) |

Former catalog startup gains (for reference / `default` preset only — **not auto-applied**):

| SDO | Panel param | Value | Meaning |
|-----|-------------|-------|---------|
| `0x2000.0x05` | C00.04 | 0 | Manual gain mode |
| `0x2000.0x07` | C00.06 | 100 | Load inertia ratio 100% |
| `0x2001.0x01` | C01.00 | 300 | Position loop gain **30.0 rad/s** |
| `0x2001.0x02` | C01.01 | 200 | Speed loop gain **20.0 Hz** |
| `0x2001.0x03` | C01.02 | 3184 | Speed integral **31.84 ms** |
| `0x2001.0x31` | C01.30 | 1 | Adaptive notch filter |

**Not configured here:** carrier frequency, velocity/torque feedforward (60B1/60B2), kalico-style system ID — see prior discussion for Tier 2+.

---

## Servo Tuning tab (Probe Basic GUI)

Open **Servo Tuning** in Probe Basic (`probe_basic/user_tabs/servo_tuner/`).

| Control | Action |
|---------|--------|
| **PRESET** | One-line strip: combo + **LOAD** (Pending only) + **SAVE AS PRESET** / **DELETE** |
| **PLOT / EDIT** | Axis buttons toggle FERR traces (multi-OK); last clicked-on = edit axis |
| *(auto-read)* | SDOs load into Current + Pending on tab open / unread axis focus |
| **COPY TUNING** / **COPY PLOT** | Clipboard text (table labels) + FERR image for LLM |
| **START PLOT / STOP PLOT** | Live 60F4 FERR trace only — **nothing written to disk**. HAL is polled (~1 kHz) **only while START PLOT is on** and this tab is visible; pulse/mm readouts stay idle otherwise. |
| **FERR / FFT** | Toggle the plot stack: live FERR strip chart (default) or post-**ANALYZE** FFT spectrum. |
| **MM** / **PULSES** | Plot Y-axis units (pulses = raw `lcec.0.N.ferr-fb`) |
| **TUNING PARAMETERS** | Grouped table: Current / Pending / Unit / Range |
| **APPLY TO DRIVE** | In the parameters box — cycles motors OFF if needed, writes Pending SDOs with retry+verify, re-enables |
| **ONE-CLICK TUNE** | Gain ladder auto-tune (`ONE_CLICK_TUNING.md`) |
| **INERTIA TUNE** | Drive F30.10 inertia ID → C00.06 (`INERTIA_TUNE.md`) |

**Not on this tab anymore:** READ button, REVERT, LOAD DEFAULT, Tune Trial / Cancel, Load Soft Baseline, Auto Cycle Start, notes field, CSV logging.

Presets live under `config/tuning/presets/<axis>/*.json`. Combo starts on **(none)**.

**Bench / validated presets (2026-07-12 hardware)**

| Axis | Preset | Gains (C01.01 / C01.00 / C01.02) | Notes |
|------|--------|-----------------------------------|-------|
| X | `one_click_best_20260712` | 150 Hz / 224.6 rad/s / 5.0 ms | Best stable step from first X one-click run (verify reverted; salvaged manually). |
| Y | `one_click_best_20260712` | 164.6 Hz / 60 rad/s / 3.5 ms | AGGRESSIVE one-click; ~39% score improvement; kept via verify-fail → best-step logic. |
| X | `10um` | (legacy hand tune) | Older reference. |
| Y | `20um_y_axis` | (legacy hand tune) | Older reference. |
| Z | `20um`, `no_buzz` | — | Z references. |

Auto-tune also writes timestamped `one_click_*` / `pre_one_click_*` presets per campaign; copy anything worth keeping into a named preset.

### FERR plot time zoom

The live strip chart keeps a **5 s** sample buffer at **1 kHz** (`FERR_WINDOW_S` in `servo_tuner.py`) so **COPY PLOT**, **ANALYZE**, and resonance FFT still see the full capture.

The **visible X axis** is zoomed in for detail: `FERR_PLOT_X_FRAC = 0.075` → about **0.375 s** of trailing time on screen (~30% of the old default span). When the buffer holds more data than fits, the view follows the **most recent** samples (trailing window). Y autoscale is unchanged.

To zoom more or less, edit `FERR_PLOT_X_FRAC` in `probe_basic/user_tabs/servo_tuner/servo_tuner.py` (smaller = tighter zoom, e.g. `0.05` ≈ 0.25 s).

**Typical workflow**

1. Open tab — auto-read when EtherCAT is up.
2. **START PLOT** → pick **MM** or **PULSES** → run `nc_files/x_tuning.ngc` (or jog).
3. **COPY PLOT** + **COPY TUNING** → paste into LLM with `SERVO_TUNING_LLM.md`.
4. Edit **Pending** from the suggestion.
5. **APPLY TO DRIVE** — confirm the value list; unread / read-only keys are skipped.
6. If better: **SAVE AS PRESET**. Repeat per axis.

### APPLY reliability notes

- **C01.10** (speed FB filter) and **C01.38** (gain switchover mode) are **read-only** on this A6 firmware. They used to abort the whole APPLY mid-batch; they are skipped now.
- Each writable SDO is downloaded, re-uploaded, and retried on mismatch.
- Machine ON → APPLY turns it OFF, waits for `cia402.N.enable` to drop, writes, then restores ON.

### Revert paths

| Want | Do |
|------|----|
| Undo Pending edits | Re-open the Servo Tuning tab (fresh auto-read) |
| Known-good named set | Preset **LOAD**, then **APPLY TO DRIVE** |
| Survive power loss | Store to drive **EEPROM** via vendor tool after a good tune |

---

## Tuning workflow (plot on Servo Tuning; optional Logging CSV)

1. Start LinuxCNC; confirm no HAL errors.
2. **Servo Tuning** → **START PLOT** → **DRIVE FERR** in mm or pulses.
3. Run `nc_files/x_tuning.ngc` (or jog). Prefer drive 60F4 over LinuxCNC `joint.f-error`.
4. Soften **C01.01** if ringing/whine persists, or raise gains carefully toward your target.
5. Optional: **Logging** tab → **START LIVE** for multi-channel CSV at **1000 Hz** under `logs/signals/`.

### Suggested gain ladder (C01.01 speed gain, u16 hex)

| Step | Hz | SDO `0x2001.0x02` | Notes |
|------|-----|-------------------|-------|
| Catalog ref | 20.0 | `C8 00` | Old XML / `default` preset |
| Softer | 17.6 | `B0 00` | −12% |
| Softer | 15.0 | `96 00` | −25% |
| Factory-ish | 25.0 | `FA 00` | kalico cal default |

After changing C01.01, revisit C01.00 / C01.02 if response feels mushy or overshoots.

### Inertia ratio (C00.06)

Default reference 100%. If accelerations ring but cruise is fine, try 70–130% via Servo Tuning or SDO `0x2000.0x07`.

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
| `ethercat-conf.xml` | PDO telemetry + 6065/6066 only (no C00/C01 loop gains) |
| `custom.hal` | Torque / velocity / **drive 60F4** → `tune-*` pins |
| `probe_basic/python/a6_servo_tune.py` | SDO read/write, presets, FERR helpers |
| `probe_basic/python/a6_auto_tune.py` | **One-click** auto-tune engine (`ONE_CLICK_TUNING.md`) |
| `probe_basic/python/a6_auto_tune_sim.py` | Simulated axis for auto-tune tests / `--sim` |
| `probe_basic/python/a6_inertia_tune.py` | **Inertia** F30.10 engine (`INERTIA_TUNE.md`) |
| `scripts/run_auto_tune.py` | Headless one-click CLI (`--sim`, `--dry-run`) |
| `probe_basic/user_tabs/servo_tuner/` | Servo Tuning GUI (ONE-CLICK + INERTIA TUNE) |
| `config/tuning/presets/` | Per-axis JSON presets — see table above; UI starts on **(none)** |
| `config/logging/signals.json` | Logging-tab channels; default **1000 Hz** |
| `logs/tuning/one_click/` | Auto-tune journals (gitignored) |
| `SIGNAL_LOGGING.md` | Logging tab + HAL telemetry |
| `nc_files/*_tuning.ngc` | Oscillation moves for FERR plots |

---

## Branch

`servo-tuning-gui` — Logging + Servo Tuning + Tune Trial; rebased onto current `main`.
