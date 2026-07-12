#!/usr/bin/env python3
"""End-to-end tests for the one-click auto-tuner against the simulated plant.

No LinuxCNC / Qt / hardware required — only numpy. Run directly:

    python3 probe_basic/python/test_a6_auto_tune.py

Each scenario exercises a different branch of the state machine, mirroring
the failure modes documented in ONE_CLICK_TUNING.md.
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
    assert speed > plant.resonance_gain_threshold_hz, speed
    assert speed <= plant.critical_speed_hz, speed
    # Notch 3 landed on the plant resonance
    notch = io.params["notch3_freq_hz"]
    assert abs(notch - plant.resonance_hz) <= 0.15 * plant.resonance_hz, notch
    # Position followed, integral tightened
    assert io.params["pos_gain_rad_s"] > SIM_BASELINE["pos_gain_rad_s"]
    assert io.params["integral_ms"] < SIM_BASELINE["integral_ms"]
    # Backup + final presets saved
    names = [name for _axis, name, _params in io.presets_saved]
    assert any(n.startswith("pre_one_click_") for n in names), names
    assert any(n.startswith("one_click_") for n in names), names
    assert result.preset_name and result.preset_name.startswith("one_click_")

    # Journal artifacts exist and parse
    jdir = result.journal_dir
    assert jdir and os.path.isdir(jdir), jdir
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

    assert result.status == "improved", result.summary()
    speed = io.params["speed_gain_hz"]
    assert speed <= plant.critical_speed_hz, speed
    assert speed > SIM_BASELINE["speed_gain_hz"], speed
    # The notch attempt against hard instability was reverted
    assert io.params["notch3_freq_hz"] == SIM_BASELINE["notch3_freq_hz"]
    print(f"  low critical: backed off to {speed:.1f}Hz, notch reverted")


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
    ]
    tmp_root = tempfile.mkdtemp(prefix="one_click_test_")
    try:
        for test in tests:
            print(f"{test.__name__}:")
            test(os.path.join(tmp_root, test.__name__))
        print(f"{test_estimate_and_config.__name__}:")
        test_estimate_and_config()
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
