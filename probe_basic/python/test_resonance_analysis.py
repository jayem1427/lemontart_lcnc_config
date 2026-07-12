#!/usr/bin/env python3
"""Smoke test for resonance_analysis (no LinuxCNC / Qt required)."""

from __future__ import annotations

import math
import os
import sys

HERE = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.insert(0, HERE)

from resonance_analysis import (  # noqa: E402
    analyze_ferr_resonance,
    format_resonance_text,
    suggest_manual_notch,
)


def _tone(freq_hz: float, fs: float = 1000.0, seconds: float = 1.0, amp: float = 1.0):
    n = int(fs * seconds)
    return [
        amp * math.sin(2.0 * math.pi * freq_hz * i / fs)
        for i in range(n)
    ]


def main() -> int:
    fs = 1000.0
    # Quiet buffer → should PASS gate (no strong peak relative to floor after noise).
    quiet = [0.0001 * math.sin(2 * math.pi * 3 * i / fs) for i in range(2000)]
    r_quiet = analyze_ferr_resonance(quiet, axis="X", fs_hz=fs)
    assert r_quiet.n_samples == 2000
    print("quiet:", r_quiet.summary_line())

    # Strong 120 Hz tone → dominant near 120, FAIL gate, notch suggestion.
    tone = _tone(120.0, fs=fs, seconds=2.0, amp=0.01)
    r_tone = analyze_ferr_resonance(tone, axis="X", fs_hz=fs)
    assert r_tone.dominant is not None
    assert abs(r_tone.dominant.freq_hz - 120.0) < 2.0
    assert not r_tone.stable
    assert "notch3_freq_hz" in r_tone.suggested_notch
    assert abs(r_tone.suggested_notch["notch3_freq_hz"] - 120.0) < 2.0
    print("tone:", r_tone.summary_line())
    print(format_resonance_text(r_tone).splitlines()[0:8])

    sug = suggest_manual_notch(250.0, notch_index=3)
    assert sug["notch3_freq_hz"] == 250.0
    print("suggest:", sug)

    # PARAM_DEFS must include notch keys.
    from a6_servo_tune import PARAM_BY_KEY

    for key in (
        "notch1_freq_hz",
        "notch3_freq_hz",
        "notch5_depth_pct",
        "adaptive_notch_freq_hz",
    ):
        assert key in PARAM_BY_KEY, key
        assert PARAM_BY_KEY[key]["group"] == "Notch"
    assert PARAM_BY_KEY["adaptive_notch_freq_hz"].get("writable") is False
    print("PARAM_DEFS notch catalog ok:", sum(1 for p in PARAM_BY_KEY if p.startswith("notch")))

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
