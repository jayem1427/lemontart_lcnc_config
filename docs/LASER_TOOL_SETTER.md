# Laser tool setter (Kexin DS-5V-M)

Measure tool **diameter** (and optionally experiment with length) using a cheap
U-slot laser beam sensor — without messing up your contact toolsetter.

**See also:** [TOOLSETTER.md](TOOLSETTER.md) (contact M600 length) ·
[PROBE_BASIC_UI.md](PROBE_BASIC_UI.md) · [README](../README.md)

---

## ELI5: what is this?

Imagine a tiny doorway with a laser tripwire across it. When a tool sticks into
the doorway and blocks the light, the sensor says “broken.” When the tool moves
out of the way, it says “clear.”

This mill uses that tripwire to:

1. Find the **tip** (lower until the beam breaks).
2. From each side, trip the beam **9 times** on a spinning tool and keep the
   **outermost** flute tips (max-of-N first-tooth triggers).
3. Report that width, then optionally correct it with a
   **master-pin beam-width calibration**.

It has its **own** HAL signal (`laser-beam-broken`). During measure macros,
**M62 P0** routes **raw** beam onto `motion.probe-input` for continuous **G38**
moves only; **M63 P0** restores the contact probe / toolsetter mux so the two
systems don't fight when you're not measuring.

> Contact toolsetter = “how long is this tool?”  
> Laser setter = “how wide is this tool?” (raw, or corrected after beam-width cal)

---

## What works today

| Feature | Status |
|---------|--------|
| Live beam LED on the tab | Works (keeps updating during measure) |
| **+X / −X hit dots** | Works — 9+9 red→green from accepted `G38.3` trips (`M68 E2/E3`) |
| **Hit CSV** | Works — `logs/laser_hits/<stamp>_diameter.csv` after MEASURE |
| **MEASURE DIAMETER** | Works — G38, 9+9 max first-tooth triggers |
| **20× stats** | Works — MDI `o<laser_diameter_stats> call` (avg + sample stdev) |
| **CALIBRATE BEAM** / editable **MEASURED BEAM WIDTH** | Works — master pin − raw → `#5516` |
| **MEASURE LENGTH** | Experimental (needs `#5504` BEAM Z via MDI; not a contact TLO replacement) |
| Runout / broken-tool / air blast | Not built yet (roadmap only — no fake buttons) |

---

## Your machine layout (important)

On this mill the setter sits **lengthwise along Y**. The laser beam crosses the
slot in **X**.

So for diameter:

- **Y** ≈ center of the slot  
- **BEAM X/Y** = eyeball position with the tool **blocking** the light (LED broken)  
- **START** = `BEAM + START OFFSET` (+X, clear side away from the toolsetter)  
- Macro tip-finds at **BEAM**, then **9× G38.3** from +X clear; **probe-feeds** through
  the tool (break→clear + 1 mm) before **9× G38.3** from the −X clear — never **G0**
  through the beam toward the far wall

| Label | Meaning |
|-------|---------|
| **BEAM** | Where you CAPTURE — tool blocking the light; tip-find XY |
| **START** | +X clear approach = `BEAM X + START OFFSET` (default +15 mm) |
| **MAX TRAVEL** | How far from START toward **−X** you’re willing to search — **stop before the far wall / toolsetter** |

---

## Measure diameter (happy path)

You need: machine on, homed enough to move, a cutter in the spindle, LinuxCNC
restarted after any HAL/tab change.

1. Jog **Y** to the middle of the U-slot.  
2. Jog **X** so the tool is **in the beam** (LED shows broken).  
   Eyeball center is fine — this is BEAM XY.  
3. Press **CAPTURE BEAM (TOOL BLOCKING LIGHT)**.  
4. Set:
   - **START OFFSET** — +X from BEAM to clear START (default `15`)
   - **MAX TRAVEL** — max −X from START through the beam; stay short of the far wall / toolsetter (default `30`)
   - **Z DROP** — how far below the tip to sit for the side sweep (default `2`)
   - **PROBE RPM** — `0` = static (pins); `>0` = reverse (**M3**) during diameter hits (~200–1500 for flutes; if raising RPM shrinks the reading, go slower)  
5. Press **MEASURE DIAMETER**.  
6. Watch **+X HITS / −X HITS** dots go red→green. On success, **DIAMETER** updates.

**Rule of thumb:** `START OFFSET` must be **less than** `MAX TRAVEL` (ideally `MAX TRAVEL ≥ 2 × START OFFSET` so −X clear fits).

### What the macro does (plain English)

1. **`G0 G53`** to machine Z0 (safe height), then to **BEAM XY**.  
2. Optional coarse **`G1 G53`** approach when BEAM Z is taught.  
3. **M62 P0** → **G38** tip-find → **M63 P0** (mux on only during the probe).  
4. Back off / fine tip-find the same way (M62 ↔ G38 ↔ M63).  
5. Retract ~5 mm above tip, **`G0 G53`** to **START**, drop to tip − Z DROP.  
6. Pre-touch **G38 −X**, back off, optional **M3**.  
7. **9×** `G38.3 −X` from +X clear — keep **max X** (outermost +X flute tip).  
   Miss before **MAX TRAVEL** (`x_stop`) → fail.  
8. Probe transit: `G38.3 −X` entrance → `G38.5 −X` exit → **G1 −1 mm**
   = backside start (same break/clear/overshoot as before).  
9. **9×** `G38.3 +X` from that −X clear toward the **forward (+X) break** (`#5513`) — keep **min X**.  
   Miss before that known +X tip → fail (do not run out to START / +X clear).  
10. `raw = x_plus − x_minus`; corrected = raw + `#5516`; retract to Z0, **M5**, **M63 P0**.

LinuxCNC only allows **G53 with G0 or G1** — never with G38. Probes use **G91**
relative moves toward a machine-coordinate target, then **G90**.

If anything fails (never sees the beam, still in the beam at a clear start, hits MAX TRAVEL
without a +X-side tip trip, reaches the known forward (+X) break without a −X-side tip trip,
etc.), it **retracts to Z0**, stops the spindle, restores **M63 P0**,
and the footer says it failed. It will **not** pretend the last good diameter is
still valid.

Progress chatter is silent; only **failure** `(DEBUG, …)` lines notify in Probe Basic.

---

## Beam-width calibration

1. Enter the known **MASTER PIN** diameter.  
2. **MEASURE DIAMETER** on that pin (raw shadow width).  
3. Press **CALIBRATE BEAM** — or type a value into **MEASURED BEAM WIDTH** by hand.

**MEASURED BEAM WIDTH** = `master pin − last raw diameter` (stored in `#5516`).  
Later diameter results are `raw + #5516`, so the master reads back as the master size.
You can fine-tune the field anytime; leaving it (or measuring again) persists `#5516`
into `linuxcnc.var` in **ascending parameter order** (required by LinuxCNC).

## Optional: length experiments

**MEASURE LENGTH** — seeks down onto the beam at captured **BEAM XY** and reports
`beam_z − tip_z` (needs `#5504` taught via MDI `#5504=<G53 Z>`). Useful for polarity /
smoke tests. **Not** a spindle-nose TLO replacement — keep using the contact setter
+ M600 for real tool lengths.

---

## Hardware / wiring (this mill)

| Item | Note |
|------|------|
| Sensor | Kexin **DS-5V-M** |
| Spec tool range | Ø 0.05–8 mm (bigger tools may still trip; MAX TRAVEL limits the sweep) |
| Power | **5 V** only — never feed 24 V into the sensor |
| Select | Tie to **GND** (0 V = ON) |
| Signal | Slave **2** `lcec.0.2.di-5` — DB15 **pin 11**, level-shift 5 V → 24 V |

### HAL picture

Defined in `ethercat_mill.hal`:

```
lcec.0.2.di-5 → laser-beam-broken → motion.digital-in-03 (LED / M66 P3 RAW)
                      │
                      └── laser-flute-hold → and2.7 → G38 mux when M62 P0
                                         → motion.digital-in-04 (M66 P4 FILT)
contact probe / toolsetter → or2.0 → and2.8 (gated off when M62 P0) → or2.3
```

G38 uses the **flute envelope** (`on-delay=0`, `off-delay=BEAM_OFF_DELAY`) so
`G38.5` can clear through gullets. First-tooth `G38.3` still trips immediately.
LED / `M66 P3` stay **raw**. Macros wait **FILT** (`M66 P4`) clear before each
hit so G38 starts from a falling envelope — real travel + beep.

**+X / −X HITS** dots (RESULTS) are the live progress display: red until that
slot’s `G38.3` is accepted, then green. After MEASURE, a CSV of every hit X is
written to `logs/laser_hits/<timestamp>_diameter.csv`. Each accepted hit dwells
`G4 P0.20` so the last −X slot is not skipped by the UI poll.

Measure macros: **M62 P0** only around each **G38** (never during G0/G1),
**M63 P0** immediately after each probe and on every exit — otherwise LinuxCNC
aborts with *Probe tripped during non-probe move* when the beam breaks mid-rapid.
`on_abort.ngc` also issues **M63 P0**.

Exact tree to inspect while LinuxCNC is running:

```bash
halcmd show pin lcec.0.2.di-5
halcmd show sig laser-beam-broken
halcmd getp motion.digital-in-03
halcmd gets laser-beam-broken
```

```
lcec.0.2.di-5          (pin — Slave 2 DI5 / DB15 pin 11)
        │
        ▼
 laser-beam-broken   (signal; TRUE = tool blocking beam)
        │
        ▼
 motion.digital-in-03  (live G-code reads via M66 P3)
```

This mill’s level shift is **TRUE when broken** — no invert. If the LED is
backwards (on when clear / off when blocked), insert a `not` between DI5 and
`laser-beam-broken`.

**Do not** use `#<_hal[laser-beam-broken]>` in the measure loops — that value is
frozen at program start. G38 uses `motion.probe-input` while **M62 P0** is on;
**M66 P3** / `#5399` is still used for clear-start safety checks.

Results publish with `M68 E0` (corrected diameter or length) and `M68 E1` (1 = success).
`#5512` stores **raw** = `x_plus − x_minus`; `#5513`/`#5514` are the kept outer edges.
Each accepted (or final-failed) tip hit also publishes `M68 E2` (X mm) and `M68 E3`
(packed: `seq*10000 + side*100 + slot*10 + ok`, side 1 = +X, 2 = −X).

---

## Files involved

| Path | Role |
|------|------|
| `probe_basic/user_tabs/laser_setter/` | Tab UI + tool-setter photo |
| `laser_diameter.ngc` | Diameter sequence |
| `laser_diameter_stats.ngc` | 20× diameter, mean + sample stdev (`o<laser_diameter_stats> call`) |
| `laser_rpm_sweep.ngc` | Diameter at RPM 0 / 500 / 1000 / 2000 / 4000 / 6000 |
| `laser_zdrop_sweep.ngc` | Diameter at Z DROP 1 / 2 / 3 / 4 / 6 mm |
| `laser_length.ngc` | Length experiment |
| `laser_set_start_xy.ngc` | BEAM X/Y + RPM → `#5501–#5503` (UI usually writes params directly) |
| `laser_set_diam_params.ngc` | Z DROP / MAX TRAVEL / START OFFSET |
| `laser_set_beam_z.ngc` | BEAM Z for length |
| `ethercat_mill.hal` | `laser-beam-broken` → FILT → G38 mux; RAW on `digital-in-03`; FILT on `digital-in-04` |
| `custom.hal` | Loads `timedelay` as `laser-flute-hold` + spindle at-speed delay |
| `ethercat_mill.ini` `[LASER]` | `BEAM_OFF_DELAY` (G38 envelope off-delay) |
| `logs/laser_hits/` | Per-hit CSV from MEASURE DIAMETER (gitignored `*.csv`) |

---

## Parameters (reference)

Laser uses **`#5501+`** on purpose so it never overwrites G30 / contact setter
teach (`#5181–#5186`) or ATC `M66` (`#5399`).

| # | Name | Meaning |
|---|------|---------|
| `#5501` / `#5502` | BEAM X/Y | Tool blocking light (G53 mm) — **CAPTURE BEAM** writes these + `linuxcnc.var` |
| `#5503` | PROBE RPM | 0 = static; else spin during diameter hits |
| `#5504` | BEAM Z | Length only (MDI teach) |
| `#5507` | Z DROP | Below tip for side sweep |
| `#5508` | MAX TRAVEL | Max −X from START |
| `#5509` | START OFFSET | BEAM → clear START (+X); also mirrors −X clear |
| `#5512` | Raw diameter | `x_plus − x_minus` (max-of-9 each side) |
| `#5513` | x_plus | Outermost +X-side trigger |
| `#5514` | x_minus | Outermost −X-side trigger |
| `#5515` | Success | 1 = OK (`M68 E1`) |
| `#5516` | Beam width | `master − raw` offset; corrected = raw + `#5516` |
| `#5517` | Master pin | Last master-pin size used for cal |
| `#5518` | Reverse spindle | 1 = **M3** (VFD reverse); 0 = **M4** (forward); `custom.hal` swaps M3/M4 |
| `#5531–#5550` | Stats corr | 20 corrected diameters from `laser_diameter_stats` |
| `#5551–#5570` | Stats raw | Matching raw widths |
| `#5571` / `#5572` / `#5573` | Stats mean / sample stdev / n | MDI `o<laser_diameter_stats> call` |

UI always syncs **millimeters** into these params, even if the Units combo shows inches.

`linuxcnc.var` parameter numbers must stay **strictly ascending**. The Laser Setter
tab rewrites the file sorted when it saves `#5516` / `#5517` / `#5518`.

---

## Fluted tools and max-trigger diameter (notes for humans + AI)

### Current method (use this)

Diameter does **not** reconstruct a solid silhouette with a gullet envelope.
It measures **effective cutting diameter** by spinning the tool and taking
**first-tooth triggers** from both sides:

1. **9×** `G38.3 −X` from +X clear → keep **max X** (`#5513`); miss stop = `x_stop`  
2. Probe transit: `G38.3` entrance → `G38.5` exit → **G1 −1 mm** backside start  
3. **9×** `G38.3 +X` from that −X clear → keep **min X** (`#5514`); miss stop = `#5513` (forward break)  
4. `raw = x_plus − x_minus`; `corrected = raw + #5516`

G38 uses the **flute envelope** again (`on-delay=0`, `off-delay=BEAM_OFF_DELAY`) so
`G38.5` can clear through gullets. First-tooth `G38.3` still trips immediately.
Max-of-9 randomizes flute phase so the outermost tip is usually caught.

Recommended PROBE RPM for typical mill endmills: about **200–1500**. Pins: **RPM = 0**.
Fine hit feed is **F50** (≈0.0008 mm per 1 ms sample). If diameter **falls as RPM rises**, the flute pulse is already too short — slow down rather than spin faster. See **Why a thin flute reads small** below.

**Re-run CALIBRATE BEAM** on a master pin after switching to this method — old
`#5516` values included envelope clear-delay bias.

### Repeatability (20× stats)

From MDI (same BEAM / RPM / Z DROP as MEASURE DIAMETER):

```text
o<laser_diameter_stats> call
```

That calls `o<laser_diameter>` **20 times** (up to 3 retries per sample), then
prints mean and sample stdev. Each sample line also prints **tip_z** (`#5510`)
so you can see whether static tip-find is wandering separately from diameter.
Results stay in `#5531–#5573` (must stay below `#5600`). Hit dots will cycle
through all 20 runs if the Laser Setter tab is open — that is expected.

### What failed (do not resurrect)

| Approach | Why it failed |
|----------|----------------|
| Symmetric `debounce` (15–25 ms) | Averages duty cycle; both edges delayed; never recovers a true envelope |
| `oneshot` retriggerable + OR raw | Oneshot **expires during a long continuous block**; next gullet clears early |
| Break→clear `G38.5` without hold | First gullet looks like “left the tool” |
| Envelope `timedelay` + break→clear | Stops gullet aborts but left ~0.2 mm skinny silhouette vs mic OD |
| “Just spin faster” with silhouette method | Optical averaging undersizes further |

### Hit dots + per-hit CSV

RESULTS shows two rows of **9 dots** (+X / −X):

| State | Meaning |
|-------|---------|
| Red | Hit slot not yet accepted |
| Green | That `G38.3` trip succeeded (`#5070 != 0` and travel ≥ min) |
| Red with yellow ring | That slot exhausted retries / miss |

Reset all red when **MEASURE DIAMETER** starts. Dots are driven from **accepted
G38 trips** (`M68 E2/E3`), not from RAW waveform sampling.

After MEASURE, Laser Setter writes `logs/laser_hits/<stamp>_diameter.csv`:

```text
# raw=... corr=... beam=... tip_z=... rpm=... success=0|1
side,hit,x_mm,ok
plus,1,12.341,1
minus,1,6.012,1
```

Plot in a spreadsheet or script (hit index vs X, two series). Do **not** reuse
the HAL signal logger for this — wrong data shape.

### Accuracy notes

- Spinning laser OD may read **slightly larger** than a static micrometer (runout
  included) — that is closer to cutting radius than a mic on the flutes.  
- If still systematically skinny, check **Z DROP** on full OD and tip trigger
  threshold / beam cal — not feedrate.  
- Pin cal: `corrected = raw + (master − raw_pin)` → `#5516`.  
- Macro rejects raw `< 0.025 mm` or `x_plus ≤ x_minus`.

### Why a thin flute reads small — and how to get a real diameter

The thing that has to break the beam during MEASURE DIAMETER is the
**outermost metal of a flute** — the cutting edge — as it crosses the slot
sideways. Call that the **flute tip** if you want; it is a thin strip of
carbide, not a pin.

The sensor does not trip at the geometric sharp edge. It trips when enough
light has been blocked for long enough. A pin is a wide shadow. A flute tip
is a slit. A thinner object has to go **deeper** into the beam, or stay
there **longer**, before the bit flips. Higher RPM shortens the time the
flute tip is in the beam — same as making it optically smaller — so the trip
moves inward and the reading shrinks. A pin should not do that.

```text
t_ms ≈ 19100 × flute_tip_width_mm / (D_mm × RPM)
```

Need **t ≳ 2 ms** (sensor + 1 ms servo). Ø6 mm cutter, ~0.2 mm of metal at
the OD → stay under about **300 RPM**. If the number falls as you raise RPM,
you are already too fast.

#### How you actually get an accurate number

You do not make the flute thicker. You either give the sensor more time,
calibrate the leftover bias on **that cutter**, or stop asking this U-slot
for cutting-diameter metrology.

1. **Slow the spindle** until the RPM sweep is flat or peaked — typically
   **200–1500 RPM**, not several thousand. That is the main fix on this
   hardware. Max-of-9 still catches the outermost flute; the probe move at
   F50 is long enough to see many revolutions even at 300 RPM.
2. **CALIBRATE BEAM on a pin** — that only removes the *beam width* for a
   fat shadow. Keep it; it is not enough by itself for a fluted cutter.
3. **Mic the cutter, then laser it at the RPM you will use.**  
   `fudge = mic − laser_raw` (or vs already-corrected). If 20× stats are
   tight, that fudge is your accuracy for **that geometry**. A 2-flute and a
   4-flute will not share one fudge. Roadmap: optional per-tool optical
   fudge once this is proven.
4. **Shank at RPM = 0** if the shank is the same diameter as the cut
   (many endmills). That is a solid cylinder, like the pin. Then you have a
   real OD; the flutes may still cut a few hundredths larger because of
   runout.
5. **If a parked flute tip never breaks the LED** — this beam cannot see
   that cutting edge. Put **D** in the tool table from a micrometer. Use the
   laser for “is something still there,” not for size. A focused commercial
   laser setter is the hardware that measures skinny flutes at speed.

Repeatable ≠ accurate. `o<laser_diameter_stats> call` at one RPM: low stdev
and a mean off the mic means the fudge in step 3 will work. High stdev means
the flute tip is still barely tripping — slower RPM, or give up on size.

#### How to test

Capture BEAM XY first. Record **raw** (`#5512`); pin cal will not hide an
RPM slope.

1. **Parked flute-tip LED** — spindle off, ~2 mm below the end face. Rotate
   the collet so the **outside of a flute** sits in the slot, jog X into the
   beam. Pin: LED snaps broken. Flute tip: must go solidly broken, not
   flicker. If it never breaks, this sensor cannot size that cutter.
2. **Slow graze vs pin** — jog −X slowly across that parked flute, then the
   pin. If the flute needs more inward travel before the LED flips, it is
   already too thin at RPM=0; spinning makes it worse.
3. **Beep / halscope** — graze a flute in the beam, spin 200 → 6000 RPM.
   Clicks on `laser-beam-broken` should not vanish. Tab LED is too slow
   (200 ms poll).
4. **Pin** `o<laser_rpm_sweep> call` — should stay **flat**.
5. **Cutter** same sweep — falling curve = flute tip too brief at OD; keep
   the peak, not 6000 RPM.
6. **`o<laser_zdrop_sweep> call`** — confirm you are on the flute OD, not
   the end-face teeth. Keep Z DROP on the plateau.
7. **Stats + mic** at the RPM you keep — that is the accuracy loop.

### Related drive note

### Related drive note

`ethercat-conf.xml` sets **C01.10 = 3** (speed observer) on all A6 axes via
`0x2001:0x11` — unrelated to laser optics, but part of the same bench session.

---

## Troubleshooting

| What you see | Try this |
|--------------|----------|
| LED never changes | `halcmd gets laser-beam-broken` and `halcmd getp lcec.0.2.di-5`; Select tied to GND? 5 V power? |
| LED frozen mid-measure | Restart Probe Basic so the tab’s non-blocking MDI wait is loaded |
| Tip-find never trips / never stops | Restart after HAL change; measure needs **M62 P0** + G38 on `motion.probe-input` (not `#<_hal[]>`) |
| Tip-find never trips | BEAM XY wrong, or polarity (DI invert) |
| *Probe tripped during non-probe move* | M62 left on during G0/G1 — macros should wrap each G38 only; MDI **M63 P0** to clear |
| *Parameter file out of order* | `#5516`–`#5518` must sit before `#5519` — open Laser Setter once (it rewrites sorted) or sort `linuxcnc.var` |
| “Beam already broken at START” but clear | Polarity inverted — DI should be TRUE when broken |
| “Beam already broken at START” / −X clear | START OFFSET too small — increase it so both clears are open |
| Never trips before MAX TRAVEL | Raise MAX TRAVEL (still short of the wall) or fix START OFFSET / polarity / RPM |
| −X clear still broken | Need `MAX TRAVEL ≥ ~2× START OFFSET`, or raise START OFFSET |
| −X-side hit missed before forward (+X) break | No tip between −X clear and `#5513` — polarity / RPM / tool not in path; reverse no longer searches past the known +X tip |
| *forward break not beyond -X clear* / *transit never reached -X clear* | Stale FILT after last +X hit — macro now waits FILT/RAW clear and retries transit; restart LinuxCNC so that NGC is loaded |
| Raw width &lt; 0.025 mm / edge order bad | Tip never seen — check polarity, spin RPM; inspect hit CSV / dots |
| Fluted OD still off after recal | Slow RPM until the sweep is flat; then mic that cutter and fudge — pin cal is not enough |
| Diameter shrinks as PROBE RPM rises | Flute tip too brief in the beam — `o<laser_rpm_sweep> call`; slow down |
| Pin OD flat vs RPM, cutter is not | Thin flute tip × time — keep the RPM plateau, then mic-fudge |
| Parked flute never breaks LED | This beam cannot see that cutting edge — mic D, do not laser-size it |
| Diameter grows with Z DROP then plateaus | Side hits were on the end-face teeth — keep Z DROP on the plateau |
| Last −X hit dot stays red | Restart Probe Basic so the tab’s hit-event poll + post-hit `G4 P0.20` is loaded |
| G38 does not follow FILT | Restart after HAL change — mux must be `laser-flute-hold.out` → `and2.7.in0` |
| Footer FAILED, old diameter gone | That’s correct — success is gated on `M68 E1` |
| Contact probe acting weird | MDI **M63 P0** if a laser measure aborted; then check contact mux / tool number |

---

## Roadmap

1. ~~HAL + LED + diameter~~  
2. ~~G38 via M62 P0 mux; capture BEAM XY; START OFFSET / MAX TRAVEL (−X sweep)~~  
3. ~~Beam-width / master-pin calibration (true diameter)~~  
4. ~~Flute envelope filter (`timedelay`)~~  
5. ~~Max-of-N first-tooth diameter (G38, 9+9 sides)~~  
6. ~~Hit feedback + per-hit CSV~~ — red→green 9+9 dots; `logs/laser_hits/`  
7. Optional measure axis (X vs Y)  
8. Runout / broken-tool check  
9. Length → real TLO vs gauge line  
10. Air blast DO / controllable Select  
11. Optional `G10` tool-table diameter once accuracy is proven  
12. Optional per-tool optical fudge if flutes stay systematically off  

PRs welcome — especially safer travel limits for other mill layouts.
