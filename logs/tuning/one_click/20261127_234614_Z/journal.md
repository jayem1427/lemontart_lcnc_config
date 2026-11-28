# One-click tune — axis Z

- started: 2026-11-27T23:46:14
- engine: a6_auto_tune v2.1
- profile: conservative
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
    "baseline_warmup": 1,
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
    "improvement_min_pct": 4.0,
    "integral_improve_min_pct": 0.5,
    "integral_min_ms": 3.0,
    "integral_peak_guard_pct": 10.0,
    "integral_skip_improved_pct": 0.0,
    "integral_step_ratio": 0.7,
    "keep_best_min_improve_pct": 1.0,
    "live_writes": false,
    "margin_ratio": 0.5,
    "max_noise_threshold_pct": 15.0,
    "max_stall_steps": 2,
    "max_steps_per_phase": 6,
    "min_meaningful_rms": 0.0005,
    "min_prominence_ratio": 4.0,
    "min_resonance_amplitude": 0.001,
    "ms_max": 0.0,
    "noise_k": 2.0,
    "notch_depth_pct": 10.0,
    "notch_width_pct": 5.0,
    "pos_gain_max_rad_s": 250.0,
    "pos_step_ratio": 1.2,
    "pos_to_speed_ratio": 2.0,
    "profile": "conservative",
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
  "position": -39.69486999511719
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

**[     1.8s | baseline | backup]** baseline preset saved: pre_one_click_20261127_234616
```json
{
  "path": "/home/jon/linuxcnc/configs/ethercat_mill/config/tuning/presets/Z/pre_one_click_20261127_234616.json"
}
```

**[     3.8s | baseline | ferr-window]** 6065 set to 1 mm for tuning (was 0.500031); production window is 0.5
```json
{
  "abort_ferr": 0.8,
  "prior": 0.500030517578125,
  "tuning": 1.0
}
```

**[     8.6s | measure | measurement]** warmup_1: peak=0.35202 rms=0.02274 score=0.39749 stable dom=61.0Hz tq=187%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_234614_Z/01_warmup_1.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 61.0 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.001035681587426704,
    "ms": null,
    "n_samples": 4477,
    "peak_abs": 0.352020263671875,
    "peaks": [
      {
        "freq_hz": 60.97833370560643,
        "magnitude": 0.00011164089808225062,
        "prominence": 33.7240781644484
      },
      {
        "freq_hz": 75.72034844762118,
        "magnitude": 0.00011076448602269926,
        "prominence": 33.4593347835881
      },
      {
        "freq_hz": 83.09135581862854,
        "magnitude": 0.00010816193144728623,
        "prominence": 32.67316452308187
      },
      {
        "freq_hz": 85.995085995086,
        "magnitude": 0.00010216542299875901,
        "prominence": 30.861760968419333
      },
      {
        "freq_hz": 70.13625195443377,
        "magnitude": 9.972169084766007e-05,
        "prominence": 30.123567210645017
      }
    ],
    "ring_score": 0.24101125487029806,
    "rms": 0.02273614141879807,
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
    "position_drift": 0.0,
    "tripped_ferr": null
  }
}
```

**[     8.6s | baseline | warmup]** warm-up move (not scored): warmup_1: peak=0.35202 rms=0.02274 score=0.39749 stable dom=61.0Hz tq=187%

**[    13.3s | measure | measurement]** baseline_1: peak=0.04906 rms=0.01899 score=0.08703 stable dom=60.4Hz tq=42%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_234614_Z/02_baseline_1.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 60.4 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0011259267048416633,
    "ms": null,
    "n_samples": 4489,
    "peak_abs": 0.0490570068359375,
    "peaks": [
      {
        "freq_hz": 60.36979282691022,
        "magnitude": 0.0001577088194673366,
        "prominence": 50.05105228481912
      },
      {
        "freq_hz": 62.59746045889953,
        "magnitude": 0.00013147887951025104,
        "prominence": 41.72662185249533
      },
      {
        "freq_hz": 61.48362664290487,
        "magnitude": 0.00012006522615906459,
        "prominence": 38.10434275250276
      },
      {
        "freq_hz": 68.83492982846958,
        "magnitude": 0.00011938889154786913,
        "prominence": 37.889698707221655
      },
      {
        "freq_hz": 67.72109601247493,
        "magnitude": 0.00011421487592102778,
        "prominence": 36.24765403567973
      }
    ],
    "ring_score": 0.026237560473001298,
    "rms": 0.018985328371270226,
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

**[    17.9s | measure | measurement]** baseline_2: peak=0.04890 rms=0.01893 score=0.08676 stable dom=65.6Hz tq=42%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_234614_Z/03_baseline_2.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 65.6 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0012190904105572797,
    "ms": null,
    "n_samples": 4497,
    "peak_abs": 0.0489044189453125,
    "peaks": [
      {
        "freq_hz": 65.59928841449856,
        "magnitude": 0.00020763994526001178,
        "prominence": 67.96760131727099
      },
      {
        "freq_hz": 67.60062263731376,
        "magnitude": 0.00017569462378884426,
        "prominence": 57.51081338571244
      },
      {
        "freq_hz": 63.59795419168334,
        "magnitude": 0.00015760906047613944,
        "prominence": 51.590794695200316
      },
      {
        "freq_hz": 64.70980653769179,
        "magnitude": 0.00014850340276711035,
        "prominence": 48.61020388390995
      },
      {
        "freq_hz": 76.71781187458305,
        "magnitude": 0.00012411206563396658,
        "prominence": 40.626091406011255
      }
    ],
    "ring_score": 0.02684072360235122,
    "rms": 0.01892886559502346,
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
    "position_drift": 0.0,
    "tripped_ferr": null
  }
}
```

**[    22.6s | measure | measurement]** baseline_3: peak=0.04723 rms=0.01902 score=0.08526 stable dom=63.6Hz tq=42%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_234614_Z/04_baseline_3.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 63.6 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0016852499652821474,
    "ms": null,
    "n_samples": 4497,
    "peak_abs": 0.0472259521484375,
    "peaks": [
      {
        "freq_hz": 63.59795419168334,
        "magnitude": 0.00024472190347034654,
        "prominence": 78.12648843038089
      },
      {
        "freq_hz": 64.70980653769179,
        "magnitude": 0.00023797008095365665,
        "prominence": 75.97099610928558
      },
      {
        "freq_hz": 65.59928841449856,
        "magnitude": 0.00022831071533403088,
        "prominence": 72.88728228708595
      },
      {
        "freq_hz": 66.711140760507,
        "magnitude": 0.00020113389136963334,
        "prominence": 64.2111899842722
      },
      {
        "freq_hz": 62.70847231487658,
        "magnitude": 0.0001596466833727915,
        "prominence": 50.966564841975455
      }
    ],
    "ring_score": 0.028340116281323262,
    "rms": 0.01901772908260158,
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

**[    22.6s | baseline | noise]** baseline spread 2.0% over 3 runs -> a step must improve the score by >= 4.1%
```json
{
  "improve_pct": 4.071483387817688,
  "scores": [
    0.08702766357847795,
    0.08676215013535943,
    0.08526141031364065
  ],
  "spread_pct": 2.035741693908844
}
```

**[    23.8s | rest | standstill]** baseline: rest FERR rms 0.13 um, torque rms 0.37% (about mean 12.2%)
```json
{
  "ferr_peak": 0.000457763671875,
  "ferr_rms": 0.00013166294690170424,
  "n": 1007.0,
  "torque_mean_pct": 12.20307845084409,
  "torque_peak_pct": 13.5,
  "torque_rms_pct": 0.3651127300748963
}
```

**[    23.8s | speed | cap]** speed gain capped at 37.5 Hz (0.25 x C01.03 torque filter 150 Hz)

**[    23.8s | speed | start]** speed ladder from 26.0 Hz, cap 37.5 Hz

**[    24.6s | speed | write]** SDO write speed_gain_hz=29.9
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    29.3s | measure | measurement]** speed_29.9hz: peak=0.04326 rms=0.01760 score=0.07847 stable dom=64.8Hz tq=42%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_234614_Z/05_speed_29.9hz.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 64.8 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0018604385051827121,
    "ms": null,
    "n_samples": 4474,
    "peak_abs": 0.0432586669921875,
    "peaks": [
      {
        "freq_hz": 64.81895395619132,
        "magnitude": 0.0002652099717812126,
        "prominence": 80.74986619203663
      },
      {
        "freq_hz": 63.70138578453285,
        "magnitude": 0.00025045290628952684,
        "prominence": 76.25670533598937
      },
      {
        "freq_hz": 66.83057666517657,
        "magnitude": 0.00024192571709341979,
        "prominence": 73.66038747525724
      },
      {
        "freq_hz": 65.7130084935181,
        "magnitude": 0.00023889216909111225,
        "prominence": 72.73674726056903
      },
      {
        "freq_hz": 62.80733124720607,
        "magnitude": 0.00017756064637803955,
        "prominence": 54.06281799926622
      }
    ],
    "ring_score": 0.02883600871491236,
    "rms": 0.017603722813115157,
    "sensitivity": "|S| n/a (only 1 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 50.0,
    "speed_gain_hz": 29.9,
    "torque_ff_pct": 200.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "capture": "realtime-sampler",
    "capture_error": null,
    "fs_hz": 1000.0,
    "machine_fault": false,
    "position_drift": 0.00640869140625,
    "tripped_ferr": null
  }
}
```

**[    29.3s | speed | accept]** 29.9 Hz accepted (speed_29.9hz: peak=0.04326 rms=0.01760 score=0.07847 stable dom=64.8Hz tq=42%)

**[    30.0s | speed | write]** SDO write speed_gain_hz=34.385
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    34.7s | measure | measurement]** speed_34.4hz: peak=0.04143 rms=0.01632 score=0.07406 stable dom=65.8Hz tq=42%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_234614_Z/06_speed_34.4hz.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 65.8 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.001643136038373973,
    "ms": null,
    "n_samples": 4501,
    "peak_abs": 0.0414276123046875,
    "peaks": [
      {
        "freq_hz": 65.7631637413908,
        "magnitude": 0.00017874697689441264,
        "prominence": 55.18801038930482
      },
      {
        "freq_hz": 64.8744723394801,
        "magnitude": 0.00016497183679213784,
        "prominence": 50.93494503241467
      },
      {
        "freq_hz": 63.76360808709175,
        "magnitude": 0.00015696927633351913,
        "prominence": 48.46415980625572
      },
      {
        "freq_hz": 82.20395467673849,
        "magnitude": 0.0001367520792854824,
        "prominence": 42.222113646287625
      },
      {
        "freq_hz": 67.76271939568984,
        "magnitude": 0.00013511608541925661,
        "prominence": 41.71700162674594
      }
    ],
    "ring_score": 0.028627422959963345,
    "rms": 0.01631678705447666,
    "sensitivity": "|S| n/a (only 1 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 50.0,
    "speed_gain_hz": 34.385,
    "torque_ff_pct": 200.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "capture": "realtime-sampler",
    "capture_error": null,
    "fs_hz": 1000.0,
    "machine_fault": false,
    "position_drift": 0.0064849853515625,
    "tripped_ferr": null
  }
}
```

**[    34.7s | speed | accept]** 34.4 Hz accepted (speed_34.4hz: peak=0.04143 rms=0.01632 score=0.07406 stable dom=65.8Hz tq=42%)

**[    35.5s | speed | write]** SDO write speed_gain_hz=37.5
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    40.2s | measure | measurement]** speed_37.5hz: peak=0.04074 rms=0.01573 score=0.07220 stable dom=81.5Hz tq=42%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_234614_Z/07_speed_37.5hz.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 81.5 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0014370038832910177,
    "ms": null,
    "n_samples": 4476,
    "peak_abs": 0.040740966796875,
    "peaks": [
      {
        "freq_hz": 81.54602323503127,
        "magnitude": 0.00016453332817636354,
        "prominence": 50.51104817984662
      },
      {
        "freq_hz": 82.66309204647006,
        "magnitude": 0.0001474497085280985,
        "prominence": 45.266447923449114
      },
      {
        "freq_hz": 79.53529937444146,
        "magnitude": 0.00014304957193033455,
        "prominence": 43.91562426874662
      },
      {
        "freq_hz": 80.65236818588025,
        "magnitude": 0.00013098782246839726,
        "prominence": 40.21271729568584
      },
      {
        "freq_hz": 84.67381590705988,
        "magnitude": 0.00013091133680336826,
        "prominence": 40.18923651428935
      }
    ],
    "ring_score": 0.028148460332271346,
    "rms": 0.015730520049011196,
    "sensitivity": "|S| n/a (only 1 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 50.0,
    "speed_gain_hz": 37.5,
    "torque_ff_pct": 200.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "capture": "realtime-sampler",
    "capture_error": null,
    "fs_hz": 1000.0,
    "machine_fault": false,
    "position_drift": 0.006561279296875,
    "tripped_ferr": null
  }
}
```

**[    40.2s | speed | stall]** 37.5 Hz stable but no 4.1% improvement (speed_37.5hz: peak=0.04074 rms=0.01573 score=0.07220 stable dom=81.5Hz tq=42%) — reverting to 34.4 Hz (stall 1/2)

**[    40.9s | speed | write]** SDO write speed_gain_hz=34.385
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    41.7s | speed | write]** SDO write speed_gain_hz=37.5
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    46.3s | measure | measurement]** speed_37.5hz: peak=0.04120 rms=0.01582 score=0.07285 stable dom=82.1Hz tq=42%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_234614_Z/08_speed_37.5hz.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 82.1 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0015422760462751924,
    "ms": null,
    "n_samples": 4446,
    "peak_abs": 0.04119873046875,
    "peaks": [
      {
        "freq_hz": 82.09626630679263,
        "magnitude": 0.00012504853320168243,
        "prominence": 38.07744539531124
      },
      {
        "freq_hz": 71.52496626180837,
        "magnitude": 0.0001226692448994792,
        "prominence": 37.35294892912136
      },
      {
        "freq_hz": 69.72559604138551,
        "magnitude": 0.00011897064987736402,
        "prominence": 36.22672180443514
      },
      {
        "freq_hz": 70.17543859649123,
        "magnitude": 0.00011459136949360443,
        "prominence": 34.89322507789281
      },
      {
        "freq_hz": 85.02024291497976,
        "magnitude": 0.00010708889672931435,
        "prominence": 32.60871209962925
      }
    ],
    "ring_score": 0.028362443481365986,
    "rms": 0.015823407407955487,
    "sensitivity": "|S| n/a (only 1 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 50.0,
    "speed_gain_hz": 37.5,
    "torque_ff_pct": 200.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "capture": "realtime-sampler",
    "capture_error": null,
    "fs_hz": 1000.0,
    "machine_fault": false,
    "position_drift": 0.0028228759765625,
    "tripped_ferr": null
  }
}
```

**[    46.3s | speed | stall]** 37.5 Hz stable but no 4.1% improvement (speed_37.5hz: peak=0.04120 rms=0.01582 score=0.07285 stable dom=82.1Hz tq=42%) — reverting to 34.4 Hz (stall 2/2)

**[    47.1s | speed | write]** SDO write speed_gain_hz=34.385
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    47.1s | position | start]** position ladder from 50.0 rad/s toward ~68.8 (cap 82.5)

**[    47.8s | position | write]** SDO write pos_gain_rad_s=60
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    52.5s | measure | measurement]** pos_60.0rads: peak=0.03670 rms=0.01398 score=0.06466 stable dom=72.1Hz tq=42%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_234614_Z/09_pos_60.0rads.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 72.1 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0027213748574067232,
    "ms": null,
    "n_samples": 4477,
    "peak_abs": 0.0366973876953125,
    "peaks": [
      {
        "freq_hz": 72.14652669198124,
        "magnitude": 0.00022109253041939354,
        "prominence": 67.95361588847614
      },
      {
        "freq_hz": 70.13625195443377,
        "magnitude": 0.00020894254273363317,
        "prominence": 64.21927174450296
      },
      {
        "freq_hz": 74.1568014295287,
        "magnitude": 0.0001558086673198789,
        "prominence": 47.88837646874067
      },
      {
        "freq_hz": 84.65490283672102,
        "magnitude": 0.00015234084291139527,
        "prominence": 46.82252767061181
      },
      {
        "freq_hz": 69.0194326557963,
        "magnitude": 0.00014204555045849068,
        "prominence": 43.658231041154814
      }
    ],
    "ring_score": 0.032335445462968126,
    "rms": 0.013980610702214829,
    "sensitivity": "|S| n/a (only 1 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 60.0,
    "speed_gain_hz": 34.385,
    "torque_ff_pct": 200.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "capture": "realtime-sampler",
    "capture_error": null,
    "fs_hz": 1000.0,
    "machine_fault": false,
    "position_drift": 0.0038909912109375,
    "tripped_ferr": null
  }
}
```

**[    52.5s | position | accept]** 60.0 rad/s accepted (pos_60.0rads: peak=0.03670 rms=0.01398 score=0.06466 stable dom=72.1Hz tq=42%)

**[    53.3s | position | write]** SDO write pos_gain_rad_s=72
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    57.9s | measure | measurement]** pos_72.0rads: peak=0.03105 rms=0.01178 score=0.05461 stable dom=60.6Hz tq=43%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_234614_Z/10_pos_72.0rads.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 60.6 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0026931840820753803,
    "ms": null,
    "n_samples": 4475,
    "peak_abs": 0.0310516357421875,
    "peaks": [
      {
        "freq_hz": 60.55865921787709,
        "magnitude": 0.00015528333675493878,
        "prominence": 46.40071392790506
      },
      {
        "freq_hz": 62.56983240223463,
        "magnitude": 0.0001131803367321783,
        "prominence": 33.81978090322522
      },
      {
        "freq_hz": 85.13966480446926,
        "magnitude": 0.00010268545640377359,
        "prominence": 30.68377191473717
      },
      {
        "freq_hz": 87.37430167597765,
        "magnitude": 0.00010244550059460884,
        "prominence": 30.61206994665051
      },
      {
        "freq_hz": 69.72067039106145,
        "magnitude": 9.9292432724565e-05,
        "prominence": 29.66989158230956
      }
    ],
    "ring_score": 0.03383056166995079,
    "rms": 0.011777806144100999,
    "sensitivity": "|S| n/a (only 1 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 72.0,
    "speed_gain_hz": 34.385,
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

**[    57.9s | position | accept]** 72.0 rad/s accepted (pos_72.0rads: peak=0.03105 rms=0.01178 score=0.05461 stable dom=60.6Hz tq=43%)

**[    58.7s | position | write]** SDO write pos_gain_rad_s=82.524
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    63.3s | measure | measurement]** pos_82.5rads: peak=0.02838 rms=0.01037 score=0.04913 stable dom=63.1Hz tq=42%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_234614_Z/11_pos_82.5rads.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 63.1 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0025053650848238357,
    "ms": null,
    "n_samples": 4436,
    "peak_abs": 0.02838134765625,
    "peaks": [
      {
        "freq_hz": 63.11992786293958,
        "magnitude": 0.00013138889072799285,
        "prominence": 40.100587471075514
      },
      {
        "freq_hz": 80.70333633904418,
        "magnitude": 0.00010314051185773211,
        "prominence": 31.479032166616047
      },
      {
        "freq_hz": 61.09107303877367,
        "magnitude": 0.00010030612264428675,
        "prominence": 30.613961520604246
      },
      {
        "freq_hz": 78.67448151487827,
        "magnitude": 9.196569047027752e-05,
        "prominence": 28.06841731144553
      },
      {
        "freq_hz": 61.992786293958524,
        "magnitude": 8.933721907100868e-05,
        "prominence": 27.266193876286078
      }
    ],
    "ring_score": 0.03501065936897601,
    "rms": 0.010374445438801132,
    "sensitivity": "|S| n/a (only 1 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 82.52399999999999,
    "speed_gain_hz": 34.385,
    "torque_ff_pct": 200.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "capture": "realtime-sampler",
    "capture_error": null,
    "fs_hz": 1000.0,
    "machine_fault": false,
    "position_drift": 0.005340576171875,
    "tripped_ferr": null
  }
}
```

**[    63.3s | position | accept]** 82.5 rad/s accepted (pos_82.5rads: peak=0.02838 rms=0.01037 score=0.04913 stable dom=63.1Hz tq=42%)

**[    63.3s | position | done]** reached cap

**[    63.3s | integral | start]** integral tighten from 3.00 ms toward 3.00 ms (lower = stronger)

**[    63.3s | integral | skip]** already at/below floor

**[    63.3s | feedforward | start]** torque FF 200% (search 50-200%)

**[    64.1s | feedforward | write]** SDO write torque_ff_pct=173.9
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "torque_ff_pct"
  ]
}
```

**[    68.8s | measure | measurement]** ff_173.9pct: peak=0.02777 rms=0.01022 score=0.04821 stable dom=63.5Hz tq=42%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_234614_Z/12_ff_173.9pct.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 63.5 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.002868160161950058,
    "ms": null,
    "n_samples": 4489,
    "peak_abs": 0.02777099609375,
    "peaks": [
      {
        "freq_hz": 63.48852751169525,
        "magnitude": 0.00014147622611702853,
        "prominence": 43.87221269352662
      },
      {
        "freq_hz": 65.49342838048562,
        "magnitude": 0.00013074125842495141,
        "prominence": 40.543266207101674
      },
      {
        "freq_hz": 64.37959456449097,
        "magnitude": 8.968663547125066e-05,
        "prominence": 27.812101404985803
      },
      {
        "freq_hz": 81.9781688572065,
        "magnitude": 8.812316304724866e-05,
        "prominence": 27.32726379934074
      },
      {
        "freq_hz": 83.53753619959902,
        "magnitude": 8.627045466706814e-05,
        "prominence": 26.75273323441655
      }
    ],
    "ring_score": 0.03514658688124072,
    "rms": 0.010220711299587841,
    "sensitivity": "|S| n/a (only 1 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 82.52399999999999,
    "speed_gain_hz": 34.385,
    "torque_ff_pct": 173.9
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "capture": "realtime-sampler",
    "capture_error": null,
    "fs_hz": 1000.0,
    "machine_fault": false,
    "position_drift": 0.0048828125,
    "tripped_ferr": null
  }
}
```

**[    68.8s | feedforward | stall]** 173.9% no better — back to 200%

**[    69.5s | feedforward | write]** SDO write torque_ff_pct=200
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "torque_ff_pct"
  ]
}
```

**[    75.4s | rest | standstill]** verify: rest FERR rms 0.06 um, torque rms 0.25% (about mean 12.0%)
```json
{
  "ferr_peak": 0.0002288818359375,
  "ferr_rms": 6.380940651984381e-05,
  "n": 1005.0,
  "torque_mean_pct": 11.959303482587066,
  "torque_peak_pct": 12.700000000000001,
  "torque_rms_pct": 0.2547958160926497
}
```

**[    75.4s | measure | measurement]** verify: peak=0.02823 rms=0.01036 score=0.04895 stable dom=65.5Hz tq=42%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_234614_Z/13_verify.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 65.5 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0032342644484343232,
    "ms": null,
    "n_samples": 4457,
    "peak_abs": 0.028228759765625,
    "peaks": [
      {
        "freq_hz": 65.51492035001122,
        "magnitude": 0.00013687216921607988,
        "prominence": 40.68232349405776
      },
      {
        "freq_hz": 64.39308952210007,
        "magnitude": 0.0001314576700998207,
        "prominence": 39.07297949178511
      },
      {
        "freq_hz": 63.94435719093561,
        "magnitude": 0.0001270519640240386,
        "prominence": 37.76347763453211
      },
      {
        "freq_hz": 74.71393313888267,
        "magnitude": 0.00012261587607476868,
        "prominence": 36.44494541549946
      },
      {
        "freq_hz": 86.1566075835764,
        "magnitude": 0.0001203909734371953,
        "prominence": 35.7836407151871
      }
    ],
    "ring_score": 0.03743669605740358,
    "rms": 0.010361432871118615,
    "sensitivity": "|S| n/a (only 1 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 82.52399999999999,
    "speed_gain_hz": 34.385,
    "torque_ff_pct": 200.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "capture": "realtime-sampler",
    "capture_error": null,
    "fs_hz": 1000.0,
    "machine_fault": false,
    "position_drift": 0.0048828125,
    "tripped_ferr": null
  }
}
```

**[    75.4s | verify | ok]** verify: peak=0.02823 rms=0.01036 score=0.04895 stable dom=65.5Hz tq=42%

**[    75.4s | finalize | preset]** final tune saved as preset one_click_20261127_234730
```json
{
  "path": "/home/jon/linuxcnc/configs/ethercat_mill/config/tuning/presets/Z/one_click_20261127_234730.json"
}
```

**[    75.4s | finalize | result]** campaign status: improved
```json
{
  "baseline_score": 0.08676215013535943,
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
  "final_score": 0.04895162550786223,
  "final_values": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 82.52399999999999,
    "speed_gain_hz": 34.385,
    "torque_ff_pct": 200.0
  },
  "improvement_pct": 43.57951545519356,
  "measurements": 13,
  "notch_applied": false,
  "preset": "one_click_20261127_234730",
  "reason": "score improved 43.6%"
}
```


---

**FINAL STATUS: IMPROVED** — 2026-11-27T23:47:30
**[    75.9s | finalize | ferr-window]** 6065 restored to 0.5 production window

