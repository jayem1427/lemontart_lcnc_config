# Drive homing: home switch, then encoder index, inside the A6-EC drives

**Status (2026-11-28): branch `dev-drive-homing`, rebased on `dev-jerk-testing`. NOT yet run on
the machine.** Work through the tests below in order; each one gates the next. Until X has
passed H3, home with `dev-jerk-testing`.

## The plan in one page

1. **Now: switch + index.** Each drive finds its home switch, backs off it, and stops on the
   first encoder index (Z pulse). The switch only picks *which* screw turn; the index sets the
   position. These encoders are absolute, and the manual says that on an absolute encoder "the Z
   signal refers to the zero point of motor single-turn position feedback", so the index is a
   digital value, not an analog edge. The same turn means the same count.
2. **Then: measure it.** Re-home and probe a block in the vise with the touch probe, before
   (switch homing) and after (drive homing), in one session and across power cycles
   (*Repeatability test plan*).
3. **Later: torque (hard-stop) homing** to replace the switches. Research and the parked
   plan are at the end. Nothing in the config uses it yet.

It is staged per axis, because the wiring differs:

| Axis | Home switch seen by its own drive? | State in this branch |
|---|---|---|
| X | Yes: slave 0 DI2 | **Drive homing on** (method 5). `HOME_OFFSET` is a placeholder until test H0 |
| A | No switch; index only (method 34) | **Drive homing on**. A is disconnected, so it is the safe bench axis |
| Y | Yes: slave 1 DI4, but that input is the bus shorted to the Z home switch | Switch homing. Drive homing prepared (method 5 + HAL guard); enable in test H5 |
| Z | **No.** The Z switch is on the shared bus on slaves 0/1, not on slave 2 | Switch homing. Needs one jumper wire first; enable in test H6 |

`DRIVE_HOME_ENABLE` in each `[JOINT_N]` selects the mode. The homing module runs LinuxCNC's
normal switch homing for joints with 0, so a mixed machine works.

## How it works

Upstream code, nothing of our own in the motion path:
- **[`cia402_homecomp`](https://github.com/linuxcnc-ethercat/cia402_homecomp)**, a LinuxCNC
  homing module (`[EMCMOT]HOMEMOD`), pinned at commit `b13bf72`.
- **`cia402` from linuxcnc-ethercat v1.49.0**, which runs the CiA 402 state machine, scaling
  and the homing handshake.

| File | Change against `dev-jerk-testing` |
|---|---|
| `scripts/install-drive-homing.sh` | Upgrades `~/linuxcnc-ethercat` to v1.49.0, builds lcec + `cia402` + `cia402_homecomp` for the tpnext RIP and/or stock 2.9.8. Backs up the old modules |
| `scripts/drive_homing_d0.sh` | Read-only survey of each drive's homing and DI objects → `logs/drive_homing/` |
| `scripts/index_survey.py` (also on `dev-jerk-testing`) | Latches the encoder index with the drive's touch-probe function and prints the switch-to-index clearance and the `HOME_OFFSET` to use |
| `scripts/home_repeat_test.py` (also on `dev-jerk-testing`) | Re-home + block probe loop for the repeatability tests |
| `patches/cia402_homecomp-home-ref.patch` | Optional change to the homing module (see below). Not applied by default |
| `ethercat-conf.xml` | Maps `6060`/`6061` and the homing objects `6098`, `6099:01/02`, `609A`, `607C`, `60E6` into the PDOs; the fixed `6060 = 08` SDO is gone. **Slave 0 DI2 gets drive function 5 (home switch)** with logic 1 (active high, to be confirmed in H1). RxPDO now has 9 entries and TxPDO 7; the drive takes 10 each at most |
| `ethercat_mill.hal` | Per joint: `cia402` scales position and owns controlword and opmode; enable, command and feedback pass through `joint.N.cia-*`. `joint.N.request-custom-homing` comes from `DRIVE_HOME_ENABLE`. New **shared bus guard** (`or2.6`, `or2.7`) |
| `ethercat_mill.ini` | `HOMEMOD = cia402_homecomp`; per joint `DRIVE_HOME_*`. X and A: search/latch velocity 0 (required when the drive homes). Y and Z: unchanged switch-homing values |

Every change is fenced with `DRIVE-HOMING START/END` and has a `REVERT:` note.

**The sequence for a drive-homed joint:**
1. REF starts homing. The module waits for the drive to report operation enabled, then raises
   `cia402.N.home`.
2. `cia402` requests mode 6 and, once `0x6061` reads 6, sends the start edge (controlword bit 4).
3. The drive runs its method. For method 5 (X, Y: switch at the negative end): move negative at
   `DRIVE_HOME_SPEED_FAST` until the switch closes, reverse at `DRIVE_HOME_SPEED_SLOW` until it
   opens, carry on to the first index. Method 3 (Z: switch at the top) is the mirror image.
   If the axis starts on the switch, it just backs off and takes the index. (This is the A6
   manual's own description of modes 5 and 3, read 2026-11-28. "Forward" is the drive's
   positive direction, which is machine + on all three axes because `SCALE` is positive.)
4. While the drive moves, LinuxCNC's feedback follows its own command, so LinuxCNC raises no
   following error. **Only the drive's own protections apply during this time**: its
   following-error window, torque limit and C10.08 timeout, plus `DRIVE_HOME_TIMEOUT_MS`.
   LinuxCNC also ignores the limit switches while a joint homes, and the drives have no
   overtravel inputs assigned, so nothing stops a drive that searches the wrong way except the
   timeout and you. That is why H1 checks the switch polarity before anything moves.
5. Done = statusword bits 10 and 12, accepted only after the drive was seen busy.
6. `cia402` goes back to mode 8. The module lines LinuxCNC's command up with the drive's actual
   position and declares it `HOME_OFFSET`; LinuxCNC then makes its normal final move to `HOME`.

**Shared bus guard (Y and Z).** The Y and Z home switches are shorted onto one input. LinuxCNC's
switch homing copes by ignoring a bus that is already closed when a home starts. A drive
can't: if it starts with the bus closed by the *other* axis, it believes it is on its own switch
and drives away looking for it to open (Y toward +, **Z downward**) until the timeout. So HAL
now aborts a Y or Z drive home that starts with the bus closed (`flipflop.0/1.out` → `or2.6/7` →
`joint.N.cia-stat-fault`). The module prints `homing aborted: drive fault`, nothing moves, and the
machine stays on. Jog the axis that is on its switch off it and home again. The real fix is to
separate the two switch wires.

**Failure handling.** A drive fault, a homing error (statusword bit 13), the guard, or the
timeout aborts the home: the request is withdrawn, LinuxCNC's command is synced to the drive's
position, the joint stays **unhomed**, and the terminal shows
`cia402_homecomp: joint N homing aborted: <reason>`. A real drive fault also reaches
`joint.N.amp-fault-in`, so the machine turns off as before. `cia402.N.auto-fault-reset` is 0.

**The one silent trap.** A joint with `request-custom-homing = 0` *and* search and latch
velocity 0 is marked **homed where it stands**. So `DRIVE_HOME_ENABLE` and the two velocities
must always be changed together: 1 with 0/0, or 0 with real velocities. H1 checks
`joint.N.is-custom-homing` against the INI.

**Useful pins:** `joint.N.cia-state` (0 idle, 1 mode wait, 2 running, 3 base finalization,
4 enable wait, 5 unlock wait), `joint.N.is-custom-homing`, `cia402.N.stat-homing`, `.stat-homed`,
`.stat-homing-error`, `.pos-fb`, `lcec.0.N.opmode-display`, `lcec.0.N.status-word`.

## linuxcnc-ethercat version

Checked 2026-11-28: **v1.49.0 (2026-11-17) is still the newest release**, and the branch already
uses it. The 10 commits on master after it only touch the Delta ASDA driver. So there is nothing
newer to move to; the install script stays pinned to the tag.

What 1.47–1.49 brought that this branch relies on (the "easier" part):
- `cia402` now ships inside lcec (since 1.47), so no separate `halcompile` of hal-cia402.
- It does the drive-homing handshake itself: mode 6 acknowledged before the start bit, done on
  bits 10 + 12, stale "homed" status rejected, `home` pin made for `index-enable`-style use.
- Position scaling with 64-bit unwrapping, so the HAL `mult2`/`conv` chain is gone.

Also in lcec now, **not used here on purpose**: a native `basic_cia402` device type (give it
`vid`/`pid`, set `homeMethod`, `homeSpeedFast`… as `<modParam>`s) and an `inovance` driver for
the SV660N the A6 is said to be a rebrand of. The A6 has a different vendor ID (`0x00400000`,
Inovance is `0x00100000`), and moving off `generic` renames every `lcec.0.N.*` pin the tuner,
capture and DI wiring use. Worth a look once homing works, not before.

## Changes to the homing module (`cia402_homecomp.comp`)

What has to change in upstream's file for this machine, most certain first.

**1. Nothing, to build it. But it must be rebuilt for each LinuxCNC tree.** The module
`#include`s that tree's `src/emc/motion/homing.c`. The tpnext-ma tree differs from 2.9 in two
ways the module already handles at build time:
- the 64-bit HAL API (2026-09-18): `lcec_hal_compat.h` from lcec selects the right calls
  (`LCEC_HAL_NEW_API`);
- `HOME_SEARCH_DIST` / `HOME_LATCH_DIST` and the sync-return states: `homing_config.h`, which
  the install script generates, defines `CIA402_HOMING_HAS_DISTANCES` when `homing.h` has them.

So: **rerun `scripts/install-drive-homing.sh tpnext` every time `~/src/linuxcnc-tpnext` is
updated or rebuilt.** A module built for another tree loads fine and then misbehaves, because
it carries a stale copy of `homing.c`.

**2. Where "home" is taken from (the patch in `patches/`).** At the end of a drive home,
upstream does this in `custom_sync_position()`:

```c
joint->motor_offset = actual - joint->backlash_filt - H[jno].home_offset;
```

`actual` is where the drive is *standing* when it reports done. That declares the resting
position to be `HOME_OFFSET`. But with `0x60E6 = 0` the drive has already set its own position
so that the index it latched reads `0x607C` (= 0 here). If the drive coasts past the index while
it decelerates and does not go back, `actual` is not 0, and that distance is thrown away: home
would be off by however far it coasted, and would vary with it. At 1 mm/s and 100 mm/s² the
coast is about 5 µm.

The patch adds two pins and uses the drive's own reference when asked to:

```c
double ref = LCEC_PIN_BIT_GET(c->cia_home_ref_enable) ?
    LCEC_PIN_FLOAT_GET(c->cia_home_ref) : actual;
joint->motor_offset = ref - joint->backlash_filt - H[jno].home_offset;
```

- `joint.N.cia-home-ref-enable` (bit, default 0 = upstream behaviour)
- `joint.N.cia-home-ref` (float, machine units: `0x607C / SCALE`, so 0 here)

**Whether it is needed is decided by test H2:** read `cia402.N.pos-fb` right after a drive home.
If it is within ±2 counts (0.00015 mm) every time, the drive returns to the index and the patch
is not needed. If not, build with `HOMECOMP_HOME_REF_PATCH=1 scripts/install-drive-homing.sh
tpnext` and add `setp joint.N.cia-home-ref-enable 1` per drive-homed joint (those pins only
exist in the patched module). The patch applies cleanly to `b13bf72`; **it has not been
compiled or run.** If it proves itself, it should go upstream as a pull request.

**3. Completion bits: no change expected.** `cia402` (lcec, not the homing module) decides
"done" on statusword bits 10 + 12. The A6 manual lists bit 10 "home located or homing
interrupted", bit 12 "homing completion output" and bit 15 "homing completion"; another A6
homing component in use tests 12 *and* 15. So bit 12 should be there. H2 logs the statusword to confirm. If bit 12 never
came, the fix would belong in lcec's `cia402.c`, reported upstream with the log.

**4. Not needed after all: the shared-bus guard.** It is done in HAL through the module's
existing `cia-stat-fault` input. The only cost is the misleading "drive fault" wording.

## Hardware prep

1. **Z: one jumper wire.** From the shared Y/Z home bus (the node already on slave 0 DI3/DI4
   and slave 1 DI3/DI4) to **slave 2 (Z drive) CN1 pin 8 = DI3**. Until then Z stays on switch
   homing. Wire it the same way round as the others (same COM, pin 13).
2. **Better, when convenient: un-short the Y and Z home switches** so each drive sees only its
   own. Then the guard never fires and Y/Z can start from anywhere.
3. Nothing for X or A.
4. If H0 finds a switch-to-index clearance under 2 mm or over 8 mm on an axis, that axis needs
   its switch flag moved a few mm, or the motor coupling re-clocked on the screw. Software can't
   move the index.

## Test plan

Log raw results to `logs/drive_homing/<date>_<test>.md`. Hand on the E-stop for every test
that moves. Terminal commands need `source ~/src/linuxcnc-tpnext/scripts/rip-environment` first.

### H0: before switching branches (on `dev-jerk-testing`, switch homing)

a. **Baseline repeatability.** Run R1 from the repeatability plan. This is the number drive
   homing has to beat, measured the same way on the same day.

b. **Index survey**, per axis, with that axis homed in this session:
   `python3 scripts/index_survey.py X` (then Y, then Z). It arms the drive's Z latch
   (`0x60B8 = 0x15`), you jog the axis slowly about 25 mm, and it prints:
   - the latched raw positions and their value mod 131072: **the spread must be ≤ 8 counts.**
     This is the "is the index talking to us reliably" check;
   - the clearance between the switch edge and the index the drive will take: **2 to 8 mm**;
   - the `HOME_OFFSET` that keeps machine zero where it is today.

   Record all three per axis. If the SDO write to `0x60B8` is refused, report it and stop.

c. `scripts/drive_homing_d0.sh`: read-only record of each drive's homing objects, the list of
   supported methods (`0x60E3`), DI functions and hard-stop parameters. Keep the file: it is the
   record of original values.

**Go:** residue spread ≤ 8 counts on X; X clearance 2–8 mm; methods 5, 3 and 34 in `0x60E3`.

### H1: install, load, polarity (no homing)

1. Close LinuxCNC. `git checkout dev-drive-homing`. Put the X `HOME_OFFSET` from H0 into
   `[JOINT_0]` (replacing the placeholder 0.0).
2. `scripts/install-drive-homing.sh tpnext`. It refuses to run if `~/linuxcnc-ethercat` has
   local changes, and backs the old modules up to `~/drive-homing-backup/<time>/`.
3. Start with the tpnext launcher. **lcec 1.41 → 1.49 is a big jump on its own** (1.44 changed
   M2R DC resync, 1.46 added Sync Units), so before anything else: machine on, jog every axis,
   run a short G61 program. No vibration at enable (CLAUDE.md rule 7), no Er47.0, DRO moves
   10 mm for a 10 mm jog (and 10° on A).
4. With the machine off, check:
   - `joint.0.is-custom-homing` and `joint.3.is-custom-homing` TRUE; joints 1 and 2 FALSE;
   - `cia402.N.pos-scale` = 13107.2 (A 364.0889); `cia402.N.auto-fault-reset` FALSE;
   - `halcmd show thread servo-thread`: `lcec.read-all` → `cia402.N.read-all` → … `or2.6`,
     `or2.7` → `motion-command-handler` → `motion-controller` → `cia402.N.write-all` →
     `lcec.write-all`;
   - `lcec.0.N.opmode-display` = 8 with the machine on.
5. **X switch polarity as the drive sees it** (jogging only):
   `ethercat upload -p 0 -t uint32 0x60FD 0`, bit 2 (value 4) = "home signal active".
   - X well off the switch: bit 2 must be **0**.
   - Jog X onto the switch (it is unhomed, so go slowly): bit 2 must be **1**.
   - `lcec.0.0.di-2` must still toggle as before.

   If bit 2 is the wrong way round: `ethercat download -p 0 -t uint16 0x2004 6 0`, re-check,
   and change the `2004:06` line in `ethercat-conf.xml` to `00 00`. **Do not home X until this
   is right**: with it inverted the drive would run toward +X looking for the switch.

### H2: A on the bench (index only, nothing attached)

1. Capture at the servo rate (`halscope` or `halsampler`): `lcec.0.3.status-word`,
   `lcec.0.3.opmode-display`, `joint.3.cia-state`, `cia402.3.home`, `cia402.3.stat-homing`,
   `cia402.3.stat-homed`, `cia402.3.pos-fb`, `joint.3.motor-pos-fb`, `joint.3.homed`.
2. Home A (its home button).

**Pass:** the drive goes to mode 6, turns to its index, returns to mode 8; `joint.3.homed` = 1;
the command never steps at the hand-back; no Er87.1 or Er47.0.

**Record:**
- Which statusword bits are set at the end (10, 12, 15).
- `cia402.3.pos-fb` right after homing, before the final move, over 5 homes. Within ±2 counts
  (±0.0055°) every time → the drive returns to the index, no patch. Otherwise → patch (see
  *Changes to the homing module*, item 2).
- Home 5 times in a row **without power-cycling**: every run must really move. One that
  finishes instantly is the "homing only works once per power cycle" failure; stop and report.
- `joint.3.cia-state` reaches 2 within 0.5 s of the request.

### H3: X, first drive home

1. Jog X to 20–30 mm from the home switch. `DRIVE_HOME_TIMEOUT_MS` is 90 s; be ready to stop it
   much sooner.
2. Home X only (not REF ALL). Expect: toward −X at 12 mm/s, switch, slow reverse, stop within
   10 mm. **If it starts toward +X, or passes the switch, E-stop.**
3. Check it took the expected index: jog X slowly back onto the switch and read the DRO when
   `lcec.0.0.di-2` changes. It must read the old switch position (−5) within about 0.2 mm. A
   reading 10 mm off means the neighbouring index: stop and report with the H0 numbers.
4. Repeat from: on the switch, 5 mm off it, 100 mm away. Same result each time.
5. Abort paths, each leaving X **unhomed** with no motion afterwards: ESC during the search
   (`homing aborted: cancelled`), E-stop during the search, machine off/on after a good home then
   a jog (no jump).
6. Turn the pendant wheel during a home: nothing may move.

### H4: X repeatability

R2 from the repeatability plan (X is drive-homed, Y and Z still on switches, so only the X
numbers are new). Then the power-cycle series.

### H5: Y (shared bus)

1. Edit together: `[JOINT_1]` `DRIVE_HOME_ENABLE = 1`, `HOME_OFFSET` from H0,
   `HOME_SEARCH_VEL = 0.0`, `HOME_LATCH_VEL = 0.0`; in `ethercat-conf.xml` slave 1, DI4 function
   `05 00` and logic as found for X.
2. Polarity check as H1.5 on slave 1, with **Z off its switch**: `0x60FD` bit 2 follows the Y
   switch.
3. **Guard test first:** jog Z up onto its switch, then home Y. It must abort at once with
   `homing aborted: drive fault` and **not move**. Then with Y on its own switch: same.
4. Jog both off the bus. Home Y from 20–30 mm away, then as H3 steps 3–6.

### H6: Z (after the jumper)

1. Edit together: `[JOINT_2]` `DRIVE_HOME_ENABLE = 1`, method 3, `HOME_OFFSET` from H0,
   velocities 0; slave 2 DI3 function `05 00` + logic.
2. Polarity on slave 2 with Y off its switch.
3. **Guard test first:** Y on its switch, home Z → immediate abort, no motion. This one matters
   most: without the guard Z would go **down**.
4. Home Z from 20–30 mm below the switch. Expect: up, switch, slow down, stop. As H3 steps 3–6.

### H7: whole machine

REF ALL (Z → X → Y → A) five times from scattered positions. Then, on each axis: force a drive
fault during homing (must end unhomed, machine off); re-power the drives' logic with the machine
homed and see whether the joints unhome (if they stay "homed", that needs HAL to unhome them,
and proof).

### H8: stored positions

If every `HOME_OFFSET` came from H0, machine zero has not moved by more than the old switch
scatter (tens of µm). Still, with **CLAUDE.md rules 1 and 2** in force, re-check the toolsetter,
laser and tool-change positions with closed-loop G38 seeks from `G53 Z0`, never a rapid to a
stored value. Then update `docs/HARDWARE.md`, `docs/CONFIG_TOUR.md`, `CLAUDE.md`.

## Repeatability test plan (touch probe on a block in the vise)

**What is measured.** A block clamped in the self-centering vise is probed with the touch
probe (T99) after every home: the top face (Z) and the X and Y centers, all in G54, with G54
left untouched. If homing puts machine zero somewhere else, the block appears to move by the
same amount. The center of a block cancels the probe's own pre-travel, so it is a clean number.

**Tool:** `scripts/home_repeat_test.py` (same script on both branches). Per cycle it lifts Z,
moves a random ±15 mm in XY, unhomes and homes Z, X, Y, returns, touches the top, and runs the
Probe Basic ridge probes twice per axis in measure-only mode. One CSV row per probe; a summary
(range, standard deviation, shift against the start) at the end.

**Setup, the same for every series:**
- Block in the vise, clamped once and **not re-clamped** during a series. Note the torque.
- T99 loaded and not re-seated during a series. Stylus over the block center, ~2 mm above it.
- Note the room temperature and whether the machine is cold or warmed up (spindle + axes 30 min).
- `--hint-x` / `--hint-y` = block width + ~2 mm.

| # | Series | Config | How | What it shows |
|---|---|---|---|---|
| R0 | Probe noise | either | The two ridge probes inside each cycle, and the `start` row | The floor: nothing below this can be blamed on homing. Earlier work on this machine: under 1 µm in a session |
| R1 | Baseline, in session | `dev-jerk-testing` | `--cycles 20` | Switch homing scatter with nothing power-cycled |
| R1p | Baseline, power cycles | `dev-jerk-testing` | `--cycles 0` once, then 8× (shut down, drives off 30 s, on, REF ALL, `--measure-only --note "pc N"`) | The known problem: X +60, Y +45…64, Z +16 µm between power-ups in November |
| R2 | Drive homing, in session | `dev-drive-homing` | `--cycles 20` | Index homing scatter |
| R2p | Drive homing, power cycles | `dev-drive-homing` | as R1p | Whether the power-up shift is gone |
| R3 | Warm vs cold | `dev-drive-homing` | R2 cold, then again after 30 min warm-up | Thermal growth, so it isn't mistaken for homing error |
| R4 | Wrong-index hunt | `dev-drive-homing` | `--cycles 50 --reps 1 --scatter 40` | Any 10 mm jump. The script stops on the first one |

**Pass:**
- R2 range per axis ≤ 3 µm, or no worse than the R0 floor plus 2 µm.
- R2p range per axis ≤ 5 µm at steady temperature (the baseline was 45–64 µm).
- R4: zero jumps in 50 homes.
- No drive faults or LinuxCNC errors in any series.

**Reading the results:**
- A shift of almost exactly 10.000 mm = wrong index (clearance problem, H0b).
- R2 good but R2p bad = something changes at power-up that the index doesn't fix: look at
  thermal state first (R3), then at the drive's position frame after power-up.
- X good, Y/Z unchanged while they are still on switches is expected, and is a useful control.
- The same drift on all series, growing with time = temperature, not homing.

Keep the CSVs in `logs/homing_repeat/` and add a short `README.md` with the table of results.

## Torque (hard-stop) homing: research, not active

Goal: drop the home switches. The stop only has to pick the screw turn; the index still sets the
position, so the same 2–8 mm clearance rule applies (stop to index).

**What is known:**
- The A6-EC manual's homing chapter documents methods **−1 / −2**: reverse / forward to the
  mechanical end, then the Z pulse. But its own object list for `0x60E3` (supported methods)
  gives 1–14, 17–30 and 33–35 only, and StepperOnline said on the forum that torque homing is
  not supported. One user reports −1 working on default parameters. **H0c settles it**: read
  `0x60E3`, then write `0x6098 = -1` and look for ALF4.2.
- Parameters: **C10.30** torque limit while homing against the stop (0.1 %, default 1000 =
  100 %, far too high), **C10.31** speed (rpm, default 10), **C10.32** "number of times for
  homing upon hit-and-stop" (default 30; most likely the stall confirmation count). The manual's
  index column for these is shifted by one against the usual `C<g>.<n>` → `0x20<g>:<n+1>` rule,
  so read `0x2010:31…34` in H0c and match by default value before writing anything.
- The drive's following-error window here is 0.5 mm / 250 ms; pushing on a stop will likely
  trip Er47.0. It would have to be widened only while homing (map `0x6065`, or raise it by SDO
  around the home).

**Three ways to do it, in order of preference:**
1. **Drive-native −1 / −2**, if H0c says the firmware has it. Only `DRIVE_HOME_METHOD` and the
   three C10 parameters change; everything else in this branch is reused.
2. **LinuxCNC finds the stop, drive finds the index.** Map max torque `0x6072` into the RxPDO
   (the tenth and last slot), lower it to ~20 % for the search, move slowly, and call it "home
   switch" in HAL when torque (`6077`) sits at the limit with speed near zero for a set time.
   Then hand over to drive method 33/34 (index only). Needs a two-phase home, which the module
   does not do today.
3. **Torque stop as a virtual home switch for LinuxCNC's own index homing**, with the drive's
   Z latch (`0x60B8`, already used by `index_survey.py`) feeding `index-enable`. No drive homing
   mode at all, so no mode switching, but a small HAL component of our own.

**Mechanical points whichever way:** a dedicated rigid stop per axis (not the screw nut on the
end bearing, not a bumper), the lowest torque that detects 10 out of 10, Z homing upward so
gravity always loads it the same way.

The parked step-by-step plan for option 1, written before the switch-first decision (its "D"
test numbers refer to the earlier plan):

> ### D3: Tune the hard-stop homing on one linear axis (X), still with no LinuxCNC homing
> Use drive homing only, started from LinuxCNC as in D2. Do it on X first.
> 1. Start with C10.30 = 20 %, C10.31 = 10 rpm, `0x609A` modest. Jog X about 20 mm away from the stop first.
> 2. Home. Watch it drive into the stop, stall, back off to the Z pulse, and report homed.
>    - If it never detects the stop (it keeps pushing until the timeout): raise C10.30 in 5 % steps.
>    - If it "detects" the stop in mid-air (friction spikes): lower the speed or raise the stall time.
>    - Stay at the lowest torque that detects the stop reliably, 10 out of 10.
> 3. Watch the drive's following-error window (`0x6065` = 0.5 mm / 250 ms). Find
>    out whether it trips Er47.0 while pushing against the stop in homing mode. If
>    it does, stop and decide with Jon how to widen it only during homing (e.g.
>    map `0x6065` into the RxPDO and switch it on `cia402.N.stat-homing`). Don't
>    widen it permanently.
> 4. **Stop-to-Z clearance (important):** log `lcec.0.0.pos-fb` at the stall and
>    at the Z pulse (before the drive zeroes it). Clearance = travel from the stop
>    to the Z pulse, 0 … 10 mm.
>    - It must be **2–8 mm**, ideally about 5 mm. Near 0 or 10 mm, the stall-point
>      scatter can pick the next Z pulse, and home jumps by 10 mm.
>    - To fix it, move the stop block or rotate the motor coupling on the screw.
>      The software can't move the drive's Z pulse.
>    - Record the final clearance for every axis in `docs/HARDWARE.md`.
>
> **Pass:** 20 out of 20 homes detect the stop, the clearance spread is under
> ±0.5 mm, and there are no faults.
>
> ### D4: X repeatability
> 1. **Baseline first:** with the old config (switch homing), 20 homes, each read
>    on a 1 µm indicator against a fixed block at a fixed G53 position.
> 2. New config: 20 homes cold. Then exercise the spindle and axes for 30 min and do 20 more warm.
> 3. Set `HOME_OFFSET` and `HOME` so the machine coordinates make sense. Re-check
>    soft limits against the new zero, so that travel never reaches the stop in
>    normal use.
>
> **Pass (A1, A3):** the indicator range is ≤ 2 µm in each set and no worse than
> the baseline. No faults.
>

## Risks to watch

| # | Risk | Where it's caught |
|---|------|-------------------|
| K1 | Switch polarity inverted in the drive → it searches the wrong way with nothing but the timeout to stop it | H1.5, H5.2, H6.2 before any home |
| K2 | Index too close to the switch edge → home jumps 10 mm | H0b clearance, H3.3, R4 |
| K3 | Shared Y/Z bus closed at the start → Y runs to +, Z runs **down** | HAL guard; H5.3 and H6.3 prove it before the first real home |
| K4 | `DRIVE_HOME_ENABLE` and the search/latch velocities out of step → joint homed in place | Edit them together; H1.4 |
| K5 | lcec 1.41 → 1.49 changes DC sync behaviour | H1.3 smoke test before any homing |
| K6 | Module built for another LinuxCNC tree | Rerun the install script after every tpnext rebuild |
| K7 | The drive stops past the index and the module calls that spot home | H2 record → patch |
| K8 | The A6 flags done on bit 15 only → home never completes (times out safely) | H2 statusword log |
| K9 | Stale target when CSP resumes → Er87.1 jump | Module re-sync (upstream sim-tested); H2 |
| K10 | LinuxCNC feedback is held during the drive's move, so only drive-side protection is live | Drive following-error window, C10.08, `DRIVE_HOME_TIMEOUT_MS`, hand on E-stop |
| K11 | DI function and logic writes stay in the drive's EEPROM after they leave the XML | Rollback writes them back to 0 explicitly |

## Rollback
- **Config:** check out `dev-jerk-testing` (or revert this branch's commits).
  That restores the `6060 = 08` SDO, the old scaling and the switch-homing
  `HOME_*` values, and removes `HOMEMOD`.
  - lcec 1.49 can stay: its `cia402` keeps the same pin names as the old one
    (`pos-scale` defaults to 1, `csp-mode` to CSP).
  - Its `auto-fault-reset` defaults to **1**, though. On the old config, add
    `setp cia402.N.auto-fault-reset 0` or restore the backed-up modules.
- **Modules:** `scripts/install-drive-homing.sh` saved the old `lcec.so`,
  `cia402.so` and `lcec_conf`, plus the previous lcec commit, in
  `~/drive-homing-backup/<time>/`. Copy them back (sudo for
  `/usr/lib/linuxcnc/modules`, `/usr/bin`), or check out that commit and
  rebuild lcec.
- **DI functions:** set `0x2004:05/06` (slave 0) and any Y/Z ones back to 0 with `ethercat download`, or keep the XML lines with `00 00`. `dev-jerk-testing` already writes the five function objects to 0 at every start, but not the logic objects.
- **Drive values:** explicitly write back the original drive values recorded
  in H0c with `ethercat download`. The A6 keeps SDO writes after they're removed
  from the XML (F6). Keep the stored positions from before H8 in the log.
- **Our own component** (`a6home`) was the first version of this branch. The branch that kept
  it was deleted on 2026-11-27; its last commit is `ce0861f` if it is ever wanted back.

## Open questions for Jon
- Z jumper: is slave 2 DI3 (CN1 pin 8) free and reachable? Any reason not to un-short Y and Z instead?
- Home switches: mechanical or proximity? (Proximity sensors have more hysteresis, which eats into the clearance.)
- Does the master E-stop cut the drives' logic power? (H7)

## Reference: drive, machine and LinuxCNC facts

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
    "1 to 35". Which one is right gets settled on the real drive in test H0.
- Hard-stop homing parameters (from the A6-PN manual; the EC version should
  match, **verify in H0**):
  - **C10.30**: torque limit while homing against a hard stop, unit 0.1 % of rated, default 1000 (= 100 %, far too high).
  - **C10.31**: hard-stop homing speed, rpm, default 10 (= 1.67 mm/s on a 10 mm screw).
  - The stall detection time is a parameter near those two; find it in H0c.
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
  actually sets has to be logged in H2** (risk K8).
- In CSP mode, the A6 holds statusword bit 10 at 1 all the time.
- Encoder: 17-bit, 131 072 counts/rev, multi-turn absolute. The multi-turn
  part needs the battery; the Z pulse doesn't. The absolute mode is C00.07
  (`0x2000:08`); leave it as it is unless H0c shows a problem.
- StepperOnline replied on the LinuxCNC forum (thread 58323) that the A6 doesn't
  support torque homing. That contradicts the manual's methods −1 and −2. H0c
  settles it on your drives and firmware (`AS715N_sAxis_V0.10`).

**This machine (repo):**
- 10 mm screws, so 13 107.2 counts/mm and one Z pulse every 10 mm. A is 1:1
  (364.0889 counts/° = 131 072/360), so one Z pulse per table revolution.
- Before this branch: CSP mode with `0x6060 = 8` set by SDO and not mapped in the
  PDOs. This branch maps `6060`/`6061` so modes can change while running.
- Before this branch, position scaling was in HAL (`mult2`/`conv-real-sint` on
  the command, `conv-sint-real`/`div2` on the feedback), and the old `cia402`
  only handled enable and fault. Now `cia402.N.pos-scale` does the scaling.
- Before this branch all drive DI functions were cleared (`0x2004 = 0`) and LinuxCNC read the
  raw inputs. Switch + index homing gives the home input back its drive function (5) on each
  drive-homed axis; the limit inputs stay cleared, so the drives never act on overtravel.

**LinuxCNC (`homing.c` in 2.9 and tpnext-ma, `control.c`):**
- `[EMCMOT]HOMEMOD` swaps in a homing module. `cia402_homecomp` `#include`s the
  `homing.c` of the LinuxCNC it is built for, so it is built once per LinuxCNC
  build. `homing.c` is identical in 2.9.8 and 2.9.10. tpnext-ma adds only
  negative-sequence gantry sync and the `HOME_SEARCH_DIST`/`LATCH_DIST`
  fields, which the module detects at build time.
- Each servo cycle: read homing pins → read `motor-pos-fb` → homing → compute `motor-pos-cmd` → write.

**lcec (`linuxcnc-ethercat`):**
- Before this branch the mill ran lcec **v1.41** with an older `cia402` component (enable and fault only).
- lcec ≥ 1.49.0 (2026-11-17) ships a `cia402` with a homing handshake: mode 6
  acknowledged before bit 4, bits 10 + 12, stale status rejected. It also does
  64-bit unwrapped position scaling.
- `cia402_homecomp` adds the LinuxCNC side on top of it: command-as-feedback
  while the drive moves, re-sync at the end or on abort, timeout, fault
  handling. That's what this branch uses (`scripts/install-drive-homing.sh`).

---

## Reference: prior art: what other A6 owners have already done (researched 2026-11-23)

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
- **Contradicting claim:** andrax (thread 54965, page 12) says −1/−2 on the A6 means *limit switch on DI1/DI2* + Z pulse, not torque. **The torque research tests settle this:** the drives' DI functions are cleared (`0x2004 = 0`), so if the axis stops at the block and goes on to find Z, it's torque.

**Existing A6 code and configs to borrow from:**
- **TangentAudio, `github.com/tangentaudio/linuxcnc-bridgeport`** (last commit Apr 2026):
  - The A6 runs Z on a Bridgeport, with **the same `vid 00400000 / pid 00000715`** as this mill. The config comment calls the A6 "an OEM version of Inovance SV660N".
  - Uses method 33 (Z pulse only).
  - **Maps `6060`, `607C`, `6098`, `6099:01/02`, `609A` and `60E6` into RxPDO `0x1600`, and `6061` into TxPDO `0x1a00`.** The A6 accepts all of these in PDOs, so homing settings can be changed live from HAL.
  - Custom `el7_homecomp` / `el7_cia402`. At the end of homing it forces `pos_cmd = 0`, which is right only because `607C = 0` and `60E6 = 0`.
- **Colin Bardini, `github.com/CollinBardini/linuxcnc-a6-servo`** (Feb 2025):
  - An A6 homecomp. **It counts homing as complete when statusword bit 12 AND bit 15 are both set.** So the A6 sets bit 12, and lcec's `cia402` test (bits 10 + 12) should work. This mostly retires risk K8, but H2 still logs it.
  - andrax runs this homecomp in production with **method 4** (home switch + Z) on drive-wired switches (thread 58467).
- **rodw, `github.com/rodw-au/cia402_homecomp`**: a draft, already reviewed (see §3 of the earlier analysis). Not used.
- **Marcos DC, `github.com/MarcosDuqueCesar/linuxcnc-cia402-layer`**: a CiA 402 framework with homing as a separate part. Simulation only, not tested on hardware (Mar 2026). Not used.
- **Konstantin, threads 58808 / 58325** (May 2026): methods 34 and 19 start and finish reliably from dbraun-style `cia402` with `x-home-index`. But see failure F1.

**Failure modes the community has hit, and where this plan handles each:**

| # | What people saw | Likely cause | This plan |
|---|---|---|---|
| F1 | After homing, the drive jumps or "rushes back to where homing started", with Er87.1 or "position deviation too large" (Jugo2 thread 54965 p.12; Konstantin thread 58325 p.6) | CSP resumes with LinuxCNC's stale target from before homing | `cia402_homecomp` syncs LinuxCNC's command to the drive's actual position before CSP resumes (upstream sim-tested). H2 checks the step |
| F2 | "Homing only works once per power cycle" (andrax, Jugo2) | The drive's homed bits (12/15) stay set, so the next request is seen as already done | `cia402` and `cia402_homecomp` only accept "done" after the drive was seen busy since the start. Upstream sim-tested; **H2: home 5 times in a row with no power cycle** |
| F3 | A custom homecomp can't be stopped once started (thread 54965 p.8) | The homecomp has no abort path | `cia402_homecomp` has an abort path ("cancelled") built on `homing.c`'s own. H3.5 |
| F4 | Jumps when the MPG/handwheel is live during homing (andrax) | Jog input reaching the joint during the hand-back | LinuxCNC already drops wheel counts while homing is active (`control.c`, checked in 2.9 and master), so no HAL gate was added. H3.6 proves it on the machine |
| F5 | One axis doesn't start homing and nobody notices (gantry users) | No supervision | C10.08 drive timeout (default 60 s) + `stat-homing` must rise within 0.5 s of `home` (log it in H2). `DRIVE_HOME_TIMEOUT_MS` aborts if it never finishes |
| F6 | Values written with `sdoConfig` **stay in the drive after being removed from the XML** (fer662) | The A6 saves SDO writes | **H0c must record every original value** (`6098`, `6099`, `609A`, `607C`, `60E6`, `2010:09`, `2010:31/32`, stall time). Rollback writes them back explicitly |
| F7 | andrax recommends `sync0Shift="0"` | Timing | Observation only. This mill runs `300000` with M2R and is stable. **Don't change it** unless H2 shows timing problems |

---

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
- `cia402_homecomp` (HOMEMOD used here; README, TESTING.md, headless sim tests): https://github.com/linuxcnc-ethercat/cia402_homecomp
- LinuxCNC `homing.c` / `control.c`: https://github.com/LinuxCNC/linuxcnc (branches `2.9`, `master`), https://github.com/grandixximo/linuxcnc/tree/tpnext-ma
- A6-EC manual, parameter list and descriptions read 2026-11-28: C04 DI functions (5 = home switch, 6/7 = forward/reverse overtravel, 30/31 = probes; logic 0 = active low, 1 = active high), `60FD` bits, `60B8` bits (bit 2 = trigger on the Z signal; on an absolute encoder the Z signal is the single-turn zero), `60E3` list, C10.30–C10.32
