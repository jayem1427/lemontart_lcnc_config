#!/usr/bin/env python3
"""Run the HAL signal logger alongside LinuxCNC."""

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

from hal_signal_logger import (  # noqa: E402
    HalSignalLogger,
    default_config_path,
    load_config,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--arm",
        action="store_true",
        help="Arm for the next AUTO program (default)",
    )
    mode.add_argument(
        "--live",
        action="store_true",
        help="Start live logging immediately (stop with Ctrl+C)",
    )
    parser.add_argument(
        "--config",
        default=default_config_path(),
        help="Path to signals JSON config",
    )
    parser.add_argument(
        "--ini",
        default=os.environ.get("INI_FILE_NAME", os.path.join(ROOT, "ethercat_mill.ini")),
        help="LinuxCNC INI path",
    )
    parser.add_argument(
        "--log-root",
        default=os.path.join(ROOT, "logs"),
        help="Root directory for CSV logs",
    )
    parser.add_argument(
        "--rate-hz",
        type=float,
        help="Override sample rate",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not os.path.isfile(args.config):
        print(f"Config not found: {args.config}", file=sys.stderr)
        return 1

    config = load_config(args.config)
    if args.rate_hz is not None:
        config.rate_hz = args.rate_hz

    saved_paths: list[str] = []

    def on_saved(csv_path: str, _summary_path: str) -> None:
        saved_paths.append(csv_path)
        print(f"\nLog saved: {csv_path}")

    logger = HalSignalLogger(
        config=config,
        log_root=args.log_root,
        ini_path=args.ini,
        on_session_saved=on_saved,
    )

    print(f"Signal logger: {config.name}")
    print(f"Sample rate: {config.rate_hz} Hz")
    print(f"Logging to: {logger.log_dir}")

    if args.live:
        print("Live logging — press Ctrl+C to stop.")
        logger.start_live()
    else:
        print("Armed for next program — run a .ngc in AUTO (Ctrl+C to exit).")
        logger.arm_for_next_program()

    try:
        while True:
            logger.poll()
            time.sleep(0.005)
    except KeyboardInterrupt:
        if logger.state == "logging":
            logger.stop()
        if saved_paths:
            print(f"Last log: {saved_paths[-1]}")
        else:
            print("Stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
