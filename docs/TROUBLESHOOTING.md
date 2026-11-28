# Troubleshooting

Symptoms seen on this mill and what actually caused them. Many of them have
a cause that isn't the obvious one, which is why they're written down. The
laser setter and one-click tuner have their own tables in
[LASER_TOOL_SETTER.md](LASER_TOOL_SETTER.md#troubleshooting) and
[ONE_CLICK_TUNING.md](ONE_CLICK_TUNING.md#the-journal).

## Commands you'll use a lot

```bash
ethercat slaves                     # are all drives there, and in OP?
halcmd show pin lcec.0.1            # every pin on slave 1
halcmd getp motion.probe-input      # is the probe input tripped?
halcmd show pin halui.tool.number   # which tool LinuxCNC thinks is loaded
watch -n 0.2 halcmd getp spindle.0.at-speed   # live view of one pin
ls -l /dev/serial/by-id/            # which USB-serial adapter is which
```

Start LinuxCNC from a terminal (`./launch.sh`) so you can see HAL and mb2hal
errors.

---

## LinuxCNC won't start

| Symptom | Cause / fix |
|---------|-------------|
| `lcec_conf` fails, no slaves | EtherCAT master not running (`systemctl status ethercat`), wrong MAC in `/etc/ethercat.conf`, drives not powered |
| HAL components "fail to load" (lowpass, limit1, …) | Usually stale LinuxCNC processes from a crash, not the component. Reboot, or `halrun -U` |
| A HAL file errors on a `net` line | Two writers on one signal, or `count=` and `names=` mixed for one component. See [CONFIG_TOUR.md](CONFIG_TOUR.md#hal-conventions-in-this-config) |
| "Parameter file out of order" | `linuxcnc.var` must be sorted by number. Sort it, or open the Laser Setter tab once |
| "Bad character 'o' used on startup" | An O-word call in `RS274NGC_STARTUP_CODE`. Not allowed there |
| Probe Basic crashes with `FileNotFoundError` for `x/x.py` | A leftover folder in `probe_basic/user_tabs/` after a branch switch. Delete it |
| Probe Basic window blank or broken | Start with `QT_QUICK_BACKEND=software` (`launch.sh` does) |
| Fails on stock LinuxCNC 2.9 with a TP module error | This branch's INI uses the tpnext planner. Comment out `TPMOD`. See [SETUP.md](SETUP.md#stock-linuxcnc-vs-the-tpnext-build) |

## Motion and drives

| Symptom | Cause / fix |
|---------|-------------|
| Whole machine shakes violently on enable | DC clock in R2M mode. Use M2R (`refClockSyncCycles="-1"`) |
| "joint 3 amplifier fault" at startup or mid-tune, drive error `0x8611` (following error) | The unconnected A motor tripped its 0.5° window. A's `6065` is widened to 3641 counts (10°) in `ethercat-conf.xml`. Put it back to 182 when A is reconnected. Read a drive's last error with `ethercat upload -p 3 -t uint16 0x603F 0` |
| Machine turns off right after enable | Software E-stop open (slave 3 DI1), a drive fault, or a VFD fault code of 64/92 |
| Drive fault Er47.0 | Following error over 0.5 mm for 250 ms. Tune, or check for binding. See [CONFIG_TOUR.md](CONFIG_TOUR.md#following-error) |
| Drive tuning lost on every restart | Gain SDOs in `ethercat-conf.xml`. Remove them |
| Can't jog Z before homing | The saved position (`position.txt`) is outside the soft limits |
| A 100 mm move never reaches full speed | Stock 2.9 planner gives only half acceleration under `G64`. Test with `G61` |
| Need to re-home before jogging after a job | Known open issue: after `M30` the machine stays in AUTO with jog stuck. Switch to Manual |

## Homing and switches

| Symptom | Cause / fix |
|---------|-------------|
| No drive input responds | A CN1 cable is unplugged. Really: check it |
| Axis homes the wrong way | Home input polarity (an inverter on a normally-open sensor), not the velocity sign |
| Y "homes" without moving | The shared Y/Z home switch was already closed. HAL's ignore-until-open logic handles this. Don't add `HOME_IS_SHARED` |
| Y runs away on REF ALL | `HOME_ABSOLUTE_ENCODER = 1`. Never use it here |
| Tool setter only works after pressing Z home | It's on a different input than HAL expects. Trip each sensor and watch `halcmd` |

## Probing and tool changes

| Symptom | Cause / fix |
|---------|-------------|
| Probe never trips | Wrong tool loaded for the routing: T99 listens to the touch probe, anything else to the setter. Check `halui.tool.number` |
| Probe input stuck on | An unplugged NC probe floats high |
| PROBE SPINDLE NOSE crashes Z | The touch probe was loaded. The macro now refuses to run in that state |
| M600 never probes | Setter position (`#5181–#5183`) or spindle zero (`#3010`) not taught |
| "Spindle zero not configured" and every probe/laser setting reads 0 | `linuxcnc.var` got zeroed (seen after an unclean shutdown). Close LinuxCNC first (it rewrites the file on exit), then restore it from git: `git log -- linuxcnc.var` to find a good commit, `git show <commit>:linuxcnc.var > linuxcnc.var`. Check `git diff linuxcnc.var` before committing it |
| M600 doesn't stop at the setter | Correct: it stops at the tool-load spot (G53 X270 Y100), then moves to the setter |
| M600 runs but never shows the dialog | The same tool is already loaded with a known length. That's the skip, working as intended |
| Work Z jumps after Stop | Something issued `G49`. This config keeps `G43` on Stop. See [TOOL_CHANGE.md](TOOL_CHANGE.md#keep-g43-on-stop) |
| Pocket probe moves dangerously fast | `[3017]` vs `[#3017]` typo in a Probe Basic macro. Fixed here; re-check after upgrading |
| "Probe tripped during non-probe move" | Laser mux left on. MDI `M63 P0` |

## Spindle and coolant

| Symptom | Cause / fix |
|---------|-------------|
| VFD or injector doesn't answer at all | A/B swapped, a wire on GND instead of A/B, or the wrong adapter. See [MODBUS.md](MODBUS.md#bench-testing) |
| Spindle and coolant swapped after a reboot | `SERIAL_PORT` uses `/dev/ttyUSBn`. Use `/dev/serial/by-id/` |
| Spindle runs backwards | M3/M4 swap in `custom.hal` (look for `REVERT:`) |
| Program waits too long after M3 | The 5 s at-speed delay in `custom.hal` |
| RPM gauge in Probe Basic blank | `probe_basic_postgui.hal` must net `spindle-speed-in` |
| Coolant sprays for 5 s then stops | The coil isn't being rewritten. The Microject's watchdog turned it off |
| Injector never fires | Coil address 0 vs 1 (`FIRST_ELEMENT`), 24 V missing, or the injector is on a different port |

## UI and pendant

| Symptom | Cause / fix |
|---------|-------------|
| Pendant wheel does nothing after starting the spindle from the screen | MDI mode took over. Tap Manual on the pendant. The feed knob must not be on Off or Lead |
| Pendant won't jog Z | Homing gate. `xhc-whb04b-6.hal` ties the pendant's "is homed" inputs to machine-on |
| Plots flat or NaN in a custom tab | `hal.get_value` only works on the thread that created the component, and returns NaN for some pins. Read raw `lcec` pins instead |
| Clipboard copy empty on the tuning tab | X11/Wayland quirk. Retry, or screenshot |

## One-click tune refuses to start: "realtime capture (sampler.0) not loaded"

Engine v2 needs the REALTIME CAPTURE block at the end of `custom.hal`. Check
`halcmd show pin sampler.0.enable`. If the block is there but the pin isn't,
LinuxCNC was not restarted after the HAL change. `--allow-python-sampler` runs
the old poller, but its FFT frequencies are wrong (it ran at 250–750 Hz).

## One-click tune stops: "did not settle after re-enable"

After the machine OFF→ON that each gain write needs, the axis moved more than
0.02 mm. On Z this is probably sag with the drive disabled. Park Z low or on a
support, or run `scripts/test_live_gain_write.py --axis Z`; if it passes, tune
with `--live-writes` so the drive never disables.

### Servo tuning: "sampler.0 is already capturing"

`sampler.0` has one FIFO, so only one reader works at a time. START PLOT on
the Servo Tuning tab holds it; one-click stops the stream before it starts
and restarts it after. If nothing is running (a crashed session left it on):
`halcmd setp sampler.0.enable 0`.
