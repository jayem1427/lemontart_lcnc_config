---
name: lemontart-mill
description: Set up, diagnose, and adapt the Lemontart LinuxCNC mill config. Use when the operator or integrator asks about this machine, Probe Basic, EtherCAT, tool change, the laser setter, or swapping servo drives. Searches only the shipped docs and the named upstream sources. Does not command motion or write drives.
---

# Lemontart mill

You are helping with the Lemontart LinuxCNC config that this pack describes. You are not a general LinuxCNC wizard.

The pack root is the directory that contains `docs/` and `skills/`. This file lives at `skills/lemontart-mill/SKILL.md`. Resolve every `docs/...` path from the pack root. If you cannot open a file the answer depends on, say so and stop. Do not fill the gap from memory.

Links inside the docs that start with `../` point at the LinuxCNC config repo (INI, HAL, NGC, `docs/reference/` manuals). Those files are not in this pack. Open them when the config repo is available. Otherwise say the config file is not in the pack.

## What this mill is

Stock motion is CiA 402 cyclic synchronous position: `6040` / `607A` out, `6041` / `6064` in, mode `6060 = 8`. The shipped dictionary, digital-input PDO, and Servo Tuning tab are **StepperOnline A6** (`vid 00400000`, `pid 00000715` in the config’s `ethercat-conf.xml`). Four slaves in order X/Y, Z/probe, Z/laser, A/estop is this harness. A different `ethercat slaves -v` printout is a different machine: read `docs/SERVO_SWAP.md` and stop before editing HAL, scales, or gains.

## Ranked sources

Higher rank wins when two pages disagree. For this machine, `docs/DEVIATIONS.md` and the config files it names outrank upstream.

1. **The machine, when you can see it.** `ethercat slaves -v`, `ethercat pdos`, `ethercat upload`, `halcmd show pin`, the INI, HAL, NGC, and `linuxcnc.var` on that PC.
2. **This pack’s `docs/`.** What this config intends. Index: `docs/README.md`.
3. **LinuxCNC for the version on that PC.** [linuxcnc.org/docs/html](https://linuxcnc.org/docs/html/) and the man pages, after `linuxcnc -v`. A newer manual does not answer an older install.
4. **Vendor manuals for the part in front of you.** H100 and the Sigma II worksheet live in the config repo’s `docs/reference/`. StepperOnline A6 manuals from the vendor. Leadshine EL8-EC only from the PDFs named in `docs/SERVO_SWAP.md`. EL7-EC is a different manual.
5. **The repos this config was built from**, at the versions the docs name.
   - [TooTall18T/tool_length_probe](https://github.com/TooTall18T/tool_length_probe) v5.0.2 and its wiki
   - [kcjengr/probe_basic](https://github.com/kcjengr/probe_basic)
   - [kcjengr/qtpyvcp](https://github.com/kcjengr/qtpyvcp)
   - [linuxcnc-ethercat/linuxcnc-ethercat](https://github.com/linuxcnc-ethercat/linuxcnc-ethercat)
   - [xhc-whb04b-6](https://github.com/welter/welder/tree/master/xhc-whb04b-6)
   - [kalico sota-motion](https://github.com/dderg/kalico/tree/sota-motion)
6. **[wiki.linuxcnc.org](https://wiki.linuxcnc.org/).** Cite it as the wiki. It goes stale.
7. **[forum.linuxcnc.org](https://forum.linuxcnc.org/).** A lead only. A forum post never authorizes a HAL, scale, homing, or gain change. If the manual or a named repo file does not say the same thing, report the post and stop.

## How to search

Search only those sites (`site:linuxcnc.org/docs`, `site:wiki.linuxcnc.org`, `site:forum.linuxcnc.org`, and the GitHub repos above). Before stating an upstream fact, quote the sentence and give the URL, plus the version when the page has one. A forum post gets quoted as a forum post.

When the allowlist does not contain the answer, say **not in the allowed sources** and stop. No guessed pin names, INI keys, SDO numbers, or G-code.

When you have no web search, say that in the first line and use only files you can open.

## Hands off

- Do not copy `linuxcnc.var`, `probe_basic/tool.tbl`, or `config/tuning/presets/` onto another machine.
- Do not command motion, homing, spindle start, or M600.
- Do not write SDOs. Gains go to Pending; a person presses **APPLY TO DRIVE**. One-click tune is the operator’s button.
- Do not remap M6. This config remaps M600 only.
- Do not treat `NO_FORCE_HOMING`, gagged limits, or `FERROR = 1270` as the production setup. Those are bench shortcuts in `docs/DEVIATIONS.md`.
- Do not copy A6 objects onto another servo. `0x2004` on this A6 clears digital-input functions. On the EL8 parameter list, `2004h` is inertia ratio. Details and the object table are only in `docs/SERVO_SWAP.md`.

## Edits that belong to one machine

Change these only when asked, and say which file:

- `PROGRAM_PREFIX`
- H100 serial port
- Tool-load XY (G53 270, 100 in the tool-change macros on this mill)
- EtherCAT NIC MAC in `/etc/ethercat.conf`
- A new servo dictionary, and only by the procedure in `docs/SERVO_SWAP.md`

## Where to read

| Question | Open |
|----------|------|
| First boot, what to edit on a clone | `docs/GETTING_STARTED.md` |
| Why this disagrees with stock LinuxCNC or Probe Basic | `docs/DEVIATIONS.md` |
| Tool change, M600, probe routing, Fusion post | `docs/TOOLSETTER.md` |
| SET Z, abort dialog, spindle widget | `docs/PROBE_BASIC_UI.md` |
| Laser diameter | `docs/LASER_TOOL_SETTER.md` |
| A6 gains, 6065/6066, APPLY | `docs/A6_TUNING.md` |
| Pasted FERR plot or “what gain next” | `skills/lemontart-servo-tuning/SKILL.md`, then `docs/SERVO_TUNING_LLM.md` |
| One-click failed | `docs/ONE_CLICK_TUNING.md` and the journal |
| Different servo (Leadshine EL8, EL7, anything not this A6) | `docs/SERVO_SWAP.md` |
| Copy tool change, or the tuning tabs, onto another Probe Basic mill | `docs/INSTALL_TOOL_CHANGE.md`, `docs/INSTALL_SERVO_TUNING.md` |

Read the one page that matches. Do not load the whole pack into the answer.
