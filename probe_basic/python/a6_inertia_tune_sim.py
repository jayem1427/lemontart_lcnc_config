"""Simulated IO for a6_inertia_tune tests (no LinuxCNC / hardware)."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple

from a6_inertia_tune import InertiaTuneError
from a6_servo_tune import AXES


class SimInertiaIO:
    """In-memory stand-in for HardwareInertiaIO."""

    name = "sim"

    def __init__(
        self,
        *,
        axis: str = "X",
        position: float = 50.0,
        min_limit: float = -254.0,
        max_limit: float = 370.0,
        homed: bool = True,
        baseline_ratio: float = 100.0,
        result_ratio: float = 350.0,
        f30_writable: bool = True,
        move: bool = True,
        fault_after_s: Optional[float] = None,
        complete_after_s: float = 0.4,
        machine_on: bool = True,
    ) -> None:
        self.axis = axis
        self.position = float(position)
        self.min_limit = float(min_limit)
        self.max_limit = float(max_limit)
        self.homed = bool(homed)
        self.ratio = float(baseline_ratio)
        self.result_ratio = float(result_ratio)
        self.f30_writable = bool(f30_writable)
        self.move = bool(move)
        self.fault_after_s = fault_after_s
        self.complete_after_s = float(complete_after_s)
        self._machine_on = bool(machine_on)
        self._fault = False
        self._f30 = 0
        self._t0: Optional[float] = None
        self.sdos: Dict[Tuple[int, int], int] = {
            (0x2007, 0x01): 769,
            (0x2007, 0x02): 500,
            (0x2007, 0x03): 100,
            (0x2007, 0x04): 150,
            (0x2007, 0x05): 200,
            (0x2030, 0x11): 0,
            (0x6065, 0x00): 13107,
        }
        self.writes: list = []

    def machine_ready(self) -> Tuple[bool, str]:
        if not self._machine_on:
            return False, "machine is not ON (turn it on first)"
        return True, "ok"

    def axis_state(self, axis: str) -> Dict[str, Any]:
        self._tick()
        return {
            "homed": self.homed,
            "position": self.position,
            "min_limit": self.min_limit,
            "max_limit": self.max_limit,
            "fault": self._fault,
        }

    def read_inertia_ratio(self, axis: str) -> float:
        self._tick()
        return float(self.ratio)

    def read_u16(self, axis: str, index: int, sub: int) -> int:
        self._tick()
        key = (index, sub)
        if key not in self.sdos:
            raise InertiaTuneError(f"sim SDO missing 0x{index:04X}:{sub}")
        return int(self.sdos[key])

    def write_u16(self, axis: str, index: int, sub: int, value: int) -> None:
        if index == 0x2030 and sub == 0x11 and not self.f30_writable:
            raise InertiaTuneError("sim: F30.10 rejected")
        self.sdos[(index, sub)] = int(value)
        self.writes.append((index, sub, int(value)))
        if index == 0x2030 and sub == 0x11 and int(value) == 1:
            self._f30 = 1
            self._t0 = time.monotonic()

    def read_u32(self, axis: str, index: int, sub: int) -> int:
        return self.read_u16(axis, index, sub)

    def write_u32(self, axis: str, index: int, sub: int, value: int) -> None:
        self.write_u16(axis, index, sub, int(value))

    def write_inertia_ratio(self, axis: str, pct: float) -> None:
        self.ratio = float(pct)

    def set_machine(self, enable: bool) -> None:
        self._machine_on = bool(enable)

    def sleep(self, seconds: float) -> None:
        time.sleep(min(seconds, 0.05))
        self._tick()

    def _tick(self) -> None:
        if self._t0 is None:
            return
        elapsed = time.monotonic() - self._t0
        if self.fault_after_s is not None and elapsed >= self.fault_after_s:
            self._fault = True
            return
        if self.move and elapsed >= 0.05:
            # Nudge position so the tuner sees motion.
            self.position += 0.2
        if elapsed >= self.complete_after_s:
            self.ratio = float(self.result_ratio)
            self.sdos[(0x2030, 0x11)] = 0
            self._f30 = 0
