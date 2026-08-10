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
2. From each side, trip the beam **5 times** on a spinning tool and keep the
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
| **SCOPE** / **SAVE PNG** | Live plot; auto-captures each measure to `logs/laser_scope/` |
| **MEASURE DIAMETER** | Works — raw G38, 5+5 max first-tooth triggers |
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
- **MINUS START** = `BEAM − START OFFSET` (−X clear, clamped to MAX TRAVEL stop)  
- Macro tip-finds at **BEAM**, then **5× G38.3** from each side (keep outermost edges)

| Label | Meaning |
|-------|---------|
| **BEAM** | Where you CAPTURE — tool blocking the light; tip-find XY |
| **START** | +X clear approach = `BEAM X + START OFFSET` (default +15 mm) |
| **MINUS START** | −X clear = `BEAM X − START OFFSET` (clamped to travel stop) |
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
   - **PROBE RPM** — `0` = static (pins); `>0` = reverse (**M3**) during diameter hits (~1000–6000 for flutes)  
5. Press **MEASURE DIAMETER**.  
6. Watch the footer status. On success, **DIAMETER** updates.

**Rule of thumb:** `START OFFSET` must be **less than** `MAX TRAVEL` (ideally `MAX TRAVEL ≥ 2 × START OFFSET` so −X clear fits).

### What the macro does (plain English)

1. **`G0 G53`** to machine Z0 (safe height), then to **BEAM XY**.  
2. Optional coarse **`G1 G53`** approach when BEAM Z is taught.  
3. **M62 P0** → **G38** tip-find → **M63 P0** (mux on only during the probe).  
4. Back off / fine tip-find the same way (M62 ↔ G38 ↔ M63).  
5. Retract ~5 mm above tip, **`G0 G53`** to **START**, drop to tip − Z DROP.  
6. Pre-touch **G38 −X**, back off, optional **M3**.  
7. **5×** `G38.3 −X` from +X clear — keep **max X** (outermost +X flute tip).  
8. **`G0`** to −X clear (mux off; may pass through beam).  
9. **5×** `G38.3 +X` from −X clear — keep **min X** (outermost −X flute tip).  
10. `raw = x_plus − x_minus`; corrected = raw + `#5516`; retract to Z0, **M5**, **M63 P0**.

LinuxCNC only allows **G53 with G0 or G1** — never with G38. Probes use **G91**
relative moves toward a machine-coordinate target, then **G90**.

If anything fails (never sees the beam, still in the beam at a clear start, hits MAX TRAVEL
without a tip trip, etc.), it **retracts to Z0**, stops the spindle, restores **M63 P0**,
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
lcec.0.2.di-5 → laser-beam-broken → motion.digital-in-03 (LED / M66)
                      │
                      ├── when M62 P0: and2.7 → or2.3 → motion.probe-input  (RAW)
                      └── laser-flute-hold (SCOPE "FILT" only — not on G38 path)
contact probe / toolsetter → or2.0 → and2.8 (gated off when M62 P0) → or2.3
```

G38 uses **raw** `laser-beam-broken`. Diameter is **max-of-5 first-tooth triggers**
from each side of the beam (no gullet envelope / timedelay on the probe path).
`laser-flute-hold` remains loaded so SCOPE can still show FILT for comparison.
LED / `M66 P3` stay **raw**.

Press **SCOPE** for a live plot, or just run **MEASURE DIAMETER** — capture starts
automatically for the whole macro. With **SAVE PNG** checked (default), a full-run
screenshot is written to `logs/laser_scope/<timestamp>_diameter.png`.

Traces:

1. **RAW** `lcec.0.2.di-5` — individual flute pulses  
2. **FILT** `laser-flute-hold.out` — legacy envelope (not used by G38)  
3. **G38** `motion.probe-input` — follows RAW while M62 is on  

With a spinning 3-flute in the beam, RAW and G38 should chatter. A solid pin should
keep RAW/G38 solid high while blocking.

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

---

## Files involved

| Path | Role |
|------|------|
| `probe_basic/user_tabs/laser_setter/` | Tab UI + tool-setter photo |
| `laser_diameter.ngc` | Diameter sequence |
| `laser_length.ngc` | Length experiment |
| `laser_set_start_xy.ngc` | BEAM X/Y + RPM → `#5501–#5503` (UI usually writes params directly) |
| `laser_set_diam_params.ngc` | Z DROP / MAX TRAVEL / START OFFSET |
| `laser_set_beam_z.ngc` | BEAM Z for length |
| `ethercat_mill.hal` | `laser-beam-broken` raw → G38 mux + M62/M63 |
| `custom.hal` | Loads `timedelay` as `laser-flute-hold` (SCOPE only) + spindle at-speed delay |
| `ethercat_mill.ini` `[LASER]` | `BEAM_OFF_DELAY` (SCOPE FILT only; unused by G38) |
| `logs/laser_scope/` | Auto PNG captures from MEASURE (gitignored `*.png`) |

---

## Parameters (reference)

Laser uses **`#5501+`** on purpose so it never overwrites G30 / contact setter
teach (`#5181–#5186`) or ATC `M66` (`#5399`).

| # | Name | Meaning |
|---|------|---------|
| `#5501` / `#5502` | BEAM X/Y | Tool blocking light (G53 mm) — **CAPTURE BEAM** writes these + `linuxcnc.var` |
| `#5503` | PROBE RPM | 0 = static; else **M3** during diameter hits (`custom.hal` swaps to VFD reverse) |
| `#5504` | BEAM Z | Length only (MDI teach) |
| `#5507` | Z DROP | Below tip for side sweep |
| `#5508` | MAX TRAVEL | Max −X from START |
| `#5509` | START OFFSET | BEAM → clear START (+X); also mirrors −X clear |
| `#5512` | Raw diameter | `x_plus − x_minus` (max-of-5 each side) |
| `#5513` | x_plus | Outermost +X-side trigger |
| `#5514` | x_minus | Outermost −X-side trigger |
| `#5515` | Success | 1 = OK (`M68 E1`) |
| `#5516` | Beam width | `master − raw` offset; corrected = raw + `#5516` |
| `#5517` | Master pin | Last master-pin size used for cal |

UI always syncs **millimeters** into these params, even if the Units combo shows inches.

`linuxcnc.var` parameter numbers must stay **strictly ascending**. The Laser Setter
tab rewrites the file sorted when it saves `#5516` / `#5517`.

---

## Fluted tools and max-trigger diameter (notes for humans + AI)

### Current method (use this)

Diameter does **not** reconstruct a solid silhouette with a gullet envelope.
It measures **effective cutting diameter** by spinning the tool and taking
**first-tooth triggers** from both sides:

1. **5×** `G38.3 −X` from +X clear → keep **max X** (`#5513`)  
2. **G0** to −X clear (mux off)  
3. **5×** `G38.3 +X` from −X clear → keep **min X** (`#5514`)  
4. `raw = x_plus − x_minus`; `corrected = raw + #5516`

G38 is wired to **raw** `laser-beam-broken` (1 kHz servo). No `G38.5` clear pass.
Max-of-5 randomizes flute phase so the outermost tip is usually caught.

Recommended PROBE RPM for flutes: about **1000–6000**. Pins: **RPM = 0**.
Fine hit feed is **F50** (≈0.0008 mm per 1 ms sample).

**Re-run CALIBRATE BEAM** on a master pin after switching to this method — old
`#5516` values included envelope clear-delay bias.

### What failed (do not resurrect)

| Approach | Why it failed |
|----------|----------------|
| Symmetric `debounce` (15–25 ms) | Averages duty cycle; both edges delayed; never recovers a true envelope |
| `oneshot` retriggerable + OR raw | Oneshot **expires during a long continuous block**; next gullet clears early |
| Break→clear `G38.5` without hold | First gullet looks like “left the tool” |
| Envelope `timedelay` + break→clear | Stops gullet aborts but left ~0.2 mm skinny silhouette vs mic OD |
| “Just spin faster” with silhouette method | Optical averaging undersizes further |

### Scope capture (debug)

Laser Setter tab:

- **SCOPE** — live pyqtgraph plot (UI-thread HAL sample, target **1000 Hz**)  
- **SAVE PNG** (default on) — full macro to `logs/laser_scope/<stamp>_diameter.png`

Traces: **RAW** / **FILT** (legacy, unused by G38) / **G38** (follows RAW).

Healthy fluted capture: RAW and G38 chatter on each approach; tip trips should
land near the geometric OD. X axis must be **0…T seconds** for the whole run.

### Accuracy notes

- Spinning laser OD may read **slightly larger** than a static micrometer (runout
  included) — that is closer to cutting radius than land OD.  
- If still systematically skinny, check **Z DROP** on full OD and tip trigger
  threshold / beam cal — not feedrate.  
- Pin cal: `corrected = raw + (master − raw_pin)` → `#5516`.  
- Macro rejects raw `< 0.025 mm` or `x_plus ≤ x_minus`.

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
| *Parameter file out of order* | `#5516`/`#5517` must sit before `#5519` — open Laser Setter once (it rewrites sorted) or sort `linuxcnc.var` |
| “Beam already broken at START” but clear | Polarity inverted — DI should be TRUE when broken |
| “Beam already broken at START” / −X clear | START OFFSET too small — increase it so both clears are open |
| Never trips before MAX TRAVEL | Raise MAX TRAVEL (still short of the wall) or fix START OFFSET / polarity / RPM |
| −X clear still broken | Need `MAX TRAVEL ≥ ~2× START OFFSET`, or raise START OFFSET |
| Raw width &lt; 0.025 mm / edge order bad | Tip never seen — check polarity, spin RPM, SCOPE PNG |
| Fluted OD still off after recal | Check Z DROP on full OD; expect runout ≥ mic land OD possible |
| SCOPE PNG only shows last ~2 s | Old bug; current code freezes sampling then renders **full** 0…T capture |
| Footer FAILED, old diameter gone | That’s correct — success is gated on `M68 E1` |
| Contact probe acting weird | MDI **M63 P0** if a laser measure aborted; then check contact mux / tool number |
| G38 does not follow RAW | Restart after HAL change — mux must be raw `and2.7.in0` |

---

## Roadmap

1. ~~HAL + LED + diameter~~  
2. ~~G38 via M62 P0 mux; capture BEAM XY; START OFFSET / MAX TRAVEL (−X sweep)~~  
3. ~~Beam-width / master-pin calibration (true diameter)~~  
4. ~~Flute envelope filter (`timedelay`) + SCOPE PNG capture~~ (superseded for G38)  
5. ~~Max-of-N first-tooth diameter (raw G38, 5+5 sides)~~  
6. Optional measure axis (X vs Y)  
7. Runout / broken-tool check  
8. Length → real TLO vs gauge line  
9. Air blast DO / controllable Select  
10. Optional `G10` tool-table diameter once accuracy is proven  
11. Optional per-tool optical fudge if flutes stay systematically off  

PRs welcome — especially safer travel limits for other mill layouts.
