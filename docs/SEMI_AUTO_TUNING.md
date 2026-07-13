# Semi-Auto Servo Tuning

Operator guide for the **clipboard → LLM** loop on the Servo Tuning tab: run a frozen back-and-forth move, copy drive FERR + parameters, paste into an LLM, apply suggested gains yourself.

**Related:** `SERVO_TUNING.md` (manual zones), `SERVO_TUNING_LLM.md` (LLM playbook), `SEMI_AUTO_TUNING_SCOPE.md` (design), `A6_TUNING.md` (tooling pin)

---

## Safety rules

1. **Machine clear** — tuning NGCs move the selected axis through their envelope.
2. **LLM never writes SDOs** — suggestions go into Pending → you press **APPLY TO DRIVE** (motors cycle OFF→ON as usual).
3. **Tune on drive 60F4** — the plot is CiA following error via `tune-drive-ferr.*`, not LinuxCNC `joint.f-error` / INI `FERROR`.
4. **Abort** with the normal LinuxCNC Abort button if anything looks wrong.
5. **Same NGC all campaign** — do not edit `nc_files/*_tuning.ngc` mid-compare or plots lie.

---

## One-session recipe

1. Home / enable machine. Open **Servo Tuning**.
2. Parameters **auto-read** on tab open and when you focus an unread axis (no READ button).
3. Check the axis button(s) to plot; last clicked-on axis is the one you edit.
4. **START PLOT**, then run the frozen axis NGC (MDI / AUTO + Cycle Start).
5. **COPY PLOT** (image) and **COPY TUNING** (text — same labels as the parameter table).
6. Paste into an LLM that has `SERVO_TUNING_LLM.md` context.
7. Edit Pending from the suggestion → **APPLY TO DRIVE** → repeat from step 4.

Optional: **SAVE AS PRESET** / **LOAD** for named snapshots (combo starts on `(none)`).

---

## Clipboard buttons

| Button | What it copies |
|--------|----------------|
| **COPY TUNING** | Live/Pending parameters for the edit axis as text. Labels match the Parameter column (`C01.00 1st position loop gain`, …). |
| **COPY PLOT** | Current FERR strip-chart image. |

---

## Frozen stimuli

| Axis | File | Intent |
|------|------|--------|
| X | `nc_files/x_tuning.ngc` | 10× 0↔80 mm @ F1000 |
| Y | `nc_files/y_tuning.ngc` | 10× 0↔15 mm @ F30000 |
| Z | `nc_files/z_tuning.ngc` | 1× 0↔15 mm @ F10000 |
| A | `nc_files/a_tuning.ngc` | 10× 0↔90° @ F3600 |

`y_tuning_85.ngc` is an alternate — use it only if you intentionally change the campaign.

---

## Soft starting point

There is no **LOAD SOFT BASELINE** button. Start from auto-read live values, or **SAVE AS PRESET** a soft set you like and **LOAD** it later. C01.38 gain switchover is read-only on this A6 — set Fixed 1st on the drive panel if needed.

---

## Files / code

| Path | Role |
|------|------|
| `probe_basic/python/tune_trial.py` | `format_tuning_text` + clipboard helpers |
| `probe_basic/user_tabs/servo_tuner/servo_tuner.py` | Servo Tuning UI (auto-read, COPY TUNING / COPY PLOT) |

---

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Current column empty / APPLY blocked | Auto-read failed (EtherCAT / sudo?) — re-open tab or change axis |
| Clipboard empty | Wayland/X11 quirks — screenshot the plot; re-try **COPY TUNING** |
| Copy labels look wrong | Should match Parameter column exactly — report if a key diverges |
| Switchover still wrong | C01.38 is read-only here — set Fixed 1st on the drive panel |

---

## Not in scope

Auto-apply of LLM JSON, EEPROM store, multi-axis batch, Halscope. See `SEMI_AUTO_TUNING_SCOPE.md`.

A one-button per-axis auto-tune now exists separately (**ONE-CLICK TUNE** on the same tab — `ONE_CLICK_TUNING.md`); this clipboard → LLM loop remains the tool for the judgment calls it does not automate (torque filter, feedforward, 2nd gain set).
