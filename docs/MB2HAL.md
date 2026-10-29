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

**Microject (this mill, port 1)**

```
M101 P10 Q1
  → analog E4 = 10 Hz, E5 = 1 %
  → coolant.hal: period_ms = 1000/Hz, pulse_ms = period * duty/100
  → microject.coolant_period.00.float  → fnct_06 Hreg 2 = 100
  → microject.coolant_pulse.00.float   → fnct_06 Hreg 1 = 1

M8
  → iocontrol.0.coolant-flood
  → or2 with mist
  → microject.coolant_run.00.bit
  → function 05, slave 8, coil 1 (PDU address 0)
```

Firmware default if the Hreg writes never land: **1 ms on / 100 ms period**.

---

## 2. What you need from the device

| Question | H100 VFD | Microject (Dan Mills, testers chat) |
|----------|----------|-------------------------------------|
| Electrical | 2-wire RS-485 | 2-wire RS-485 + **24 V** supply |
| Baud / bits / parity / stop | 38400 8**N**1 | **19200 8E1** unless DIP switches say otherwise |
| Slave ID | 1 | **8** |
| Enable | holding register 512 (control word) | **coil N** for port N (`fnct_05`; port 1 → coil 1) |
| Pulse recipe | n/a | defaults 1 ms / 100 ms; **H 2N−1** pulse, **H 2N** period (port 1 → H1 / H2) |
| Watchdog | VFD-specific | coil OFF **5 s** after last **valid** message |
| Bench tool | — | `mbpoll`, `modbuslens` |

Hex vs decimal: mb2hal `FIRST_ELEMENT` is **decimal**. VFD freq `0x0201` =
**513**. That is why `h100.mb2hal` says 513, not 201.

Coil numbering: Dan’s `mbpoll … -t0 -r1 1` is **1-based coil 1**. libmodbus /
mb2hal protocol address is **0**. [`microject.mb2hal`](../microject.mb2hal)
uses `FIRST_ELEMENT = 0`. If the injector never fires, try `1`.

---

## 3. Why this mill uses two dongles

RS-485 is a bus: **one master**, many slaves, **same baud/parity**. The master
picks a device by **slave ID** in each request (H100 = 1, Microject = 8), not
by which wire pair it is on.

You *can* daisy-chain A–A, B–B, GND–GND on the existing VFD dongle — that is
the normal RS-485 topology — **but only after baud and parity match**.
Microject factory defaults (**19200 even**) do **not** match the H100
(**38400 none**). Dan’s testers chat: DIPs were not changed before ship.
Until you flip the injector to 38400 8N1, a series splice will just corrupt
the VFD bus.

```
PC
 ├─ dongle A  /dev/ttyUSB0   38400 8N1   H100 slave 1
 └─ dongle B  /dev/ttyUSB1   19200 8E1   Microject slave 8
```

That is two buses, two `loadusr mb2hal` processes, two `HAL_MODULE_NAME`s
(`mb2hal` and `microject`). Legal.

**Do not** run two mb2hal instances on the **same** tty.

If you later set the injector to 38400 8N1, daisy-chain on the VFD dongle and
move the Microject transactions into `h100.mb2hal` with `MB_SLAVE_ID = 8`.
Until then, keep them apart.

Physical RS-485: daisy-chain, not a star, not a ring. 120 Ω at the far end.
Swap A/B on one device if it never answers.

### Bench tools (not a LinuxCNC GUI)

LinuxCNC has no Modbus scanner. Prove the wire first, then watch HAL pins:

| Where | Tool |
|-------|------|
| Linux, outside LinuxCNC | `mbpoll` (writes), `modbuslens` (sniff / extra diagnostics) |
| LinuxCNC running | `halcmd show pin microject` / `halcmd getp …` (this mill’s bring-up below) |
| Windows laptop | QModMaster, OpenModScan, Modbus Tester (free; Dan noted commercial ones are pricey) |

`mbpoll` examples for port 1 are in [COOLANT.md](COOLANT.md) and in the header
of [`microject.mb2hal`](../microject.mb2hal).

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

## 5. Holding registers (pulse + period)

Dan (port 4 example): pulse length on **Hregister 7**, period on **Hregister 8**.
That is **two registers per injector port**:

```
port N:  coil N,  pulse Hreg 2N-1,  period Hreg 2N
```

Port 1 (this config): coil 1, **H1** pulse, **H2** period. mb2hal 0-based:
`FIRST_ELEMENT` 0 / 0 / 1. Richie landed on port 4 after swapping wires — same
Modbus, just coil 4 / H7 / H8; pot/switch mode is channels 1–2 only.

G-code stays Hz + duty %; HAL converts:

```
period_ms = 1000 / freq_Hz          # 10 Hz → 100
pulse_ms  = period_ms * duty / 100  # 1 % → 1
```

Assume milliseconds until a dump says otherwise. If the regs are 0.1 ms,
`[COOLANT]PULSE_SCALE` / `PERIOD_SCALE` = 10.

Reads (opto inputs, analog) work according to Dan; not mapped in HAL yet.

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
6. `M101 P10 Q1` then `M8`:
   `halcmd getp microject.coolant_period.00.float` → ~100
   `halcmd getp microject.coolant_pulse.00.float` → ~1
   `M9` zeros the pulse float even if E5 is still 1.

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
| `fnct_06_write_single_register` | H100 freq/ctrl; Microject pulse (H1) and period (H2) |
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

Port 1 (default): coil 1, pulse H1, period H2  (mb2hal 0 / 0 / 1)
Port 4 (Richie):  coil 4, pulse H7, period H8  (mb2hal 3 / 6 / 7)
Units assumed ms; SCALE if 0.1 ms.
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
