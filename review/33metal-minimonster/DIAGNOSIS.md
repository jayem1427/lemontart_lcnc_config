# 33metal / minimonster jog review

Review of the uploaded config dump (Omron G5 + Leadshine L6N, Probe Basic).
Symptoms reported:

- MPG / pendant buttons flaky — work about half the time
- Keyboard cursors similarly unreliable
- X died for a while while Y/Z still jogged
- Pendant could still move X when cursors could not

## `custom.hal` arrived — and it has no MPG

`minimonster.ini` loads only:

```ini
HALFILE = cia402.hal
HALFILE = custom.hal
```

`custom.hal` is **spindle Modbus only** (`mb2hal` + `mux4` + `mult2`). There is:

- no `xhc-whb04b-6` / pendant `loadusr`
- no `axis.*.jog-*` nets
- no physical jog-button debounce
- no `halui.jog` wiring

So **this LinuxCNC config does not wire an MPG at all.** Whatever they call “MPG buttons” is one of:

1. **Probe Basic on-screen jog** (continuous / step) — most likely given KEYBOARD_JOG in the INI
2. A pendant started **outside** these HAL files (manual `loadusr`, another INI, desktop helper)
3. A hardware MPG on drive DIs that was never connected in HAL (would feel completely dead, not half-time)

Ask them: *is the flaky control a wireless XHC pendant, or the GUI jog pad?* If it is an XHC, the HALFILE for it is simply missing from the machine config they sent.

## What the symptoms actually imply

| Observation | What it rules in / out |
|-------------|------------------------|
| Y/Z cursors worked, X cursors did not | Not “GUI lost focus” (that kills all arrow keys) |
| “MPG” could still move X | X drive + EtherCAT path were alive — not a dead servo |
| Intermittent / half-time buttons | Soft-limit / ferror inhibit, GUI mode, or an external pendant — **not** something in `custom.hal` |

Primary story remains **axis-selective inhibit** (soft limits + following error). Pendant button flakiness is **not explained by any HAL in this dump**.

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

## Finding 3 — Flaky “MPG buttons” (not in this HAL tree)

Confirmed: **no pendant component is loaded.** Treat “MPG” as Probe Basic jog UI unless they produce another HALFILE.

If it really is a WHB04B-6 elsewhere:

1. **Wireless dongle** — USB hub / shared bus / low power → missed button packets (“half the time”)
2. **Axis rotary between detents** — no axis selected → wheel/buttons do nothing
3. **WHB `is-homed` gate** — refuses jog until `whb.halui.joint.*.is-homed`; with `NO_FORCE_HOMING` tie those to `halui.machine.is-on` (Lemontart `xhc-whb04b-6.hal` pattern)
4. They need an actual `HALFILE = xhc-whb04b-6.hal` — it is not present today

If it is **GUI jog buttons** feeling flaky, soft limits + FERROR (findings 1–2) already explain “works half the time / one axis dies,” especially near limit 0 or after a fast jog.

**Check live:**

```bash
# Is any WHB even loaded?
halcmd show comp | grep -i whb
# Soft-limit / fault path for X
halcmd getp joint.0.pos-fb joint.0.amp-fault-in cia402.2.drv-fault
```

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
4. Confirm what “MPG” is. If XHC: add a real pendant HALFILE. If GUI: findings 1–2 are the fix.

## `custom.hal` notes (spindle only — unrelated to jog)

| Item | Note |
|------|------|
| `mux4` stop code `6` | Unusual; confirm against their VFD register map |
| `mult2.spindle_freq_out.in0 = 15` fixed × `speed-out-rps` | Odd scaling vs the Lemontart RPM→0.1 Hz path — verify spindle commanded Hz |
| Pin names `mb2hal.00.spindle_start_stop.float` | Must match their mb2hal build; mismatch = silent spindle fails, not jog |

## Patched files in this folder

| File | What changed |
|------|----------------|
| `patched/minimonster.ini` | Wider soft limits for unhomed abs encoders; sane FERROR/MIN_FERROR; notes |
| `patched/cia402.hal` | Clean estop dummy; comments that pendant is absent |
| `patched/ethercat-conf.xml` | Larger G5 `6065` follow-error window for bring-up (~1 mm) |
| `patched/custom.hal` | As uploaded (spindle only) + header note: no MPG here |

These are **review suggestions**, not a drop-in for the Lemontart mill.
