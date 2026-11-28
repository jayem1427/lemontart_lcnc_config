#!/usr/bin/env python3
"""Write ~/linuxcnc/nc_files/clunk_test_<AXIS>.ngc (air moves, one axis).

Every stroke goes + then back -, so the axis only ever sits between the start
point and start + 20 mm. Blocks a-f run with G61, then again with G64 P0.01.

  python3 scripts/clunk_test_gcode.py X        # or Y
"""
import os
import sys

BLOCKS = [  # (name, stroke mm, feed mm/min)
    ("a", 20.0, 1000),
    ("b", 20.0, 3000),
    ("c", 20.0, 6000),
    ("d", 20.0, 12000),
    ("e", 2.0, 3000),
    ("f", 0.1, 500),
]
CYCLES = 10
DWELL = 0.5
MAX_EXCURSION = 25.0  # mm from the start point, never exceeded


def program(axis: str, passes: int = 1) -> str:
    assert max(s for _, s, _ in BLOCKS) <= MAX_EXCURSION
    out = [
        f"(clunk test, axis {axis} only: air moves, spindle off, Z untouched)",
        f"(start: jog {axis} to mid-travel with Z raised. Range: start .. start+20 mm)",
        "G21 G90 G94 G61",
        "M5",
    ]
    for mode, code in (("G61", "G61"), ("G64", "G64 P0.01")) * passes:
        out.append(f"(=== {mode} ===)")
        out.append(code)
        out.append("G91")
        for i, (name, stroke, feed) in enumerate(BLOCKS):
            out.append(f"(block {name} {mode}: +/-{stroke:g} mm at F{feed}, {CYCLES} cycles)")
            for _ in range(CYCLES):
                out.append(f"G1 {axis}{stroke:.4f} F{feed}")
                out.append(f"G1 {axis}-{stroke:.4f}")
            out.append(f"G4 P{DWELL}")
    out += ["G90", "G61", "M2", ""]
    return "\n".join(out)


def main() -> None:
    axis = (sys.argv[1] if len(sys.argv) > 1 else "X").upper()
    if axis not in "XYZ":
        raise SystemExit("axis must be X, Y or Z")
    passes = int(sys.argv[2]) if len(sys.argv) > 2 else 1  # >1: long "stress" run
    name = f"clunk_test_{axis}.ngc" if passes == 1 else f"clunk_stress_{axis}.ngc"
    path = os.path.expanduser(f"~/linuxcnc/nc_files/{name}")
    with open(path, "w", encoding="ascii", newline="\n") as fh:
        fh.write(program(axis, passes))
    print(path)


if __name__ == "__main__":
    main()
