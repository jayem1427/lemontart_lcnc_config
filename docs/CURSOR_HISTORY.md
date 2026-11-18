# Cursor-era history (May → Nov 2026)

A distilled record of ~60 local Cursor agent chats plus 14 Cursor cloud-agent chats
that built this config. Use it to answer "why is it like this?" and "did we
already try that?". The current rules for agents are in [../CLAUDE.md](../CLAUDE.md).
Full transcripts are local only in `.cursor-history/` (gitignored; secrets redacted).

---

## Timeline

### May 2026: bring-up
- Fixed the original config. `TWOPASS` needs `lcec_conf` in its own
  `ethercat_loadusr.hal` (`#NOTWOPASS`). Probe Basic requires
  `[DISPLAY] INTRO_GRAPHIC`, the tool table path, and `SPINDLES=1`.
- **SCALE** corrected from 26214.4 to **13107.2 counts/mm** (17-bit, 10 mm pitch). A = 364.09 counts/°.
- Pendant jog smoothing went through a long detour where `ilowpass`/`lowpass`/`limit1` "failed to load".
  The real cause was stale LinuxCNC processes and a `motmod` symbol error. Final version:
  `jog-scale → limit1 → mult2(×0.001)`, `jog-counts → ilowpass (gain 0.01, scale 1000)`.
  The pendant `limit1.max` is 1.0 on X/Y and 0.5 on Z/A.
- Speeds and feeds: XY 500 mm/s (30 m/min), Z 10 m/min, accel 0.3 g (2942 mm/s²).
- **Vibration and near tip-over on enable**: DC mode was R2M. Switched to **M2R**
  (`refClockSyncCycles="-1"`). linuxcnc-ethercat upgraded to v1.41.0 from source
  (v1.41 also rejects `syncToRefClock` combined with `refClockSyncCycles`).
- Spindle direction was backwards, so M3/M4 were swapped in `custom.hal`.
- First GitHub publish of `jayem1427/lemontart_lcnc_config` with portable paths,
  plus `launch.sh` and `Launch_Mill.desktop`.
- Limits and homing went through several rounds of "disable all switches so I can keep
  testing" (`and2.0` constant-false gag net, `NO_FORCE_HOMING`, home-in-place).
  This "breakout off" mode has been reused many times since.

### June 2026: I/O, probe, homing, tool change
- **The DI saga.** Tried A6 `0x2004` DI-function clears, `0x60FD` vs `0x2040:05`,
  and active-low inverters. Root cause: **one drive's CN1 cable was unplugged**.
  Final: DI functions cleared, raw DI via PDO, CN1 pin map documented.
- Touch probe wired into `motion.probe-input`. You can't also net
  `qtpyvcp.probe-in.out/.io` onto the same signal (two writers).
- **Homing semantics learned:** same-sign latch (search −, latch −) gives
  search → back off → slow re-approach. With an opposite-sign latch it never re-approaches.
  With home at the negative end, a negative `HOME_OFFSET` puts zero off the switch.
  "Homes the wrong way" turned out to be **home-input polarity**, not velocity sign.
  There were several "it's all broken, roll back to the June 8 commit" moments.
- Tool change switched to Z-retract only (no XY move). A Python M3/M4/M5 delay remap broke
  interpreter init and was deleted. It was replaced by a HAL `timedelay` gate on
  `spindle.0.at-speed` (5 s after `near.0`). G0 rapids still don't wait for at-speed, which is LinuxCNC behavior.
- Probe Basic persistence: `PREFERENCE_FILE`, probe params `#3004–3039` in
  `linuxcnc.var`, tip diameter in the tool table, calibration offset in `#3032`.
- G-code moved to `/home/jon/linuxcnc/nc_files` and synced with Syncthing (the OneDrive OAuth attempt was abandoned).
- Small-bore probing (5 mm hole, 2 mm tip) fix: slow pass off (`#3015=0`), XY clearance 0.8.
- `NO_FORCE_HOMING=1` on main. FERROR tightened to 0.2/0.1 and later relaxed (see July).
- Tool table: every tool set to `Q0`. A nonzero Q made LinuxCNC treat it as a lathe tool (G41 error).
- **Metrology:** `probe_z_three_samples.ngc` and `probe_z_repeat_stats.ngc`. Measured
  **Z probe repeatability ≈ 0.4 µm and homing repeatability ≈ 1.5 µm**, so index homing was shelved.
- Software E-stop on Slave 3 DI1 (NC). VFD fault monitoring: H100 reg `0x000A` = 64/92 → E-stop.
- Branches were archived as `archive/*` tags on Jun 27.

### July 2026: toolsetter, tuning tabs, logging
- **Contact toolsetter**: TooTall18T `tool_touch_off.ngc` + `REMAP=M600`
  (M6 not remapped), `TOOL_CHANGE_AT_G30=0`, `[ATC] POCKETS=1`, `TOOLSETTER.md` (now `TOOL_CHANGE.md`).
  Bugs fixed: an inline `;` on the REMAP line, nested comments, `M61` not setting
  `_selected_tool`, negative tool length (ABS bug), a feed hold that never cleared (`M50`).
  Merged via PR #9.
- **Probe routing by tool:** T99 → touch probe, otherwise → toolsetter, keyed on
  `halui.tool.number` (`tool-prep-number` was wrong after M61). The float `mux2` was replaced with bit logic.
- NPN vs PNP: wiring GND+SIG vs 24V+SIG decides polarity. An unplugged NC probe
  floats HIGH and locks `probe-input`, so the touch probe became **NO + `not`**. Jon rejected a
  manual "arm" pin and a separate-signal design.
- M600 upgrades: separate tool-load park at **G53 X270 Y100**, 30 m/min XY traverse,
  custom OK dialog with Resume and ABORT, no motion in `on_abort.ngc`.
- **Following-error philosophy settled:** LinuxCNC FERROR wide (1270/254), with the drive's
  `6065/6066` window doing the real protection (0.3 mm → later **0.5 mm**, 250 ms).
  The "ghost-lag" HAL rewiring of LinuxCNC's ferror was abandoned.
- **Servo Tuning tab** (A6 SDO read/write, live 60F4 FERR plot, presets),
  **one-click auto-tune** (`a6_auto_tune.py`), then the verify-discards-best bug, fixed in `e201e5d`.
  Best X preset: speed gain 150 Hz, position gain 224.6 rad/s, integral 5 ms. Jon is very
  happy with the Y preset. **Incident:** C00/C01 gains in `ethercat-conf.xml` were
  re-written on every startup and wiped his tuning, so they were removed.
- **Signal Logging tab**: was laggy and plotted flat lines. Causes: work on the Qt
  thread, `halcmd` per sample, and `hal.get_value` returning NaN across threads and on
  `tune-*` float pins. Now reads raw drive PDOs (DRIVE 60F4 mm, TORQUE 6077 %,
  VEL 606C → mm/min, POS).
- Found the **LinuxCNC 2.9.8 half-acceleration rule** (#4220). Workaround is `G61`.
- Docs moved into `docs/`. The SET Z field replaced ZERO ALL in the DRO.
- Laser setter (Kexin DS-5V-M) UI and wiring: 5 V push-pull output, Select pin tied to GND,
  `lcec.0.2.di-5`, G38 routing via `M62/M63 P0`, beam-width calibration
  (`#5516 = master − raw`).
- Graphical inertia ID (Yaskawa Sigma II style). Drive-internal ID isn't reachable
  over EtherCAT. Results are noisy because the A6 PDOs stair-step (606C held 17–36 ms).
- Branch `dev` created (Jul 20). `main` fast-forwarded to it.

### August 2026: laser accuracy, M600 polish
- Fluted endmills chop the beam. Tried: symmetric debounce, retriggerable hold,
  then the `laser-flute-hold` off-delay (`[LASER] BEAM_OFF_DELAY`, 10 ms at 6k RPM,
  50 ms at 1k RPM). Then max-of-9 first-tooth G38 hits, then **static-X first-peak hunt**
  (park, `M66` wait 0.2 s, 0.020/0.001 mm steps).
- **Results:** 6 mm pin mean 6.0008 mm, σ ≈ 7 µm. A 6.35 mm 3-flute reads
  ~6.08–6.11 (~0.25 mm small) because of the optical silhouette, not calibration or feed.
- **Incidents:** a mirrored `G0` start crashed into the setter wall, and an open-loop G1 seek
  went past the beam (E-stop). Rule: transit is G38-only, reusing the last known-good logic.
- Hit-dot UI (9+9) plus a `logs/laser_hits/` CSV. `laser_diameter_stats.ngc` (params ≤ 5599).
- M600 same-tool skip (`#<_current_tool>` vs `#2002`). G94 at macro start because the Fusion
  post emitted G93 at the top of programs.
- Stop/Abort used to drop G43 (startup code + `on_abort`). Now `G49` was removed from startup
  and `on_abort` calls `restore_tool_length`.
- Every other branch merged and deleted on Aug 14 (only `main` + `dev` were left).
  `launch.sh`/`Launch_Mill.desktop` were accidentally deleted by that merge and restored.
- Spindle warmup is 10 min per step at 6k/12k/18k/24k RPM (`nc_files`, gitignored in the repo).

### October–November 2026: new location, tpnext, rewire, MQL
- The machine moved. QC used breakout mode (all switches gagged, home-in-place).
- Built **tpnext-ma** (jerk-limited planner) as a run-in-place install next to stock 2.9.8. Branch
  `dev-jerk-testing`. A/B testing: low jerk caps the reachable acceleration (J=12.5k ≈ 0.25 g peak).
  1 g trapezoidal was "terrifying". Settled on **0.7 g, jerk 30 000 mm/s³, equal on all axes**.
- **Switch rewire QC** with a live 20-pin DI watcher, `switch_watch.py` GUI and
  `switch_announce.py` voice (espeak; neural Piper/Kokoro voices were tried and were too laggy).
  Found: shorted home bus (X/Y/Z homes common), probe and toolsetter swapped,
  dead Y-limit input. The map was rewritten in HAL. Y/Z share one home input
  with serialized homing and an 8 ms debounce (80 ms rolled past the flag).
- Pendant MPG had stopped working after a partial home (joint mode). Now wired to joint and axis jog pins.
- **Microject MQL** on the shared RS-485 dongle, with M201/M202/M8/M9. The spindle Modbus is
  unloaded because of the baud-rate conflict. MQL Probe Basic tab started.

---

## Postmortems / root causes worth remembering

| Symptom | Real cause |
|---|---|
| Whole machine vibrates on enable | DC R2M mode → use M2R |
| No DI responds after SDO changes | Drive CN1 cable unplugged |
| HAL modules "fail to load" (lowpass etc.) | Stale LinuxCNC processes / bad RT state |
| Axis homes the "wrong direction" | Home input polarity (inverter on a NO sensor) |
| Y runaway on REF ALL | `HOME_ABSOLUTE_ENCODER = 1` |
| Lost drive tuning every restart | Gain SDOs in `ethercat-conf.xml` |
| Probe stuck on | Unplugged NC probe floats HIGH and goes through an OR gate |
| Toolsetter only works after pressing Z home | Wire on a different DI than HAL expected |
| Can't jog Z unhomed | Restored position (`position.txt`) outside soft limits |
| 100 mm move tops at 23 m/min | 2.9.8 trajectory planner half-accel under G64 |
| M600 runs but never prompts | Stock M6 does nothing when the same tool is already loaded |
| G54 Z "lost" after Stop | Stop/abort issues `G49` |
| Must re-home to jog after a job | AUTO mode + stuck jog-active (not fixed) |
| Probe Basic crashes after branch switch | Leftover `user_tabs/<tab>/` folder |
| Plot flat / NaN | `hal.get_value` thread affinity and float pins |
| Endmill reads small on laser | Optical silhouette of flutes; fine on pins |

## Abandoned or parked approaches (don't re-propose without new info)

- Python M3/M4/M5 remap for a spindle delay (broke interp init).
- "Ghost-lag" rewiring of LinuxCNC's ferror (`servo_tuning.hal`).
- Drive-internal inertia ID (objects not on EtherCAT for this firmware).
- Classic index homing on lcec/cia402 (no index-enable handshake). Unneeded at 1.5 µm repeatability.
- Manual HAL "arm" gate for an unplugged probe, and separate toolsetter signals.
- OneDrive sync, neural TTS for the switch announcer, pendant Macro-10 feed-override toggle.
- Pulse stretcher on the laser G38 path, and raising RPM to fix flute undersize (20k reads smaller).
- CSV saving inside the Servo Tuning tab (plot only, by request).

## Ideas Jon raised (not started)

- Datron Neo-style camera-assisted WCS / orientation correction in Probe Basic.
- Making the repo a reference for others (GETTING_STARTED, maybe a video series).
- A Codesys/PLC CNC port (feasibility talk only).
- A fixture-load / job-done park position.

---

## Chat index

Local transcripts are under `.cursor-history/transcripts/` and cloud agents under
`.cursor-history/cloud-agents/` (local only).

| Date | Chat | Turns | Topic |
|---|---|---|---|
| 2026-05-03 | [`be6f25cc`](../.cursor-history/transcripts/2026-05-03_be6f25cc.md) | 6 | LCNC configuration summary and features |
| 2026-05-09 | [`65b4db94`](../.cursor-history/transcripts/2026-05-09_65b4db94.md) | 20 | XHC-HB04 pendant configuration and smoothing |
| 2026-05-11 | [`00967223`](../.cursor-history/transcripts/2026-05-11_00967223.md) | 38 | Y-axis limit switch logic |
| 2026-05-11 | [`47441854`](../.cursor-history/transcripts/2026-05-11_47441854.md) | 2 | GitHub repository update and configuration |
| 2026-05-15 | [`293cc94a`](../.cursor-history/transcripts/2026-05-15_293cc94a.md) | 1 | Z axis movement issue |
| 2026-05-17 | [`adae3e9b`](../.cursor-history/transcripts/2026-05-17_adae3e9b.md) | 12 | LinuxCNC EtherCAT latest release update |
| 2026-06-09 | [`cc95d4b2`](../.cursor-history/transcripts/2026-06-09_cc95d4b2.md) | 6 | Touch probe parameter persistence |
| 2026-06-09 | [`cf340a4e`](../.cursor-history/transcripts/2026-06-09_cf340a4e.md) | 47 | EtherCAT configuration for servo drives |
| 2026-06-14 | [`ba7bf0a8`](../.cursor-history/transcripts/2026-06-14_ba7bf0a8.md) | 25 | Tool change behavior modification |
| 2026-06-15 | [`c264ce33`](../.cursor-history/transcripts/2026-06-15_c264ce33.md) | 39 | Homing configuration for x, y, and z axes |
| 2026-06-16 | [`db40ec61`](../.cursor-history/transcripts/2026-06-16_db40ec61.md) | 5 | Configuration changes and wiring table |
| 2026-06-18 | [`a2e57195`](../.cursor-history/transcripts/2026-06-18_a2e57195.md) | 1 | Git backup and cleanup |
| 2026-06-20 | [`9959dcda`](../.cursor-history/transcripts/2026-06-20_9959dcda.md) | 21 | Spindle speed delay configuration |
| 2026-06-20 | [`a103cbc8`](../.cursor-history/transcripts/2026-06-20_a103cbc8.md) | 10 | LinuxCNC OneDrive configuration |
| 2026-06-20 | [`b91efa68`](../.cursor-history/transcripts/2026-06-20_b91efa68.md) | 4 | Z axis unlocking issue |
| 2026-06-21 | [`593a60f0`](../.cursor-history/transcripts/2026-06-21_593a60f0.md) | 23 | Touch probe configuration update |
| 2026-06-27 | [`01062d5e`](../.cursor-history/transcripts/2026-06-27_01062d5e.md) | 10 | Touch probe input availability |
| 2026-06-27 | [`22216edf`](../.cursor-history/transcripts/2026-06-27_22216edf.md) | 7 | Syncthing status |
| 2026-06-27 | [`f1ceeb46`](../.cursor-history/transcripts/2026-06-27_f1ceeb46.md) | 38 | Probe Basic version inquiry |
| 2026-06-28 | [`bfb22f35`](../.cursor-history/transcripts/2026-06-28_bfb22f35.md) | 65 | Laser tool setter UI integration |
| 2026-07-01 | [`9f330d69`](../.cursor-history/transcripts/2026-07-01_9f330d69.md) | 27 | Current git branch inquiry |
| 2026-07-01 | [`dda81116`](../.cursor-history/transcripts/2026-07-01_dda81116.md) | 14 | Toolsetter subroutine review |
| 2026-07-05 | [`f4ef80ce`](../.cursor-history/transcripts/2026-07-05_f4ef80ce.md) | 9 | Git status and update |
| 2026-07-07 | [`e5b1614b`](../.cursor-history/transcripts/2026-07-07_e5b1614b.md) | 2 | Tool setter GitHub status |
| 2026-07-08 | [`67f95b4b`](../.cursor-history/transcripts/2026-07-08_67f95b4b.md) | 13 | MDIButton runtime error |
| 2026-07-08 | [`7c2c4081`](../.cursor-history/transcripts/2026-07-08_7c2c4081.md) | 5 | Latest changes from main |
| 2026-07-08 | [`ea3b33ac`](../.cursor-history/transcripts/2026-07-08_ea3b33ac.md) | 25 | Main menu navigation |
| 2026-07-09 | [`b3c1d094`](../.cursor-history/transcripts/2026-07-09_b3c1d094.md) | 47 | Branch status inquiry |
| 2026-07-11 | [`c12b666e`](../.cursor-history/transcripts/2026-07-11_c12b666e.md) | 1 | Cursor client update |
| 2026-07-12 | [`5abd3a9d`](../.cursor-history/transcripts/2026-07-12_5abd3a9d.md) | 38 | Branch changes and switch |
| 2026-07-13 | [`2c705db4`](../.cursor-history/transcripts/2026-07-13_2c705db4.md) | 50 | Git status and branch pull |
| 2026-07-13 | [`3dccc604`](../.cursor-history/transcripts/2026-07-13_3dccc604.md) | 3 | Branch and commit status |
| 2026-07-13 | [`67f6f310`](../.cursor-history/transcripts/2026-07-13_67f6f310.md) | 2 | Git status and branch pull |
| 2026-07-13 | [`8c220ee8`](../.cursor-history/transcripts/2026-07-13_8c220ee8.md) | 1 | Git status and branch pull |
| 2026-07-15 | [`612a2ec6`](../.cursor-history/transcripts/2026-07-15_612a2ec6.md) | 33 | Branch switch and backup |
| 2026-07-15 | [`c0b6b6ee`](../.cursor-history/transcripts/2026-07-15_c0b6b6ee.md) | 6 | Cursor update |
| 2026-07-16 | [`694faa55`](../.cursor-history/transcripts/2026-07-16_694faa55.md) | 14 | Jogging without homing |
| 2026-07-16 | [`d2ce1d2e`](../.cursor-history/transcripts/2026-07-16_d2ce1d2e.md) | 28 | Inertia auto tune status |
| 2026-07-16 | [`e4063a6a`](../.cursor-history/transcripts/2026-07-16_e4063a6a.md) | 1 | Laser diameter error |
| 2026-07-20 | [`a8445e90`](../.cursor-history/transcripts/2026-07-20_a8445e90.md) | 3 | Homing functionality issue |
| 2026-07-20 | [`b4dcf259`](../.cursor-history/transcripts/2026-07-20_b4dcf259.md) | 17 | Laser tool setter commands |
| 2026-07-25 | [`c164d6fa`](../.cursor-history/transcripts/2026-07-25_c164d6fa.md) | 14 | Probe sounds dev branch |
| 2026-07-31 | [`40703a47`](../.cursor-history/transcripts/2026-07-31_40703a47.md) | 33 | <timestamp>Thursday, Jul 30, 2026, 9:35 PM (UTC-7)</timestamp>  https: |
| 2026-08-06 | [`61a3a955`](../.cursor-history/transcripts/2026-08-06_61a3a955.md) | 11 | <timestamp>Wednesday, Aug 5, 2026, 9:23 PM (UTC-7)</timestamp>  in the |
| 2026-08-07 | [`a72cfef8`](../.cursor-history/transcripts/2026-08-07_a72cfef8.md) | 8 | <timestamp>Thursday, Aug 6, 2026, 11:22 PM (UTC-7)</timestamp>  change |
| 2026-08-14 | [`d0deabc6`](../.cursor-history/transcripts/2026-08-14_d0deabc6.md) | 37 | <timestamp>Tuesday, Aug 11, 2026, 7:13 PM (UTC-7)</timestamp>  lets ma |
| 2026-08-18 | [`f0084bed`](../.cursor-history/transcripts/2026-08-18_f0084bed.md) | 1 | <timestamp>Monday, Aug 17, 2026, 10:34 PM (UTC-7)</timestamp>  whats w |
| 2026-08-20 | [`19844be6`](../.cursor-history/transcripts/2026-08-20_19844be6.md) | 15 | <timestamp>Wednesday, Aug 19, 2026, 10:58 PM (UTC-7)</timestamp>  huh. |
| 2026-08-20 | [`a07e1488`](../.cursor-history/transcripts/2026-08-20_a07e1488.md) | 9 | <timestamp>Friday, Aug 14, 2026, 12:50 PM (UTC-7)</timestamp>  hmm som |
| 2026-08-25 | [`4b2c57ad`](../.cursor-history/transcripts/2026-08-25_4b2c57ad.md) | 1 | <timestamp>Monday, Aug 24, 2026, 6:51 PM (UTC-7)</timestamp>  do you s |
| 2026-08-25 | [`bcc3e19e`](../.cursor-history/transcripts/2026-08-25_bcc3e19e.md) | 11 | <timestamp>Friday, Aug 21, 2026, 8:38 PM (UTC-7)</timestamp>  can you  |
| 2026-08-25 | [`bef6d321`](../.cursor-history/transcripts/2026-08-25_bef6d321.md) | 2 | <timestamp>Monday, Aug 24, 2026, 7:16 PM (UTC-7)</timestamp>  im gonna |
| 2026-08-26 | [`0b9d3715`](../.cursor-history/transcripts/2026-08-26_0b9d3715.md) | 1 | <timestamp>Tuesday, Aug 25, 2026, 8:47 PM (UTC-7)</timestamp>  what ne |
| 2026-08-26 | [`5279843d`](../.cursor-history/transcripts/2026-08-26_5279843d.md) | 3 | <timestamp>Tuesday, Aug 25, 2026, 8:46 PM (UTC-7)</timestamp>  did we  |
| 2026-08-30 | [`8d49462f`](../.cursor-history/transcripts/2026-08-30_8d49462f.md) | 3 | <timestamp>Saturday, Aug 29, 2026, 3:28 PM (UTC-7)</timestamp>  can yo |
| 2026-08-31 | [`36650bd6`](../.cursor-history/transcripts/2026-08-31_36650bd6.md) | 2 | <timestamp>Sunday, Aug 30, 2026, 3:51 PM (UTC-7)</timestamp>  is there |
| 2026-08-31 | [`66d224b3`](../.cursor-history/transcripts/2026-08-31_66d224b3.md) | 1 | <timestamp>Sunday, Aug 30, 2026, 3:51 PM (UTC-7)</timestamp>  can you  |
| 2026-10-12 | [`14464ef1`](../.cursor-history/transcripts/2026-10-12_14464ef1.md) | 5 | <timestamp>Sunday, Oct 11, 2026, 7:29 PM (UTC-7)</timestamp>  what bra |
| 2026-11-04 | [`c75925f3`](../.cursor-history/transcripts/2026-11-04_c75925f3.md) | 141 | <timestamp>Monday, Oct 12, 2026, 10:37 PM (UTC-7)</timestamp>  how do  |
| 2026-11-04 | [`d91c7c10`](../.cursor-history/transcripts/2026-11-04_d91c7c10.md) | 2 | <timestamp>Wednesday, Nov 4, 2026, 12:29 AM (UTC-8)</timestamp>  can y |
| 2026-05-18 | [`bc-e41f1f5`](../.cursor-history/cloud-agents/2026-05-18_bc-e41f1f5.md) | cloud |  config usability |
| 2026-05-23 | [`bc-b7f6f7f`](../.cursor-history/cloud-agents/2026-05-23_bc-b7f6f7f.md) | cloud | oo backup LinuxCNC purpose |
| 2026-06-25 | [`bc-2d11307`](../.cursor-history/cloud-agents/2026-06-25_bc-2d11307.md) | cloud | ed servo homing |
| 2026-06-26 | [`bc-bbe0591`](../.cursor-history/cloud-agents/2026-06-26_bc-bbe0591.md) | cloud | e basic machine visualization |
| 2026-06-27 | [`bc-54982c3`](../.cursor-history/cloud-agents/2026-06-27_bc-54982c3.md) | cloud | e basic simulation |
| 2026-06-27 | [`bc-d8fd7a7`](../.cursor-history/cloud-agents/2026-06-27_bc-d8fd7a7.md) | cloud | e Basic version identification |
| 2026-07-12 | [`bc-7e8354f`](../.cursor-history/cloud-agents/2026-07-12_bc-7e8354f.md) | cloud |  IDE access issue |
| 2026-07-12 | [`bc-e89155a`](../.cursor-history/cloud-agents/2026-07-12_bc-e89155a.md) | cloud | ant setting behavior |
| 2026-07-12 | [`bc-ebc74fc`](../.cursor-history/cloud-agents/2026-07-12_bc-ebc74fc.md) | cloud | is ferror reduction |
| 2026-07-13 | [`bc-7e1ddbc`](../.cursor-history/cloud-agents/2026-07-13_bc-7e1ddbc.md) | cloud | mentation folder structure |
| 2026-07-14 | [`bc-9e771c0`](../.cursor-history/cloud-agents/2026-07-14_bc-9e771c0.md) | cloud | 02 auto-tune portability |
| 2026-07-20 | [`bc-df0ded4`](../.cursor-history/cloud-agents/2026-07-20_bc-df0ded4.md) | cloud | ng table di pins db15 |
| 2026-07-22 | [`bc-a1df9ad`](../.cursor-history/cloud-agents/2026-07-22_bc-a1df9ad.md) | cloud | sys CNC migration feasibility |
| 2026-07-22 | [`bc-fccec85`](../.cursor-history/cloud-agents/2026-07-22_bc-fccec85.md) | cloud |  visual styling |
