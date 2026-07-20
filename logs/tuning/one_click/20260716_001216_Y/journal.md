# One-click tune — axis Y

- started: 2026-07-16T00:12:16
- engine: a6_auto_tune v1.0
- profile: conservative
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
  "position": 154.76101684570312
}
```

**[     0.0s | preflight | stimulus]** stimulus direction +15 mm
```json
{
  "direction": 1.0,
  "spec": "4x 0<->15 mm @ F10000 (~3.2s per measurement)"
}
```

**[     1.7s | baseline | warning]** 2 SDO reads failed (they will never be written)
```json
{
  "failed": [
    "adaptive_notch_freq_hz",
    "adaptive_notch_amp_pct"
  ]
}
```

**[     1.7s | baseline | params]** baseline snapshot (44 keys)
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
    "speed_gain_hz": 164.60000000000002,
    "stiffness_level": 16.0,
    "torque_ff_filter_hz": 318.0,
    "torque_ff_pct": 125.0,
    "torque_ff_source": 1.0,
    "torque_filter_2_hz": 820.0,
    "torque_filter_hz": 920.0
  }
}
```

**[     1.7s | baseline | backup]** baseline preset saved: pre_one_click_20260716_001218
```json
{
  "path": "/home/jon/linuxcnc/configs/ethercat_mill/config/tuning/presets/Y/pre_one_click_20260716_001218.json"
}
```

**[     5.6s | measure | measurement]** baseline: peak=0.02640 rms=0.00575 score=0.03790 stable
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260716_001216_Y/01_baseline.csv",
  "fft": {
    "gate_min_hz": 66.66666666666666,
    "gate_reason": "no strong resonance signature",
    "gate_stable": true,
    "hf_energy_ratio": 0.18717252594144715,
    "n_samples": 2187,
    "peak_abs": 0.026397705078125,
    "peaks": [],
    "ring_score": 0.3952125699588408,
    "rms": 0.00575094253889595
  },
  "gains": {
    "integral_ms": 3.5,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 60.0,
    "speed_gain_hz": 164.60000000000002
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": 0.0,
    "tripped_ferr": null
  }
}
```

**[     5.6s | speed | start]** speed ladder from 164.6 Hz, cap 120.0 Hz

**[     5.6s | speed | skip]** already at/above cap — nothing to climb

**[     5.6s | position | start]** position ladder from 60.0 rad/s toward ~329.2 (cap 250.0)

**[     6.1s | position | write]** SDO write pos_gain_rad_s=72
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    10.0s | measure | measurement]** pos_72.0rads: peak=0.02205 rms=0.00477 score=0.03158 stable dom=69.8Hz
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260716_001216_Y/02_pos_72.0rads.csv",
  "fft": {
    "gate_min_hz": 66.66666666666666,
    "gate_reason": "peak at 69.8 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.2234366181250684,
    "n_samples": 2207,
    "peak_abs": 0.0220489501953125,
    "peaks": [
      {
        "freq_hz": 69.77797915722701,
        "magnitude": 0.0004005226529275571,
        "prominence": 4.864016285093776
      },
      {
        "freq_hz": 74.30901676483916,
        "magnitude": 0.0003877971895533971,
        "prominence": 4.709476059628741
      },
      {
        "freq_hz": 78.84005437245129,
        "magnitude": 0.00036300062997397694,
        "prominence": 4.408342356635885
      },
      {
        "freq_hz": 83.37109198006344,
        "magnitude": 0.00034705501772807945,
        "prominence": 4.214696087010619
      },
      {
        "freq_hz": 87.90212958767557,
        "magnitude": 0.00034044445124331086,
        "prominence": 4.134416225682962
      }
    ],
    "ring_score": 0.46109981945874434,
    "rms": 0.004767312890333828
  },
  "gains": {
    "integral_ms": 3.5,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 72.0,
    "speed_gain_hz": 164.60000000000002
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": 7.62939453125e-05,
    "tripped_ferr": null
  }
}
```

**[    10.0s | position | accept]** 72.0 rad/s accepted (pos_72.0rads: peak=0.02205 rms=0.00477 score=0.03158 stable dom=69.8Hz)

**[    10.5s | position | write]** SDO write pos_gain_rad_s=86.4
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    14.4s | measure | measurement]** pos_86.4rads: peak=0.01854 rms=0.00390 score=0.02635 stable dom=74.9Hz
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260716_001216_Y/03_pos_86.4rads.csv",
  "fft": {
    "gate_min_hz": 66.66666666666666,
    "gate_reason": "peak at 74.9 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.2533982371272,
    "n_samples": 2190,
    "peak_abs": 0.0185394287109375,
    "peaks": [
      {
        "freq_hz": 74.88584474885845,
        "magnitude": 0.00035868201010566753,
        "prominence": 4.530870447511406
      },
      {
        "freq_hz": 84.01826484018265,
        "magnitude": 0.00035810101965197465,
        "prominence": 4.523531377240924
      },
      {
        "freq_hz": 88.58447488584476,
        "magnitude": 0.0003578097136852416,
        "prominence": 4.519851600841027
      },
      {
        "freq_hz": 79.45205479452055,
        "magnitude": 0.0003556599869739081,
        "prominence": 4.492696257243679
      },
      {
        "freq_hz": 70.31963470319636,
        "magnitude": 0.0003474243879313281,
        "prominence": 4.3886641863054505
      }
    ],
    "ring_score": 0.5465207152453965,
    "rms": 0.0039042437476720132
  },
  "gains": {
    "integral_ms": 3.5,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 86.39999999999999,
    "speed_gain_hz": 164.60000000000002
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": -7.62939453125e-05,
    "tripped_ferr": null
  }
}
```

**[    14.4s | position | accept]** 86.4 rad/s accepted (pos_86.4rads: peak=0.01854 rms=0.00390 score=0.02635 stable dom=74.9Hz)

**[    14.9s | position | write]** SDO write pos_gain_rad_s=103.68
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    18.8s | measure | measurement]** pos_103.7rads: peak=0.01617 rms=0.00319 score=0.02255 stable dom=70.1Hz
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260716_001216_Y/04_pos_103.7rads.csv",
  "fft": {
    "gate_min_hz": 66.66666666666666,
    "gate_reason": "peak at 70.1 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.3383961811222122,
    "n_samples": 2141,
    "peak_abs": 0.01617431640625,
    "peaks": [
      {
        "freq_hz": 70.06071929005137,
        "magnitude": 0.0003618719812843115,
        "prominence": 4.859600244053294
      },
      {
        "freq_hz": 74.73143390938813,
        "magnitude": 0.0003500454621917296,
        "prominence": 4.700781219533521
      },
      {
        "freq_hz": 88.27650630546474,
        "magnitude": 0.0003203419616331253,
        "prominence": 4.301891153351742
      },
      {
        "freq_hz": 101.82157870154133,
        "magnitude": 0.0003129042008063575,
        "prominence": 4.2020090232108815
      },
      {
        "freq_hz": 83.60579168612797,
        "magnitude": 0.00030808650813793055,
        "prominence": 4.13731194336466
      }
    ],
    "ring_score": 0.6048733228078254,
    "rms": 0.00318696524313163
  },
  "gains": {
    "integral_ms": 3.5,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 103.67999999999999,
    "speed_gain_hz": 164.60000000000002
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": -0.0003814697265625,
    "tripped_ferr": null
  }
}
```

**[    18.8s | position | accept]** 103.7 rad/s accepted (pos_103.7rads: peak=0.01617 rms=0.00319 score=0.02255 stable dom=70.1Hz)

**[    19.4s | position | write]** SDO write pos_gain_rad_s=124.416
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    23.2s | measure | measurement]** pos_124.4rads: peak=0.01595 rms=0.00248 score=0.02090 UNSTABLE dom=70.8Hz [HF energy 39%]
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260716_001216_Y/05_pos_124.4rads.csv",
  "fft": {
    "gate_min_hz": 66.66666666666666,
    "gate_reason": "peak at 70.8 Hz; HF energy 39%",
    "gate_stable": false,
    "hf_energy_ratio": 0.3919685989753965,
    "n_samples": 2175,
    "peak_abs": 0.0159454345703125,
    "peaks": [
      {
        "freq_hz": 70.80459770114942,
        "magnitude": 0.0002978764122925286,
        "prominence": 4.456539095254595
      },
      {
        "freq_hz": 75.40229885057471,
        "magnitude": 0.0002956399070704653,
        "prominence": 4.423078664862818
      },
      {
        "freq_hz": 79.99999999999999,
        "magnitude": 0.0002703651225556844,
        "prominence": 4.044941757521392
      }
    ],
    "ring_score": 0.6549297905754806,
    "rms": 0.002478312376673824
  },
  "gains": {
    "integral_ms": 3.5,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 124.41599999999998,
    "speed_gain_hz": 164.60000000000002
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": 0.0,
    "tripped_ferr": null
  }
}
```

**[    23.2s | position | backoff]** unstable at 124.4 rad/s (HF energy 39%) — returning to 103.7

**[    23.7s | position | write]** SDO write pos_gain_rad_s=103.68
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    23.7s | integral | skip]** best already 40.5% better than baseline (≥30%) — skipping integral tighten

**[    27.6s | measure | measurement]** verify: peak=0.01648 rms=0.00325 score=0.02298 stable dom=78.8Hz
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260716_001216_Y/06_verify.csv",
  "fft": {
    "gate_min_hz": 66.66666666666666,
    "gate_reason": "peak at 78.8 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.3080703504091746,
    "n_samples": 2171,
    "peak_abs": 0.0164794921875,
    "peaks": [
      {
        "freq_hz": 78.76554583141409,
        "magnitude": 0.00035813159667561287,
        "prominence": 4.385319215974288
      },
      {
        "freq_hz": 74.15937356057115,
        "magnitude": 0.0003547759331533799,
        "prominence": 4.3442291366208
      },
      {
        "freq_hz": 83.37171810225702,
        "magnitude": 0.00035098064375721656,
        "prominence": 4.297755841123632
      },
      {
        "freq_hz": 87.97789037309995,
        "magnitude": 0.00033124470133360953,
        "prominence": 4.056089346575262
      },
      {
        "freq_hz": 70.01381851681252,
        "magnitude": 0.00032794670530917827,
        "prominence": 4.015705405380469
      }
    ],
    "ring_score": 0.5598520799717147,
    "rms": 0.0032495590187080602
  },
  "gains": {
    "integral_ms": 3.5,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 103.67999999999999,
    "speed_gain_hz": 164.60000000000002
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": -7.62939453125e-05,
    "tripped_ferr": null
  }
}
```

**[    27.6s | verify | ok]** verify: peak=0.01648 rms=0.00325 score=0.02298 stable dom=78.8Hz

**[    27.6s | finalize | preset]** final tune saved as preset one_click_20260716_001244
```json
{
  "path": "/home/jon/linuxcnc/configs/ethercat_mill/config/tuning/presets/Y/one_click_20260716_001244.json"
}
```

**[    27.6s | finalize | result]** campaign status: improved
```json
{
  "baseline_score": 0.0378995901559169,
  "baseline_values": {
    "integral_ms": 3.5,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 60.0,
    "speed_gain_hz": 164.60000000000002
  },
  "final_score": 0.02297861022491612,
  "final_values": {
    "integral_ms": 3.5,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 103.67999999999999,
    "speed_gain_hz": 164.60000000000002
  },
  "improvement_pct": 39.369765925216235,
  "measurements": 6,
  "notch_applied": false,
  "preset": "one_click_20260716_001244",
  "reason": "score improved 39.4%"
}
```


---

**FINAL STATUS: IMPROVED** — 2026-07-16T00:12:44
