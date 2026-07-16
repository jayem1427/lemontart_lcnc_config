# One-click tune — axis Y

- started: 2026-07-12T18:30:55
- engine: a6_auto_tune v1.0
- profile: aggressive
- stimulus: 4x 0<->15 mm @ F10000 (~3.2s per measurement)
- dry run: False

**[     0.0s | setup | config]** campaign configuration
```json
{
  "config": {
    "allow_notch": true,
    "axis": "Y",
    "backoff_ratio": 0.75,
    "dry_run": false,
    "ferr_abort_fallback": 0.8,
    "ferr_abort_ratio": 0.8,
    "gate_min_hz_cap": 120.0,
    "gate_min_hz_factor": 6.0,
    "gate_min_hz_floor": 25.0,
    "hf_fail": 0.35,
    "improvement_min_pct": 2.0,
    "integral_improve_min_pct": 0.5,
    "integral_min_ms": 1.0,
    "integral_peak_guard_pct": 10.0,
    "integral_skip_improved_pct": 30.0,
    "integral_step_ratio": 0.7,
    "keep_best_min_improve_pct": 1.0,
    "max_stall_steps": 2,
    "max_steps_per_phase": 10,
    "min_meaningful_rms": 0.0005,
    "min_prominence_ratio": 4.0,
    "min_resonance_amplitude": 0.001,
    "notch_depth_pct": 10.0,
    "notch_width_pct": 5.0,
    "pos_gain_max_rad_s": 800.0,
    "pos_step_ratio": 1.2,
    "pos_to_speed_ratio": 2.0,
    "profile": "aggressive",
    "rescue_max_steps": 3,
    "resonance_vs_rms": 0.1,
    "ring_fail": 0.85,
    "sample_hz": 1000.0,
    "save_presets": true,
    "speed_gain_max_hz": 400.0,
    "speed_step_ratio": 1.4,
    "speed_vs_filter_cap": 0.25,
    "stimulus": {
      "axis": "Y",
      "cycles": 4,
      "dwell_s": 0.25,
      "feed": 10000.0,
      "settle_s": 0.5,
      "stroke": 15.0
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
  "max_limit": 308.0,
  "min_limit": -254.0,
  "position": 107.17686462402344
}
```

**[     0.0s | preflight | stimulus]** stimulus direction +15 mm
```json
{
  "direction": 1.0,
  "spec": "4x 0<->15 mm @ F10000 (~3.2s per measurement)"
}
```

**[     1.8s | baseline | warning]** 2 SDO reads failed (they will never be written)
```json
{
  "failed": [
    "adaptive_notch_freq_hz",
    "adaptive_notch_amp_pct"
  ]
}
```

**[     1.8s | baseline | params]** baseline snapshot (44 keys)
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
    "inertia_ratio_pct": 100.0,
    "integral_2_ms": 4.0,
    "integral_ms": 3.5,
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
    "pos_gain_2_rad_s": 90.0,
    "pos_gain_rad_s": 60.0,
    "speed_fb_filter": 0.0,
    "speed_fb_lpf_hz": 8000.0,
    "speed_ff_filter_hz": 318.0,
    "speed_ff_pct": 100.0,
    "speed_ff_source": 1.0,
    "speed_gain_2_hz": 300.0,
    "speed_gain_hz": 60.0,
    "stiffness_level": 16.0,
    "torque_ff_filter_hz": 318.0,
    "torque_ff_pct": 125.0,
    "torque_ff_source": 1.0,
    "torque_filter_2_hz": 820.0,
    "torque_filter_hz": 920.0
  }
}
```

**[     1.8s | baseline | backup]** baseline preset saved: pre_one_click_20260712_183057
```json
{
  "path": "/home/jon/linuxcnc/configs/ethercat_mill/config/tuning/presets/Y/pre_one_click_20260712_183057.json"
}
```

**[     6.1s | measure | measurement]** baseline: peak=0.02159 rms=0.00514 score=0.03186 stable dom=70.7Hz
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_183055_Y/01_baseline.csv",
  "fft": {
    "gate_min_hz": 66.66666666666666,
    "gate_reason": "peak at 70.7 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.16953999954053306,
    "n_samples": 2460,
    "peak_abs": 0.0215911865234375,
    "peaks": [
      {
        "freq_hz": 70.73170731707317,
        "magnitude": 0.000416140118142564,
        "prominence": 5.999088951738792
      },
      {
        "freq_hz": 74.79674796747967,
        "magnitude": 0.0003920259436812712,
        "prominence": 5.651458258892486
      },
      {
        "freq_hz": 78.86178861788618,
        "magnitude": 0.00035847559286549837,
        "prominence": 5.167795352743864
      },
      {
        "freq_hz": 82.92682926829268,
        "magnitude": 0.0003318647946920914,
        "prominence": 4.7841732544189295
      },
      {
        "freq_hz": 86.58536585365853,
        "magnitude": 0.000321982348039112,
        "prominence": 4.641707594542979
      }
    ],
    "ring_score": 0.41068088006163533,
    "rms": 0.005136232852006136
  },
  "gains": {
    "integral_ms": 3.5,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 60.0,
    "speed_gain_hz": 60.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": 0.0,
    "tripped_ferr": null
  }
}
```

**[     6.1s | speed | cap]** speed gain capped at 230.0 Hz (0.25 x C01.03 torque filter 920 Hz)

**[     6.2s | speed | start]** speed ladder from 60.0 Hz, cap 230.0 Hz

**[     6.7s | speed | write]** SDO write speed_gain_hz=84
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    11.0s | measure | measurement]** speed_84.0hz: peak=0.01831 rms=0.00429 score=0.02688 stable dom=81.5Hz
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_183055_Y/02_speed_84.0hz.csv",
  "fft": {
    "gate_min_hz": 66.66666666666666,
    "gate_reason": "peak at 81.5 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.18274605037291947,
    "n_samples": 2307,
    "peak_abs": 0.018310546875,
    "peaks": [
      {
        "freq_hz": 81.49111400086693,
        "magnitude": 0.00039204287168247197,
        "prominence": 6.975838775754884
      },
      {
        "freq_hz": 77.15648027741656,
        "magnitude": 0.00038952149493670657,
        "prominence": 6.9309745046716875
      },
      {
        "freq_hz": 68.05374945817078,
        "magnitude": 0.0003778342684351642,
        "prominence": 6.7230171262844545
      },
      {
        "freq_hz": 72.38838318162115,
        "magnitude": 0.00036504167238652735,
        "prominence": 6.4953912873661865
      },
      {
        "freq_hz": 85.8257477243173,
        "magnitude": 0.00035187785351246335,
        "prominence": 6.261160072436497
      }
    ],
    "ring_score": 0.397305570356753,
    "rms": 0.004285818602952621
  },
  "gains": {
    "integral_ms": 3.5,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 60.0,
    "speed_gain_hz": 84.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": 0.0,
    "tripped_ferr": null
  }
}
```

**[    11.1s | speed | accept]** 84.0 Hz accepted (speed_84.0hz: peak=0.01831 rms=0.00429 score=0.02688 stable dom=81.5Hz)

**[    11.5s | speed | write]** SDO write speed_gain_hz=117.6
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    15.9s | measure | measurement]** speed_117.6hz: peak=0.01503 rms=0.00362 score=0.02228 stable dom=67.3Hz
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_183055_Y/03_speed_117.6hz.csv",
  "fft": {
    "gate_min_hz": 66.66666666666666,
    "gate_reason": "peak at 67.3 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.20594159922074873,
    "n_samples": 2318,
    "peak_abs": 0.0150299072265625,
    "peaks": [
      {
        "freq_hz": 67.29939603106125,
        "magnitude": 0.0003114391316505209,
        "prominence": 6.030955571434986
      },
      {
        "freq_hz": 71.6134598792062,
        "magnitude": 0.0002927408082335044,
        "prominence": 5.6688663336737815
      },
      {
        "freq_hz": 75.92752372735116,
        "magnitude": 0.0002776146495548905,
        "prominence": 5.375951341027436
      },
      {
        "freq_hz": 80.24158757549611,
        "magnitude": 0.00026456768617663315,
        "prominence": 5.123299543357047
      },
      {
        "freq_hz": 84.55565142364107,
        "magnitude": 0.00025484554784755786,
        "prominence": 4.935032307922439
      }
    ],
    "ring_score": 0.4039643224415088,
    "rms": 0.003624948466436012
  },
  "gains": {
    "integral_ms": 3.5,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 60.0,
    "speed_gain_hz": 117.6
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": -7.62939453125e-05,
    "tripped_ferr": null
  }
}
```

**[    15.9s | speed | accept]** 117.6 Hz accepted (speed_117.6hz: peak=0.01503 rms=0.00362 score=0.02228 stable dom=67.3Hz)

**[    16.4s | speed | write]** SDO write speed_gain_hz=164.64
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    20.8s | measure | measurement]** speed_164.6hz: peak=0.01297 rms=0.00318 score=0.01932 stable dom=98.1Hz
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_183055_Y/04_speed_164.6hz.csv",
  "fft": {
    "gate_min_hz": 66.66666666666666,
    "gate_reason": "peak at 98.1 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.2180194418232575,
    "n_samples": 2213,
    "peak_abs": 0.012969970703125,
    "peaks": [
      {
        "freq_hz": 98.05693628558518,
        "magnitude": 0.0002854654885828115,
        "prominence": 5.314597635611248
      },
      {
        "freq_hz": 93.53818346136465,
        "magnitude": 0.00028381388912651314,
        "prominence": 5.2838493072966894
      },
      {
        "freq_hz": 89.01943063714414,
        "magnitude": 0.00027935939349917066,
        "prominence": 5.200918610327177
      },
      {
        "freq_hz": 84.50067781292363,
        "magnitude": 0.00027901366130796243,
        "prominence": 5.194482009198712
      },
      {
        "freq_hz": 102.5756891098057,
        "magnitude": 0.00027769969870655833,
        "prominence": 5.170019568679644
      }
    ],
    "ring_score": 0.40523699487096343,
    "rms": 0.003176345120187905
  },
  "gains": {
    "integral_ms": 3.5,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 60.0,
    "speed_gain_hz": 164.64
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": -0.000152587890625,
    "tripped_ferr": null
  }
}
```

**[    20.8s | speed | accept]** 164.6 Hz accepted (speed_164.6hz: peak=0.01297 rms=0.00318 score=0.01932 stable dom=98.1Hz)

**[    21.3s | speed | write]** SDO write speed_gain_hz=230
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    22.1s | measure | measurement]** speed_230.0hz: peak=0.03586 rms=0.01877 score=0.07339 UNSTABLE dom=313.4Hz [move aborted: MDI leg reported RCS_ERROR; resonance peak 313.4 Hz (mag 0.008924, x4.1 floor, amp floor 0.001877); HF energy 93%; ring score 1.40]
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_183055_Y/05_speed_230.0hz.csv",
  "fft": {
    "gate_min_hz": 66.66666666666666,
    "gate_reason": "peak at 313.4 Hz; HF energy 93%; ring score 1.40",
    "gate_stable": false,
    "hf_energy_ratio": 0.9331692881910884,
    "n_samples": 217,
    "peak_abs": 0.035858154296875,
    "peaks": [
      {
        "freq_hz": 313.3640552995392,
        "magnitude": 0.008923692928613995,
        "prominence": 4.127774340342819
      },
      {
        "freq_hz": 253.4562211981567,
        "magnitude": 0.008902173372155549,
        "prominence": 4.117820179697072
      }
    ],
    "ring_score": 1.403847298127887,
    "rms": 0.018767352238899426
  },
  "gains": {
    "integral_ms": 3.5,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 60.0,
    "speed_gain_hz": 230.0
  },
  "meta": {
    "abort_reason": "MDI leg reported RCS_ERROR",
    "aborted": true,
    "position_drift": 15.150527954101562,
    "tripped_ferr": null
  }
}
```

**[    22.1s | speed | notch]** trying 3rd notch at 313 Hz (width 5%, depth 10%)
```json
{
  "suggestion": {
    "notch3_depth_pct": 10.0,
    "notch3_freq_hz": 313.0,
    "notch3_width_pct": 5.0
  }
}
```

**[    22.4s | speed | write]** SDO write notch3_freq_hz=313, notch3_width_pct=5, notch3_depth_pct=10
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "notch3_freq_hz",
    "notch3_width_pct",
    "notch3_depth_pct"
  ]
}
```

**[    22.5s | measure | measurement]** speed_230.0hz_notched: peak=0.00000 rms=0.00000 score=0.00000 UNSTABLE [move aborted: MDI leg reported RCS_ERROR; short buffer (11)]
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_183055_Y/06_speed_230.0hz_notched.csv",
  "fft": {
    "gate_min_hz": 66.66666666666666,
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
    "integral_ms": 3.5,
    "manual_mode": 0.0,
    "notch3_depth_pct": 10.0,
    "notch3_freq_hz": 313.0,
    "notch3_width_pct": 5.0,
    "pos_gain_rad_s": 60.0,
    "speed_gain_hz": 230.0
  },
  "meta": {
    "abort_reason": "MDI leg reported RCS_ERROR",
    "aborted": true,
    "position_drift": 0.0,
    "tripped_ferr": null
  }
}
```

**[    22.5s | speed | notch-revert]** notch did not help — restoring
```json
{
  "notch3_depth_pct": 100.0,
  "notch3_freq_hz": 8000.0,
  "notch3_width_pct": 0.0
}
```

**[    22.8s | speed | write]** SDO write notch3_freq_hz=8000, notch3_width_pct=0, notch3_depth_pct=100
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "notch3_freq_hz",
    "notch3_width_pct",
    "notch3_depth_pct"
  ]
}
```

**[    22.8s | speed | backoff]** unstable at 230.0 Hz (move aborted: MDI leg reported RCS_ERROR; resonance peak 313.4 Hz (mag 0.008924, x4.1 floor, amp floor 0.001877); HF energy 93%; ring score 1.40) — returning to 164.6 Hz

**[    22.9s | speed | write]** SDO write speed_gain_hz=164.64
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    22.9s | position | start]** position ladder from 60.0 rad/s toward ~329.3 (cap 395.1)

**[    23.1s | position | write]** SDO write pos_gain_rad_s=72
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    23.2s | measure | measurement]** pos_72.0rads: peak=0.00000 rms=0.00000 score=0.00000 UNSTABLE [move aborted: MDI leg reported RCS_ERROR; short buffer (11)]
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_183055_Y/07_pos_72.0rads.csv",
  "fft": {
    "gate_min_hz": 66.66666666666666,
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
    "integral_ms": 3.5,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 72.0,
    "speed_gain_hz": 164.64
  },
  "meta": {
    "abort_reason": "MDI leg reported RCS_ERROR",
    "aborted": true,
    "position_drift": 0.0,
    "tripped_ferr": null
  }
}
```

**[    23.2s | position | backoff]** unstable at 72.0 rad/s (move aborted: MDI leg reported RCS_ERROR; short buffer (11)) — returning to 60.0

**[    23.3s | position | write]** SDO write pos_gain_rad_s=60
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    23.3s | integral | skip]** best already 39.4% better than baseline (≥30%) — skipping integral tighten

**[    23.4s | measure | measurement]** verify: peak=0.00000 rms=0.00000 score=0.00000 UNSTABLE [move aborted: MDI leg reported RCS_ERROR; short buffer (15)]
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_183055_Y/08_verify.csv",
  "fft": {
    "gate_min_hz": 66.66666666666666,
    "gate_reason": "short buffer (15 samples)",
    "gate_stable": false,
    "hf_energy_ratio": 0.0,
    "n_samples": 15,
    "peak_abs": 0.0,
    "peaks": [],
    "ring_score": 0.0,
    "rms": 0.0
  },
  "gains": {
    "integral_ms": 3.5,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 60.0,
    "speed_gain_hz": 164.64
  },
  "meta": {
    "abort_reason": "MDI leg reported RCS_ERROR",
    "aborted": true,
    "position_drift": 0.0,
    "tripped_ferr": null
  }
}
```

**[    23.4s | verify | warning]** final tune unstable on verify (move aborted: MDI leg reported RCS_ERROR; short buffer (15)) — backing off speed & position by 0.75x

**[    23.6s | verify | write]** SDO write speed_gain_hz=123.48, pos_gain_rad_s=45
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

**[    23.8s | measure | measurement]** verify_backoff: peak=0.00000 rms=0.00000 score=0.00000 UNSTABLE [move aborted: MDI leg reported RCS_ERROR; short buffer (11)]
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_183055_Y/09_verify_backoff.csv",
  "fft": {
    "gate_min_hz": 66.66666666666666,
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
    "integral_ms": 3.5,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 45.0,
    "speed_gain_hz": 123.47999999999999
  },
  "meta": {
    "abort_reason": "MDI leg reported RCS_ERROR",
    "aborted": true,
    "position_drift": 0.0,
    "tripped_ferr": null
  }
}
```

**[    23.8s | verify | keep-best]** verify unstable (move aborted: MDI leg reported RCS_ERROR; short buffer (15)); backoff failed (MDI leg reported RCS_ERROR) — restoring best stable step (39.4% better than baseline)
```json
{
  "backoff_score": 0.0,
  "baseline_score": 0.031863652227449774,
  "best_score": 0.01932266094350081,
  "best_values": {
    "integral_ms": 3.5,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 60.0,
    "speed_gain_hz": 164.64
  },
  "verify_score": 0.0
}
```

**[    24.0s | verify | write]** SDO write speed_gain_hz=164.64, pos_gain_rad_s=60
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

**[    24.1s | measure | measurement]** verify_best: peak=0.00000 rms=0.00000 score=0.00000 UNSTABLE [move aborted: MDI leg reported RCS_ERROR; short buffer (15)]
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_183055_Y/10_verify_best.csv",
  "fft": {
    "gate_min_hz": 66.66666666666666,
    "gate_reason": "short buffer (15 samples)",
    "gate_stable": false,
    "hf_energy_ratio": 0.0,
    "n_samples": 15,
    "peak_abs": 0.0,
    "peaks": [],
    "ring_score": 0.0,
    "rms": 0.0
  },
  "gains": {
    "integral_ms": 3.5,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 60.0,
    "speed_gain_hz": 164.64
  },
  "meta": {
    "abort_reason": "MDI leg reported RCS_ERROR",
    "aborted": true,
    "position_drift": 0.000152587890625,
    "tripped_ferr": null
  }
}
```

**[    24.1s | verify | best-check]** verify_best: peak=0.00000 rms=0.00000 score=0.00000 UNSTABLE [move aborted: MDI leg reported RCS_ERROR; short buffer (15)]

**[    24.1s | finalize | preset]** final tune saved as preset one_click_20260712_183119
```json
{
  "path": "/home/jon/linuxcnc/configs/ethercat_mill/config/tuning/presets/Y/one_click_20260712_183119.json"
}
```

**[    24.2s | finalize | result]** campaign status: improved
```json
{
  "baseline_score": 0.031863652227449774,
  "baseline_values": {
    "integral_ms": 3.5,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 60.0,
    "speed_gain_hz": 60.0
  },
  "final_score": 0.01932266094350081,
  "final_values": {
    "integral_ms": 3.5,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 60.0,
    "speed_gain_hz": 164.64
  },
  "improvement_pct": 39.35829827173797,
  "measurements": 10,
  "notch_applied": false,
  "preset": "one_click_20260712_183119",
  "reason": "verify/backoff failed but best stable step kept (39.4% better than baseline)"
}
```


---

**FINAL STATUS: IMPROVED** — 2026-07-12T18:31:19
