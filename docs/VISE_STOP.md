# Vise stop: same WCS every part, no probing

A self-centering vise already locates the part across the jaws (always on
center), and Z is set by the parallels the part sits on. The only loose
direction is **along the jaws**.

The **VISE STOP** tab fixes that with a tool in the spindle used as a hard
stop. The vise WCS is set once, at the **vise center**, and is never changed.
For each part, GO TO STOP parks the pin so that a part of the length you enter
ends up **centered on that WCS** when you push it against the pin. Clamp,
retract, run. Op 2 flips need no probing at all.

Files:
- Tab: `probe_basic/user_tabs/vise_stop/`
- Macros: `probe_basic/subroutines/vise_stop_go.ngc` and `vise_stop_retract.ngc`
- Settings: `#5580`, `#5581`, `#5585`, `#5586` (tab) and `#5583`, `#5587` (set and forget) in `linuxcnc.var`
- Pictures: `probe_basic/user_tabs/vise_stop/images/`, made by `tools/vise_render/`

## Where the pin goes

```
pin center (vise WCS) = -side x (part length / 2 + pin diameter / 2)   along the jaws
                        0                                               across the jaws
```

`side` is the side of the pin the part sits on. Pick it on the tab as **PIN SIDE
-X / +X** (or Y), or tap that side of the picture. The pin diameter comes from the
tool table for the tool in the spindle. The dark readout under the fields shows
where the pin will park in the vise WCS, for example `G55 X -33.000 / Y 0.000 /
Z -10.000`. If something is missing (no pin loaded, no diameter, pin too short)
the readout says so in amber instead.

**In CAM, put the op 2 origin at the part center in X and Y, and at the part
bottom (parallel top) in Z.**

## The picture

The right panel shows the H67 the way it sits on the table (jaws along X
or Y), with the part centered, the stop pin in the spindle on the chosen side,
and a red arrow for which way to push the part. Every picture uses the same
camera (just right of front, 45° down, +Y pointing up and leaning right, the way
the machine looks from the screen), so for jaws along Y the whole vise is simply
turned 90° and the +X / +Y indicator in the bottom-left corner points the same
way in all of them.

The picture's frame turns red if the touch probe is loaded or the tool has no
diameter. The picture is drawn with a 6 mm
pin and a fixed part size. The numbers are the real ones.

## Setup (once per vise mount)

1. Clamp any part in the vise. Probe its center in **both X and Y** into the
   vise WCS (default **G55**, so G54 is left alone) with Probe Basic's normal
   boss/pocket probing. Across the jaws, the self-centering vise puts every
   part on that line. Along the jaws, this is the point the part will be
   centered on.
2. Set the vise WCS **Z0 on the top of the jaws**.
3. On the tab, pick **JAW AXIS** (X or Y) so the picture matches the
   table, then **VISE WCS**.

The pin always parks its tip **10 mm below the vise Z0** (`#5583`), i.e. 10 mm
below the jaw tops: deep enough to catch a part clamped in the jaws, and the
same every time. The machine doesn't know where your parallels are, so keep
them lower than that. To change it, edit `#5583` in `linuxcnc.var` with
LinuxCNC closed.

**Spindle-nose check.** Tool lengths on this machine are measured from the
spindle nose (`#3010`, see TOOL_CHANGE.md), so the pin's tool length is its
stickout. With the tip 10 mm down, the nose sits (length − 10) above the jaw
tops, and that must be at least `#5587` (default 5 mm). So the stop pin needs
**at least 15 mm of stickout**, or the macro refuses. This doesn't know about a
part sticking up above the jaws: the collet nut overhangs the part end, so with
a tall part use a longer pin.

## Every part

1. Enter the **PART LENGTH** (along the jaws) and pick the pin side.
2. Load the stop pin with `M600`.
3. Press **GO TO STOP**: `G53 Z0` → vise WCS XY over the pin spot → `G53`
   rapid to 25 mm above the stop → `G53 G1` down at F600. All Z moves are in
   machine coordinates (vise Z0 + G92 − depth + tool length); the WCS is not
   changed.
4. Push the part against the pin **gently**, keep light pressure toward it,
   and clamp.
5. Press **RETRACT** (`G53 Z0`, Z only). Load your cutting tool and run in the
   vise WCS.

The macro refuses to move if any of these is true:
- No tool is loaded, or T99 (the touch probe) is loaded.
- The tool has no diameter in the tool table.
- The part length is 0.
- `#5583` (depth) or `#5587` (nose clearance) is 0 or less (not set).
- Tool length − depth is less than the nose clearance (pin too short).
- The vise WCS X, Y or Z is still zero (not probed).
- The stop would put the spindle above machine Z0.

## Getting good numbers

- **Use a ground dowel or gauge pin in a collet as the stop**, set up as its own
  tool number with its real diameter. A fluted endmill touches on its flute
  tips, and its real diameter is often tens of µm off nominal.
- **Part length matters:** half of any error in the length you enter shows up
  as position error. Measure the part, don't use the drawing size.
- **Push gently.** The axis is held by the servo. A hard shove deflects it a few
  µm, and 0.5 mm trips the drive's following error (Er47).
- **Keep the pin down until the part is clamped.** Both jaws move as you
  tighten, and that can drag the part off the stop.
- **The face that touches the pin must be a finished, deburred op 1 face.**
- **Power-ups:** the vise WCS is stored in machine coordinates. Homing
  currently shifts 40–60 µm between power-ups (see the open thread in
  `CLAUDE.md`). If that matters for the part, re-probe the vise center once
  after each power-up.

## Settings

| Param | Meaning |
|---|---|
| 5580 | Axis the jaws run along: 0 = X, 1 = Y |
| 5581 | Part side of the pin: +1 = part toward +, pin on the − side; −1 = the reverse |
| 5583 | Pin depth: tip parks this far below the vise WCS Z0 (mm, default 10). Not on the tab |
| 5585 | Part length along the jaws |
| 5586 | Vise WCS: 1 = G54 … 6 = G59 |
| 5587 | Spindle-nose clearance above the vise WCS Z0 (mm, default 5). Not on the tab |
| 5582, 5584 | Unused (left over from the first version) |

The tab pushes these to the interpreter by MDI and merges them into
`linuxcnc.var` (kept sorted) when you press GO TO STOP. Other edits are
written to the file too, but LinuxCNC rewrites the file from its own values on
exit, so press GO TO STOP once before shutting down if a changed setting must
stick.

## Running it without the tab

Set the params by MDI, then call:

```
o<vise_stop_go> call
o<vise_stop_retract> call
```

## Regenerating the pictures

`tools/vise_render/` is a small numpy renderer with Fusion-style black edge
lines (sharp mesh edges and silhouettes). It needs numpy, scipy and
Pillow. For a different vise, export the vise body and the jaws from Fusion:
right-click the component → **Save As Mesh** → STL (Binary), mm. The clamp
must run along the mesh's X and the jaws along its Y. Fusion writes each
component in its own coordinates, so `make_images.py` centers the jaws on the
vise and turns them right side up. Check that against your model. Then run:

```
cd tools/vise_render
python3 make_images.py vise.stl jaws.stl ../../probe_basic/user_tabs/vise_stop/images
```

Scene numbers (jaw face position, parallel height, part size, pin stickout)
are at the top of `make_images.py`.

## Layout

Two panels, styled like the rest of Probe Basic (grey gradient buttons, white
fields, green text on a selected toggle):

- **VISE STOP** (left): JAW AXIS, VISE WCS, PART LENGTH, PIN SIDE, the
  pin-position readout, then GO TO STOP and RETRACT. The line above the buttons
  shows the result of the last press, or a machine problem (E-stop, machine
  off, not homed). It is blank when there's nothing to say.
- **PIN POSITION** (right): the render. Tap a side of the vise to put the pin
  there.
