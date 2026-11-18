---
name: linuxcnc-ngc-macros
description: >-
  LinuxCNC RS274NGC / .ngc macro, remap and INI-G-code authoring rules for this
  mill config. Use when creating or editing .ngc subroutines (probe, toolsetter,
  laser, M600, metrology, tuning programs), REMAP lines, RS274NGC_STARTUP_CODE,
  or when LinuxCNC reports Nested comment found, Bad character, P word with no…,
  duplicate O-word, Parameter file out of order, or garbage characters in a file.
---

# LinuxCNC NGC macros and remaps

## Text hygiene (hard failures)

1. **No nested parentheses in comments.** RS274NGC `(...)` comments can't nest,
   including `(DEBUG, ...)`, `(ABORT, ...)` and `(MSG, ...)`. An inner `(` gives
   `Nested comment found` and the program won't load. Use dashes or slashes instead:
   `(keep MAX X - outermost)`, not `(keep MAX X (outermost))`.
   Fusion/CAM output does this too (`(Parallel1 (2))`). When asked, flatten it to
   `(Parallel1 - 2)` and strip `%` markers if requested.
2. **Plain ASCII only.** Em dashes, arrows and other Unicode show up as garbage in the
   LinuxCNC editor and preview.
3. **LF line endings only.** CRLF causes `Null missing after newline` and odd failures.
4. **O-word labels must be unique per file** (two `o<3007>` blocks → duplicate label).
5. **The filename must match the O-name** (`o<spindle_break_in>` →
   `spindle_break_in.ngc`). A called subroutine ends with `endsub`, **no M2**.
   A standalone program needs `%…%` or M2/M30.

Scan before you finish:

```bash
python3 - <<'PY'
from pathlib import Path
import sys
roots = [Path("probe_basic/subroutines"), Path("nc_files")]
bad = []
for root in roots:
    for p in root.rglob("*.ngc"):
        raw = p.read_bytes()
        if b"\r\n" in raw: bad.append(f"{p}: CRLF")
        try: raw.decode("ascii")
        except UnicodeDecodeError: bad.append(f"{p}: non-ASCII")
        for i, line in enumerate(raw.decode("utf-8", "replace").splitlines(), 1):
            d = m = 0
            for ch in line:
                if ch == "(": d += 1; m = max(m, d)
                elif ch == ")": d = max(0, d - 1)
            if m > 1: bad.append(f"{p}:{i}: nested comment: {line.strip()}")
print("OK" if not bad else "\n".join(bad)); sys.exit(1 if bad else 0)
PY
```

## Motion words

- **`G53` only with `G0`/`G1` on the same line** (`G0 G53 Z0`). Never `G53` with G38.
  Probe with `G91 G38.x …` then `G90`, and read machine coords via `#<_abs_x>` etc.
- LinuxCNC **cannot home from G-code** (`G28.2` is not "home Z"). Homing happens through the GUI or
  `halui.joint.N.home`. Metrology macros measure only, and Jon homes by hand.
- G38 seeks must be bounded by real limits and be closed-loop. Never `G0` to a
  guessed target near the setter or laser. Don't command Z above `G53 Z0`.
- `#<_hal[pin]>` is **read once when the program starts** (read-ahead), so it never
  updates inside a loop. For live input use `M66 P<n> L<mode> Q<timeout>` and read `#5399`.
  The laser beam is on `motion.digital-in-03` and the filtered probe path on `-04`.
- `M62 P0` (laser → probe-input) wraps **only** the G38 moves. Call `M63 P0` on every
  exit path, or the next retract trips "Probe tripped during non-probe move".
- M600/tool-touch-off start with `G94`. CAM may leave `G93` inverse-time active, which makes `F` meaningless.
- `M61 Qn` (Probe Basic's tool tab) does **not** update `#<_selected_tool>`. Compare
  `#<_current_tool>` against the CAM T word (`#2002`).
- Release `M50 P0` (feed-override lock) before any `M00`/`M01`, or the UI looks
  stuck in feed hold.

## Parameters

- User parameters max out at **#5599**. `#5601+` gives "Parameter number out of range".
- `linuxcnc.var` must stay **sorted ascending**. Appending out of order gives "Parameter
  file out of order". Write the file in sorted order.
- Persistent values only survive a restart if the number is listed in `linuxcnc.var`.
- Probe Basic macros need **UPDATE PROBE PARAMS** clicked first (`#3004–3039`).

## INI / startup / remap

- **No inline `;` comments on `REMAP=` lines.** They're parsed as options and give
  "NGC file not found", then interpreter death, then a misleading "servo-thread not found".
  Put comments on their own `#` lines.
- `RS274NGC_STARTUP_CODE`: **no O-word calls** ("Bad character 'o' used on startup")
  and **one P word per line** (`G64 P0.001` already uses it).
- **M100–M199 can't be remapped** (they're reserved for user M-files). Use M200+.
- Remapped M-codes that take words need `argspec=` (e.g. `argspec=pqr`), or you get
  "P word with no … to use it".
- `python=` remap functions must be **plain names** defined or imported in
  `probe_basic/python/remap.py`. Dotted `module.func` silently fails. If the interpreter fails to init,
  you get "No message text set" and `milltask` exits.
- `on_abort.ngc` may call O-words but **must not move** (E-stop runs it with motion disabled).

## Where things live

- Subroutines: `probe_basic/subroutines/` (`SUBROUTINE_PATH = .:probe_basic/subroutines`,
  not recursive. That's why the metrology runnables sit in the top level, with docs in `metrology/README.md`).
- Operator programs: `/home/jon/linuxcnc/nc_files` (`PROGRAM_PREFIX`). The repo's
  `nc_files/` isn't browsed by LinuxCNC, so copy files across when Jon needs them in the file picker.
- Test-move programs: from the current position (`#5420` = X), use `G61` (not G61.1, not G64),
  F30000 single out-and-back. Under G64 a stop-to-stop move only gets half the acceleration.
