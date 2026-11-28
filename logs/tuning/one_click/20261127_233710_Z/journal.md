# One-click tune — axis Z

- started: 2026-11-27T23:37:10
- engine: a6_auto_tune v2.1
- profile: balanced
- stimulus: 4x 0<->10 mm @ F6000 (~3.3s per measurement)
- dry run: False

**[     0.0s | setup | config]** campaign configuration
```json
{
  "config": {
    "allow_notch": true,
    "allow_python_sampler": false,
    "axis": "Z",
    "backoff_ratio": 0.75,
    "baseline_repeats": 3,
    "dry_run": false,
    "ferr_abort_fallback": 0.8,
    "ferr_abort_ratio": 0.8,
    "ff_enabled": true,
    "ff_improve_min_pct": 3.0,
    "ff_max_pct": 200.0,
    "ff_min_pct": 50.0,
    "ff_step_ratio": 1.15,
    "frf_nperseg": 256,
    "gate_min_hz_cap": 120.0,
    "gate_min_hz_factor": 6.0,
    "gate_min_hz_floor": 25.0,
    "hf_fail": 0.35,
    "improvement_min_pct": 3.0,
    "integral_improve_min_pct": 0.5,
    "integral_min_ms": 3.0,
    "integral_peak_guard_pct": 10.0,
    "integral_skip_improved_pct": 0.0,
    "integral_step_ratio": 0.7,
    "keep_best_min_improve_pct": 1.0,
    "live_writes": false,
    "margin_ratio": 0.55,
    "max_noise_threshold_pct": 15.0,
    "max_stall_steps": 2,
    "max_steps_per_phase": 8,
    "min_meaningful_rms": 0.0005,
    "min_prominence_ratio": 4.0,
    "min_resonance_amplitude": 0.001,
    "ms_max": 0.0,
    "noise_k": 2.0,
    "notch_depth_pct": 10.0,
    "notch_width_pct": 5.0,
    "pos_gain_max_rad_s": 400.0,
    "pos_step_ratio": 1.2,
    "pos_to_speed_ratio": 2.0,
    "profile": "balanced",
    "rescue_max_steps": 3,
    "resonance_vs_rms": 0.1,
    "rest_capture_s": 1.0,
    "rest_ferr_rms_max": 0.002,
    "rest_torque_rms_max_pct": 5.0,
    "ring_fail": 0.85,
    "sample_hz": 1000.0,
    "save_presets": true,
    "settle_ferr": 0.02,
    "settle_hold_s": 0.3,
    "settle_timeout_s": 5.0,
    "speed_gain_max_hz": 200.0,
    "speed_step_ratio": 1.25,
    "speed_vs_filter_cap": 0.25,
    "stimulus": {
      "axis": "Z",
      "cycles": 4,
      "dwell_s": 0.25,
      "feed": 6000.0,
      "settle_s": 0.5,
      "stroke": 10.0
    },
    "torque_guard_drive_ratio": 0.8,
    "torque_guard_pct": 250.0,
    "verify_hf_margin": 0.12,
    "verify_offsets": []
  }
}
```

**[     0.0s | preflight | machine]** machine ready
```json
{
  "feed_override": 1.0,
  "homed": true,
  "max_limit": 400.0,
  "min_limit": -203.2,
  "opmode": null,
  "position": -37.272003173828125
}
```

**[     0.1s | preflight | info]** drive torque limit 0x6072 = 300% -> guard 240%

**[     0.1s | preflight | stimulus]** stimulus direction +10 mm
```json
{
  "direction": 1.0,
  "spec": "4x 0<->10 mm @ F6000 (~3.3s per measurement)"
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
  "abort_ferr": 0.4000244140625,
  "values": {
    "adaptive_notch": 0.0,
    "adaptive_notch_times": 0.0,
    "damping_pct": 0.0,
    "following_error": 0.500030517578125,
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
    "speed_fb_filter": 3.0,
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

**[     1.8s | baseline | backup]** baseline preset saved: pre_one_click_20261127_233712
```json
{
  "path": "/home/jon/linuxcnc/configs/ethercat_mill/config/tuning/presets/Z/pre_one_click_20261127_233712.json"
}
```

**[     3.9s | baseline | ferr-window]** 6065 set to 1 mm for tuning (was 0.500031); production window is 0.5
```json
{
  "abort_ferr": 0.8,
  "prior": 0.500030517578125,
  "tuning": 1.0
}
```

**[     8.7s | measure | measurement]** baseline_1: peak=0.40466 rms=0.02375 score=0.45216 stable dom=79.7Hz tq=198%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233710_Z/01_baseline_1.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 79.7 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0010543287157276406,
    "ms": null,
    "n_samples": 4494,
    "peak_abs": 0.4046630859375,
    "peaks": [
      {
        "freq_hz": 79.6617712505563,
        "magnitude": 0.00014514844036523465,
        "prominence": 44.521732395431634
      },
      {
        "freq_hz": 81.6644414775256,
        "magnitude": 0.00013941039119821298,
        "prominence": 42.76168668744374
      },
      {
        "freq_hz": 77.4365821094793,
        "magnitude": 0.00011265574006454235,
        "prominence": 34.55516779472185
      },
      {
        "freq_hz": 83.66711170449489,
        "magnitude": 0.00010594047270620823,
        "prominence": 32.49537758588997
      },
      {
        "freq_hz": 71.42857142857143,
        "magnitude": 0.00010565522772591207,
        "prominence": 32.407883702745714
      }
    ],
    "ring_score": 0.2642888575622417,
    "rms": 0.023747444356963587,
    "sensitivity": "|S| n/a (only 0 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 50.0,
    "speed_gain_hz": 26.0,
    "torque_ff_pct": 200.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "capture": "realtime-sampler",
    "capture_error": null,
    "fs_hz": 1000.0,
    "machine_fault": false,
    "position_drift": 7.62939453125e-05,
    "tripped_ferr": null
  }
}
```

**[    13.3s | measure | measurement]** baseline_2: peak=0.04921 rms=0.01919 score=0.08759 stable dom=81.6Hz tq=42%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233710_Z/02_baseline_2.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 81.6 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0013454686008426595,
    "ms": null,
    "n_samples": 4485,
    "peak_abs": 0.0492095947265625,
    "peaks": [
      {
        "freq_hz": 81.60535117056855,
        "magnitude": 0.000130091600282928,
        "prominence": 41.57805212529178
      },
      {
        "freq_hz": 79.59866220735785,
        "magnitude": 0.00012649691538053556,
        "prominence": 40.429169369444196
      },
      {
        "freq_hz": 83.61204013377926,
        "magnitude": 0.0001245170108666538,
        "prominence": 39.79638006635128
      },
      {
        "freq_hz": 77.59197324414714,
        "magnitude": 0.00011396448528906655,
        "prominence": 36.42372989090428
      },
      {
        "freq_hz": 74.47045707915272,
        "magnitude": 0.00010366249845025406,
        "prominence": 33.13115339213993
      }
    ],
    "ring_score": 0.02731817241295645,
    "rms": 0.01919250648220072,
    "sensitivity": "|S| n/a (only 1 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 50.0,
    "speed_gain_hz": 26.0,
    "torque_ff_pct": 200.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "capture": "realtime-sampler",
    "capture_error": null,
    "fs_hz": 1000.0,
    "machine_fault": false,
    "position_drift": 7.62939453125e-05,
    "tripped_ferr": null
  }
}
```

**[    18.0s | measure | measurement]** baseline_3: peak=0.04913 rms=0.01928 score=0.08769 stable dom=67.7Hz tq=43%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233710_Z/03_baseline_3.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 67.7 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0017118328493428735,
    "ms": null,
    "n_samples": 4502,
    "peak_abs": 0.04913330078125,
    "peaks": [
      {
        "freq_hz": 67.74766770324301,
        "magnitude": 0.00014656015219784776,
        "prominence": 49.304952171301366
      },
      {
        "freq_hz": 69.74677920924034,
        "magnitude": 0.00014553622530205898,
        "prominence": 48.96048837355897
      },
      {
        "freq_hz": 74.85561972456686,
        "magnitude": 0.0001225092235037745,
        "prominence": 41.21387235762964
      },
      {
        "freq_hz": 72.85650821856953,
        "magnitude": 0.00012235687752613005,
        "prominence": 41.16262097020539
      },
      {
        "freq_hz": 60.63971568191915,
        "magnitude": 0.0001144728886667844,
        "prominence": 38.510333238514434
      }
    ],
    "ring_score": 0.02764982655211897,
    "rms": 0.019277831697009962,
    "sensitivity": "|S| n/a (only 1 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 50.0,
    "speed_gain_hz": 26.0,
    "torque_ff_pct": 200.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "capture": "realtime-sampler",
    "capture_error": null,
    "fs_hz": 1000.0,
    "machine_fault": false,
    "position_drift": -7.62939453125e-05,
    "tripped_ferr": null
  }
}
```

**[    18.0s | baseline | noise]** baseline spread 415.7% over 3 runs -> a step must improve the score by >= 15.0%
```json
{
  "improve_pct": 15.0,
  "scores": [
    0.45215797465142715,
    0.08759460769096394,
    0.08768896417526992
  ],
  "spread_pct": 415.7460067971444
}
```

**[    19.2s | rest | standstill]** baseline: rest FERR rms 0.12 um, torque rms 13.35%
```json
{
  "ferr_peak": 0.0003814697265625,
  "ferr_rms": 0.00011553534901279297,
  "n": 1006.0,
  "torque_peak_pct": 15.100000000000001,
  "torque_rms_pct": 13.34508308496922
}
```

**[    19.2s | speed | cap]** speed gain capped at 37.5 Hz (0.25 x C01.03 torque filter 150 Hz)

**[    19.2s | speed | start]** speed ladder from 26.0 Hz, cap 37.5 Hz

**[    20.0s | speed | write]** SDO write speed_gain_hz=32.5
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    24.7s | measure | measurement]** speed_32.5hz: peak=0.04272 rms=0.01687 score=0.07647 stable dom=65.8Hz tq=43%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233710_Z/04_speed_32.5hz.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 65.8 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0021388319316130843,
    "ms": null,
    "n_samples": 4497,
    "peak_abs": 0.042724609375,
    "peaks": [
      {
        "freq_hz": 65.82165888370024,
        "magnitude": 0.00020607167104162542,
        "prominence": 66.24056469043771
      },
      {
        "freq_hz": 68.04536357571715,
        "magnitude": 0.00018145127108202104,
        "prominence": 58.32647738292421
      },
      {
        "freq_hz": 66.9335112297087,
        "magnitude": 0.0001760340040631464,
        "prominence": 56.58512776123528
      },
      {
        "freq_hz": 68.9348454525239,
        "magnitude": 0.00017440520088844372,
        "prominence": 56.061558259825794
      },
      {
        "freq_hz": 63.820324660885035,
        "magnitude": 0.00014692644267517312,
        "prominence": 47.22866797539958
      }
    ],
    "ring_score": 0.028684580749410167,
    "rms": 0.016874064683401704,
    "sensitivity": "|S| n/a (only 1 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 50.0,
    "speed_gain_hz": 32.5,
    "torque_ff_pct": 200.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "capture": "realtime-sampler",
    "capture_error": null,
    "fs_hz": 1000.0,
    "machine_fault": false,
    "position_drift": 0.0057220458984375,
    "tripped_ferr": null
  }
}
```

**[    24.7s | speed | stall]** 32.5 Hz stable but no 15.0% improvement (speed_32.5hz: peak=0.04272 rms=0.01687 score=0.07647 stable dom=65.8Hz tq=43%) — reverting to 26.0 Hz (stall 1/2)

**[    25.5s | speed | write]** SDO write speed_gain_hz=26
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    26.2s | speed | write]** SDO write speed_gain_hz=32.5
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    30.9s | measure | measurement]** speed_32.5hz: peak=0.04219 rms=0.01694 score=0.07608 stable dom=69.0Hz tq=44%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233710_Z/05_speed_32.5hz.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 69.0 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0020415864560476508,
    "ms": null,
    "n_samples": 4493,
    "peak_abs": 0.0421905517578125,
    "peaks": [
      {
        "freq_hz": 68.99621633652347,
        "magnitude": 0.0002650272330343791,
        "prominence": 83.52901416088139
      },
      {
        "freq_hz": 66.99310037836635,
        "magnitude": 0.00022775953265045118,
        "prominence": 71.78329943763711
      },
      {
        "freq_hz": 70.99933229468061,
        "magnitude": 0.00021345632020848592,
        "prominence": 67.27533540340508
      },
      {
        "freq_hz": 67.88337413754729,
        "magnitude": 0.00021207962446939053,
        "prominence": 66.84144022754137
      },
      {
        "freq_hz": 70.10905853549966,
        "magnitude": 0.0001988656750707803,
        "prominence": 62.6767807931107
      }
    ],
    "ring_score": 0.029664351091571485,
    "rms": 0.016944432935948807,
    "sensitivity": "|S| n/a (only 1 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 50.0,
    "speed_gain_hz": 32.5,
    "torque_ff_pct": 200.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "capture": "realtime-sampler",
    "capture_error": null,
    "fs_hz": 1000.0,
    "machine_fault": false,
    "position_drift": 0.0022125244140625,
    "tripped_ferr": null
  }
}
```

**[    30.9s | speed | stall]** 32.5 Hz stable but no 15.0% improvement (speed_32.5hz: peak=0.04219 rms=0.01694 score=0.07608 stable dom=69.0Hz tq=44%) — reverting to 26.0 Hz (stall 2/2)

**[    31.7s | speed | write]** SDO write speed_gain_hz=26
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    31.7s | position | start]** position ladder from 50.0 rad/s toward ~52.0 (cap 62.4)

**[    32.4s | position | write]** SDO write pos_gain_rad_s=60
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    37.1s | measure | measurement]** pos_60.0rads: peak=0.04051 rms=0.01642 score=0.07336 stable dom=69.4Hz tq=44%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233710_Z/06_pos_60.0rads.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 69.4 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.002177107237112212,
    "ms": null,
    "n_samples": 4465,
    "peak_abs": 0.0405120849609375,
    "peaks": [
      {
        "freq_hz": 69.42889137737963,
        "magnitude": 0.0002891278749692098,
        "prominence": 94.67796892241245
      },
      {
        "freq_hz": 66.29339305711086,
        "magnitude": 0.00025039331791852713,
        "prominence": 81.99393010720486
      },
      {
        "freq_hz": 71.44456886898097,
        "magnitude": 0.00023613096531603262,
        "prominence": 77.32357247875667
      },
      {
        "freq_hz": 68.30907054871221,
        "magnitude": 0.00022195658396236123,
        "prominence": 72.68202196260447
      },
      {
        "freq_hz": 67.41321388577828,
        "magnitude": 0.00020149228725097193,
        "prominence": 65.9807723917484
      }
    ],
    "ring_score": 0.03195630649484634,
    "rms": 0.016424819174850308,
    "sensitivity": "|S| n/a (only 1 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 60.0,
    "speed_gain_hz": 26.0,
    "torque_ff_pct": 200.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "capture": "realtime-sampler",
    "capture_error": null,
    "fs_hz": 1000.0,
    "machine_fault": false,
    "position_drift": 0.00152587890625,
    "tripped_ferr": null
  }
}
```

**[    37.1s | position | accept]** 60.0 rad/s accepted (pos_60.0rads: peak=0.04051 rms=0.01642 score=0.07336 stable dom=69.4Hz tq=44%)

**[    37.9s | position | write]** SDO write pos_gain_rad_s=62.4
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    42.6s | measure | measurement]** pos_62.4rads: peak=0.03754 rms=0.01576 score=0.06906 stable dom=62.7Hz tq=43%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233710_Z/07_pos_62.4rads.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 62.7 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0014193788089411439,
    "ms": null,
    "n_samples": 4484,
    "peak_abs": 0.03753662109375,
    "peaks": [
      {
        "freq_hz": 62.667261373773414,
        "magnitude": 0.00012410380512135815,
        "prominence": 40.53971480340728
      },
      {
        "freq_hz": 65.78947368421052,
        "magnitude": 0.00012336675639037888,
        "prominence": 40.298950667924935
      },
      {
        "freq_hz": 78.27832292595896,
        "magnitude": 0.00011908374670746073,
        "prominence": 38.899863904421245
      },
      {
        "freq_hz": 76.27118644067797,
        "magnitude": 0.00011611745901397416,
        "prominence": 37.93089718336696
      },
      {
        "freq_hz": 63.782337198929525,
        "magnitude": 0.0001131326201655982,
        "prominence": 36.9558705471654
      }
    ],
    "ring_score": 0.029888147041235567,
    "rms": 0.015763824404297837,
    "sensitivity": "|S| n/a (only 1 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 62.4,
    "speed_gain_hz": 26.0,
    "torque_ff_pct": 200.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "capture": "realtime-sampler",
    "capture_error": null,
    "fs_hz": 1000.0,
    "machine_fault": false,
    "position_drift": 0.00518798828125,
    "tripped_ferr": null
  }
}
```

**[    42.6s | position | stall]** 62.4 rad/s stable but no improvement (pos_62.4rads: peak=0.03754 rms=0.01576 score=0.06906 stable dom=62.7Hz tq=43%) — reverting to 60.0 (stall 1/2)

**[    43.4s | position | write]** SDO write pos_gain_rad_s=60
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    44.1s | position | write]** SDO write pos_gain_rad_s=62.4
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    48.8s | measure | measurement]** pos_62.4rads: peak=0.04051 rms=0.01584 score=0.07219 stable dom=75.8Hz tq=43%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233710_Z/08_pos_62.4rads.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 75.8 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0019241282914663695,
    "ms": null,
    "n_samples": 4486,
    "peak_abs": 0.0405120849609375,
    "peaks": [
      {
        "freq_hz": 75.79135086937139,
        "magnitude": 0.00014443477158560485,
        "prominence": 48.049229037638696
      },
      {
        "freq_hz": 62.41640659830585,
        "magnitude": 0.00012351621063143035,
        "prominence": 41.090234915996646
      },
      {
        "freq_hz": 73.78510922871155,
        "magnitude": 0.00012298024092316495,
        "prominence": 40.91193345169574
      },
      {
        "freq_hz": 74.67677218011592,
        "magnitude": 0.000122094885403057,
        "prominence": 40.61740153463454
      },
      {
        "freq_hz": 64.42264823896568,
        "magnitude": 0.00011727749610887063,
        "prominence": 39.0147968500511
      }
    ],
    "ring_score": 0.031152741457295106,
    "rms": 0.01583938284554401,
    "sensitivity": "|S| n/a (only 1 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 62.4,
    "speed_gain_hz": 26.0,
    "torque_ff_pct": 200.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "capture": "realtime-sampler",
    "capture_error": null,
    "fs_hz": 1000.0,
    "machine_fault": false,
    "position_drift": 0.0014495849609375,
    "tripped_ferr": null
  }
}
```

**[    48.8s | position | stall]** 62.4 rad/s stable but no improvement (pos_62.4rads: peak=0.04051 rms=0.01584 score=0.07219 stable dom=75.8Hz tq=43%) — reverting to 60.0 (stall 2/2)

**[    49.6s | position | write]** SDO write pos_gain_rad_s=60
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    49.6s | integral | start]** integral tighten from 3.00 ms toward 3.00 ms (lower = stronger)

**[    49.6s | integral | skip]** already at/below floor

**[    49.6s | feedforward | start]** torque FF 200% (search 50-200%)

**[    50.4s | feedforward | write]** SDO write torque_ff_pct=173.9
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "torque_ff_pct"
  ]
}
```

**[    55.1s | measure | measurement]** ff_173.9pct: peak=0.04326 rms=0.01621 score=0.07569 stable dom=72.7Hz tq=43%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233710_Z/09_ff_173.9pct.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 72.7 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0026403932421008042,
    "ms": null,
    "n_samples": 4484,
    "peak_abs": 0.0432586669921875,
    "peaks": [
      {
        "freq_hz": 72.70294380017842,
        "magnitude": 0.0002061958485793551,
        "prominence": 67.29958179721538
      },
      {
        "freq_hz": 74.71008028545941,
        "magnitude": 0.00019818539462694812,
        "prominence": 64.6850761962679
      },
      {
        "freq_hz": 76.71721677074041,
        "magnitude": 0.00019320079399996978,
        "prominence": 63.05816886552853
      },
      {
        "freq_hz": 70.69580731489741,
        "magnitude": 0.00018915397719564448,
        "prominence": 61.737341698456724
      },
      {
        "freq_hz": 78.94736842105263,
        "magnitude": 0.0001695872512380349,
        "prominence": 55.35102265682453
      }
    ],
    "ring_score": 0.03272195208867789,
    "rms": 0.01621369936016432,
    "sensitivity": "|S| n/a (only 1 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 60.0,
    "speed_gain_hz": 26.0,
    "torque_ff_pct": 173.9
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "capture": "realtime-sampler",
    "capture_error": null,
    "fs_hz": 1000.0,
    "machine_fault": false,
    "position_drift": 0.001373291015625,
    "tripped_ferr": null
  }
}
```

**[    55.1s | feedforward | stall]** 173.9% no better — back to 200%

**[    55.8s | feedforward | write]** SDO write torque_ff_pct=200
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "torque_ff_pct"
  ]
}
```

**[    61.7s | rest | standstill]** verify: rest FERR rms 0.09 um, torque rms 11.95%
```json
{
  "ferr_peak": 0.0002288818359375,
  "ferr_rms": 8.944254669914246e-05,
  "n": 1015.0,
  "torque_peak_pct": 13.200000000000001,
  "torque_rms_pct": 11.951003420576061
}
```

**[    61.8s | measure | measurement]** verify: peak=0.04280 rms=0.01666 score=0.07613 UNSTABLE dom=65.4Hz tq=43% [standstill torque rms 12.0% > 5%]
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233710_Z/10_verify.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 65.4 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.002097977992812915,
    "ms": null,
    "n_samples": 4452,
    "peak_abs": 0.0428009033203125,
    "peaks": [
      {
        "freq_hz": 65.36388140161725,
        "magnitude": 0.00015686723525498448,
        "prominence": 51.386263945909306
      },
      {
        "freq_hz": 84.45642407906558,
        "magnitude": 0.00015291512913349694,
        "prominence": 50.09164070625768
      },
      {
        "freq_hz": 82.43486073674752,
        "magnitude": 0.00014423836506229619,
        "prominence": 47.249323201047886
      },
      {
        "freq_hz": 76.1455525606469,
        "magnitude": 0.00013803972701380748,
        "prominence": 45.21878540042278
      },
      {
        "freq_hz": 74.12398921832884,
        "magnitude": 0.000137920746339893,
        "prominence": 45.17980994258231
      }
    ],
    "ring_score": 0.03142440680640097,
    "rms": 0.016662913631688384,
    "sensitivity": "|S| n/a (only 1 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 60.0,
    "speed_gain_hz": 26.0,
    "torque_ff_pct": 200.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "capture": "realtime-sampler",
    "capture_error": null,
    "fs_hz": 1000.0,
    "machine_fault": false,
    "position_drift": 0.0052642822265625,
    "tripped_ferr": null
  }
}
```

**[    61.8s | verify | warning]** final tune unstable on verify (standstill torque rms 12.0% > 5%) — backing off speed & position by 0.75x

**[    62.7s | verify | write]** SDO write speed_gain_hz=19.5, pos_gain_rad_s=45
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

**[    68.5s | rest | standstill]** verify_backoff: rest FERR rms 0.29 um, torque rms 13.02%
```json
{
  "ferr_peak": 0.0006103515625,
  "ferr_rms": 0.00028995606762160413,
  "n": 1007.0,
  "torque_peak_pct": 15.4,
  "torque_rms_pct": 13.022775481109255
}
```

**[    68.5s | measure | measurement]** verify_backoff: peak=0.06248 rms=0.02609 score=0.11466 UNSTABLE dom=66.4Hz tq=43% [standstill torque rms 13.0% > 5%]
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233710_Z/11_verify_backoff.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 66.4 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0010911167946528104,
    "ms": null,
    "n_samples": 4490,
    "peak_abs": 0.0624847412109375,
    "peaks": [
      {
        "freq_hz": 66.36971046770601,
        "magnitude": 0.000147351353627885,
        "prominence": 49.29121275654872
      },
      {
        "freq_hz": 84.85523385300668,
        "magnitude": 0.0001386413930383636,
        "prominence": 46.377601785566725
      },
      {
        "freq_hz": 64.14253897550111,
        "magnitude": 0.00013357808074502858,
        "prominence": 44.68384874320312
      },
      {
        "freq_hz": 82.85077951002226,
        "magnitude": 0.00012970476587286726,
        "prominence": 43.38816748384428
      },
      {
        "freq_hz": 68.37416481069042,
        "magnitude": 0.00012469734468732236,
        "prominence": 41.71311084580581
      }
    ],
    "ring_score": 0.02589348241510943,
    "rms": 0.026089805769226652,
    "sensitivity": "|S| n/a (only 1 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 45.0,
    "speed_gain_hz": 19.5,
    "torque_ff_pct": 200.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "capture": "realtime-sampler",
    "capture_error": null,
    "fs_hz": 1000.0,
    "machine_fault": false,
    "position_drift": 0.0054931640625,
    "tripped_ferr": null
  }
}
```

**[    68.5s | verify | keep-best]** verify unstable (standstill torque rms 12.0% > 5%); backoff failed (standstill torque rms 13.0% > 5%) — restoring best stable step (16.3% better than baseline)
```json
{
  "backoff_score": 0.1146643527493908,
  "baseline_score": 0.08768896417526992,
  "best_score": 0.07336172331063812,
  "best_values": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 60.0,
    "speed_gain_hz": 26.0,
    "torque_ff_pct": 200.0
  },
  "verify_score": 0.07612673058368927
}
```

**[    69.4s | verify | write]** SDO write speed_gain_hz=26, pos_gain_rad_s=60
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

**[    75.2s | rest | standstill]** verify_best: rest FERR rms 0.07 um, torque rms 12.84%
```json
{
  "ferr_peak": 0.00030517578125,
  "ferr_rms": 7.090337456472465e-05,
  "n": 1005.0,
  "torque_peak_pct": 13.9,
  "torque_rms_pct": 12.843209871406566
}
```

**[    75.3s | measure | measurement]** verify_best: peak=0.04257 rms=0.01628 score=0.07513 UNSTABLE dom=66.1Hz tq=44% [standstill torque rms 12.8% > 5%]
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233710_Z/12_verify_best.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 66.1 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.001978353413915035,
    "ms": null,
    "n_samples": 4496,
    "peak_abs": 0.042572021484375,
    "peaks": [
      {
        "freq_hz": 66.05871886120995,
        "magnitude": 0.0001813712905267035,
        "prominence": 59.88306932904979
      },
      {
        "freq_hz": 68.06049822064057,
        "magnitude": 0.0001811458196471382,
        "prominence": 59.80862596883837
      },
      {
        "freq_hz": 66.5035587188612,
        "magnitude": 0.00012681827526818013,
        "prominence": 41.87138740657987
      },
      {
        "freq_hz": 63.83451957295373,
        "magnitude": 0.00012130061070729805,
        "prominence": 40.049628910655755
      },
      {
        "freq_hz": 84.51957295373664,
        "magnitude": 0.00012120726643178871,
        "prominence": 40.01880958028895
      }
    ],
    "ring_score": 0.030164638832701447,
    "rms": 0.01628126184819587,
    "sensitivity": "|S| n/a (only 1 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 60.0,
    "speed_gain_hz": 26.0,
    "torque_ff_pct": 200.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "capture": "realtime-sampler",
    "capture_error": null,
    "fs_hz": 1000.0,
    "machine_fault": false,
    "position_drift": 0.005950927734375,
    "tripped_ferr": null
  }
}
```

**[    75.3s | verify | best-check]** verify_best: peak=0.04257 rms=0.01628 score=0.07513 UNSTABLE dom=66.1Hz tq=44% [standstill torque rms 12.8% > 5%]

**[    75.3s | verify | best-rejected]** best step failed its re-check: standstill torque rms 12.8% > 5%

**[    75.3s | verify | revert]** still unstable after backoff and no salvageable best step — restoring baseline

**[    75.3s | verify | revert]** restoring baseline values for touched keys
```json
{
  "values": {
    "pos_gain_rad_s": 50.0,
    "speed_gain_hz": 26.0,
    "torque_ff_pct": 200.0
  }
}
```

**[    76.2s | verify | write]** SDO write pos_gain_rad_s=50, speed_gain_hz=26, torque_ff_pct=200
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s",
    "speed_gain_hz",
    "torque_ff_pct"
  ]
}
```

**[    76.3s | verify | revert-ok]** baseline restored

**[    82.2s | rest | standstill]** verify_baseline: rest FERR rms 0.13 um, torque rms 12.10%
```json
{
  "ferr_peak": 0.0003814697265625,
  "ferr_rms": 0.00012701311328965499,
  "n": 1011.0,
  "torque_peak_pct": 13.8,
  "torque_rms_pct": 12.101482362542198
}
```

**[    82.2s | measure | measurement]** verify_baseline: peak=0.04730 rms=0.01914 score=0.08559 UNSTABLE dom=66.8Hz tq=44% [standstill torque rms 12.1% > 5%]
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233710_Z/13_verify_baseline.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 66.8 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0018968282134772683,
    "ms": null,
    "n_samples": 4505,
    "peak_abs": 0.04730224609375,
    "peaks": [
      {
        "freq_hz": 66.81465038845727,
        "magnitude": 0.0002386429464117339,
        "prominence": 78.33514537401666
      },
      {
        "freq_hz": 67.9245283018868,
        "magnitude": 0.00021999038483283992,
        "prominence": 72.2123952787362
      },
      {
        "freq_hz": 68.81243063263041,
        "magnitude": 0.00020398214684824134,
        "prominence": 66.95765103189879
      },
      {
        "freq_hz": 65.92674805771365,
        "magnitude": 0.00018371898966535502,
        "prominence": 60.306218892273215
      },
      {
        "freq_hz": 64.81687014428414,
        "magnitude": 0.00018260857842254403,
        "prominence": 59.941723618314995
      }
    ],
    "ring_score": 0.0283778331654898,
    "rms": 0.01914322096974806,
    "sensitivity": "|S| n/a (only 1 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 50.0,
    "speed_gain_hz": 26.0,
    "torque_ff_pct": 200.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "capture": "realtime-sampler",
    "capture_error": null,
    "fs_hz": 1000.0,
    "machine_fault": false,
    "position_drift": 0.0061798095703125,
    "tripped_ferr": null
  }
}
```

**[    82.2s | verify | baseline-check]** verify_baseline: peak=0.04730 rms=0.01914 score=0.08559 UNSTABLE dom=66.8Hz tq=44% [standstill torque rms 12.1% > 5%]

**[    82.2s | finalize | result]** campaign status: reverted
```json
{
  "baseline_score": 0.08768896417526992,
  "baseline_values": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 50.0,
    "speed_gain_hz": 26.0,
    "torque_ff_pct": 200.0
  },
  "final_score": 0.08558868803324612,
  "final_values": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 50.0,
    "speed_gain_hz": 26.0,
    "torque_ff_pct": 200.0
  },
  "improvement_pct": null,
  "measurements": 13,
  "notch_applied": false,
  "preset": null,
  "reason": "verify stayed unstable after backoff \u2014 baseline restored"
}
```


---

**FINAL STATUS: REVERTED** — 2026-11-27T23:38:32
**[    82.6s | finalize | ferr-window]** 6065 restored to 0.5 production window

