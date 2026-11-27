#!/usr/bin/env python3
"""End-to-end tests for the one-click auto-tuner against the simulated plant.

No LinuxCNC / Qt / hardware required — only numpy. Run directly:

    python3 probe_basic/python/test_a6_auto_tune.py

Each scenario exercises a different branch of the state machine, mirroring
the failure modes documented in docs/ONE_CLICK_TUNING.md.
"""

from __future__ import annotations

import glob
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.abspath(os.path.dirname(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from a6_auto_tune import (  # noqa: E402
    CORE_GAIN_KEYS,
    Measurement,
    OneClickConfig,
    OneClickTuner,
    StimulusSpec,
    estimate_campaign_seconds,
)
from a6_auto_tune_sim import SIM_BASELINE, SimPlant, SimTuneIO  # noqa: E402

# Short stimulus so each scenario runs in well under a second.
TEST_STIM = StimulusSpec("X", stroke=40.0, feed=3000.0, cycles=1,
                         dwell_s=0.05, settle_s=0.1)


def make_config(**overrides):
    defaults = dict(
        stimulus=TEST_STIM,
        max_steps_per_phase=10,
    )
    defaults.update(overrides)
    return OneClickConfig.for_axis("X", "balanced", **defaults)


def run_campaign(io, tmp, **cfg_overrides):
    cfg = make_config(**cfg_overrides)
    tuner = OneClickTuner(cfg, io=io, journal_root=tmp)
    result = tuner.run()
    return tuner, result


def _events(jdir):
    with open(os.path.join(jdir, "journal.json"), encoding="utf-8") as handle:
        return json.load(handle)["events"]


def _first_unstable(jdir, phase):
    for e in _events(jdir):
        if e["phase"] == phase and e["kind"] == "backoff":
            return (e.get("data") or {}).get("first_unstable")
    return None


def test_happy_path(tmp: str) -> None:
    """Ladder climbs, notch clears the resonance, verify passes, preset saved."""
    plant = SimPlant(instability_amp=1.2)  # force a FERR watchdog trip too
    io = SimTuneIO(plant=plant)
    _tuner, result = run_campaign(io, tmp)

    assert result.status == "improved", result.summary()
    assert result.final_score is not None and result.baseline_score is not None
    assert result.final_score < result.baseline_score * 0.5, result.summary()
    # Speed gain climbed past the resonance threshold (notch made that possible)
    speed = io.params["speed_gain_hz"]
    assert speed > SIM_BASELINE["speed_gain_hz"], speed
    # v2 margin rule: settle at margin_ratio x the first ringing speed gain
    first = _first_unstable(result.journal_dir, "speed")
    assert first is not None and first > plant.critical_speed_hz, first
    assert abs(speed - 0.55 * first) < 0.5, (speed, first)
    # Notch 3 landed on the plant resonance
    notch = io.params["notch3_freq_hz"]
    assert abs(notch - plant.resonance_hz) <= 0.15 * plant.resonance_hz, notch
    jdir = result.journal_dir
    assert jdir and os.path.isdir(jdir), jdir
    # Position followed; integral tightened or skipped when already ≥30% better
    assert io.params["pos_gain_rad_s"] > SIM_BASELINE["pos_gain_rad_s"]
    with open(os.path.join(jdir, "journal.json"), encoding="utf-8") as handle:
        integral_events = {
            (e["phase"], e["kind"])
            for e in json.load(handle)["events"]
            if e["phase"] == "integral"
        }
    if io.params["integral_ms"] < SIM_BASELINE["integral_ms"]:
        assert ("integral", "accept") in integral_events or (
            "integral",
            "done",
        ) in integral_events
    else:
        assert ("integral", "skip") in integral_events, integral_events
    # Backup + final presets saved
    names = [name for _axis, name, _params in io.presets_saved]
    assert any(n.startswith("pre_one_click_") for n in names), names
    assert any(n.startswith("one_click_") for n in names), names
    assert result.preset_name and result.preset_name.startswith("one_click_")

    # Journal artifacts exist and parse
    with open(os.path.join(jdir, "journal.json"), encoding="utf-8") as handle:
        data = json.load(handle)
    kinds = {(e["phase"], e["kind"]) for e in data["events"]}
    assert ("speed", "notch") in kinds, sorted(kinds)
    assert ("finalize", "result") in kinds
    md = open(os.path.join(jdir, "journal.md"), encoding="utf-8").read()
    assert "FINAL STATUS: IMPROVED" in md
    csvs = glob.glob(os.path.join(jdir, "*.csv"))
    assert len(csvs) >= 5, csvs
    print(f"  happy path: {result.reason}; speed={speed:.1f}Hz "
          f"pos={io.params['pos_gain_rad_s']:.1f} "
          f"integral={io.params['integral_ms']:.2f}ms notch3={notch:.0f}Hz "
          f"({result.measurements} measurements)")


def test_low_critical_backoff(tmp: str) -> None:
    """Hard instability just above baseline: notch cannot help, engine backs
    off to the last stable gain and reverts the useless notch."""
    plant = SimPlant(critical_speed_hz=30.0, resonance_gain_threshold_hz=60.0)
    io = SimTuneIO(plant=plant)
    _tuner, result = run_campaign(io, tmp)

    # v2: baseline (20 Hz) is within 1.6x of instability (~31 Hz), so the
    # margin rule lowers the gain below baseline and says so.
    assert result.status in ("margin-limited", "improved"), result.summary()
    speed = io.params["speed_gain_hz"]
    first = _first_unstable(result.journal_dir, "speed")
    assert first is not None and first > plant.critical_speed_hz, first
    assert abs(speed - 0.55 * first) < 0.5, (speed, first)
    assert result.preset_name, result.summary()
    # The notch attempt against hard instability was reverted
    assert io.params["notch3_freq_hz"] == SIM_BASELINE["notch3_freq_hz"]
    print(f"  low critical: {result.status}, margin {speed:.1f}Hz "
          f"(first ring {first:.1f}Hz), notch reverted")


def test_rescue_unstable_baseline(tmp: str) -> None:
    """Baseline already rings: engine softens speed gain before laddering."""
    plant = SimPlant(resonance_gain_threshold_hz=90.0, critical_speed_hz=300.0)
    io = SimTuneIO(plant=plant, baseline={"speed_gain_hz": 120.0})
    _tuner, result = run_campaign(io, tmp, allow_notch=False)

    assert result.status == "improved", result.summary()
    speed = io.params["speed_gain_hz"]
    assert speed <= plant.resonance_gain_threshold_hz + 0.01, speed
    with open(os.path.join(result.journal_dir, "journal.json"),
              encoding="utf-8") as handle:
        data = json.load(handle)
    phases = {e["phase"] for e in data["events"]}
    assert "rescue" in phases, sorted(phases)
    print(f"  rescue: softened 120 -> {speed:.1f}Hz, then finished ladder")


def test_write_failure_reverts(tmp: str) -> None:
    """A single SDO write failure aborts the campaign and restores baseline."""
    io = SimTuneIO(fail_write_calls={2})  # backup preset is not a write; this
    # kills an early ladder write while later (revert) writes succeed.
    _tuner, result = run_campaign(io, tmp)

    assert result.status == "failed", result.summary()
    for key in CORE_GAIN_KEYS:
        assert io.params[key] == SIM_BASELINE[key], (key, io.params[key])
    with open(os.path.join(result.journal_dir, "journal.json"),
              encoding="utf-8") as handle:
        data = json.load(handle)
    kinds = {e["kind"] for e in data["events"]}
    assert "exception" in kinds
    assert "revert-ok" in kinds
    print(f"  write failure: {result.reason}; baseline restored")


def test_revert_failure_is_critical(tmp: str) -> None:
    """When even the revert write fails, the journal must scream CRITICAL."""
    io = SimTuneIO(fail_writes_from=2)  # every write after the first fails
    _tuner, result = run_campaign(io, tmp)

    assert result.status == "failed", result.summary()
    with open(os.path.join(result.journal_dir, "journal.json"),
              encoding="utf-8") as handle:
        data = json.load(handle)
    kinds = {e["kind"] for e in data["events"]}
    assert "CRITICAL" in kinds, sorted(kinds)
    critical = [e for e in data["events"] if e["kind"] == "CRITICAL"]
    assert "speed_gain_hz" in critical[0]["message"]
    print("  revert failure: CRITICAL journaled with hand-restore values")


def test_cancel_reverts(tmp: str) -> None:
    """Operator cancel mid-ladder restores the baseline."""
    io = SimTuneIO()
    cfg = make_config()
    tuner = OneClickTuner(cfg, io=io, journal_root=tmp)

    seen = []

    def progress(phase: str, message: str) -> None:
        seen.append((phase, message))
        if phase == "speed":
            tuner.cancel()

    tuner._progress_fn = progress
    result = tuner.run()

    assert result.status == "cancelled", result.summary()
    for key in CORE_GAIN_KEYS:
        assert io.params[key] == SIM_BASELINE[key], (key, io.params[key])
    assert any(phase == "speed" for phase, _m in seen)
    print("  cancel: baseline restored after operator cancel")


def test_dry_run_writes_nothing(tmp: str) -> None:
    io = SimTuneIO()
    _tuner, result = run_campaign(io, tmp, dry_run=True)

    assert result.status == "dry-run", result.summary()
    assert io.write_calls == 0, io.write_calls
    assert result.baseline_score is not None
    print(f"  dry run: measured baseline (score {result.baseline_score:.5f}), "
          "0 SDO writes")


def test_preflight_failure(tmp: str) -> None:
    """A not-ready machine fails before anything is written or moved."""

    class NotReadyIO(SimTuneIO):
        def machine_ready(self):
            return False, "machine is not ON (turn it on first)"

    io = NotReadyIO()
    _tuner, result = run_campaign(io, tmp)
    assert result.status == "failed", result.summary()
    assert "preflight" in result.reason, result.reason
    assert io.write_calls == 0
    assert io.measure_calls == 0
    print(f"  preflight: blocked cleanly ({result.reason})")


def test_short_stroke_gate_not_fooled(tmp: str) -> None:
    """Regression: short fast strokes (Y default: 0.09s legs) push stimulus
    harmonics into the 30-60 Hz band with huge FFT prominence. The gate must
    treat those as forced motion, not resonance, or the ladder never starts.
    Found via this simulator — see docs/ONE_CLICK_TUNING.md lessons learned."""
    from a6_auto_tune import DEFAULT_STIMULI

    for axis in ("Y", "Z"):
        io = SimTuneIO()
        cfg = OneClickConfig.for_axis(axis, "balanced",
                                      stimulus=DEFAULT_STIMULI[axis])
        tuner = OneClickTuner(cfg, io=io, journal_root=tmp)
        gate_hz = tuner._gate_min_hz()
        assert gate_hz > 40.0, (axis, gate_hz)  # above the harmonic band
        result = tuner.run()
        assert result.status == "improved", (axis, result.summary())
    print("  short-stroke gate: Y/Z default stimuli tune clean "
          f"(gate floor {gate_hz:.0f} Hz)")


def test_verify_fail_keeps_best(tmp: str) -> None:
    """Regression: ladder finds a strong stable step, verify/backoff fail —
    engine must keep the best gains, not restore baseline (20260712 X run)."""
    plant = SimPlant(instability_amp=1.2)
    io = SimTuneIO(plant=plant)
    cfg = make_config()
    tuner = OneClickTuner(cfg, io=io, journal_root=tmp)
    real_measure = tuner._measure

    def measure(label: str) -> Measurement:
        m = real_measure(label)
        if not label.startswith("verify"):
            return m
        return Measurement(
            label=m.label,
            n_samples=m.n_samples,
            peak=m.peak,
            rms=m.rms,
            score=m.score * 2.0,
            unstable=True,
            unstable_why="HF energy 45%",
            aborted=m.aborted,
            abort_reason=m.abort_reason,
            dominant_hz=m.dominant_hz,
            dominant_mag=m.dominant_mag,
            report=m.report,
        )

    tuner._measure = measure  # type: ignore[method-assign]
    result = tuner.run()

    assert result.status == "improved", result.summary()
    assert result.preset_name and result.preset_name.startswith("one_click_")
    assert io.params["speed_gain_hz"] > SIM_BASELINE["speed_gain_hz"]
    assert io.params["pos_gain_rad_s"] > SIM_BASELINE["pos_gain_rad_s"]
    first = _first_unstable(result.journal_dir, "speed")
    assert first is not None, "ladder should have found the ring"
    assert io.params["speed_gain_hz"] <= 0.55 * first + 0.5, (
        io.params["speed_gain_hz"], first)
    with open(os.path.join(result.journal_dir, "journal.json"),
              encoding="utf-8") as handle:
        data = json.load(handle)
    kinds = {(e["phase"], e["kind"]) for e in data["events"]}
    assert ("verify", "keep-best") in kinds, sorted(kinds)
    print(
        f"  verify keep-best: {result.reason}; "
        f"speed={io.params['speed_gain_hz']:.1f}Hz"
    )


# ---------------------------------------------------------------- v2 tests


def test_machine_fault_stops(tmp: str) -> None:
    """2026-07-16 Z run: after a fault every move returned RCS_ERROR but the
    engine kept writing gains. v2 must stop at the first fault and revert."""
    io = SimTuneIO(fault_on_measure=5)
    _tuner, result = run_campaign(io, tmp)
    assert result.status == "failed", result.summary()
    assert "machine fault" in result.reason, result.reason
    assert io.measure_calls == 5, io.measure_calls  # nothing measured after it
    for key in CORE_GAIN_KEYS:
        assert io.params[key] == SIM_BASELINE[key], (key, io.params[key])
    kinds = {e["kind"] for e in _events(result.journal_dir)}
    assert "fault" in kinds and "revert-ok" in kinds, sorted(kinds)
    print(f"  machine fault: stopped after measure #{io.measure_calls}, reverted")


def test_baseline_repeats_set_threshold(tmp: str) -> None:
    io = SimTuneIO()
    _tuner, result = run_campaign(io, tmp, dry_run=True)
    assert io.measure_calls == 3, io.measure_calls
    noise = [e for e in _events(result.journal_dir)
             if e["phase"] == "baseline" and e["kind"] == "noise"]
    assert noise, "noise event missing"
    data = noise[0]["data"]
    assert data["improve_pct"] >= 3.0, data
    print(f"  repeats: spread {data['spread_pct']:.1f}% -> threshold "
          f"{data['improve_pct']:.1f}%")


def test_torque_guard(tmp: str) -> None:
    """A clipped torque hides instability: over the guard counts as unstable."""
    plant = SimPlant(torque_motion_pct=150.0)
    io = SimTuneIO(plant=plant)
    _tuner, result = run_campaign(io, tmp, torque_guard_pct=100.0)
    assert result.status == "failed", result.summary()
    msgs = " ".join(e["message"] for e in _events(result.journal_dir))
    assert "torque" in msgs and "guard" in msgs, msgs[:300]
    for key in CORE_GAIN_KEYS:
        assert io.params[key] == SIM_BASELINE[key], (key, io.params[key])
    print("  torque guard: over-guard torque blocked the run, baseline kept")


def test_rest_noise_gate(tmp: str) -> None:
    """Standstill hiss above the limit fails verify (needs realtime capture)."""
    plant = SimPlant(rest_torque_per_hz=0.1)  # ~8.7% rms at 82 Hz
    io = SimTuneIO(plant=plant)
    _tuner, result = run_campaign(io, tmp)
    verify = [e for e in _events(result.journal_dir)
              if e["kind"] == "measurement" and e["message"].startswith("verify")]
    assert verify, "no verify measurement"
    assert "standstill torque" in verify[0]["message"], verify[0]["message"]
    assert io.rest_calls >= 2, io.rest_calls
    # No gain within the margin is quiet enough at rest -> baseline restored
    assert result.status == "reverted", result.summary()
    for key in CORE_GAIN_KEYS:
        assert io.params[key] == SIM_BASELINE[key], (key, io.params[key])
    print(f"  rest gate: verify flagged standstill hiss -> {result.status}")


def test_true_fs_used(tmp: str) -> None:
    """FFT uses the capture's real rate: a 180 Hz resonance sampled at 500 Hz
    is still notched at ~180 Hz (the legacy bug put it at the wrong place)."""
    plant = SimPlant(instability_amp=1.2)
    io = SimTuneIO(plant=plant, sample_hz=500.0)
    _tuner, result = run_campaign(io, tmp)
    fs = {(e.get("data") or {}).get("fft", {}).get("fs_hz")
          for e in _events(result.journal_dir) if e["kind"] == "measurement"}
    assert fs == {500.0}, fs
    notch = io.params["notch3_freq_hz"]
    assert abs(notch - plant.resonance_hz) <= 0.15 * plant.resonance_hz, notch
    print(f"  true fs: 500 Hz capture, notch at {notch:.0f} Hz")


def test_ferr_window_via_io(tmp: str) -> None:
    io = SimTuneIO()
    _tuner, result = run_campaign(io, tmp)
    assert io.ferr_window_calls == ["relax", "restore"], io.ferr_window_calls
    print("  6065 window: relaxed and restored through the IO layer")


def test_estimate_and_config() -> None:
    cfg = OneClickConfig.for_axis("Z", "conservative")
    est = estimate_campaign_seconds(cfg)
    assert 30.0 < est < 3600.0, est
    for profile in ("conservative", "balanced", "aggressive"):
        OneClickConfig.for_axis("A", profile)
    try:
        OneClickConfig.for_axis("Q")
    except ValueError:
        pass
    else:
        raise AssertionError("axis Q should be rejected")
    print(f"  config: Z/conservative estimate ~{est / 60.0:.1f} min")


def test_feedforward_phase(tmp: str) -> None:
    """Torque FF climbs toward the plant's ideal when the source is on."""
    plant = SimPlant(torque_ff_ideal_pct=150.0)
    io = SimTuneIO(plant=plant, baseline={"torque_ff_source": 1.0,
                                          "torque_ff_pct": 100.0})
    _tuner, result = run_campaign(io, tmp)
    assert result.status in ("improved", "margin-limited"), result.summary()
    ff = io.params["torque_ff_pct"]
    assert 130.0 <= ff <= 175.0, ff
    accepts = [e for e in _events(result.journal_dir)
               if e["phase"] == "feedforward" and e["kind"] == "accept"]
    assert accepts, "no FF accept events"
    print(f"  feedforward: torque FF 100 -> {ff:g}% (ideal 150)")


def test_feedforward_skipped_when_source_off(tmp: str) -> None:
    io = SimTuneIO(plant=SimPlant(torque_ff_ideal_pct=150.0))
    _tuner, result = run_campaign(io, tmp)
    assert io.params["torque_ff_pct"] == SIM_BASELINE["torque_ff_pct"]
    skips = [e for e in _events(result.journal_dir)
             if e["phase"] == "feedforward" and e["kind"] == "skip"]
    assert skips, "FF phase should log a skip"
    print("  feedforward: source off -> untouched")


def test_drive_torque_limit_guard(tmp: str) -> None:
    """Guard = min(config, 0.8 x 0x6072)."""
    plant = SimPlant(torque_motion_pct=150.0)
    io = SimTuneIO(plant=plant)
    io.max_torque = 150.0  # -> guard 120 %, below the 150 % motion torque
    _tuner, result = run_campaign(io, tmp)
    assert result.status == "failed", result.summary()
    msgs = " ".join(e["message"] for e in _events(result.journal_dir))
    assert "0x6072 = 150% -> guard 120%" in msgs, msgs[:400]
    assert "guard 120%" in msgs
    print("  torque limit: 0x6072 150% -> guard 120%, run blocked")


def test_multi_position_verify(tmp: str) -> None:
    """A ring at another spot along travel reverts; start position restored."""
    plant = SimPlant(ring_at_offset={50.0: 0.02})
    io = SimTuneIO(plant=plant)
    _tuner, result = run_campaign(io, tmp, verify_offsets=(-50.0, 50.0))
    assert io.moves[-1] == 0.0, io.moves
    assert -50.0 in io.moves and 50.0 in io.moves, io.moves
    assert result.status == "reverted", result.summary()
    for key in CORE_GAIN_KEYS:
        assert io.params[key] == SIM_BASELINE[key], (key, io.params[key])
    ok_dir = tmp + "_ok"
    io2 = SimTuneIO(plant=SimPlant())
    _t, r2 = run_campaign(io2, ok_dir, verify_offsets=(-50.0, 50.0))
    assert r2.status in ("improved", "margin-limited"), r2.summary()
    assert io2.moves == [-50.0, 50.0, 0.0], io2.moves
    print("  multi-position: ring at +50 reverted; clean plant kept tune")


def test_sensitivity_estimator() -> None:
    """|S| from cmd vs ferr matches a sine sweep of the same discrete loop."""
    import math
    import numpy as np
    from frf_analysis import margins_from_ms, sensitivity
    fs, dt = 1000.0, 1e-3

    def run(r, kp=60.0, kv=150.0, ki=3000.0, m=1.0, b=0.5, delay=2):
        x = v = integ = 0.0
        buf = [0.0] * delay
        out = np.zeros(len(r))
        for i, ri in enumerate(r):
            e = ri - x
            out[i] = e
            ev = kp * e - v
            integ += ki * ev * dt
            buf.append(kv * ev + integ)
            u = buf.pop(0)
            v += (u - b * v) / m * dt
            x += v * dt
        return out

    rng = np.random.default_rng(1)
    r = np.cumsum(np.cumsum(np.repeat(rng.normal(0, 1, 600), 15))) * 5e-5
    rep = sensitivity(r, run(r), fs)
    assert rep.ok(), rep.reason
    assert abs(rep.ms - 1.39) < 0.1 and abs(rep.f_ms_hz - 25) < 6, rep.summary()
    gm, pm = margins_from_ms(2.0)
    assert abs(gm - 6.02) < 0.05 and abs(pm - 28.96) < 0.1, (gm, pm)
    flat = sensitivity([0.0] * 4000, [0.0] * 4000, fs)
    assert not flat.ok()
    print(f"  sensitivity: {rep.summary()} (true 1.39 @ 25 Hz)")


def main() -> int:
    tests = [
        test_happy_path,
        test_low_critical_backoff,
        test_rescue_unstable_baseline,
        test_write_failure_reverts,
        test_revert_failure_is_critical,
        test_cancel_reverts,
        test_dry_run_writes_nothing,
        test_preflight_failure,
        test_short_stroke_gate_not_fooled,
        test_verify_fail_keeps_best,
        test_machine_fault_stops,
        test_baseline_repeats_set_threshold,
        test_torque_guard,
        test_rest_noise_gate,
        test_true_fs_used,
        test_ferr_window_via_io,
        test_feedforward_phase,
        test_feedforward_skipped_when_source_off,
        test_drive_torque_limit_guard,
        test_multi_position_verify,
    ]
    tmp_root = tempfile.mkdtemp(prefix="one_click_test_")
    try:
        for test in tests:
            print(f"{test.__name__}:")
            test(os.path.join(tmp_root, test.__name__))
        print(f"{test_estimate_and_config.__name__}:")
        test_estimate_and_config()
        print("test_sensitivity_estimator:")
        test_sensitivity_estimator()
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
