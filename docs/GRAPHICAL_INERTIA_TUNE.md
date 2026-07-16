# Graphical inertia auto-tune (Yaskawa Sigma II)

**Inertia by Graphical Analysis** for this mill, matching the Yaskawa
*Sigma II Parameter Calculator* worksheet (`Sigma II Parameter Calculator
Rev 2.42.xls` in-repo). Servo Tuning **INERTIA** moves the edit axis, samples
drive torque + velocity, solves for load/motor inertia ratio, and writes
**C00.06** (A6 equivalent of Sigma II **Pn103**).

Kept **separate** from one-click gain tuning and from the drive-internal
**F30.10** path (`docs/INERTIA_TUNE.md` on branch
`cursor/internal-inertia-tune-f9d7`). Order of work:

1. **INERTIA** panel → BEGIN → C00.06 written (only if quality is **good**)  
2. Switch to **GAINS** → **ONE-CLICK TUNE**

| Where | What |
|-------|------|
| Servo Tuning → panel **INERTIA** | Settings + BEGIN / CANCEL |
| `probe_basic/python/a6_graphical_inertia.py` | Math + campaign (v0.6) |
| `config/tuning/inertia_settings.json` | Saved per-axis knobs (auto-written) |
| `logs/tuning/graphical_inertia/` | Journals + `trace.csv` |
| `test_a6_graphical_inertia.py` | Unit tests (no hardware) |
| `Sigma II Parameter Calculator Rev 2.42.xls` | Source worksheet / Techniques |

**Related:** `SERVO_TUNING.md` (Phase 1), `ONE_CLICK_TUNING.md` (gains only),
`A6_TUNING.md` (SDO map).

---

## Operator recipe (v0.6 defaults)

1. Look up **motor rotor inertia** \(J_M\) and **rated torque** on the datasheet
   (400 W XYZ: \(J_M=5.9\times10^{-5}\,\mathrm{kg\cdot m^2}\), \(1.27\,\mathrm{N\cdot m}\)).
2. Servo Tuning → edit axis → **INERTIA**.
   Live plot shows **torque % + velocity**. Prefer **cycles = 1**.
3. Use the hardened linear recipe (defaults on X):
   - **Feed F8000** (keep F5000–F10000)
   - **Stroke ~50 mm** (Y/Z defaults 30 mm — need clear cruise)
   - **ID accel auto** → ~**180 ms** 0→feed ramp
4. Home, park **mid-travel**, machine ON.
5. **BEGIN INERTIA AUTO-TUNE** → confirm.
   - Campaign lowers `ini.*.max_acceleration` for the ~180 ms ramp.
   - **Always clamps:** fixed **Torque limit > 0**, *or* probe then
     Pn402-style flatten (~90% of probe \(T_p\)). Unclamped estimates
     cannot be quality **good**.
6. If quality is **good**, C00.06 is written (RAM). Marginal/bad estimates are
   shown but **not** written.
7. Switch to **GAINS** → **ONE-CLICK**.

Factory C00.06 default is **100%** — that is not a measured load ratio.
Manual feel on this X axis settled near **~120%**.

---

## Method (v0.6 — hardened windows)

Trapezoidal G1 under CSP. Sample:

- torque = CiA **6077** (% rated) — closest PDO to SigmaWin “torque”
- velocity = CiA **606C** → unit/min → motor RPM (10 mm/rev XYZ / 360°/rev A)

Workbook math (verified against BIFF formulas on the Inertia sheet):

\[
T_a = T_p - T_f,\quad
\alpha = \frac{\Delta V_{\mathrm{rpm}}\cdot 2\pi}{60\cdot(\Delta t_{\mathrm{ms}}/1000)},\quad
J_L = \frac{T_a}{\alpha} - J_M,\quad
\mathrm{ratio\%} = 100\cdot\frac{J_L}{J_M}
\]

| Symbol | How we measure it (v0.6) |
|--------|--------------------------|
| \(T_p\) | **Torque limit** when clamped (workbook: limit IS peak). Probe pass uses α-band upper-half mean only to choose the clamp. |
| \(T_f\) | **Cruise** mean torque. Triangle fallback is allowed for analysis but **not** for quality=good. |
| \(\Delta V,\Delta t\) | Fixed **25–75% of peak RPM** band on the accel edge — **not** torque-gated |

**Always clamp:** probe unconstrained (if Torque limit = 0) → set CiA limit ≈ 90% of probe \(T_p\) (above \(T_f\)) → re-measure. Fixed Torque limit skips the probe.

**Quality gates (write only if good):**

- Torque clamp active and α-band torque tracks the limit (mean within ~20%)
- α-band duration ≥ ~80 ms (recipe targets ~90 ms at 180 ms ramp)
- Cruise \(T_f\) present (≥ ~40 ms)
- Inertial \(T_a\) ≥ ~4% rated
- Leg spread ≤ ~35% relative
- Ratio inside ~30–500%
- α-band torque CV ≤ ~0.18 when clamped

---

## What still differs from SigmaWin (honest gaps)

| Sigma II workbook | This mill |
|-------------------|-----------|
| Torque **reference** in SigmaWin TRACE | CiA **6077** torque actual (only PDO we have) |
| Manual horizontal/vertical cursors | Fixed RPM α band + cruise window |
| Pn402 / Pn403 | CiA 6072 / 60E0 / 60E1 (when writable) |
| Speed or position amp with soft-start | LinuxCNC **CSP** G1 trapezoid |
| Tuning sheet → Pn100/101/102 from rigidity | **Not** done here — use one-click / hand tune after C00.06 |

**Back pocket (not implemented):** Sigma II Techniques also offer two
alternate \(T_f\) measurements if cruise-from-trace is untrustworthy —
(1) cumulative load while jogging at ~½ application speed, (2) torque-limit
walk (won’t-move vs just-reaches-top-speed, then average). Revisit only after
the hardened clamp + fixed-α path is stable on hardware.

---

## Why these defaults

| Choice | Reason |
|--------|--------|
| ~180 ms accel stretch | Fixed 25–75% α band needs ≥~80 ms; 180 ms → ~90 ms band |
| F8000 / 50 mm stroke | SNR for \(T_a\) + cruise room after two ~12 mm ramps |
| Always clamp | \(T_p\) is known; torque noise no longer picks Δt |
| Fixed RPM α band | Stops spiky 6077 from moving the α window |
| Cruise required for good | Triangle \(T_f\) couples friction into noisy edges |
| Write only if `good` | Avoids overwriting C00.06 with garbage |

---

## Required inputs

| Field | Why |
|-------|-----|
| Motor rotor inertia | Datasheet \(J_M\) — **required** |
| Rated torque | Converts 6077 % → N·m — **required** |
| Stroke / feed / cycles | ID move; prefer cycles=1, F8000 / 50 mm linear |
| Torque limit % | 0 = always probe→flatten; >0 = fixed clamp as \(T_p\) |
| ID accel | 0 = auto from feed (~180 ms ramp). Non-zero overrides. |

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
| quality `bad` / analysis fails, short α band | Accel stretch did not apply | Confirm LinuxCNC running; check journal `accel` events |
| quality `marginal`, “no torque clamp” | Flatten skipped / CiA limits not writable | Check 6072/60E0/60E1; set Torque limit explicitly |
| quality `marginal`, “not tracking limit” | Clamp not biting / Fake peak | Lower limit slightly; confirm drive accepted SDO |
| quality `marginal`, “no cruise Tf” | Stroke too short for feed/ramp | Raise stroke or lower feed |
| quality `marginal`, ratio ≫200%, low feed | \(T_a\) SNR too low | Raise feed to F5000–F10000 |
| Live plot flat / empty before BEGIN | Plot arms only during the campaign | Press BEGIN — strip starts at t=0 with the move |
| C00.06 unchanged after “ok” | Estimate was marginal | Gate skipped write — read status line / journal |

---

## Tests

```bash
python3 probe_basic/python/test_a6_graphical_inertia.py
```

Includes an exact replay of the Sigma II demo numbers (Tp=90%, Tf=4.5%,
ΔV=1000 rpm, Δt=3.34 ms → Pn103≈138.24).
