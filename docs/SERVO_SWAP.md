# Servo family swap

This mill’s motion path is CiA 402. The EtherCAT identity, digital-input PDO, and Servo Tuning dictionary are **StepperOnline A6**. Another drive, including a Leadshine EL8-EC, keeps the motion HAL and replaces the dictionary. It does not get a copy of `a6_servo_tune.py`’s object map or of `config/tuning/presets/`.

A6 facts below are this repo (`ethercat-conf.xml`, `probe_basic/python/a6_servo_tune.py`, [DEVIATIONS.md](DEVIATIONS.md)). EL8 facts are the Leadshine EtherCAT parameter list, [Parameter List – EtherCAT](https://en.leadshine.com/upfiles/downloads/ac80808f7b709e704a26ec2547d3fe2f_1673935632110.pdf). The matching narrative manual is [EL8-EC Series AC Servo Drive User Manual V1.01](https://atbautomation.eu/uploads/EL8-EC_User_Manual_V1.01.pdf). Where that list does not give a number, read it from the drive. Do not invent one.

## Three layers

| Layer | A6 today | On a different servo |
|-------|----------|----------------------|
| **Motion** | `cia402`, CSP (`6060h = 8`), `6040` / `607A` out, `6041` / `6064` in | Keep, after `ethercat pdos` shows those objects |
| **Telemetry** | PDO `606C`, `6077`, `60F4`, scaled in `custom.hal` | Keep the pins only if that drive maps the same objects into the same units |
| **This drive** | VID/PID, `0x2040:05` DI bits, `0x2004` DI setup, C00/C01 SDOs, one-click ladder | Replace from that drive’s manual. Leave loop gains out of XML |

Joint `SCALE` is the screw (or rotary) times the encoder counts the drive reports as command units. `13107.2` counts/mm and `364.09` counts/deg are this mill’s A6 scales. A new encoder or an electronic gear changes `SCALE`, and it changes the `6065` count value that means 0.5 mm.

## Files that are A6

| File | What is A6-specific |
|------|---------------------|
| `ethercat-conf.xml` | `vid="00400000"` `pid="00000715"`. Startup `6065`/`6066`. `0x2004` subindexes that zero DI functions. TxPDO `0x2040:05` packed as `di-1`…`di-5`. |
| `probe_basic/python/a6_servo_tune.py` | C00/C01 index, subindex, scale, and unit for every Servo Tuning row. One-click’s `6065` widen/restore. |
| `probe_basic/python/a6_auto_tune.py` | Gain ladder written to those C01 objects. Notch “off” = 8000 Hz. |
| `probe_basic/python/a6_graphical_inertia.py` | Writes A6 **C00.06**. |
| `custom.hal` | `6077` scaled as 0.1% per count. `60F4` divided by joint `SCALE`. |
| `config/tuning/presets/` | Numbers from this A6. Do not load them into another family. |
| [SERVO_TUNING_LLM.md](SERVO_TUNING_LLM.md) | Playbook ratio: position (rad/s) ≈ 2× speed (Hz). That is an A6 rule of thumb. |

`ethercat_mill.hal` joint wiring, the probe mux, the VFD, and the tool-change macros are not the servo family. They still name `lcec.0.N.di-*`. Those pin names only survive if the new TxPDO uses the same `halPin` names.

## Identify the slave before editing

On the machine, with the drives powered:

```bash
ethercat slaves -v
ethercat pdos -p 0
ethercat upload -p 0 -t int32 0x60F4 0
ethercat upload -p 0 -t int16 0x6077 0
```

Record vendor id, product id, and whether `606C`, `6077`, `60F4`, and a digital-input object are actually in the PDO. The XML `vid`/`pid` come from that printout. A manual’s marketing name is not a vendor id.

If `60F4` is absent, the Logging **DRIVE** trace and one-click have nothing to measure. Stop there. Do not retarget the plot at LinuxCNC `joint.N.f-error`.

## Leadshine EL8-EC

Objects below are from the Leadshine parameter list linked above. Panel `Pr0.04` is index `2004h` with no subindex in that list. A6 C-parameters use index plus subindex (`0x2001:01` for C01.00).

| Role | A6 in this repo | EL8-EC in the parameter list |
|------|-----------------|------------------------------|
| Mode CSP | `6060h = 8` | `6060h`, default 8, CSP listed |
| Position / velocity / torque feedback | `6064` / `606C` / `6077` | Same indexes. `6077h` unit **0.1%**. `606Ch` unit command units/s |
| Following error | `60F4` counts, ÷ `SCALE` | `60F4h` actual following error, command units |
| Deviation window | `6065` / `6066`, startup 0.5 mm / 250 ms | `6065h` default **30000** command units. `6066h` unit ms, default **10** in the summary table |
| Inertia ratio | `0x2000:07` (C00.06, %) | **`2004h` / Pr0.04** |
| 1st position gain | `0x2001:01` (C01.00, 0.1 rad/s) | **`2100h` / Pr1.00**, 0.1/s, default 320 |
| 1st velocity gain | `0x2001:02` (C01.01, 0.1 Hz) | **`2101h` / Pr1.01**, 0.1 Hz, default 180 |
| 1st velocity integral | `0x2001:03` (C01.02, 0.01 ms) | **`2102h` / Pr1.02**, **0.1 ms**, default 310 |
| 1st torque filter | `0x2001:04` (C01.03, **Hz**) | **`2104h` / Pr1.04**, **0.01 ms** time constant, default 126 |
| 2nd position gain | `0x2001:09` (C01.08) | `2105h` / Pr1.05 |
| Notch 1 frequency | `0x2001:41` (C01.40, Hz; 8000 = off) | `2201h` / Pr2.01 |
| Adaptive notch | `0x2001:31` (C01.30) | `2200h` / Pr2.00 |
| Digital inputs in the PDO | `0x2040:05` bits → `di-1`…`di-5` | **`60FDh` input status** (see below) |
| DI function setup | `0x2004` subindexes written `0` at startup | `2400h`… DI selection (Pr4.00 is `2400h`) |

EL8’s own ratio, quoted from that list under Pr1.00: **1.2 ≤ Pr1.00/Pr1.01 ≤ 1.8**. The A6 playbook’s “position ≈ 2× speed” does not transfer. Torque-filter math does not transfer either: one-click treats C01.03 as a cutoff in Hz, and Pr1.04 is a time constant.

### Do not copy `0x2004`

On this A6, `ethercat-conf.xml` writes `0x2004` subindexes `01`, `05`, `09`, `0d`, and `11` to zero. [DEVIATIONS.md](DEVIATIONS.md) describes that as clearing DI functions. On the EL8 list, **`2004h` is the inertia ratio**. Leaving those `sdoConfig` lines in place points startup writes at a different object. Delete them when the slave is not an A6. Set EL8 inertia only from the Servo Tuning tab, after the row points at `2004h`, and only after `ethercat upload` shows the type and unit you expect.

### Digital inputs are a different bitfield

EL8 `60FDh` (parameter list, index 60FDh):

| Bit | Signal |
|-----|--------|
| 0 | NOT |
| 1 | POT |
| 2 | HOME |
| 3 | DI1 |
| 4 | DI2 |
| 5 | DI3 |
| 6 | DI4 |
| 7 | DI5 |

The A6 PDO packs vendor `0x2040:05` so the first complex bit is `di-1`. Wiring `lcec.0.0.di-1` straight across will land on EL8’s NOT bit, not DI1. Rebuild the `complexEntry` list to match `60FDh`, then check each `ethercat_mill.hal` net (X home, limits, toolsetter, laser, estop) against a meter before homing.

The A6 CN1 / DB15 pin table in the README is the A6 connector. EL8 I/O pins come from the EL8 hardware chapter, not that table.

### `6064` vs encoder counts

The EL8 list says `6064h * gear ratio = 6063h` (internal encoder position). `SCALE` and the `6065` count value have to be in **6064 command units**. A gear set in Pr0.08 / `608F`–`6092` moves the mill if `SCALE` is still the A6 number.

## Procedure

1. Run `ethercat slaves -v` and `ethercat pdos`. Write the printed VID/PID into `ethercat-conf.xml`. Remove every A6 `0x2004` `sdoConfig`.
2. Map TxPDO feedback only for objects the PDO listing contains. Keep `halPin` names (`pos-fb`, `vel-fb`, `torque-fb`, `ferr-fb`, `di-1`…) so `ethercat_mill.hal` and `custom.hal` still connect. Fix bit order for `60FD` before trusting a home or a probe.
3. Recompute `[JOINT_*] SCALE` from command counts per mm (or deg). Recompute startup `6065` as `0.5 mm × SCALE` (A axis: `0.5° × SCALE`). Confirm `6065` / `6066` accept a write with `ethercat upload` / `ethercat download` on one slave before putting them in XML. The EL8 list’s default window is 30000 command units, not this mill’s 0.5 mm.
4. Leave position, velocity, integral, torque-filter, notch, and inertia SDOs **out** of `ethercat-conf.xml`. Same rule as [A6_TUNING.md](A6_TUNING.md): startup SDO writes land on every bus claim and wipe a tune.
5. Add a new parameter catalog (a sibling of `PARAM_DEFS`, not an edit that reuses C01 indexes). Units come from the manual row: Pr1.04 stays a time constant. One-click, notch auto-write, and the inertia panel stay off until that catalog exists and a person has applied one change by hand.
6. Tune on the machine. Do not load `config/tuning/presets/`. Store to the drive’s EEPROM from the vendor panel after the tune is good. APPLY on the A6 path is RAM-only; confirm the EL8 save path in the EL8 manual (parameter saving chapter) before assuming the same.
7. Homing and the first probe happen after DI bits have been checked with `halcmd show pin`.

## EL7

EL7-EC is a different manual. Do not reuse the EL8 index table for an EL7 until that manual’s object column matches line for line. The agent reads the EL7-EC PDF from Leadshine, then fills the same three layers. A shared “Pr1.00” label is not an object index.

## What stays unfilled until the drive says so

Vendor id, product id, PDO index for inputs if `60FD` is not mapped, `6077` scale if `ethercat upload` disagrees with 0.1%, and every gain default. The parameter list is the claim. The drive’s upload is the check. A missing line in either one is “not in the sources,” not a guess.
