# One-click servo tuning

One button per axis. It moves the axis back and forth over a short stroke,
measures the drive's following error, and raises the gains step by step until
the axis starts to ring. Then it backs off, adds a notch filter if there's a
resonance, checks the result, and saves it as a preset. Every step is written
to a journal, so a failed run still tells you something.

It automates the manual zone ladder in [SERVO_TUNING.md](SERVO_TUNING.md).

---

## Running it

1. Home the machine (or at least be sure of the clearance). Machine on.
2. Servo Tuning tab → click the axis.
3. Pick a profile: **BALANCED** unless you have a reason.
4. **ONE-CLICK TUNE <axis>** → read the confirmation → Yes.
5. Watch the plot with your hand near the E-stop. **CANCEL** stops the motion
   and restores the original gains.
6. When it's done, read the summary and try the axis. If you like it, store it
   to the drive's EEPROM (the tuner only writes RAM).

The same engine runs from the command line:

```bash
python3 scripts/run_auto_tune.py --axis X --sim       # simulated axis: nothing moves, no LinuxCNC needed
python3 scripts/run_auto_tune.py --axis X --dry-run   # real machine: measure only, write nothing
python3 scripts/run_auto_tune.py --axis X --profile balanced
python3 scripts/run_auto_tune.py --axis Z --stroke 5 --feed 3000 --no-notch
```

Exit code 0 means improved, no change, or dry run. 2 means anything else.
Ctrl+C cancels the same way the CANCEL button does.

---

## Safety

- **The axis moves**, relative to where it is now. Default strokes: X 40 mm,
  Y 15 mm, Z 10 mm, A 60° (`DEFAULT_STIMULI` in `a6_auto_tune.py`). When homed
  it picks a direction that fits inside the soft limits. When not homed it goes
  positive and trusts you.
- **A watchdog** samples following error at 1 kHz and aborts the move at 80 %
  of the drive's limit, before the drive faults. During a run the limit (6065)
  is temporarily raised to 2.0 mm, then restored to 0.5.
- **Writes use the same checked path as APPLY**: machine off, write, read
  back, retry, machine on. Only parameters that were read successfully at the
  start are ever written.
- **Revert guarantee.** The starting gains are saved as a
  `pre_one_click_<time>` preset before anything is written. Cancel, an error,
  or a failed final check restores them. If even the restore fails, the
  journal gets a **CRITICAL** entry listing the exact values to put back.
- **Not touched:** LinuxCNC's following-error settings, the 2nd gain set,
  torque filter, feedforward, stiffness, inertia, EEPROM.
- C00.04 (gain mode) is set to manual if it wasn't, so the drive's own
  auto-tuner can't fight it.

---

## What a run does

```
PREFLIGHT → BASELINE → [RESCUE] → SPEED → [NOTCH] → POSITION → [INTEGRAL] → VERIFY → FINALIZE
```

| Step | What happens |
|------|--------------|
| Preflight | Machine on, idle, numpy installed, stroke fits. Fails here = nothing written |
| Baseline | Read all parameters, save the backup preset, measure once |
| Rescue | Only if the axis already rings: try a notch, else soften speed gain up to 3 times |
| Speed | Speed gain (C01.01) × 1.25 per step until unstable or no longer improving (< 3 % twice) |
| Notch | If the unstable step shows a clear resonance at 40–500 Hz, put notch 3 there and retry |
| Position | Position gain (C01.00) × 1.2 per step, aiming for about 2× the speed gain |
| Integral | Tighten C01.02 while it helps. Skipped if the result is already ≥ 30 % better than baseline |
| Verify | Measure the final gains. If unstable, back off 25 % once. If still unstable, keep the best stable step (if it beat baseline by ≥ 1 %) or revert |
| Finalize | Save a `one_click_<time>` preset if it improved |

**Score** = peak error + 2 × RMS error (lower is better). A step is kept only
if it's stable **and** improves the score by at least 3 %.

**"Unstable"** means any of: the move was aborted; the FFT shows a sharp peak
(≥ 4× the noise floor and ≥ 10 % of the RMS); more than 35 % of the energy is
above 40 Hz; or the ring score is ≥ 0.85. Frequencies below
`max(25 Hz, 6 / stroke time)` are ignored, because a short fast stroke
naturally puts energy there. See the lessons below.

To see the scoring visually, `python3 scripts/visualize_auto_tune_scoring.py`
regenerates the charts in [assets/auto_tune_scoring/](assets/auto_tune_scoring/).

| Profile | Speed cap | Position cap | Step | Integral floor |
|---------|-----------|--------------|------|----------------|
| CONSERVATIVE | 120 Hz | 250 rad/s | ×1.15 | 3.0 ms |
| BALANCED | 200 Hz | 400 rad/s | ×1.25 | 3.0 ms |
| AGGRESSIVE | 400 Hz | 800 rad/s | ×1.4 | 1.0 ms |

Speed gain is also capped at ¼ of the torque filter frequency (C01.03), since
the filter's lag destabilises the speed loop.

---

## The journal

Every run writes `logs/tuning/one_click/<time>_<axis>/` (not in git, so copy
out anything worth keeping):

| File | Contents |
|------|----------|
| `journal.md` | Readable log, written as it goes, so a crash still leaves the story up to that point |
| `journal.json` | Same events, machine-readable: every write, every measurement with its FFT peaks |
| `NN_<label>.csv` | Raw following-error samples for each measurement (1 kHz) |

The engine writes what it's *about* to do before doing it, so **the last
entry before a failure tells you what went wrong**.

| Result | Means | Try |
|--------|-------|-----|
| `failed` at preflight | Machine off, program running, no numpy, or no room | Fix it and rerun. Nothing was written |
| `failed`: baseline read failed | `ethercat upload` isn't working | `ethercat slaves -v`; check the udev rule / sudo |
| `failed`: rescue failed | Rings even after softening 3× | Probably mechanical: coupling, wrong inertia, adaptive notch fighting |
| `failed`: SDO write failed | A write didn't read back right | Check the bus. If it's always the same parameter, it may be read-only on your firmware |
| **CRITICAL** | The restore itself failed | Machine off; LOAD the `pre_one_click_*` preset and APPLY |
| `reverted` | Final check unstable, nothing better than baseline to keep | Try CONSERVATIVE, or a longer stroke for cleaner measurements |
| `improved` (after a failed verify) | Kept the best stable step | Try it. The journal says why verify failed |
| `no-change` | Nothing beat baseline by 3 % | Baseline may already be good. Try AGGRESSIVE |
| Watchdog trips on the first step | Already close to the edge | Start from a softer preset |

Engine bugs can usually be reproduced in the simulator
(`a6_auto_tune_sim.py` has knobs for resonance, instability, noise). Tests:
`python3 probe_basic/python/test_a6_auto_tune.py`.

---

## What it deliberately doesn't do

| Not automated | Why |
|---------------|-----|
| Torque filter, feedforward, 2nd gain set | Trade-offs that need judgment. Use the AI-assisted loop |
| Inertia | Needs its own measurement: [INERTIA_TUNING.md](INERTIA_TUNING.md) |
| Storing to EEPROM | Kept manual for safety |
| More than one notch | Notches 1–2 belong to the drive's adaptive notch; a second failed notch usually means mechanics |

Limits: resonances above ~500 Hz are invisible to it (1 kHz sampling). It
tunes in one direction per run, which matters for Z because of gravity.

---

## Lessons learned

Failed runs are data. Add a row when a run teaches you something.

| Date | Lesson | Evidence |
|------|--------|----------|
| 2026-07-12, X | The final check rejected a ~49 % better tune because a harmless share of high-frequency energy crossed 35 %. Fix: the verify check now compares against baseline, integral is skipped when already ≥ 30 % better, and the best stable step is kept instead of reverting | `one_click_best_20260712` preset; `test_verify_fail_keeps_best` |
| 2026-07-12, Y | AGGRESSIVE reached 164.6 Hz / 60 rad/s / 3.5 ms (~39 % better). Verify hit an error, but the best stable step was kept and validated on the machine | Y `one_click_best_20260712` |
| 2026-07-12, sim | Short fast strokes (Y: 0.09 s per leg) put normal tracking-error harmonics at 30–60 Hz that look like resonance. The check called a healthy axis unstable and "rescued" it into mush. Fix: ignore below `6 / leg time`, and require a peak to carry ≥ 10 % of RMS | `test_short_stroke_gate_not_fooled` |
