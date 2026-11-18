---
name: linuxcnc-hal-edits
description: >-
  Rules for editing HAL files in this LinuxCNC EtherCAT mill config
  (ethercat_mill.hal, custom.hal, coolant.hal, xhc-whb04b-6.hal,
  probe_basic_postgui.hal, probe_beep.hal). Use before adding or changing any
  loadrt, addf, net, setp, or when LinuxCNC startup fails with a twopass / HAL
  error.
---

# HAL edits on this mill

Each rule below was learned from a failed LinuxCNC launch. Check them all
before you call a HAL change done.

## 1. Find existing owners first

```bash
grep -n "<pin-or-signal>" *.hal probe_basic/*.hal
```

- A pin can be on **only one** net. A signal can have **only one** writer (OUT
  pin). Two nets on `and2.0.out`, or `qtpyvcp.probe-in.out`/`.io` added to a
  signal already driven by `not.6.out`, both abort the load.
- If a signal already exists, join it (`net existing-sig => new.pin`). Don't
  create a second net for the same source pin.
- `spindle.0.on`, `halui.program.is-idle` and others are already netted in
  `xhc-whb04b-6.hal`. Reuse those signals (e.g. `pdnt.spindle.is-on`).

## 2. Component loading

- **Never mix `count=` and `names=`** for the same component type across files
  (`loadrt_substitute: cannot mix count=, num_chan= and names=`). Shared pools
  (`not`, `and2`, `or2`, `mult2`, `conv_*`, `near`) are loaded **once** in
  `ethercat_mill.hal` with `count=`. To get more instances, bump that count and use
  the next free `.N`. Don't `loadrt` the same component again in another file.
- Every instance you use needs its `addf <inst> servo-thread`, and only **once**
  ("function may only be added to one thread").
- **`not.0` is reserved** for `probe_basic_postgui.hal` (cycle timer).
- Update the **HAL component inventory** table in `README.md` whenever you
  allocate instances. Check it before picking `.N`.
- `ilowpass`, `lowpass` and `limit1` are fine. Earlier "module failed to load" errors
  came from stale LinuxCNC processes. Kill them (`pkill -f 'linuxcnc|milltask|rtapi_app|halui'`)
  and relaunch before you blame a component.

## 3. Types and params

- `mux2` is **float-only**. For bit routing, use `and2`/`or2`/`not`.
- `constant` has only a float `.out`. To feed a bit pin, `setp` the bit input instead.
- `conv_s32_float` has no `scale`/`offset` params.
- `setp` works on **pins/params**, not signal names. To set a signal's value, setp
  the pin after the `net` line has created it.
- `motion.digital-out-NN` can't be setp'd from HAL (it defaults off).
- Extra `motion.digital-in-NN` need `num_dio=` on the `motmod` loadrt line (currently 5).
  Analog outs need `num_aio=` (currently 7).
- Use `halcmd gets <signal>` for signals and `getp` for pins.

## 4. Load order (TWOPASS = on)

`[HAL]` order: `ethercat_loadusr.hal` (`#NOTWOPASS`, `loadusr -W lcec_conf` exactly
once) → `ethercat_mill.hal` → `probe_beep.hal` → `xhc-whb04b-6.hal` → `custom.hal`
→ `coolant.hal`, then `POSTGUI_HALFILE`. A signal must already exist before a later file
references it by name. If `custom.hal` needs a signal the pendant creates, reorder
or create it earlier.

## 5. Machine-specific gotchas

- Each drive's DIs belong to that slave: `lcec.0.N.di-1..5` (no `di-6+`). Before
  remapping, confirm with a live watch of all 20 DI pins. Physical wiring has
  been wrong more than once (unplugged CN1 cable, shorted home bus, swapped probe
  and toolsetter).
- A6 inputs can be active-low depending on NPN/PNP wiring. Flip polarity with a
  `not` per input and say which one you flipped. Home sensors are NO, and the probe was NC
  and then NO. Don't blanket-invert everything ("make them all NO" broke
  enable once).
- Unplugged sensors **float HIGH**. That's why the NO touch probe goes through `not`
  (unplugged reads idle).
- The tpnext build needs `initf lcec.activate servo-thread` after the lcec addf lines.
- HAL and INI changes need a **full LinuxCNC restart**. `.ngc` changes don't
  (next `o<> call` re-reads them).

## Verify

After editing, launch (`./launch.sh` or `./launch-tpnext.sh`). If you can't launch,
at least grep for duplicate nets/addf and confirm the `count=` values cover every
`.N` you use. Report the first real error line from the startup log, not the cascade
after it (`servo-thread not found` in postgui usually means something earlier failed).
