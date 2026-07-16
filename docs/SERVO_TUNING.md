# Manual Servo Tuning (Boiled Down)

**Goal:** low following error (ferror) without buzz/ring.  
**Tools:** scope on **actual position deviation**, same test move every time, push/tap test for stability.

Your drives are a **cascaded position → speed → torque** loop. Map:

| Drive param | Role | Frequency zone |
|---|---|---|
| Torque filter / notch | Kill HF noise & resonance | Highest |
| Speed loop gain | Inner stiffness / damping | High |
| Speed loop integral | Kill speed/steady lag (lower ms = stronger) | Mid-low |
| Position loop gain | Outer tracking / ferror | Mid |
| Feedforward (if available) | Cut lag without raising loop gains | Outside the loop |

---

## Phase 0 — Prep

1. Axis safe, brakes/counterbalance correct, coupling tight.
2. **Fixed to 1st gain set** while learning (no gain switchover yet).
3. Soft starting gains. Scope **ferror**.
4. Pick one repeatable move (real accel/speed you’ll use).

---

## Phase 1 — Inertia

1. Run drive **inertia / load ratio** estimate (graphical or auto inertia).
   On this machine: Servo Tuning → panel **INERTIA** → **BEGIN INERTIA
   AUTO-TUNE** (Yaskawa Sigma II Tp−Tf — see `GRAPHICAL_INERTIA_TUNE.md`).
   Use F8000 / ~50 mm / ~180 ms ramp on linear axes (always clamps;
   C00.06 writes only when quality is **good**).
   Alternate: drive-internal F30.10 on branch `cursor/internal-inertia-tune-f9d7`
   (`INERTIA_TUNE.md`).
2. Write the ratio down (C00.06 is written automatically on success). Bad
   inertia estimate makes every later gain lie.
3. If ratio is huge (load >> motor), expect softer gains + more filter/notch need.
4. Switch back to **GAINS** before Phase 3 / one-click.

---

## Phase 2 — Rigidity (coarse start)

1. Use drive **rigidity / stiffness level** to land in the ballpark.
2. Higher = faster / lower ferror, but easier to vibrate.
3. Stop at the highest level that is **stable at rest** and only mildly reactive to a light push.
4. This only gets you close — then hand-tune.

---

## Phase 3 — Zone-based hand tune (preferred)

Tune **high frequency → low frequency**. One knob at a time. Re-scope after each change.

### Zone A — High frequency (filters first if it already sings)

- If it buzzes/rings at rest or after a tap: lower **torque filter cutoff**, or set a **notch** at the ring frequency.
- Don’t chase ferror with filters; just remove the zing.

### Zone B — Speed loop (inner)

1. Hold **position gain** modest; **integral** soft (higher ms).
2. Raise **speed loop gain** until velocity tracks cleanly and ferror peaks shrink.
3. Stop when a **push/tap** starts a sustained buzz → back off **~20%**.
4. Then strengthen **speed integral** a little (lower ms) to pull down steady offset / lag. Keep integral as weak as you can while still killing DC error.

### Zone C — Position loop (outer)

1. Run your real move. Watch ferror.
2. Raise **position loop gain** until peak ferror drops.
3. Keep a sane ratio (often **position ≈ 2× speed** in these units: e.g. 100 rad/s with ~50 Hz).
4. If overshoot/ring grows, back off position **~20%**, or revisit speed gain / filter.

### Zone D — Steady-state only

- Resting ferror offset (like Z sitting at 8–26): nudge integral (lower ms) or check gravity/bias.
- Don’t use big integral to hide bad position/speed gains.

---

## Phase 4 — Disturbance / 2nd gain set (optional)

Only after 1st set is solid.

1. If using **position-deviation switchover**, make **2nd set close to 1st** — not a huge jump.
2. Soften 2nd set for pushes/bumps: lower **2nd speed gain** and **2nd torque filter** first.
3. Push test: short thud OK; sustained buzz = still too hot.
4. Or leave **Fixed to 1st** if you don’t need switching.

---

## Phase 5 — Polish

1. **Feedforward** (vel/accel) if the controller has it — often cuts peak ferror more than another gain bump.
2. Notch / vibration suppression for leftover natural ring.
3. Test both directions, real loads, and the moves you actually run.

---

## Quick decision table

| Symptom | Change |
|---|---|
| Big ferror during accel, smooth | ↑ position, then ↑ speed (keep ratio) |
| Steady offset at rest | ↓ integral time (stronger I), lightly |
| Buzz when pushed / after move | ↓ speed gain and/or torque filter; check 2nd set |
| High-pitch natural ring | torque filter down, then notch |
| Soft / laggy after quieting | ↑ speed a little, then position; don’t open filter wide again |

---

## One-page order

```
1. Inertia estimate
2. Rigidity level → highest stable
3. Fix to 1st gain set
4. Zone tune: filter/notch → speed gain → speed integral → position gain
5. Same move + ferror scope every step
6. Push/tap test every step
7. Optional: 2nd set for disturbance (keep it close/softer)
8. Feedforward + notch polish
```

**Rule of thumb:** raise tracking gains for ferror, but treat jagged ringing as a hard stop — back off and filter/notch instead of stacking more gain.

---

## Semi-auto (plot → LLM)

On the machine: Servo Tuning → **START PLOT** + frozen NGC → **COPY PLOT** + **COPY TUNING** (see `SEMI_AUTO_TUNING.md`).  
Paste into an LLM loaded with `SERVO_TUNING_LLM.md`, then APPLY suggested gains yourself.
