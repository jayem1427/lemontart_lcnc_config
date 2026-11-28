# One-click tune — axis Z

- started: 2026-11-27T23:38:45
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
  "position": -37.33341979980469
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

**[     1.8s | baseline | backup]** baseline preset saved: pre_one_click_20261127_233847
```json
{
  "path": "/home/jon/linuxcnc/configs/ethercat_mill/config/tuning/presets/Z/pre_one_click_20261127_233847.json"
}
```

**[     4.1s | baseline | ferr-window]** 6065 set to 1 mm for tuning (was 0.500031); production window is 0.5
```json
{
  "abort_ferr": 0.8,
  "prior": 0.500030517578125,
  "tuning": 1.0
}
```

**[     8.8s | measure | measurement]** baseline_1: peak=0.12192 rms=0.01971 score=0.16133 stable dom=69.0Hz tq=98%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233845_Z/01_baseline_1.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 69.0 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0017290259100842566,
    "ms": null,
    "n_samples": 4476,
    "peak_abs": 0.121917724609375,
    "peaks": [
      {
        "freq_hz": 69.03485254691688,
        "magnitude": 0.00035211728524543853,
        "prominence": 111.39462013402519
      },
      {
        "freq_hz": 67.02412868632707,
        "magnitude": 0.0003153107649139748,
        "prominence": 99.75063523870602
      },
      {
        "freq_hz": 68.14119749776586,
        "magnitude": 0.0002707597552972459,
        "prominence": 85.65663019892614
      },
      {
        "freq_hz": 70.15192135835568,
        "magnitude": 0.0002609017196478279,
        "prominence": 82.53797575494121
      },
      {
        "freq_hz": 71.0455764075067,
        "magnitude": 0.0002471426629698398,
        "prominence": 78.18520763968475
      }
    ],
    "ring_score": 0.08420921444925811,
    "rms": 0.019707321336422008,
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
    "position_drift": 0.0002288818359375,
    "tripped_ferr": null
  }
}
```

**[    13.5s | measure | measurement]** baseline_2: peak=0.04524 rms=0.01915 score=0.08354 stable dom=69.1Hz tq=43%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233845_Z/02_baseline_2.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 69.1 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0011463719476944851,
    "ms": null,
    "n_samples": 4484,
    "peak_abs": 0.0452423095703125,
    "peaks": [
      {
        "freq_hz": 69.13470115967885,
        "magnitude": 0.00023174694609007213,
        "prominence": 71.97105950715387
      },
      {
        "freq_hz": 67.12756467439786,
        "magnitude": 0.00019726017146797268,
        "prominence": 61.2608872679381
      },
      {
        "freq_hz": 71.36485280999108,
        "magnitude": 0.0001823735124874213,
        "prominence": 56.63770393185414
      },
      {
        "freq_hz": 68.01962533452274,
        "magnitude": 0.00016032606867089517,
        "prominence": 49.79067566386088
      },
      {
        "freq_hz": 61.10615521855486,
        "magnitude": 0.0001587770881606377,
        "prominence": 49.30962609509619
      }
    ],
    "ring_score": 0.02732453638700899,
    "rms": 0.019151260766850822,
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
    "position_drift": 0.0002288818359375,
    "tripped_ferr": null
  }
}
```

**[    18.2s | measure | measurement]** baseline_3: peak=0.04562 rms=0.01912 score=0.08387 stable dom=69.3Hz tq=43%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233845_Z/03_baseline_3.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 69.3 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0017010657224630521,
    "ms": null,
    "n_samples": 4485,
    "peak_abs": 0.045623779296875,
    "peaks": [
      {
        "freq_hz": 69.3422519509476,
        "magnitude": 0.00012888369006506877,
        "prominence": 40.612717024114644
      },
      {
        "freq_hz": 67.33556298773689,
        "magnitude": 0.00011930470998907386,
        "prominence": 37.59427142398008
      },
      {
        "freq_hz": 75.58528428093645,
        "magnitude": 0.0001169298911864755,
        "prominence": 36.84593900143088
      },
      {
        "freq_hz": 67.78149386845038,
        "magnitude": 0.00011323898945219668,
        "prominence": 35.68289387429026
      },
      {
        "freq_hz": 61.09253065774804,
        "magnitude": 0.0001090946433833142,
        "prominence": 34.37696327856825
      }
    ],
    "ring_score": 0.028167078382237202,
    "rms": 0.01912394780648285,
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

**[    18.2s | baseline | noise]** baseline spread 92.7% over 3 runs -> a step must improve the score by >= 15.0%
```json
{
  "improve_pct": 15.0,
  "scores": [
    0.161332367282219,
    0.08354483110401414,
    0.08387167490984071
  ],
  "spread_pct": 92.7458957530345
}
```

**[    19.4s | rest | standstill]** baseline: rest FERR rms 0.13 um, torque rms 12.50%
```json
{
  "ferr_peak": 0.0003814697265625,
  "ferr_rms": 0.00012661008542687958,
  "n": 1012.0,
  "torque_peak_pct": 14.0,
  "torque_rms_pct": 12.499436746203088
}
```

**[    19.4s | speed | cap]** speed gain capped at 37.5 Hz (0.25 x C01.03 torque filter 150 Hz)

**[    19.4s | speed | start]** speed ladder from 26.0 Hz, cap 37.5 Hz

**[    20.2s | speed | write]** SDO write speed_gain_hz=32.5
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    24.9s | measure | measurement]** speed_32.5hz: peak=0.04295 rms=0.01697 score=0.07689 stable dom=76.8Hz tq=44%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233845_Z/04_speed_32.5hz.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 76.8 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.002067413226320954,
    "ms": null,
    "n_samples": 4482,
    "peak_abs": 0.0429534912109375,
    "peaks": [
      {
        "freq_hz": 76.75145024542614,
        "magnitude": 0.00019316372650536747,
        "prominence": 57.19593425201376
      },
      {
        "freq_hz": 74.74341811691208,
        "magnitude": 0.00018057004022142064,
        "prominence": 53.46693364864688
      },
      {
        "freq_hz": 73.62784471218205,
        "magnitude": 0.0001356723165646403,
        "prominence": 40.17268168531599
      },
      {
        "freq_hz": 62.47211066488175,
        "magnitude": 0.00013457883550682141,
        "prominence": 39.84890106759689
      },
      {
        "freq_hz": 84.11423471664435,
        "magnitude": 0.00013442038782817092,
        "prominence": 39.80198458294197
      }
    ],
    "ring_score": 0.02973846745636402,
    "rms": 0.016967316518852225,
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
    "position_drift": 0.005035400390625,
    "tripped_ferr": null
  }
}
```

**[    24.9s | speed | stall]** 32.5 Hz stable but no 15.0% improvement (speed_32.5hz: peak=0.04295 rms=0.01697 score=0.07689 stable dom=76.8Hz tq=44%) — reverting to 26.0 Hz (stall 1/2)

**[    25.7s | speed | write]** SDO write speed_gain_hz=26
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    26.4s | speed | write]** SDO write speed_gain_hz=32.5
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    31.1s | measure | measurement]** speed_32.5hz: peak=0.04387 rms=0.01716 score=0.07819 stable dom=63.9Hz tq=44%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233845_Z/05_speed_32.5hz.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 63.9 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0017805603505525167,
    "ms": null,
    "n_samples": 4461,
    "peak_abs": 0.0438690185546875,
    "peaks": [
      {
        "freq_hz": 63.88702084734364,
        "magnitude": 0.00016490328866388686,
        "prominence": 51.49296482770956
      },
      {
        "freq_hz": 62.99036090562654,
        "magnitude": 0.00016057710156504375,
        "prominence": 50.142062720639544
      },
      {
        "freq_hz": 61.86953597848016,
        "magnitude": 0.000149553455129765,
        "prominence": 46.69980124262922
      },
      {
        "freq_hz": 75.09527011880743,
        "magnitude": 0.00014638263738202096,
        "prominence": 45.70967661817461
      },
      {
        "freq_hz": 76.21609504595382,
        "magnitude": 0.00014012906077351313,
        "prominence": 43.75692477824238
      }
    ],
    "ring_score": 0.029485641385849033,
    "rms": 0.017160656403150662,
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
    "position_drift": 0.0017547607421875,
    "tripped_ferr": null
  }
}
```

**[    31.1s | speed | stall]** 32.5 Hz stable but no 15.0% improvement (speed_32.5hz: peak=0.04387 rms=0.01716 score=0.07819 stable dom=63.9Hz tq=44%) — reverting to 26.0 Hz (stall 2/2)

**[    31.9s | speed | write]** SDO write speed_gain_hz=26
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    31.9s | position | start]** position ladder from 50.0 rad/s toward ~52.0 (cap 62.4)

**[    32.6s | position | write]** SDO write pos_gain_rad_s=60
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    37.2s | measure | measurement]** pos_60.0rads: peak=0.04318 rms=0.01678 score=0.07674 stable dom=76.9Hz tq=43%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233845_Z/06_pos_60.0rads.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 76.9 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0017355098484248689,
    "ms": null,
    "n_samples": 4446,
    "peak_abs": 0.043182373046875,
    "peaks": [
      {
        "freq_hz": 76.92307692307693,
        "magnitude": 0.00017330837349388277,
        "prominence": 58.02461311642206
      },
      {
        "freq_hz": 65.45209176788124,
        "magnitude": 0.00016300082606737973,
        "prominence": 54.573588566687185
      },
      {
        "freq_hz": 82.09626630679263,
        "magnitude": 0.000161539409657273,
        "prominence": 54.0842981758716
      },
      {
        "freq_hz": 63.42780026990554,
        "magnitude": 0.0001599847703167411,
        "prominence": 53.56379622636184
      },
      {
        "freq_hz": 74.67386414754836,
        "magnitude": 0.00015000347749846056,
        "prominence": 50.22200354487382
      }
    ],
    "ring_score": 0.030610722023144115,
    "rms": 0.016777097161256235,
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
    "position_drift": 0.0014495849609375,
    "tripped_ferr": null
  }
}
```

**[    37.3s | position | stall]** 60.0 rad/s stable but no improvement (pos_60.0rads: peak=0.04318 rms=0.01678 score=0.07674 stable dom=76.9Hz tq=43%) — reverting to 50.0 (stall 1/2)

**[    38.0s | position | write]** SDO write pos_gain_rad_s=50
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    38.8s | position | write]** SDO write pos_gain_rad_s=60
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    43.5s | measure | measurement]** pos_60.0rads: peak=0.04318 rms=0.01658 score=0.07635 stable dom=75.8Hz tq=43%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233845_Z/07_pos_60.0rads.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 75.8 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0019831569112858283,
    "ms": null,
    "n_samples": 4484,
    "peak_abs": 0.043182373046875,
    "peaks": [
      {
        "freq_hz": 75.82515611061552,
        "magnitude": 0.00013958609436584294,
        "prominence": 46.86683449656222
      },
      {
        "freq_hz": 68.68867082961641,
        "magnitude": 0.0001345555161794725,
        "prominence": 45.1777889196818
      },
      {
        "freq_hz": 67.35057983942909,
        "magnitude": 0.00013359522264056419,
        "prominence": 44.85536483753665
      },
      {
        "freq_hz": 69.35771632471008,
        "magnitude": 0.0001310522330724241,
        "prominence": 44.00154145521505
      },
      {
        "freq_hz": 87.19892952720785,
        "magnitude": 0.00012388042863415593,
        "prominence": 41.593566841575644
      }
    ],
    "ring_score": 0.030875309134653906,
    "rms": 0.016582650396617365,
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
    "position_drift": 0.0018310546875,
    "tripped_ferr": null
  }
}
```

**[    43.5s | position | stall]** 60.0 rad/s stable but no improvement (pos_60.0rads: peak=0.04318 rms=0.01658 score=0.07635 stable dom=75.8Hz tq=43%) — reverting to 50.0 (stall 2/2)

**[    44.3s | position | write]** SDO write pos_gain_rad_s=50
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    44.3s | integral | start]** integral tighten from 3.00 ms toward 3.00 ms (lower = stronger)

**[    44.3s | integral | skip]** already at/below floor

**[    44.3s | feedforward | start]** torque FF 200% (search 50-200%)

**[    45.0s | feedforward | write]** SDO write torque_ff_pct=173.9
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "torque_ff_pct"
  ]
}
```

**[    49.7s | measure | measurement]** ff_173.9pct: peak=0.04768 rms=0.01913 score=0.08594 stable dom=67.5Hz tq=44%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233845_Z/08_ff_173.9pct.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 67.5 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0020072344724345885,
    "ms": null,
    "n_samples": 4502,
    "peak_abs": 0.0476837158203125,
    "peaks": [
      {
        "freq_hz": 67.52554420257664,
        "magnitude": 0.00025482876493940334,
        "prominence": 83.12045661100011
      },
      {
        "freq_hz": 69.52465570857397,
        "magnitude": 0.00022952968586858067,
        "prominence": 74.86836228913411
      },
      {
        "freq_hz": 65.5264326965793,
        "magnitude": 0.00022159344714656933,
        "prominence": 72.27970717202302
      },
      {
        "freq_hz": 66.63705019991116,
        "magnitude": 0.000221404383790164,
        "prominence": 72.21803818219547
      },
      {
        "freq_hz": 68.63616170590849,
        "magnitude": 0.0002162798979933664,
        "prominence": 70.54652515882195
      }
    ],
    "ring_score": 0.028906701961067566,
    "rms": 0.019128138141141032,
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
    "torque_ff_pct": 173.9
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "capture": "realtime-sampler",
    "capture_error": null,
    "fs_hz": 1000.0,
    "machine_fault": false,
    "position_drift": 0.0019073486328125,
    "tripped_ferr": null
  }
}
```

**[    49.7s | feedforward | stall]** 173.9% no better — back to 200%

**[    50.5s | feedforward | write]** SDO write torque_ff_pct=200
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "torque_ff_pct"
  ]
}
```

**[    56.4s | rest | standstill]** verify: rest FERR rms 0.12 um, torque rms 11.59%
```json
{
  "ferr_peak": 0.00030517578125,
  "ferr_rms": 0.00011988704505817048,
  "n": 1008.0,
  "torque_peak_pct": 13.200000000000001,
  "torque_rms_pct": 11.59022448321984
}
```

**[    56.4s | measure | measurement]** verify: peak=0.04662 rms=0.01941 score=0.08544 UNSTABLE dom=69.1Hz tq=44% [standstill torque rms 11.6% > 5%]
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233845_Z/09_verify.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 69.1 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0020634049900325026,
    "ms": null,
    "n_samples": 4459,
    "peak_abs": 0.0466156005859375,
    "peaks": [
      {
        "freq_hz": 69.07378335949764,
        "magnitude": 0.00033965135627647675,
        "prominence": 109.23882827417418
      },
      {
        "freq_hz": 67.95245570755773,
        "magnitude": 0.00031469313310300903,
        "prominence": 101.2117528484672
      },
      {
        "freq_hz": 69.97084548104955,
        "magnitude": 0.0002768136299776163,
        "prominence": 89.02892931321372
      },
      {
        "freq_hz": 71.09217313298944,
        "magnitude": 0.00025142043405549194,
        "prominence": 80.8619577483735
      },
      {
        "freq_hz": 67.05539358600582,
        "magnitude": 0.00024945433387661356,
        "prominence": 80.22961968806118
      }
    ],
    "ring_score": 0.028864625653267095,
    "rms": 0.01941271907634491,
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
    "position_drift": 0.006103515625,
    "tripped_ferr": null
  }
}
```

**[    56.4s | verify | warning]** final tune unstable on verify (standstill torque rms 11.6% > 5%) — backing off speed & position by 0.75x

**[    57.2s | verify | write]** SDO write speed_gain_hz=19.5, pos_gain_rad_s=37.5
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

**[    63.0s | rest | standstill]** verify_backoff: rest FERR rms 0.48 um, torque rms 11.76%
```json
{
  "ferr_peak": 0.001068115234375,
  "ferr_rms": 0.00047747856476908896,
  "n": 1008.0,
  "torque_peak_pct": 14.700000000000001,
  "torque_rms_pct": 11.764532131361674
}
```

**[    63.1s | measure | measurement]** verify_backoff: peak=0.06371 rms=0.03035 score=0.12441 UNSTABLE dom=67.4Hz tq=44% [standstill torque rms 11.8% > 5%]
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233845_Z/10_verify_backoff.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 67.4 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0008034792828970022,
    "ms": null,
    "n_samples": 4465,
    "peak_abs": 0.0637054443359375,
    "peaks": [
      {
        "freq_hz": 67.41321388577828,
        "magnitude": 0.00036000698180487623,
        "prominence": 122.38200625648162
      },
      {
        "freq_hz": 68.53303471444569,
        "magnitude": 0.0003130068808800268,
        "prominence": 106.40463099391586
      },
      {
        "freq_hz": 69.42889137737963,
        "magnitude": 0.00030128120853545375,
        "prominence": 102.41856578195625
      },
      {
        "freq_hz": 66.51735722284435,
        "magnitude": 0.0002558178586564917,
        "prominence": 86.96359893260949
      },
      {
        "freq_hz": 70.54871220604704,
        "magnitude": 0.0002488436620533458,
        "prominence": 84.59276665585453
      }
    ],
    "ring_score": 0.023870042446912633,
    "rms": 0.030353664906831872,
    "sensitivity": "|S| n/a (only 0 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 37.5,
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
    "position_drift": 0.0066375732421875,
    "tripped_ferr": null
  }
}
```

**[    63.1s | verify | no-salvage]** verify failed but best only improved 0.0% (need ≥1%) — reverting

**[    63.1s | verify | revert]** still unstable after backoff and no salvageable best step — restoring baseline

**[    63.1s | verify | revert]** restoring baseline values for touched keys
```json
{
  "values": {
    "pos_gain_rad_s": 50.0,
    "speed_gain_hz": 26.0,
    "torque_ff_pct": 200.0
  }
}
```

**[    64.0s | verify | write]** SDO write pos_gain_rad_s=50, speed_gain_hz=26, torque_ff_pct=200
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

**[    64.0s | verify | revert-ok]** baseline restored

**[    69.9s | rest | standstill]** verify_baseline: rest FERR rms 0.13 um, torque rms 11.79%
```json
{
  "ferr_peak": 0.0003814697265625,
  "ferr_rms": 0.0001328654880591485,
  "n": 1006.0,
  "torque_peak_pct": 13.600000000000001,
  "torque_rms_pct": 11.791445242823839
}
```

**[    69.9s | measure | measurement]** verify_baseline: peak=0.04601 rms=0.01938 score=0.08476 UNSTABLE dom=69.1Hz tq=43% [standstill torque rms 11.8% > 5%]
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233845_Z/11_verify_baseline.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 69.1 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0011933628800022264,
    "ms": null,
    "n_samples": 4469,
    "peak_abs": 0.0460052490234375,
    "peaks": [
      {
        "freq_hz": 69.14298500783173,
        "magnitude": 0.0001954110568973849,
        "prominence": 60.66598781983209
      },
      {
        "freq_hz": 60.86372790333407,
        "magnitude": 0.00016852675405653478,
        "prominence": 52.31966998816431
      },
      {
        "freq_hz": 68.02416648019691,
        "magnitude": 0.00016753334583437883,
        "prominence": 52.01126322724555
      },
      {
        "freq_hz": 71.1568583575744,
        "magnitude": 0.00016339224246668656,
        "prominence": 50.72564443753188
      },
      {
        "freq_hz": 76.30342358469456,
        "magnitude": 0.00014577443657232423,
        "prominence": 45.256140230506354
      }
    ],
    "ring_score": 0.026663930060997466,
    "rms": 0.019376958448730976,
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
    "position_drift": 0.0055694580078125,
    "tripped_ferr": null
  }
}
```

**[    69.9s | verify | baseline-check]** verify_baseline: peak=0.04601 rms=0.01938 score=0.08476 UNSTABLE dom=69.1Hz tq=43% [standstill torque rms 11.8% > 5%]

**[    69.9s | finalize | result]** campaign status: reverted
```json
{
  "baseline_score": 0.08387167490984071,
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
  "final_score": 0.08475916592089945,
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
  "measurements": 11,
  "notch_applied": false,
  "preset": null,
  "reason": "verify stayed unstable after backoff \u2014 baseline restored"
}
```


---

**FINAL STATUS: REVERTED** — 2026-11-27T23:39:55
**[    70.3s | finalize | ferr-window]** 6065 restored to 0.5 production window

