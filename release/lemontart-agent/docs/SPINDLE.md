# Spindle (H100 VFD over Modbus)

The spindle is a 24 000 RPM motor on an H100 VFD. LinuxCNC talks to the VFD
over RS-485 Modbus. It sets the speed and direction, reads back the actual
frequency and current, and watches for faults. There is no encoder.

If you've never set up Modbus in LinuxCNC, read [MODBUS.md](MODBUS.md) first.

## Connection

| Setting | Value |
|---------|-------|
| Adapter | CH340 USB-RS485, `/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0` |
| Serial | 38400 baud, 8 data bits, no parity, 1 stop bit (8N1) |
| Modbus slave ID | 1 |
| Driver | `mb2hal` (component name `mb2hal`), loaded at the top of `custom.hal` |
| Register map | `h100.mb2hal` |

The VFD's own communication settings (baud, format, address, and "run and
frequency from RS-485") are set on the VFD's keypad. The parameter numbers are
in the H100 manual: [`reference/h100 manual.pdf`](reference/h100%20manual.pdf).

## Registers used

Register numbers in `.mb2hal` files are **decimal**. The manual lists them in
hex.

| What | Register (hex / decimal) | Function | HAL pin |
|------|--------------------------|----------|---------|
| Set frequency | 0x0201 / 513 | 06 write | `mb2hal.freq_set.00.float` |
| Run / stop / direction | 0x0200 / 512 | 06 write | `mb2hal.vfd_ctrl.00.float` |
| Output frequency, current, … | 0x0000 / 0, 4 registers | 04 read | `mb2hal.freq_fb.00` … `.03` |
| Current fault code | 0x000A / 10 | 04 read | `mb2hal.vfd_fault.00.float` |

## How it's wired in HAL (`custom.hal`)

```
spindle speed (RPM) → × 0.166666 → freq_set           (RPM → VFD 0.1 Hz units)
M3 / M4 / M5 → mux4 → vfd_ctrl                        (3 = run fwd, 5 = run rev, 8 = stop)
freq_fb.00 → × 6 → spindle.0.speed-in                 (back to RPM)
freq_fb.02 → × 0.01 → spindle-current                 (amps)
|command − feedback| ≤ 50 RPM → wait 5 s → spindle.0.at-speed
fault code 64 or 92 → halui.estop.activate
```

- **M3 and M4 are swapped.** The VFD's forward/reverse is backwards relative
  to LinuxCNC on this machine, so **`M3` runs the VFD in reverse**. The swap is
  two lines in `custom.hal` marked `REVERT:`.
- **The 5 s at-speed delay.** The VFD reports "at speed" a little before the
  spindle really is. After the feedback matches the command (±50 RPM), HAL
  waits another 5 s before releasing the program. Change
  `spindle-at-speed-delay.on-delay` to tune it.
- **Critical faults stop the machine.** Fault 64 (E.OCS, overcurrent) and 92
  (E.oHS, inverter overheat) trigger a software E-stop.
- **Probe Basic's RPM and load gauges** read `spindle-speed-in` and
  `spindle-current` (`probe_basic_postgui.hal`). Load % assumes about 4.2 A at
  full load (`mult2.7.in1 = 23.81`).

## Checking it

```bash
halcmd show pin mb2hal                 # all VFD pins
halcmd getp mb2hal.vfd_fault.00.float  # 0 = no fault
```

Then `M3 S6000`. `spindle.0.speed-in` should read about 6000, and
`spindle.0.at-speed` should go true about 5 s later. `M5` stops it.

To test the wiring without LinuxCNC, see [MODBUS.md](MODBUS.md#bench-testing).

## Different spindle?

Keep the structure (scale → command, feedback → `speed-in`, compare →
at-speed) and change `h100.mb2hal` to your VFD's registers. Recompute the
scale factor: it converts RPM into whatever units your VFD's frequency
register uses. If you have an encoder instead, wire it to `spindle.0.speed-in`
and drop the Modbus feedback.
