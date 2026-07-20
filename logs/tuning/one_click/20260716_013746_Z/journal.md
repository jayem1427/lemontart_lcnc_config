# One-click tune — axis Z

- started: 2026-07-16T01:37:46
- engine: a6_auto_tune v1.0
- profile: conservative
- stimulus: 4x 0<->10 mm @ F6000 (~3.3s per measurement)
- dry run: False

**[     0.0s | setup | config]** campaign configuration
```json
{
  "config": {
    "allow_notch": true,
    "axis": "Z",
    "backoff_ratio": 0.75,
    "dry_run": false,
    "ferr_abort_fallback": 0.8,
    "ferr_abort_ratio": 0.8,
    "gate_min_hz_cap": 120.0,
    "gate_min_hz_factor": 6.0,
    "gate_min_hz_floor": 25.0,
    "hf_fail": 0.35,
    "improvement_min_pct": 4.0,
    "integral_improve_min_pct": 0.5,
    "integral_min_ms": 3.0,
    "integral_peak_guard_pct": 10.0,
    "integral_skip_improved_pct": 30.0,
    "integral_step_ratio": 0.7,
    "keep_best_min_improve_pct": 1.0,
    "max_stall_steps": 2,
    "max_steps_per_phase": 6,
    "min_meaningful_rms": 0.0005,
    "min_prominence_ratio": 4.0,
    "min_resonance_amplitude": 0.001,
    "notch_depth_pct": 10.0,
    "notch_width_pct": 5.0,
    "pos_gain_max_rad_s": 250.0,
    "pos_step_ratio": 1.2,
    "pos_to_speed_ratio": 2.0,
    "profile": "conservative",
    "rescue_max_steps": 3,
    "resonance_vs_rms": 0.1,
    "ring_fail": 0.85,
    "sample_hz": 1000.0,
    "save_presets": true,
    "speed_gain_max_hz": 120.0,
    "speed_step_ratio": 1.15,
    "speed_vs_filter_cap": 0.25,
    "stimulus": {
      "axis": "Z",
      "cycles": 4,
      "dwell_s": 0.25,
      "feed": 6000.0,
      "settle_s": 0.5,
      "stroke": 10.0
    },
    "verify_hf_margin": 0.12
  }
}
```

**[     0.0s | preflight | machine]** machine ready
```json
{
  "feed_override": 1.0,
  "homed": true,
  "max_limit": 9999.0,
  "min_limit": -9999.0,
  "position": -54.60003662109375
}
```

**[     0.0s | preflight | stimulus]** stimulus direction +10 mm
```json
{
  "direction": 1.0,
  "spec": "4x 0<->10 mm @ F6000 (~3.3s per measurement)"
}
```

**[     1.6s | baseline | warning]** 2 SDO reads failed (they will never be written)
```json
{
  "failed": [
    "adaptive_notch_freq_hz",
    "adaptive_notch_amp_pct"
  ]
}
```

**[     1.6s | baseline | params]** baseline snapshot (44 keys)
```json
{
  "abort_ferr": 0.79998779296875,
  "values": {
    "adaptive_notch": 0.0,
    "adaptive_notch_times": 0.0,
    "damping_pct": 0.0,
    "following_error": 0.9999847412109375,
    "following_error_time_ms": 250.0,
    "gain_sw_mode": 0.0,
    "gain_sw_thresh": 10.0,
    "gain_sw_time_ms": 5.0,
    "gain_sw_width": 10.0,
    "inertia_ratio_pct": 150.0,
    "integral_2_ms": 2.0,
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch1_depth_pct": 100.0,
    "notch1_freq_hz": 8000.0,
    "notch1_width_pct": 0.0,
    "notch2_depth_pct": 100.0,
    "notch2_freq_hz": 8000.0,
    "notch2_width_pct": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "notch4_depth_pct": 100.0,
    "notch4_freq_hz": 8000.0,
    "notch4_width_pct": 0.0,
    "notch5_depth_pct": 100.0,
    "notch5_freq_hz": 8000.0,
    "notch5_width_pct": 0.0,
    "pdff_pct": 100.0,
    "pos_gain_2_rad_s": 144.0,
    "pos_gain_rad_s": 50.0,
    "speed_fb_filter": 0.0,
    "speed_fb_lpf_hz": 8000.0,
    "speed_ff_filter_hz": 318.0,
    "speed_ff_pct": 101.0,
    "speed_ff_source": 1.0,
    "speed_gain_2_hz": 30.0,
    "speed_gain_hz": 26.0,
    "stiffness_level": 14.0,
    "torque_ff_filter_hz": 318.0,
    "torque_ff_pct": 200.0,
    "torque_ff_source": 1.0,
    "torque_filter_2_hz": 420.0,
    "torque_filter_hz": 150.0
  }
}
```

**[     1.6s | baseline | backup]** baseline preset saved: pre_one_click_20260716_013748
```json
{
  "path": "/home/jon/linuxcnc/configs/ethercat_mill/config/tuning/presets/Z/pre_one_click_20260716_013748.json"
}
```

**[     5.7s | measure | measurement]** baseline: peak=0.04684 rms=0.01628 score=0.07940 stable
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260716_013746_Z/01_baseline.csv",
  "fft": {
    "gate_min_hz": 60.0,
    "gate_reason": "no strong resonance signature",
    "gate_stable": true,
    "hf_energy_ratio": 0.012733750247758262,
    "n_samples": 2155,
    "peak_abs": 0.046844482421875,
    "peaks": [],
    "ring_score": 0.14201934118403708,
    "rms": 0.016275699017023817
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 50.0,
    "speed_gain_hz": 26.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": 0.000152587890625,
    "tripped_ferr": null
  }
}
```

**[     5.7s | speed | cap]** speed gain capped at 37.5 Hz (0.25 x C01.03 torque filter 150 Hz)

**[     5.7s | speed | start]** speed ladder from 26.0 Hz, cap 37.5 Hz

**[     6.3s | speed | write]** SDO write speed_gain_hz=29.9
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[     6.6s | measure | measurement]** speed_29.9hz: peak=1.00342 rms=0.39357 score=1.79056 UNSTABLE [move aborted: FERR watchdog tripped at 1.0034 (limit 0.8000); short buffer (13); HF energy 92%]
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260716_013746_Z/02_speed_29.9hz.csv",
  "fft": {
    "gate_min_hz": 60.0,
    "gate_reason": "short buffer (13 samples); HF energy 92%",
    "gate_stable": false,
    "hf_energy_ratio": 0.9222509707113888,
    "n_samples": 13,
    "peak_abs": 1.00341796875,
    "peaks": [],
    "ring_score": 0.0,
    "rms": 0.39357290905657194
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 50.0,
    "speed_gain_hz": 29.9
  },
  "meta": {
    "abort_reason": "FERR watchdog tripped at 1.0034 (limit 0.8000)",
    "aborted": true,
    "position_drift": 1.322021484375,
    "tripped_ferr": 1.00341796875
  }
}
```

**[     6.6s | speed | backoff]** unstable at 29.9 Hz (move aborted: FERR watchdog tripped at 1.0034 (limit 0.8000); short buffer (13); HF energy 92%) — returning to 26.0 Hz

**[     6.7s | speed | write]** SDO write speed_gain_hz=26
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[     6.7s | position | start]** position ladder from 50.0 rad/s toward ~52.0 (cap 62.4)

**[     6.8s | position | write]** SDO write pos_gain_rad_s=60
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[     6.9s | measure | measurement]** pos_60.0rads: peak=0.00000 rms=0.00000 score=0.00000 UNSTABLE [move aborted: MDI leg reported RCS_ERROR; short buffer (11)]
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260716_013746_Z/03_pos_60.0rads.csv",
  "fft": {
    "gate_min_hz": 60.0,
    "gate_reason": "short buffer (11 samples)",
    "gate_stable": false,
    "hf_energy_ratio": 0.0,
    "n_samples": 11,
    "peak_abs": 0.0,
    "peaks": [],
    "ring_score": 0.0,
    "rms": 0.0
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 60.0,
    "speed_gain_hz": 26.0
  },
  "meta": {
    "abort_reason": "MDI leg reported RCS_ERROR",
    "aborted": true,
    "position_drift": -0.000152587890625,
    "tripped_ferr": null
  }
}
```

**[     6.9s | position | backoff]** unstable at 60.0 rad/s (move aborted: MDI leg reported RCS_ERROR; short buffer (11)) — returning to 50.0

**[     7.1s | position | write]** SDO write pos_gain_rad_s=50
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[     7.1s | integral | start]** integral tighten from 3.00 ms toward 3.00 ms (lower = stronger)

**[     7.1s | integral | skip]** already at/below floor

**[     7.2s | measure | measurement]** verify: peak=0.00000 rms=0.00000 score=0.00000 UNSTABLE [move aborted: MDI leg reported RCS_ERROR; short buffer (11)]
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260716_013746_Z/04_verify.csv",
  "fft": {
    "gate_min_hz": 60.0,
    "gate_reason": "short buffer (11 samples)",
    "gate_stable": false,
    "hf_energy_ratio": 0.0,
    "n_samples": 11,
    "peak_abs": 0.0,
    "peaks": [],
    "ring_score": 0.0,
    "rms": 0.0
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 50.0,
    "speed_gain_hz": 26.0
  },
  "meta": {
    "abort_reason": "MDI leg reported RCS_ERROR",
    "aborted": true,
    "position_drift": 0.0,
    "tripped_ferr": null
  }
}
```

**[     7.2s | verify | warning]** final tune unstable on verify (move aborted: MDI leg reported RCS_ERROR; short buffer (11)) — backing off speed & position by 0.75x

**[     7.4s | verify | write]** SDO write speed_gain_hz=19.5, pos_gain_rad_s=37.5
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz",
    "pos_gain_rad_s"
  ]
}
```

**[     7.6s | measure | measurement]** verify_backoff: peak=0.00000 rms=0.00000 score=0.00000 UNSTABLE [move aborted: MDI leg reported RCS_ERROR; short buffer (13)]
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260716_013746_Z/05_verify_backoff.csv",
  "fft": {
    "gate_min_hz": 60.0,
    "gate_reason": "short buffer (13 samples)",
    "gate_stable": false,
    "hf_energy_ratio": 0.0,
    "n_samples": 13,
    "peak_abs": 0.0,
    "peaks": [],
    "ring_score": 0.0,
    "rms": 0.0
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 37.5,
    "speed_gain_hz": 19.5
  },
  "meta": {
    "abort_reason": "MDI leg reported RCS_ERROR",
    "aborted": true,
    "position_drift": -7.62939453125e-05,
    "tripped_ferr": null
  }
}
```

**[     7.6s | verify | no-salvage]** verify failed but best only improved 0.0% (need ≥1%) — reverting

**[     7.6s | verify | revert]** still unstable after backoff and no salvageable best step — restoring baseline

**[     7.6s | verify | revert]** restoring baseline values for touched keys
```json
{
  "values": {
    "pos_gain_rad_s": 50.0,
    "speed_gain_hz": 26.0
  }
}
```

**[     7.8s | verify | write]** SDO write pos_gain_rad_s=50, speed_gain_hz=26
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s",
    "speed_gain_hz"
  ]
}
```

**[     7.8s | verify | revert-ok]** baseline restored

**[     7.9s | measure | measurement]** verify_baseline: peak=0.00000 rms=0.00000 score=0.00000 UNSTABLE [move aborted: MDI leg reported RCS_ERROR; short buffer (9)]
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260716_013746_Z/06_verify_baseline.csv",
  "fft": {
    "gate_min_hz": 60.0,
    "gate_reason": "short buffer (9 samples)",
    "gate_stable": false,
    "hf_energy_ratio": 0.0,
    "n_samples": 9,
    "peak_abs": 0.0,
    "peaks": [],
    "ring_score": 0.0,
    "rms": 0.0
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 50.0,
    "speed_gain_hz": 26.0
  },
  "meta": {
    "abort_reason": "MDI leg reported RCS_ERROR",
    "aborted": true,
    "position_drift": 7.62939453125e-05,
    "tripped_ferr": null
  }
}
```

**[     7.9s | verify | baseline-check]** verify_baseline: peak=0.00000 rms=0.00000 score=0.00000 UNSTABLE [move aborted: MDI leg reported RCS_ERROR; short buffer (9)]

**[     7.9s | finalize | result]** campaign status: reverted
```json
{
  "baseline_score": 0.07939588045592263,
  "baseline_values": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 50.0,
    "speed_gain_hz": 26.0
  },
  "final_score": 0.0,
  "final_values": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 50.0,
    "speed_gain_hz": 26.0
  },
  "improvement_pct": null,
  "measurements": 6,
  "notch_applied": false,
  "preset": null,
  "reason": "verify stayed unstable after backoff \u2014 baseline restored"
}
```


---

**FINAL STATUS: REVERTED** — 2026-07-16T01:37:54
