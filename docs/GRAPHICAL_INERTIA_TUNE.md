# Graphical inertia auto-tune (physics fit + Yaskawa cross-check)

Inertia identification for this mill. Servo Tuning **INERTIA** moves the edit
axis, samples drive torque + velocity, solves for load/motor inertia ratio,
and writes **C00.06** (A6 equivalent of Sigma II **Pn103**).

Kept **separate** from one-click gain tuning and from the drive-internal
**F30.10** path (`docs/INERTIA_TUNE.md` on branch
`cursor/internal-inertia-tune-f9d7`). Order of work:

1. **INERTIA** panel → BEGIN → C00.06 written (only if quality is **good**)  
2. Switch to **GAINS** → **ONE-CLICK TUNE**

| Where | What |
|-------|------|
| Servo Tuning → panel **INERTIA** | Settings + BEGIN / CANCEL |
| `probe_basic/python/a6_graphical_inertia.py` | Math + campaign (v0.6.1) |
| `config/tuning/inertia_settings.json` | Saved per-axis knobs (auto-written) |
| `logs/tuning/graphical_inertia/` | Journals + `trace.csv` |
| `test_a6_graphical_inertia.py` | Unit tests (no hardware) |
| `docs/reference/Sigma II Parameter Calculator Rev 2.42.xls` | Cross-check worksheet |

**Related:** `SERVO_TUNING.md` (Phase 1), `ONE_CLICK_TUNING.md` (gains only),
`A6_TUNING.md` (SDO map).

---

## Why v0.6 replaced the two-point rule

The A6-EC PDOs **sample-and-hold**: 606C velocity holds for 17–36 ms and 6077
torque for up to ~25 ms at our 1 kHz journal rate. Any method that computes
\(\alpha = \Delta V/\Delta t\) from two cursor points — including the classic
Sigma II worksheet — divides by a ΔV that may sit entirely inside one hold.
On 37 real traces from 2026-07-14/15 the two-point answers swung from −100%
to +104 000% depending on windowing. **This is a hardware artifact, not an
operator error.**

The v0.6 estimator never differentiates the velocity. It fits the rigid-body
model

\[
J\dot\omega = T - F_c\,\mathrm{sgn}(\omega) - b\,\omega
\]

by **integrating the measured torque** through the model and choosing
\((J, F_c, b)\) so the simulated velocity reproduces the measured profile
(decimated to 250 Hz, Nelder–Mead on the RMS velocity error). Integration is
immune to the stair-stepping. Then:

\[
J_L = J_{\mathrm{total}} - J_M,\qquad
\mathrm{ratio\%} = 100\cdot\frac{J_L}{J_M}\;\rightarrow\;\text{C00.06}
\]

Replayed over every good recipe trace on file, the fit clusters X at
**~100% (IQR 85–120%)** with run-to-run agreement of ±15% — consistent with
the manual feel of ~120%. The two-point Sigma II analysis still runs as a
**cross-check** and draws the Tp/Tf/α-window overlays when it succeeds.

---

## Operator recipe

1. Look up **motor rotor inertia** \(J_M\) and **rated torque** on the datasheet
   (400 W XYZ: \(J_M=5.9\times10^{-5}\,\mathrm{kg\cdot m^2}\), \(1.27\,\mathrm{N\cdot m}\)).
2. Servo Tuning → edit axis → **INERTIA**.
   Live plot shows **torque % + velocity**. Prefer **cycles = 1**.
3. Linear axes: **stroke ~40**, feed **F8000–F10000**, **torque limit 0**.
4. Home, park **mid-travel**, machine ON.
5. **BEGIN INERTIA AUTO-TUNE** → confirm.
   - Campaign lowers `ini.*.max_acceleration` so 0→feed takes ~100 ms
     (physics fit prefers a softer ramp than the old two-point rule).
   - The physics fit runs on the whole capture; torque-limit clamps are
     unnecessary (they caused aborts/short strokes in testing — leave 0).
6. If quality is **good**, C00.06 is written (RAM). Marginal/bad estimates are
   shown but **not** written.
7. Switch to **GAINS** → **ONE-CLICK**.

Factory C00.06 default is **100%** — that is not a measured load ratio.
Manual feel on this X axis settled near **~120%**; the physics fit lands
**~85–120%** across good runs.

---

## Quality gates (write only if good)

| Gate | Threshold | Why |
|------|-----------|-----|
| Velocity fit error (cruise-weighted) | ≤ 18% of peak → good; ≤ 27% still good if J-sensitivity ≥ 12% and ratio in 80–200%; ≤ 28% marginal; > 40% reject | Hard ramps leave PDO stair noise; don’t throw away a well-identified J |
| J-sensitivity | ≥ 8% (good), ≥ 4% (marginal), else reject | Perturbing J ±40% must worsen the fit — otherwise friction dominates and J is unidentifiable |
| Peak speed (linear) | ≥ 500 rpm good, ≥ 400 rpm to analyze at all | Slow moves (F2000) are friction-dominated → nonsense ratios |
| Ratio band | 30–500% | Sanity for a C00.06 write |

Every one of tonight's known-bad traces (F2000 runs, aborted clamped moves,
soft-ramp buried-Jα runs) is rejected or downgraded by these gates; every
known-good recipe run passes.

---

## The analysis plot

After BEGIN finishes, the plot swaps to the **1 kHz journal capture**:

- **TQ%** (orange, left axis) and **VEL** (blue, right axis)
- **VEL fit** (violet dashed) — the fitted model's simulated velocity.
  *This is the honesty check: if the dashed line hugs the blue one, the ratio
  in the title is trustworthy.*
- Dashed **Tp** / **Tf** horizontals + orange **α window** / blue **cruise**
  bands when the Yaskawa cross-check succeeds
- Title: ratio, quality, fit error, fitted Coulomb friction

---

## What the fit reports

| Output | Meaning |
|--------|---------|
| ratio% | \(100\,(J_{\mathrm{total}}-J_M)/J_M\) → C00.06 |
| \(F_c\) | Coulomb (sliding) friction, N·m — X measured ~0.05–0.08 N·m (4–6% rated) |
| \(b\) | Viscous friction, N·m·s/rad |
| fit err | RMS(sim vel − meas vel)/peak vel |
| J-sensitivity | How much the fit degrades with J off ±40% (identifiability) |
| cross-check | Two-point Sigma II ratio (display only, never written) |

---

## Why these defaults

| Choice | Reason |
|--------|--------|
| ~100 ms accel stretch | Physics fit wants fewer 606C stair-steps during accel; hard ~60 ms ramps inflate velocity residual even when J is correct |
| Stroke ~40 mm | Two clean accel/decel edges per direction without long friction-only cruise |
| F8000–F10000 | Peak ~800–1000 rpm: inertia impulse ≫ friction noise |
| Torque limit 0 | Clamps caused aborted/short moves (the two worst traces on file); the fit needs no flat plateau |
| Write only if `good` | Avoids overwriting C00.06 with garbage |

---

## Required inputs

| Field | Why |
|-------|-----|
| Motor rotor inertia | Datasheet \(J_M\) — **required** |
| Rated torque | Converts 6077 % → N·m — **required** |
| Stroke / feed / cycles | ID move; stroke ~40, F8000–F10000 linear, cycles=1 |
| Torque limit % | Leave **0** (kept for compat; clamps not needed by the fit) |
| ID accel | 0 = auto from feed (~100 ms ramp). Non-zero overrides. |

---

## Safety

- Soft-limit clearance when homed.
- CANCEL aborts MDI.
- `ini.*.max_acceleration` and any torque limit are restored after the move.
- Feed soft-clamped to ≤ 10000 for ID.
- C00.06 write only on **good** quality; RAM only (EEPROM store separately).

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| "physics fit untrustworthy" | Move aborted / clamped / non-rigid trace | Torque limit 0, stroke ~40, F8000+, re-run |
| "J barely constrains the fit" | Friction-dominated move | Raise feed (and let ID accel stay auto) |
| marginal, peak < 500 rpm | Feed too low | F8000–F10000 on linear axes |
| VEL fit (dashed) diverges from VEL | Model mismatch (backlash, stiction event) | Re-run; if persistent, inspect trace.csv |
| C00.06 unchanged after "ok" | Estimate was marginal | Gate skipped write — read status line / journal |

---

## Tests

```bash
python3 probe_basic/python/test_a6_graphical_inertia.py
```

Includes: a synthetic physically-consistent trace corrupted with real-style
PDO holds (fit must recover J within ±25%), the exact Sigma II demo numbers
for the cross-check formulas (Tp=90%, Tf=4.5%, ΔV=1000 rpm, Δt=3.34 ms →
Pn103≈138.24), and a replay of every journaled X trace (good cluster must
land 80–180%).
