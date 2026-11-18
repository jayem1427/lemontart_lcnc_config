# Modbus (mb2hal) for the spindle and coolant

Two devices on this mill talk Modbus RTU over RS-485: the spindle VFD and the
MQL coolant controller. LinuxCNC's `mb2hal` driver connects them to HAL. This
page covers the parts both have in common: adapters, the `.mb2hal` file
format, and how to test on the bench. Device specifics are in
[SPINDLE.md](SPINDLE.md) and [COOLANT.md](COOLANT.md).

Upstream reference: [mb2hal documentation](https://linuxcnc.org/docs/html/drivers/mb2hal.html).

---

## The idea

G-code has no Modbus commands. Instead, HAL pins are copied to and from
device registers on a timer:

```
G-code (M3 S…, M8, M201…)  →  LinuxCNC pin  →  HAL math  →  mb2hal pin  →  RS-485  →  device register
```

`mb2hal` is a normal user process (`loadusr`), not real-time. Each
"transaction" in a `.mb2hal` file reads or writes some registers at up to
`MAX_UPDATE_RATE` times a second, and creates HAL pins named
`<HAL_MODULE_NAME>.<HAL_TX_NAME>.NN`.

---

## One adapter per device

| Device | Adapter | Settings | Slave ID | Loaded by |
|--------|---------|----------|----------|-----------|
| H100 VFD | CH340 | 38400 8N1 | 1 | `custom.hal`: `loadusr -W mb2hal config=h100.mb2hal` |
| Microject | FTDI FT232R | 19200 8E1 | 8 | `coolant.hal`: `loadusr -Wn microject mb2hal config=microject.mb2hal` |

RS-485 is a bus. One master can talk to many devices, selecting each by slave
ID, **but they all have to use the same baud and parity**. These two don't
match out of the box, so each one gets its own adapter and its own `mb2hal`
process. That's fine as long as the two processes use different
`HAL_MODULE_NAME`s (`mb2hal` and `microject` here).

Never point two `mb2hal` processes at the same adapter.

If you set the Microject's DIP switches to 38400 8N1, both devices could share
one adapter, daisy-chained A–A, B–B. You'd then move the Microject
transactions into `h100.mb2hal` with `MB_SLAVE_ID = 8`.

### Use stable device names

```bash
ls -l /dev/serial/by-id/
```

```
usb-1a86_USB_Serial-if00-port0                 -> ../../ttyUSB0   (CH340: spindle)
usb-FTDI_FT232R_USB_UART_BG02XIBV-if00-port0   -> ../../ttyUSB1   (FTDI: coolant)
```

Put the `by-id` path in `SERIAL_PORT`, never `/dev/ttyUSB0`. The `ttyUSB`
numbers follow plug-in order and can swap after a reboot, which silently sends
spindle commands to the coolant controller. The FTDI has a unique serial
number. The CH340 doesn't, so if you ever add a **second CH340**, switch to
`/dev/serial/by-path/…` (tied to the physical USB port) instead.

To find out which adapter is wired to which device, unplug one and see which
`by-id` entry disappears, or run the bench test below on each.

---

## Anatomy of a `.mb2hal` file

It's not HAL and not the INI. mb2hal reads it directly, so INI substitutions
like `[COOLANT]SLAVE_ID` don't work here. Type the numbers.

```ini
[MB2HAL_INIT]
VERSION = 1.1              ; needed for coil writes (fnct_05)
TOTAL_TRANSACTIONS = 3
HAL_MODULE_NAME = microject
INIT_DEBUG = 1

[TRANSACTION_00]
LINK_TYPE = serial         ; the first transaction defines the link…
SERIAL_PORT = /dev/serial/by-id/usb-FTDI_FT232R_USB_UART_BG02XIBV-if00-port0
SERIAL_BAUD = 19200
SERIAL_BITS = 8
SERIAL_PARITY = even
SERIAL_STOP = 1
SERIAL_DELAY_MS = 20
MB_SLAVE_ID = 8
MB_TX_CODE = fnct_05_write_single_coil
FIRST_ELEMENT = 0          ; 0-based address, decimal
NELEMENTS = 1
HAL_TX_NAME = coolant_run  ; → pin microject.coolant_run.00.bit
MAX_UPDATE_RATE = 2.0

[TRANSACTION_01]           ; …later transactions inherit anything they don't set
MB_TX_CODE = fnct_06_write_single_register
FIRST_ELEMENT = 0
NELEMENTS = 1
HAL_TX_NAME = coolant_pulse
MAX_UPDATE_RATE = 2.0
```

Things that trip people up:

- **Addresses are decimal and 0-based.** The VFD manual's register `0x0201`
  is `FIRST_ELEMENT = 513`. A tool like `mbpoll` that calls it "coil 1" means
  `FIRST_ELEMENT = 0`.
- **Transactions inherit settings** from the one before. If you merge two
  devices into one file, restate `SERIAL_*` and `MB_SLAVE_ID` on the first
  transaction of each device, or one will silently pick up the other's baud
  rate.
- **Coils are `.bit` pins, registers are `.float` pins.** A float written to
  a register is truncated to a 16-bit integer.

| `MB_TX_CODE` | Used here for |
|--------------|---------------|
| `fnct_05_write_single_coil` | Microject on/off |
| `fnct_06_write_single_register` | VFD frequency and run command; Microject pulse and period |
| `fnct_04_read_input_registers` | VFD frequency/current feedback and fault code |
| `fnct_03_read_holding_registers` | Reading back setpoints (not used live) |

---

## Bench testing

Prove the wiring before LinuxCNC is involved. Stop LinuxCNC first: only one
program can open an adapter. `mbpoll` (`sudo apt install mbpoll`) works well:

```bash
# Spindle: read the fault register (input register 10, slave 1, 38400 8N1)
mbpoll /dev/serial/by-id/usb-1a86_USB_Serial-if00-port0 -m rtu -a 1 -b 38400 -P none -t 3 -r 11 -c 1

# Coolant: read the pulse-length register (holding register 1, slave 8, 19200 8E1)
mbpoll /dev/serial/by-id/usb-FTDI_FT232R_USB_UART_BG02XIBV-if00-port0 -m rtu -a 8 -b 19200 -P even -t 4 -r 1 -c 1
```

`mbpoll` numbers registers from 1, so mb2hal's `FIRST_ELEMENT = 10` is
`-r 11`. On Windows, QModMaster and OpenModScan are free alternatives.

**No reply at all?** In this order:

1. A and B swapped. Swap them at one end.
2. Wires on the wrong terminal (a GND terminal instead of A or B).
3. Device not powered, or its comms settings don't match.
4. Wrong adapter (check `by-id`).

**Replies, but garbage?** Baud or parity mismatch.

Once LinuxCNC is running, watch the pins instead:

```bash
halcmd show pin mb2hal
halcmd show pin microject
```

mb2hal prints transaction errors to the terminal LinuxCNC was started from.
A few at shutdown are normal.
