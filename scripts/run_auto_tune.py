#!/usr/bin/env python3
"""Headless one-click servo auto-tune for one axis (A6-EC / LinuxCNC).

Same engine as the Servo Tuning tab's ONE-CLICK TUNE button — see
ONE_CLICK_TUNING.md before running this on the real machine.

Examples:

    # Verify the pipeline end-to-end against the simulated axis (safe anywhere)
    python3 scripts/run_auto_tune.py --axis X --sim

    # Measure the real baseline without writing anything or changing gains
    python3 scripts/run_auto_tune.py --axis X --dry-run

    # Full campaign on the real X axis (LinuxCNC must be up, machine ON,
    # clearance for the stimulus stroke from the current position)
    python3 scripts/run_auto_tune.py --axis X --profile balanced

Every run writes a journal under logs/tuning/one_click/ — keep those, they
are the record we learn from when a campaign fails.
"""

from __future__ import annotations

import argparse
import os
import sys
import time


def _bootstrap_import_path() -> str:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    python_dir = os.path.join(root, "probe_basic", "python")
    sys.path.insert(0, python_dir)
    return root


ROOT = _bootstrap_import_path()

from a6_auto_tune import (  # noqa: E402
    DEFAULT_STIMULI,
    OneClickConfig,
    OneClickTuner,
    PROFILES,
    StimulusSpec,
    estimate_campaign_seconds,
)
from a6_servo_tune import AXES, axis_unit  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--axis", required=True, choices=sorted(AXES.keys()), help="axis to tune"
    )
    parser.add_argument(
        "--profile",
        default="balanced",
        choices=sorted(PROFILES.keys()),
        help="ladder aggressiveness (default: balanced)",
    )
    parser.add_argument(
        "--sim",
        action="store_true",
        help="run against the simulated axis instead of hardware "
        "(no LinuxCNC needed; nothing moves)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="preflight + baseline measurement only; write nothing",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="skip the interactive confirmation (hardware runs only)",
    )
    parser.add_argument("--stroke", type=float, help="override stimulus stroke")
    parser.add_argument(
        "--feed", type=float, help="override stimulus feed (units/min)"
    )
    parser.add_argument(
        "--cycles", type=int, help="override stimulus back-and-forth cycles"
    )
    parser.add_argument(
        "--journal-root",
        default=None,
        help="override journal directory (default logs/tuning/one_click)",
    )
    parser.add_argument(
        "--no-notch",
        action="store_true",
        help="never write notch filters automatically",
    )
    parser.add_argument(
        "--no-presets",
        action="store_true",
        help="do not save pre/post presets under config/tuning/presets",
    )
    return parser.parse_args()


def build_stimulus(args: argparse.Namespace) -> StimulusSpec:
    base = DEFAULT_STIMULI[args.axis]
    return StimulusSpec(
        axis=args.axis,
        stroke=args.stroke if args.stroke is not None else base.stroke,
        feed=args.feed if args.feed is not None else base.feed,
        cycles=args.cycles if args.cycles is not None else base.cycles,
        dwell_s=base.dwell_s,
        settle_s=base.settle_s,
    )


def main() -> int:
    args = parse_args()
    stimulus = build_stimulus(args)
    cfg = OneClickConfig.for_axis(
        args.axis,
        args.profile,
        stimulus=stimulus,
        dry_run=args.dry_run,
        allow_notch=not args.no_notch,
        save_presets=not args.no_presets,
    )

    unit = axis_unit(args.axis)
    est_min = estimate_campaign_seconds(cfg) / 60.0
    print(f"one-click tune — axis {args.axis} ({args.profile})")
    print(f"  stimulus : {stimulus.describe()}")
    print(f"  envelope : up to {stimulus.stroke:g} {unit} from the CURRENT position")
    print(f"  duration : up to ~{est_min:.0f} min worst case")
    print(f"  mode     : {'SIM' if args.sim else 'HARDWARE'}"
          f"{' + DRY RUN (no writes)' if args.dry_run else ''}")

    if args.sim:
        from a6_auto_tune_sim import SimTuneIO

        io = SimTuneIO()
    else:
        from a6_auto_tune import HardwareTuneIO

        if not args.dry_run and not args.yes:
            print(
                "\nThe axis WILL MOVE and drive gains WILL BE REWRITTEN "
                "(RAM only; baseline preset saved first)."
            )
            answer = input(f"Type the axis letter ({args.axis}) to continue: ")
            if answer.strip().upper() != args.axis:
                print("aborted — nothing was written")
                return 2
        io = HardwareTuneIO()

    t0 = time.time()

    def progress(phase: str, message: str) -> None:
        print(f"[{time.time() - t0:7.1f}s] {phase:>9}: {message}", flush=True)

    tuner = OneClickTuner(
        cfg, io=io, journal_root=args.journal_root, progress=progress
    )
    # Ctrl+C is handled inside run(): the engine reverts to baseline and
    # finalizes the journal with status "cancelled".
    result = tuner.run()
    print()
    print(result.summary())
    return 0 if result.status in ("improved", "no-change", "dry-run") else 2


if __name__ == "__main__":
    raise SystemExit(main())
