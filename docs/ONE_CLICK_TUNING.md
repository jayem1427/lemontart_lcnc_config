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

**Engine 2.1 (same day)** adds a measured stability margin (sensitivity peak
**Ms**) on every move, a torque-feedforward phase, a torque guard taken from
the drive's own limit, and optional re-checks at other positions along the
axis. See *Reading the results* below.

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
6. When it's done, read the summary and try the axis. There's nothing to
   save: the drive stores every SDO write in EEPROM itself (C13.10 = 1, see
   [SERVO_TUNING.md](SERVO_TUNING.md#three-rules)). If you don't like it, LOAD
   the `pre_one_click_*` preset and APPLY.

The same engine runs from the command line:

```bash
python3 scripts/run_auto_tune.py --axis X --sim       # simulated axis: nothing moves, no LinuxCNC needed
python3 scripts/run_auto_tune.py --axis X --dry-run   # real machine: measure only, write nothing
python3 scripts/run_auto_tune.py --axis X --profile balanced
python3 scripts/run_auto_tune.py --axis Z --stroke 5 --feed 3000 --no-notch
python3 scripts/run_auto_tune.py --axis Y --live-writes          # only after test_live_gain_write.py passed
python3 scripts/run_auto_tune.py --axis Y --margin 0.5 --repeats 5
python3 scripts/run_auto_tune.py --axis X --verify-at=-100,100   # re-check at two more spots (homed only)
python3 scripts/run_auto_tune.py --axis Y --ms-max 2.0           # reject any step with Ms above 2.0
python3 scripts/run_auto_tune.py --axis Z --no-ff                # leave torque feedforward alone
python3 probe_basic/python/rt_capture.py Y 1.0                    # bench check: 1 s realtime capture at rest
```

| Flag | Default | What it does |
|------|---------|--------------|
| `--sim` | off | Simulated axis. Nothing moves; no LinuxCNC needed |
| `--dry-run` | off | Real moves and measurements, no SDO writes |
| `--profile` | balanced | conservative / balanced / aggressive (table below) |
| `--stroke`, `--feed`, `--cycles` | per axis | Override the test move |
| `--no-notch` | off | Never place notch 3 |
| `--no-presets` | off | Don't save `pre_one_click_*` / `one_click_*` presets |
| `--live-writes` | off | Write gains with the drive enabled. Only after `test_live_gain_write.py` printed `LIVE OK` |
| `--margin` | 0.5 / 0.55 / 0.65 | Settle at this × the first ringing gain |
| `--repeats` | 3 | Baseline repeats; their spread sets the improvement bar |
| `--no-ff` | off | Skip the feedforward phase |
| `--ms-max` | 0 (report only) | Steps with a measured Ms above this count as unstable |
| `--verify-at` | none | Comma list of offsets (mm, ° for A) from the start position to re-verify at. Use `=` before a negative first value: `--verify-at=-100,100` |
| `--allow-python-sampler` | off | Old ~300 Hz poller when `sampler.0` is missing. FFT frequencies are wrong; don't trust notches |
| `--yes` | off | Skip the confirmation prompt |

The tab's ONE-CLICK button uses the defaults: feedforward phase on, Ms
report-only, no extra positions. `--ms-max` and `--verify-at` are CLI-only
for now.

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
- **Torque guard.** A step whose torque peak (6077) reaches the guard counts as
  unstable, because a drive sitting on its torque limit can't show you it's
  ringing. The guard is the lower of 250 % rated and **80 % of the drive's torque
  limit 0x6072**, read at preflight (the journal shows
  `drive torque limit 0x6072 = …% -> guard …%`). If 0x6072 can't be read it
  stays at 250 %. Lowering the drive's torque limit (step 4 of the plan) therefore
  lowers the guard automatically.
- **Multi-position moves** (`--verify-at` only). The tuned axis only, `G53 G1` at
  half the test feed, absolute targets = start + offset. Refused unless the axis
  is homed; offsets whose stroke would cross a soft limit are skipped; Z refuses
  negative (downward) offsets. It always returns to the start position, even
  after an error.
- **Drive opmode.** On the drive-homing branch (`lcec.0.N.opmode-display`
  exists) the drive must be in CSP (8), or preflight fails.
- **Writes use the same checked path as APPLY**: machine off, write, read
  back, retry, machine on. Only parameters that were read successfully at the
  start are ever written.
- **Revert guarantee.** The starting gains are saved as a
  `pre_one_click_<time>` preset before anything is written. Cancel, an error,
  or a failed final check restores them. If even the restore fails, the
  journal gets a **CRITICAL** entry listing the exact values to put back.
- **Touched:** speed gain, position gain, integral, notch 3, gain mode, and
  torque FF % (only when the drive's torque FF source is already on).
- **Not touched:** LinuxCNC's following-error settings, the 2nd gain set,
  torque filter, speed feedforward, FF source and FF filters, stiffness,
  inertia. (Every write persists: the drive stores SDO writes in EEPROM,
  C13.10 = 1. Restore from the `pre_one_click_*` preset if a run was
  interrupted by a power loss.)
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
| Baseline | Read all parameters, save the backup preset, make **one unscored warm-up move** (`baseline_warmup`, default 1), then measure **3 times** (spread sets the improvement bar), record standstill noise |
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
only) standstill torque RMS > 5 % or standstill FERR RMS > 2 µm. The
standstill torque RMS is taken **about its mean**: a vertical axis holds a
steady gravity torque (Z ≈ 12 %) that isn't noise. The journal shows both,
e.g. `torque rms 0.25% (about mean 12.0%)`. Frequencies below
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

Every run writes `logs/tuning/one_click/<time>_<axis>/` (committed to git:
`.gitignore` lets the CSV, JSON and MD through):

| File | Contents |
|------|----------|
| `journal.md` | Readable log, written as it goes, so a crash still leaves the story up to that point |
| `journal.json` | Same events, machine-readable: every write, every measurement with its FFT peaks |
| `NN_<label>.csv` | Raw following-error samples for each measurement, at the true servo rate (`fs_hz` in the JSON) |

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
| `reverted`: unstable at offset ±N | The tune held at the start but rang elsewhere along the axis | Tune at the worst spot (start the run there), or check that stretch of the screw / ways |
| Steps flagged `Ms … > 2` | Only with `--ms-max`: the measured margin is too thin | Expected near the top of the ladder. If even baseline trips it, the axis was already marginal |
| `feedforward skip: source is off` | C01.16 torque FF source is 0 | Not an error. Turn it on in the table (1 = internal) if you want the phase |
| Torque guard trips early after you lowered 0x6072 | Guard = 0.8 × the new limit | Intended. Raise the limit or shorten/slow the test move |
| `improved` (after a failed verify) | Kept the best stable step | Try it. The journal says why verify failed |
| `no-change` | Nothing beat baseline by 3 % | Baseline may already be good. Try AGGRESSIVE |
| Watchdog trips on the first step | Already close to the edge | Start from a softer preset |

Engine bugs can usually be reproduced in the simulator
(`a6_auto_tune_sim.py` has knobs for resonance, instability, noise). Tests:
`python3 probe_basic/python/test_a6_auto_tune.py`.

---

## Reading the results

### Ms, the measured stability margin

Following error is the command filtered by the loop's **sensitivity
function** S(f): `FERR(f) = S(f) × CMD(f)`. The realtime capture records both
signals, so each measurement estimates |S(f)| = |FERR / CMD| at every frequency
the test move contains (Welch averaging, `frf_analysis.py`). It only keeps
frequencies where the two signals are clearly related (coherence ≥ 0.7). The
**peak of |S| is Ms**. It is the standard single-number robustness measure,
and it bounds both margins whatever the mechanics are:

| Ms | Gain margin at least | Phase margin at least | Reads as |
|----|----------------------|-----------------------|----------|
| 1.2 | 15.6 dB | 49° | Very calm, probably leaving stiffness on the table |
| 1.4 | 10.9 dB | 42° | Comfortable |
| **2.0** | **6.0 dB** | **29°** | Usual industrial upper limit |
| 2.5 | 4.4 dB | 23° | Lightly damped; will overshoot and ring on hard moves |
| > 3 | < 3.5 dB | < 19° | Close to oscillating at f(Ms) |

The journal line looks like
`Ms 1.62 @ 48 Hz (GM>=8.2 dB, PM>=36 deg, bw~19 Hz; 31 coherent bins)`.
**f(Ms)** is where the loop is weakest, and is often where it will ring.
**bw** is roughly where the loop stops rejecting following error (|S| first
reaches 0.707). Higher bw means stiffer tracking.

How to use it:

- **Compare steps, not absolute values.** As the ladder raises gains, Ms
  rises and its frequency moves up. A sudden jump marks where margin goes.
- **It complements the ringing check.** The FFT check sees ringing that has
  already started; Ms sees the margin before any ringing starts.
- **Limits.** The normal test stroke is a trapezoid, so most of its energy is
  below ~50 Hz. If it reports "only N coherent bins", the move didn't excite
  enough frequencies. A longer stroke or more cycles helps. It says nothing
  about frequencies the move didn't contain (that's what chirp injection would
  add, see below). Air moves give a slightly optimistic Ms, because cutting
  adds load.
- **Gate.** Report-only by default. `--ms-max 2.0` treats any step above it
  as unstable. Try report-only for a few runs first, to see where your axes sit.

### Torque feedforward

Feedforward sends the torque the commanded acceleration *will* need straight
to the current loop, instead of waiting for following error to build up and the PID
to react. Get it right and the error during acceleration mostly disappears without
raising any feedback gain, so it costs no stability margin. 100 % means
"inertia exactly as the drive believes it is". Above that it over-predicts:
the axis leads the command and overshoots at the end of the ramp.

The phase starts from the current value (C01.17), tries × 1.15 steps up to
200 %, and keeps each one that improves the score ≥ 3 %. If the first step up
doesn't help, it tries ÷ 1.15 steps down to 50 %. Expect it to settle near
100 % when the inertia ratio (C00.06) is right. **A result far from 100 %
usually means the inertia ratio is wrong**: fix that, don't chase it with FF.
The July presets had torque FF at 120–125 % on X/Y and 200 % on Z, which
suggests Z's inertia ratio is low, or that FF is covering for gravity.

### Multi-position verify

A ball screw isn't the same everywhere along its length. Near the far end the unsupported
length is longest, so the first screw mode is lowest, and a tight spot
or a lube patch changes friction. `--verify-at` re-runs the verify move at the
offsets you give and reverts if any of them fails. A good set for X is the
start ± a third of the travel. On Z, start low and use positive offsets only.

---

## What it deliberately doesn't do

| Not automated | Why |
|---------------|-----|
| Torque filter, speed feedforward, FF filters, switching FF on, 2nd gain set | Trade-offs that need judgment. Use the AI-assisted loop |
| Inertia | Needs its own measurement: [INERTIA_TUNING.md](INERTIA_TUNING.md) |
| Choosing what reaches EEPROM | The drive stores every write itself (C13.10 = 1), including each ladder step. The backup preset is the undo. Writing a lot of parameters often can raise ALF1.3 ("too frequent writing of EEPROM by host controller SDO"); not seen so far |
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
| 2026-11-27, Z | Standstill check failed every Z tune: "torque rms 12 % > 5 %". Peak was 13–15 % against RMS 12–13 %, so it was steady gravity hold, not hiss (FERR at rest 0.1 µm). The backoff "failed" too and the tuner fell back to an early step. Fix: torque RMS about the mean (`_ac_rms`); verify then read 0.25 % about a 12 % mean | Z `20261127_233710_Z` vs `20261127_234614_Z`; `test_rest_gate_ignores_holding_torque` |
| 2026-11-27, Z | The campaign's first move spiked (Z: 405 µm, 198 % torque; the next two baselines 49 µm), so the baseline spread read 416 % and every step needed 15 % improvement. The speed ladder stalled at 26 Hz. Fix: one unscored warm-up move before the baselines; spread then 2.0 %, bar 4.1 % | `01_warmup_1.csv` in `20261127_234614_Z`; `test_warmup_absorbs_first_move_spike` |
| 2026-11-27, Z | The fixed run passed every check (34.4 Hz / 82.5 rad/s, FERR 1.9× better) but **whined** audibly. Reverted to 26 / 50. The tuner can't hear above 500 Hz (1 kHz sampling) and only gates standstill torque ripple. On Z, listen before keeping a result | Z presets `one_click_20261127_234730` (don't use), `pre_one_click_20261127_233712` (in use) |
| 2026-11-27, Y | First Y run tripped the **A** drive (0x8611 following error) 0.4 s after the first gain write: A is mechanically unconnected and its 0.5° window was too tight for the machine OFF→ON cycle. Fix: A's 6065 widened to 10° while unconnected | `20261127_232720_Y`; commit "Widen A drive following-error window" |
| 2026-11-28, all | The drive stores every SDO write in EEPROM (C13.10 = 1). The tuner's writes were never "RAM only" as documented; each ladder step persisted | `ethercat upload -p N -t uint16 0x2013 0x11` → 1 on all four drives |
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

**First machine runs, 2026-11-27:** X 3.2× and Y 1.7× lower RMS following
error, Z 1.9× but whined and was reverted. Two fixes came out of the Z runs:
the warm-up move and the mean-removed standstill torque (see Lessons). Results
table and plots: [SERVO_TUNING.md](SERVO_TUNING.md#first-machine-runs-of-engine-v21-2026-11-27).

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
