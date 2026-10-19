#!/usr/bin/env python3
"""Speak home/limit trips while LinuxCNC is running (eyes-free QC).

  source ~/src/linuxcnc-tpnext/scripts/rip-environment
  python3 scripts/switch_announce.py

Watches post-invert trip signals (TRUE = switch active). If several trip
within SHORT_WINDOW_S, announces them together as a short/cluster.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time

import hal

# Logical name -> HAL pin/signal (TRUE when tripped after not.*)
WATCH = [
    ("X home", "x-home"),
    ("X limit", "x-limit"),
    ("Y limit", "y-limit"),
    ("Y and Z home", "yz-home"),
    # Z- limit DI hijacked for Y limit — joint.2 neg lim is gagged
]

POLL_S = 0.02
SHORT_WINDOW_S = 0.15  # edges closer than this = one spoken group
COOLDOWN_S = 0.35  # ignore re-chatter after speaking a name


def speak(text: str) -> None:
    cmd = None
    if shutil.which("espeak-ng"):
        cmd = ["espeak-ng", "-s", "160", "-a", "200", text]
    elif shutil.which("espeak"):
        cmd = ["espeak", "-s", "160", "-a", "200", text]
    else:
        print(f"TTS unavailable: {text}", flush=True)
        return
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> int:
    # Attach as a tiny HAL component so we share the running session.
    h = hal.component("switch-announce")
    h.ready()

    missing = []
    state: dict[str, bool] = {}
    for name, pin in WATCH:
        try:
            state[pin] = bool(hal.get_value(pin))
        except Exception as exc:  # noqa: BLE001
            missing.append(f"{pin} ({exc})")
    if missing:
        speak("Switch announce failed. Hal pins missing.")
        print("Missing:", ", ".join(missing), file=sys.stderr)
        return 1

    speak("Switch announce ready. Flip switches.")
    print("Watching:", ", ".join(n for n, _ in WATCH), flush=True)
    for name, pin in WATCH:
        print(f"  {name}: {'TRIP' if state[pin] else 'ok'}", flush=True)

    pending: list[tuple[float, str]] = []  # (t, name)
    last_spoken: dict[str, float] = {}

    def flush_pending(now: float) -> None:
        nonlocal pending
        if not pending:
            return
        if now - pending[0][0] < SHORT_WINDOW_S:
            return
        # unique names in order
        names: list[str] = []
        for _, n in pending:
            if n not in names:
                names.append(n)
        pending = []
        for n in names:
            last_spoken[n] = now
        if len(names) == 1:
            msg = f"{names[0]} triggered"
        else:
            msg = "Short. " + ", ".join(names) + " triggered together"
        print(msg, flush=True)
        speak(msg)

    while True:
        now = time.time()
        for name, pin in WATCH:
            try:
                val = bool(hal.get_value(pin))
            except Exception as exc:  # noqa: BLE001
                speak("Hal connection lost")
                print(f"HAL error: {exc}", file=sys.stderr)
                return 1
            prev = state[pin]
            state[pin] = val
            if val and not prev:
                if now - last_spoken.get(name, 0) < COOLDOWN_S:
                    continue
                pending.append((now, name))
            elif (not val) and prev:
                # optional clear — keep quiet unless alone and idle pending
                pass
        if pending and (now - pending[0][0]) >= SHORT_WINDOW_S:
            flush_pending(now)
        time.sleep(POLL_S)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        speak("Switch announce stopped")
        raise SystemExit(0)
