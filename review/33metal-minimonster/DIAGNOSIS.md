# 33metal / minimonster jog review

Review of the uploaded config dump (Omron G5 + Leadshine L6N, Probe Basic).
Symptoms (clarified): **Probe Basic UI jog buttons + keyboard cursors** — no MPG/pendant.

- UI jog / cursors flaky — work about half the time
- X died for a while while Y/Z still jogged
- (Earlier “MPG” report was a mis-speak for UI jog)

## No pendant — UI jog only (confirmed)

`minimonster.ini` loads only `cia402.hal` + `custom.hal`. `custom.hal` is spindle Modbus. That matches “no MPG.” Flaky controls are **Probe Basic continuous/step jog and keyboard cursors**, both going through motion soft limits / following error.

## What the symptoms imply

| Observation | Meaning |
|-------------|---------|
| Y/Z UI jog worked, X did not | Axis-selective inhibit (soft limit or per-joint fault), not GUI focus |
| Intermittent / half-time | Position near soft limit, or speed-dependent following-error trip |

## Finding 1 — Soft limits at 0 with `NO_FORCE_HOMING` (high confidence)

```ini
NO_FORCE_HOMING = 1
[AXIS_X] / [JOINT_0]  MIN_LIMIT = 0  MAX_LIMIT = 330  HOME = 0
[AXIS_Y] / [JOINT_1]  MIN_LIMIT = 0  MAX_LIMIT = 280  HOME = 0
[AXIS_Z] / [JOINT_2]  MIN_LIMIT = 0  MAX_LIMIT = 120  HOME = 120
```

G5 absolute encoders report a real machine position before homing. If unhomed X sits at **≤ 0** or **≥ 330**, LinuxCNC soft-limits block continuous jog on that axis while other axes still move. That matches “X dead, Y/Z fine” without killing the drive.

Same class of bug as on the Lemontart mill: soft max had to clear unhomed absolute Z (~300+ mm) or jog was blocked before HOME ALL.

**Check live:**

```bash
halcmd getp joint.0.pos-fb
halcmd getp joint.0.min-soft-limit
halcmd getp joint.0.max-soft-limit
halcmd getp axis.x.jog-enable
```

If `pos-fb` is outside `[MIN_LIMIT, MAX_LIMIT]`, widen limits for bring-up (see `patched/minimonster.ini`), home, then tighten.

## Finding 2 — `FERROR` / `MIN_FERROR` inverted and far too tight (high confidence)

```ini
FERROR = 1
MIN_FERROR = 50
```

LinuxCNC interpolates the following-error trip between **MIN_FERROR (near zero speed)** and **FERROR (at speed)**. Here those are backwards, and **`FERROR = 1` mm is brutal** for untuned CSP over EtherCAT.

Effect in practice:

- Slow MPG / fine step → often stays under the trip → **still moves**
- Faster keyboard / GUI continuous jog → following-error abort or joint inhibit → **feels dead / flaky**

Drive SDO `6065` on the G5s is also tiny:

```xml
<!-- 0x0F5C = 3932 counts; @ 104857.6 counts/mm ≈ 0.037 mm -->
<sdoConfig idx="6065" ... data="5C 0F 00 00"/>
```

A drive-side window that tight will fault **one axis** (statusword → `cia402.*.drv-fault` → `joint.*.amp-fault-in`) while the others keep jogging — again matching “only X died.”

**Bring-up fix:** widen host `FERROR`/`MIN_FERROR` (patched INI), and open `6065` to something like 1 mm of counts (`104858` ≈ `0x1A000` for the 104857.6 scale) until tuning is done.

## Finding 3 — (withdrawn) pendant / MPG

Operator clarified: no MPG. Skip WHB/USB checks. UI jog + cursors share the motion path in findings 1–2.

## Finding 4 — Estop dummy loop is written oddly

```hal
net estop-out => iocontrol.0.user-enable-out
net estop-out <= iocontrol.0.emc-enable-in
```

Prefer:

```hal
net estop-out iocontrol.0.user-enable-out => iocontrol.0.emc-enable-in
```

## Finding 5 — Other smells (lower priority)

| Item | Note |
|------|------|
| INI `SCALE = -1` on XYZ | Leftover stepgen; real scale is `cia402.*.pos-scale` |
| `encoder-filter` loaded but bypassed | Dead code |
| Slave/name map | idx1=Z, idx2=X, idx3=Y — easy to mis-debug |
| `TWOPASS = one` | Prefer `on` |
| TRAJ max 700 vs joint 500 | Inconsistent |
| A axis `max limit =` / `min limit =` blank | Invalid junk in INI |
| Spindle `mux4` stop=`6`, fixed `mult2`×15 | Verify vs VFD; unrelated to jog |

## Action items (in order)

1. **Live check when X “dies”:**
   ```bash
   halcmd getp joint.0.pos-fb
   halcmd getp joint.0.min-soft-limit joint.0.max-soft-limit
   halcmd getp joint.0.amp-fault-in cia402.2.drv-fault
   halcmd getp lcec.0.G5-200WZ.error-code
   ```
2. **Widen soft limits** for bring-up (see `patched/minimonster.ini`), home, then tighten to real travel.
3. **Fix FERROR:** e.g. `FERROR=50` `MIN_FERROR=5` (or wider until tuned).
4. **Open drive 6065** to ~1 mm of counts on all G5s (`patched/ethercat-conf.xml`).
5. **Clean A limits** and traj/joint max velocity mismatch.
6. Retest UI jog + cursors before chasing GUI/Probe Basic bugs.

## Patched files

| File | Change |
|------|--------|
| `patched/minimonster.ini` | Wider soft limits; sane FERROR; A limits; traj cap |
| `patched/cia402.hal` | Clean estop dummy |
| `patched/ethercat-conf.xml` | G5 `6065` ~1 mm bring-up |
| `patched/custom.hal` | Unchanged spindle (header note only) |
