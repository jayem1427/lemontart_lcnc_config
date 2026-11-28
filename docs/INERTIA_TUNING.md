# Inertia tuning (work in progress)

The **INERTIA** panel on the Servo Tuning tab estimates the load-to-motor
inertia ratio and writes it to the drive as **C00.06** (the A6 equivalent of
Yaskawa Sigma II's Pn103). A good inertia ratio makes every gain after it
behave more predictably.

**Status:** it works on X but isn't fully trusted yet. The factory default
(C00.06 = 100 %) is good enough to start one-click or manual tuning, so don't
block on this. Measure it when the load is heavy compared to the motor, or
when gains refuse to settle.

Order: inertia first, then switch the tab back to **GAINS** and tune.

---

## Running it

1. Look up the motor's **rotor inertia** and **rated torque** on its
   datasheet. 400 W XYZ motors here: 5.9 × 10⁻⁵ kg·m², 1.27 N·m.
2. Servo Tuning → pick the axis → **INERTIA** panel. Enter those two values.
3. Linear axes: stroke about **40 mm**, feed **F8000–F10000**, cycles **1**,
   torque limit **0**.
4. Home, park mid-travel, machine on.
5. **BEGIN INERTIA AUTO-TUNE** → confirm.
6. If the quality is **good**, C00.06 is written (the drive stores it in EEPROM, C13.10 = 1). Marginal and bad
   results are shown but not written.

During the move it temporarily lowers the axis acceleration so the speed-up
takes about 100 ms, then puts it back.

---

## How it works

The A6 updates its velocity and torque feedback in steps, holding each value
for 17–36 ms. So you can't just compute acceleration from two points on the
velocity curve, which is what Yaskawa's classic worksheet method does. On 37
real traces from this mill, that method gave anything from −100 % to
+104 000 %.

Instead it fits a simple physical model:

```
J × dω/dt = torque − Coulomb friction × sign(ω) − viscous friction × ω
```

It runs the measured torque through the model to *simulate* a velocity curve,
and adjusts J and the two friction terms until the simulated velocity matches
the measured one. Integrating doesn't care about the stair-steps. Then
`ratio % = 100 × (J − J_motor) / J_motor`.

Across every good X trace on file, this gives about **100 %** (85–120 %),
consistent across runs to about ±15 %, and close to the ~120 % found by hand.
The old two-point method still runs as a cross-check and is shown, never
written.

### When it writes

| Check | Needed for "good" |
|-------|-------------------|
| How well the simulated velocity matches | ≤ 18 % of peak error (up to 27 % if the rest is solid) |
| How much J matters to the fit (±40 % J must make it worse) | ≥ 8 %. Below that, friction dominates and J can't be measured |
| Peak motor speed | ≥ 500 rpm. Slow moves are all friction |
| Result | Between 30 % and 500 % |

On the plot afterwards, the violet dashed line is the model's velocity. If it
hugs the blue measured line, trust the number.

---

## Troubleshooting

| Message | Fix |
|---------|-----|
| "physics fit untrustworthy" | Move was aborted or clamped. Torque limit 0, stroke ~40, F8000+, retry |
| "J barely constrains the fit" | Too slow, friction dominates. Raise the feed |
| Marginal, peak < 500 rpm | Feed too low |
| Dashed line wanders from the measured one | Backlash or a sticky spot. Rerun; if it persists, look at `trace.csv` |
| C00.06 didn't change | The result was only marginal, so it wasn't written. Check the status line |

## Files

| File | Role |
|------|------|
| `probe_basic/python/a6_graphical_inertia.py` | Fit, quality checks, the run |
| `config/tuning/inertia_settings.json` | Saved per-axis settings |
| `logs/tuning/graphical_inertia/` | Journals and `trace.csv` (not in git) |
| `probe_basic/python/test_a6_graphical_inertia.py` | Tests, including a replay of every saved X trace |
| `docs/reference/Sigma II Parameter Calculator Rev 2.42.xls` | The Yaskawa worksheet used for the cross-check |
