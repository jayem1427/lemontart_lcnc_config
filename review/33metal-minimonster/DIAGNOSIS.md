# 33metal / minimonster jog review

Review of the uploaded config dump (Omron G5 + Leadshine L6N, Probe Basic).
Symptoms reported:

- MPG / pendant buttons flaky — work about half the time
- Keyboard cursors similarly unreliable
- X died for a while while Y/Z still jogged
- Pendant could still move X when cursors could not

## Missing files (blocks full pendant diagnosis)

`minimonster.ini` loads:

```ini
HALFILE = cia402.hal
HALFILE = custom.hal
```

**`custom.hal` was not in the dump.** That is almost certainly where spindle, IO, and any XHC/MPG pendant wiring live. Without it we cannot audit button nets, debounce, or `jog-enable` gating. Ask for `custom.hal` and any `xhc-*.hal` / pendant HALFILE.

Also absent: the real `HALFILE` list may load a pendant file that never made it into this zip.

## What the symptoms actually imply

| Observation | What it rules in / out |
|-------------|------------------------|
| Y/Z cursors worked, X cursors did not | Not “GUI lost focus” (that kills all arrow keys) |
| Pendant could still move X | X drive + EtherCAT path were alive — not a dead servo |
| Intermittent / half-time buttons | Input path or inhibit (limits / mode / wireless), not a permanent HAL typo |

So: **axis-selective inhibit** (soft limits, joint fault, or jog-enable), plus a **separately flaky input device** for the pendant buttons.

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

## Finding 3 — Flaky MPG buttons (likely hardware + missing HAL)

The dump has **no pendant HAL**. Common WHB04B-6 failure modes when that file exists:

1. **Wireless dongle** — USB hub / shared bus / low power → missed button packets (“half the time”)
2. **Axis rotary between detents** — no axis selected → wheel and some buttons do nothing
3. **WHB `is-homed` gate** — component refuses jog until `whb.halui.joint.*.is-homed` is true; with `NO_FORCE_HOMING` and unfinished home, axes randomly refuse until those pins are tied to `halui.machine.is-on` (see Lemontart `xhc-whb04b-6.hal`)
4. **No debounce** on button → MDI / mode toggles

**Check live (once pendant HAL is loaded):**

```bash
halcmd watch whb.button.reset whb.button.stop whb.button.start-pause
halcmd watch whb.axis.x.jog-enable axis.x.jog-enable
halcmd getp whb.halui.joint.x.is-homed
```

If button pins flicker without a press → USB/wireless. If pins stay solid but `jog-enable` stays false → homed-gate or mode.

## Finding 4 — Estop dummy loop is written oddly

```hal
net estop-out => iocontrol.0.user-enable-out
net estop-out <= iocontrol.0.emc-enable-in
```

Prefer the usual one-liner dummy:

```hal
net estop-out iocontrol.0.user-enable-out => iocontrol.0.emc-enable-in
```

Unlikely to cause X-only flakiness, but worth cleaning so enable state is unambiguous.

## Finding 5 — Other config smells (lower priority)

| Item | Note |
|------|------|
| INI `SCALE = -1` on XYZ | Leftover stepgen values; motion scale is `cia402.*.pos-scale` in HAL — confusing, not the jog bug |
| `encoder-filter` loaded but bypassed | Dead code; fine, just noise |
| Slave/name map | EtherCAT idx0=L6N(A), idx1=G5-200W(Z), idx2=G5-200WZ(X), idx3=G5-400W(Y) — easy to mis-wire mentally when debugging “X” |
| `TWOPASS = one` | Unusual; stock is `on` |
| `refClockSyncCycles="-1"` | DC ref sync disabled on purpose; can add jitter but not X-only cursor death |
| TRAJ `MAX_LINEAR_VELOCITY = 700` vs joint max 500 | Inconsistent caps |

## Recommended debug order (on their machine)

1. **Watch X soft limits vs feedback** while reproducing “X dead”:
   `halcmd show sig` / `getp joint.0.pos-fb` vs MIN/MAX.
2. **Watch faults:**
   `halcmd getp cia402.2.drv-fault` (X), `lcec.0.G5-200WZ.error-code`, `joint.0.amp-fault-in`.
3. **Widen soft limits + FERROR** using `patched/minimonster.ini`, open drive `6065`, retest cursors vs MPG.
4. **Send `custom.hal` + pendant HAL** — then audit button nets / homed gates / USB placement (dongle on motherboard port, no hub).

## Patched files in this folder

| File | What changed |
|------|----------------|
| `patched/minimonster.ini` | Wider soft limits for unhomed abs encoders; sane FERROR/MIN_FERROR; notes |
| `patched/cia402.hal` | Clean estop dummy; comments pointing at missing pendant / custom.hal |
| `patched/ethercat-conf.xml` | Larger G5 `6065` follow-error window for bring-up (~1 mm) |

These are **review suggestions**, not a drop-in for the Lemontart mill.
