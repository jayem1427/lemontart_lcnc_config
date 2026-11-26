# Vise stop: same WCS every part, no probing

A self-centering vise already locates the part in two of three directions:
- **Across the jaws** the part is always centered.
- **Z** is set by the parallels or jaw step it sits on.

The only loose direction is **along the jaws**. The **VISE STOP** tab handles
that by parking a tool in the spindle at a stored machine position, so you
slide the part against it, clamp, and run. You set the vise WCS once and never
touch it again for that vise mount, which makes op 2 flips trivial.

Files:
- Tab: `probe_basic/user_tabs/vise_stop/`
- Macros: `probe_basic/subroutines/vise_stop_go.ngc` and `vise_stop_retract.ngc`
- Settings: `#5580–#5587` in `linuxcnc.var`

## How the origin is worked out

The tab writes only the free axis of the vise WCS. It never touches the clamp
axis or Z.

```
part edge   = stop position + side x (pin diameter / 2)
EDGE mode   origin = part edge
CENTER mode origin = part edge + side x (part length / 2)
```

`side` is +1 when the part sits on the + side of the pin, and -1 when it sits on
the - side. The pin diameter comes from the tool table for the tool in the
spindle. The tab shows the result live under FREE-AXIS ORIGIN.

## Setup (once per vise mount)

1. Clamp any part in the vise. Probe its center across the jaws into the
   vise WCS (default **G55**, so G54 is left alone) with Probe Basic's normal
   boss/web probing.
2. Set the vise WCS **Z** where you want it. The parallel top or jaw step
   (= part bottom) means every op 2 has the same Z0. In CAM, put the op 2
   origin at the stock bottom.
3. On the tab, pick **ALONG THE JAWS** (X or Y), **PART SIDE OF STOP**, **VISE WCS**
   and **STOP Z**. STOP Z is the pin tip height in the vise WCS: low enough to
   touch the side of your thinnest part, and above the parallels.
4. Load the stop pin. Jog it to where the part's end should sit, then press
   **CAPTURE STOP**. Only the free-axis machine coordinate is stored. The
   clamp-axis position of the pin always comes from the vise WCS (the vise center).

## Every part

1. Load the stop pin with `M600`.
2. Press **GO TO STOP**. This writes the free-axis origin, then goes `G53 Z0` →
   stop XY → rapid to STOP Z + 25 → feed down at F600.
3. Slide the part against the pin **gently**, keep light pressure toward it,
   and clamp.
4. Press **RETRACT** (`G53 Z0`, Z only). Load your cutting tool and run in the vise WCS.

The macro refuses to move if:
- No tool is loaded, or T99 (the touch probe) is loaded.
- The tool has no diameter in the tool table.
- The stop hasn't been captured.
- The vise WCS clamp axis or Z is still zero.
- STOP Z would put the spindle above machine Z0.

## Getting good numbers

- **Use a ground dowel or gauge pin in a collet as the stop**, set up as its own
  tool number with its real diameter. A fluted endmill touches on its flute tips,
  you have to spin it by hand to find the high spot, and its real diameter is
  often tens of µm off nominal. If you do use an endmill, measure it on the
  laser setter first.
- **Push gently.** The axis is held by the servo. A hard shove deflects it a few
  µm, and 0.5 mm trips the drive's following error (Er47).
- **Keep the pin down until the part is clamped.** Both jaws move as you tighten,
  and that can drag the part off the stop.
- **The face that touches the pin must be a finished, deburred op 1 edge.**
- **Prefer EDGE mode.** In CENTER mode, half of any error in the part length goes
  straight into the position. In EDGE mode, length doesn't matter.
- **Power-ups:** the stop and vise center are stored in machine coordinates.
  Homing currently shifts 40–60 µm between power-ups (see the open thread in
  `CLAUDE.md`). If that matters for the part, re-probe the vise center once after
  each power-up.

## Settings (`#5580–#5587`)

| Param | Meaning |
|---|---|
| 5580 | Free axis along the jaws: 0 = X, 1 = Y |
| 5581 | Part side of the stop: +1 or -1 |
| 5582 | Stop position, machine coordinate on the free axis (spindle centerline) |
| 5583 | STOP Z: tool tip height in the vise WCS |
| 5584 | Origin mode: 0 = part edge, 1 = part center |
| 5585 | Part length along the jaws (CENTER mode only) |
| 5586 | Vise WCS: 1 = G54 … 6 = G59 |
| 5587 | Last free-axis origin written (machine coordinate) |

The tab pushes these to the interpreter by MDI and merges them into
`linuxcnc.var` (kept sorted) when you press CAPTURE STOP or GO TO STOP. Edits
you make without pressing either are written to the file, but LinuxCNC rewrites
the file from its own values on exit, so press GO TO STOP once before shutting
down if you want a changed setting to stick.

## Running it without the tab

Set the params by MDI, then call:

```
o<vise_stop_go> call
o<vise_stop_retract> call
```
