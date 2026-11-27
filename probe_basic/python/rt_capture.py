"""Realtime drive telemetry capture for servo tuning.

Python cannot sample HAL pins at 1 kHz: a polling thread got 250-750 Hz with
jitter (see docs/ONE_CLICK_TUNING.md, "lessons learned" 2026-11-27), and the FFT
then reported every frequency at the wrong place. This module reads the
realtime ``sampler.0`` component loaded in ``custom.hal`` instead. It writes
one row per servo cycle into a FIFO, and ``halsampler`` streams it out.

Channel layout (must match the ``cfg=`` string and nets in custom.hal):

    per axis k (X=0, Y=1, Z=2, A=3), base = 4*k
      base+0  60F4 following error, counts   (s32)  <- <ax>-ferr-s32
      base+1  6077 torque, 0.1 % rated       (s32)  <- <ax>-torque-s32
      base+2  606C velocity, counts/s        (s32)  <- <ax>-vel-s32
      base+3  joint motor-pos-cmd, mm or deg (float)<- <ax>-pos-float-cmd

Those signals exist on both dev-jerk-testing and dev-drive-homing, so the
capture does not depend on how homing is done.

``sampler.0.enable`` is FALSE at rest so the FIFO stays empty. A capture
drains anything stale, starts ``halsampler``, sets enable, and on stop clears
enable, waits for the FIFO to empty and checks ``sampler.0.overruns`` did not
move. Note: in LinuxCNC 2.9 ``sampler.N.sample-num`` is never incremented, so
``halsampler -t`` tags cannot detect gaps; the overrun counter and a
sample-count vs elapsed-time check do that instead.
"""

from __future__ import annotations

import atexit
import collections
import os
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

SAMPLER = "sampler.0"
CHANNELS_PER_AXIS = 4
AXIS_BASE = {"X": 0, "Y": 4, "Z": 8, "A": 12}
N_CHANNELS = 16
TORQUE_PCT_PER_COUNT = 0.1  # A6 6077: 0.1 % rated per count (custom.hal)


class CaptureError(RuntimeError):
    """The capture is missing, overran, or returned an implausible count."""


def _halcmd(*args: str, timeout: float = 3.0) -> str:
    return subprocess.check_output(
        ["halcmd", *args], stderr=subprocess.STDOUT, text=True, timeout=timeout
    ).strip()


def _getp(pin: str) -> float:
    text = _halcmd("getp", pin)
    if text in ("TRUE", "FALSE"):
        return 1.0 if text == "TRUE" else 0.0
    return float(text)


def _setp(pin: str, value: str) -> None:
    _halcmd("setp", pin, value)


def servo_period_s(default: float = 0.001) -> float:
    """[EMCMOT]SERVO_PERIOD from the running INI (ns), else ``default``."""
    try:
        import linuxcnc  # type: ignore

        stat = linuxcnc.stat()
        stat.poll()
        ini = linuxcnc.ini(stat.ini_filename)
        value = ini.find("EMCMOT", "SERVO_PERIOD")
        if value:
            return float(value) * 1e-9
    except Exception:
        pass
    return default


def sampler_available() -> bool:
    """True when sampler.0 is loaded and halsampler is on PATH."""
    if shutil.which("halsampler") is None:
        return False
    try:
        _getp(f"{SAMPLER}.enable")
        return True
    except Exception:
        return False


@dataclass
class AxisCapture:
    axis: str
    fs_hz: float
    ferr_counts: List[float] = field(default_factory=list)
    torque_pct: List[float] = field(default_factory=list)
    vel_counts_s: List[float] = field(default_factory=list)
    pos_cmd: List[float] = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.ferr_counts)


class RtCapture:
    """One capture session. Not reusable: create one per measurement.

    ``latest_ferr_counts`` is updated by the reader thread as rows arrive, so
    callers can use it as a (tens of ms latency) watchdog. The hard,
    realtime stop is still the drive's own 6065 window.
    """

    def __init__(self, axis: str, fs_hz: Optional[float] = None) -> None:
        if axis not in AXIS_BASE:
            raise ValueError(f"unknown axis {axis!r}")
        self.axis = axis
        self.fs_hz = fs_hz if fs_hz else 1.0 / servo_period_s()
        self._base = AXIS_BASE[axis]
        self._rows: List[List[float]] = []
        self._proc: Optional[subprocess.Popen] = None
        self._reader: Optional[threading.Thread] = None
        self._overruns0 = 0
        self._t_start = 0.0
        self._t_stop = 0.0
        self._parse_errors = 0
        self.latest_ferr_counts: Optional[float] = None

    # -- lifecycle -----------------------------------------------------------

    def start(self) -> None:
        if not sampler_available():
            raise CaptureError(
                "realtime sampler not available: sampler.0 is not loaded "
                "(custom.hal REALTIME CAPTURE block) or halsampler is missing"
            )
        _check_not_busy()
        _setp(f"{SAMPLER}.enable", "0")
        self._drain_stale()
        self._overruns0 = int(_getp(f"{SAMPLER}.overruns"))
        cmd = ["halsampler", "-c", "0"]
        if shutil.which("stdbuf"):
            cmd = ["stdbuf", "-oL"] + cmd  # line-buffer so the watchdog sees rows quickly
        self._proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
        )
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        self._t_start = time.monotonic()
        _setp(f"{SAMPLER}.enable", "1")

    def stop(self) -> AxisCapture:
        try:
            _setp(f"{SAMPLER}.enable", "0")
        finally:
            self._t_stop = time.monotonic()
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            try:
                if int(_getp(f"{SAMPLER}.curr-depth")) == 0:
                    break
            except Exception:
                break
            time.sleep(0.02)
        time.sleep(0.1)  # let the reader consume the last lines
        self._terminate()
        overruns = int(_getp(f"{SAMPLER}.overruns")) - self._overruns0
        if overruns:
            raise CaptureError(
                f"sampler FIFO overran {overruns} time(s): samples were lost"
            )
        cap = self._to_axis()
        elapsed = self._t_stop - self._t_start
        expected = elapsed * self.fs_hz
        # enable/disable go through halcmd (tens of ms each), so allow slack.
        if expected > 200 and abs(cap.n - expected) > 0.10 * expected + 150:
            raise CaptureError(
                f"captured {cap.n} samples in {elapsed:.2f}s, expected "
                f"~{expected:.0f} at {self.fs_hz:g} Hz"
            )
        return cap

    def abort(self) -> None:
        """Best effort: stop sampling and the reader, discard data."""
        try:
            _setp(f"{SAMPLER}.enable", "0")
        except Exception:
            pass
        self._terminate()

    # -- internals -------------------------------------------------------------

    def _drain_stale(self) -> None:
        depth = int(_getp(f"{SAMPLER}.curr-depth"))
        if depth > 0:
            subprocess.run(
                ["halsampler", "-c", "0", "-n", str(depth)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
            )

    def _read_loop(self) -> None:
        assert self._proc is not None and self._proc.stdout is not None
        ferr_idx = self._base
        for line in self._proc.stdout:
            parts = line.split()
            if len(parts) < N_CHANNELS:
                self._parse_errors += 1
                continue
            try:
                row = [float(p) for p in parts[-N_CHANNELS:]]
            except ValueError:
                self._parse_errors += 1
                continue
            self._rows.append(row)
            self.latest_ferr_counts = row[ferr_idx]

    def _terminate(self) -> None:
        proc = self._proc
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                proc.kill()
        if self._reader is not None:
            self._reader.join(timeout=2.0)

    def _to_axis(self) -> AxisCapture:
        b = self._base
        cap = AxisCapture(axis=self.axis, fs_hz=self.fs_hz)
        for row in self._rows:
            cap.ferr_counts.append(row[b])
            cap.torque_pct.append(row[b + 1] * TORQUE_PCT_PER_COUNT)
            cap.vel_counts_s.append(row[b + 2])
            cap.pos_cmd.append(row[b + 3])
        return cap


def _check_not_busy() -> None:
    """sampler.0 has one FIFO: only one reader at a time."""
    if _getp(f"{SAMPLER}.enable") >= 0.5:
        raise CaptureError(
            "sampler.0 is already capturing (Servo Tuning plot running, or a "
            "tuner in another window). Stop it first. If nothing is running, "
            "a crashed session left it on: halcmd setp sampler.0.enable 0"
        )


class RtStream:
    """Continuous capture for the Servo Tuning tab: a ring buffer per axis.

    Started with START PLOT, stopped with STOP PLOT (and before one-click,
    which needs the sampler itself). ANALYZE takes ``snapshot()``: the last N
    seconds at the true servo rate. No count check (it runs for minutes);
    overruns are reported in the snapshot instead.
    """

    def __init__(self, seconds: float = 20.0, fs_hz: Optional[float] = None) -> None:
        self.fs_hz = fs_hz if fs_hz else 1.0 / servo_period_s()
        maxlen = max(int(seconds * self.fs_hz), 1000)
        self._rows: "collections.deque[List[float]]" = collections.deque(maxlen=maxlen)
        self._proc: Optional[subprocess.Popen] = None
        self._reader: Optional[threading.Thread] = None
        self._overruns0 = 0
        self.running = False

    def start(self) -> None:
        if not sampler_available():
            raise CaptureError("realtime sampler not available (sampler.0)")
        _check_not_busy()
        drain = RtCapture("X", fs_hz=self.fs_hz)
        drain._drain_stale()
        self._overruns0 = int(_getp(f"{SAMPLER}.overruns"))
        cmd = ["halsampler", "-c", "0"]
        if shutil.which("stdbuf"):
            cmd = ["stdbuf", "-oL"] + cmd
        self._proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
        )
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        _setp(f"{SAMPLER}.enable", "1")
        self.running = True
        atexit.register(self.stop)

    def _read_loop(self) -> None:
        assert self._proc is not None and self._proc.stdout is not None
        for line in self._proc.stdout:
            parts = line.split()
            if len(parts) < N_CHANNELS:
                continue
            try:
                self._rows.append([float(p) for p in parts[-N_CHANNELS:]])
            except ValueError:
                continue

    def overruns(self) -> int:
        try:
            return int(_getp(f"{SAMPLER}.overruns")) - self._overruns0
        except Exception:
            return -1

    def healthy(self) -> bool:
        return bool(
            self.running and self._proc is not None and self._proc.poll() is None
        )

    def snapshot(self, axis: str, seconds: float = 10.0) -> AxisCapture:
        """Last ``seconds`` of one axis (counts / % / counts/s / pos-cmd)."""
        if not self.healthy():
            raise CaptureError("realtime stream stopped (halsampler exited)")
        n = int(seconds * self.fs_hz)
        rows = list(self._rows)[-n:]
        b = AXIS_BASE[axis]
        cap = AxisCapture(axis=axis, fs_hz=self.fs_hz)
        for row in rows:
            cap.ferr_counts.append(row[b])
            cap.torque_pct.append(row[b + 1] * TORQUE_PCT_PER_COUNT)
            cap.vel_counts_s.append(row[b + 2])
            cap.pos_cmd.append(row[b + 3])
        return cap

    def stop(self) -> None:
        if not self.running:
            return
        self.running = False
        try:
            _setp(f"{SAMPLER}.enable", "0")
        except Exception:
            pass
        proc = self._proc
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                proc.kill()
        if self._reader is not None:
            self._reader.join(timeout=2.0)
        try:
            atexit.unregister(self.stop)
        except Exception:
            pass


def summarize(cap: AxisCapture, scale: float) -> Dict[str, float]:
    """Handy numbers for journals: peaks/RMS in axis units and % torque."""
    import math

    def rms(xs: List[float]) -> float:
        return math.sqrt(sum(x * x for x in xs) / len(xs)) if xs else 0.0

    ferr = [c / scale for c in cap.ferr_counts]
    return {
        "n": float(cap.n),
        "fs_hz": cap.fs_hz,
        "ferr_peak": max((abs(x) for x in ferr), default=0.0),
        "ferr_rms": rms(ferr),
        "torque_peak_pct": max((abs(x) for x in cap.torque_pct), default=0.0),
        "torque_rms_pct": rms(cap.torque_pct),
    }


if __name__ == "__main__":  # pragma: no cover - quick bench check on the machine
    import sys

    axis = sys.argv[1] if len(sys.argv) > 1 else "X"
    seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    from a6_servo_tune import AXES

    c = RtCapture(axis)
    c.start()
    time.sleep(seconds)
    result = c.stop()
    print({k: round(v, 6) for k, v in summarize(result, AXES[axis]["scale"]).items()})
    print(f"rows={result.n} ok", file=sys.stderr)
    os._exit(0)
