# Drive-internal inertia tune (F30.10)

One-button attempt to run the A6-EC **offline inertia auto-tune** from the
Servo Tuning tab, then read the result into **C00.06**.

| Where | What |
|-------|------|
| Probe Basic → **Servo Tuning** → **INERTIA TUNE** | GUI button (edit axis) |
| `probe_basic/python/a6_inertia_tune.py` | Planner + state machine |
| `probe_basic/python/a6_inertia_tune_sim.py` | Simulator for tests |
| `probe_basic/python/test_a6_inertia_tune.py` | Unit tests |
| `logs/tuning/inertia/<stamp>_<axis>/` | Journals (gitignored) |

**Related:** `SERVO_TUNING.md` (Phase 1), `ONE_CLICK_TUNING.md` (gain ladder —
does **not** touch inertia), `A6_TUNING.md` (SDO map).

---

## Operator recipe

1. Home the machine. Park the axis **near mid-travel** (F30 needs room both ways).
2. Servo Tuning → select the edit axis → **INERTIA TUNE \<axis\>**.
3. Confirm dialog shows the **computed** C07.04 stroke + speed/accel/torque.
4. Keep a hand near ESTOP. Watch the status line / FERR plot.
5. On success, C00.06 refreshes in the table. Store to EEPROM from the drive
   panel if you want it to survive power loss.
6. Keep the journal folder — especially on failure.

**CANCEL** aborts: clears F30.10 and restores the previous 6065 window.

---

## Inputs: defaults vs critical

You do **not** need to type parameters. The confirm dialog shows what will run.

| Knob | Source | Notes |
|------|--------|-------|
| **C07.04 revolutions** | **Computed** from soft-limit room at the current pose (75% margin, capped at 2.0 rev, floor 0.5 rev) | **Critical** — never blind vendor 2.00 rev |
| C07.01 speed | Default **300 rpm** | Above vendor 150 rpm floor; softer than 500 |
| C07.02 accel time | Default **100 ms** | |
| C07.03 target torque | Default **12.0%** | Slightly under vendor 15% |
| Axis | Edit axis button | |
| Clearance | Confirm dialog | Mid-travel is on you |

If soft-limit room cannot fit ≥0.5 rev both ways, the button refuses to start.

---

## What the campaign does

```
PREFLIGHT → PLAN → ARM C07 (machine OFF) → widen 6065 → F30.10=1
        → poll motion / C00.06 / F30 flag → restore 6065 → refresh UI
```

- **6065** is widened temporarily (~50 mm/deg) so CSP position-hold + F30
  motion does not trip Er47.0; INI `FERROR` is already huge on this machine.
- Writes are **RAM-only**. `ethercat-conf.xml` still does not push C00.06.
- Journals under `logs/tuning/inertia/` (markdown + JSON).

### SDO map

| Panel | SDO | Role |
|-------|-----|------|
| C07.01–C07.04 | `0x2007:02`–`:05` | ID speed / accel / torque / revolutions |
| F30.10 | `0x2030:11` | Start offline inertia ID (`1`) |
| C00.06 | `0x2000:07` | Resulting load inertia ratio (%) |
| 6065 | `0x6065:00` | Temporary widen + restore |

---

## Known risk (read this)

The A6 manual describes F30.10 as a **keypad** enable. Vendor PC software can
start the same ID. **EtherCAT write of F30.10 may or may not start motion** on
a given firmware.

If the button arms C07 but the axis never moves:

1. Journal will say motion=no / timeout or F30.10 write failed.
2. C07 limits are already set — run F30 from the **drive panel** or A6 software.
3. Re-open Servo Tuning (or change axis and back) so C00.06 auto-reads.

Er51.0 / Er51.1 = ID failure: soften speed/torque, check couplings, ensure
≥0.5 rev travel and enough accel.

---

## Tests

```bash
python3 probe_basic/python/test_a6_inertia_tune.py
```
