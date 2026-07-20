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
2. Sweep sideways to find the **left and right edges** of the tool.
3. Report how wide that shadow was, then optionally correct it with a
   **master-pin beam-width calibration**.

It has its **own** HAL signal (`laser-beam-broken`). During measure macros,
**M62 P0** routes it onto `motion.probe-input` for continuous **G38** moves only;
**M63 P0** restores the contact probe / toolsetter mux so the two systems
don't fight when you're not measuring.

> Contact toolsetter = “how long is this tool?”  
> Laser setter = “how wide is this tool?” (raw, or corrected after beam-width cal)

---

## What works today

| Feature | Status |
|---------|--------|
| Live beam LED on the tab | Works (keeps updating during measure) |
| **MEASURE DIAMETER** | Works |
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
- Macro tip-finds at **BEAM**, then feeds **−X** from START through the beam

| Label | Meaning |
|-------|---------|
| **BEAM** | Where you CAPTURE — tool blocking the light; tip-find XY |
| **START** | Clear approach = `BEAM X + START OFFSET` (default +15 mm) |
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
   - **PROBE RPM** — `0` = no spin; `>0` = reverse (**M3**) during the diameter pass  
5. Press **MEASURE DIAMETER**.  
6. Watch the footer status. On success, **DIAMETER** updates.

**Rule of thumb:** `START OFFSET` must be **less than** `MAX TRAVEL`.

### What the macro does (plain English)

1. **`G0 G53`** to machine Z0 (safe height), then to **BEAM XY**.  
2. Optional coarse **`G1 G53`** approach when BEAM Z is taught.  
3. **M62 P0** → **G38** tip-find → **M63 P0** (mux on only during the probe).  
4. Back off / fine tip-find the same way (M62 ↔ G38 ↔ M63).  
5. Retract ~5 mm above tip, **`G0 G53`** to **START**, drop to tip − Z DROP.  
6. Pre-touch **G38 −X**, back off +2 mm, optional **M3**, then break→clear **G38**.  
7. Corrected diameter = raw shadow + `#5516` beam width; retract to Z0, **M5**, **M63 P0**.

LinuxCNC only allows **G53 with G0 or G1** — never with G38. Probes use **G91**
relative moves toward a machine-coordinate target, then **G90**.

If anything fails (never sees the beam, still in the beam at START, hits MAX TRAVEL
without clearing, etc.), it **retracts to Z0**, stops the spindle, restores **M63 P0**,
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
                      └── when M62 P0: and2.7 → or2.3 → motion.probe-input
contact probe / toolsetter → or2.0 → and2.8 (gated off when M62 P0) → or2.3
```

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
**M66 P3** / `#5399` is still used for beam-at-START safety checks.

Results publish with `M68 E0` (corrected diameter or length) and `M68 E1` (1 = success).
`#5512` always stores the **raw** shadow width.

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
| `ethercat_mill.hal` | `laser-beam-broken` + M62/M63 probe mux |

---

## Parameters (reference)

Laser uses **`#5501+`** on purpose so it never overwrites G30 / contact setter
teach (`#5181–#5186`) or ATC `M66` (`#5399`).

| # | Name | Meaning |
|---|------|---------|
| `#5501` / `#5502` | BEAM X/Y | Tool blocking light (G53 mm) — **CAPTURE BEAM** writes these + `linuxcnc.var` |
| `#5503` | PROBE RPM | 0 = static; else **M3** on diameter pass (`custom.hal` swaps to VFD reverse) |
| `#5504` | BEAM Z | Length only (MDI teach) |
| `#5507` | Z DROP | Below tip for side sweep |
| `#5508` | MAX TRAVEL | Max −X from START |
| `#5509` | START OFFSET | BEAM → clear START (+X) |
| `#5512` | Raw diameter | Last **raw** shadow width |
| `#5515` | Success | 1 = OK (`M68 E1`) |
| `#5516` | Beam width | `master − raw` offset; corrected = raw + `#5516` |
| `#5517` | Master pin | Last master-pin size used for cal |

UI always syncs **millimeters** into these params, even if the Units combo shows inches.

`linuxcnc.var` parameter numbers must stay **strictly ascending**. The Laser Setter
tab rewrites the file sorted when it saves `#5516` / `#5517`.

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
| “Beam already broken at START” | START OFFSET too small — increase it so START is clear |
| Never trips before MAX TRAVEL | Raise MAX TRAVEL (still short of the wall) or fix START OFFSET / polarity |
| Never clears / oversize abort | Tool bigger than the travel window, or stop too short |
| Footer FAILED, old diameter gone | That’s correct — success is gated on `M68 E1` |
| Contact probe acting weird | MDI **M63 P0** if a laser measure aborted; then check contact mux / tool number |

---

## Roadmap

1. ~~HAL + LED + diameter~~  
2. ~~G38 via M62 P0 mux; capture BEAM XY; START OFFSET / MAX TRAVEL (−X sweep)~~  
3. ~~Beam-width / master-pin calibration (true diameter)~~  
4. Optional measure axis (X vs Y)  
5. Runout / broken-tool check  
6. Length → real TLO vs gauge line  
7. Air blast DO / controllable Select  

PRs welcome — especially safer travel limits for other mill layouts.
