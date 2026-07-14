# One-Click Servo Tuning (per axis)

Automated version of the manual gain ladder in `SERVO_TUNING.md` for the
StepperOnline **A6-EC** drives: one button per axis that moves the axis
through a short repeatable stimulus, measures **drive following error**
(CiA **60F4**), climbs the loop gains until the FFT stability gate trips,
backs off, applies a notch when a resonance shows, verifies, and saves the
result — with **every step journaled** so a failed run still teaches us
something.

| Where | What |
|-------|------|
| Probe Basic → **Servo Tuning** → **ONE-CLICK** strip | GUI button per edit axis + profile + CANCEL |
| `scripts/run_auto_tune.py` | Same engine headless (`--sim`, `--dry-run`) |
| `probe_basic/python/a6_auto_tune.py` | The engine (state machine, gates, journal) |
| `probe_basic/python/a6_auto_tune_sim.py` | Simulated axis for tests / desk demos |
| `probe_basic/python/test_a6_auto_tune.py` | End-to-end tests against the simulator |
| `logs/tuning/one_click/<stamp>_<axis>/` | Journals (gitignored — copy out what you want to keep) |

**Related:** `SERVO_TUNING.md` (the manual procedure this automates),
`A6_TUNING.md` (SDO map / APPLY path), `SEMI_AUTO_TUNING.md` (clipboard → LLM
loop — still useful for judgment calls the robot cannot make).

---

## TL;DR operator recipe

1. Home the machine (or at least know you have clearance), machine **ON**.
2. Servo Tuning tab → click the axis button you want to tune (it becomes the
   edit axis).
3. Pick a profile (**BALANCED** unless you have a reason).
4. **ONE-CLICK TUNE <axis>** → read the confirm dialog → Yes.
5. Watch the FERR plot and the progress line. Keep a hand near ESTOP.
6. When it finishes: read the summary, try the axis, and if you like it,
   store to drive **EEPROM** from the panel/vendor tool (writes are RAM-only).
7. Keep the journal folder — especially if anything looked wrong.

Cancel anytime with **CANCEL**: motion aborts and every touched SDO is
restored to its baseline value.

---

## Safety model

- **The axis moves.** Strokes are *relative to the position it is sitting
  at*: X 40 mm, Y 15 mm, Z 10 mm, A 60° by default (edit
  `DEFAULT_STIMULI` in `a6_auto_tune.py` or use CLI `--stroke/--feed`).
  Direction is chosen from soft limits when homed; unhomed axes go positive
  and rely on you having confirmed clearance.
- **FERR watchdog.** A 1 kHz sampler watches drive 60F4 during every move
  and aborts motion when |FERR| crosses **80% of the drive 6065 window**
  (1.0 mm / 1.0° on this machine → abort at 0.8). An unstable gain step is
  therefore stopped by software *before* the drive faults with Er47.0.
- **Writes reuse the hardened APPLY path** (`apply_axis_params`): machine
  OFF → SDO download + read-back verify with retries → machine ON. Only keys
  that were successfully auto-read at baseline are ever written; the
  drive-rejected read-only SDOs (C01.10, C01.38) are never touched.
- **Revert guarantee.** Before the first write, the whole baseline is saved
  as a `pre_one_click_<stamp>` preset *and* into the journal. Cancel, any
  exception, or a failed verify restores every touched SDO to baseline. If
  the *revert itself* fails (dead bus), the journal gets a **CRITICAL** entry
  listing the exact values to restore by hand.
- **RAM only.** Nothing is stored to drive EEPROM, and `ethercat-conf.xml`
  still does not push loop gains at startup — a power cycle is always a
  hard reset to whatever the drive has stored.
- **Not touched:** LinuxCNC `joint.f-error` / INI `FERROR`, 6065/6066 fault
  windows, 2nd gain set, torque filter, feedforward, stiffness, inertia
  (set C00.06 first via the **INERTIA** panel — `GRAPHICAL_INERTIA_TUNE.md`).

---

## What one campaign does (state machine)

```
PREFLIGHT -> BASELINE -> [RESCUE] -> SPEED -> [NOTCH] -> POSITION -> [INTEGRAL] -> VERIFY -> FINALIZE
     |            \                                                        (unstable?)   |
     fail          \-- backup preset (pre_one_click_*)                    backoff once   +-- save preset (one_click_*)
                                                                          else keep best or REVERT
```

Zone order follows `SERVO_TUNING.md` (high frequency → low frequency).

| Phase | What happens | Stops when |
|-------|--------------|------------|
| **PREFLIGHT** | Machine ON, interp idle, numpy present, stimulus fits soft limits (homed), warn on ≠100% feed override | any check fails → status `failed`, nothing written |
| **BASELINE** | Read all SDOs (auto-read), save backup preset, run the stimulus once for the reference measurement | core gain SDOs unreadable → `failed` |
| **RESCUE** | Only if the baseline already rings: try a notch at the FFT peak, else soften speed gain 25% at a time (≤3 tries) | stable, or `failed` with "check mechanics" |
| **SPEED** | Multiply **C01.01** by 1.25/step (≤ profile cap, ≤ ¼ of the C01.03 torque filter cutoff). Each step: write → stimulus → gate | gate trips (→ notch attempt, else back off to last good) or improvement < 3% twice |
| **NOTCH** | One-shot: if the unstable step shows a dominant FFT peak 40–500 Hz and notch 3 (C01.46/47/48) is free, write it (width 5%, depth 10%) and re-measure at the same gain | notch kept if the ring clears, reverted otherwise |
| **POSITION** | Climb **C01.00** ×1.2/step toward ~**2× speed gain** (rad/s vs Hz rule of thumb), same gating | gate trips / stalls / cap |
| **INTEGRAL** | Tighten **C01.02** ×0.7/step (lower ms = stronger) while RMS improves ≥0.5% and peak regresses <10% — **skipped** if the best step so far is already ≥30% better than baseline | first non-improvement, ring, or skip |
| **VERIFY** | Re-measure with final gains. If unstable: back speed+position off 25% once and re-verify; if still unstable but a **stable best step** beat baseline by ≥1%, **restore that best** (not baseline); else full revert | always produces a final measurement |
| **FINALIZE** | Save `one_click_<stamp>` preset if improved; journal the summary | — |

Also at setup: **C00.04 is forced to 0 (manual gain mode)** if it wasn't,
so the drive's own auto-tuner cannot fight our writes (journaled).

### The stability gate

Every measurement gets a Hann-windowed FFT (`resonance_analysis.py`,
Nyquist ≈ 500 Hz at 1 kHz sampling) and is called **unstable** when any of:

- the move was **aborted** (FERR watchdog, timeout, machine dropped out),
- a spectral peak ≥ 4× the noise floor **and** above the amplitude floor —
  which is the larger of `min_resonance_amplitude` (~1 µm) and **10% of the
  buffer RMS** (`resonance_vs_rms`) so forced tracking-error harmonics never
  masquerade as resonance,
- HF energy (≥40 Hz) ≥ 35% of total **and** RMS is above the noise floor,
- ring score ≥ 0.85 **and** RMS is above the noise floor.

Peaks below the **motion-harmonic band** are ignored entirely: the gate's
low cutoff is `max(25 Hz, 6 / leg_time)` capped at 120 Hz, because a short
fast stroke (Y's 0.09 s legs) legitimately fills 30–60 Hz with stimulus
harmonics (see *Lessons learned* below).

The **score** is `peak + 2×RMS` (axis units; lower is better). A ladder step
is accepted only when stable **and** the score improves by ≥3%
(`improvement_min_pct`), so the tuner prefers *quiet + good* over *hot*.

**Verify measurements** use a slightly different gate: HF energy must exceed
`max(35%, baseline_HF + 12pp)` *and* the score must not beat baseline — so
stimulus harmonics that were acceptable during the ladder do not false-fail a
good final tune on HF alone. Real resonance peaks and ring scores still fail
hard. If verify/backoff fail anyway but a **stable best step** during the
ladder beat baseline by ≥1%, the engine restores that best (journaled as
`verify/keep-best`) instead of wiping gains.

### Profiles

| Profile | Speed cap | Pos cap | Step | Steps/phase | Integral floor |
|---------|-----------|---------|------|-------------|----------------|
| CONSERVATIVE | 120 Hz | 250 rad/s | ×1.15 | 6 | 3.0 ms |
| BALANCED | 200 Hz | 400 rad/s | ×1.25 | 8 | 3.0 ms |
| AGGRESSIVE | 400 Hz | 800 rad/s | ×1.4 | 10 | 1.0 ms |

All profiles also respect `speed ≤ 0.25 × C01.03` (torque-filter phase-lag
rule) and the SDO catalog ranges from `PARAM_DEFS`.

---

## The journal — read this when something fails

Every campaign writes `logs/tuning/one_click/<stamp>_<axis>/`:

| File | Contents |
|------|----------|
| `journal.md` | Human narrative, **appended + fsynced per event** — a crash or power loss still leaves the story up to that moment |
| `journal.json` | Same events machine-readable (config, every SDO write with result, every measurement with FFT peaks, decisions, tracebacks) |
| `NN_<label>.csv` | Raw FERR samples for measurement NN (1 kHz, axis units) — plot with `scripts/plot_signal_log.py` or any spreadsheet |

Journals are **gitignored**. When a run is interesting (good or bad), copy
the folder somewhere safe or paste `journal.md` into an issue/LLM chat.

### How to learn from a failed run

1. Open `journal.md` and find the **last event before the failure** — the
   engine journals its *intent* before acting, so the last entry tells you
   what it was trying to do.
2. Look at the measurement events: each has peak/RMS/score, the gate verdict
   with reasons, the FFT's top peaks, and the gains that were live. The CSV
   next to it has the raw trace.
3. Match the `status` against this table:

| Status / symptom | What it means | Where to look | What to try |
|------------------|---------------|---------------|-------------|
| `failed` at preflight | Machine off / estop / program running / no numpy / no room inside soft limits | the preflight event lists the exact check | fix and rerun; nothing was written |
| `failed`: "baseline read failed for core gain keys" | `ethercat upload` failing (bus down, sudo) | baseline `warning` events | `ethercat slaves -v`, passwordless sudo (see `A6_TUNING.md`) |
| `failed`: "rescue failed" | Axis rings even after softening 3× — probably mechanical (loose coupling, adaptive notch fighting, wrong inertia) or a resonance the 3rd notch can't reach | rescue measurements + FFT peaks; listen to the axis | fix mechanics; try drive panel notch; then rerun |
| `failed`: "SDO write failed" | A write did not verify after retries | the `write` event has the drive's error string | check bus health; if it repeats on one SDO, that SDO may be RO on your firmware — report it so we mark it `writable: False` |
| **`CRITICAL` in journal** | The *revert* failed — drive may hold a mixed tune | the CRITICAL event lists exact key=value pairs | machine OFF, restore values via Servo Tuning tab or `LOAD` the `pre_one_click_*` preset → APPLY |
| `reverted` | Final verify stayed unstable after backoff **and** no stable best step beat baseline by ≥1% | compare `verify*` measurements with the ladder ones; look for `verify/keep-best` — if missing, nothing salvageable | rerun CONSERVATIVE; consider a longer stimulus (more cycles) for less measurement noise |
| `improved` (verify/backoff failed) | Ladder found a strong stable step; verify tripped on HF harmonics or a late integral stress but engine kept `_best_values` | `verify/keep-best` event lists the restored gains | try the axis; store EEPROM if happy — journal explains why verify failed |
| `no-change` | Ladder found nothing ≥3% better than baseline | accepted vs stalled steps | baseline may already be good; try AGGRESSIVE, or tune stimulus feed up so tracking error dominates noise |
| `cancelled` | You pressed CANCEL / Ctrl+C | — | baseline was restored; journal keeps everything measured so far |
| Watchdog trips at the *first* speed step | Baseline is closer to instability than it looks, or 6065 window is tight | `tripped_ferr` value in the measure meta | verify 6065 (should be ~1.0 mm), start from a softer baseline preset |
| Gains end up lower than your hand tune | The gate is stricter than your ears, or the stimulus excites a mode your NGC didn't | FFT peaks in the last stalled/unstable step | that peak frequency is real information — consider a manual notch there, then rerun |

4. If the behavior looks like an engine bug, reproduce it in the simulator:
   the plant knobs in `a6_auto_tune_sim.py` (`resonance_hz`,
   `critical_speed_hz`, …) make most hardware pathologies reproducible in
   milliseconds, and `test_a6_auto_tune.py` shows how to pin them down.

---

## Headless CLI

```bash
# Prove the pipeline end-to-end on any PC — nothing moves, no LinuxCNC needed
python3 scripts/run_auto_tune.py --axis X --sim

# On the mill: measure the real baseline, write NOTHING
python3 scripts/run_auto_tune.py --axis X --dry-run

# Full campaign (interactive confirm unless --yes)
python3 scripts/run_auto_tune.py --axis X --profile balanced

# Custom stimulus / no automatic notch / keep presets out of the repo
python3 scripts/run_auto_tune.py --axis Z --stroke 5 --feed 3000 --no-notch --no-presets
```

Exit code 0 for `improved` / `no-change` / `dry-run`, 2 otherwise. Ctrl+C
cancels through the same revert path as the GUI CANCEL.

---

## Design decisions (and what is deliberately NOT automated)

| Decision | Why |
|----------|-----|
| Tune on drive **60F4**, not LinuxCNC `joint.f-error` | Same rule as the rest of the tuning stack — see `A6_TUNING.md` design rule |
| MDI relative strokes instead of the frozen `*_tuning.ngc` | The engine needs to own start/abort/return-to-start; comparability only matters *within* a campaign (spec is journaled). Run your frozen NGC afterwards to compare against manual campaigns |
| One notch attempt per campaign, always notch **3** | Notches 1/2 belong to the drive's adaptive notch; a second failed notch usually means mechanics, not filters |
| `pos ≈ 2× speed` target ratio | Matches `SERVO_TUNING.md` Zone C guidance for these units |
| Speed gain capped at ¼ torque filter | Filter phase lag destabilizes the speed loop well below Nyquist; raising C01.03 is a judgment call left to humans |
| Stall = revert the step | A hotter gain with no measurable benefit is pure instability risk |
| **Not automated:** torque filter (C01.03), stiffness (C00.05), inertia (C00.06), feedforward (C01.13–18), 2nd gain set, EEPROM store | Each either needs judgment (filter/FF trade-offs), a real load measurement (inertia), or is intentionally manual for safety (EEPROM). The LLM clipboard loop (`SEMI_AUTO_TUNING.md`) remains the tool for those |

Known limitations:

- Measurement noise can stall the ladder early on a very quiet axis; more
  stimulus cycles (`--cycles`) average it out at the cost of time.
- Nyquist is ~500 Hz — resonances above that are invisible to the gate (the
  drive's adaptive notch still sees them; C01.30 mode 1/2 is your friend).
- The stimulus is unidirectional per campaign; strongly asymmetric axes
  (gravity on Z) get tuned on the direction with clearance. Journal notes the
  direction chosen.
- Z runs against gravity with a short stroke by default — if the counter-
  balance/brake situation changes, re-check `DEFAULT_STIMULI["Z"]` first.

---

## Lessons learned (add yours here)

The point of the journals is that failed runs are data. Record what they
taught us, with the journal that proved it:

| Date | Lesson | Evidence / fix |
|------|--------|----------------|
| 2026-07-12 (hardware X) | **Verify HF false-fail discarded a ~49% better tune.** Position ladder peaked at 150/224.6/5.0 ms; integral 2.45 ms hit 259 Hz ring; verify measured low peak but HF 45% > 35% and engine reverted to baseline. Fix: skip integral when best already ≥30% better; verify HF gate is relative to baseline; if verify/backoff fail but best stable step beats baseline ≥1%, restore best and save preset. | `one_click_best_20260712` preset; journal `20260712_172935_X`; `test_verify_fail_keeps_best` |
| 2026-07-12 (hardware Y) | **AGGRESSIVE one-click to 164.6 Hz / 60 rad/s / 3.5 ms (~39% better).** Verify/backoff hit `RCS_ERROR` but post-fix engine kept best stable step and saved preset. Validated on machine — shipped as `Y/one_click_best_20260712`. | journal `20260712_183055_Y`; preset `one_click_20260712_183119` |
| 2026-07-12 (pre-hardware, sim) | **Short strokes fool a naive resonance gate.** Y's default stimulus (15 mm @ F10000 → 0.09 s legs) puts *forced* tracking-error harmonics at 30–60 Hz with ~200× spectral prominence; a gate keyed only on prominence declared the untouched baseline "unstable" and the rescue phase softened a healthy axis until it gave up (`rescue failed: … check mechanics`). Fix: the gate now ignores the stimulus-harmonic band (`6 / leg_time` low cutoff) and requires a candidate peak to carry ≥10% of buffer RMS. | `test_short_stroke_gate_not_fooled` in `test_a6_auto_tune.py`; the false-positive is reproducible by calling `analyze_ferr_resonance` on a sim Y baseline buffer with `min_hz=25` |

When a hardware campaign fails in a *new* way: keep the journal folder, add a
row here, and if the failure is mechanical (loose coupling, gravity, brake),
note the axis and symptom so the next person recognizes it.

---

## Verification story

The engine is exercised end-to-end against a simulated axis
(`a6_auto_tune_sim.py`: tracking lag that shrinks with gain, a resonance
tone above a gain threshold, a hard instability cliff, integral offset,
noise floor):

```bash
python3 probe_basic/python/test_a6_auto_tune.py
```

covers: happy path (climb → notch → climb → verify → preset), hard-cliff
backoff with notch revert, rescue of an already-ringing baseline,
write-failure revert, revert-failure CRITICAL journaling, cancel restore,
dry-run write-freeze, and preflight blocking. `--sim` on the CLI runs the
same engine + plant interactively.

On hardware, start with `--dry-run` (baseline measurement only), then a
CONSERVATIVE campaign on X with your hand hovering over ESTOP, and compare
the journal's baseline/final CSVs before trusting BALANCED.
