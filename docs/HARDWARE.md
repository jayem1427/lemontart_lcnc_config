# Hardware and wiring

What is physically on this mill and how it's wired to the PC. If you're
building something similar, this is the page to check your wiring against.
Where this page and a config file disagree, **the config file wins**:
`ethercat_mill.hal` is the source of truth for every input.

---

## Parts list

| Part | Model | Notes |
|------|-------|-------|
| Machine | Lemontart CNC mill | Manual collet spindle, no ATC |
| Servo drives | 4× StepperOnline **A6-EC** (EtherCAT, CiA 402) | Firmware `AS715N_sAxis_V0.10` |
| Servo motors | XYZ 400 W, A 100 W | 17-bit encoders (131 072 counts/rev) |
| Ball screws | 10 mm pitch | XYZ |
| Rotary | A axis, table along X | Not mechanically connected right now |
| Spindle VFD | H100 | 24 000 RPM max, Modbus RTU |
| Coolant | Dan Mills Microject + automotive injector (GM0521994) | MQL, Modbus RTU, 24 V board supply |
| Contact tool setter | Switch-type setter, wired like the probe (TRUE when tripped) | Tool length |
| Touch probe | NC (NPN) probe, used as tool **T99** | Work probing |
| Laser setter | Kexin **DS-5V-M** U-slot beam sensor | Tool diameter, **5 V** supply |
| Pendant | XHC WHB04B-6 wireless (USB `10ce:eb93`) | |
| USB-RS485 #1 | CH340-based (`1a86:7523`) | Spindle VFD |
| USB-RS485 #2 | FTDI FT232R (`0403:6001`, serial `BG02XIBV`) | Coolant |
| PC NIC for EtherCAT | Onboard Intel I219-LM on the IgH native `ec_e1000e` driver | Dedicated to the drives. Any NIC works on the `generic` driver; see [SETUP.md](SETUP.md#ethercat-driver-and-timing) |

---

## Motion

| Axis | Joint | EtherCAT slave | Scale | Travel (soft limits) | Max velocity |
|------|-------|----------------|-------|----------------------|--------------|
| X | 0 | 0 | 13 107.2 counts/mm | −254 … 370 mm | 500 mm/s (30 m/min) |
| Y | 1 | 1 | 13 107.2 counts/mm | −254 … 308 mm | 500 mm/s |
| Z | 2 | 2 | 13 107.2 counts/mm | −203.2 … 400 mm | 166.7 mm/s (10 m/min) |
| A | 3 | 3 | 364.0889 counts/° | unlimited | 360 °/s |

- **Scale**: 131 072 counts/rev ÷ 10 mm pitch = 13 107.2 counts/mm. One count
  is about 76 nm. The scaling is done in HAL (`mult2`/`div2`), not by the
  EtherCAT driver.
- **Acceleration**: 6865 mm/s² (0.7 g) on XYZ, with a jerk limit of
  30 000 mm/s³ on the tpnext build. Keep X and Y jerk equal or arcs won't feed
  evenly.
- **Z max limit is 400 mm** (above home) on purpose. The encoders are absolute,
  so an unhomed Z can report 300+ mm, and a lower limit would stop you jogging
  it before homing.

The drives run in **CSP** (cyclic synchronous position) mode with
distributed clocks in **M2R** mode (`refClockSyncCycles="-1"` in
`ethercat-conf.xml`). R2M made the whole machine shake violently on enable.

---

## A6-EC drive notes

What has held up on these four drives (vendor `0x00400000`, product
`0x00000715`, firmware `AS715N_sAxis_V0.10`) with IgH + linuxcnc-ethercat.
The config that goes with it is [`ethercat-conf.xml`](../ethercat-conf.xml).

| Topic | What works here |
|-------|-----------------|
| Distributed clocks | `assignActivate="300"`, SYNC0 = 1 × cycle, shift 300 µs, 1 ms cycle. The master leads (**M2R**, `refClockSyncCycles="-1"`). With the reference clock leading (R2M) the machine shook violently on enable |
| Mode | CSP, `0x6060 = 8` |
| Digital inputs | Read raw from PDO `0x2040:05` (bits 0–4 = DI1–DI5). The drive's own input functions are cleared with `0x2004:01/05/09/0D/11 = 0`, so homes and limits are LinuxCNC's business only. **On this branch (`dev-drive-homing`) slave 0 DI2 has drive function 5 (home switch)** so the X drive can home on it; LinuxCNC still reads the raw bit |
| Following error | The drive enforces `0x6065` (counts) and `0x6066` (ms): Er47.0, EtherCAT error code `0x8611`. Read the last error with `ethercat upload -p N -t uint16 0x603F 0` |
| SDO writes persist | C13.10 (`0x2013:11`) = 1 on all four: **every SDO write is stored in EEPROM**. A "temporary" write is permanent unless you write the old value back |
| Start-up SDOs | lcec writes them on every start, so loop gains (C00/C01) there overwrite your tuning each launch. Only mode, fault windows, input functions and the speed observer (`0x2001:11 = 3`) belong there |
| Feedback PDOs | `0x6064` position and `0x60F4` following error update every cycle. `0x606C` velocity and `0x6077` torque **stair-step** (held 17–36 ms at a 1 ms cycle): fine for display, not for per-cycle analysis |
| SDO types | The drive doesn't describe its object types, so `ethercat upload/download` needs `-t` |
| Bus health counters | C13.04 `0x2013:05` sync loss, C13.09 `0x2013:0A` invalid frames, C13.12 `0x2013:13` IRQ loss (all read only) |
| Not reachable | Drive-internal inertia identification (C07 / F30) isn't available over EtherCAT on this firmware |
| Homing | **This branch:** X and A are homed by the drive (home switch, then encoder index; A index only); Y and Z are still homed by LinuxCNC on switches. Not yet run on the machine: `docs/DRIVE_HOMING.md`. `HOME_ABSOLUTE_ENCODER = 1` caused a runaway; don't use it |

Tuning the gains over EtherCAT: [SERVO_TUNING.md](SERVO_TUNING.md). NIC driver
and timing: [SETUP.md](SETUP.md#ethercat-driver-and-timing).

---

## Drive inputs

Every A6-EC has the same 15-pin CN1 connector. It is the **high-density
3-row** kind (HD15 / DE-15, VGA size), not a 2-row DB15, although these docs
call it DB15 for short. Each drive's inputs show up in
HAL as `lcec.0.<slave>.di-1` … `di-5`, read straight from PDO `0x2040:05`.
The config clears the drive's own input functions at startup (`0x2004`
subindexes set to 0), so the drive never acts on these inputs by itself. They
are plain inputs for LinuxCNC.

### CN1 (DB15) pinout

| Input | DB15 pin | Drive's default label |
|-------|----------|-----------------------|
| DI1 | 10 | Positive limit |
| DI2 | 9 | Negative limit |
| DI3 | 8 | Home |
| DI4 | 7 | TouchProbe2 |
| DI5 | 11 | TouchProbe1 |
| COM | 13 | Input common |
| +24 V out | 15 | Internal 24 V supply |

Check whether each sensor is NPN or PNP and wire COM accordingly
(GND+signal vs 24 V+signal). And check the CN1 cable is actually plugged in:
an unplugged one was the root cause of a long "the drive ignores its inputs"
hunt on this mill.

### What's wired where on this mill

| Function | HAL pin | DB15 pin | Notes |
|----------|---------|----------|-------|
| X home | `lcec.0.0.di-2` | 9 | NC, inverted in HAL, 5 ms debounce |
| X limit (both ends, in series) | `lcec.0.0.di-5` | 11 | NC, ignored while X homes |
| Y limit (both ends) | `lcec.0.0.di-1` | 10 | Uses the input that used to be Z−. Y's own input was damaged |
| Y home **and** Z home | `lcec.0.1.di-4` | 7 | **One shared bus**, see below |
| Touch probe | `lcec.0.1.di-2` | 9 | Only listened to when T99 is loaded |
| Contact tool setter | `lcec.0.1.di-5` | 11 | Only listened to when any other tool is loaded |
| Laser beam broken | `lcec.0.2.di-5` | 11 | TRUE = beam blocked, level-shifted 5 V → 24 V |
| Software E-stop | `lcec.0.3.di-1` | 10 | NC. Opening it drops machine enable |
| Z− limit, Z+ limit, A home/limits | none | | Forced off in HAL (`and2.0`, net `a-lims-gagged`) |

**The shared Y/Z home bus.** The Y and Z home switches are shorted together
(along with a few spare inputs: `0.0.di-3/4`, `0.1.di-3`). It works because
homing is sequential: Z first, then X, then Y, so only one axis is ever
looking at the bus. HAL also ignores the bus if it is already closed when an
axis starts homing, until it has been seen open. That stops Y from "homing" in
place. Don't use `HOME_IS_SHARED = 1` to solve this: it aborts Z homing.

**Known compromises.** Z− has no limit switch input left, the A axis has no
switches, and there is some electrical noise on the home inputs. These are
deliberate software workarounds, not oversights. Fix the wiring if you're
building fresh.

---

## E-stop

Two layers:

1. **Master E-stop** cuts mains power to the drives and VFD.
2. **Software E-stop**: a normally-closed switch on slave 3 DI1. It's ANDed
   with the UI's enable (`and2.2`) into `iocontrol.0.emc-enable-in`, so opening
   it turns the machine off in LinuxCNC.

The drives also enforce their own following-error limit: 0.5 mm for 250 ms,
which trips drive fault Er47.0. (A is normally 0.5°, widened to 10° while its
motor is mechanically unconnected.) See
[CONFIG_TOUR.md](CONFIG_TOUR.md#following-error).

---

## RS-485 (spindle and coolant)

Two USB adapters, one per device, because the two devices use different serial
settings and can't share a bus:

```
PC
 ├─ CH340 USB-RS485  ── A/B ──  H100 VFD       38400 8N1, slave 1
 └─ FTDI  USB-RS485  ── A/B ──  Microject      19200 8E1, slave 8
```

- Refer to adapters by `/dev/serial/by-id/...`, never `/dev/ttyUSB0`. The
  `ttyUSB` numbers depend on plug-in order and can swap after a reboot.
- If a device never answers, swap A and B at one end first. Then check that
  the wires are on A/B and not on a GND terminal (that one has bitten me).
- Wire RS-485 as a daisy chain, not a star, with a 120 Ω terminator at the far
  end on long runs.

More in [MODBUS.md](MODBUS.md), [SPINDLE.md](SPINDLE.md) and [COOLANT.md](COOLANT.md).

---

## Laser setter (DS-5V-M)

| Wire | Connect to |
|------|------------|
| Power | **5 V only.** 24 V will kill it |
| Select | GND (0 V = on) |
| Signal | Through a 5 V → 24 V level shifter to slave 2 DI5 (DB15 pin 11) |

It mounts lengthwise along Y with the beam crossing the slot in X. Max tool
diameter is about 8–9 mm, which is why the contact setter stays for length.
See [LASER_TOOL_SETTER.md](LASER_TOOL_SETTER.md).

---

## Pendant

Plug in the WHB04B-6 USB receiver. LinuxCNC ships the udev rule, and
`xhc-whb04b-6.hal` starts the driver with `-HsfB`. Nothing else to wire.
