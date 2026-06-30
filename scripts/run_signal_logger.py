#!/usr/bin/env python3
"""Run a HAL signal logger preset alongside LinuxCNC."""

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
    default_preset_dir,
    list_presets,
    load_preset,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--preset",
        default="cut_ferr",
        help="Preset name without .json (default: cut_ferr)",
    )
    parser.add_argument(
        "--config",
        help="Path to a custom JSON preset (overrides --preset)",
    )
    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="List available presets and exit",
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
        help="Override preset sample rate",
    )
    return parser.parse_args()


def resolve_preset_path(args: argparse.Namespace) -> str:
    if args.config:
        return os.path.abspath(args.config)
    preset_dir = default_preset_dir()
    return os.path.join(preset_dir, f"{args.preset}.json")


def main() -> int:
    args = parse_args()

    if args.list_presets:
        for path in list_presets():
            print(os.path.splitext(os.path.basename(path))[0])
        return 0

    preset_path = resolve_preset_path(args)
    if not os.path.isfile(preset_path):
        print(f"Preset not found: {preset_path}", file=sys.stderr)
        return 1

    preset = load_preset(preset_path)
    if args.rate_hz is not None:
        preset.rate_hz = args.rate_hz

    logger = HalSignalLogger(
        preset=preset,
        log_root=args.log_root,
        ini_path=args.ini,
    )

    print(f"Signal logger preset: {preset.name}")
    print(f"Trigger: {preset.trigger} @ {preset.rate_hz} Hz")
    print(f"Logging to: {logger.log_dir}")
    print("Press Ctrl+C to stop.")

    try:
        while True:
            logger.poll()
            time.sleep(0.005)
    except KeyboardInterrupt:
        if logger.state == "logging":
            logger.stop_manual()
        print("Stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
