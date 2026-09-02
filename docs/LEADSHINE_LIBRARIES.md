# Leadshine libraries vs this mill (MC508CS)

Source of truth for interpolation/G-code FBs: **LeadSys Studio Command Manual 20250102** (Jan 2025). That PDF never names MC508CS, LeadSys 3.1, SP15, or `SMC_Interpolator`.

G-code FBs live in the **PMC600 chapter** and are implemented by **`PMC_IpoLib`**, not chapter 4 **`LS_IpoLib`**.

Architecture that consumes this: [CODESYS_ARCHITECTURE.md](CODESYS_ARCHITECTURE.md).

---

## What this means for Lemontart (XYZA mill)

| This mill today | Jan 2025 book |
|-----------------|---------------|
| Rotary **A** in G-code | `LS_4AxisGCode_File` is **X,Y,Z,U**. No A word. Sibling `LS_4AxisGCodeAxisP_File` is **X,Y,Z,P**. No rotary kinematics. |
| LinuxCNC G38 / probe skip | **No interpolator probe.** Latch FBs + Halt/Stop. |
| `G43` tool length | Not mentioned. 6-axis FB `dOffset*` is **zero-point**, not tool-length. |
| `G64` blending | FB params `LimitMaxAcc` / `LimitMaxAccJerk` (transition arcs), not a G-word. |
| `G93` inverse time | Not mentioned. Fusion post cannot assume it. |
| `M600` handshake | 4-axis file FB has **no** `wM` / `AcknM`. Those pins exist on `LS_6AxisGCodeAxisUVW_File` only. |
| Store SoftMotion CNC | **Not authorized.** Types `SMC_CNC_REF` / `SMC_VarList` are data shapes on Leadshine FBs. |
| S-curve / jerk | **On the G-code FB**, same family as `LS_nAxisLine` (`VelocityMode` 0/1/3 + `Jerk`). |

Do **not** treat MC508CS as a LinuxCNC replacement until two things are proven on the brick: **`PMC_IpoLib` ships with that SKU**, and mill **A** has a documented mapping to **U** or **P**.

---

## 1. `LS_4AxisGCode_File`: XYZ+A path, or 3-line + 1 follow?

**Neither A, nor the Line-FB follow model.**

`LS_4AxisGCode_File` is documented as four-axis continuous G-code interpolation on **X, Y, Z, U**. Pins are `AxisX` / `Y` / `Z` / `U`. There is **no A word**. Combined speed `Vel` is “current interpolation path speed,” not “first three axes only.”

That is a different contract from the Line FBs:

| FB | Library | Axis 4 |
|----|---------|--------|
| `LS_4AxisLineAbs` / `Rel` | `PMC_IpoLib` | **Follower.** First three: spatial line. Fourth: follow, start/stop together. `Vel` = first-three path speed. |
| `LS_5AxisLineAbs` | `PMC_IpoLib` | Axis0–2 interpolate; Axis3–4 跟随. |
| `LS_4AxisMoveSequence` | `LS_IpoLib` | Axis3 labeled 跟随轴，速度不连续 (follower, velocity not continuous). |
| `LS_4AxisLine` (ch. 4) | `LS_IpoLib` | All four called “participating in interpolation”; example is a 4-vector `EndPos`. Does not copy the 3+1 sentence. |
| **`LS_4AxisGCode_File`** | **`PMC_IpoLib`** | **X,Y,Z,U as G-code axes. No follow sentence.** |

If the fourth axis is a **rotary A**, this FB is the **wrong word**. Closest sibling is `LS_4AxisGCodeAxisP_File` (**X,Y,Z,P**). Still not A, and no rotary kinematics are described.

Practical read: a block with X/Y/Z/U is treated as a **4-axis G-code segment**, not `LS_4AxisLine`’s 3+1 follower. The book never writes “G1 X Y Z U is a 4-D linear interpolant,” but it also never calls U a follower, and it uses different speed wording than the Line FBs.

---

## 2. What G-words actually parse?

This manual has **no G-word catalog**. **G43, G38/G31, G64, G93 are not mentioned.**

What it does pin down on `LS_4AxisGCode_File`:

- **F**, plus acc/dec in the CNC file
- **G01** explicitly (`DefaultVelFF` / `DefaultAccFF` / `DefaultDecFF` = defaults when G01 F/acc/dec omitted)
- Split defaults (`DefaultVel` vs `DefaultVelFF`) imply a rapid vs G01 feed pair (almost certainly **G00 vs G01**)
- **H-codes** → `dwSwitches`
- Path blending is a **FB parameter**, not a G-word: `LimitMaxAcc` / `LimitMaxAccJerk` = max acc/jerk of 过渡圆弧 (transition/fillet arcs)
- `LS_4AxisGCode_File` has **no** `wM` / `AcknM`. Those exist only on `LS_6AxisGCodeAxisUVW_File`, which also exposes:
  - `AcknM` / `wM` — M-code handshake
  - `dOffsetX..W` — zero-point offsets (**not** G43 tool-length)
  - `SMC_VarList_0` typed `SMC_VarList`, described as **DIN 66025** system variables
  - in-memory G-code FBs take `POINTER TO SMC_CNC_REF`

Leadshine is wrapping a **DIN 66025 / SoftMotion CNC-shaped decoder** on the 6-axis file FB. That still does not document Fanuc **G43 / G31 / G38 / G64 / G93**. Treat those as unsupported until proven on the brick.

---

## 3. Path jerk / S-curve on the G-code FB?

**Yes, same profile family as `LS_nAxisLine`.**

`LS_4AxisGCode_File` has:

- `VelocityMode` `SMC_INT_VELMODE`: **0 TRAPEZOID, 1 SIGMOID, 3 QUADRATIC**
- **`Jerk`** — required and must be ≠ 0 when mode = 3
- plus `LimitMaxAcc` / `LimitMaxAccJerk` for the transition-arc look-ahead

Jerk is not line-only. G-code also has `VelRatio` (0.01–2) as feed override.

---

## 4. Probe: interpolator latch, or ST + fast DI + Halt?

**No interpolator probe.** G-code FBs have **Halt / Stop** only. No skip/probe input, no G38/G31.

Probe/latch in this book is **hardware, outside the interpolator**:

- `LS_HighSpeedLatch_*` (`PMC_Controller`)
- `LS_TouchProbe` (LC1000 high-speed I/O)
- `LS_ZeroLatch_*` (home-input position latch)
- EZ latch on the drive

Documented path: **ST + fast DI / high-speed latch + Halt/Stop**, not a G-code skip cycle.

---

## 5. CODESYS Store SoftMotion CNC vs `LS_IpoLib`?

This manual **never authorizes** Store SoftMotion CNC (`SMC_Interpolator`).

What it shows:

- Axes are `AXIS_REF_VIRTUAL_SM3`; limits cite “SoftMotion driver: general”
- Cam tappets come from **`SM3_Basic`**
- Interpolation/G-code FBs are Leadshine: **`LS_IpoLib`** (ch. 4 line/circle/sequence, **no G-code**) and **`PMC_IpoLib`** (PMC600 chapter, **all `LS_*GCode*`**)
- Types `SMC_CNC_REF` / `SMC_VarList` appear on Leadshine G-code FBs — SM CNC **data shapes**, not a license to run `SMC_Interpolator`

**`LS_IpoLib` ≠ G-code.** If the MC508CS project only has `LS_IpoLib`, this book’s G-code FBs are **not in that library**.

---

## 6. Does MC508CS show up in LeadSys 3.1? Is `LS_IpoLib` bundled?

**Not in this PDF.** Coverage line is “LC series and MC series” plus a **PMC600-only** chapter. No SKU list, no IDE version, no “bundled vs extra install.”

From library tags only:

- `LS_IpoLib`: generic interpolator (ch. 4)
- `PMC_IpoLib`: PMC600 interpolator **including G-code**
- G-code is filed as **PMC600 dedicated**, not as “all MC series”

If the question is “can this **MC508CS** brick run the G-code FBs from this book,” the manual’s filing says those FBs are **PMC600 / `PMC_IpoLib`**. Confirm in the LeadSys 3.1 device catalog and which libraries ship with the MC508CS package — **this instruction book will not settle that.**

---

## Still open after this PDF

- Does **MC508CS** get **`PMC_IpoLib`** at all, or only `LS_IpoLib` (line/circle, no G-code)?
- Mapping mill **A** → documented **U** or **P** (no rotary kinematics in the book).
- G43 / G31 / G38 / G64 / G93 on the brick (prove, don’t assume).
- LeadSys 3.1 device list: **MC508CS** present? Libraries bundled vs extra?
- M600: 4-axis file FB has no M handshake. Is the 6-axis UVW FB available on MC508CS, or does toolchange stay ST-owned?

## What to open in LeadSys 3.1 (not this PDF)

Install **LeadSys Studio V3.1** on Windows. Do not install Store CODESYS SP22 expecting a match (this brick is SP15-class). Do not wipe the LinuxCNC mill PC.

1. New project: **MC508CS** (or nearest MC SKU if 508 is missing).
2. Library Manager: is **`PMC_IpoLib`** present, or only **`LS_IpoLib`**?
3. F1 **`LS_4AxisGCode_File`**. Confirm pins `AxisX/Y/Z/U`, `VelocityMode`, `Jerk`, no probe input, no `wM`.
4. Compare F1 vs this page. If they diverge, trust the installed help for *that* package version and patch this doc.
