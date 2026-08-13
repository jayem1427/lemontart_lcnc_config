---
name: linuxcnc-ngc-macros
description: >-
  LinuxCNC RS274NGC / .ngc macro authoring rules for this mill config. Use when
  creating or editing .ngc subroutines, probe/laser macros, DEBUG/ABORT messages,
  or when LinuxCNC reports Nested comment found.
---

# LinuxCNC NGC macros

## Nested comments — hard fail

RS274NGC `(...)` comments **cannot nest**. An inner `(` before the closing `)`
causes:

```text
Error in <file>.ngc line N
Nested comment found
```

That aborts load/run before any motion.

### Rules

1. Inside a `(...)` comment or `(DEBUG, ...)` / `(ABORT, ...)` message, **never**
   use `(...)` again.
2. Prefer dashes, commas, or slash wording instead of parenthetical asides.
3. Before finishing any `.ngc` edit, scan for nested parens (depth > 1 on a line).

### Bad → good

```ngc
(Bad: raw beam (no gullet envelope).)
(Good: raw beam — no gullet envelope.)

(--- keep MAX X (outermost) ---)
(--- keep MAX X / outermost ---)

(DEBUG, edge order invalid (x_plus <= x_minus))
(DEBUG, edge order invalid — x_plus <= x_minus)
```

Quotes `"..."` inside comments are fine; only nested `(` is forbidden.

## Quick check

After editing macros under `probe_basic/subroutines/`:

```bash
python3 - <<'PY'
from pathlib import Path
bad = []
for p in Path("probe_basic/subroutines").rglob("*.ngc"):
    for i, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
        d = m = 0
        for ch in line:
            if ch == "(":
                d += 1; m = max(m, d)
            elif ch == ")":
                d = max(0, d - 1)
        if m > 1:
            bad.append(f"{p}:{i}:{line}")
print("OK" if not bad else "\n".join(bad))
PY
```

## Related

- Same rule noted in `docs/TOOLSETTER.md` for ABORT messages.
- Laser measure macros: `probe_basic/subroutines/laser_*.ngc`
