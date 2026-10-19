#!/usr/bin/env python3
"""Speak home/limit trips while LinuxCNC is running (eyes-free QC).

  source ~/src/linuxcnc-tpnext/scripts/rip-environment
  python3 scripts/switch_announce.py

Watches post-invert trip signals (TRUE = switch active). If several trip
within SHORT_WINDOW_S, announces them together as a short/cluster.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
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
HOLD_S = 0.08  # ignore EMI blips; real NC trips stay closed longer
COOLDOWN_S = 1.5  # don't re-speak the same name while still bouncing

def speak(text: str) -> None:
    """espeak-ng — instant. Kokoro/Piper were too laggy next to LinuxCNC."""
    threading.Thread(target=_espeak, args=(text,), daemon=True).start()


def _espeak(text: str) -> None:
    if shutil.which("espeak-ng"):
        cmd = ["espeak-ng", "-v", "en-gb", "-s", "160", "-a", "200", text]
    elif shutil.which("espeak"):
        cmd = ["espeak", "-v", "en-gb", "-s", "160", "-a", "200", text]
    else:
        print(f"TTS unavailable: {text}", flush=True)
        return
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> int:
    # Unique name so relaunch works if a prior instance left a HAL component.
    h = hal.component(f"switch-announce-{os.getpid()}")
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
    rose_at: dict[str, float] = {}  # pin -> time it went TRUE
    held: set[str] = set()  # already queued this pulse

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
                rose_at[pin] = now
                held.discard(pin)
            elif (not val) and prev:
                t0 = rose_at.pop(pin, None)
                if t0 is not None and pin not in held:
                    print(f"glitch {name} {(now - t0) * 1000:.0f} ms", flush=True)
                held.discard(pin)
            if val and pin in rose_at and pin not in held:
                if now - rose_at[pin] >= HOLD_S:
                    held.add(pin)
                    if now - last_spoken.get(name, 0) >= COOLDOWN_S:
                        pending.append((now, name))
        if pending and (now - pending[0][0]) >= SHORT_WINDOW_S:
            flush_pending(now)
        time.sleep(POLL_S)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        speak("Switch announce stopped")
        raise SystemExit(0)
