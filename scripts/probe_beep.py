#!/usr/bin/env python3
"""HAL userspace component: play beep.mp3 on rising edge of probe-in.

Wired from probe_beep.hal to the existing probe-in net (touch probe,
toolsetter, or laser trip → motion.probe-input).

Requires an MP3-capable CLI player (mpg123, ffplay, or gst-play-1.0).
Disable by commenting out HALFILE = probe_beep.hal in ethercat_mill.ini.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time

COMPONENT_NAME = "probe-beep"
POLL_S = 0.01
# Ignore extra rising edges while a beep is still playing (rapid laser G38).
COOLDOWN_S = 0.05

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
DEFAULT_BEEP = os.path.join(_ROOT, "beep.mp3")

# (argv prefix without the sound file). First match on PATH wins.
_PLAYERS = (
    ("mpg123", ["mpg123", "-q"]),
    ("ffplay", ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"]),
    ("gst-play-1.0", ["gst-play-1.0", "--no-interactive"]),
)


def find_player() -> list[str] | None:
    for _name, argv in _PLAYERS:
        if shutil.which(argv[0]):
            return list(argv)
    return None


def play_beep(player: list[str], path: str, prev_proc: subprocess.Popen | None) -> subprocess.Popen | None:
    if prev_proc is not None and prev_proc.poll() is None:
        return prev_proc
    try:
        return subprocess.Popen(
            player + [path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
    except OSError as exc:
        sys.stderr.write(f"probe_beep: play failed: {exc}\n")
        return prev_proc


def check_mode() -> int:
    """Smoke test without LinuxCNC HAL (scripts/probe_beep.py --check)."""
    path = DEFAULT_BEEP
    player = find_player()
    print(f"beep file: {path} ({'ok' if os.path.isfile(path) else 'MISSING'})")
    print(f"player:    {player[0] if player else 'NONE (install mpg123 or ffmpeg)'}")
    if not os.path.isfile(path) or not player:
        return 1
    proc = play_beep(player, path, None)
    if proc is None:
        return 1
    return proc.wait()


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        return check_mode()

    try:
        import hal  # LinuxCNC python3-hal
    except ImportError:
        sys.stderr.write(
            "probe_beep: cannot import hal — run under LinuxCNC "
            "or use --check for a desk smoke test\n"
        )
        return 1

    beep_path = DEFAULT_BEEP
    player = find_player()
    if not os.path.isfile(beep_path):
        sys.stderr.write(f"probe_beep: missing sound file: {beep_path}\n")
    if player is None:
        sys.stderr.write(
            "probe_beep: no MP3 player found "
            "(apt install mpg123  — or ffmpeg for ffplay)\n"
        )

    h = hal.component(COMPONENT_NAME)
    h.newpin("trigger", hal.HAL_BIT, hal.HAL_IN)
    h.ready()

    prev = False
    last_play = 0.0
    proc: subprocess.Popen | None = None

    try:
        while True:
            try:
                on = bool(h["trigger"])
            except Exception:
                break

            now = time.monotonic()
            if (
                on
                and not prev
                and player is not None
                and os.path.isfile(beep_path)
                and (now - last_play) >= COOLDOWN_S
            ):
                proc = play_beep(player, beep_path, proc)
                last_play = now

            prev = on
            time.sleep(POLL_S)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
