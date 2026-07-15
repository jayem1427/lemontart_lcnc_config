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
| `probe_basic/python/a6_graphical_inertia.py` | Math + campaign (v0.5) |
| `config/tuning/inertia_settings.json` | Saved per-axis knobs (auto-written) |
| `logs/tuning/graphical_inertia/` | Journals + `trace.csv` |
| `test_a6_graphical_inertia.py` | Unit tests (no hardware) |
| `Sigma II Parameter Calculator Rev 2.42.xls` | Source worksheet / Techniques |

**Related:** `SERVO_TUNING.md` (Phase 1), `ONE_CLICK_TUNING.md` (gains only),
`A6_TUNING.md` (SDO map).

---

## Operator recipe

1. Look up **motor rotor inertia** \(J_M\) and **rated torque** on the datasheet
   (400 W XYZ: \(J_M=5.9\times10^{-5}\,\mathrm{kg\cdot m^2}\), \(1.27\,\mathrm{N\cdot m}\)).
2. Servo Tuning → edit axis → **INERTIA**.
   Live plot shows **torque % + velocity**. Prefer **cycles = 1**.
3. Set feed to **F5000–F10000** on linear axes (default X = F8000).
4. Home, park **mid-travel**, machine ON.
5. **BEGIN INERTIA AUTO-TUNE** → confirm.
   - Campaign lowers `ini.*.max_acceleration` so 0→feed takes ~120 ms.
   - If accel torque is spiky and **Torque limit = 0**, **auto-flatten**
     runs a second pass with a CiA torque clamp (Sigma II Pn402 step).
   - Fixed **Torque limit > 0** skips the probe and uses that clamp directly
     (workbook: “the torque limit IS the peak torque”).
6. If quality is **good**, C00.06 is written (RAM). Marginal/bad estimates are
   shown but **not** written.
7. Switch to **GAINS** → **ONE-CLICK**.

Factory C00.06 default is **100%** — that is not a measured load ratio.
Manual feel on this X axis settled near **~120%**.

---

## Method (v0.5 — Sigma II worksheet)

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

| Symbol | How we measure it |
|--------|-------------------|
| \(T_p\) | Mean torque on the **flat** accel plateau (or the torque limit if clamped) |
| \(T_f\) | **Cruise** mean torque (trapezoid). If no cruise: workbook triangle rule \(T_f=(T_{acc}+T_{dec})/2\) (signed) |
| \(\Delta V,\Delta t\) | Only inside the **constant-torque** accel window (Sigma II vertical cursors) |

**Two-pass flatten (Techniques / Example):** probe unconstrained → if accel
torque CV is high, re-run with limit ≈ 90% of probe \(T_p\) (above \(T_f\)).

**Quality gates (write only if good):**

- Constant-torque accel window ≥ ~80 ms (A6 606C needs longer than the
  Sigma II demo’s 3.34 ms)
- Inertial \(T_a\) ≥ ~4% rated
- Leg spread ≤ ~35% relative
- Ratio inside ~30–500%

---

## What still differs from SigmaWin (honest gaps)

| Sigma II workbook | This mill |
|-------------------|-----------|
| Torque **reference** in SigmaWin TRACE | CiA **6077** torque actual (only PDO we have) |
| Manual horizontal/vertical cursors | Auto plateau / cruise windows |
| Pn402 / Pn403 | CiA 6072 / 60E0 / 60E1 (when writable) |
| Speed or position amp with soft-start | LinuxCNC **CSP** G1 trapezoid |
| Tuning sheet → Pn100/101/102 from rigidity | **Not** done here — use one-click / hand tune after C00.06 |

---

## Why these defaults

| Choice | Reason |
|--------|--------|
| ~120 ms accel stretch | Native INI accel (~17 ms 0→F3000) makes 606C look stepped |
| F5000–F10000 | On a 120 ms ramp, F3000 only produces ~2–3% rated \(T_a\) |
| Cruise \(T_f\) (not v0.4 accel/decel cancel) | Matches Sigma II trapezoid worksheet |
| Triangle fallback | Same workbook note when there is no cruise |
| Auto-flatten | Matches Example steps 1→2 (Pn402 for flat \(T_p\)) |
| Write only if `good` | Avoids overwriting C00.06 with garbage |

---

## Required inputs

| Field | Why |
|-------|-----|
| Motor rotor inertia | Datasheet \(J_M\) — **required** |
| Rated torque | Converts 6077 % → N·m — **required** |
| Stroke / feed / cycles | ID move; prefer cycles=1, F5000–F10000 linear |
| Torque limit % | 0 = auto-flatten may choose; >0 = fixed Pn402-style clamp |
| ID accel | 0 = auto from feed (~120 ms ramp). Non-zero overrides. |

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
| quality `bad` / analysis fails, ~20 ms ramp | Accel stretch did not apply | Confirm LinuxCNC running; check journal `accel` events |
| quality `marginal`, “not flat” | Spiky accel torque | Let auto-flatten run, or set Torque limit just below peak |
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
