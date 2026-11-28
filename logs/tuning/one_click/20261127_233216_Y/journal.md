# One-click tune — axis Y

- started: 2026-11-27T23:32:16
- engine: a6_auto_tune v2.1
- profile: balanced
- stimulus: 4x 0<->15 mm @ F10000 (~3.2s per measurement)
- dry run: False

**[     0.0s | setup | config]** campaign configuration
```json
{
  "config": {
    "allow_notch": true,
    "allow_python_sampler": false,
    "axis": "Y",
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
      "axis": "Y",
      "cycles": 4,
      "dwell_s": 0.25,
      "feed": 10000.0,
      "settle_s": 0.5,
      "stroke": 15.0
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
  "max_limit": 308.0,
  "min_limit": -254.0,
  "opmode": null,
  "position": 132.89486694335938
}
```

**[     0.1s | preflight | info]** drive torque limit 0x6072 = 300% -> guard 240%

**[     0.1s | preflight | stimulus]** stimulus direction +15 mm
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
    "integral_2_ms": 4.0,
    "integral_ms": 10.0,
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
    "pos_gain_rad_s": 90.0,
    "speed_fb_filter": 3.0,
    "speed_fb_lpf_hz": 8000.0,
    "speed_ff_filter_hz": 318.0,
    "speed_ff_pct": 100.0,
    "speed_ff_source": 1.0,
    "speed_gain_2_hz": 300.0,
    "speed_gain_hz": 30.0,
    "stiffness_level": 16.0,
    "torque_ff_filter_hz": 318.0,
    "torque_ff_pct": 125.0,
    "torque_ff_source": 1.0,
    "torque_filter_2_hz": 820.0,
    "torque_filter_hz": 920.0
  }
}
```

**[     1.8s | baseline | backup]** baseline preset saved: pre_one_click_20261127_233218
```json
{
  "path": "/home/jon/linuxcnc/configs/ethercat_mill/config/tuning/presets/Y/pre_one_click_20261127_233218.json"
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

**[     9.1s | measure | measurement]** baseline_1: peak=0.06264 rms=0.01779 score=0.09822 stable dom=71.4Hz tq=30%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233216_Y/01_baseline_1.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 66.66666666666666,
    "gate_reason": "peak at 71.4 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.00021590366888529528,
    "ms": null,
    "n_samples": 4750,
    "peak_abs": 0.0626373291015625,
    "peaks": [
      {
        "freq_hz": 71.36842105263158,
        "magnitude": 3.519162672125876e-05,
        "prominence": 11.338569544688367
      },
      {
        "freq_hz": 72.0,
        "magnitude": 2.9386527565505655e-05,
        "prominence": 9.468195065762774
      },
      {
        "freq_hz": 70.10526315789474,
        "magnitude": 2.836769803859414e-05,
        "prominence": 9.139933188681379
      },
      {
        "freq_hz": 92.21052631578947,
        "magnitude": 2.7036191015762364e-05,
        "prominence": 8.710928155830798
      },
      {
        "freq_hz": 77.68421052631578,
        "magnitude": 2.4076457484290835e-05,
        "prominence": 7.757316526958199
      }
    ],
    "ring_score": 0.030715383713245684,
    "rms": 0.017789642830695594,
    "sensitivity": "|S| n/a (only 0 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 10.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 90.0,
    "speed_gain_hz": 30.0,
    "torque_ff_pct": 125.0
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

**[    14.0s | measure | measurement]** baseline_2: peak=0.05203 rms=0.01755 score=0.08714 stable dom=70.7Hz tq=30%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233216_Y/02_baseline_2.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 66.66666666666666,
    "gate_reason": "peak at 70.7 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.00026311513524638003,
    "ms": null,
    "n_samples": 4739,
    "peak_abs": 0.052032470703125,
    "peaks": [
      {
        "freq_hz": 70.6900189913484,
        "magnitude": 4.6779771275457794e-05,
        "prominence": 15.02836394127032
      },
      {
        "freq_hz": 72.58915382992193,
        "magnitude": 3.6770563729271226e-05,
        "prominence": 11.812828472273331
      },
      {
        "freq_hz": 66.89174931420132,
        "magnitude": 3.215584629145129e-05,
        "prominence": 10.330314743565372
      },
      {
        "freq_hz": 70.05697404515722,
        "magnitude": 2.752491826148761e-05,
        "prominence": 8.842593236542182
      },
      {
        "freq_hz": 92.00253217978477,
        "magnitude": 2.5767275499380483e-05,
        "prominence": 8.277936882150312
      }
    ],
    "ring_score": 0.02926535161924988,
    "rms": 0.017552572402075178,
    "sensitivity": "|S| n/a (only 1 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 10.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 90.0,
    "speed_gain_hz": 30.0,
    "torque_ff_pct": 125.0
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

**[    18.9s | measure | measurement]** baseline_3: peak=0.05096 rms=0.01773 score=0.08642 stable dom=70.7Hz tq=30%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233216_Y/03_baseline_3.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 66.66666666666666,
    "gate_reason": "peak at 70.7 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.00027868755859476036,
    "ms": null,
    "n_samples": 4735,
    "peak_abs": 0.05096435546875,
    "peaks": [
      {
        "freq_hz": 70.74973600844773,
        "magnitude": 4.307705383549305e-05,
        "prominence": 14.986962225161506
      },
      {
        "freq_hz": 77.71911298838437,
        "magnitude": 3.931475265280127e-05,
        "prominence": 13.67801788741704
      },
      {
        "freq_hz": 69.90496304118268,
        "magnitude": 3.776751343263183e-05,
        "prominence": 13.139717013022937
      },
      {
        "freq_hz": 71.80570221752903,
        "magnitude": 3.204713346761534e-05,
        "prominence": 11.149536375863502
      },
      {
        "freq_hz": 72.86166842661035,
        "magnitude": 3.0481842589796832e-05,
        "prominence": 10.604955139021186
      }
    ],
    "ring_score": 0.02925150226807368,
    "rms": 0.017730000642158954,
    "sensitivity": "|S| n/a (only 1 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 10.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 90.0,
    "speed_gain_hz": 30.0,
    "torque_ff_pct": 125.0
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

**[    18.9s | baseline | noise]** baseline spread 13.5% over 3 runs -> a step must improve the score by >= 15.0%
```json
{
  "improve_pct": 15.0,
  "scores": [
    0.09821661476295368,
    0.08713761550727536,
    0.08642435675306791
  ],
  "spread_pct": 13.532913359215348
}
```

**[    20.1s | rest | standstill]** baseline: rest FERR rms 0.07 um, torque rms 0.42%
```json
{
  "ferr_peak": 0.00030517578125,
  "ferr_rms": 7.155387786530304e-05,
  "n": 1005.0,
  "torque_peak_pct": 1.1,
  "torque_rms_pct": 0.41875199561416515
}
```

**[    20.1s | speed | start]** speed ladder from 30.0 Hz, cap 200.0 Hz

**[    20.9s | speed | write]** SDO write speed_gain_hz=37.5
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    25.8s | measure | measurement]** speed_37.5hz: peak=0.04379 rms=0.01540 score=0.07458 stable dom=71.2Hz tq=30%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233216_Y/04_speed_37.5hz.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 66.66666666666666,
    "gate_reason": "peak at 71.2 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0002960851998226602,
    "ms": null,
    "n_samples": 4744,
    "peak_abs": 0.043792724609375,
    "peaks": [
      {
        "freq_hz": 71.247892074199,
        "magnitude": 3.4230810755980075e-05,
        "prominence": 11.451219435557986
      },
      {
        "freq_hz": 67.03204047217538,
        "magnitude": 3.323254990238574e-05,
        "prominence": 11.117271631343648
      },
      {
        "freq_hz": 71.88026981450254,
        "magnitude": 3.0235910987705157e-05,
        "prominence": 10.114807213373505
      },
      {
        "freq_hz": 92.95952782462058,
        "magnitude": 2.7291873749170204e-05,
        "prominence": 9.129939613092423
      },
      {
        "freq_hz": 69.77234401349074,
        "magnitude": 2.660712185089339e-05,
        "prominence": 8.900869834348931
      }
    ],
    "ring_score": 0.029331928575791085,
    "rms": 0.015395413632929789,
    "sensitivity": "|S| n/a (only 1 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 10.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 90.0,
    "speed_gain_hz": 37.5,
    "torque_ff_pct": 125.0
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

**[    25.8s | speed | stall]** 37.5 Hz stable but no 15.0% improvement (speed_37.5hz: peak=0.04379 rms=0.01540 score=0.07458 stable dom=71.2Hz tq=30%) — reverting to 30.0 Hz (stall 1/2)

**[    26.6s | speed | write]** SDO write speed_gain_hz=30
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    27.3s | speed | write]** SDO write speed_gain_hz=37.5
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    32.3s | measure | measurement]** speed_37.5hz: peak=0.04272 rms=0.01548 score=0.07369 stable dom=70.0Hz tq=29%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233216_Y/05_speed_37.5hz.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 66.66666666666666,
    "gate_reason": "peak at 70.0 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0003119243661345157,
    "ms": null,
    "n_samples": 4727,
    "peak_abs": 0.042724609375,
    "peaks": [
      {
        "freq_hz": 70.0232705733023,
        "magnitude": 4.457636312244899e-05,
        "prominence": 14.595060783646895
      },
      {
        "freq_hz": 71.9272265707637,
        "magnitude": 3.409258905741475e-05,
        "prominence": 11.162494530969857
      },
      {
        "freq_hz": 75.94668923207108,
        "magnitude": 2.67754604520622e-05,
        "prominence": 8.766741955473188
      },
      {
        "freq_hz": 77.00444256399408,
        "magnitude": 2.5055552625410768e-05,
        "prominence": 8.203614829034153
      },
      {
        "freq_hz": 69.17706790776391,
        "magnitude": 2.3611958219467692e-05,
        "prominence": 7.7309574243958386
      }
    ],
    "ring_score": 0.029195229653372262,
    "rms": 0.01548209192137241,
    "sensitivity": "|S| n/a (only 1 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 10.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 90.0,
    "speed_gain_hz": 37.5,
    "torque_ff_pct": 125.0
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

**[    32.3s | speed | accept]** 37.5 Hz accepted (speed_37.5hz: peak=0.04272 rms=0.01548 score=0.07369 stable dom=70.0Hz tq=29%)

**[    33.0s | speed | write]** SDO write speed_gain_hz=46.875
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    38.0s | measure | measurement]** speed_46.9hz: peak=0.03593 rms=0.01362 score=0.06317 stable dom=83.5Hz tq=30%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233216_Y/06_speed_46.9hz.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 66.66666666666666,
    "gate_reason": "peak at 83.5 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.00040201867981500857,
    "ms": null,
    "n_samples": 4743,
    "peak_abs": 0.0359344482421875,
    "peaks": [
      {
        "freq_hz": 83.49146110056925,
        "magnitude": 4.418910221389145e-05,
        "prominence": 13.824976103958992
      },
      {
        "freq_hz": 85.5998313303816,
        "magnitude": 3.663931580481716e-05,
        "prominence": 11.462954441010734
      },
      {
        "freq_hz": 71.05207674467636,
        "magnitude": 3.606170551648943e-05,
        "prominence": 11.28224363147948
      },
      {
        "freq_hz": 69.15454353784524,
        "magnitude": 3.5326766332392976e-05,
        "prominence": 11.052310997663657
      },
      {
        "freq_hz": 86.23234239932532,
        "magnitude": 3.484524506793006e-05,
        "prominence": 10.901662542700135
      }
    ],
    "ring_score": 0.029018359113279178,
    "rms": 0.01361636624569797,
    "sensitivity": "|S| n/a (only 1 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 10.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 90.0,
    "speed_gain_hz": 46.875,
    "torque_ff_pct": 125.0
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

**[    38.0s | speed | stall]** 46.9 Hz stable but no 15.0% improvement (speed_46.9hz: peak=0.03593 rms=0.01362 score=0.06317 stable dom=83.5Hz tq=30%) — reverting to 37.5 Hz (stall 1/2)

**[    38.8s | speed | write]** SDO write speed_gain_hz=37.5
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    39.5s | speed | write]** SDO write speed_gain_hz=46.875
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    44.4s | measure | measurement]** speed_46.9hz: peak=0.03632 rms=0.01347 score=0.06326 stable dom=67.7Hz tq=30%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233216_Y/07_speed_46.9hz.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 66.66666666666666,
    "gate_reason": "peak at 67.7 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0003493932401326815,
    "ms": null,
    "n_samples": 4753,
    "peak_abs": 0.03631591796875,
    "peaks": [
      {
        "freq_hz": 67.74668630338734,
        "magnitude": 2.7535293869680905e-05,
        "prominence": 9.595732640854965
      },
      {
        "freq_hz": 76.16242373237955,
        "magnitude": 2.7170398397153127e-05,
        "prominence": 9.468570773151406
      },
      {
        "freq_hz": 92.57311171891436,
        "magnitude": 2.612152983185689e-05,
        "prominence": 9.103052163631062
      },
      {
        "freq_hz": 71.32337471070902,
        "magnitude": 2.4927315688019044e-05,
        "prominence": 8.68688229471917
      },
      {
        "freq_hz": 68.58826004628655,
        "magnitude": 2.429784712275392e-05,
        "prominence": 8.467519752714214
      }
    ],
    "ring_score": 0.02897417012459163,
    "rms": 0.013472155197729312,
    "sensitivity": "|S| n/a (only 1 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 10.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 90.0,
    "speed_gain_hz": 46.875,
    "torque_ff_pct": 125.0
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

**[    44.5s | speed | stall]** 46.9 Hz stable but no 15.0% improvement (speed_46.9hz: peak=0.03632 rms=0.01347 score=0.06326 stable dom=67.7Hz tq=30%) — reverting to 37.5 Hz (stall 2/2)

**[    45.2s | speed | write]** SDO write speed_gain_hz=37.5
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    45.2s | position | start]** position ladder from 90.0 rad/s toward ~75.0 (cap 90.0)

**[    45.2s | position | skip]** already at/above cap — leaving it alone

**[    45.2s | integral | start]** integral tighten from 10.00 ms toward 3.00 ms (lower = stronger)

**[    46.0s | integral | write]** SDO write integral_ms=7
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "integral_ms"
  ]
}
```

**[    50.9s | measure | measurement]** integral_7.00ms: peak=0.03700 rms=0.01331 score=0.06363 stable dom=70.6Hz tq=30%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233216_Y/08_integral_7.00ms.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 66.66666666666666,
    "gate_reason": "peak at 70.6 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.000488882732827049,
    "ms": null,
    "n_samples": 4719,
    "peak_abs": 0.0370025634765625,
    "peaks": [
      {
        "freq_hz": 70.5657978385251,
        "magnitude": 3.338452734509029e-05,
        "prominence": 10.609932633618506
      },
      {
        "freq_hz": 72.47298156389064,
        "magnitude": 3.130467265560134e-05,
        "prominence": 9.948934264071765
      },
      {
        "freq_hz": 69.50625132443314,
        "magnitude": 3.0432913299658112e-05,
        "prominence": 9.67188052766041
      },
      {
        "freq_hz": 70.9896164441619,
        "magnitude": 2.8909012897013576e-05,
        "prominence": 9.187569923371429
      },
      {
        "freq_hz": 67.1752489934308,
        "magnitude": 2.8667867276502647e-05,
        "prominence": 9.110931462623853
      }
    ],
    "ring_score": 0.031120414232822198,
    "rms": 0.013313484464883655,
    "sensitivity": "|S| n/a (only 1 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 7.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 90.0,
    "speed_gain_hz": 37.5,
    "torque_ff_pct": 125.0
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

**[    50.9s | integral | accept]** 7.00 ms accepted (rms +14.0%, peak -13.4%)

**[    51.7s | integral | write]** SDO write integral_ms=4.9
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "integral_ms"
  ]
}
```

**[    56.6s | measure | measurement]** integral_4.90ms: peak=0.03227 rms=0.01184 score=0.05595 stable dom=69.6Hz tq=30%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233216_Y/09_integral_4.90ms.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 66.66666666666666,
    "gate_reason": "peak at 69.6 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0008112217761137383,
    "ms": null,
    "n_samples": 4741,
    "peak_abs": 0.0322723388671875,
    "peaks": [
      {
        "freq_hz": 69.60556844547564,
        "magnitude": 4.019226962034828e-05,
        "prominence": 12.4793183391562
      },
      {
        "freq_hz": 71.50390213035224,
        "magnitude": 3.825034597366281e-05,
        "prominence": 11.87636947346054
      },
      {
        "freq_hz": 68.55093862054419,
        "magnitude": 3.5719732483944065e-05,
        "prominence": 11.090637997485993
      },
      {
        "freq_hz": 70.6601982704071,
        "magnitude": 3.557756810465366e-05,
        "prominence": 11.046497306691181
      },
      {
        "freq_hz": 83.10483020459819,
        "magnitude": 3.539379825355514e-05,
        "prominence": 10.98943851168756
      }
    ],
    "ring_score": 0.03237148669036795,
    "rms": 0.011840031654146106,
    "sensitivity": "|S| n/a (only 1 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 4.8999999999999995,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 90.0,
    "speed_gain_hz": 37.5,
    "torque_ff_pct": 125.0
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

**[    56.6s | integral | accept]** 4.90 ms accepted (rms +11.1%, peak -12.8%)

**[    57.4s | integral | write]** SDO write integral_ms=3.43
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "integral_ms"
  ]
}
```

**[    62.3s | measure | measurement]** integral_3.43ms: peak=0.02571 rms=0.01069 score=0.04709 stable dom=76.5Hz tq=30%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233216_Y/10_integral_3.43ms.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 66.66666666666666,
    "gate_reason": "peak at 76.5 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.000940351189336508,
    "ms": null,
    "n_samples": 4731,
    "peak_abs": 0.0257110595703125,
    "peaks": [
      {
        "freq_hz": 76.51659268653562,
        "magnitude": 3.603873054813496e-05,
        "prominence": 11.40955445658426
      },
      {
        "freq_hz": 91.10124709363771,
        "magnitude": 3.5025181076913274e-05,
        "prominence": 11.088673345888632
      },
      {
        "freq_hz": 68.69583597548088,
        "magnitude": 3.463242914234732e-05,
        "prominence": 10.964331436026576
      },
      {
        "freq_hz": 93.00359332065104,
        "magnitude": 3.3410182799798404e-05,
        "prominence": 10.577378677353602
      },
      {
        "freq_hz": 82.43500317057705,
        "magnitude": 3.250591681697844e-05,
        "prominence": 10.29109578621678
      }
    ],
    "ring_score": 0.03233978532952697,
    "rms": 0.010691956513035401,
    "sensitivity": "|S| n/a (only 1 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 3.4299999999999993,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 90.0,
    "speed_gain_hz": 37.5,
    "torque_ff_pct": 125.0
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

**[    62.3s | integral | accept]** 3.43 ms accepted (rms +9.7%, peak -20.3%)

**[    63.1s | integral | write]** SDO write integral_ms=3
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "integral_ms"
  ]
}
```

**[    68.0s | measure | measurement]** integral_3.00ms: peak=0.02472 rms=0.01034 score=0.04541 stable dom=70.5Hz tq=30%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233216_Y/11_integral_3.00ms.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 66.66666666666666,
    "gate_reason": "peak at 70.5 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.001094850478934467,
    "ms": null,
    "n_samples": 4735,
    "peak_abs": 0.02471923828125,
    "peaks": [
      {
        "freq_hz": 70.53854276663147,
        "magnitude": 5.621104059986308e-05,
        "prominence": 17.811506246527095
      },
      {
        "freq_hz": 69.48257655755016,
        "magnitude": 4.803226245010214e-05,
        "prominence": 15.219909354727497
      },
      {
        "freq_hz": 68.6378035902851,
        "magnitude": 4.0012444514908175e-05,
        "prominence": 12.67868194238414
      },
      {
        "freq_hz": 71.38331573389651,
        "magnitude": 3.980498099229068e-05,
        "prominence": 12.612943294076018
      },
      {
        "freq_hz": 72.65047518479409,
        "magnitude": 3.6222015294806654e-05,
        "prominence": 11.477614447273197
      }
    ],
    "ring_score": 0.03212405771512606,
    "rms": 0.010343885814429141,
    "sensitivity": "|S| n/a (only 1 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 90.0,
    "speed_gain_hz": 37.5,
    "torque_ff_pct": 125.0
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

**[    68.0s | integral | accept]** 3.00 ms accepted (rms +3.3%, peak -3.9%)

**[    68.0s | integral | done]** reached floor

**[    68.0s | feedforward | start]** torque FF 125% (search 50-200%)

**[    68.8s | feedforward | write]** SDO write torque_ff_pct=143.8
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "torque_ff_pct"
  ]
}
```

**[    73.7s | measure | measurement]** ff_143.8pct: peak=0.02434 rms=0.01030 score=0.04494 stable dom=70.1Hz tq=30%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233216_Y/12_ff_143.8pct.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 66.66666666666666,
    "gate_reason": "peak at 70.1 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0009631318558208211,
    "ms": null,
    "n_samples": 4750,
    "peak_abs": 0.0243377685546875,
    "peaks": [
      {
        "freq_hz": 70.10526315789474,
        "magnitude": 4.460672995808939e-05,
        "prominence": 14.401764645798584
      },
      {
        "freq_hz": 69.26315789473684,
        "magnitude": 4.168980176033031e-05,
        "prominence": 13.460002866078584
      },
      {
        "freq_hz": 70.94736842105263,
        "magnitude": 3.8740311058867844e-05,
        "prominence": 12.507727930270821
      },
      {
        "freq_hz": 68.63157894736841,
        "magnitude": 3.6341524996382904e-05,
        "prominence": 11.733253936324422
      },
      {
        "freq_hz": 67.36842105263158,
        "magnitude": 3.51366938970837e-05,
        "prominence": 11.344261200332593
      }
    ],
    "ring_score": 0.03165020990002896,
    "rms": 0.010302013230199887,
    "sensitivity": "|S| n/a (only 1 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 90.0,
    "speed_gain_hz": 37.5,
    "torque_ff_pct": 143.8
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

**[    73.7s | feedforward | stall]** 143.8% no better — back to 125%

**[    74.5s | feedforward | write]** SDO write torque_ff_pct=125
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "torque_ff_pct"
  ]
}
```

**[    75.3s | feedforward | write]** SDO write torque_ff_pct=108.7
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "torque_ff_pct"
  ]
}
```

**[    80.2s | measure | measurement]** ff_108.7pct: peak=0.02472 rms=0.01038 score=0.04549 stable dom=69.3Hz tq=30%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233216_Y/13_ff_108.7pct.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 66.66666666666666,
    "gate_reason": "peak at 69.3 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0010647813253708413,
    "ms": null,
    "n_samples": 4736,
    "peak_abs": 0.02471923828125,
    "peaks": [
      {
        "freq_hz": 69.25675675675676,
        "magnitude": 4.9170006051902217e-05,
        "prominence": 16.46351654980749
      },
      {
        "freq_hz": 70.3125,
        "magnitude": 4.1876960526391745e-05,
        "prominence": 14.021597474568816
      },
      {
        "freq_hz": 71.1570945945946,
        "magnitude": 4.080715639076619e-05,
        "prominence": 13.663396621932508
      },
      {
        "freq_hz": 76.01351351351352,
        "magnitude": 3.655503890666214e-05,
        "prominence": 12.239666746907108
      },
      {
        "freq_hz": 68.20101351351352,
        "magnitude": 3.3469368139779567e-05,
        "prominence": 11.20649640960423
      }
    ],
    "ring_score": 0.03242556273215649,
    "rms": 0.010384841039725128,
    "sensitivity": "|S| n/a (only 1 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 90.0,
    "speed_gain_hz": 37.5,
    "torque_ff_pct": 108.7
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

**[    80.2s | feedforward | stall]** 108.7% no better — back to 125%

**[    81.0s | feedforward | write]** SDO write torque_ff_pct=125
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "torque_ff_pct"
  ]
}
```

**[    87.1s | rest | standstill]** verify: rest FERR rms 0.07 um, torque rms 2.86%
```json
{
  "ferr_peak": 0.0002288818359375,
  "ferr_rms": 6.769454509583638e-05,
  "n": 1006.0,
  "torque_peak_pct": 3.7,
  "torque_rms_pct": 2.856705341394991
}
```

**[    87.1s | measure | measurement]** verify: peak=0.02419 rms=0.01033 score=0.04484 stable dom=70.7Hz tq=30%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_233216_Y/14_verify.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 66.66666666666666,
    "gate_reason": "peak at 70.7 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.001091488174069881,
    "ms": null,
    "n_samples": 4738,
    "peak_abs": 0.0241851806640625,
    "peaks": [
      {
        "freq_hz": 70.70493879273955,
        "magnitude": 6.071139628521173e-05,
        "prominence": 19.64716884492786
      },
      {
        "freq_hz": 68.80540312368088,
        "magnitude": 5.9477204989004395e-05,
        "prominence": 19.247765005332223
      },
      {
        "freq_hz": 69.86070071760236,
        "magnitude": 5.188831392418039e-05,
        "prominence": 16.791879731405817
      },
      {
        "freq_hz": 67.96116504854369,
        "magnitude": 4.3728961932531e-05,
        "prominence": 14.151384271673123
      },
      {
        "freq_hz": 71.76023638666103,
        "magnitude": 3.8656565924358954e-05,
        "prominence": 12.509876631942404
      }
    ],
    "ring_score": 0.03182559678281514,
    "rms": 0.010329745526932138,
    "sensitivity": "|S| n/a (only 1 coherent bins (the move did not excite enough frequencies))"
  },
  "gains": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 90.0,
    "speed_gain_hz": 37.5,
    "torque_ff_pct": 125.0
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

**[    87.1s | verify | ok]** verify: peak=0.02419 rms=0.01033 score=0.04484 stable dom=70.7Hz tq=30%

**[    87.1s | finalize | preset]** final tune saved as preset one_click_20261127_233343
```json
{
  "path": "/home/jon/linuxcnc/configs/ethercat_mill/config/tuning/presets/Y/one_click_20261127_233343.json"
}
```

**[    87.1s | finalize | result]** campaign status: improved
```json
{
  "baseline_score": 0.08713761550727536,
  "baseline_values": {
    "integral_ms": 10.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 90.0,
    "speed_gain_hz": 30.0,
    "torque_ff_pct": 125.0
  },
  "final_score": 0.044844671717926776,
  "final_values": {
    "integral_ms": 3.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 90.0,
    "speed_gain_hz": 37.5,
    "torque_ff_pct": 125.0
  },
  "improvement_pct": 48.53580574030905,
  "measurements": 14,
  "notch_applied": false,
  "preset": "one_click_20261127_233343",
  "reason": "score improved 48.5%"
}
```


---

**FINAL STATUS: IMPROVED** — 2026-11-27T23:33:43
**[    87.6s | finalize | ferr-window]** 6065 restored to 0.5 production window

