# Graphical inertia auto-tune (T = Jα)

Yaskawa-style **Inertia by Graphical Analysis** for this mill: a Servo Tuning
**INERTIA** panel that moves the edit axis, samples drive torque + velocity,
solves for load/motor inertia ratio, and writes **C00.06**.

Kept **separate** from one-click gain tuning and from the experimental F30.10
button on other branches. Order of work:

1. **INERTIA** panel → BEGIN → C00.06 written  
2. Switch to **GAINS** → **ONE-CLICK TUNE**

| Where | What |
|-------|------|
| Servo Tuning → panel **INERTIA** | Settings + BEGIN / CANCEL |
| `probe_basic/python/a6_graphical_inertia.py` | Math + campaign |
| `config/tuning/inertia_settings.json` | Saved per-axis knobs (auto-written) |
| `logs/tuning/graphical_inertia/` | Journals + `trace.csv` |
| `test_a6_graphical_inertia.py` | Unit tests (no hardware) |

---

## Operator recipe

1. Look up **motor rotor inertia** \(J_M\) and **rated torque** on the datasheet
   (400 W XYZ / 100 W A on this machine — enter the real numbers).
2. Servo Tuning → select edit axis → **INERTIA**.
3. Fill J_M, rated torque, stroke, feed (defaults are motion-only).
4. Home, park **mid-travel**, machine ON.
5. **BEGIN INERTIA AUTO-TUNE** → confirm.
6. Read the result / quality notes. C00.06 is written on success (RAM).
7. Switch to **GAINS** → run **ONE-CLICK** (or hand-tune).

---

## Method (matches the Yaskawa eLV)

Trapezoidal G1 move under CSP. Sample:

- torque = CiA **6077** (% rated)  
- velocity = CiA **606C** → unit/min → motor RPM via 10 mm/rev (XYZ) or 360°/rev (A)

Then:

\[
T_A = T_{\mathrm{peak}} - T_{\mathrm{friction}},\quad
\alpha = \frac{\Delta\omega}{\Delta t},\quad
J_{\mathrm{tot}} = \frac{|T_A|}{\alpha},\quad
J_L = J_{\mathrm{tot}} - J_M,\quad
\mathrm{ratio\%} = 100\cdot J_L / J_M
\]

Peak torque is the median during the accel window; friction is median cruise
torque. Ragged plateaus are flagged `marginal` / `bad` (soften gains or
flatten with a drive torque limit, then retry).

---

## Required inputs

| Field | Why |
|-------|-----|
| Motor rotor inertia | Datasheet \(J_M\) — **required**, no useful default |
| Rated torque | Converts 6077 % → N·m — **required** |
| Stroke / feed / cycles | Identification move (auto-saved) |

---

## Safety

- Soft-limit clearance check when homed (full stroke one direction).
- CANCEL aborts MDI.
- Writes only **C00.06** via the normal APPLY path (motors cycle OFF/ON).
- RAM only — store EEPROM from the panel if you want persistence.

---

## Tests

```bash
python3 probe_basic/python/test_a6_graphical_inertia.py
```
