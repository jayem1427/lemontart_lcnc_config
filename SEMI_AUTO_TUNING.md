# Semi-Auto Servo Tuning

Operator guide for the **Tune Trial** flow on the Servo Tuning tab: run a frozen back-and-forth move, capture drive FERR, paste into an LLM, apply suggested gains yourself.

**Related:** `SERVO_TUNING.md` (manual zones), `SERVO_TUNING_LLM.md` (LLM playbook), `SEMI_AUTO_TUNING_SCOPE.md` (design), `A6_TUNING.md` (tooling pin)

---

## Safety rules

1. **Machine clear** — trials move the selected axis through the NGC envelope.
2. **Default is manual Cycle Start** — leave **AUTO CYCLE START** unchecked unless you intentionally want the UI to start motion after a second confirm.
3. **LLM never writes SDOs** — suggestions go into Pending → you press **APPLY TO DRIVE** (motors cycle OFF→ON as usual).
4. **Tune on drive 60F4** — the plot is CiA following error via `tune-drive-ferr.*`, not LinuxCNC `joint.f-error` / INI `FERROR`.
5. **Abort** with the normal LinuxCNC Abort button if anything looks wrong. **CANCEL TRIAL** only stops waiting/export; it does not stop motion.
6. **Same NGC all campaign** — do not edit `nc_files/*_tuning.ngc` mid-compare or trial plots lie.

---

## One-session recipe

1. Home / enable machine. Open **Servo Tuning**. Select axis.
2. **READ**.
3. Optional: **LOAD SOFT BASELINE** → review Pending → **APPLY TO DRIVE**.
4. Optional notes in the notes field (`buzzes on push`, etc.).
5. **TUNE TRIAL** → confirm → **Cycle Start** (unless auto-run).
6. When the program ends, PNG + paste pack land on the clipboard and under `logs/tuning/<trial_id>/`.
7. Paste into an LLM that has `SERVO_TUNING_LLM.md` context (plot image + text).
8. Edit Pending from the suggestion → **APPLY TO DRIVE** → repeat from step 5.

**COPY PASTE PACK** re-copies the text if your chat only accepted the image.

You do **not** need to press **START PLOT** first — Tune Trial turns capture on for the run (at 100 Hz during the trial so a full move fits in memory).

---

## What TUNE TRIAL does

| Step | Behavior |
|------|----------|
| Preflight | ESTOP clear, machine ON, interpreter idle |
| Plot | Clears FERR strip; enables capture; drops sample rate to **10 ms** and expands buffer to ~**180 s** |
| Program | Opens `nc_files/<axis>_tuning.ngc` in AUTO |
| Run | Waits for Cycle Start **or** issues AUTO_RUN if checked |
| Capture | Polls live drive FERR into the plot |
| Finish | Writes `drive_ferr.png`, `drive_ferr.csv`, `meta.json`, `paste_pack.txt` |
| Clipboard | Image + paste-pack text (best-effort; files always saved) |
| Restore | Returns the live plot timer to the normal 1 ms / 5 s window |

Artifacts directory example:

```text
logs/tuning/20260711_133015_Y/
  drive_ferr.png
  drive_ferr.csv
  meta.json
  paste_pack.txt
```

PNG title burn-in: `Y · <trial_id> · pos/speed/integral/filter · mm`.

---

## Frozen stimuli

| Axis | File | Intent |
|------|------|--------|
| X | `nc_files/x_tuning.ngc` | 10× 0↔80 mm @ F1000 |
| Y | `nc_files/y_tuning.ngc` | 10× 0↔15 mm @ F30000 |
| Z | `nc_files/z_tuning.ngc` | 10× 0↔15 mm @ F10000 |
| A | `nc_files/a_tuning.ngc` | 10× 0↔90° @ F3600 |

`y_tuning_85.ngc` is an alternate — **not** used by the button. Point `AXIS_TUNING_NGC` in `tune_trial.py` only if you intentionally change the campaign.

---

## Soft baseline

**LOAD SOFT BASELINE**:

- Overlays `config/tuning/presets/<axis>/soft.json` onto the last READ
- Tries `manual_mode = 0` when that key is readable **and** writable
- Tries `gain_sw_mode = 0` (Fixed 1st) only when writable — on this A6 build **C01.38 is read-only**, so switchover may need the drive panel
- **Does not write the drive** until you **APPLY TO DRIVE**

Use this before the first LLM loop so you start from a known-soft Pending set.

---

## Files / code

| Path | Role |
|------|------|
| `probe_basic/python/tune_trial.py` | NGC resolve, preflight, paste pack, artifacts, clipboard |
| `probe_basic/user_tabs/servo_tuner/servo_tuner.py` | Semi-Auto strip + trial state machine |
| `logs/tuning/` | Trial outputs (created on demand) |

---

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Trial blocked | ESTOP, machine OFF, program already running |
| Empty / short plot | Forgot Cycle Start; cancelled early; wrong axis selected |
| Clipboard empty | Wayland/X11 quirks — open `drive_ferr.png` from `logs/tuning/` and use **COPY PASTE PACK** |
| Paste pack gains look wrong | **READ** before the trial |
| Motion continues after CANCEL TRIAL | Expected — hit LinuxCNC Abort |
| Soft baseline didn’t fix switchover | C01.38 is read-only here — set Fixed 1st on the drive panel |

---

## Not in v0

Auto-apply of LLM JSON, FFT scoring, EEPROM store, multi-axis batch, Halscope. See `SEMI_AUTO_TUNING_SCOPE.md` WP5.
