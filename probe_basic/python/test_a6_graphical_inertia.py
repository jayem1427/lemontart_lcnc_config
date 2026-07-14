#!/usr/bin/env python3
"""Tests for graphical inertia analysis (no LinuxCNC required)."""

from __future__ import annotations

import math
import os
import sys
import tempfile

HERE = os.path.abspath(os.path.dirname(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from a6_graphical_inertia import (  # noqa: E402
    AxisInertiaSettings,
    GraphicalInertiaConfig,
    GraphicalInertiaError,
    GraphicalInertiaTuner,
    analyze_torque_velocity,
    unit_per_min_to_rpm,
)


def _trap_trace(
    *,
    j_total: float,
    j_motor: float,
    rated_nm: float,
    friction_pct: float,
    peak_rpm: float,
    accel_s: float,
    cruise_s: float,
    sample_hz: float = 1000.0,
    axis: str = "X",
):
    """Build ideal torque/velocity traces for known J (X: 10 mm/rev)."""
    alpha = (peak_rpm * 2 * math.pi / 60.0) / accel_s  # rad/s²
    t_accel_nm = j_total * alpha
    t_accel_pct = 100.0 * t_accel_nm / rated_nm
    t_peak = friction_pct + t_accel_pct
    # mm/min for X
    peak_feed = peak_rpm * 10.0

    torque = []
    vel = []
    n_acc = int(accel_s * sample_hz)
    n_cru = int(cruise_s * sample_hz)
    n_dec = n_acc
    for i in range(n_acc):
        frac = (i + 1) / n_acc
        torque.append(t_peak)
        vel.append(peak_feed * frac)
    for _ in range(n_cru):
        torque.append(friction_pct)
        vel.append(peak_feed)
    for i in range(n_dec):
        frac = 1.0 - (i + 1) / n_dec
        torque.append(friction_pct - t_accel_pct)  # opposite on decel
        vel.append(peak_feed * max(0.0, frac))
    return torque, vel, {
        "alpha": alpha,
        "t_peak": t_peak,
        "ratio_pct": 100.0 * (j_total - j_motor) / j_motor,
    }


def test_unit_rpm() -> None:
    assert abs(unit_per_min_to_rpm("X", 3000.0) - 300.0) < 1e-9
    assert abs(unit_per_min_to_rpm("A", 3600.0) - 10.0) < 1e-9


def test_analyze_ideal_trace() -> None:
    j_m = 1.0e-4
    j_l = 2.5e-4
    rated = 1.27
    tq, vel, truth = _trap_trace(
        j_total=j_m + j_l,
        j_motor=j_m,
        rated_nm=rated,
        friction_pct=5.0,
        peak_rpm=300.0,
        accel_s=0.05,
        cruise_s=0.1,
    )
    est = analyze_torque_velocity("X", tq, vel, 1000.0, j_m, rated)
    assert est.quality in ("good", "marginal"), est
    # Allow ~15% relative error from windowing/median
    assert abs(est.ratio_pct - truth["ratio_pct"]) / truth["ratio_pct"] < 0.15, (
        est.ratio_pct,
        truth["ratio_pct"],
    )


def test_analyze_rejects_tiny_move() -> None:
    tq = [5.0] * 50
    vel = [10.0] * 50  # ~1 rpm on X
    try:
        analyze_torque_velocity("X", tq, vel, 1000.0, 1e-4, 1.27)
        raise AssertionError("expected error")
    except GraphicalInertiaError:
        pass


def test_settings_validate() -> None:
    s = AxisInertiaSettings()
    try:
        s.validate()
        raise AssertionError("expected error")
    except GraphicalInertiaError:
        pass
    s.motor_inertia_kgm2 = 1e-4
    s.rated_torque_nm = 1.27
    s.validate()


class _FakeIO:
    name = "fake"

    def __init__(self, tq, vel):
        self.tq = tq
        self.vel = vel
        self.written = None
        self.ratio = 100.0

    def machine_ready(self):
        return True, "ok"

    def axis_state(self, axis):
        return {
            "homed": True,
            "position": 0.0,
            "min_limit": -200.0,
            "max_limit": 200.0,
        }

    def read_inertia_ratio(self, axis):
        return self.ratio

    def write_inertia_ratio(self, axis, pct):
        self.written = pct

    def run_move_and_sample(self, *args, **kwargs):
        return list(self.tq), list(self.vel), {"aborted": False}


def test_tuner_writes(tmp: str) -> None:
    j_m = 1.0e-4
    j_l = 3.0e-4
    rated = 1.27
    tq, vel, truth = _trap_trace(
        j_total=j_m + j_l,
        j_motor=j_m,
        rated_nm=rated,
        friction_pct=4.0,
        peak_rpm=250.0,
        accel_s=0.04,
        cruise_s=0.08,
    )
    settings = AxisInertiaSettings(
        motor_inertia_kgm2=j_m,
        rated_torque_nm=rated,
        stroke=40.0,
        feed=3000.0,
        write_to_drive=True,
    )
    io = _FakeIO(tq, vel)
    cfg = GraphicalInertiaConfig.for_axis("X", settings, sample_hz=1000.0)
    result = GraphicalInertiaTuner(cfg, io=io, journal_root=tmp).run()
    assert result.status == "ok", result.summary()
    assert io.written is not None
    assert abs(io.written - truth["ratio_pct"]) / truth["ratio_pct"] < 0.2


if __name__ == "__main__":
    failed = 0
    cases = [
        ("rpm", test_unit_rpm, False),
        ("analyze", test_analyze_ideal_trace, False),
        ("tiny", test_analyze_rejects_tiny_move, False),
        ("validate", test_settings_validate, False),
        ("tuner", test_tuner_writes, True),
    ]
    for name, fn, needs_tmp in cases:
        try:
            if needs_tmp:
                with tempfile.TemporaryDirectory() as tmp:
                    fn(tmp)
            else:
                fn()
            print(f"OK  {name}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {name}: {exc}")
    raise SystemExit(1 if failed else 0)
