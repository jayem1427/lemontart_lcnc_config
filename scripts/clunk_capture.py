#!/usr/bin/env python3
"""Run clunk_test_<AXIS>.ngc and capture following error at the servo rate.

  (tpnext build: source ~/src/linuxcnc-tpnext/scripts/rip-environment first,
   or linuxcnc/halcmd report a HAL version mismatch)
  python3 scripts/clunk_capture.py X            # checks only, prints what it would do
  python3 scripts/clunk_capture.py X --run      # open + run the program, capture, save

Uses rt_capture.RtCapture (sampler.0, one row per servo cycle). Saves
logs/clunk/<YYYYMMDD_HHMMSS>_<AXIS>.csv with t_s, pos_cmd_mm, ferr_mm. If the
sampler overran or the sample count is off, the data is still saved but as
..._UNTRUSTED.csv and the script exits non-zero.
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "probe_basic", "python"))

import linuxcnc  # noqa: E402
import rt_capture  # noqa: E402

SCALE = 13107.2  # counts/mm, XYZ
JOINT = {"X": 0, "Y": 1, "Z": 2}
STROKE_MAX = 20.0  # program goes start .. start + 20 mm


def precheck(axis: str, allow_unhomed: bool):
    s = linuxcnc.stat()
    s.poll()
    for attempt in range(5):  # open can fail transiently under heavy disk load
        try:
            ini = linuxcnc.ini(s.ini_filename)
            break
        except linuxcnc.error:
            if attempt == 4:
                raise
            time.sleep(0.5)
            s.poll()
    lo = float(ini.find(f"AXIS_{axis}", "MIN_LIMIT"))
    hi = float(ini.find(f"AXIS_{axis}", "MAX_LIMIT"))
    j = JOINT[axis]
    pos = s.actual_position[j]  # machine coordinates
    problems = []
    if s.task_state != linuxcnc.STATE_ON:
        problems.append("machine is not ON")
    if s.interp_state != linuxcnc.INTERP_IDLE:
        problems.append("interpreter is busy (a program is running)")
    if not s.homed[j]:
        msg = f"{axis} is not homed: soft limits are not enforced"
        if not allow_unhomed:
            problems.append(msg)
        else:
            print("WARNING:", msg)
    if s.spindle[0]["enabled"]:
        problems.append("spindle is on")
    if not (lo <= pos and pos + STROKE_MAX <= hi):
        problems.append(
            f"{axis} at {pos:.3f} (G53): start..start+{STROKE_MAX:g} leaves "
            f"soft limits {lo:g}..{hi:g}"
        )
    if rt_capture._getp("sampler.0.enable") >= 0.5:
        problems.append("sampler.0 is busy: stop the Servo Tuning plot first")
    print(f"{axis} G53 = {pos:.4f} mm; program range {pos:.3f} .. {pos + STROKE_MAX:.3f}; "
          f"soft limits {lo:g} .. {hi:g}; homed={bool(s.homed[j])}")
    return problems


def run_program(path: str) -> float:
    c, s = linuxcnc.command(), linuxcnc.stat()
    c.mode(linuxcnc.MODE_AUTO)
    c.wait_complete()
    c.program_open(path)
    c.wait_complete()
    t0 = time.monotonic()
    c.auto(linuxcnc.AUTO_RUN, 0)
    started = False
    while True:
        time.sleep(0.05)
        s.poll()
        if s.task_state != linuxcnc.STATE_ON:
            raise RuntimeError("machine left ON during the program (E-stop / fault)")
        if s.interp_state != linuxcnc.INTERP_IDLE:
            started = True
        elif started or time.monotonic() - t0 > 3.0:
            break
    return time.monotonic() - t0


def save(cap, axis: str, out_dir: str, tag: str, meta: dict, rows=None) -> str:
    """t_s, pos_cmd_mm, ferr_mm of AXIS, then X/Y/Z ferr (mm) from the same
    servo cycle so a bus-wide timing glitch can be told from one axis's."""
    stamp = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(out_dir, f"{stamp}_{axis}{tag}.csv")
    fs = cap.fs_hz
    with open(path, "w") as fh:
        fh.write("# " + json.dumps(meta) + "\n")
        fh.write("t_s,pos_cmd_mm,ferr_mm,ferr_x_mm,ferr_y_mm,ferr_z_mm\n")
        for i, (p, f) in enumerate(zip(cap.pos_cmd, cap.ferr_counts)):
            r = rows[i] if rows else None
            xyz = (f",{r[0] / SCALE:.7f},{r[4] / SCALE:.7f},{r[8] / SCALE:.7f}"
                   if r else ",,,")
            fh.write(f"{i / fs:.4f},{p:.6f},{f / SCALE:.7f}{xyz}\n")
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("axis", nargs="?", default="X")
    ap.add_argument("--run", action="store_true", help="actually run the program")
    ap.add_argument("--allow-unhomed", action="store_true")
    ap.add_argument("--program", help="program file name in ~/linuxcnc/nc_files "
                    "(default clunk_test_<AXIS>.ngc)")
    ap.add_argument("--tag", default="", help="extra text in the CSV name")
    a = ap.parse_args()
    axis = a.axis.upper()
    prog = os.path.expanduser(
        "~/linuxcnc/nc_files/" + (a.program or f"clunk_test_{axis}.ngc"))
    out_dir = os.path.join(REPO, "logs", "clunk")
    os.makedirs(out_dir, exist_ok=True)

    if not os.path.exists(prog):
        print("missing", prog, "- run scripts/clunk_test_gcode.py", axis)
        return 2
    problems = precheck(axis, a.allow_unhomed)
    if problems:
        print("NOT RUNNING:\n  " + "\n  ".join(problems))
        return 2
    if not a.run:
        print("checks OK. Re-run with --run to start", prog)
        return 0

    cap_obj = rt_capture.RtCapture(axis)
    cap_obj.start()
    time.sleep(0.3)
    health = {"axis": axis, "program": prog, "fs_hz": cap_obj.fs_hz}
    try:
        health["program_s"] = round(run_program(prog), 2)
    except BaseException as exc:
        health["program_error"] = str(exc)
        print("PROGRAM PROBLEM:", exc)
    time.sleep(0.5)
    overruns0 = cap_obj._overruns0
    try:
        cap = cap_obj.stop()
        tag, ok = "", True
    except rt_capture.CaptureError as exc:
        cap, tag, ok = cap_obj._to_axis(), "_UNTRUSTED", False
        health["capture_error"] = str(exc)
    elapsed = cap_obj._t_stop - cap_obj._t_start
    health.update(
        samples=cap.n,
        elapsed_s=round(elapsed, 3),
        expected_samples=round(elapsed * cap.fs_hz),
        overruns=int(rt_capture._getp("sampler.0.overruns")) - overruns0,
        parse_errors=cap_obj._parse_errors,
    )
    path = save(cap, axis, out_dir, (("_" + a.tag) if a.tag else "") + tag, health,
                rows=cap_obj._rows)
    print(json.dumps(health, indent=1))
    print("saved", path)
    if "program_error" in health:
        ok = False
    sys.stdout.flush()
    os._exit(0 if ok else 1)


if __name__ == "__main__":
    raise SystemExit(main())
