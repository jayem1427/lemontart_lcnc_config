# Laser tool setter (tool diameter)

A Kexin **DS-5V-M** is a cheap U-shaped sensor with a laser beam across the
slot: it reports when something blocks the beam. This mill uses one to measure
**tool diameter**, with the tool spinning, so the result is the true cutting
diameter including runout. Tool **length** still comes from the contact
setter ([TOOL_CHANGE.md](TOOL_CHANGE.md)), because the slot only fits tools up
to about 8–9 mm.

Everything runs from the **Laser Setter** tab in Probe Basic.

---

## Measuring a diameter

You need: machine on and homed, a cutter in the spindle.

1. Jog **Y** so the tool is in the middle of the slot.
2. Jog **X** until the tool blocks the beam (the LED on the tab shows
   "broken"). Roughly centred is fine.
3. Press **CAPTURE BEAM (TOOL BLOCKING LIGHT)**.
4. Check the settings:

   | Setting | Default | Meaning |
   |---------|---------|---------|
   | START OFFSET | 15 mm | How far +X from the beam to start, clear of the tool |
   | MAX TRAVEL | 30 mm | How far −X it may travel searching. Keep it short of the slot wall and the contact setter |
   | Z DROP | 2 mm | How far below the tip to measure |
   | PROBE RPM | 0 | 0 = stationary (pins, gauges). For cutters use 1000–6000. Runs in reverse (`M3` on this machine) |

   Keep MAX TRAVEL at least twice START OFFSET so the far side has room.
5. Press **MEASURE DIAMETER**. The result shows on the tab when it's done.

**Calibrate once** with a gauge pin of known size: enter it as MASTER PIN,
measure it, then press **CALIBRATE BEAM**. This stores the beam-width
correction (`#5516 = master − raw`). Every later result is `raw + #5516`.
Recalibrate if you change how the measurement works.

For repeatability, run `o<laser_diameter_stats> call` from MDI. It measures 5
times and prints the mean and standard deviation.

---

## What the macro does

1. Rapids to `G53 Z0`, then to the captured beam XY.
2. Finds the tool tip: probes down (`G38`) until the beam breaks.
3. Moves to START (beam X + START OFFSET), drops to tip − Z DROP, starts the
   spindle if RPM > 0.
4. **+X side:** a quick `G38` toward −X finds roughly where the tool edge is.
   Then a **static hunt**: park X, wait up to 0.2 s for *any* flute to break
   the beam, step 0.02 mm inward and repeat. At the first break, back up and
   repeat in 0.001 mm steps. That station is the outermost flute tip.
5. Feeds through the tool to the −X side and repeats the same hunt from there.
6. `raw = x_plus − x_minus`, `diameter = raw + #5516`. Retracts, stops the
   spindle.

If anything goes wrong (never sees the beam, beam already broken at START,
runs out of travel), it retracts, stops the spindle, and reports a failure. It
never shows a stale diameter as if it were new.

### Why the static hunt

A moving `G38` stops wherever the axis happens to be when some flute breaks
the beam. With a spinning cutter that's a different spot every time, and a
short flute makes the tool read undersize. Parking X and waiting for any flute
means the first station that sees a break *is* the outermost tip, within the
0.001 mm step.

### What didn't work (don't bring these back)

| Approach | Why it failed |
|----------|---------------|
| Debouncing the beam signal (15–25 ms) | Averages the duty cycle; never recovers the true edge |
| Retriggerable oneshot | Expires during long blocks; the next gap clears early |
| Probe "break → clear" without a hold | The first gap between flutes looks like "left the tool" |
| Envelope filter + break → clear | Left the reading about 0.2 mm undersize |
| Spinning faster with the silhouette method | Optical averaging makes it read even smaller |
| Max of N moving `G38` hits | Never the same station twice; short flutes undersize |

---

## How it's wired

| Item | Value |
|------|-------|
| Sensor power | **5 V only** |
| Select wire | GND (= on) |
| Signal | Level-shifted 5 V → 24 V into slave 2 DI5 (`lcec.0.2.di-5`), TRUE when blocked |
| Mounting | Lengthwise along Y; beam crosses the slot in X |

In HAL (`ethercat_mill.hal`):

```
lcec.0.2.di-5 → laser-beam-broken ─┬→ motion.digital-in-03       (raw; LED and M66 P3)
                                   └→ laser-flute-hold ─┬→ motion.digital-in-04   (filtered; M66 P4)
                                                        └→ and2.7 → probe input, only while M62 P0 is on
```

- The laser only joins `motion.probe-input` between `M62 P0` and `M63 P0`,
  and the macros wrap **only** each `G38` in those. If it were on during a
  rapid, LinuxCNC would abort with "Probe tripped during non-probe move" when
  the beam broke. `on_abort.ngc` always issues `M63 P0`.
- `laser-flute-hold` is a `timedelay` (on 0, off `[LASER]BEAM_OFF_DELAY` =
  50 ms) so a `G38` that waits for "clear" isn't fooled by gaps between
  flutes. The static hunt reads the raw signal instead.
- Don't read the beam in G-code with `#<_hal[laser-beam-broken]>`: that value
  is frozen when the program starts. Use `M66 P3`.

If the LED is backwards (lit when clear), put a `not` between `lcec.0.2.di-5`
and `laser-beam-broken`.

---

## Parameters

The laser uses `#5501` and up, so it never collides with the contact setter
(`#5181–#5186`) or Probe Basic's ATC parameter (`#5399`).

| # | Meaning |
|---|---------|
| `#5501` / `#5502` | Beam X / Y (G53 mm), set by CAPTURE BEAM |
| `#5503` | Probe RPM |
| `#5504` | Beam Z (only for the length experiment) |
| `#5507` / `#5508` / `#5509` | Z DROP / MAX TRAVEL / START OFFSET |
| `#5512` | Raw diameter |
| `#5513` / `#5514` | +X and −X edge positions |
| `#5515` | 1 = last measurement succeeded |
| `#5516` | Beam-width correction |
| `#5517` | Master pin size |
| `#5518` | Spindle direction for measuring (1 = `M3`, which is reverse on this machine) |
| `#5531–#5573` | Results of the 5× stats run |

`linuxcnc.var` must stay sorted by parameter number, or LinuxCNC refuses to
start ("parameter file out of order"). The tab rewrites the file sorted when
it saves. If you edit it by hand, keep it sorted. Parameters must stay below
`#5600`.

Results reach the tab through analog outputs: `E0` = diameter, `E1` =
success, `E2`/`E3` = each parked sample (drives the +X / −X scan dots).

---

## The tab's extras

- **Scan dots.** Two rows of 9 dots, one per side. Red = not sampled yet,
  gray = parked and clear, green = a flute broke the beam there.
- **Hit log.** Every measurement writes `logs/laser_hits/<time>_diameter.csv`
  with each parked X and whether it saw a break. Plot X vs sample number to
  see the hunt.
- **MEASURE LENGTH** is experimental. It needs `#5504` taught by MDI and is
  not a replacement for the contact setter.

---

## Troubleshooting

| You see | Try |
|---------|-----|
| LED never changes | `halcmd getp lcec.0.2.di-5` while blocking the beam. Check 5 V power and Select to GND |
| "Beam already broken at START" (but it's clear) | Polarity is backwards; add a `not` |
| "Beam already broken at START" (really blocked) | START OFFSET too small |
| Never trips before MAX TRAVEL | Beam XY captured wrong, MAX TRAVEL too short, or polarity |
| Static hunt missed | Coarse pass stopped too far from the tip, or RPM too low for the 0.2 s wait. Check the hit CSV |
| "Probe tripped during non-probe move" | A measure was interrupted with `M62 P0` still on. MDI `M63 P0` |
| "Parameter file out of order" | Sort `linuxcnc.var`, or open the Laser Setter tab once (it rewrites it sorted) |
| Contact probe acting strangely | MDI `M63 P0` after an aborted laser measure, then check the tool number |
| Fluted tools still off after calibrating | Check Z DROP reaches full diameter. Spinning reads include runout, so slightly over a micrometer reading is expected |
| Scan dots stay red / tab frozen | Restart Probe Basic after updating the tab |

---

## Files

| File | Role |
|------|------|
| `probe_basic/user_tabs/laser_setter/` | The tab |
| `laser_diameter.ngc` | Measure sequence |
| `laser_static_edge.ngc` | Park-and-wait edge hunt |
| `laser_diameter_stats.ngc` | 5× repeatability |
| `laser_length.ngc` | Length experiment |
| `laser_set_*.ngc` | Save tab settings to parameters |
| `ethercat_mill.hal` | Beam input, filter, probe mux |
| `custom.hal` | Loads the `laser-flute-hold` timedelay |

**Ideas not built yet:** measuring along Y, runout and broken-tool checks,
writing diameter into the tool table, an air blast to clean the slot.
