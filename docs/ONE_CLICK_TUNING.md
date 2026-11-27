# One-click servo tuning

One button per axis. It moves the axis back and forth over a short stroke,
measures the drive's following error and torque, and raises the gains step by
step until the axis starts to ring. Then it settles at a fixed stability margin
below that point, adds a notch filter if there's a resonance, checks the
result (including noise at standstill), and saves it as a preset. Every step is
written to a journal, so a failed run still tells you something.

**Engine v2 (2026-11-27).** The review of v1 found that the Python sampler ran
at 250–750 Hz instead of 1 kHz, so every FFT frequency (and any notch) was in
the wrong place, and that the "back off one step" rule left only ~2 dB of gain
margin. v2 captures in realtime, uses a real margin, measures run-to-run noise,
and stops on the first machine fault. See *What changed in v2* below.

It automates the manual zone ladder in [SERVO_TUNING.md](SERVO_TUNING.md).

---

## Running it

1. Home the machine (or at least be sure of the clearance). Machine on.
   Fix mechanics first: tuning a loose ball nut tunes around the play.
   Optional, once per axis: `python3 scripts/test_live_gain_write.py --axis Y`.
   If it prints `LIVE OK` for all three gains, add `--live-writes` (CLI) so the
   tuner stops turning the machine off and on for every write.
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
python3 scripts/run_auto_tune.py --axis Y --live-writes          # only after test_live_gain_write.py passed
python3 scripts/run_auto_tune.py --axis Y --margin 0.5 --repeats 5
python3 probe_basic/python/rt_capture.py Y 1.0                    # bench check: 1 s realtime capture at rest
```

Exit code 0 means improved, margin-limited, no change, or dry run. 2 means anything else.
Ctrl+C cancels the same way the CANCEL button does.

---

## Safety

- **The axis moves**, relative to where it is now. Default strokes: X 40 mm,
  Y 15 mm, Z 10 mm, A 60° (`DEFAULT_STIMULI` in `a6_auto_tune.py`). When homed
  it picks a direction that fits inside the soft limits. When not homed it goes
  positive and trusts you.
- **Realtime capture.** `sampler.0` (REALTIME CAPTURE block at the end of
  `custom.hal`) records 60F4 following error, 6077 torque, 606C velocity and
  the commanded position for all four axes every servo cycle; `rt_capture.py`
  reads it with `halsampler`. A capture that overran or returned the wrong
  number of samples is rejected, never used. Without the sampler the tuner
  refuses to run (`--allow-python-sampler` runs the old poller, with a warning).
- **Two watchdogs.** The hard one is the drive's own 6065 window, raised to
  **1.0 mm** for the run (was 2.0) and restored to 0.5 in a `finally` block.
  The soft one aborts the MDI move at 80 % of that, checked every 10 ms (was
  100 ms, ~17 mm of travel at F10000).
- **Stops on a machine fault.** An RCS error, the machine dropping out of ON,
  or a drive fault ends the campaign at once and reverts. (v1 kept writing
  gains and "verifying" after a fault: Z run 2026-07-16.)
- **Settles before moving.** After each machine OFF→ON write, the axis must
  hold |FERR| ≤ 0.02 mm for 0.3 s within 5 s, or the run stops. Avoided
  entirely with `--live-writes`.
- **Torque guard.** A step whose torque peak reaches 250 % rated counts as
  unstable (a clipped torque hides instability). Placeholder until the drive's
  real torque limit is set.
- **Drive opmode.** On the drive-homing branch (`lcec.0.N.opmode-display`
  exists) the drive must be in CSP (8), or preflight fails.
- **Writes use the same checked path as APPLY**: machine off, write, read
  back, retry, machine on. Only parameters that were read successfully at the
  start are ever written.
- **Revert guarantee.** The starting gains are saved as a
  `pre_one_click_<time>` preset before anything is written. Cancel, an error,
  or a failed final check restores them. If even the restore fails, the
  journal gets a **CRITICAL** entry listing the exact values to put back.
- **Not touched:** LinuxCNC's following-error settings, the 2nd gain set,
  torque filter, feedforward, stiffness, inertia, EEPROM. (Drive-homing work
  found that some A6 SDO writes persist; restore from the `pre_one_click_*`
  preset if a run was interrupted by a power loss.)
- C00.04 (gain mode) is set to manual if it wasn't, so the drive's own
  auto-tuner can't fight it.

---

## What a run does

```
PREFLIGHT → BASELINE → [RESCUE] → SPEED → [NOTCH] → POSITION → [INTEGRAL] → [FEEDFORWARD] → VERIFY → [VERIFY AT OTHER POSITIONS] → FINALIZE
```

| Step | What happens |
|------|--------------|
| Preflight | Machine on, idle, numpy installed, stroke fits, drive in CSP. Reads the drive torque limit 0x6072 and sets the torque guard to min(250 %, 0.8 × that limit). Fails here = nothing written |
| Baseline | Read all parameters, save the backup preset, measure **3 times** (spread sets the improvement bar), record standstill noise |
| Rescue | Only if the axis already rings: try a notch, else soften speed gain up to 3 times |
| Speed | Speed gain (C01.01) × 1.25 per step until unstable or no longer improving. **When a step rings, settle at margin × that gain** (balanced 0.55, ≈5 dB) and re-measure |
| Notch | If the unstable step shows a clear resonance at 40–500 Hz, put notch 3 there and retry |
| Position | Position gain (C01.00) × 1.2 per step toward ~2× the speed gain; same margin rule |
| Integral | Tighten C01.02 while it helps. Always runs in v2 (it matters for cutting loads) |
| Feedforward | Only if the drive's torque FF source (C01.16) is already on: torque FF % (C01.17) × 1.15 per step within 50–200 %, then ÷ 1.15 if going up did not help. Kept when the score improves ≥ 3 %. The tuner never switches FF on. `--no-ff` skips it |
| Verify | Measure the final gains plus 1 s at standstill. If unstable, back off 25 % once. If still unstable, keep the best stable step **only if its re-check fails for nothing worse than the HF-energy rule**, else revert |
| Verify at other positions | Only with `--verify-at -100,100` (offsets from the start position). Needs the axis homed; offsets that would put the stroke past a soft limit are skipped, and Z only accepts positive (upward) offsets. Moves with `G53 G1` at half the stimulus feed, re-measures, and always goes back to the start. A failure anywhere reverts to baseline |
| Finalize | Save a `one_click_<time>` preset if it improved or was margin-limited |

**Score** = peak error + 2 × RMS error (lower is better). A step is kept only
if it's stable **and** improves the score by at least max(3 %, 2 × the
baseline's run-to-run spread), capped at 15 %. A step above the margin can
never become the "best" step.

**Sensitivity |S|.** Every measurement also computes |S(f)| = |FERR / command|
from the captured joint command and drive FERR (`frf_analysis.py`, Welch H1,
only coherent bins). Its peak **Ms** bounds the loop margins: gain margin ≥
Ms/(Ms−1), phase margin ≥ 2·asin(1/(2Ms)). Ms 2.0 means at least 6 dB / 29°.
The journal shows it as `sensitivity` on each measurement. It is report-only by
default; `--ms-max 2.0` makes any step above it count as unstable. Short
strokes may not excite enough frequencies, in which case it says "only N
coherent bins" and has no effect.

**"Unstable"** means any of: the move was aborted; the FFT shows a sharp peak
(≥ 4× the noise floor and ≥ 10 % of the RMS); more than 35 % of the energy is
above 40 Hz; the ring score is ≥ 0.85; torque reached the guard; or (verify
only) standstill torque RMS > 5 % or standstill FERR RMS > 2 µm. Frequencies below
`max(25 Hz, 6 / stroke time)` are ignored, because a short fast stroke
naturally puts energy there. See the lessons below.

To see the scoring visually, `python3 scripts/visualize_auto_tune_scoring.py`
regenerates the charts in [assets/auto_tune_scoring/](assets/auto_tune_scoring/).

| Profile | Speed cap | Position cap | Step | Integral floor | Margin |
|---------|-----------|--------------|------|----------------|--------|
| CONSERVATIVE | 120 Hz | 250 rad/s | ×1.15 | 3.0 ms | 0.50 (6 dB) |
| BALANCED | 200 Hz | 400 rad/s | ×1.25 | 3.0 ms | 0.55 (5 dB) |
| AGGRESSIVE | 400 Hz | 800 rad/s | ×1.4 | 1.0 ms | 0.65 (3.7 dB) |

Expect v2 to land **lower** than v1 presets on the same axis: v1 kept the last
stable step (~0.8 × the ringing gain), v2 keeps 0.55 ×. That is the point:
air-move tuning under-excites the axis, and cutting does not.

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
| `failed`: realtime capture not loaded | `sampler.0` missing | Restore the REALTIME CAPTURE block in `custom.hal`, restart LinuxCNC |
| `failed`: measurement invalid (overran / sample count) | The FIFO overflowed or `halsampler` stalled | Rerun; if repeatable, raise `depth=` in `custom.hal` |
| `failed`: machine fault during … | RCS error, machine OFF or drive fault mid-move | Read the drive panel code, clear it, check clearance. The gains were reverted |
| `failed`: did not settle after re-enable | Axis moved after machine OFF→ON (Z sag?) | Park Z low / supported, or use `--live-writes` if the test passed |
| `failed`: opmode is 6, not 8 | A drive home was interrupted (drive-homing branch) | Home again or power-cycle the drive |
| `failed`: still unstable at the margin gain | Rings well below where the ladder found it | Mechanics, notch, or inertia ratio |
| `margin-limited` | Baseline was already within the margin; gains were lowered | Keep it. The air-move score is worse, the stability margin is better |
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
| Torque filter, speed feedforward, FF filters, switching FF on, 2nd gain set | Trade-offs that need judgment. Use the AI-assisted loop |
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
| 2026-11-27, review | v1 "1 kHz" sampler really ran at 250–300 Hz (X) and 650–750 Hz (Y): sample counts vs stimulus time in the July journals. FFT frequencies were wrong by 1.4–4×. Fix: realtime `sampler.0` capture, true fs passed to the FFT | `test_true_fs_used` |
| 2026-11-27, review | Z run 2026-07-16: first move after a write tripped at 1.0 mm in 13 samples; every later move returned RCS_ERROR and the engine kept writing for 1.4 s. Cause not proven (Z sag on re-enable vs instability). Fix: settle check, stop on fault, `--live-writes` option | `test_machine_fault_stops` |
| 2026-11-27, review | "Back off one step" left ~2 dB gain margin, measured with unloaded moves. Fix: margin × first ringing gain; best steps above the margin are discarded | `test_happy_path`, `test_verify_fail_keeps_best` |
| 2026-07-12, sim | Short fast strokes (Y: 0.09 s per leg) put normal tracking-error harmonics at 30–60 Hz that look like resonance. The check called a healthy axis unstable and "rescued" it into mush. Fix: ignore below `6 / leg time`, and require a peak to carry ≥ 10 % of RMS | `test_short_stroke_gate_not_fooled` |

---

## What changed in v2 (2026-11-27)

| v1 | v2 |
|----|----|
| Python thread "at 1 kHz" (really 250–750 Hz), FFT assumed 1 kHz | Realtime `sampler.0`, one row per servo cycle, true fs to the FFT; overruns and bad counts reject the measurement |
| 6065 raised to 2.0 mm; soft watchdog checked every 100 ms | 6065 at 1.0 mm; soft watchdog every 10 ms |
| Faults classified as "unstable", ladder carried on | First machine fault stops the run and reverts |
| Moved right after machine OFF→ON | Waits for the axis to settle; `--live-writes` skips the cycle |
| Settled one step below ringing (~0.8×) | Settles at margin × first ringing gain (0.5–0.65) |
| One baseline, fixed 3 % bar | 3 baselines, bar = max(3 %, 2 × spread) |
| Integral skipped when ≥ 30 % better | Integral always runs |
| No torque check, no standstill check | Torque guard; standstill torque/FERR RMS at verify |
| Keep-best on any verify failure | Keep-best only if its re-check fails for HF energy alone |
| 6065 window set through hardware calls even in `--sim` | Through the IO layer (sim never touches EtherCAT) |

**Engine 2.1 (same day):** sensitivity |S| on every measurement, torque FF
phase, torque guard from 0x6072, optional multi-position verify
(`test_feedforward_phase`, `test_drive_torque_limit_guard`,
`test_multi_position_verify`, `test_sensitivity_estimator`).

**Still not done, on purpose:**

- **Chirp/PRBS injection.** A dedicated broadband command needs either a
  HAL summer on `joint.N.motor-pos-cmd` → drive target (changes the command
  path that `cia402_homecomp` on `dev-drive-homing` also sits on) or a G-code
  generated sweep (the planner smooths it away above a few Hz). |S| from the
  normal strokes covers the low band where margin problems show up.
- **Load-rejection test via 0x60B2 (torque offset).** Needs 0x60B2 added to
  the RxPDO in `ethercat-conf.xml` — the same PDO map the drive-homing branch
  rewrites. Do it after that branch is merged, not before.

**Drive homing compatibility.** The capture taps signals that exist unchanged
on `dev-drive-homing` (lcec 1.49 `cia402` + `cia402_homecomp`), and neither
branch touches the other's files, so they merge cleanly. Homing uses its own
torque limit (C10.30), separate from the tuner's guard.
