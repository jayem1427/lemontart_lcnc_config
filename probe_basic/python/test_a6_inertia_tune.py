#!/usr/bin/env python3
"""Tests for drive-internal inertia tune planning + state machine."""

from __future__ import annotations

import os
import sys
import tempfile

HERE = os.path.abspath(os.path.dirname(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from a6_inertia_tune import (  # noqa: E402
    InertiaTuneConfig,
    InertiaTuneError,
    InertiaTuner,
    plan_inertia_tune,
    revs_to_raw,
    units_to_revs,
)
from a6_inertia_tune_sim import SimInertiaIO  # noqa: E402


def test_plan_uses_soft_limit_room() -> None:
    plan = plan_inertia_tune(
        "X",
        position=0.0,
        min_limit=-254.0,
        max_limit=370.0,
        homed=True,
    )
    assert plan.revolutions == 2.0
    assert abs(plan.stroke_unit - 20.0) < 0.01


def test_plan_rejects_tight_envelope() -> None:
    try:
        plan_inertia_tune(
            "Y",
            position=5.0,
            min_limit=0.0,
            max_limit=15.0,
            homed=True,
        )
        raise AssertionError("expected InertiaTuneError")
    except InertiaTuneError as exc:
        msg = str(exc).lower()
        assert "safe room" in msg or "need" in msg


def test_plan_y_mid_travel_ok() -> None:
    plan = plan_inertia_tune(
        "Y",
        position=0.0,
        min_limit=-254.0,
        max_limit=308.0,
        homed=True,
    )
    assert plan.revolutions >= 0.5
    assert revs_to_raw(plan.revolutions) >= 50


def test_units_to_revs() -> None:
    assert abs(units_to_revs("X", 10.0) - 1.0) < 1e-9
    assert abs(units_to_revs("A", 360.0) - 1.0) < 1e-9


def test_happy_path(tmp: str) -> None:
    io = SimInertiaIO(result_ratio=420.0)
    cfg = InertiaTuneConfig.for_axis("X", timeout_s=5.0, poll_s=0.05)
    result = InertiaTuner(cfg, io=io, journal_root=tmp).run()
    assert result.status == "ok", result.summary()
    assert result.final_ratio_pct == 420.0
    assert result.baseline_ratio_pct == 100.0
    revs_writes = [w for w in io.writes if w[0] == 0x2007 and w[1] == 0x05]
    assert revs_writes, io.writes
    f30 = [w for w in io.writes if w[0] == 0x2030 and w[1] == 0x11]
    assert any(v == 1 for _, _, v in f30), f30
    assert io.sdos[(0x6065, 0x00)] == 13107


def test_f30_rejected(tmp: str) -> None:
    io = SimInertiaIO(f30_writable=False)
    cfg = InertiaTuneConfig.for_axis("X", timeout_s=2.0, poll_s=0.05)
    result = InertiaTuner(cfg, io=io, journal_root=tmp).run()
    assert result.status == "failed"
    assert "F30.10" in result.reason


def test_dry_run(tmp: str) -> None:
    io = SimInertiaIO()
    cfg = InertiaTuneConfig.for_axis("X", dry_run=True)
    result = InertiaTuner(cfg, io=io, journal_root=tmp).run()
    assert result.status == "dry-run"
    assert not any(w[0] == 0x2030 for w in io.writes)


def test_unhomed_fails(tmp: str) -> None:
    io = SimInertiaIO(homed=False)
    io.position = None
    io.min_limit = None
    io.max_limit = None
    cfg = InertiaTuneConfig.for_axis("X")
    result = InertiaTuner(cfg, io=io, journal_root=tmp).run()
    assert result.status == "failed"


if __name__ == "__main__":
    failed = 0
    cases = [
        ("plan_soft_limits", test_plan_uses_soft_limit_room, False),
        ("plan_tight", test_plan_rejects_tight_envelope, False),
        ("plan_y", test_plan_y_mid_travel_ok, False),
        ("units", test_units_to_revs, False),
        ("happy", test_happy_path, True),
        ("f30_reject", test_f30_rejected, True),
        ("dry_run", test_dry_run, True),
        ("unhomed", test_unhomed_fails, True),
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
