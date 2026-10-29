# mb2hal for analog devices (VFD + Microject)

A first-pass guide to LinuxCNC’s **Modbus-to-HAL** driver, using this mill’s two
devices:

| Device | Role | Link |
|--------|------|------|
| H100 VFD | Spindle RPM / run / fault | `/dev/ttyUSB0` 38400 **8N1** slave **1** (`h100.mb2hal`) |
| Microject | Injector enable (coil 1) | `/dev/ttyUSB1` 19200 **8E1** slave **8** (`microject.mb2hal`) |

Day-to-day M-codes and wiring: **[COOLANT.md](COOLANT.md)**. Upstream:
[mb2hal](https://linuxcnc.org/docs/html/drivers/mb2hal.html).

---

## 1. Mental model

G-code has **no Modbus**. There is no “M-code that writes register 100.”

```
M8 / S-word / M68
        │
        ▼
LinuxCNC pin  (bit or float)
        │
        ▼
optional HAL scale / mux
        │
        ▼
<component>.<tx>.00.bit  or  .float     ← you net to this
        │
        ▼
mb2hal userspace process   ← reads a .mb2hal file
        │
        ▼
RS-485 USB dongle
        │
        ▼
device coil or 16-bit register
```

`mb2hal` is **userspace** (`loadusr`), not realtime. It copies HAL pins onto
the wire on a timer (`MAX_UPDATE_RATE`).

**Spindle (this mill, working)**

```
S12000 M3
  → spindle.0.speed-out-abs     (RPM)
  → mult2.4                     (× 0.166666 → 0.1 Hz units)
  → mb2hal.freq_set.00.float
  → function 06, slave 1, register 513
```

**Microject (this mill, coil only so far)**

```
M8
  → iocontrol.0.coolant-flood
  → or2 with mist
  → microject.coolant_run.00.bit
  → function 05, slave 8, coil 1 (PDU address 0)
```

Firmware then pulses the injector at **1 ms on / 100 ms period** until you
write holding registers (addresses still unknown — do not invent them).

---

## 2. What you need from the device

| Question | H100 VFD | Microject (Dan Mills, testers chat) |
|----------|----------|-------------------------------------|
| Electrical | 2-wire RS-485 | 2-wire RS-485 + **24 V** supply |
| Baud / bits / parity / stop | 38400 8**N**1 | **19200 8E1** unless DIP switches say otherwise |
| Slave ID | 1 | **8** |
| Enable | holding register 512 (control word) | **coil #1** (`fnct_05`) |
| Pulse recipe | n/a | defaults 1 ms / 100 ms; override via **holding registers** (numbers TBD) |
| Watchdog | VFD-specific | coil OFF **5 s** after last **valid** message |
| Bench tool | — | `mbpoll`, `modbuslens` |

Hex vs decimal: mb2hal `FIRST_ELEMENT` is **decimal**. VFD freq `0x0201` =
**513**. That is why `h100.mb2hal` says 513, not 201.

Coil numbering: Dan’s `mbpoll … -t0 -r1 1` is **1-based coil 1**. libmodbus /
mb2hal protocol address is **0**. [`microject.mb2hal`](../microject.mb2hal)
uses `FIRST_ELEMENT = 0`. If the injector never fires, try `1`.

---

## 3. Why this mill uses two dongles

RS-485 is a bus: **one master**, many slaves, **same baud/parity**.

Microject defaults (**19200 even**) do **not** match the H100 (**38400 none**).
They cannot share `/dev/ttyUSB0` unless you change the injector DIP switches.

```
PC
 ├─ dongle A  /dev/ttyUSB0   38400 8N1   H100 slave 1
 └─ dongle B  /dev/ttyUSB1   19200 8E1   Microject slave 8
```

That is two buses, two `loadusr mb2hal` processes, two `HAL_MODULE_NAME`s
(`mb2hal` and `microject`). Legal.

**Do not** run two mb2hal instances on the **same** tty.

If you later set the injector to 38400 8N1, daisy-chain A/A B/B GND/GND on the
VFD dongle and move the Microject transactions into `h100.mb2hal` with
`MB_SLAVE_ID = 8`. Until then, keep them apart.

Physical RS-485: daisy-chain, not a star, not a ring. 120 Ω at the far end.
Swap A/B on one device if it never answers.

---

## 4. Anatomy of a `.mb2hal` file

Not HAL, not the LinuxCNC INI. mb2hal reads it itself — **no** `[COOLANT]KEY`
substitution. Type the numbers.

### Header

```ini
[MB2HAL_INIT]
VERSION = 1.1          ; required for fnct_05 coil writes
TOTAL_TRANSACTIONS = 1
HAL_MODULE_NAME = microject
INIT_DEBUG = 1
```

`TOTAL_TRANSACTIONS` must equal the number of `[TRANSACTION_xx]` sections.
`VERSION = 1.1` is required for `fnct_05_write_single_coil`.

Load a custom component name with matching `-Wn`:

```hal
loadusr -Wn microject mb2hal config=microject.mb2hal
```

Pins are then `microject.<HAL_TX_NAME>.00.bit` (coil) or `.float` (register).

### One coil write (Microject enable)

```ini
[TRANSACTION_00]
LINK_TYPE = serial
SERIAL_PORT = /dev/ttyUSB1
SERIAL_BAUD = 19200
SERIAL_BITS = 8
SERIAL_PARITY = even
SERIAL_STOP = 1
SERIAL_DELAY_MS = 20
MB_SLAVE_ID = 8
MB_TX_CODE = fnct_05_write_single_coil
FIRST_ELEMENT = 0
NELEMENTS = 1
HAL_TX_NAME = coolant_run
MAX_UPDATE_RATE = 2.0
```

| Key | Meaning here |
|-----|----------------|
| `SERIAL_PARITY = even` | Dan’s 8-E-1 |
| `fnct_05_write_single_coil` | HAL pin is **`.bit`**, not `.float` |
| `MAX_UPDATE_RATE = 2.0` | Rewrite coil every 0.5 s so the **5 s watchdog** stays fed |

### One register write (VFD frequency, for comparison)

```ini
MB_TX_CODE = fnct_06_write_single_register
FIRST_ELEMENT = 513
HAL_TX_NAME = freq_set
```

Pin: `mb2hal.freq_set.00.float`. HAL float is truncated to uint16 on the wire.

A **new link** (second UART) must repeat `LINK_TYPE`, `SERIAL_*`, and
`MB_SLAVE_ID` on that transaction. Later txs inherit. Optional keys omitted
are copied from the previous transaction — easy to accidentally inherit the
VFD’s 38400 none onto the injector if you merge files carelessly.

---

## 5. Holding registers (not wired yet)

Dan: override the 1 ms / 100 ms default by **writing holding registers**.
Those addresses were not in the first testers dump.

**Do not** add `fnct_06` placeholders. A timed-out write costs
`MB_RESPONSE_TIMEOUT_MS` (default 500 ms) and can delay the coil transaction
past 5 s → injector watchdog trips even though M8 is on.

When the map lands, typical conversion from G-code (Hz + duty %) is:

```
period_ms = 1000 / freq_Hz          # 10 Hz → 100 ms
on_ms     = period_ms * duty / 100  # 1 % → 1 ms
```

Put that math in HAL, not in Fusion. Then net to
`microject.<name>.00.float`.

Until then M101/M102 only poke analog E4/E5/E6.

---

## 6. HAL: coil enable

[`coolant.hal`](../coolant.hal):

```hal
loadusr -Wn microject mb2hal config=microject.mb2hal
net coolant-flood iocontrol.0.coolant-flood => or2.2.in0
net coolant-mist  iocontrol.0.coolant-mist  => or2.2.in1
net coolant-enable or2.2.out => microject.coolant_run.00.bit
```

Stock **M8/M7** set those iocontrol bits. **M9** clears them. Probe Basic
Flood/Mist buttons and the pendant stay in sync. Do not remap M7/M8/M9.

---

## 7. Bring-up checklist

1. **VFD still works** on USB0 (`M3 S500`). If the spindle dies after adding
   a dongle, ports swapped — udev.
2. **Bench coil** with `mbpoll` (above) before LinuxCNC. Injector should tick
   at ~10 Hz, 1 % (a faint click / tiny dribble).
3. LinuxCNC up:

   ```bash
   halcmd show pin microject
   # expect microject.coolant_run.00.bit
   ```

4. MDI `M8`. `halcmd getp microject.coolant_run.00.bit` → TRUE. `M9` → FALSE.
5. Unplug USB1 with M8 on: within ~5 s the injector must stop (watchdog).
6. Holding registers: only after Dan’s map. Then add `fnct_06` txs and HAL
   period/on-time math.

Disable Microject without deleting files: comment `HALFILE = coolant.hal`.

---

## 8. Common failures

| Symptom | Usual cause |
|---------|-------------|
| `microject` pin missing | `coolant.hal` not in `[HAL]`, or `loadusr -Wn` / `HAL_MODULE_NAME` mismatch |
| Coil pin TRUE, no spray | `FIRST_ELEMENT` 0 vs 1; A/B swapped; 24 V missing; wrong tty |
| Spray for 5 s then dies | Coil writes not cycling (`MAX_UPDATE_RATE`); extra failed txs blocking the UART |
| VFD and injector swapped | Two USB adapters, no udev rule |
| Garbage on the VFD after daisy-chain | Injector still 19200 8E1 on the 38400 8N1 bus |
| Laser UI insane | Coolant analog on E0–E3. Don’t. |

---

## 9. Function-code cheat sheet

| `MB_TX_CODE` | Use on this mill |
|--------------|------------------|
| `fnct_05_write_single_coil` | Microject run (coil 1) |
| `fnct_06_write_single_register` | H100 freq/ctrl; Microject on-time/period later |
| `fnct_04_read_input_registers` | H100 fault / freq fb |
| `fnct_03_read_holding_registers` | Read-back setpoints (optional) |

---

## 10. Worksheet

```
Microject
  tty: /dev/ttyUSB1
  19200 8E1  slave 8
  coil 1 enable:  mbpoll … -t 0 -r 1 1
  mb2hal FIRST_ELEMENT for that coil: 0 (try 1 if dead)

On-time holding register:  0x____ = ____   units: ms?
Period  holding register:  0x____ = ____   units: ms?
Pressure (if any):         0x____ = ____
```

---

## See also

| Doc / file | When |
|------------|------|
| [COOLANT.md](COOLANT.md) | M8 coil, analog E4–E6, plumbing |
| [`microject.mb2hal`](../microject.mb2hal) | Live injector transactions |
| [`h100.mb2hal`](../h100.mb2hal) | VFD transactions |
| [`coolant.hal`](../coolant.hal) | flood/mist → coil |
| [mb2hal.html](https://linuxcnc.org/docs/html/drivers/mb2hal.html) | Pin names and codes |
