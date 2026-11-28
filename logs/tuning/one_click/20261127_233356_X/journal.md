# One-click tune — axis X

- started: 2026-11-27T23:33:56
- engine: a6_auto_tune v2.1
- profile: balanced
- stimulus: 3x 0<->40 mm @ F3000 (~6.8s per measurement)
- dry run: False

**[     0.0s | setup | config]** campaign configuration
```json
{
  "config": {
    "allow_notch": true,
    "allow_python_sampler": false,
    "axis": "X",
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
      "axis": "X",
      "cycles": 3,
      "dwell_s": 0.25,
      "feed": 3000.0,
      "settle_s": 0.5,
      "stroke": 40.0
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
  "max_limit": 370.0,
  "min_limit": -254.0,
  "opmode": null,
  "position": 122.52281188964844
}
```

**[     0.1s | preflight | info]** drive torque limit 0x6072 = 300% -> guard 240%

**[     0.1s | preflight | stimulus]** stimulus direction +40 mm
```json
{
  "direction": 1.0,
  "spec": "3x 0<->40 mm @ F3000 (~6.8s per measurement)"
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
    "inertia_ratio_pct": 100.0,
    "integral_2_ms": 3.0,
    "integral_ms": 5.0,
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
    "pos_gain_2_rad_s": 184.0,
    "pos_gain_rad_s": 130.0,
    "speed_fb_filter": 3.0,
    "speed_fb_lpf_hz": 8000.0,
    "speed_ff_filter_hz": 318.0,
    "speed_ff_pct": 100.0,
    "speed_ff_source": 1.0,
    "speed_gain_2_hz": 115.0,
    "speed_gain_hz": 80.0,
    "stiffness_level": 18.0,
    "torque_ff_filter_hz": 1000.0,
    "torque_ff_pct": 120.0,
    "torque_ff_source": 1.0,
    "torque_filter_2_hz": 920.0,
    "torque_filter_hz": 600.0
  }
}
```

**[     1.7s | baseline | backup]** baseline preset saved: pre_one_click_20261127_233358
```json
{
  "path": "/home/jon/linuxcnc/configs/ethercat_mill/config/tuning/presets/X/pre_one_click_20261127_233358.json"
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

**[    11.5s | measure | measurement]** baseline_1: peak=0.00877 rms=0.00215 score=0.01308 stable dom=50.1Hz tq=17%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233356_X/01_baseline_1.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 50.1 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.014536735586484642,
    "ms": 0.039112634375753796,
    "n_samples": 7481,
    "peak_abs": 0.0087738037109375,
    "peaks": [
      {
        "freq_hz": 50.1269883705387,
        "magnitude": 0.0001697956193020046,
        "prominence": 68.60988420537531
      },
      {
        "freq_hz": 49.19128458762197,
        "magnitude": 0.00011581987145071592,
        "prominence": 46.79972311170962
      },
      {
        "freq_hz": 74.45528672637347,
        "magnitude": 0.00010639673874820261,
        "prominence": 42.99208634093169
      },
      {
        "freq_hz": 75.2573185403021,
        "magnitude": 0.00010434024382570216,
        "prominence": 42.16111155441061
      },
      {
        "freq_hz": 74.85630263333778,
        "magnitude": 9.499455536625656e-05,
        "prominence": 38.38476793813861
      }
    ],
    "ring_score": 0.10215975266598415,
    "rms": 0.0021506554271619694,
    "sensitivity": "Ms 0.04 @ 16 Hz (GM>=inf dB, PM>=180 deg; 3 coherent bins)"
  },
  "gains": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 130.0,
    "speed_gain_hz": 80.0,
    "torque_ff_pct": 120.0
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

**[    19.2s | measure | measurement]** baseline_2: peak=0.00877 rms=0.00215 score=0.01307 stable dom=50.3Hz tq=17%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233356_X/02_baseline_2.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 50.3 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.014050531682567816,
    "ms": 0.03854201170347367,
    "n_samples": 7474,
    "peak_abs": 0.0087738037109375,
    "peaks": [
      {
        "freq_hz": 50.30773347605031,
        "magnitude": 0.00011926888079953365,
        "prominence": 48.084278964312304
      },
      {
        "freq_hz": 75.06020872357506,
        "magnitude": 0.00011126940112745885,
        "prominence": 44.85921967354973
      },
      {
        "freq_hz": 49.90634198554991,
        "magnitude": 0.00011103460111921755,
        "prominence": 44.76455802315599
      },
      {
        "freq_hz": 49.37115333154937,
        "magnitude": 0.00011055908205626496,
        "prominence": 44.57284840768394
      },
      {
        "freq_hz": 74.65881723307466,
        "magnitude": 9.664500400788447e-05,
        "prominence": 38.96326771970823
      }
    ],
    "ring_score": 0.09755166524559784,
    "rms": 0.0021491121142556903,
    "sensitivity": "Ms 0.04 @ 16 Hz (GM>=inf dB, PM>=180 deg; 3 coherent bins)"
  },
  "gains": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 130.0,
    "speed_gain_hz": 80.0,
    "torque_ff_pct": 120.0
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

**[    26.9s | measure | measurement]** baseline_3: peak=0.00870 rms=0.00215 score=0.01300 stable dom=50.2Hz tq=17%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233356_X/03_baseline_3.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 50.2 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.013577039935641848,
    "ms": null,
    "n_samples": 7455,
    "peak_abs": 0.008697509765625,
    "peaks": [
      {
        "freq_hz": 50.167672702883976,
        "magnitude": 0.0001293184255514048,
        "prominence": 54.777842512130256
      },
      {
        "freq_hz": 49.36284372904092,
        "magnitude": 0.0001247638354639279,
        "prominence": 52.84856895768271
      },
      {
        "freq_hz": 74.71495640509725,
        "magnitude": 0.0001239321904311751,
        "prominence": 52.49629339883731
      },
      {
        "freq_hz": 75.6539235412475,
        "magnitude": 8.490976987627472e-05,
        "prominence": 35.96683134821287
      },
      {
        "freq_hz": 25.75452716297787,
        "magnitude": 8.058491215247157e-05,
        "prominence": 34.13486986034518
      }
    ],
    "ring_score": 0.09076899546622147,
    "rms": 0.0021505300304191593,
    "sensitivity": "|S| n/a (only 2 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 130.0,
    "speed_gain_hz": 80.0,
    "torque_ff_pct": 120.0
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

**[    26.9s | baseline | noise]** baseline spread 0.6% over 3 runs -> a step must improve the score by >= 3.0%
```json
{
  "improve_pct": 3.0,
  "scores": [
    0.013075114565261439,
    0.01307202793944888,
    0.01299856982646332
  ],
  "spread_pct": 0.5855613157551637
}
```

**[    28.1s | rest | standstill]** baseline: rest FERR rms 0.05 um, torque rms 1.52%
```json
{
  "ferr_peak": 0.000152587890625,
  "ferr_rms": 4.6766727719602866e-05,
  "n": 1006.0,
  "torque_peak_pct": 2.6,
  "torque_rms_pct": 1.5192535050884888
}
```

**[    28.1s | speed | cap]** speed gain capped at 150.0 Hz (0.25 x C01.03 torque filter 600 Hz)

**[    28.1s | speed | start]** speed ladder from 80.0 Hz, cap 150.0 Hz

**[    28.9s | speed | write]** SDO write speed_gain_hz=100
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    36.5s | measure | measurement]** speed_100.0hz: peak=0.00816 rms=0.00201 score=0.01218 stable dom=75.3Hz tq=18%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233356_X/04_speed_100.0hz.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 75.3 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.011608092086056166,
    "ms": null,
    "n_samples": 7462,
    "peak_abs": 0.0081634521484375,
    "peaks": [
      {
        "freq_hz": 75.31492897346556,
        "magnitude": 0.00010772849521014784,
        "prominence": 42.470289663744815
      },
      {
        "freq_hz": 50.12061109622085,
        "magnitude": 0.0001069579687363592,
        "prominence": 42.16652154304888
      },
      {
        "freq_hz": 74.51085499865988,
        "magnitude": 9.272912404850168e-05,
        "prominence": 36.55702004305187
      },
      {
        "freq_hz": 49.316537121415166,
        "magnitude": 8.35089822994705e-05,
        "prominence": 32.92212205196534
      },
      {
        "freq_hz": 25.730367193781827,
        "magnitude": 6.674822514556298e-05,
        "prominence": 26.314453301728477
      }
    ],
    "ring_score": 0.0985384059404498,
    "rms": 0.0020079228519067696,
    "sensitivity": "|S| n/a (only 2 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 130.0,
    "speed_gain_hz": 100.0,
    "torque_ff_pct": 120.0
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

**[    36.5s | speed | accept]** 100.0 Hz accepted (speed_100.0hz: peak=0.00816 rms=0.00201 score=0.01218 stable dom=75.3Hz tq=18%)

**[    37.3s | speed | write]** SDO write speed_gain_hz=125
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    44.9s | measure | measurement]** speed_125.0hz: peak=0.00801 rms=0.00190 score=0.01181 stable dom=50.2Hz tq=19%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233356_X/05_speed_125.0hz.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 50.2 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.009844994572438846,
    "ms": null,
    "n_samples": 7450,
    "peak_abs": 0.0080108642578125,
    "peaks": [
      {
        "freq_hz": 50.20134228187919,
        "magnitude": 0.00010836780838432793,
        "prominence": 44.80215717940971
      },
      {
        "freq_hz": 49.261744966442954,
        "magnitude": 9.00633137002806e-05,
        "prominence": 37.23458835845571
      },
      {
        "freq_hz": 75.43624161073825,
        "magnitude": 7.970304269811317e-05,
        "prominence": 32.95137458140647
      },
      {
        "freq_hz": 74.63087248322148,
        "magnitude": 7.573057007448452e-05,
        "prominence": 31.309047902218484
      },
      {
        "freq_hz": 25.77181208053691,
        "magnitude": 5.335652972970998e-05,
        "prominence": 22.059019806144057
      }
    ],
    "ring_score": 0.11010657565882732,
    "rms": 0.0018988260430536784,
    "sensitivity": "|S| n/a (only 2 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 130.0,
    "speed_gain_hz": 125.0,
    "torque_ff_pct": 120.0
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

**[    44.9s | speed | accept]** 125.0 Hz accepted (speed_125.0hz: peak=0.00801 rms=0.00190 score=0.01181 stable dom=50.2Hz tq=19%)

**[    45.7s | speed | write]** SDO write speed_gain_hz=150
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    53.4s | measure | measurement]** speed_150.0hz: peak=0.00771 rms=0.00182 score=0.01135 stable dom=49.9Hz tq=20%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233356_X/06_speed_150.0hz.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 49.9 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.009002223084365298,
    "ms": 0.03560320981657848,
    "n_samples": 7461,
    "peak_abs": 0.0077056884765625,
    "peaks": [
      {
        "freq_hz": 49.85926819461198,
        "magnitude": 7.48472722871116e-05,
        "prominence": 30.04211694145551
      },
      {
        "freq_hz": 75.19099316445516,
        "magnitude": 7.025196438298565e-05,
        "prominence": 28.197657240797607
      },
      {
        "freq_hz": 74.25278112853503,
        "magnitude": 4.2283091371568516e-05,
        "prominence": 16.971541337648
      },
      {
        "freq_hz": 49.457177322074784,
        "magnitude": 4.134344823126425e-05,
        "prominence": 16.59438839350366
      },
      {
        "freq_hz": 29.218603404369386,
        "magnitude": 3.8455131394476995e-05,
        "prominence": 15.435078915372157
      }
    ],
    "ring_score": 0.11843483086167259,
    "rms": 0.0018242577465884735,
    "sensitivity": "Ms 0.04 @ 16 Hz (GM>=inf dB, PM>=180 deg; 3 coherent bins)"
  },
  "gains": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 130.0,
    "speed_gain_hz": 150.0,
    "torque_ff_pct": 120.0
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

**[    53.4s | speed | accept]** 150.0 Hz accepted (speed_150.0hz: peak=0.00771 rms=0.00182 score=0.01135 stable dom=49.9Hz tq=20%)

**[    53.4s | speed | done]** reached cap

**[    53.4s | position | start]** position ladder from 130.0 rad/s toward ~300.0 (cap 360.0)

**[    54.1s | position | write]** SDO write pos_gain_rad_s=156
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    61.8s | measure | measurement]** pos_156.0rads: peak=0.00664 rms=0.00153 score=0.00970 stable dom=50.1Hz tq=18%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233356_X/07_pos_156.0rads.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 50.1 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.012773583656989496,
    "ms": 0.030903230632834646,
    "n_samples": 7486,
    "peak_abs": 0.0066375732421875,
    "peaks": [
      {
        "freq_hz": 50.09350788137858,
        "magnitude": 8.743277219692339e-05,
        "prominence": 35.06473566777047
      },
      {
        "freq_hz": 74.80630510285867,
        "magnitude": 5.657374164852559e-05,
        "prominence": 22.688784157207493
      },
      {
        "freq_hz": 49.15842906759284,
        "magnitude": 5.09378677750102e-05,
        "prominence": 20.42852838964915
      },
      {
        "freq_hz": 29.12102591504141,
        "magnitude": 4.8622072583359926e-05,
        "prominence": 19.499783432632128
      },
      {
        "freq_hz": 360.00534330750736,
        "magnitude": 4.307028790253582e-05,
        "prominence": 17.273251464973384
      }
    ],
    "ring_score": 0.14227003065887653,
    "rms": 0.00153277700690644,
    "sensitivity": "Ms 0.03 @ 16 Hz (GM>=inf dB, PM>=180 deg; 3 coherent bins)"
  },
  "gains": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 156.0,
    "speed_gain_hz": 150.0,
    "torque_ff_pct": 120.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "capture": "realtime-sampler",
    "capture_error": null,
    "fs_hz": 1000.0,
    "machine_fault": false,
    "position_drift": -0.0003814697265625,
    "tripped_ferr": null
  }
}
```

**[    61.9s | position | accept]** 156.0 rad/s accepted (pos_156.0rads: peak=0.00664 rms=0.00153 score=0.00970 stable dom=50.1Hz tq=18%)

**[    62.6s | position | write]** SDO write pos_gain_rad_s=187.2
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    70.3s | measure | measurement]** pos_187.2rads: peak=0.00557 rms=0.00129 score=0.00815 stable dom=50.0Hz tq=18%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233356_X/08_pos_187.2rads.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 50.0 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.019120665082283803,
    "ms": null,
    "n_samples": 7477,
    "peak_abs": 0.0055694580078125,
    "peaks": [
      {
        "freq_hz": 50.0200615220008,
        "magnitude": 9.322888754702877e-05,
        "prominence": 37.060683553118
      },
      {
        "freq_hz": 74.62886184298516,
        "magnitude": 5.3991755630724555e-05,
        "prominence": 21.462997387995014
      },
      {
        "freq_hz": 75.16383576300656,
        "magnitude": 4.7636900279102396e-05,
        "prominence": 18.936792373551366
      },
      {
        "freq_hz": 75.56506620302261,
        "magnitude": 4.268722613007702e-05,
        "prominence": 16.969180057727648
      },
      {
        "freq_hz": 49.08385716196336,
        "magnitude": 4.2433891574511686e-05,
        "prominence": 16.8684735916965
      }
    ],
    "ring_score": 0.18036078049660328,
    "rms": 0.0012891844257396311,
    "sensitivity": "|S| n/a (only 2 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 187.2,
    "speed_gain_hz": 150.0,
    "torque_ff_pct": 120.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "capture": "realtime-sampler",
    "capture_error": null,
    "fs_hz": 1000.0,
    "machine_fault": false,
    "position_drift": -0.0003814697265625,
    "tripped_ferr": null
  }
}
```

**[    70.3s | position | accept]** 187.2 rad/s accepted (pos_187.2rads: peak=0.00557 rms=0.00129 score=0.00815 stable dom=50.0Hz tq=18%)

**[    71.1s | position | write]** SDO write pos_gain_rad_s=224.64
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    78.7s | measure | measurement]** pos_224.6rads: peak=0.00481 rms=0.00108 score=0.00698 stable dom=49.5Hz tq=18%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233356_X/09_pos_224.6rads.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 49.5 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.026549883664664636,
    "ms": null,
    "n_samples": 7438,
    "peak_abs": 0.0048065185546875,
    "peaks": [
      {
        "freq_hz": 49.47566550147889,
        "magnitude": 8.693201249914065e-05,
        "prominence": 32.47579331883535
      },
      {
        "freq_hz": 50.282333960742136,
        "magnitude": 6.928784907333743e-05,
        "prominence": 25.884341122720556
      },
      {
        "freq_hz": 74.88572196827104,
        "magnitude": 5.745102980910134e-05,
        "prominence": 21.462378661175794
      },
      {
        "freq_hz": 360.3119118042485,
        "magnitude": 4.806888530319392e-05,
        "prominence": 17.957426030931465
      },
      {
        "freq_hz": 299.9462221027158,
        "magnitude": 4.200862648347777e-05,
        "prominence": 15.69345321781275
      }
    ],
    "ring_score": 0.22040114274440617,
    "rms": 0.0010848349520887425,
    "sensitivity": "|S| n/a (only 2 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 224.64,
    "speed_gain_hz": 150.0,
    "torque_ff_pct": 120.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "capture": "realtime-sampler",
    "capture_error": null,
    "fs_hz": 1000.0,
    "machine_fault": false,
    "position_drift": -0.0002288818359375,
    "tripped_ferr": null
  }
}
```

**[    78.7s | position | accept]** 224.6 rad/s accepted (pos_224.6rads: peak=0.00481 rms=0.00108 score=0.00698 stable dom=49.5Hz tq=18%)

**[    79.5s | position | write]** SDO write pos_gain_rad_s=269.568
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    87.2s | measure | measurement]** pos_269.6rads: peak=0.00412 rms=0.00091 score=0.00594 stable dom=50.0Hz tq=20%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233356_X/10_pos_269.6rads.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 50.0 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0376975388069528,
    "ms": 0.018060090520664342,
    "n_samples": 7495,
    "peak_abs": 0.004119873046875,
    "peaks": [
      {
        "freq_hz": 50.03335557038025,
        "magnitude": 6.404143203774117e-05,
        "prominence": 24.012056198999964
      },
      {
        "freq_hz": 74.98332221480987,
        "magnitude": 5.7212443996874504e-05,
        "prominence": 21.45155685659062
      },
      {
        "freq_hz": 300.2001334222815,
        "magnitude": 4.643016035749832e-05,
        "prominence": 17.40878653643788
      },
      {
        "freq_hz": 359.97331554369583,
        "magnitude": 3.902197262466659e-05,
        "prominence": 14.631118790521997
      },
      {
        "freq_hz": 49.36624416277518,
        "magnitude": 3.539508355194592e-05,
        "prominence": 13.271232518922327
      }
    ],
    "ring_score": 0.2668584737914123,
    "rms": 0.0009092873672804701,
    "sensitivity": "Ms 0.02 @ 16 Hz (GM>=inf dB, PM>=180 deg; 3 coherent bins)"
  },
  "gains": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 269.568,
    "speed_gain_hz": 150.0,
    "torque_ff_pct": 120.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "capture": "realtime-sampler",
    "capture_error": null,
    "fs_hz": 1000.0,
    "machine_fault": false,
    "position_drift": -0.00030517578125,
    "tripped_ferr": null
  }
}
```

**[    87.2s | position | accept]** 269.6 rad/s accepted (pos_269.6rads: peak=0.00412 rms=0.00091 score=0.00594 stable dom=50.0Hz tq=20%)

**[    88.0s | position | write]** SDO write pos_gain_rad_s=323.482
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    95.7s | measure | measurement]** pos_323.5rads: peak=0.00366 rms=0.00077 score=0.00520 stable dom=49.4Hz tq=23%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233356_X/11_pos_323.5rads.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 49.4 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.05538678015672766,
    "ms": null,
    "n_samples": 7468,
    "peak_abs": 0.003662109375,
    "peaks": [
      {
        "freq_hz": 49.410819496518485,
        "magnitude": 5.446349246154789e-05,
        "prominence": 19.75717143930644
      },
      {
        "freq_hz": 50.21424745581147,
        "magnitude": 5.3331373573949236e-05,
        "prominence": 19.34648409736348
      },
      {
        "freq_hz": 75.12051419389395,
        "magnitude": 5.060088717097487e-05,
        "prominence": 18.35597310480554
      },
      {
        "freq_hz": 300.34815211569367,
        "magnitude": 4.678406170112335e-05,
        "prominence": 16.971381853794444
      },
      {
        "freq_hz": 399.83931440814143,
        "magnitude": 4.644733754525542e-05,
        "prominence": 16.849231830456606
      }
    ],
    "ring_score": 0.34221560953487673,
    "rms": 0.0007664726879703758,
    "sensitivity": "|S| n/a (only 2 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 323.48159999999996,
    "speed_gain_hz": 150.0,
    "torque_ff_pct": 120.0
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

**[    95.7s | position | accept]** 323.5 rad/s accepted (pos_323.5rads: peak=0.00366 rms=0.00077 score=0.00520 stable dom=49.4Hz tq=23%)

**[    96.5s | position | write]** SDO write pos_gain_rad_s=360
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[   104.1s | measure | measurement]** pos_360.0rads: peak=0.00320 rms=0.00070 score=0.00460 stable dom=49.8Hz tq=22%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233356_X/12_pos_360.0rads.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 49.8 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.07604448466387564,
    "ms": 0.014210607219732387,
    "n_samples": 7463,
    "peak_abs": 0.003204345703125,
    "peaks": [
      {
        "freq_hz": 49.845906471928174,
        "magnitude": 6.570703642480328e-05,
        "prominence": 23.548637089556305
      },
      {
        "freq_hz": 75.17084282460137,
        "magnitude": 5.496523901442561e-05,
        "prominence": 19.698901921603525
      },
      {
        "freq_hz": 360.0428781991156,
        "magnitude": 4.386600212499991e-05,
        "prominence": 15.721064604602905
      },
      {
        "freq_hz": 399.8392067533163,
        "magnitude": 4.3632333983719903e-05,
        "prominence": 15.637320662434833
      },
      {
        "freq_hz": 419.93836258877127,
        "magnitude": 4.278291879633711e-05,
        "prominence": 15.332900145631793
      }
    ],
    "ring_score": 0.4156450702520809,
    "rms": 0.0006961428372018307,
    "sensitivity": "Ms 0.01 @ 16 Hz (GM>=inf dB, PM>=180 deg; 3 coherent bins)"
  },
  "gains": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 360.0,
    "speed_gain_hz": 150.0,
    "torque_ff_pct": 120.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "capture": "realtime-sampler",
    "capture_error": null,
    "fs_hz": 1000.0,
    "machine_fault": false,
    "position_drift": 0.000152587890625,
    "tripped_ferr": null
  }
}
```

**[   104.1s | position | accept]** 360.0 rad/s accepted (pos_360.0rads: peak=0.00320 rms=0.00070 score=0.00460 stable dom=49.8Hz tq=22%)

**[   104.1s | position | done]** reached cap

**[   104.2s | integral | start]** integral tighten from 5.00 ms toward 3.00 ms (lower = stronger)

**[   104.9s | integral | write]** SDO write integral_ms=3.5
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "integral_ms"
  ]
}
```

**[   112.6s | measure | measurement]** integral_3.50ms: peak=0.00313 rms=0.00067 score=0.00447 stable dom=359.9Hz tq=21%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233356_X/13_integral_3.50ms.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 359.9 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.07923875185061019,
    "ms": 0.014044517039535,
    "n_samples": 7467,
    "peak_abs": 0.0031280517578125,
    "peaks": [
      {
        "freq_hz": 359.8500066961296,
        "magnitude": 6.939591255980009e-05,
        "prominence": 24.570744478997078
      },
      {
        "freq_hz": 50.2209722780233,
        "magnitude": 4.76051546436806e-05,
        "prominence": 16.855374437580377
      },
      {
        "freq_hz": 75.26449712066425,
        "magnitude": 4.191929363804938e-05,
        "prominence": 14.842203448697271
      },
      {
        "freq_hz": 49.283514128833524,
        "magnitude": 4.145128886758805e-05,
        "prominence": 14.676498795414592
      },
      {
        "freq_hz": 360.78746484531933,
        "magnitude": 4.0706825172331065e-05,
        "prominence": 14.412909391438
      }
    ],
    "ring_score": 0.4348365825442619,
    "rms": 0.0006714067586504654,
    "sensitivity": "Ms 0.01 @ 16 Hz (GM>=inf dB, PM>=180 deg; 3 coherent bins)"
  },
  "gains": {
    "integral_ms": 3.5,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 360.0,
    "speed_gain_hz": 150.0,
    "torque_ff_pct": 120.0
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

**[   112.6s | integral | accept]** 3.50 ms accepted (rms +3.6%, peak -2.4%)

**[   113.3s | integral | write]** SDO write integral_ms=3
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "integral_ms"
  ]
}
```

**[   121.0s | measure | measurement]** integral_3.00ms: peak=0.00328 rms=0.00066 score=0.00461 stable dom=360.2Hz tq=21%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233356_X/14_integral_3.00ms.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 360.2 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.08337111415253387,
    "ms": 0.014011269332230635,
    "n_samples": 7473,
    "peak_abs": 0.0032806396484375,
    "peaks": [
      {
        "freq_hz": 360.2301619162318,
        "magnitude": 4.925522813659057e-05,
        "prominence": 16.83883704455463
      },
      {
        "freq_hz": 399.9732369864847,
        "magnitude": 4.658337147665675e-05,
        "prominence": 15.925412001059383
      },
      {
        "freq_hz": 49.37775993576877,
        "magnitude": 4.286242584978243e-05,
        "prominence": 14.65333593049828
      },
      {
        "freq_hz": 50.18065034122842,
        "magnitude": 4.216420734558303e-05,
        "prominence": 14.414636648036277
      },
      {
        "freq_hz": 419.6440519202462,
        "magnitude": 4.053437233170191e-05,
        "prominence": 13.857446533473277
      }
    ],
    "ring_score": 0.4548113866170415,
    "rms": 0.0006649219381955735,
    "sensitivity": "Ms 0.01 @ 16 Hz (GM>=inf dB, PM>=180 deg; 3 coherent bins)"
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 360.0,
    "speed_gain_hz": 150.0,
    "torque_ff_pct": 120.0
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

**[   121.0s | integral | accept]** 3.00 ms accepted (rms +1.0%, peak +4.9%)

**[   121.0s | integral | done]** reached floor

**[   121.0s | feedforward | start]** torque FF 120% (search 50-200%)

**[   121.8s | feedforward | write]** SDO write torque_ff_pct=138
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "torque_ff_pct"
  ]
}
```

**[   129.5s | measure | measurement]** ff_138pct: peak=0.00336 rms=0.00067 score=0.00470 stable dom=360.0Hz tq=22%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233356_X/15_ff_138pct.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 360.0 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.09683544612650434,
    "ms": null,
    "n_samples": 7469,
    "peak_abs": 0.00335693359375,
    "peaks": [
      {
        "freq_hz": 360.02142187709194,
        "magnitude": 7.795903975633907e-05,
        "prominence": 27.66344456590817
      },
      {
        "freq_hz": 399.78578122908016,
        "magnitude": 7.388131951154902e-05,
        "prominence": 26.216482311118998
      },
      {
        "freq_hz": 400.58910162002945,
        "magnitude": 5.3836778164395576e-05,
        "prominence": 19.103759269132766
      },
      {
        "freq_hz": 50.207524434328555,
        "magnitude": 4.929339738298696e-05,
        "prominence": 17.491559288461637
      },
      {
        "freq_hz": 359.0842147543178,
        "magnitude": 4.183271821830744e-05,
        "prominence": 14.844167977060113
      }
    ],
    "ring_score": 0.506463975475515,
    "rms": 0.0006690452230098662,
    "sensitivity": "|S| n/a (only 2 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 360.0,
    "speed_gain_hz": 150.0,
    "torque_ff_pct": 138.0
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

**[   129.5s | feedforward | stall]** 138% no better — back to 120%

**[   130.3s | feedforward | write]** SDO write torque_ff_pct=120
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "torque_ff_pct"
  ]
}
```

**[   131.1s | feedforward | write]** SDO write torque_ff_pct=104.3
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "torque_ff_pct"
  ]
}
```

**[   138.7s | measure | measurement]** ff_104.3pct: peak=0.00328 rms=0.00067 score=0.00461 stable dom=300.0Hz tq=20%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233356_X/16_ff_104.3pct.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 300.0 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.08344321645734379,
    "ms": null,
    "n_samples": 7454,
    "peak_abs": 0.0032806396484375,
    "peaks": [
      {
        "freq_hz": 299.97316876844644,
        "magnitude": 5.700563961218735e-05,
        "prominence": 20.266706113448947
      },
      {
        "freq_hz": 50.174403005097936,
        "magnitude": 4.9170077267233815e-05,
        "prominence": 17.48099858768285
      },
      {
        "freq_hz": 75.12744834987926,
        "magnitude": 4.5978262569428716e-05,
        "prominence": 16.34624120421911
      },
      {
        "freq_hz": 49.36946605849209,
        "magnitude": 4.59604052299735e-05,
        "prominence": 16.339892543750263
      },
      {
        "freq_hz": 399.65119398980414,
        "magnitude": 4.572276233185808e-05,
        "prominence": 16.25540548582374
      }
    ],
    "ring_score": 0.44238103903719644,
    "rms": 0.0006658092953104576,
    "sensitivity": "|S| n/a (only 2 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 360.0,
    "speed_gain_hz": 150.0,
    "torque_ff_pct": 104.3
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "capture": "realtime-sampler",
    "capture_error": null,
    "fs_hz": 1000.0,
    "machine_fault": false,
    "position_drift": -0.0003814697265625,
    "tripped_ferr": null
  }
}
```

**[   138.7s | feedforward | stall]** 104.3% no better — back to 120%

**[   139.5s | feedforward | write]** SDO write torque_ff_pct=120
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "torque_ff_pct"
  ]
}
```

**[   148.4s | rest | standstill]** verify: rest FERR rms 0.06 um, torque rms 4.31%
```json
{
  "ferr_peak": 0.0002288818359375,
  "ferr_rms": 5.745720165443017e-05,
  "n": 1005.0,
  "torque_peak_pct": 7.0,
  "torque_rms_pct": 4.305160619558695
}
```

**[   148.4s | measure | measurement]** verify: peak=0.00320 rms=0.00067 score=0.00454 stable dom=400.2Hz tq=22%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233356_X/17_verify.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 400.2 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.09451091909634105,
    "ms": 0.013787384868411134,
    "n_samples": 7456,
    "peak_abs": 0.003204345703125,
    "peaks": [
      {
        "freq_hz": 400.21459227467807,
        "magnitude": 7.210525167471475e-05,
        "prominence": 24.962510727370418
      },
      {
        "freq_hz": 50.16094420600858,
        "magnitude": 6.0969769395425536e-05,
        "prominence": 21.10745732425365
      },
      {
        "freq_hz": 399.40987124463516,
        "magnitude": 5.787673470495689e-05,
        "prominence": 20.03666275870292
      },
      {
        "freq_hz": 300.02682403433477,
        "magnitude": 4.881452206090449e-05,
        "prominence": 16.89936588937936
      },
      {
        "freq_hz": 74.57081545064378,
        "magnitude": 4.760102610076366e-05,
        "prominence": 16.47925909800041
      }
    ],
    "ring_score": 0.49024397269146003,
    "rms": 0.0006680968915038747,
    "sensitivity": "Ms 0.01 @ 16 Hz (GM>=inf dB, PM>=180 deg; 3 coherent bins)"
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 360.0,
    "speed_gain_hz": 150.0,
    "torque_ff_pct": 120.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "capture": "realtime-sampler",
    "capture_error": null,
    "fs_hz": 1000.0,
    "machine_fault": false,
    "position_drift": -0.000152587890625,
    "tripped_ferr": null
  }
}
```

**[   148.4s | verify | ok]** verify: peak=0.00320 rms=0.00067 score=0.00454 stable dom=400.2Hz tq=22%

**[   148.4s | finalize | preset]** final tune saved as preset one_click_20261127_233624
```json
{
  "path": "/home/jon/linuxcnc/configs/ethercat_mill/config/tuning/presets/X/one_click_20261127_233624.json"
}
```

**[   148.4s | finalize | result]** campaign status: improved
```json
{
  "baseline_score": 0.01307202793944888,
  "baseline_values": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 130.0,
    "speed_gain_hz": 80.0,
    "torque_ff_pct": 120.0
  },
  "final_score": 0.004540539486132749,
  "final_values": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 360.0,
    "speed_gain_hz": 150.0,
    "torque_ff_pct": 120.0
  },
  "improvement_pct": 65.26522505027495,
  "measurements": 17,
  "notch_applied": false,
  "preset": "one_click_20261127_233624",
  "reason": "score improved 65.3%"
}
```


---

**FINAL STATUS: IMPROVED** — 2026-11-27T23:36:24
**[   148.9s | finalize | ferr-window]** 6065 restored to 0.5 production window

