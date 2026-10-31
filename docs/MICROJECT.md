# Microject PCB — install, bench, LinuxCNC

Wire the Dan Mills injector, prove it with `mbpoll`, then run the LinuxCNC M-codes.
Map and HAL theory: [COOLANT.md](COOLANT.md) · [MB2HAL.md](MB2HAL.md).

Factory DIP: **19200 8E1, slave 8, port 1**. The H100 stays on its own dongle
(**38400 8N1, slave 1**). Put both on one pair only after the injector DIP is
also 38400 8N1.

| | Port 1 (this mill) |
|--|--|
| Coil | **1** — mbpoll `-r 1`, mb2hal address **0** |
| Pulse / period | **H1** / **H2**, milliseconds. Unwritten default: 1 ms / 100 ms |
| Watchdog | Coil off **5 s** after the last good Modbus message |
| Power | **24 V** on the PCB. GM0521994 is a 12 V coil; the board drives it |

`M101 P10 Q1` is a 100 ms period and a 1 ms pulse. HAL clamps the rate to 1–50 Hz.

## 1. Install

1. 24 V on the PCB, injector in **port 1**, A/B + GND on a second USB–RS-485 dongle, 120 Ω at the far end. Swap A/B if the board never answers.
2. LinuxCNC stopped. Set `SERIAL_PORT` in [`microject.mb2hal`](../microject.mb2hal) from `ls -l /dev/serial/by-id/` (`ttyUSB` numbers swap when two adapters are plugged in). That file is what mb2hal opens. HAL reads only `[COOLANT] PULSE_SCALE` and `PERIOD_SCALE` (`1.0` = ms; `10` = 0.1 ms counts).
3. `sudo apt install mbpoll`. One master on the port: quit `mbpoll` before `linuxcnc`.

Already loaded in this tree: `HALFILE = coolant.hal` (after `custom.hal`), `REMAP=M101`, `REMAP=M102`, `probe_basic/coolant_tools.ini`. Leave M7/M8/M9 stock. Injector on **port 4**: mbpoll `-r 4`, `-r 7`, `-r 8`, and mb2hal `FIRST_ELEMENT` **3 / 6 / 7**.

## 2. Modbus bench

LinuxCNC is stopped. One `mbpoll` at a time. `-1` writes once and exits. The coil line keeps polling (1 s) so the watchdog stays fed — expect a ~10 Hz click. Ctrl-C: the click stops within ~5 s. The last line is an explicit coil off.

```bash
mbpoll /dev/ttyUSB1 -1 -v -m rtu -a 8 -b 19200 -P even -t 4 -r 1 1    # H1 pulse
mbpoll /dev/ttyUSB1 -1 -v -m rtu -a 8 -b 19200 -P even -t 4 -r 2 100  # H2 period
mbpoll /dev/ttyUSB1 -v -m rtu -a 8 -b 19200 -P even -t 0 -r 1 1       # coil 1 on
mbpoll /dev/ttyUSB1 -1 -v -m rtu -a 8 -b 19200 -P even -t 0 -r 1 0    # coil 1 off
```

Silence: wrong tty, A/B, slave, baud/parity, or no 24 V. `modbuslens` sniffs this port. Windows: QModMaster, OpenModScan, Modbus Tester.

## 3. LinuxCNC

`linuxcnc ethercat_mill.ini`, Machine On, then `halcmd show pin microject`.
Expect `coolant_run.00.bit`, `coolant_pulse.00.float`, `coolant_period.00.float`.

**M101** and **M102** write the recipe only. **M8** (flood) or **M7** (mist) turns coil 1 on. **M9** turns it off and forces the pulse register to 0. Analog: **E4** Hz, **E5** duty %, **E6** pressure (no register yet). Laser owns E0–E3.

| MDI | Pass |
|-----|------|
| `M101 P10 Q1` then `M8` | run TRUE, period ~100, pulse ~1, ~10 Hz click |
| `M9` | run FALSE, pulse 0 |
| `M7` then `M9` | mist drives the same coil, then off |
| `T3 M6` then `M102` then `M8` | `coolant T3: 10 Hz, 2.0 % duty`, pulse ~2 |
| `T99 M6` then `M102` then `M8` | touch probe is dry: 0 Hz, 0 % |
| Flood, Mist, or the pendant | same coil (`iocontrol` flood OR mist) |

```bash
halcmd getp microject.coolant_run.00.bit
halcmd getp microject.coolant_period.00.float
halcmd getp microject.coolant_pulse.00.float
```

Unplug the injector dongle during `M8`: spray stops within ~5 s. Plug it back in and start LinuxCNC again so mb2hal opens the port. `M600` ends with `M102` (recipe for the new tool, coil unchanged). Abort runs `M9`. Fusion **Apply mill PWM coolant** emits `M102` on the line before `M7`/`M8`; the numbers stay in `coolant_tools.ini`. Comment `HALFILE = coolant.hal` to unload the injector.

| What you see | Where to look |
|--------------|----------------|
| No `microject` pins | `coolant.hal` in `[HAL]`; `-Wn microject` matches `HAL_MODULE_NAME`; tty free of `mbpoll` |
| Pins good, no click | 24 V, A/B, port, tty. mbpoll works and HAL does not → coil `FIRST_ELEMENT` **1** |
| Clicks ~5 s, then stops | Bus went quiet. Shipped `MAX_UPDATE_RATE` is 2 Hz |
| Spindle dies on plug-in | Dongles swapped, or the injector is still on the VFD pair |
| Laser tab goes wild | Coolant analog outputs are on E0–E3 |
