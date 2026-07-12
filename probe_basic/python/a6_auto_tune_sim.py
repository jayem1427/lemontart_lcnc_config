"""Simulated A6 axis for exercising the one-click auto-tuner without hardware.

This is NOT a physics model of the mill. It is a caricature with the right
monotonic behaviors so the OneClickTuner state machine can be tested end to
end (and demoed on a desk):

- tracking error shrinks as position / speed loop gains rise
- a resonance tone appears above ``resonance_gain_threshold_hz`` unless a
  notch filter covers ``resonance_hz``
- hard instability (huge growing oscillation) above ``critical_speed_hz``
- steady offset shrinks as the integral time is tightened; hunting appears
  below ``hunt_below_ms``
- gaussian noise floor everywhere

Used by test_a6_auto_tune.py and ``scripts/run_auto_tune.py --sim``.
"""

from __future__ import annotations

import json
import math
import os
import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from a6_servo_tune import PARAM_BY_KEY, AxisTuneParams
from a6_auto_tune import StimulusSpec

# Catalog-ish starting point for a bench axis; torque filter set high enough
# (like the real X preset) that the speed-vs-filter cap does not bind first.
SIM_BASELINE: Dict[str, float] = {
    "manual_mode": 0.0,
    "stiffness_level": 12.0,
    "inertia_ratio_pct": 100.0,
    "pos_gain_rad_s": 30.0,
    "speed_gain_hz": 20.0,
    "integral_ms": 31.84,
    "torque_filter_hz": 600.0,
    "pos_gain_2_rad_s": 56.0,
    "speed_gain_2_hz": 35.0,
    "integral_2_ms": 22.74,
    "torque_filter_2_hz": 280.0,
    "speed_ff_source": 0.0,
    "speed_ff_pct": 0.0,
    "speed_ff_filter_hz": 318.0,
    "torque_ff_source": 0.0,
    "torque_ff_pct": 0.0,
    "torque_ff_filter_hz": 318.0,
    "speed_fb_lpf_hz": 8000.0,
    "pdff_pct": 100.0,
    "damping_pct": 0.0,
    "adaptive_notch": 0.0,
    "notch1_freq_hz": 8000.0,
    "notch1_width_pct": 0.0,
    "notch1_depth_pct": 100.0,
    "notch2_freq_hz": 8000.0,
    "notch2_width_pct": 0.0,
    "notch2_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "notch3_depth_pct": 100.0,
    "notch4_freq_hz": 8000.0,
    "notch4_width_pct": 0.0,
    "notch4_depth_pct": 100.0,
    "notch5_freq_hz": 8000.0,
    "notch5_width_pct": 0.0,
    "notch5_depth_pct": 100.0,
    "gain_sw_time_ms": 5.0,
    "gain_sw_thresh": 10.0,
    "gain_sw_width": 10.0,
    "following_error": 1.0,
    "following_error_time_ms": 250.0,
}


@dataclass
class SimPlant:
    """Knobs describing the fake mechanics."""

    resonance_hz: float = 180.0
    resonance_gain_threshold_hz: float = 90.0
    critical_speed_hz: float = 140.0
    noise_units: float = 0.0003
    track_c1: float = 0.02  # ~ v / pos_gain contribution
    track_c2: float = 1.0  # ~ v / (pos_gain * speed_gain) contribution
    offset_per_ms: float = 0.0002  # steady offset ~ integral_ms
    hunt_below_ms: float = 1.5
    resonance_base_amp: float = 0.004
    instability_amp: float = 0.5

    def notched(self, params: Dict[str, float]) -> bool:
        """Any of the five torque notches close enough to the resonance?"""
        for n in range(1, 6):
            freq = params.get(f"notch{n}_freq_hz", 8000.0)
            depth = params.get(f"notch{n}_depth_pct", 100.0)
            if freq >= 7999.0 or depth >= 100.0:
                continue
            if abs(freq - self.resonance_hz) <= 0.15 * self.resonance_hz:
                return True
        return False

    def ferr_buffer(
        self,
        spec: StimulusSpec,
        signed_stroke: float,
        params: Dict[str, float],
        sample_hz: float,
        seed: int,
    ) -> np.ndarray:
        rng = np.random.default_rng(seed)
        fs = float(sample_hz)
        pos = max(params.get("pos_gain_rad_s", 30.0), 0.1)
        speed = max(params.get("speed_gain_hz", 20.0), 0.1)
        integral = max(params.get("integral_ms", 31.84), 0.15)

        v = spec.feed / 60.0  # units/s
        leg_t = spec.leg_time_s()
        leg_n = max(int(leg_t * fs), 8)
        dwell_n = max(int(spec.dwell_s * fs), 1)
        settle_n = max(int(spec.settle_s * fs), 1)

        track_amp = (
            self.track_c1 * v / pos + self.track_c2 * v / (pos * speed)
        )
        chunks: List[np.ndarray] = []
        for _cycle in range(spec.cycles):
            for sign in (1.0, -1.0):
                t = np.arange(leg_n) / fs
                hump = (
                    sign
                    * math.copysign(1.0, signed_stroke)
                    * track_amp
                    * np.sin(np.pi * t / leg_t)
                )
                chunks.append(hump)
                chunks.append(np.zeros(dwell_n))
        chunks.append(np.zeros(settle_n))
        signal = np.concatenate(chunks)
        n = signal.size
        t_all = np.arange(n) / fs

        # Steady-state offset from a lazy integral.
        signal = signal + self.offset_per_ms * integral

        # Resonance ring above the gain threshold, unless notched away.
        if speed > self.resonance_gain_threshold_hz and not self.notched(params):
            excess = (
                speed - self.resonance_gain_threshold_hz
            ) / self.resonance_gain_threshold_hz
            amp = self.resonance_base_amp * (1.0 + 4.0 * excess)
            signal = signal + amp * np.sin(
                2.0 * np.pi * self.resonance_hz * t_all
            )

        # Hard instability: violent oscillation that should trip the FERR
        # watchdog well before the buffer ends.
        if speed > self.critical_speed_hz:
            grow = np.linspace(0.2, 1.0, n)
            signal = signal + (
                self.instability_amp
                * (speed / self.critical_speed_hz)
                * grow
                * np.sin(2.0 * np.pi * self.resonance_hz * 1.3 * t_all)
            )

        # Integral hunting when over-tightened.
        if integral < self.hunt_below_ms:
            signal = signal + 0.003 * np.sin(2.0 * np.pi * 12.0 * t_all)

        signal = signal + rng.normal(0.0, self.noise_units, n)
        return signal


class SimTuneIO:
    """Duck-typed stand-in for HardwareTuneIO backed by SimPlant.

    Failure injection:

    - ``fail_write_calls``: set of 1-based write_params call ordinals that
      raise (simulates EtherCAT SDO flakiness)
    - ``fail_writes_from``: every write at/after this ordinal raises
      (simulates a dead bus — also breaks the revert, exercising the
      CRITICAL journal path)
    """

    name = "sim"

    def __init__(
        self,
        plant: Optional[SimPlant] = None,
        baseline: Optional[Dict[str, float]] = None,
        preset_dir: Optional[str] = None,
        fail_write_calls: Optional[set] = None,
        fail_writes_from: Optional[int] = None,
        read_fail_keys: Optional[List[str]] = None,
    ) -> None:
        self.plant = plant or SimPlant()
        self.params: Dict[str, float] = dict(SIM_BASELINE)
        if baseline:
            self.params.update(baseline)
        self.preset_dir = preset_dir
        self.fail_write_calls = fail_write_calls or set()
        self.fail_writes_from = fail_writes_from
        self.read_fail_keys = list(read_fail_keys or [])

        self.write_calls = 0
        self.write_log: List[Tuple[str, Dict[str, float]]] = []
        self.presets_saved: List[Tuple[str, str, Dict[str, float]]] = []
        self.measure_calls = 0

    # -- SDO ------------------------------------------------------------------

    def read_params(self, axis: str):
        values = {
            k: v for k, v in self.params.items() if k not in self.read_fail_keys
        }
        params = AxisTuneParams.__new__(AxisTuneParams)
        params.values = dict(values)
        return params, sorted(values.keys()), list(self.read_fail_keys)

    def write_params(
        self, axis: str, params: AxisTuneParams, keys: List[str]
    ) -> Dict[str, Any]:
        self.write_calls += 1
        if self.write_calls in self.fail_write_calls or (
            self.fail_writes_from is not None
            and self.write_calls >= self.fail_writes_from
        ):
            raise RuntimeError(
                f"sim: injected SDO write failure (call #{self.write_calls})"
            )
        written: List[str] = []
        skipped: List[str] = []
        for key in keys:
            defn = PARAM_BY_KEY.get(key)
            if defn is None or defn.get("writable", True) is False:
                skipped.append(key)
                continue
            self.params[key] = float(params.values[key])
            written.append(key)
        self.write_log.append((axis, {k: self.params[k] for k in written}))
        return {"written": written, "failed": [], "skipped": skipped}

    def save_preset(
        self, axis: str, name: str, params: AxisTuneParams, notes: str = ""
    ) -> str:
        self.presets_saved.append((axis, name, dict(params.values)))
        if self.preset_dir:
            os.makedirs(os.path.join(self.preset_dir, axis), exist_ok=True)
            path = os.path.join(self.preset_dir, axis, f"{name}.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "name": name,
                        "axis": axis,
                        "notes": notes,
                        "params": dict(params.values),
                    },
                    handle,
                    indent=2,
                )
            return path
        return f"<sim preset {name}>"

    # -- machine state ----------------------------------------------------------

    def machine_ready(self) -> Tuple[bool, str]:
        return True, "ok (sim)"

    def axis_state(self, axis: str) -> Dict[str, Any]:
        return {
            "homed": True,
            "position": 0.0,
            "min_limit": -10000.0,
            "max_limit": 10000.0,
            "feed_override": 1.0,
        }

    # -- motion -----------------------------------------------------------------

    def begin_session(self) -> None:
        pass

    def end_session(self) -> None:
        pass

    def run_stimulus(
        self,
        spec: StimulusSpec,
        signed_stroke: float,
        abort_ferr: float,
        sample_hz: float,
        cancel: threading.Event,
    ) -> Tuple[List[float], Dict[str, Any]]:
        self.measure_calls += 1
        meta: Dict[str, Any] = {
            "aborted": False,
            "abort_reason": "",
            "tripped_ferr": None,
            "position_drift": 0.0,
        }
        if cancel.is_set():
            meta.update(aborted=True, abort_reason="cancelled")
            return [], meta
        buf = self.plant.ferr_buffer(
            spec, signed_stroke, self.params, sample_hz, seed=self.measure_calls
        )
        over = np.nonzero(np.abs(buf) >= abs(abort_ferr))[0]
        if over.size:
            cut = min(int(over[0]) + 50, buf.size)
            buf = buf[:cut]
            meta.update(
                aborted=True,
                abort_reason=(
                    f"FERR watchdog tripped at {buf[int(over[0])]:.4f} "
                    f"(limit {abs(abort_ferr):.4f}) [sim]"
                ),
                tripped_ferr=float(buf[int(over[0])]),
            )
        return [float(v) for v in buf], meta
