# Semi-Auto Servo Tuning — Scope

High-level scope for the **plot-to-LLM** semi-auto loop on this machine. Builds on the Servo Tuning tab, signal logging, and `SERVO_TUNING.md`.

**Branch context:** `servo-tuning-gui`  
**Related docs:** `SERVO_TUNING.md` (human procedure), `SERVO_TUNING_LLM.md` (LLM playbook), `A6_TUNING.md` (tooling pin), `SIGNAL_LOGGING.md`

---

## Problem

Manual tuning works but is fiddly: run a move, screenshot, paste into chat, interpret, edit gains, repeat. We already have SDO auto-read/apply, CSV logging, and trial NGCs. We want less ceremony and a repeatable “ask the model what to change” path — **without** a full auto-tuner or blind SDO writes from an LLM.

---

## Goals

1. **Repeatable stimulus** — per-axis back-and-forth `.ngc` at fixed speed/accel.
2. **Easy clipboard** — **COPY PLOT** (image) + **COPY TUNING** (text with table labels).
3. **LLM-assisted advice** — operator pastes into an LLM loaded with `SERVO_TUNING_LLM.md`.
4. **Human apply** — suggestions stay manual in Servo Tuning (**APPLY TO DRIVE**).
5. **Auto-read on open** — no manual READ button; parameters load on tab open / unread axis focus.

Non-goals *for this clipboard loop*: closed-loop auto-apply, Halscope integration, EEPROM store automation, multi-axis batch tuning.

Two former non-goals were later built as separate features: FFT scoring (**ANALYZE** / `resonance_analysis.py`) and a one-button per-axis state machine (**ONE-CLICK TUNE** / `ONE_CLICK_TUNING.md`). The LLM loop stays human-in-the-loop by design.

---

## Chosen UX

```
Open Servo Tuning → auto-read SDOs
  → START PLOT + run axis tuning NGC (Cycle Start)
  → COPY PLOT + COPY TUNING
  → paste into LLM with SERVO_TUNING_LLM.md
  → edit Pending → APPLY TO DRIVE → repeat
```

**Primary feedback = plot image** (waveform shape).  
**Gains = structured text** with the same Parameter-column labels as the UI.

Removed from the UI (by design): Tune Trial / Cancel Trial, Auto Cycle Start, Load Soft Baseline, notes field, READ button.

---

## What already exists

| Piece | Where |
|---|---|
| SDO auto-read / apply / presets | `a6_servo_tune.py`, Servo Tuning tab |
| HAL telemetry (60F4, torque, vel) | `custom.hal`, Logging tab |
| CSV logger + summaries | `hal_signal_logger.py`, `config/logging/signals.json` |
| Excitation programs | Frozen NGC under your `PROGRAM_PREFIX` |
| Clipboard helpers | `tune_trial.py` (`format_tuning_text`, plot PNG copy) |
| Manual + LLM procedures | `SERVO_TUNING.md`, `SERVO_TUNING_LLM.md` |

---

## Work packages

### Done

- [x] Manual procedure + LLM playbook
- [x] Multi-axis FERR plot + **START PLOT**
- [x] Auto-read on tab open / unread axis
- [x] **COPY TUNING** (table labels) + **COPY PLOT**
- [x] Operator guide (`SEMI_AUTO_TUNING.md`)
- [x] Frozen NGC stimuli documented

### Later (optional)

- [ ] Structured suggestion JSON + validator (max step, allowlist)
- [ ] Optional metrics sidecar (peak, RMS, settle) beside the PNG
- [ ] Headless trial runner CLI (no GUI)
- [ ] Notch / FF / EEPROM persistence workflows
- [ ] Inertia / rigidity Active/Locked UX

---

## Safety principles

- LLM never writes the bus.
- APPLY only writes successfully auto-read keys.
- Same NGC for a campaign.
- Abort = LinuxCNC Abort.
