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
    MAX_ID_FEED,
    PREFERRED_ACCEL_S,
    analyze_torque_velocity,
    target_id_accel,
    unit_accel_to_alpha,
    unit_per_min_to_rpm,
    yaskawa_worksheet_ratio,
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
    cycles: int = 1,
):
    """Build ideal torque/velocity traces for known J (X: 10 mm/rev)."""
    alpha = (peak_rpm * 2 * math.pi / 60.0) / accel_s
    t_accel_nm = j_total * alpha
    t_accel_pct = 100.0 * t_accel_nm / rated_nm
    t_peak = friction_pct + t_accel_pct
    peak_feed = peak_rpm * 10.0

    torque = []
    vel = []
    n_acc = int(accel_s * sample_hz)
    n_cru = int(cruise_s * sample_hz)
    n_dec = n_acc
    n_rest = max(5, int(0.02 * sample_hz))

    def _one_leg(sign: float) -> None:
        for _ in range(n_rest):
            torque.append(0.5 * sign)
            vel.append(0.0)
        for i in range(n_acc):
            frac = (i + 1) / n_acc
            torque.append(t_peak * sign)
            vel.append(peak_feed * frac * sign)
        for _ in range(n_cru):
            torque.append(friction_pct * sign)
            vel.append(peak_feed * sign)
        for i in range(n_dec):
            frac = 1.0 - (i + 1) / n_dec
            torque.append((friction_pct - t_accel_pct) * sign)
            vel.append(peak_feed * max(0.0, frac) * sign)
        for _ in range(n_rest):
            torque.append(0.5 * sign)
            vel.append(0.0)

    for _ in range(max(1, cycles)):
        _one_leg(+1.0)
        _one_leg(-1.0)
    return torque, vel, {
        "alpha": alpha,
        "t_peak": t_peak,
        "ratio_pct": 100.0 * (j_total - j_motor) / j_motor,
    }


def _stepped_accel_trace(
    *,
    friction_pct: float,
    peak_pct: float,
    peak_feed: float,
    mid_feed: float,
    plateau_ms: int,
    cruise_ms: int,
    sample_hz: float = 1000.0,
    cycles: int = 5,
):
    torque: list = []
    vel: list = []
    n_plat = max(1, int(plateau_ms * sample_hz / 1000.0))
    n_cru = max(5, int(cruise_ms * sample_hz / 1000.0))
    n_rest = max(5, int(0.03 * sample_hz))

    def _leg(sign: float) -> None:
        for _ in range(n_rest):
            torque.append(0.5 * sign)
            vel.append(0.0)
        for _ in range(n_plat):
            torque.append(peak_pct * sign)
            vel.append(mid_feed * sign)
        for _ in range(n_cru):
            torque.append(friction_pct * sign)
            vel.append(peak_feed * sign)
        for _ in range(n_plat):
            torque.append(-peak_pct * sign)
            vel.append(mid_feed * sign * 0.2)
        for _ in range(n_rest):
            torque.append(0.4 * sign)
            vel.append(0.0)

    for _ in range(max(1, cycles)):
        _leg(+1.0)
        _leg(-1.0)
    return torque, vel


def _held(values, hold_n):
    """Apply PDO sample-and-hold (A6 606C/6077 style) to a sample list."""
    out = []
    for i in range(len(values)):
        out.append(values[(i // hold_n) * hold_n])
    return out


def _physical_trace(
    *,
    j_total: float,
    coulomb_nm: float,
    viscous: float,
    rated_nm: float,
    peak_rpm: float,
    accel_s: float,
    cruise_s: float,
    sample_hz: float = 1000.0,
    vel_hold_ms: float = 20.0,
    tq_hold_ms: float = 10.0,
):
    """Simulate a physically consistent trapezoid (both directions) and
    corrupt it with PDO sample-and-hold, like the real A6 feedback."""
    dt = 1.0 / sample_hz
    w_peak = peak_rpm * 2.0 * math.pi / 60.0
    alpha = w_peak / accel_s
    n_acc = int(accel_s * sample_hz)
    n_cru = int(cruise_s * sample_hz)
    n_rest = int(0.05 * sample_hz)

    omega: list = []
    torque_nm: list = []

    def _leg(sign: float) -> None:
        w = 0.0
        for _ in range(n_rest):
            omega.append(0.0)
            torque_nm.append(0.0)
        for _ in range(n_acc):
            w += sign * alpha * dt
            fr = coulomb_nm * math.tanh(2.0 * w) + viscous * w
            torque_nm.append(j_total * sign * alpha + fr)
            omega.append(w)
        for _ in range(n_cru):
            fr = coulomb_nm * math.tanh(2.0 * w) + viscous * w
            torque_nm.append(fr)
            omega.append(w)
        for _ in range(n_acc):
            w -= sign * alpha * dt
            fr = coulomb_nm * math.tanh(2.0 * w) + viscous * w
            torque_nm.append(-j_total * sign * alpha + fr)
            omega.append(w)
        for _ in range(n_rest):
            omega.append(0.0)
            torque_nm.append(0.0)

    _leg(+1.0)
    _leg(-1.0)

    tq_pct = [100.0 * t / rated_nm for t in torque_nm]
    vel = [w * 60.0 / (2.0 * math.pi) * 10.0 for w in omega]  # X: 10 mm/rev
    tq_pct = _held(tq_pct, max(1, int(tq_hold_ms * sample_hz / 1000.0)))
    vel = _held(vel, max(1, int(vel_hold_ms * sample_hz / 1000.0)))
    return tq_pct, vel


def test_physics_fit_recovers_j_through_pdo_holds() -> None:
    """Known J + friction + 606C/6077 holds → fit must recover the ratio.

    This is exactly the condition that broke the two-point rule (ΔV inside
    a hold window → α garbage). The physics fit integrates torque instead.
    """
    j_m = 5.9e-5
    j_total = 2.2 * j_m  # ratio 120%
    tq, vel = _physical_trace(
        j_total=j_total,
        coulomb_nm=0.06,
        viscous=1e-3,
        rated_nm=1.27,
        peak_rpm=800.0,
        accel_s=0.12,
        cruise_s=0.25,
    )
    est = analyze_torque_velocity("X", tq, vel, 1000.0, j_m, 1.27)
    truth = 100.0 * (j_total - j_m) / j_m
    # ±25%: worst-case hold phasing skews torque/velocity alignment a bit,
    # but nothing like the ×1000 blowups of the two-point dV/dt rule.
    assert abs(est.ratio_pct - truth) / truth < 0.25, (est.ratio_pct, truth)
    assert est.method == "physics-fit"
    assert est.fit_err_frac is not None and est.fit_err_frac < 0.16, est
    assert est.sim_vel_unit_per_min, "sim overlay missing"


def test_unit_rpm() -> None:
    assert abs(unit_per_min_to_rpm("X", 3000.0) - 300.0) < 1e-9
    assert abs(unit_per_min_to_rpm("A", 3600.0) - 10.0) < 1e-9


def test_sigma_ii_worksheet_example() -> None:
    """Exact numbers from Sigma II Parameter Calculator Rev 2.42 Inertia sheet."""
    out = yaskawa_worksheet_ratio(
        tp_pct=90.0,
        tf_pct=4.5,
        delta_v_rpm=1000.0,
        delta_t_ms=3.34,
        rated_torque_nm=0.318,
        motor_inertia_kgm2=3.64e-6,
    )
    assert abs(out["ta_nm"] - 0.27189) < 1e-9
    assert abs(out["alpha_rad_s2"] - 31353.22009570652) < 1e-6
    assert abs(out["j_load_kgm2"] - 5.0318365504419865e-6) < 1e-15
    assert abs(out["ratio_pct"] - 138.23726786928535) < 1e-9


def test_target_id_accel() -> None:
    a = target_id_accel(3000.0, 0.08)
    assert abs(a - 625.0) < 1e-6
    assert abs(unit_accel_to_alpha("X", 2942.0) - 1848.5) < 1.0
    a120 = target_id_accel(8000.0, PREFERRED_ACCEL_S)
    assert abs(a120 - (8000.0 / 60.0 / PREFERRED_ACCEL_S)) < 1e-6


def test_analyze_ideal_trace() -> None:
    j_m = 1.0e-4
    j_l = 2.5e-4
    rated = 1.27
    tq, vel, truth = _trap_trace(
        j_total=j_m + j_l,
        j_motor=j_m,
        rated_nm=rated,
        friction_pct=5.0,
        peak_rpm=800.0,
        accel_s=0.15,
        cruise_s=0.1,
    )
    est = analyze_torque_velocity("X", tq, vel, 1000.0, j_m, rated)
    assert est.quality == "good", est
    assert abs(est.ratio_pct - truth["ratio_pct"]) / truth["ratio_pct"] < 0.15, (
        est.ratio_pct,
        truth["ratio_pct"],
    )


def test_analyze_short_stepped_no_mega_ratio() -> None:
    """Stepped 606C ramps must never explode into a mega-ratio.

    The physics fit integrates torque instead of differentiating the
    stair-stepped velocity, so a stepped trace either fails the fit gates
    (honest rejection) or produces a bounded, sane ratio — never the old
    104603%-style nonsense from a two-point dV/dt.
    """
    j_m = 5.9e-5
    rated = 1.27
    tq, vel = _stepped_accel_trace(
        friction_pct=8.9,
        peak_pct=28.6,
        peak_feed=8000.0,
        mid_feed=4000.0,
        plateau_ms=21,
        cruise_ms=200,
        cycles=5,
    )
    try:
        est = analyze_torque_velocity("X", tq, vel, 1000.0, j_m, rated)
    except GraphicalInertiaError:
        return  # honest rejection is fine
    assert -100.0 < est.ratio_pct < 600.0, est
    assert est.fit_err_frac is not None and est.fit_err_frac < 0.25, est


def test_analyze_rejects_tiny_move() -> None:
    tq = [5.0] * 50
    vel = [10.0] * 50
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

    def __init__(self, tq, vel, *, force_marginal: bool = False):
        self.tq = tq
        self.vel = vel
        self.written = None
        self.ratio = 100.0
        self.torque_limit_applied = None
        self.torque_limit_restored = None
        self.accel_applied = None
        self.accel_restored = None
        self.force_marginal = force_marginal
        self.feed_used = None

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

    def apply_torque_limit(self, axis, pct):
        self.torque_limit_applied = pct
        return {"max": 300.0}, ["max"]

    def restore_torque_limit(self, axis, previous):
        self.torque_limit_restored = previous

    def apply_id_accel(self, axis, accel):
        self.accel_applied = accel
        return {"ini.0.max_acceleration": 2942.0}

    def restore_id_accel(self, previous):
        self.accel_restored = previous

    def run_move_and_sample(self, axis, stroke, feed, cycles, hz, settle, cancel):
        self.feed_used = feed
        return list(self.tq), list(self.vel), {"aborted": False}


def test_tuner_writes_when_good(tmp: str) -> None:
    j_m = 1.0e-4
    j_l = 3.0e-4
    rated = 1.27
    tq, vel, truth = _trap_trace(
        j_total=j_m + j_l,
        j_motor=j_m,
        rated_nm=rated,
        friction_pct=4.0,
        peak_rpm=800.0,
        accel_s=0.15,
        cruise_s=0.08,
    )
    settings = AxisInertiaSettings(
        motor_inertia_kgm2=j_m,
        rated_torque_nm=rated,
        stroke=40.0,
        feed=8000.0,
        write_to_drive=True,
        id_accel_unit_s2=1111.0,
        auto_flatten=False,
    )
    io = _FakeIO(tq, vel)
    cfg = GraphicalInertiaConfig.for_axis("X", settings, sample_hz=1000.0)
    result = GraphicalInertiaTuner(cfg, io=io, journal_root=tmp).run()
    assert result.status == "ok", result.summary()
    assert io.written is not None
    assert io.accel_applied == 1111.0
    assert io.accel_restored is not None
    assert abs(io.written - truth["ratio_pct"]) / truth["ratio_pct"] < 0.25


def test_tuner_clamps_feed(tmp: str) -> None:
    j_m = 1.0e-4
    j_l = 3.0e-4
    rated = 1.27
    tq, vel, _truth = _trap_trace(
        j_total=j_m + j_l,
        j_motor=j_m,
        rated_nm=rated,
        friction_pct=4.0,
        peak_rpm=800.0,
        accel_s=0.15,
        cruise_s=0.08,
    )
    settings = AxisInertiaSettings(
        motor_inertia_kgm2=j_m,
        rated_torque_nm=rated,
        feed=50000.0,
        write_to_drive=False,
        id_accel_unit_s2=1111.0,
        auto_flatten=False,
    )
    io = _FakeIO(tq, vel)
    cfg = GraphicalInertiaConfig.for_axis("X", settings, sample_hz=1000.0)
    result = GraphicalInertiaTuner(cfg, io=io, journal_root=tmp).run()
    assert result.status == "ok", result.summary()
    assert io.feed_used == MAX_ID_FEED


def test_tuner_skips_write_when_marginal(tmp: str) -> None:
    """Short stepped ramp → analysis fails or marginal → no C00.06 write."""
    j_m = 5.9e-5
    rated = 1.27
    tq, vel = _stepped_accel_trace(
        friction_pct=8.9,
        peak_pct=18.2,
        peak_feed=3000.0,
        mid_feed=1290.0,
        plateau_ms=23,
        cruise_ms=200,
        cycles=1,
    )
    settings = AxisInertiaSettings(
        motor_inertia_kgm2=j_m,
        rated_torque_nm=rated,
        write_to_drive=True,
        id_accel_unit_s2=2942.0,
    )
    io = _FakeIO(tq, vel)
    cfg = GraphicalInertiaConfig.for_axis("X", settings, sample_hz=1000.0)
    result = GraphicalInertiaTuner(cfg, io=io, journal_root=tmp).run()
    assert io.written is None
    assert result.status in ("failed", "ok")
    if result.status == "ok":
        assert result.estimate is not None
        assert result.estimate.quality != "good"


def test_real_f10000_traces_cluster() -> None:
    """Stretched high-feed journals should land near the manual ~120% class."""
    root = os.path.abspath(
        os.path.join(HERE, "..", "..", "logs", "tuning", "graphical_inertia")
    )
    if not os.path.isdir(root):
        print("SKIP real_f10000 (no journals)")
        return
    ratios = []
    for name in sorted(os.listdir(root)):
        if "233454" in name or "230733" in name or "232140" in name:
            continue  # F3000 / unstretched — expect fail/marginal elsewhere
        path = os.path.join(root, name, "trace.csv")
        if not os.path.isfile(path):
            continue
        tq, vel, hz = [], [], 1000.0
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("# fs_hz="):
                    hz = float(line.split("=", 1)[1])
                    continue
                if line.startswith("t_s") or not line.strip():
                    continue
                _t, a, b = line.split(",")
                tq.append(float(a))
                vel.append(float(b))
        try:
            est = analyze_torque_velocity("X", tq, vel, hz, 5.9e-5, 1.27)
        except GraphicalInertiaError as exc:
            print(f"SKIP {name}: {exc}")
            continue
        print(
            f"{name}: ratio={est.ratio_pct:.1f}% q={est.quality} "
            f"dt={est.delta_t_s * 1000:.0f}ms"
        )
        # Only "good" estimates are trusted for the cluster check; marginal
        # (pair spread / SNR) is allowed to sit outside and must not write.
        if est.quality != "good":
            continue
        ratios.append(est.ratio_pct)
        assert 70.0 < est.ratio_pct < 220.0, est
    if not ratios:
        print("SKIP real_f10000 (no good-quality traces)")
        return
    med = sorted(ratios)[len(ratios) // 2]
    print(f"good cluster n={len(ratios)} med={med:.1f} range={min(ratios):.1f}-{max(ratios):.1f}")
    assert 80.0 < med < 180.0, (med, ratios)
    # Run-to-run can swing; quality gate (not this span) decides writes.
    assert (max(ratios) - min(ratios)) / med < 1.20, ratios


def test_unused_torque_limit_not_forced_as_tp() -> None:
    """Configured limit must not invent Tp when the plateau never rides it."""
    j_m = 1.0e-4
    j_l = 2.5e-4
    rated = 1.27
    tq, vel, truth = _trap_trace(
        j_total=j_m + j_l,
        j_motor=j_m,
        rated_nm=rated,
        friction_pct=5.0,
        peak_rpm=800.0,
        accel_s=0.15,
        cruise_s=0.1,
    )
    # Peak on this ideal trace is well below 50% — limit must be ignored for Tp.
    est = analyze_torque_velocity(
        "X", tq, vel, 1000.0, j_m, rated, torque_limit_pct=50.0
    )
    assert est.t_peak_pct < 40.0, est
    assert "unused" in " ".join(est.notes).lower(), est.notes
    assert abs(est.ratio_pct - truth["ratio_pct"]) / truth["ratio_pct"] < 0.2, (
        est.ratio_pct,
        truth["ratio_pct"],
    )
    assert est.accel_t0_s is not None and est.accel_t1_s is not None
    assert est.tp_plot_pct is not None and est.tf_plot_pct is not None


def test_bogus_limit_on_real_journal_no_longer_explodes() -> None:
    """Regression: 20260715_224143_X must not report ~100000% from unused 50% limit."""
    root = os.path.abspath(os.path.join(HERE, "..", ".."))
    path = os.path.join(
        root,
        "logs",
        "tuning",
        "graphical_inertia",
        "20260715_224143_X",
        "trace.csv",
    )
    if not os.path.isfile(path):
        print("SKIP bogus_limit_journal (trace missing)")
        return
    from a6_graphical_inertia import load_trace_csv

    _t, tq, vel, hz = load_trace_csv(path)
    try:
        est = analyze_torque_velocity(
            "X", tq, vel, hz, 5.9e-5, 1.27, torque_limit_pct=50.0
        )
    except GraphicalInertiaError as exc:
        # Honest rejection (Ta≈0 / Jα invisible) is fine — just not a fantasy mega-ratio.
        msg = str(exc).lower()
        assert "104" not in msg
        assert (
            "inertial" in msg
            or "invisible" in msg
            or "ta" in msg
        ), exc
        return
    assert est.ratio_pct < 5000.0, est
    assert est.t_peak_pct < 40.0, est
    assert "unused" in " ".join(est.notes).lower() or est.delta_rpm > 50.0


def test_soft_ramp_refuses_fake_cancel_when_ja_invisible() -> None:
    """F10000 soft ramp with Tp < cruise must NOT invent ~6% via cancel."""
    root = os.path.abspath(os.path.join(HERE, "..", ".."))
    path = os.path.join(
        root,
        "logs",
        "tuning",
        "graphical_inertia",
        "20260715_225733_X",
        "trace.csv",
    )
    if not os.path.isfile(path):
        # Fall back to the earlier soft-ramp journal.
        path = os.path.join(
            root,
            "logs",
            "tuning",
            "graphical_inertia",
            "20260715_224934_X",
            "trace.csv",
        )
    if not os.path.isfile(path):
        print("SKIP soft_ramp_ja_invisible (trace missing)")
        return
    from a6_graphical_inertia import load_trace_csv

    _t, tq, vel, hz = load_trace_csv(path)
    try:
        est = analyze_torque_velocity("X", tq, vel, hz, 5.9e-5, 1.27)
    except GraphicalInertiaError as exc:
        msg = str(exc).lower()
        assert "jα invisible" in msg or "ja invisible" in msg or "invisible" in msg, exc
        return
    # If analysis somehow succeeds, it must not be the bogus ~6% cancel result.
    assert est.ratio_pct > 30.0, est
    assert "cancel" not in " ".join(est.notes).lower() or est.ratio_pct > 30.0


if __name__ == "__main__":
    failed = 0
    cases = [
        ("physics_fit_pdo_holds", test_physics_fit_recovers_j_through_pdo_holds, False),
        ("rpm", test_unit_rpm, False),
        ("sigma_ii_worksheet", test_sigma_ii_worksheet_example, False),
        ("target_accel", test_target_id_accel, False),
        ("analyze", test_analyze_ideal_trace, False),
        ("short_stepped", test_analyze_short_stepped_no_mega_ratio, False),
        ("tiny", test_analyze_rejects_tiny_move, False),
        ("validate", test_settings_validate, False),
        ("unused_limit", test_unused_torque_limit_not_forced_as_tp, False),
        ("bogus_limit_journal", test_bogus_limit_on_real_journal_no_longer_explodes, False),
        ("soft_ramp_ja", test_soft_ramp_refuses_fake_cancel_when_ja_invisible, False),
        ("tuner", test_tuner_writes_when_good, True),
        ("clamp_feed", test_tuner_clamps_feed, True),
        ("no_write_marginal", test_tuner_skips_write_when_marginal, True),
        ("real_f10000", test_real_f10000_traces_cluster, False),
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
