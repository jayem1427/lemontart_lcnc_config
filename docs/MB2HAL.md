# mb2hal for analog devices (VFD + PWM coolant)

A first-pass guide to LinuxCNC’s **Modbus-to-HAL** driver, using this mill’s two
devices as the examples:

| Device | Role | How LinuxCNC talks to it |
|--------|------|--------------------------|
| H100 VFD | Spindle RPM / run / fault | `S` / `M3` → HAL pins → mb2hal |
| PWM coolant | Frequency, duty, optional pressure | `M101` / `M68` → analog-out pins → mb2hal |

If you only need day-to-day coolant recipes (which M-code, which analog channel,
per-tool INI), use **[COOLANT.md](COOLANT.md)**. This page is the “I have never
configured mb2hal” version.

Upstream reference: [mb2hal(1)](https://linuxcnc.org/docs/html/man/man1/mb2hal.1.html).
Trust that man page for pin names and legal `MB_TX_CODE` values; this tree shows
how one machine wires them.

---

## 1. Mental model

G-code has **no Modbus**. There is no “M-code that writes register 100.”

```
something the operator/CAM understands
        │
        ▼
LinuxCNC pin  (float or bit)
        │
        ▼
optional HAL scale / mux / gate
        │
        ▼
mb2hal.<name>.00.float     ← you net to this
        │
        ▼
mb2hal userspace process   ← reads h100.mb2hal
        │
        ▼
RS-485  (USB dongle, /dev/ttyUSB0)
        │
        ▼
device register  (16-bit integer)
```

`mb2hal` is a **userspace** HAL component (`loadusr`), not a realtime module.
It periodically copies HAL floats onto the wire as Modbus RTU frames, and copies
replies back into HAL pins. That is the entire conversion.

Two worked paths on this mill:

**Spindle (already working)**

```
S12000 M3
  → spindle.0.speed-out-abs     (RPM)
  → mult2.4                     (× 0.166666 → 0.1 Hz units)
  → mb2hal.freq_set.00.float
  → function 06, slave 1, register 513
```

**Coolant (same idea, different slave)**

```
M101 P20000 Q35
  → M68 E4 / E5
  → motion.analog-out-04 / 05
  → scale + M9 gate in coolant.hal
  → mb2hal.coolant_freq.00.float
  → mb2hal.coolant_duty.00.float
  → function 06, slave 2, registers 100 / 101   (placeholders — see §5)
```

If you can follow the VFD path in [`custom.hal`](../custom.hal) +
[`h100.mb2hal`](../h100.mb2hal), you can add or retarget the coolant transactions.

---

## 2. What you need from the device manual

Before editing files, write these down from the **coolant controller** (or VFD)
manual. If a line is blank, mb2hal cannot be finished.

| Question | VFD on this mill | Coolant (fill in) |
|----------|------------------|-------------------|
| Electrical | 2-wire RS-485 | almost always the same |
| Baud, data bits, parity, stop | 38400 8N1 | **must match the VFD** if they share the dongle |
| Modbus slave ID | 1 | 2 (or whatever is not 1) |
| Write function | 06 (single holding register) | usually 06 or 16 |
| Frequency register | `0x0201` = **513 decimal** | |
| Duty / PWM register | — | |
| Pressure register (optional) | — | |
| Units in that register | 0.1 Hz (12000 RPM → 2000 in the register for a 2-pole-ish scale) | Hz? 0.1 Hz? 0–1000 = 0–100 %? |
| Is duty=0 a real stop? | stop is a *different* register (512) | if not, you need an enable coil too |

Hex vs decimal is the usual foot-gun. mb2hal `FIRST_ELEMENT` is **decimal**.
This mill’s VFD freq command is manual address `0x0201`:

```
0x0201 = 2×256 + 1 = 513
```

That is why [`h100.mb2hal`](../h100.mb2hal) says `FIRST_ELEMENT = 513`, not `201`.

Some manuals instead list “holding register 40101” (the old PLC numbering).
Drop the 4 and subtract 1: `40101` → protocol address **100**. When in doubt,
try the number the vendor shows in hex, converted to decimal, and watch the
device (or a USB Modbus sniffer) rather than assuming.

---

## 3. One dongle, many slaves

RS-485 is a **bus**. The PC is the only master. Several slaves share A/B/GND.

```
PC USB
  └── existing RS-485 dongle   /dev/ttyUSB0
        ├── H100 VFD      slave 1     38400 8N1
        └── coolant PWM   slave 2     38400 8N1
```

Physically daisy-chain A→A, B→B, GND→GND. Not a star, not a ring. 120 Ω
termination at the **far end** of the cable (and on the dongle only if it is
the other end). Swap A/B on **one** device if it never answers.

**Do not** start a second `mb2hal` on the same `/dev/ttyUSB0`. Two masters on
one UART will lose. This config loads mb2hal **once** from `custom.hal`:

```hal
loadusr -W mb2hal config=h100.mb2hal
```

Extra devices are extra `[TRANSACTION_xx]` blocks in **that same file**, with a
different `MB_SLAVE_ID`. Serial settings (`SERIAL_PORT`, baud, …) are set on
`TRANSACTION_00` and inherited.

A second USB adapter is only needed when baud/parity cannot match, the extra
device is analog (4–20 mA) rather than Modbus, or you deliberately want two
masters (then it is two buses).

---

## 4. Anatomy of `h100.mb2hal`

The file is **not** HAL and **not** the LinuxCNC INI. mb2hal reads it itself.
INI substitutions like `[COOLANT]SLAVE_ID` do **not** work here — type the
numbers.

### Header

```ini
[MB2HAL_INIT]
VERSION = 1.1
TOTAL_TRANSACTIONS = 7
HAL_MODULE_NAME = mb2hal
INIT_DEBUG = 1
```

`TOTAL_TRANSACTIONS` must equal the number of `[TRANSACTION_xx]` sections
(`00` through `06` → 7). If you comment out coolant txs, drop this count too
or mb2hal will look for missing sections and fail.

`INIT_DEBUG = 1` prints setup to the LinuxCNC console. `3` is very noisy; use
it only while chasing a slave that will not talk.

### One write transaction (VFD frequency)

```ini
[TRANSACTION_00]
LINK_TYPE = serial
SERIAL_PORT = /dev/ttyUSB0
SERIAL_BAUD = 38400
SERIAL_BITS = 8
SERIAL_PARITY = none
SERIAL_STOP = 1
SERIAL_DELAY_MS = 25
MB_SLAVE_ID = 1
MB_TX_CODE = fnct_06_write_single_register
FIRST_ELEMENT = 513
NELEMENTS = 1
HAL_TX_NAME = freq_set
MAX_UPDATE_RATE = 10.0
```

| Key | Meaning |
|-----|---------|
| `MB_TX_CODE` | Modbus function. `fnct_06_write_single_register` = “put this 16-bit value in one holding register.” |
| `FIRST_ELEMENT` | Register address, **decimal**. |
| `NELEMENTS` | How many consecutive registers. `06` is always 1. |
| `HAL_TX_NAME` | Becomes the HAL pin name. |
| `MAX_UPDATE_RATE` | How often to send, in Hz. `10` = at most every 0.1 s. |
| `SERIAL_DELAY_MS` | Pause after this (and between) transactions so slaves can think. |

That transaction creates:

```
mb2hal.freq_set.00.float
```

Pattern: `mb2hal.<HAL_TX_NAME>.<element>.float`. Element `00` is the first
(and here only) register. You **net a HAL float onto that pin**; mb2hal
truncates it to a 16-bit integer and writes it.

### One read transaction (VFD fault)

```ini
[TRANSACTION_03]
MB_SLAVE_ID = 1
MB_TX_CODE = fnct_04_read_input_registers
FIRST_ELEMENT = 10
NELEMENTS = 1
HAL_TX_NAME = vfd_fault
MAX_UPDATE_RATE = 2.0
```

Reads create the same pin shape; LinuxCNC **reads** `.float` instead of
writing it. Function **04** = input registers, **03** = holding registers.
Use whichever the manual specifies. This mill’s H100 fault is input register
`0x000A` = 10.

### Coolant writes (copy this)

```ini
[TRANSACTION_04]
MB_SLAVE_ID = 2
MB_TX_CODE = fnct_06_write_single_register
FIRST_ELEMENT = 100          ; PLACEHOLDER — your manual’s freq register
NELEMENTS = 1
HAL_TX_NAME = coolant_freq
MAX_UPDATE_RATE = 2.0
```

`HAL_TX_NAME = coolant_freq` → pin `mb2hal.coolant_freq.00.float`.
[`coolant.hal`](../coolant.hal) already nets analog-out-04 (after scale) to
that pin. Change **slave ID, register, function code, and scale** — not the
pin name — unless you also change the HAL `net`.

Keep coolant `MAX_UPDATE_RATE` **low** (1–2 Hz). The VFD wants ~10 Hz. Each
transaction costs `SERIAL_DELAY_MS` plus on-wire time. Three extra 2 Hz writes
are cheap; three extra 10 Hz writes can starve spindle freq-set.

---

## 5. Translate a datasheet → transaction

Worked example, imaginary coolant box:

> Slave ID 2, 38400 8N1.
> Holding register 0x0064 = PWM frequency, units 1 Hz.
> Holding register 0x0065 = duty, units 0.1 % (1000 = 100 %).
> Function 06 write.

That becomes:

```ini
[TRANSACTION_04]
MB_SLAVE_ID = 2
MB_TX_CODE = fnct_06_write_single_register
FIRST_ELEMENT = 100          ; 0x0064
HAL_TX_NAME = coolant_freq
MAX_UPDATE_RATE = 2.0

[TRANSACTION_05]
MB_SLAVE_ID = 2
MB_TX_CODE = fnct_06_write_single_register
FIRST_ELEMENT = 101          ; 0x0065
HAL_TX_NAME = coolant_duty
MAX_UPDATE_RATE = 2.0
```

Duty is 0.1 % per count, so 35 % must land in the register as 350. **Do not**
put that math in G-code. Put it in HAL:

```ini
# ethercat_mill.ini
[COOLANT]
DUTY_SCALE = 10.0     ; 35 % → 350
FREQ_SCALE = 1.0      ; 20000 Hz → 20000
```

[`coolant.hal`](../coolant.hal) already does:

```
motion.analog-out-05  →  (M9 mux)  →  coolant-duty-scale  →  mb2hal.coolant_duty.00.float
```

`FREQ_SCALE` / `DUTY_SCALE` / `PRESSURE_SCALE` are `scale.gain` on those
components. `1.0` means “G-code units = register units.”

16-bit holding registers only hold 0–65535 (or −32768–32767 if the device
treats them as signed). 20000 Hz fits. 200000 will wrap or clamp — if the
device wants millihertz, scale in HAL and confirm the product still fits.

---

## 6. HAL: connect the pin, then maybe gate it

mb2hal only **exports** pins. Nothing moves until a HAL `net` feeds them.

VFD (from `custom.hal`):

```hal
net spindle-speed-final mult2.4.out => mb2hal.freq_set.00.float
```

Coolant (from `coolant.hal`):

```hal
net coolant-freq-cmd motion.analog-out-04 => coolant-freq-scale.in
net coolant-freq-modbus coolant-freq-scale.out => mb2hal.coolant_freq.00.float
```

Coolant **enable** is deliberately not a Modbus register on this mill: stock
**M8/M7** set `iocontrol.0.coolant-flood` / `coolant-mist`. HAL ORs those bits
and, when false (M9 / abort / Flood off), muxes **duty and pressure to 0**
before they hit mb2hal. Frequency stays latched so the next M8 does not have
to rewrite Hz.

If *your* box needs a separate “run” coil (like the VFD’s register 512), add
another `fnct_05_write_single_coil` or `fnct_06` transaction and net
`coolant-enable` into it. Copy the VFD `mux4` / control-word pattern in
`custom.hal`, not the coolant duty mux.

---

## 7. G-code side (why M68 / M101 exist)

`M68 E<n> Q<value>` is built-in LinuxCNC: “set analog output n to this float
right now.” It is **one channel per line**.

| `M68` | Pin | This mill |
|-------|-----|-----------|
| E0–E3 | `motion.analog-out-00` … `03` | Laser mailbox — do not steal |
| E4 | `…-04` | Coolant Hz |
| E5 | `…-05` | Coolant duty % |
| E6 | `…-06` | Coolant psi |

`M101` is a tiny remap that issues those M68s from `P` / `Q` / `R` so CAM and
MDI can write one line. `M102` reads [`probe_basic/coolant_tools.ini`](../probe_basic/coolant_tools.ini)
for the loaded tool and issues the same M68s. Neither talks Modbus.

Details: [COOLANT.md](COOLANT.md).

---

## 8. Bring-up checklist

Do this in order. Skipping to “make chips with M8” hides whether the failure
is RS-485, register number, scale, or G-code.

1. **VFD still works.** `M3 S500` and `halcmd show pin mb2hal.freq_set` should
   look like they did before you added slave 2. If the spindle dies, the new
   transactions are starving or jamming the bus — lower coolant
   `MAX_UPDATE_RATE`, check A/B, check that slave 2 is actually present or
   disable those txs (below).
2. **Pins exist.** After LinuxCNC starts:

   ```bash
   halcmd show pin mb2hal.coolant
   ```

   You want `coolant_freq.00.float`, `coolant_duty.00.float`,
   `coolant_psi.00.float`. Missing pins → `TOTAL_TRANSACTIONS` / section names
   / `HAL_TX_NAME` typo, or `coolant.hal` commented out while you still
   expected the nets.
3. **Poke the analog in MDI** (machine on, no need for flood yet):

   ```
   M101 P20000 Q10
   ```

   ```bash
   halcmd getp motion.analog-out-04     # ~20000
   halcmd getp motion.analog-out-05     # ~10
   halcmd getp mb2hal.coolant_freq.00.float
   halcmd getp mb2hal.coolant_duty.00.float   # still 0 until M8
   ```

   Duty mb2hal pin stays 0 until **M8** because of the enable mux. That is
   success, not a bug.
4. **Enable:** `M8`, then re-read `mb2hal.coolant_duty.00.float` (and the
   scaled pin `coolant-duty-scale.out`). `M9` should drop the gated pins to 0
   while `motion.analog-out-05` may still show 10.
5. **Watch the device.** If HAL numbers are right and the box ignores them:
   wrong `FIRST_ELEMENT`, wrong function (03 vs 06, holding vs input), wrong
   slave ID, or units/scale. Bump `INIT_DEBUG` / per-transaction `DEBUG = 3`
   and read the LinuxCNC terminal.

### Disable coolant Modbus without deleting the feature

Until slave 2 is on the wire, failed txs add latency and log noise.

1. Comment `[TRANSACTION_04]` … `[TRANSACTION_06]` in `h100.mb2hal`.
2. Set `TOTAL_TRANSACTIONS = 4`.
3. Comment `HALFILE = coolant.hal` in `ethercat_mill.ini`.

Leave M101/M102 remaps in place; they only poke analog pins.

---

## 9. Common failures

| Symptom | Usual cause |
|---------|-------------|
| `mb2hal` pin missing | `TOTAL_TRANSACTIONS` ≠ number of `[TRANSACTION_xx]` sections; typo in `HAL_TX_NAME` |
| HAL float correct, device silent | `FIRST_ELEMENT` still hex; slave ID clash with the VFD; A/B swapped |
| Device reacts but value is 10× or 0.1× | Missing `FREQ_SCALE` / `DUTY_SCALE` |
| Device reacts, then wraps to a tiny number | Register is 16-bit; scaled value > 65535 |
| Spindle stutters after adding coolant txs | Coolant `MAX_UPDATE_RATE` too high, or slave 2 absent and timing out |
| Duty never leaves 0 | Forgot `M8`; or flood/mist bits not on (`halcmd getp iocontrol.0.coolant-flood`) |
| Laser diameter / length UI goes insane | You netted coolant onto E0–E3. Don’t. |
| Two USB adapters swap `ttyUSB0` across reboots | udev rule, or better: one dongle, two slaves |
| Second `loadusr mb2hal` on the same port | Don’t. Extra `[TRANSACTION]` in the existing file |

---

## 10. Function-code cheat sheet

From the [mb2hal man page](https://linuxcnc.org/docs/html/man/man1/mb2hal.1.html).
Use the name exactly.

| `MB_TX_CODE` | Modbus | Typical use |
|--------------|--------|-------------|
| `fnct_06_write_single_register` | 06 | Setpoint (Hz, duty, RPM, pressure) |
| `fnct_16_write_multiple_registers` | 16 | Several holding registers in one frame |
| `fnct_03_read_holding_registers` | 03 | Read back a setpoint or status word |
| `fnct_04_read_input_registers` | 04 | Read-only process value (this mill’s VFD fault) |
| `fnct_05_write_single_coil` | 05 | Boolean enable |
| `fnct_01_read_coils` / `fnct_02_read_discrete_inputs` | 01 / 02 | Boolean status |

PWM coolant on this mill only needs **06 writes**. Add a **03/04 read** later
if you want actual pressure or a fault code in the Logging tab
([SIGNAL_LOGGING.md](SIGNAL_LOGGING.md)).

---

## 11. Worksheet (copy into a note)

```
Device: __________________
Dongle: /dev/ttyUSB0   (or: ________)
Baud / parity / stop: ______  (must match H100: 38400 8N1)
Slave ID: ____  (must not be 1)

Freq  register: 0x____  = decimal ____   units: ________   HAL pin: mb2hal.coolant_freq.00.float
Duty  register: 0x____  = decimal ____   units: ________   HAL pin: mb2hal.coolant_duty.00.float
Press register: 0x____  = decimal ____   units: ________   HAL pin: mb2hal.coolant_psi.00.float

FREQ_SCALE = ____     DUTY_SCALE = ____     PRESSURE_SCALE = ____
Duty=0 stops spray?  yes / no   (if no: extra enable coil register ____)
```

Then edit **only** `FIRST_ELEMENT`, `MB_SLAVE_ID`, `MB_TX_CODE` (if not 06),
and `[COOLANT]*_SCALE`. Pin names and `coolant.hal` nets can stay.

---

## See also

| Doc | When |
|-----|------|
| [COOLANT.md](COOLANT.md) | M101/M102, analog E4–E6, per-tool INI, RS-485 physical wiring |
| [GETTING_STARTED.md](GETTING_STARTED.md) § Stage 4 | Where Modbus sits in the bring-up path |
| [`h100.mb2hal`](../h100.mb2hal) | Live transaction list |
| [`custom.hal`](../custom.hal) | VFD scale + loadusr |
| [`coolant.hal`](../coolant.hal) | Coolant nets, M9 gate, scale |
| [mb2hal(1)](https://linuxcnc.org/docs/html/man/man1/mb2hal.1.html) | Canonical pin names and codes |
