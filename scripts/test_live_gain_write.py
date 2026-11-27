#!/usr/bin/env python3
"""Do the A6 drives accept gain writes while enabled?

The one-click tuner turns the machine OFF and back ON for every gain write.
That is slow, and on Z (no brake) the re-enable is a risk: in the 2026-07-16 Z
run the first move after a write tripped the FERR watchdog. If the drive takes
C01.00 / C01.01 / C01.02 while enabled, the tuner can use --live-writes and
skip the cycle entirely.

What this does, per gain, on ONE axis, with the machine ON and the axis
standing still:
  1. read the current value
  2. write current + one step (0.1 Hz / 0.1 rad/s / 0.01 ms) WITHOUT
     disabling, read back
  3. write the original value back, read back
Nothing moves. The gains change by one resolution step for about a second.

A pass means the drive stored the value while enabled. It does not prove the
drive applies it immediately; the tuner's own measurements show that (if
scores never change during a --live-writes run, the drive is not applying
them, so go back to the default).

Usage (machine ON, homed or not, axis idle):
    python3 scripts/test_live_gain_write.py --axis X
Exit 0 = all three accepted live. 1 = at least one refused. 2 = setup error.
"""

from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "probe_basic", "python"))

from a6_servo_tune import (  # noqa: E402
    AXES,
    AxisTuneParams,
    machine_is_on,
    read_axis_params,
    write_axis_sdos,
)

STEPS = {"pos_gain_rad_s": 0.1, "speed_gain_hz": 0.1, "integral_ms": 0.01}


def _write(axis: str, key: str, value: float) -> bool:
    params = AxisTuneParams.__new__(AxisTuneParams)
    params.values = {key: float(value)}
    result = write_axis_sdos(axis, params, keys=[key])
    return key in result.get("written", [])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--axis", required=True, choices=sorted(AXES))
    args = parser.parse_args()
    axis = args.axis

    if not machine_is_on():
        print("machine must be ON (drives enabled) for this test", file=sys.stderr)
        return 2
    params, ok_keys, _failed = read_axis_params(axis)
    missing = [k for k in STEPS if k not in ok_keys]
    if missing:
        print(f"could not read {missing}; check ethercat access", file=sys.stderr)
        return 2

    all_ok = True
    for key, step in STEPS.items():
        orig = float(params.values[key])
        changed = _write(axis, key, orig + step)
        restored = _write(axis, key, orig)
        still_on = machine_is_on()
        verdict = "LIVE OK" if changed and restored and still_on else "REFUSED"
        all_ok &= verdict == "LIVE OK"
        print(
            f"{axis} {key}: {orig:g} -> {orig + step:g} "
            f"{'stored' if changed else 'NOT stored'}, restore "
            f"{'ok' if restored else 'FAILED'}, machine "
            f"{'on' if still_on else 'DROPPED'}  => {verdict}"
        )
        if not restored:
            print(
                f"!! restore failed: set {key} back to {orig:g} by hand "
                "(Servo Tuning tab, LOAD the latest pre_one_click preset)",
                file=sys.stderr,
            )
            return 1
    print(
        "result: use --live-writes for this axis"
        if all_ok
        else "result: keep the default (machine OFF/ON per write)"
    )
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
