# Drive homing: hard stop + Z pulse in the A6-EC drives

**Status: implemented on branch `dev-drive-homing`, NOT yet run on the machine.**
Don't home with this config until test D0 below has passed. Until then, use
the switch-homing config on `dev-jerk-testing`.

The drives home themselves: each linear axis drives into a mechanical hard
stop under a torque limit, then moves on to the encoder's Z (index) pulse, and
that is home. A has no stop (it rotates without limits), so it goes straight
to its Z pulse. LinuxCNC only starts each drive's homing, waits for it, and
takes the result. No switches are involved in homing; the limit switches stay
limit switches.

## How it works (what's in this branch)

| File | Change |
|---|---|
| `components/a6home.comp` | New realtime component, one instance per drive. Runs the homing handshake with the drive (details below) |
| `components/test/` | Bench test of the component's state machine against a simulated A6 and LinuxCNC's index homing. Needs only gcc: `sh components/test/test_a6home.sh` |
| `scripts/build-a6home.sh` | Builds and installs `a6home` for **both** LinuxCNC builds (stock 2.9.8 needs `sudo`; the tpnext RIP doesn't) |
| `scripts/drive_homing_d0.sh` | Test D0: read-only survey of each drive's homing objects, saved to `logs/drive_homing/` |
| `ethercat-conf.xml` | Maps `0x6060`/`0x6061` (modes of operation) and the homing objects `6098`, `6099:01/02`, `609A`, `607C`, `60E6` into the PDOs. The fixed `6060 = 08` SDO is gone |
| `ethercat_mill.hal` | Loads `a6home`, routes each joint's feedback, command, controlword, amp fault and `index-enable` through it, and sets the homing objects from the INI. The command scaling (`mult2.0–3`, `conv-real-sint.0–3`) now runs after `cia402.N.write-all` and `a6home.N.write-all` |
| `ethercat_mill.ini` | Per joint: `DRIVE_HOME_*` keys, and LinuxCNC set to index-only homing (`HOME_SEARCH_VEL = 0`, small `HOME_LATCH_VEL`, `HOME_USE_INDEX = YES`) |

Every change is fenced with `DRIVE-HOMING START/END` comments, and each
changed line carries its `REVERT:` value.

**Why a component instead of a custom HOMEMOD.** LinuxCNC's stock *index-only*
homing already does the right thing if something plays "encoder that resets to
zero at the index". `a6home` plays that part with the drive. This means:
- no `homing.c` rebuild and no HOMEMOD, so one module works under 2.9.8 and tpnext;
- no dependence on which `cia402` component is installed (this mill runs lcec v1.41 + an older `cia402`);
- LinuxCNC's own abort and E-stop handling stay in charge.

**The sequence, per joint:**
1. REF starts index-only homing. LinuxCNC sets `joint.N.index-enable` and creeps at `HOME_LATCH_VEL` (0.01 mm/s, cosmetic).
2. `a6home` requests modes of operation 6 and waits until the drive reports 6 in `0x6061` with operation enabled (1 s limit).
3. It then adds controlword bit 4 on top of `cia402`'s controlword. The drive homes.
   While the drive moves, `motor-pos-fb` follows `motor-pos-cmd`, so LinuxCNC sees no following error.
4. Done = statusword bits 10 and 12, but only after the drive was seen busy
   (bit 10 or 12 low) since the start. Stale "homed" bits from an earlier run
   can't end a new one; other A6 users saw "homing only works once per power
   cycle".
5. `a6home` requests CSP (8) again. Until `0x6061` reports 8, the drive gets its own actual position as target.
6. Once the drive is back in CSP, `a6home` clears `index-enable`. With
   `607C = 0` and `60E6 = 0` the drive's position is 0 at the Z pulse, which is
   what LinuxCNC's index homing expects. LinuxCNC re-bases its command onto
   that in the same servo cycle, then moves to `HOME` at `HOME_FINAL_VEL`.

**Failure handling.** A drive fault, a homing error (statusword bit 13), a
missing mode acknowledge, `DRIVE_HOME_TIMEOUT`, or an ESC abort never clear
`index-enable`; that would read as "index found".
- `a6home.N.amp-fault` goes true **only until LinuxCNC has disabled the joint**
  (`joint.N.amp-enable-out` low), then it's released. LinuxCNC releases
  `index-enable` only when its homing state machine runs, which needs the
  machine on, and it refuses to turn on while an amp fault is present.
  Holding amp-fault until `index-enable` dropped would leave a machine that
  can never be turned on again. The bench test checks for this.
- Machine off or E-stop during drive homing: `a6home` goes straight to
  holding, without waiting for its timeout.
- While holding, the drive keeps its own actual position, and LinuxCNC's
  feedback is the real position, so its command re-syncs while it's off. Once
  the machine is on, `index-enable` is released, and the command matches the
  drive within 0.01 mm, `a6home` is idle again. CSP never gets a stale target,
  which is the Er87.1 jump other A6 users hit.
- The reason is printed on the terminal: `a6home: joint N drive homing failed: ...`. LinuxCNC shows "joint N amplifier fault"; turn the machine on and home again.

**Bench test** (`sh components/test/test_a6home.sh`): 16/16 pass. It covers 8
scenarios, each run under both ways LinuxCNC writes `index-enable` (2.9 every
cycle, tpnext on edges):
- normal hard stop + Z;
- stale homed bits at start;
- two homes in a row;
- drive fault during homing;
- homing error (bit 13);
- drive never acknowledges mode 6;
- ESC abort with the machine on;
- E-stop or machine off mid-homing.

After every failure, a simulated operator turns the machine back on and jogs
1 mm, proving the joint is usable and nothing is stuck. A negative control
proves that passing LinuxCNC's command straight through trips Er87.1 in the
simulated drive. The motion model follows `homing.c`/`control.c` (2.9 and
tpnext): homing only runs while enabled, amp faults refuse enable, and the
command follows the feedback while disabled.

**Useful pins:** `a6home.N.hstate` (0 idle, 1 request, 2 start, 3 running, 4
handback, 5 error, 6 aborted), `.homing`, `.homed`, `.failed`, `.cw-out`,
`.opmode`, plus `lcec.0.N.opmode-display` and `lcec.0.N.status-word`.

---

## 1. Acceptance criteria

| # | Criterion | Target |
|---|-----------|--------|
| A1 | X, Y, Z: spread of 20 consecutive homes, read with a 1 µm dial indicator against a fixed reference | ≤ 2 µm range, cold and warm |
| A2 | A: spread of 20 consecutive homes | same Z-pulse angle each time (±2 counts ≈ ±0.005°) |
| A3 | No drive faults (Er47.0, Er87.1, ALF4.2) and no LinuxCNC following errors over 50 home cycles per axis | 0 |
| A4 | Works under both launchers: `launch.sh` (stock 2.9.8) and `launch-tpnext.sh` (tpnext-ma RIP) | both pass |
| A5 | Fault paths (E-stop, drive fault, abort, machine off, drive re-power) during homing leave the joint **unhomed**, and nothing moves on its own afterwards | all pass |
| A6 | Probe, toolsetter, laser and tool-change positions re-verified after machine zero moves | all re-measured, no guessed rapids |

---

## 2. Facts the plan rests on

**Drive (StepperOnline A6-EC manual, https://files.omc-stepperonline.com/A6-EC_series_servo_drive_manual.pdf):**
- Homing mode is `0x6060 = 6`. The method goes in `0x6098`, and the manual's
  homing chapter covers **−2 … 35**:
  - **−1: reverse to the mechanical extreme (hard stop), then to the Z pulse.**
  - **−2: forward to the mechanical extreme, then to the Z pulse.**
    The drive detects the stop when torque reaches the torque limit, speed is
    near zero, and that state lasts a set time.
  - 33 / 34: reverse / forward to the nearest Z pulse (index only). 35: current position is home.
  - 1–14: switch + Z pulse. 17–30: switch only.
  - Note: the object-dictionary table in the same manual says the range is
    "1 to 35". Which one is right gets settled on the real drive in step D0.
- Hard-stop homing parameters (from the A6-PN manual; the EC version should
  match, **verify in D0**):
  - **C10.30**: torque limit while homing against a hard stop, unit 0.1 % of rated, default 1000 (= 100 %, far too high).
  - **C10.31**: hard-stop homing speed, rpm, default 10 (= 1.67 mm/s on a 10 mm screw).
  - The stall detection time is a parameter near those two; find it in D0.
- Parameter numbers map to SDOs as `C<g>.<n>` → `0x20<g>` subindex = `n+1`
  written as hex digits. This matches the repo: C01.10 → `0x2001:11`,
  C00.04 → `0x2000:05`. The manual confirms C10.08 (homing time limit, default
  60 000 ms) = `0x2010:09`. So C10.30 is expected at **`0x2010:31`** and C10.31
  at **`0x2010:32`**; read them back before writing anything.
- `0x6099:01` (search speed, counts/s, default 1 747 627 ≈ 800 rpm),
  `0x6099:02` (speed when looking for zero, default 174 763 ≈ 80 rpm), `0x609A`
  (homing acceleration; the manual gives two conflicting defaults, so read it
  from the drive), `0x607C` (home offset, default 0).
- **`0x60E6 = 0` (absolute homing): after successful homing, `0x6064` = `0x607C`.**
  With `607C = 0`, the drive reports position 0 at the Z pulse. LinuxCNC's
  index homing expects exactly that ("the encoder resets to zero at index").
- The manual says statusword bit 10 means "home located or homing interrupted",
  and that **bit 15** marks homing complete. CiA 402 and lcec's `cia402`
  component use **bit 12** (homing attained) plus bit 10. **Which bits the A6
  actually sets has to be logged in D2** (see risk R1).
- In CSP mode, the A6 holds statusword bit 10 at 1 all the time.
- Encoder: 17-bit, 131 072 counts/rev, multi-turn absolute. The multi-turn
  part needs the battery; the Z pulse doesn't. The absolute mode is C00.07
  (`0x2000:08`); leave it as it is unless D0 shows a problem.
- StepperOnline replied on the LinuxCNC forum (thread 58323) that the A6 doesn't
  support torque homing. That contradicts the manual's methods −1 and −2. D0
  settles it on your drives and firmware (`AS715N_sAxis_V0.10`).

**This machine (repo):**
- 10 mm screws, so 13 107.2 counts/mm and one Z pulse every 10 mm. A is 1:1
  (364.0889 counts/° = 131 072/360), so one Z pulse per table revolution.
- Before this branch: CSP mode with `0x6060 = 8` set by SDO and not mapped in the
  PDOs. This branch maps `6060`/`6061` so modes can change while running.
- Position scaling is in HAL (`mult2`/`conv-real-sint` on the command,
  `conv-sint-real`/`div2` on the feedback). The `cia402` component only handles
  enable and fault.
- The drives' DI functions are cleared (`0x2004 = 0`). Hard-stop homing doesn't
  use switches, so keep it that way. The Y/Z shared home bus no longer matters
  for homing.

**LinuxCNC (`homing.c` in 2.9 and tpnext-ma, `control.c`):**
- Index-only homing (`HOME_SEARCH_VEL = 0`, `HOME_LATCH_VEL ≠ 0`,
  `HOME_USE_INDEX = YES`) sets `joint.N.index-enable`, then creeps at
  `HOME_LATCH_VEL` until something clears index-enable. It then sets
  `motor_offset = −HOME_OFFSET` and `pos_cmd = pos_fb`, assuming the feedback
  reads ~0 at the index. After that it does the final move to `HOME`.
- Each servo cycle: read homing pins → read `motor-pos-fb` → homing → compute `motor-pos-cmd` → write.
- `HOME_SEARCH_DIST` / `HOME_LATCH_DIST` exist in master and tpnext only. 2.9 ignores them.

**lcec (`linuxcnc-ethercat`):**
- This mill runs lcec **v1.41** with an older `cia402` component (enable and fault only).
- lcec ≥ 1.49.0 (2026-11-17) ships a `cia402` with a homing handshake (mode 6
  acknowledged before bit 4, bits 10 + 12, stale status rejected). It still
  doesn't (a) report the command as feedback while the drive moves on its own,
  (b) wait for the drive to be back in CSP before releasing `index-enable`, or
  (c) keep `index-enable` set on a drive fault; it clears it, which LinuxCNC
  can read as "index found".
- So this branch doesn't depend on any `cia402` homing. `a6home` does the
  handshake and (a)–(c) itself, and works with the `cia402` already installed.

---

## 2b. Prior art: what other A6 owners have already done (researched 2026-11-23)

Nobody has published hard-stop + Z homing on an A6 with measured
repeatability or with the hard-stop parameter values. This plan fills that gap.
The pieces have all been proven separately, though:

**Proof that it works:**
- **fer662, LinuxCNC forum thread 58323, 09 Jul 2026:**
  - **method −1 works on the A6** as real hard-stop homing, on default parameters.
  - Setup: Z's endstop was in the wrong place, so he switched Z to −1. It worked first time, and so did the other axis.
  - What he saw: "carriage hit a bearing block, the motor pushed for about 2 s without much force, encoder feedback stopped, then the motor reversed to search for the Z pulse."
  - He didn't change any homing parameters. Another user's question about C10.30–C10.32 values went unanswered.
- In the same thread, **spumco pointed out that the manual documents −1/−2 as torque homing (pages 74–75)**. StepperOnline's "not supported" reply (29 Jun 2026) was never followed up.
- **Contradicting claim:** andrax (thread 54965, page 12) says −1/−2 on the A6 means *limit switch on DI1/DI2* + Z pulse, not torque. **D0/D3 settles this:** the drives' DI functions are cleared (`0x2004 = 0`), so if the axis stops at the block and goes on to find Z, it's torque.

**Existing A6 code and configs to borrow from:**
- **TangentAudio, `github.com/tangentaudio/linuxcnc-bridgeport`** (last commit Apr 2026):
  - The A6 runs Z on a Bridgeport, with **the same `vid 00400000 / pid 00000715`** as this mill. The config comment calls the A6 "an OEM version of Inovance SV660N".
  - Uses method 33 (Z pulse only).
  - **Maps `6060`, `607C`, `6098`, `6099:01/02`, `609A` and `60E6` into RxPDO `0x1600`, and `6061` into TxPDO `0x1a00`.** The A6 accepts all of these in PDOs, so homing settings can be changed live from HAL.
  - Custom `el7_homecomp` / `el7_cia402`. At the end of homing it forces `pos_cmd = 0`, which is right only because `607C = 0` and `60E6 = 0`.
- **Colin Bardini, `github.com/CollinBardini/linuxcnc-a6-servo`** (Feb 2025):
  - An A6 homecomp. **It counts homing as complete when statusword bit 12 AND bit 15 are both set.** So the A6 sets bit 12, and lcec's `cia402` test (bits 10 + 12) should work. This mostly retires risk R1, but D2 still logs it.
  - andrax runs this homecomp in production with **method 4** (home switch + Z) on drive-wired switches (thread 58467).
- **rodw, `github.com/rodw-au/cia402_homecomp`**: a draft, already reviewed (see §3 of the earlier analysis). Not used.
- **Marcos DC, `github.com/MarcosDuqueCesar/linuxcnc-cia402-layer`**: a CiA 402 framework with homing as a separate part. Simulation only, not tested on hardware (Mar 2026). Not used.
- **Konstantin, threads 58808 / 58325** (May 2026): methods 34 and 19 start and finish reliably from dbraun-style `cia402` with `x-home-index`. But see failure F1.

**Failure modes the community has hit, and where this plan handles each:**

| # | What people saw | Likely cause | This plan |
|---|---|---|---|
| F1 | After homing, the drive jumps or "rushes back to where homing started", with Er87.1 or "position deviation too large" (Jugo2 thread 54965 p.12; Konstantin thread 58325 p.6) | CSP resumes with LinuxCNC's stale target from before homing | `a6home` returns the drive to CSP holding its own position, then releases index-enable so LinuxCNC re-bases. Bench-tested; D2 checks the step |
| F2 | "Homing only works once per power cycle" (andrax, Jugo2) | The drive's homed bits (12/15) stay set, so the next request is seen as already done | `a6home` only accepts "done" after it saw the drive busy. Bench-tested; **D2: home 5 times in a row with no power cycle** |
| F3 | A custom homecomp can't be stopped once started (thread 54965 p.8) | The homecomp has no abort path | Stock `homing.c` keeps abort working. T6c |
| F4 | Jumps when the MPG/handwheel is live during homing (andrax) | Jog input reaching the joint during the hand-back | LinuxCNC already drops wheel counts while homing is active (`control.c`, checked in 2.9 and master), so no HAL gate was added. T6g proves it on the machine |
| F5 | One axis doesn't start homing and nobody notices (gantry users) | No supervision | C10.08 drive timeout (30 s) + `stat-homing` must rise within 0.5 s of `home` (log it in D2). LinuxCNC aborts at the end of its latch move |
| F6 | Values written with `sdoConfig` **stay in the drive after being removed from the XML** (fer662) | The A6 saves SDO writes | **D0 must record every original value** (`6098`, `6099`, `609A`, `607C`, `60E6`, `2010:09`, `2010:31/32`, stall time). Rollback writes them back explicitly |
| F7 | andrax recommends `sync0Shift="0"` | Timing | Observation only. This mill runs `300000` with M2R and is stable. **Don't change it** unless D2 shows timing problems |

---

## 3. Hardware prep (Jon, before any software work)

1. **Hard stops.** Each of X, Y and Z needs a rigid, dedicated stop at the homing
   end: a steel block or bolt, not the ballscrew nut against the end bearing,
   not a rubber bumper, and not a way cover. The stop should be just beyond the
   axis's normal travel. Suggested directions:
   - X → negative end (method −1)
   - Y → negative end (−1)
   - Z → **up** (−2, if +Z is up on the drive), so gravity always loads Z the same way.

   Confirm each motor's positive direction against the drive's direction parameter in D0.
2. **A has no hard stop.** It rotates continuously (unlimited limits), so it
   uses the drive's index-only homing (method 33 or 34). One Z pulse per table
   revolution makes that home unique. If Jon wants hard-stop homing on A too, A
   needs a stop and limited rotation. Decide before D5.
3. Limit switches stay as limits (they're already ignored while each axis homes).
   Check that the hard stop sits **beyond** the limit switch, so normal jogging
   trips the limit before the stop.

---

## 4. Settings to fill in after the tests

The code is done (see "How it works"). These values are placeholders until the tests below set them:

| Setting | Where | Now | Set by |
|---|---|---|---|
| `DRIVE_HOME_METHOD` | INI per joint | X −1, Y −1, Z −2, A 34 | D0 (supported?), §3 directions |
| `DRIVE_HOME_SPEED_FAST/SLOW`, `DRIVE_HOME_ACCEL` | INI | XY 15 mm/s / 1 mm/s / 100 mm/s²; Z 10 mm/s; A 10 °/s / 1 °/s | D3 |
| Hard-stop torque / speed / stall time (`0x2010:31/32/…`) | `ethercat-conf.xml` SDO, **not set yet** | drive defaults | D0 confirms the addresses, D3 tunes. fer662 homed on the defaults |
| `HOME_OFFSET` | INI | 0 (= machine zero at the Z pulse) | D4 |
| `HOME` | INI | X/Y +15, Z −15 (park 15 mm off the Z pulse) | D4. Must be clear of the limit switch: LinuxCNC ignores limits only while homing, so a joint that ends homing on its limit switch faults |
| `MIN_LIMIT` / `MAX_LIMIT` | INI | unchanged (still the wide values for unhomed jogging) | D4/T8. With zero at the stop end, the old wide limits **let G-code reach the hard stop**. Tighten them once travel is measured |
| `DRIVE_HOME_TIMEOUT` | INI | 120 s (A 60 s) | D3, once the real homing time is known. The drive's own limit is C10.08 (`0x2010:09`, default 60 s) |

The `HOME_LATCH_DIST` keys only take effect on tpnext. LinuxCNC's creep is
0.01 mm/s, so 5 mm covers 500 s.

## 5. Test plan

Run the tests in order. Each one gates the next. Log raw numbers to
`logs/drive_homing/<date>_<test>.md`. Keep a hand on the E-stop for every
test that moves anything.

### D0: Confirm the drive supports it (read only, then one SDO write, no motion)
On each slave:
1. `ethercat upload -p N -t uint32 0x60E3 0`, then read each subindex: the list
   of supported homing methods. Record it.
2. Read `0x6098`, `0x6099:01/02`, `0x609A`, `0x607C`, `0x60E6`, `0x2010:09`, and
   `0x2010:2F … 0x2010:35` (C10.28–C10.34) to find the hard-stop torque, speed
   and stall-time parameters. Compare with the manual and record the values.
   (The A6 doesn't describe its own types, so `-t` is required. Try `int16` /
   `uint16` / `int32` as the manual says.)
3. Write `0x6098 = -1`, read it back, and look for ALF4.2 ("homing mode set incorrectly") on the drive panel.

**Go:** −1 / −2 is listed in `60E3` (or accepted on write without ALF4.2) on
all three linear drives, and 33/34 on A. **If it's rejected on this firmware,
stop and report to Jon** with the `60E3` list and the firmware version; don't
improvise another method.

### D1: Build and load `a6home`
1. `sh components/test/test_a6home.sh` → 7/7 + control OK.
2. `scripts/build-a6home.sh` (asks for sudo for the stock build).
3. Start LinuxCNC (both launchers) with the machine **off**. Check `halcmd show pin a6home.0`,
   `halcmd show thread servo-thread` (order: `div2.N` → `a6home.N.read-all` → motion →
   `cia402.N.write-all` → `a6home.N.write-all` → `mult2.N` → `conv-real-sint.N` → `lcec.write-all`),
   and that `lcec.0.N.opmode-display` reads 8 once the drives are enabled.
4. Machine on, jog every axis: must behave exactly as before (`a6home.N.hstate` = 0).

### D2: Bench run of drive homing, A axis (mechanically disconnected = safe)
1. All four drives are wired through `a6home` in this branch. Home A on its own first (button or `halui.joint.3.home`).
2. Start LinuxCNC. Check that the machine enables and jogs as before, and that
   `lcec.0.3.opmode-display` = 8 and `a6home.3.hstate` = 0.
3. Run `halscope` or `halsampler` at the servo rate on:
   `lcec.0.3.status-word`, `lcec.0.3.opmode-display`, `a6home.3.hstate`,
   `a6home.3.index-enable`, `a6home.3.homed`, `a6home.3.failed`, `a6home.3.cw-out`,
   `lcec.0.3.pos-fb`, `lcec.0.3.pos-cmd`, `joint.3.motor-pos-fb`, `joint.3.homed`.
4. Home A.

**Pass:**
- The drive goes to mode 6 and moves to its Z pulse.
- `pos-fb` ends at 0 (= `607C`).
- The mode returns to 8 **before** `index-enable` clears, and `lcec.0.3.pos-cmd` never steps by more than one count at the hand-back.
- `joint.3.homed` = 1, and the final move goes to `HOME`.

**R1 check:** from the statusword log, record which bits the A6 sets when
homing finishes (10, 12, 15). If bit 12 never sets, `stat-homed` never fires
and homing times out. In that case add a small patch to the `cia402`
component (or a wrapper comp) that also accepts bit 15, and document it.

**F2 check:** home A **5 times in a row without power-cycling the drive**.
Every run must actually move to the Z pulse, not finish instantly on stale
bits. If a run finishes instantly, log the statusword at the request, check the
lcec version (D1), and stop.

**F5 check:** `a6home.3.hstate` must reach 3 (running) within 0.5 s of the REF. Record the delay.

Then 20 homes from random start angles. **Pass (A2):** `lcec.0.3.pos-fb` read
at the moment of homing equals the Z position each time, and the table mark
lines up. No Er87.1 or Er47.0.

### D3: Tune the hard-stop homing on one linear axis (X), still with no LinuxCNC homing
Use drive homing only, started from LinuxCNC as in D2. Do it on X first.
1. Start with C10.30 = 20 %, C10.31 = 10 rpm, `0x609A` modest. Jog X about 20 mm away from the stop first.
2. Home. Watch it drive into the stop, stall, back off to the Z pulse, and report homed.
   - If it never detects the stop (it keeps pushing until the timeout): raise C10.30 in 5 % steps.
   - If it "detects" the stop in mid-air (friction spikes): lower the speed or raise the stall time.
   - Stay at the lowest torque that detects the stop reliably, 10 out of 10.
3. Watch the drive's following-error window (`0x6065` = 0.5 mm / 250 ms). Find
   out whether it trips Er47.0 while pushing against the stop in homing mode. If
   it does, raise the window only during homing and record how.
4. **Stop-to-Z clearance (important):** log `lcec.0.0.pos-fb` at the stall and
   at the Z pulse (before the drive zeroes it). Clearance = travel from the stop
   to the Z pulse, 0 … 10 mm.
   - It must be **2–8 mm**, ideally about 5 mm. Near 0 or 10 mm, the stall-point
     scatter can pick the next Z pulse, and home jumps by 10 mm.
   - To fix it, move the stop block or rotate the motor coupling on the screw.
     The software can't move the drive's Z pulse.
   - Record the final clearance for every axis in `docs/HARDWARE.md`.

**Pass:** 20 out of 20 homes detect the stop, the clearance spread is under
±0.5 mm, and there are no faults.

### D4: X repeatability
1. **Baseline first:** with the old config (switch homing), 20 homes, each read
   on a 1 µm indicator against a fixed block at a fixed G53 position.
2. New config: 20 homes cold. Then exercise the spindle and axes for 30 min and do 20 more warm.
3. Set `HOME_OFFSET` and `HOME` so the machine coordinates make sense. Re-check
   soft limits against the new zero, so that travel never reaches the stop in
   normal use.

**Pass (A1, A3):** the indicator range is ≤ 2 µm in each set and no worse than
the baseline. No faults.

### D5: Y and Z
Same as D3 and D4. Z homes up (−2 or 34, by direction), with a low torque limit. Z's
limit wiring is gagged, so watch the first runs closely.

### T6: Fault paths (A5), on each axis
a. Software E-stop (slave 3 DI1) while the drive homes → machine off, joint unhomed. On reset, nothing moves.
b. **Force a drive fault during homing** (expect: machine off, "a6home: joint N drive homing failed: drive fault", joint unhomed). For example, set C10.30 so low the
   drive times out (C10.08), or pull a drive's enable. The joint must be
   **unhomed** afterwards. If it shows homed, stop and report; `a6home` must never clear `index-enable` on a fault.
c. ESC / abort in LinuxCNC during drive homing. Expect: machine off (amp fault
   held until the command catches up), joint unhomed, `0x6061` back to 8, no jump
   when you turn the machine on again.
d. Turn the machine off and back on after homing, then jog: no jump.
e. Re-power the drives' logic while LinuxCNC runs, with the machine homed. Find
   out whether the joints unhome. The raw feedback changes after re-power. If
   they stay "homed", add HAL that unhomes them (`halui.joint.N.unhome`) when a
   drive drops out, and prove it.
g. **MPG during homing (F4):** turn the pendant wheel while each axis homes. Nothing may move, and the hand-back must stay clean.
f. Homing error, e.g. block the move so the drive raises the homing-error bit or
   times out → `stat-homing-error`, LinuxCNC aborts, unhomed.

### T7: Both launchers (A4)
Repeat a reduced D2/D4/D5 (5 homes per axis) under `launch.sh` (2.9.8) and
`launch-tpnext.sh`. Check `halcmd show thread servo-thread` order on both.

### T8: Re-verify everything that stores machine coordinates (A6)
Machine zero moves on every axis. With **CLAUDE.md rules 1 and 2** in force:
- Re-find the toolsetter and laser positions (`#5181–5183`, beam XY) with
  closed-loop G38 seeks from `G53 Z0`. Never rapid to old stored values.
- Tool-change and park positions, subroutine safe Z, soft limits, any `G53` in `nc_files` and subroutines.
- Work offsets in `linuxcnc.var`: shift them by the change in machine zero, or re-probe them.
- Update `docs/HARDWARE.md`, `docs/CONFIG_TOUR.md` (homing section), `docs/TROUBLESHOOTING.md` and `CLAUDE.md`.

---

## 6. Risks to watch

| # | Risk | Where it's caught |
|---|------|-------------------|
| R1 | The A6 flags homing complete on bit 15 instead of bit 12, so `a6home` never sees "done" (times out safely) | D2 statusword log |
| R2 | This firmware rejects method −1/−2 (StepperOnline's forum claim) | D0 |
| R3 | Stale target at the switch back to CSP → Er87.1 | `a6home` handback + bench test; D2 step size |
| R4 | A fault read as "index found" → false "homed" | `a6home` never clears index-enable on failure; T6b |
| R5 | Stop-to-Z clearance near 0 or 10 mm → home jumps 10 mm | D3 step 4 |
| R6 | Too much homing torque damages screw bearings or the coupling | Start at 20 %, step up 5 % at a time, dedicated rigid stop |
| R7 | Drive following-error window (0.5 mm / 250 ms here; fer662 likely ran the much wider default) trips Er47.0 while pushing against the stop | D3 step 3. If it does: check `0x6065` can be mapped into the RxPDO, then use the prepared `a6home.N.ferr-window` (commented block in `ethercat_mill.hal`) to widen it only while the drive homes |
| R8 | Machine zero moves → stored positions crash | T8 |
| R9 | The joint parks on its limit switch after homing → "joint N on limit switch error" | `HOME` 15 mm off the Z pulse; D4 checks the switch is clear at `HOME` |

## 7. Rollback
Check out `dev-jerk-testing` (or revert this branch's commits). That restores the `6060 = 08` SDO and the switch-homing `HOME_*` values; the unused `a6home` module can stay installed.
**Then explicitly write back the original drive values recorded in D0** with
`ethercat download`. The A6 keeps SDO writes after they're removed from the XML (F6). Keep
the stored positions from before T8 in the log.

## 8. Questions for Jon
- Hard-stop blocks: where on each axis, and are they already there? (Z's current top stop vs the switch; X and Y negative ends.)
- A: index-only (no stop needed), or add a stop and limit A's rotation?
- Does the master E-stop cut the drives' logic power? (T6e)

## Sources
- fer662 / spumco / StepperOnline, A6 torque homing (thread 58323): https://forum.linuxcnc.org/ethercat/58323-ethercat-a6-servo-homing-problem
- andrax / Jugo2: −1/−2 claim, once-per-power-cycle, Er87.1 jumps (thread 54965 p.12): https://forum.linuxcnc.org/ethercat/54965-stepperonline-a6-servo?start=110
- TangentAudio A6 config + components: https://github.com/tangentaudio/linuxcnc-bridgeport (`configs/bridgeport-ethercat-qtvcp`, `components/`)
- Colin Bardini A6 homecomp: https://github.com/CollinBardini/linuxcnc-a6-servo
- andrax's method 4 workflow + absolute encoders (thread 58467): https://forum.linuxcnc.org/ethercat/58467-setting-up-the-stepperonline-a6-battery-encoder-cable
- Konstantin, methods 34/19 and the jump back after Z (threads 58808, 58325): https://forum.linuxcnc.org/ethercat/58808-ethercat-servo-drive-homing , https://forum.linuxcnc.org/ethercat/58325-cia-402-folder-missing?start=50
- Marcos DC CiA 402 layer: https://forum.linuxcnc.org/ethercat/58592-cia402-framework-for-linuxcnc-follow-up-runnable-simulation-easier-debuggi
- A6-EC manual (Homing Mode §4.1.5, methods −2 … 35, `60E6`/`607C` behavior, C00.07, C10.08): https://files.omc-stepperonline.com/A6-EC_series_servo_drive_manual.pdf
- A6-PN manual (C10.30 / C10.31 hit-and-stop torque and speed, ALF4.2): https://www.scribd.com/document/808562533/A6-PN-Series-Servo-Drive-User-Manual-1
- StepperOnline forum statement on torque homing: https://forum.linuxcnc.org/ethercat/58323-ethercat-a6-servo-homing-problem
- Er87.1 after drive homing on the A6: https://forum.linuxcnc.org/ethercat/54965-stepperonline-a6-servo?start=80
- lcec `cia402` component, docs, 1.49.0 changelog, DeASDA homing for comparison: https://github.com/linuxcnc-ethercat/linuxcnc-ethercat
- LinuxCNC `homing.c` / `control.c`: https://github.com/LinuxCNC/linuxcnc (branches `2.9`, `master`), https://github.com/grandixximo/linuxcnc/tree/tpnext-ma
