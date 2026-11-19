# CAM: the Fusion 360 post

`post-processor/linuxcnc-djr.cps` is a fork of Autodesk's LinuxCNC post, set
up for this machine: `M600` tool changes, a 4th axis on the table along X, and
no tool length cancel between operations.

## Installing it

1. Copy `linuxcnc-djr.cps` into Fusion's **Posts** folder (Personal Posts).
2. Select it when posting. It needs a current Fusion (post engine 45702 or newer).

**Fusion caches posts.** If the post dialog still shows old options after you
update the file: remove the post from Personal Posts, restart Fusion, copy the
new file in, and select it again.

## Settings that matter

| Setting (post dialog) | Value | Why |
|-----------------------|-------|-----|
| **Tool change command** | `M600` (default) | Runs the park → dialog → measure cycle. See [TOOL_CHANGE.md](TOOL_CHANGE.md) |
| **Preload tool** | Off | On a manual mill, a bare `T<next>` only confuses things |
| **Fourth axis mounted along** | X | Enables A output. Set to None only if you want 3-axis output |
| **4th axis is a table** | On | Matches `trivkins coordinates=XYZA` |
| **G93 inverse time** | On | Used only for simultaneous moves that actually turn A |

### Tool change command options

| Option | Posts | Use when |
|--------|-------|----------|
| `M600` | `T3 M600` | Normal jobs. Every new cutter gets measured |
| `M6` | `T3 M6` | Lengths are already in the table. Dialog only, no move, no probe |
| T only | `T3` | You load and measure from Probe Basic before running the job |

M600 stops the spindle to measure. The post turns it back on (`M3`/`M4`) after
each tool change.

Don't end a program with `T0 M600`, and keep the touch probe (T99) out of CAM
tool lists. Load it from Probe Basic.

## 4th axis

- **Indexing** (rotate A, then cut 3-axis) stays in normal `G94` feed per
  minute.
- **Simultaneous** moves that interpolate A post `G93 G1 X… Y… Z… A… F…`
  (inverse time) and return to `G94` at the end of the section.
- The program header is `G90 G94 G17 G91.1`. Never start a program in `G93`:
  the M600 macro's feeds are in mm/min.
- **No `G49` between operations.** This machine is non-TCP, and a `G49` would
  drop tool length mid-program.
- The post uses tip mapping (`optimizeMachineAngles2(1)`), not TCP. Don't
  enable TCP in Fusion unless you also add TCP kinematics to LinuxCNC.

A Fusion **Machine Definition** on the setup overrides the post's built-in
A-axis settings.

Run the first program of any new kind as an air cut with feed override turned
down.
