# One-click tune — axis Y

- started: 2026-11-27T23:27:20
- engine: a6_auto_tune v2.1
- profile: conservative
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
  "position": 206.6418914794922
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

**[     1.8s | baseline | backup]** baseline preset saved: pre_one_click_20261127_232722
```json
{
  "path": "/home/jon/linuxcnc/configs/ethercat_mill/config/tuning/presets/Y/pre_one_click_20261127_232722.json"
}
```

**[     4.0s | baseline | ferr-window]** 6065 set to 1 mm for tuning (was 0.500031); production window is 0.5
```json
{
  "abort_ferr": 0.8,
  "prior": 0.500030517578125,
  "tuning": 1.0
}
```

**[     9.0s | measure | measurement]** baseline_1: peak=0.05928 rms=0.01823 score=0.09575 stable dom=85.1Hz tq=31%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_232720_Y/01_baseline_1.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 66.66666666666666,
    "gate_reason": "peak at 85.1 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.00019623829684510514,
    "ms": null,
    "n_samples": 4723,
    "peak_abs": 0.0592803955078125,
    "peaks": [
      {
        "freq_hz": 85.11539275883973,
        "magnitude": 2.972284391412554e-05,
        "prominence": 9.700484128255209
      },
      {
        "freq_hz": 120.89773449078976,
        "magnitude": 2.779945971809013e-05,
        "prominence": 9.072759610369777
      },
      {
        "freq_hz": 68.38873597289859,
        "magnitude": 2.492664368096042e-05,
        "prominence": 8.135174147414467
      },
      {
        "freq_hz": 70.08257463476605,
        "magnitude": 2.3304603701150755e-05,
        "prominence": 7.605797714762231
      },
      {
        "freq_hz": 87.02096125344062,
        "magnitude": 2.2967570656783267e-05,
        "prominence": 7.495802059332012
      }
    ],
    "ring_score": 0.028625771176839534,
    "rms": 0.01823415634514963,
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

**[    13.9s | measure | measurement]** baseline_2: peak=0.05196 rms=0.01799 score=0.08794 stable dom=69.1Hz tq=31%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_232720_Y/02_baseline_2.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 66.66666666666666,
    "gate_reason": "peak at 69.1 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.00022109690023764737,
    "ms": null,
    "n_samples": 4730,
    "peak_abs": 0.0519561767578125,
    "peaks": [
      {
        "freq_hz": 69.13319238900634,
        "magnitude": 3.7781439524449134e-05,
        "prominence": 13.042750660711793
      },
      {
        "freq_hz": 89.42917547568709,
        "magnitude": 3.653455855274425e-05,
        "prominence": 12.612307622483753
      },
      {
        "freq_hz": 87.52642706131077,
        "magnitude": 3.217270414559031e-05,
        "prominence": 11.10652647261463
      },
      {
        "freq_hz": 67.44186046511628,
        "magnitude": 3.129573258913621e-05,
        "prominence": 10.80378201683588
      },
      {
        "freq_hz": 75.89852008456658,
        "magnitude": 2.7739233656624427e-05,
        "prominence": 9.57602231827222
      }
    ],
    "ring_score": 0.027672722451708,
    "rms": 0.01799385555384959,
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

**[    18.9s | measure | measurement]** baseline_3: peak=0.05104 rms=0.01775 score=0.08654 stable dom=69.2Hz tq=31%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_232720_Y/03_baseline_3.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 66.66666666666666,
    "gate_reason": "peak at 69.2 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0002956664617142323,
    "ms": null,
    "n_samples": 4739,
    "peak_abs": 0.0510406494140625,
    "peaks": [
      {
        "freq_hz": 69.21291411690231,
        "magnitude": 4.1803597391202884e-05,
        "prominence": 13.98908117867333
      },
      {
        "freq_hz": 79.97467820215236,
        "magnitude": 3.634599006013052e-05,
        "prominence": 12.162757207527239
      },
      {
        "freq_hz": 68.79088415277485,
        "magnitude": 3.504072782612182e-05,
        "prominence": 11.725966584458837
      },
      {
        "freq_hz": 69.63494408102976,
        "magnitude": 3.473537633834341e-05,
        "prominence": 11.62378430788137
      },
      {
        "freq_hz": 71.5340789196033,
        "magnitude": 3.427806695827368e-05,
        "prominence": 11.47075111359196
      }
    ],
    "ring_score": 0.028381683055531213,
    "rms": 0.017751424982972993,
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
    "position_drift": 7.62939453125e-05,
    "tripped_ferr": null
  }
}
```

**[    18.9s | baseline | noise]** baseline spread 10.5% over 3 runs -> a step must improve the score by >= 15.0%
```json
{
  "improve_pct": 15.0,
  "scores": [
    0.09574870819811176,
    0.08794388786551169,
    0.08654349938000849
  ],
  "spread_pct": 10.467138810351836
}
```

**[    20.0s | rest | standstill]** baseline: rest FERR rms 0.06 um, torque rms 1.53%
```json
{
  "ferr_peak": 0.0002288818359375,
  "ferr_rms": 5.828704325904398e-05,
  "n": 1004.0,
  "torque_peak_pct": 2.4000000000000004,
  "torque_rms_pct": 1.53131001386582
}
```

**[    20.0s | speed | start]** speed ladder from 30.0 Hz, cap 120.0 Hz

**[    20.8s | speed | write]** SDO write speed_gain_hz=34.5
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    21.2s | measure | fault]** machine fault during speed_34.5hz
```json
{
  "meta": {
    "abort_reason": "machine dropped out of STATE_ON mid-leg",
    "aborted": true,
    "capture": "realtime-sampler",
    "capture_error": null,
    "fs_hz": 1000.0,
    "machine_fault": true,
    "machine_state": "machine is not ON (turn it on first)",
    "pos_cmd": [
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.643311,
      -20.64331,
      -20.643301,
      -20.643261,
      -20.643162,
      -20.642974,
      -20.642667,
      -20.642212,
      -20.641578,
      -20.640737,
      -20.639657,
      -20.638311,
      -20.636668,
      -20.634698,
      -20.632371,
      -20.629658,
      -20.62653,
      -20.622956,
      -20.618907,
      -20.614353,
      -20.609264,
      -20.603612,
      -20.597365,
      -20.590494,
      -20.623245,
      -20.618515,
      -20.613098,
      -20.608826,
      -20.608139,
      -20.608902,
      -20.610428,
      -20.612488,
      -20.614471,
      -20.616837,
      -20.618744,
      -20.619278,
      -20.618973,
      -20.618286,
      -20.617447,
      -20.616989,
      -20.616837,
      -20.616837,
      -20.617142,
      -20.617371,
      -20.617752,
      -20.617752,
      -20.617752,
      -20.617523,
      -20.617447,
      -20.617371,
      -20.617447,
      -20.617447,
      -20.617599,
      -20.617676,
      -20.617828,
      -20.617676,
      -20.617599,
      -20.617599,
      -20.617599,
      -20.617599,
      -20.617752,
      -20.617828,
      -20.617828,
      -20.617752,
      -20.617752,
      -20.617599,
      -20.617523,
      -20.617599,
      -20.617752,
      -20.617752,
      -20.617676,
      -20.617752,
      -20.617599,
      -20.617599,
      -20.617676,
      -20.617599,
      -20.617828,
      -20.617676,
      -20.617752,
      -20.617676,
      -20.617599,
      -20.617523,
      -20.617676,
      -20.617599,
      -20.617752,
      -20.617676,
      -20.617676,
      -20.617676,
      -20.617599,
      -20.617599,
      -20.617676,
      -20.617599,
      -20.617752,
      -20.617752,
      -20.617599,
      -20.617599,
      -20.617523,
      -20.617676,
      -20.617676,
      -20.617676,
      -20.617599,
      -20.617676,
      -20.617599,
      -20.617676,
      -20.617599,
      -20.617676,
      -20.617676,
      -20.617752,
      -20.617676,
      -20.617752,
      -20.617676,
      -20.617676,
      -20.617599,
      -20.617676,
      -20.617676,
      -20.617676,
      -20.617676,
      -20.617599,
      -20.617676,
      -20.617676,
      -20.617676,
      -20.617676,
      -20.617676,
      -20.617752,
      -20.617752,
      -20.617599,
      -20.617676,
      -20.617676,
      -20.617599,
      -20.617676,
      -20.617599,
      -20.617599,
      -20.617676,
      -20.617599,
      -20.617599,
      -20.617676,
      -20.617676,
      -20.617676,
      -20.617752,
      -20.617676,
      -20.617676,
      -20.617599,
      -20.617599,
      -20.617676,
      -20.617676,
      -20.617676,
      -20.617599,
      -20.617752,
      -20.617676,
      -20.617599,
      -20.617676,
      -20.617676,
      -20.617599,
      -20.617676,
      -20.617752,
      -20.617676
    ],
    "position_drift": 0.0257110595703125,
    "torque_pct": [
      0.0,
      -0.1,
      0.0,
      0.2,
      -0.1,
      -0.30000000000000004,
      0.1,
      0.1,
      0.1,
      -0.1,
      0.8,
      0.8,
      0.5,
      0.30000000000000004,
      0.30000000000000004,
      0.1,
      0.0,
      0.1,
      -0.1,
      0.30000000000000004,
      0.30000000000000004,
      0.0,
      0.6000000000000001,
      0.0,
      0.2,
      0.2,
      0.9,
      0.30000000000000004,
      0.30000000000000004,
      0.5,
      0.30000000000000004,
      0.1,
      0.7000000000000001,
      0.0,
      0.0,
      0.1,
      0.1,
      0.2,
      0.7000000000000001,
      0.4,
      0.1,
      -0.1,
      0.6000000000000001,
      1.3,
      0.7000000000000001,
      0.6000000000000001,
      0.1,
      0.4,
      0.1,
      0.0,
      0.4,
      -0.30000000000000004,
      0.2,
      0.0,
      0.2,
      0.0,
      0.0,
      0.1,
      0.8,
      0.5,
      0.30000000000000004,
      0.6000000000000001,
      0.4,
      0.4,
      0.30000000000000004,
      0.1,
      -0.4,
      -0.5,
      -0.2,
      0.1,
      0.0,
      1.4000000000000001,
      1.1,
      1.4000000000000001,
      2.1,
      2.4000000000000004,
      2.9000000000000004,
      4.3,
      3.7,
      4.4,
      7.0,
      6.300000000000001,
      7.9,
      9.4,
      9.600000000000001,
      11.600000000000001,
      13.3,
      11.700000000000001,
      12.8,
      13.700000000000001,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0,
      0.0
    ],
    "tripped_ferr": null
  }
}
```

**[    21.2s | error | exception]** OneClickError: machine fault during 'speed_34.5hz' (machine dropped out of STATE_ON mid-leg) — stopping the campaign; clear the fault before retrying
```json
{
  "traceback": "Traceback (most recent call last):\n  File \"/home/jon/linuxcnc/configs/ethercat_mill/probe_basic/python/a6_auto_tune.py\", line 1192, in run\n    ref = self._phase_speed(ref)\n  File \"/home/jon/linuxcnc/configs/ethercat_mill/probe_basic/python/a6_auto_tune.py\", line 1590, in _phase_speed\n    m = self._measure(f\"speed_{cand:.1f}hz\")\n  File \"/home/jon/linuxcnc/configs/ethercat_mill/probe_basic/python/a6_auto_tune.py\", line 2076, in _measure\n    raise OneClickError(\n    ...<3 lines>...\n    )\na6_auto_tune.OneClickError: machine fault during 'speed_34.5hz' (machine dropped out of STATE_ON mid-leg) \u2014 stopping the campaign; clear the fault before retrying\n"
}
```

**[    21.2s | error | revert]** restoring baseline values for touched keys
```json
{
  "values": {
    "speed_gain_hz": 30.0
  }
}
```

**[    21.3s | error | write]** SDO write speed_gain_hz=30
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    21.3s | error | revert-ok]** baseline restored

**[    21.3s | finalize | result]** campaign status: failed
```json
{
  "baseline_score": 0.08794388786551169,
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
  "final_score": null,
  "final_values": {
    "integral_ms": 10.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 90.0,
    "speed_gain_hz": 30.0,
    "torque_ff_pct": 125.0
  },
  "improvement_pct": null,
  "measurements": 4,
  "notch_applied": false,
  "preset": null,
  "reason": "OneClickError: machine fault during 'speed_34.5hz' (machine dropped out of STATE_ON mid-leg) \u2014 stopping the campaign; clear the fault before retrying"
}
```


---

**FINAL STATUS: FAILED** — 2026-11-27T23:27:42
**[    21.4s | finalize | ferr-window]** 6065 restored to 0.5 production window

