# Graphical inertia auto-tune (T = Jα)

Yaskawa-style **Inertia by Graphical Analysis** for this mill: a Servo Tuning
**INERTIA** panel that moves the edit axis, samples drive torque + velocity,
solves for load/motor inertia ratio, and writes **C00.06**.

Kept **separate** from one-click gain tuning and from the drive-internal
**F30.10** path (`docs/INERTIA_TUNE.md` on branch
`cursor/internal-inertia-tune-f9d7`). Order of work:

1. **INERTIA** panel → BEGIN → C00.06 written (only if quality is **good**)  
2. Switch to **GAINS** → **ONE-CLICK TUNE**

| Where | What |
|-------|------|
| Servo Tuning → panel **INERTIA** | Settings + BEGIN / CANCEL |
| `probe_basic/python/a6_graphical_inertia.py` | Math + campaign (v0.4) |
| `config/tuning/inertia_settings.json` | Saved per-axis knobs (auto-written) |
| `logs/tuning/graphical_inertia/` | Journals + `trace.csv` |
| `test_a6_graphical_inertia.py` | Unit tests (no hardware) |

**Related:** `SERVO_TUNING.md` (Phase 1), `ONE_CLICK_TUNING.md` (gains only),
`A6_TUNING.md` (SDO map). Alternate approach: drive F30.10 offline ID.

---

## Operator recipe

1. Look up **motor rotor inertia** \(J_M\) and **rated torque** on the datasheet
   (400 W XYZ: \(J_M=5.9\times10^{-5}\,\mathrm{kg\cdot m^2}\), \(1.27\,\mathrm{N\cdot m}\)).
2. Servo Tuning → edit axis → **INERTIA**.
   Live plot shows **torque % + velocity**. Prefer **cycles = 1**.
   Leave **Torque limit = 0**.
3. Set feed to **F5000–F10000** on linear axes (default X = F8000).
   Low feeds make inertial torque too small on a long ramp.
4. Home, park **mid-travel**, machine ON.
5. **BEGIN INERTIA AUTO-TUNE** → confirm.
   The campaign temporarily lowers `ini.*.max_acceleration` so 0→feed takes
   ~120 ms (then restores). That is what makes measured α usable on this mill.
6. If quality is **good**, C00.06 is written (RAM). Marginal/bad estimates are
   shown but **not** written — re-run or set manually (~100–150% is typical on X).
7. Switch to **GAINS** → **ONE-CLICK**.

Factory C00.06 default is **100%** — that is not a measured load ratio.
Manual feel on this X axis settled near **~120%**; auto-tune should land in
that neighborhood when quality is good.

---

## Method (v0.4)

Trapezoidal G1 under CSP. Sample:

- torque = CiA **6077** (% rated)  
- velocity = CiA **606C** → unit/min → motor RPM (10 mm/rev XYZ / 360°/rev A)

Each rest→cruise edge is paired with the following same-sign cruise→rest edge.
Multi-cycle uses the median across pairs.

\[
T_A = \frac{|T_{\mathrm{acc}} - T_{\mathrm{dec}}|}{2},\quad
\alpha = \frac{\Delta\omega}{\Delta t}\ (\mathrm{measured}),\quad
J_{\mathrm{tot}} = \frac{T_A}{\alpha},\quad
\mathrm{ratio\%} = 100\cdot (J_{\mathrm{tot}}-J_M)/J_M
\]

\(T_{\mathrm{acc}}\) / \(T_{\mathrm{dec}}\) are **directed mid-band quartiles**
(torque-with-motion on accel, braking on decel). That cancels coulomb/viscous
friction without relying on a noisy cruise-friction estimate, and still works
when CSP braking is soft.

α is the **measured** rest→cruise wall-clock slope. Trajectory α is **not**
used for the ratio (it overstates when the axis cannot track the lowered
`MAX_ACCELERATION`).

**Quality gates (write only if good):**

- Accel ≥ ~80 ms, decel ≥ ~70 ms (ID targets ~120 ms)
- Inertial \(T_A\) ≥ ~4% rated
- Pair spread ≤ ~35% relative
- Ratio inside ~30–500%

---

## Why these defaults

| Choice | Reason |
|--------|--------|
| ~120 ms accel stretch | Native INI accel (~17 ms 0→F3000) makes 606C look stepped; measured α needs a long ramp |
| F5000–F10000 | On a 120 ms ramp, F3000 only produces ~2–3% rated inertial torque — too noisy |
| Accel/decel cancel | Cruise friction at high F is viscous-heavy; \(T_{\mathrm{peak}}-T_{\mathrm{fric}}\) was not repeatable |
| Measured α (not traj) | Axis often cannot track the lowered `MAX_ACCELERATION`; commanded α underestimates J |
| Write only if `good` | Marginal/bad used to overwrite C00.06 with 40–180% swings or absurd ratios |

Offline replay of stretched F10000 X journals with v0.4 clustered ~117–166%
(near the manual ~120% that felt good). Unstretched short ramps fail closed.

---

## Required inputs

| Field | Why |
|-------|-----|
| Motor rotor inertia | Datasheet \(J_M\) — **required** |
| Rated torque | Converts 6077 % → N·m — **required** |
| Stroke / feed / cycles | ID move; prefer cycles=1, F5000–F10000 linear |
| Torque limit % | Optional fallback only (0 recommended) |
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
| quality `marginal`, ratio ≫200%, low feed | \(T_A\) SNR too low | Raise feed to F5000–F10000 |
| quality `marginal`, pair spread | +/− legs disagree | Re-run cycles=1 mid-travel; keep torque limit 0 |
| Live plot flat | Wrong panel / HAL pins | Stay on INERTIA panel; plot auto-arms |
| C00.06 unchanged after “ok” | Estimate was marginal | Gate skipped write — read status line / journal |

---

## Tests

```bash
python3 probe_basic/python/test_a6_graphical_inertia.py
```
