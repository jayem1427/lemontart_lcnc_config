# CLAUDE.md — Lemontart EtherCAT mill (LinuxCNC + Probe Basic)

Working notes for AI agents, distilled from ~60 Cursor chats (May–Nov 2026). It
covers how Jon likes to work, the safety rules that were learned the hard way,
and the machine facts that keep getting re-derived. The full narrative and
postmortems are in [docs/CURSOR_HISTORY.md](docs/CURSOR_HISTORY.md). The raw
transcripts are local only, in `.cursor-history/` (gitignored). Docs index:
[docs/README.md](docs/README.md).

The docs are one topic per page (SETUP, HARDWARE, CONFIG_TOUR, TOOL_CHANGE,
SPINDLE, COOLANT, MODBUS, SERVO_TUNING, …). When you change behaviour, update
the page that owns that topic rather than adding a new doc, and add symptoms
you hit to `docs/TROUBLESHOOTING.md`. Write for someone copying this setup to
their own machine: plain language, short sections, real values from the config.

## Working with Jon

- **Do it, test it, report in one line.** Keep the talk short. If something
  won't work, say so plainly instead of handing over several things to try. Don't
  take credit for things he did himself.
- **Read before you ask.** Pin maps, DB15 pinouts and wiring tables are in
  `README.md`, `docs/`, and the HAL comments. He gets annoyed when you ask
  for something that's already documented.
- **"Figure out why" means investigate only.** Change files only when he says
  to apply, fix, implement, or do it. One agent edited files when it was only
  asked to diagnose, guessed wrong, and was told to revert. After that, the
  rule is to diagnose first.
- **Don't move or rename his files** (macros, G-code, docs) unless he asks.
- **Restore before you reinvent.** If he says "this worked a few days ago",
  look in git history and restore that logic. Don't design a new approach.
- **Rollbacks are normal.** He often says "roll back to last night" or "revert
  to the last stable commit". Do it with git, say which commit you landed on,
  and don't force-push unless he asks.
- **Make features easy to switch off.** Mark them with clear `REVERT:` / START–END
  comment blocks.
- **Keep the UI quiet.** No chatty `(DEBUG, …)` popups during normal runs. Keep
  only the failure messages.
- **Git:** commit messages describe what changed. Don't open PRs ("just commit
  to the branch"). Push only when he asks, which he does often. Document changes
  in `README.md` / `docs/` as part of the same change ("document it well").
- He'll name the model or agent he's talking to (opus, grok, fable, composer,
  codex). That's just how he talks and doesn't mean anything for the work.
- `sudo` needs his password. Give him the exact command for his own terminal and
  don't try to get around the prompt.

## Hard safety rules (each one came from a real incident)

1. **Never command a guessed rapid near the toolsetter or laser.** If a position
   (`#5181–5183`, beam XY) is unset, stay at `G53 Z0` and probe down with
   G38. One invented setter-Z rapid crashed into the plate, and a mirrored-start
   `G0` hit the laser body.
2. **Never send a probe target above `G53 Z0`.** Z soft max is above home,
   so an unclamped target drives Z into the hard stop.
3. **Seeks must be closed-loop.** Use G38 so motion stops on the signal.
   An open-loop `G1` step-seek that ignored the beam had to be E-stopped.
4. **Never use `HOME_ABSOLUTE_ENCODER = 1` to get a "no-motion REF".** It caused
   a Y runaway. For home-in-place, set SEARCH, LATCH and FINAL velocities and
   `HOME_OFFSET` all to 0.
5. **No motion in `on_abort.ngc`.** E-stop runs it while motion is disabled
   ("need to be enabled…"). Park moves belong in the tool-change ABORT button path.
6. **Drive gains (C00/C01 SDOs) don't go in `ethercat-conf.xml`.** They
   overwrite bench tuning every time LinuxCNC starts, and Jon lost work to this
   twice. The only exceptions he approved are `0x2001:0x11 = 3` (speed
   observer) and the 6065/6066 fault windows.
7. **DC clock mode is M2R (`refClockSyncCycles="-1"`).** R2M made the whole
   machine vibrate violently on enable.
8. **Before any `net`/`setp` change, check who already owns the pin or signal**
   (`grep -n` across every HAL file). See the HAL skill.

## Stack and paths

| Item | Value |
|---|---|
| Config repo | `/home/jon/linuxcnc/configs/ethercat_mill` → GitHub `jayem1427/lemontart_lcnc_config` (older Cursor paths say `~/Desktop/ethercat_mill`) |
| Branches | `main` and `dev-jerk-testing` were consolidated on 2026-11-18 (same commit; both carry the tpnext INI). Work on `dev-jerk-testing`. `dev` was deleted (fully merged). `dev-no-limit-switches` is a local WIP snapshot. Old work is in `archive/*` tags |
| LinuxCNC | stock apt **2.9.8** (`launch.sh`, Desktop "Launch_Mill") **and** experimental **tpnext-ma** run-in-place build at `~/src/linuxcnc-tpnext` (`launch-tpnext.sh`, Desktop "EtherCAT Mill (tpnext / jerk)") |
| OS / RT | Debian, PREEMPT_RT kernel 6.12.x-rt |
| UI | Probe Basic 0.6.6 / QtPyVCP 5.1.0 (Debian pkg). Log: `~/qtpyvcp.log` |
| EtherCAT | IgH master 1.6.8 + linuxcnc-ethercat **v1.41.0** built from source in `~/linuxcnc-ethercat`. **Native `ec_e1000e` driver** on the onboard I219-LM since 2026-11-28 (was `generic`; backup `/etc/ethercat.conf.bak-generic`). Switch drivers with stop → rmmod → edit → start, never `restart`. CPU governor `performance` via `cpu-performance.service`. Details: `docs/SETUP.md#ethercat-driver-and-timing` |
| Scripts vs tpnext | With the tpnext build running, any terminal `halcmd` / `import linuxcnc` needs `source ~/src/linuxcnc-tpnext/scripts/rip-environment` first (else "HAL version code mismatch", stat all zeros) |
| Drives | 4× StepperOnline **A6-EC** (CiA402 CSP, `6060=8`), firmware `AS715N_sAxis_V0.10`, 17-bit encoders. **Every SDO write is stored to drive EEPROM** (C13.10 `0x2013:11` = 1 on all four): APPLY/one-click persist across power cycles; undo = LOAD backup preset + APPLY |
| Spindle | H100 VFD over Modbus (`h100.mb2hal`), max 24 000 RPM. Own **CH340** USB-RS485 adapter, 38400 8N1 slave 1 |
| Coolant | Microject PWM MQL board over Modbus (`microject.mb2hal`, `coolant.hal`). Own **FTDI** adapter, 19200 8E1 slave 8. Both `.mb2hal` files use `/dev/serial/by-id/` paths |
| Pendant | XHC WHB04B-6 wireless (`xhc-whb04b-6.hal`, `-HsfB`) |
| G-code folder | `PROGRAM_PREFIX = /home/jon/linuxcnc/nc_files` (outside the repo, synced to "workShopPC" via Syncthing). The repo's `nc_files/` is **not** what LinuxCNC opens |
| CAM post | Fusion `post-processor/linuxcnc-djr.cps` (emits `T<n> M600`, G94 header) |

## Machine facts

- **Joints:** 0=X, 1=Y, 2=Z, 3=A (A is mechanically unconnected, homes in place).
  EtherCAT slave N drives joint N.
- **SCALE:** XYZ `13107.2` counts/mm (131072 counts/rev ÷ 10 mm ballscrew), A
  `364.0889` counts/°. 1 count ≈ 76 nm, and 0.1 mm = 1311 counts. Scaling is done
  in HAL (`mult2`/`div2`), not by lcec.
- **Limits:** X −254…370, Y −254…308, Z −203.2…400 (raised from 3.048 so you can
  jog unhomed). Velocity XY 500 mm/s (30 m/min), Z 166.7 mm/s.
- **Accel/jerk (tpnext branch):** 6865 mm/s² (0.7 g), `PLANNER_TYPE=1`, jerk
  30 000 mm/s³ on all axes. Keep X and Y jerk equal so arcs feed evenly. On the
  tpnext build these are live pins (`ini.traj_planner_type`,
  `ini.traj_max_jerk`, `ini.N.max_jerk`); change them with `halcmd setp` and no relaunch.
  tpnext needs `initf lcec.activate servo-thread` in HAL.
- **2.9.8 trajectory planner quirk:** with G64 blending, stop-to-stop moves only get **half** of
  `MAX_ACCELERATION` (LinuxCNC #4220), so a 100 mm move tops out around 23 m/min.
  Put `G61` in test programs. Jogging gets full acceleration.
- **Following error is split on purpose.** LinuxCNC `FERROR 1270 / MIN_FERROR 254` is
  effectively off. The drive enforces it: `6065 = 0.5 mm` (6554 counts; A widened to 3641 counts = 10° while unconnected, normally 182) and
  `6066 = 250 ms` → Er47.0 → `amp-fault-in`. The tuning tools raise 6065
  temporarily (inertia ID 2.0, one-click 1.0) and restore it in a `finally` block.
- **Digital inputs:** lcec reads raw DI from PDO `0x2040:05` → `lcec.0.N.di-1..5`
  (only di-1…5 exist). Drive DI functions are cleared with `0x2004:01/05/09/0d/11 = 0`.
  DB15/CN1: DI1=pin 10, DI2=9, DI3=8, DI4=7 (TouchProbe2), DI5=11 (TouchProbe1),
  COM=13, +24 V=15. Check NPN vs PNP wiring (GND+SIG vs 24V+SIG).
- **Current DI map after the Oct–Nov 2026 rewire QC** (`ethercat_mill.hal`):

  | Function | Pin | Notes |
  |---|---|---|
  | X home | `lcec.0.0.di-2` | debounce 5 ms |
  | X limit (both ends) | `lcec.0.0.di-5` | suppressed while X homes |
  | Y limit | `lcec.0.0.di-1` | took over the former Z− limit input |
  | Y home **+** Z home | `lcec.0.1.di-4` | **one shared, shorted bus** (also ties 0.0.di-3/4, 0.1.di-3); 8 ms debounce; homes are serialized |
  | Z− limit | — | disabled (no free DI) |
  | Touch probe (T99) | `lcec.0.1.di-2` | swapped in HAL, not rewired |
  | Contact toolsetter | `lcec.0.1.di-5` | |
  | Laser DS-5V-M beam | `lcec.0.2.di-5` | TRUE = blocked |
  | Software E-stop (NC) | `lcec.0.3.di-1` | gates `emc-enable-in` |

- **Homing:** REF ALL runs Z(seq 0) → X(1) → Y(2) → A(3, in place).
  `NO_FORCE_HOMING = 1` (Jon wants to be able to jog unhomed). Same-sign latch,
  `HOME_IGNORE_LIMITS=YES`, and HAL ignores a shared bus that's already closed when
  a home starts. The pendant MPG is wired to both joint and axis jog pins.
  `HOME_IS_SHARED=1` broke Z ("cannot home while shared switch closed").
- **Probe routing:** `halui.tool.number == 99` (`comp.0`) → touch probe only.
  Any other tool → toolsetter only. `M62 P0` switches `motion.probe-input` over to the laser
  for G38, and `M63 P0` restores it. Wrap **only** the G38 moves in M62.
- **Tool change:** `REMAP=M600` runs `tool_touch_off.ngc` (TooTall18T-derived). It parks at
  **G53 X270 Y100 Z0**, shows a custom OK dialog (green Resume / red ABORT),
  then probes on the setter at `#5181–5183`. If the same tool is already in the
  spindle it just applies `G43` and returns. Built-in M6 motion is off. Tool-length Z must come out positive.
- **Spindle:** M3/M4 are swapped in `custom.hal` (VFD wiring). On this machine
  G-code `M3` means VFD reverse.
- **Coolant (MQL):** `M201 P<Hz 0.1–50> Q<duty 0–100> R<psi, stored only>`, `M202`
  is the per-tool recipe, `M8`/`M9` turn it on/off. There's a Probe Basic tab in `user_tabs/mql_control/`.
- **Key params:** `#3004–3039` are probe/toolsetter settings (`#3014=99` is the probe tool),
  `#5181–5183` is the setter position, `#5501/5502` beam XY, `#5503` probe RPM, `#5516` beam
  width cal, `#5517` master pin, `#5518` reverse-spindle flag, `#5580–5586` vise stop (docs/VISE_STOP.md). Max user param is **5599**.
  `linuxcnc.var` is **tracked in git** and must stay sorted ascending.

## LinuxCNC rules that bit us (details in the skills)

- **HAL** → `.claude/skills/linuxcnc-hal-edits/SKILL.md` (source copy: `docs/agent-skills/`): count=/names= mixing,
  one writer per signal, bit vs float types, TWOPASS load order, component inventory.
- **NGC / INI / remap** → `.claude/skills/linuxcnc-ngc-macros/SKILL.md` (source copy: `docs/agent-skills/`): nested
  comments, ASCII + LF only, G53 only with G0/G1, startup-code limits, the M100–199
  remap restriction, frozen `#<_hal[]>`.
- **Probe Basic:** it loads *every* folder in `probe_basic/user_tabs/`. After a
  branch switch, delete leftover tab dirs that only contain `__pycache__`, or PB crashes.
  Don't `deleteLater()` QtPyVCP `MDIButton`s. Use standard checkable Qt buttons
  instead of custom click logic. Don't block the Qt thread. The font family is `BebasKai`
  (no space). PB's own dark background is `#2e3436` (panels `#363b3d`), but
  for new tabs Jon prefers the **CONVERSATIONAL page look**: page `#818584`,
  panels with the conversational gradient (`rgb(81,86,85)`→`rgb(109,115,118)`)
  and a 2 px black border (see `vise_stop.qss`).
- **In-process HAL reads:** `hal.get_value` only works on the thread that created
  the component, and it returns NaN for some pins (e.g. `joint.N.f-error`). Read the raw
  `lcec.0.N.*-fb` pins through `a6_servo_tune`'s component, and get host values from
  `linuxcnc.stat`. Don't run a `halcmd` subprocess per sample.
- **Startup noise you can ignore:** the Qt segfault in `QPlainTextEdit::focusOutEvent`
  on exit, "Failed to get reference clock time", and mb2hal transaction errors at shutdown.

## Open threads (as of 2026-11-28)

- **Servo tuning engine v2.1: run on the machine 2026-11-27.** Gains on the
  drives now: X 150 Hz / 360 rad/s / 3 ms (RMS FERR 3.2× lower), Y 37.5 / 90 /
  3 (1.7×), **Z kept at 26 / 50 / 3**. Z's tune (34.4 / 82.5) whined audibly
  and was reverted. Don't load Z `new_tuning` / `one_click_20261127_234730`.
  Two engine fixes from the Z runs: an unscored warm-up move before the
  baselines (first-move spike inflated the bar to 15 %), and standstill
  torque RMS about the mean (gravity hold read as 12 % hiss). The tuner can't
  hear a whine above 500 Hz, so Z needs a listen. Results and plots:
  `docs/SERVO_TUNING.md` (First machine runs), lessons in
  `docs/ONE_CLICK_TUNING.md`. Deferred on purpose: chirp injection (command
  path) and 0x60B2 load rejection (PDO map). Both collide with
  `dev-drive-homing`, so do them after that merges.
- **The "clunk" (heard on the 2026-11-25 Reducer job): not mechanical on Y.**
  The reversal test (`scripts/clunk_*.py`, `docs/SERVO_TUNING.md#reversal--clunk-test`)
  found no backlash or loose-nut signature on Y with the new gains: every
  reversal overlays, asymmetry ≤ 1.7 µm. The only event was a one-cycle
  EtherCAT timing glitch on the generic driver (a late frame, missed position
  update, ±20 µm for 3 ms). It was gone in a 5 min stress run on the native
  driver, but that's not proven (it was rare on generic too). Not yet run on X
  or Z, or with a microphone. The drive's C13.09 invalid-frame counter read
  24 064 on slave 0 (others 0) on 2026-11-28. Check whether it grows.
- **Drive homing vs upstream (checked 2026-11-27).** `cia402_homecomp` has no
  commits after the pinned `b13bf72`; lcec after v1.49.0 only changed the
  Delta ASDA driver. LinuxCNC master/tpnext-ma moved to the 64-bit HAL API
  (2026-09-18) and changed `homing.c` (sync groups, bounded moves, abort
  fixes; `homing.h` unchanged). homecomp CI builds against 2.10.0-pre2 (has the
  64-bit API), so build it against the tpnext RIP tree, not the stock 2.9.8
  headers, and re-run D1/D2 on the tpnext launcher. No conflict with the tuner:
  both branches keep the 60F4/6077/606C PDOs and the `*-s32` signals.

- **Spindle back on Modbus (2026-11-18)** on its own CH340 adapter; fault→E-stop net reconnected. Confirm M3/at-speed/fault read on the machine.
- **MQL Probe Basic tab** clipping fixed 2026-11-18 (fits 1645x619). Not yet checked on the real screen.
- **Wiring:** Y/Z home short and EMI on the home inputs. Z− limit has no DI. Reducing these
  to software workarounds was a deliberate choice ("move forward with that in mind").
- **Laser diameter on fluted endmills** reads about 0.25 mm small (optical
  silhouette). Pin repeatability is about ±7 µm. Next idea: PROBE RPM 400. Don't add a pulse
  stretcher on the G38 path. See `docs/LASER_TOOL_SETTER.md`.
- **Graphical inertia ID** is still unreliable because the 606C/6077 PDOs stair-step.
  Keep C00.06 ≈ 100–120 % (manual). Drive-internal ID (C07/F30) isn't reachable over EtherCAT.
- **"Must re-home to jog after a job":** after M30 the machine is still in Auto with a stuck jog. A HAL plan was drafted but never built.
- **Conversational tab** hard-codes `M6`. The fix lives in the system package `qtpyvcp_conversational_gcode`.
- **The probed block center shifts tens of µm between power-ups (parked, unsolved, 2026-11-25).**
  It's stable to under 1 µm within a session. Between 11-18 and 11-25 the shifts reached X +60, Y +45…64
  and Z +16 µm. Ruled out as the main cause: probe runout (~4 µm), home latch delay (≤12 µm), backlash
  and temperature. The leading suspect is the home sensors' switch point shifting between power-ups (if
  they're prox sensors, warm-up or supply voltage). Next tests: a fixed reference every session, a warm-up
  re-home with no restart, and restart vs power-cycle. The likely fix is index homing. Write-up:
  `logs/metrology/20261123_block/plots.html`. The T99 length (45.0422) is still unverified.
- **The INI on `dev-jerk-testing` uses tpnext-only keys** (`TPMOD=tpnextmod`,
  `PLANNER_TYPE`, `MAX_JERK`). Check that the stock `launch.sh` still starts before relying on it.
