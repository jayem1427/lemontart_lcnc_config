# Semi-Auto Servo Tuning — Scope

High-level scope for turning the manual A6 / LinuxCNC tuning workflow into a **plot-to-LLM** semi-auto loop. Builds on the existing Servo Tuning tab, signal logging, and `SERVO_TUNING.md`.

**Branch context:** `servo-tuning-gui`  
**Related docs:** `SERVO_TUNING.md` (human procedure), `SERVO_TUNING_LLM.md` (LLM playbook), `A6_TUNING.md` (tooling pin), `SIGNAL_LOGGING.md`

---

## Problem

Manual tuning works but is fiddly: arm logger, run a move, screenshot Halscope/Logging, paste into chat, interpret, edit gains, repeat. We already have SDO read/apply, CSV logging, and trial NGCs. We want less ceremony and a repeatable “ask the model what to change” path — **without** a full auto-tuner or blind SDO writes from an LLM.

---

## Goals

1. **Repeatable stimulus** — per-axis back-and-forth `.ngc` at fixed speed/accel.
2. **One-button trial** — run move, capture the plot, put an image on the **clipboard** (and save a file copy).
3. **LLM-assisted advice** — operator pastes plot (+ gains) into an LLM loaded with `SERVO_TUNING_LLM.md`.
4. **Human (or later gated) apply** — v0 apply stays manual in Servo Tuning; later optional “apply suggestion.”
5. **Safe baseline first** — soft/rigidity/inertia path before chasing minimum ferror.

Non-goals for v0: closed-loop auto-apply, full scoring/FFT engine, Halscope integration, EEPROM store automation, multi-axis batch tuning.

---

## Chosen v0 UX

```
[Tune Trial] button
  → arm/ensure DRIVE ferror plot
  → run axis tuning NGC (or prompt Cycle Start)
  → on program end, export plot PNG
  → copy PNG to clipboard (+ write logs/tuning/…)
  → operator pastes into LLM with playbook context
  → operator applies suggested gains in Servo Tuning tab
```

**Primary feedback = plot image** (waveform shape).  
**Gains = structured text** copied or typed (not OCR-dependent).  
Optional tiny sidecar later: peak/RMS, fault bit — not required to start.

---

## What already exists

| Piece | Where |
|---|---|
| SDO read / apply / presets | `probe_basic/python/a6_servo_tune.py`, Servo Tuning tab |
| HAL telemetry (60F4, torque, vel) | `custom.hal`, Logging tab |
| CSV logger + summaries | `hal_signal_logger.py`, `config/logging/signals.json` |
| Excitation programs | `nc_files/*_tuning.ngc` |
| Manual + LLM procedures | `SERVO_TUNING.md`, `SERVO_TUNING_LLM.md` |

---

## Work packages

### WP0 — Docs (this pass)

- [x] Boiled-down manual procedure (`SERVO_TUNING.md`)
- [x] LLM playbook for plot-based advice (`SERVO_TUNING_LLM.md`)
- [x] Scope doc (this file)

### WP1 — Trial button + plot → clipboard

- [x] “Tune Trial” control on Servo Tuning tab (`SEMI-AUTO TUNE TRIAL`)
- [x] Select axis → open matching `*_tuning.ngc` (Cycle Start default; optional AUTO)
- [x] Plotted signal is **DRIVE** ferror (60F4) on the Servo Tuning strip chart
- [x] Export PNG (title burn-in: axis, trial id, gains tag, unit)
- [x] Clipboard image + paste text; always save under `logs/tuning/`
- [x] **COPY PASTE PACK** for text-only re-copy

### WP2 — Stimulus hygiene

- [x] Per-axis NGC documented + header comment “do not edit mid-campaign”
- [x] Operator guide: `SEMI_AUTO_TUNING.md`
- [x] Both directions covered by existing back-forth pattern

### WP3 — Safe baseline (light automation)

- [x] **LOAD SOFT BASELINE** → soft preset into Pending (Fixed 1st / manual only when writable)
- [x] Soft baseline skips read-only C01.38 on this A6 build
- [x] Preflight: ESTOP / machine ON / interpreter idle; trial aborts on disable/ESTOP
- [ ] Inertia / rigidity still mostly manual unless already easy via SDO UI

### WP4 — LLM workflow polish (still human paste)

- [x] Paste pack points at `SERVO_TUNING_LLM.md`
- [x] Operator notes field + checklist in `SEMI_AUTO_TUNING.md`
- [ ] Keep playbook updated from real sessions (Z ferror, Y push-buzz, ring)

### WP5 — Later (not v0)

- [ ] Structured suggestion JSON + validator (max step, allowlist)
- [ ] One-click apply / auto-revert preset per trial
- [ ] Optional metrics sidecar (peak, RMS, settle) beside the PNG
- [ ] Headless trial runner CLI (no GUI)
- [ ] Notch / FF / EEPROM persistence workflows
- [ ] True semi-auto loop (API to model) if paste UX gets old

---

## Design rules

1. **Tune on drive 60F4 (DRIVE)** — do not “fix” loops by widening LinuxCNC `FERROR`.
2. **Vision diagnoses; framework applies** — LLM does not get raw SDO rights in v0.
3. **Same move every trial** — otherwise plot comparisons lie.
4. **Jagged ring = hard stop** — back off / filter; don’t stack gain.
5. **1st vs 2nd gain sets** — push-buzz often means 2nd set or switchover; keep sets close.
6. **No ghost-lag HAL compensation** — abandoned on this branch; stay off that path (`A6_TUNING.md`).

---

## Success criteria (v0)

- Operator can run a tune trial and paste a plot into chat in **one button + paste**.
- LLM answers using `SERVO_TUNING_LLM.md` stay within bounded, zone-ordered changes.
- A session can improve an axis (lower smooth ferror or kill push-buzz) without CSV wrangling or manual screenshots.

---

## Suggested build order

1. Docs (done)  
2. PNG export + clipboard from an existing log/plot  
3. Wire **Tune Trial** button to NGC + export  
4. Gains text / paste-pack helper  
5. Soft baseline preset hook  
6. Only then: apply-suggestion / metrics / API loop  

---

## Decisions (v0 shipped)

- **Cycle Start default**; optional **AUTO CYCLE START** with second confirm.
- **Always save PNG/CSV/meta** under `logs/tuning/`; clipboard is best-effort.
- **Servo Tuning live DRIVE FERR plot** is the export source (not Logging tab).
- **Ferror-only** PNG for v0 (torque stays on Logging tab if needed).
- During trial, capture runs at **10 ms** (not the live 1 ms plot rate) so a full NGC fits in the buffer.

## Operator doc

See **`SEMI_AUTO_TUNING.md`**.
