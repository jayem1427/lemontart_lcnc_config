# One-click tune — axis Z

- started: 2026-11-27T23:40:05
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
  "position": -37.38911437988281
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

**[     1.8s | baseline | backup]** baseline preset saved: pre_one_click_20261127_234007
```json
{
  "path": "/home/jon/linuxcnc/configs/ethercat_mill/config/tuning/presets/Z/pre_one_click_20261127_234007.json"
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

**[     8.7s | measure | measurement]** baseline_1: peak=0.18173 rms=0.02046 score=0.22265 stable dom=75.8Hz tq=117%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_234005_Z/01_baseline_1.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 75.8 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0013177817466503677,
    "ms": null,
    "n_samples": 4499,
    "peak_abs": 0.181732177734375,
    "peaks": [
      {
        "freq_hz": 75.79462102689487,
        "magnitude": 0.0001697819348811082,
        "prominence": 54.3249420086217
      },
      {
        "freq_hz": 76.90597910646811,
        "magnitude": 0.00013945996769884568,
        "prominence": 44.62285497611591
      },
      {
        "freq_hz": 74.68326294732164,
        "magnitude": 0.0001313375659465669,
        "prominence": 42.02393887545855
      },
      {
        "freq_hz": 77.79506557012671,
        "magnitude": 0.0001286806637364726,
        "prominence": 41.17381274992567
      },
      {
        "freq_hz": 69.79328739719938,
        "magnitude": 0.00012341626234868558,
        "prominence": 39.48936793368593
      }
    ],
    "ring_score": 0.1347640448471464,
    "rms": 0.020459681172693724,
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

**[    13.4s | measure | measurement]** baseline_2: peak=0.04799 rms=0.01937 score=0.08673 stable dom=75.7Hz tq=43%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_234005_Z/02_baseline_2.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 75.7 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0017648975053712092,
    "ms": null,
    "n_samples": 4494,
    "peak_abs": 0.0479888916015625,
    "peaks": [
      {
        "freq_hz": 75.65643079661771,
        "magnitude": 0.00024930392328136465,
        "prominence": 82.7542361519143
      },
      {
        "freq_hz": 77.65910102358701,
        "magnitude": 0.00020715723526321112,
        "prominence": 68.7640151904135
      },
      {
        "freq_hz": 74.76635514018692,
        "magnitude": 0.00020096271564855323,
        "prominence": 66.70779909765463
      },
      {
        "freq_hz": 73.65376056964843,
        "magnitude": 0.00019663857642401752,
        "prominence": 65.2724392612307
      },
      {
        "freq_hz": 76.76902536715622,
        "magnitude": 0.00019050916376817665,
        "prominence": 63.2378348486017
      }
    ],
    "ring_score": 0.02839769652859242,
    "rms": 0.019369377761406938,
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

**[    18.0s | measure | measurement]** baseline_3: peak=0.04875 rms=0.01950 score=0.08774 stable dom=64.3Hz tq=43%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_234005_Z/03_baseline_3.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 64.3 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0016360440082939364,
    "ms": null,
    "n_samples": 4479,
    "peak_abs": 0.0487518310546875,
    "peaks": [
      {
        "freq_hz": 64.30006697923643,
        "magnitude": 0.0002772620743156025,
        "prominence": 92.12185771342175
      },
      {
        "freq_hz": 77.69591426657736,
        "magnitude": 0.0002572243579385248,
        "prominence": 85.46421561957416
      },
      {
        "freq_hz": 62.2906898861353,
        "magnitude": 0.0002559681397455706,
        "prominence": 85.04683017688787
      },
      {
        "freq_hz": 75.68653717347621,
        "magnitude": 0.0002439900037872543,
        "prominence": 81.06702825429242
      },
      {
        "freq_hz": 79.7052913596785,
        "magnitude": 0.0001936730132605897,
        "prominence": 64.34892985115954
      }
    ],
    "ring_score": 0.02833989490244087,
    "rms": 0.01949535762058352,
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

**[    18.1s | baseline | noise]** baseline spread 154.9% over 3 runs -> a step must improve the score by >= 15.0%
```json
{
  "improve_pct": 15.0,
  "scores": [
    0.22265154007976246,
    0.08672764712437638,
    0.08774254629585454
  ],
  "spread_pct": 154.9121819385904
}
```

**[    19.2s | rest | standstill]** baseline: rest FERR rms 0.10 um, torque rms 12.22%
```json
{
  "ferr_peak": 0.00030517578125,
  "ferr_rms": 0.00010352584728985747,
  "n": 1008.0,
  "torque_peak_pct": 13.5,
  "torque_rms_pct": 12.221597296433494
}
```

**[    19.3s | speed | cap]** speed gain capped at 37.5 Hz (0.25 x C01.03 torque filter 150 Hz)

**[    19.3s | speed | start]** speed ladder from 26.0 Hz, cap 37.5 Hz

**[    20.0s | speed | write]** SDO write speed_gain_hz=29.9
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    24.7s | measure | measurement]** speed_29.9hz: peak=0.04524 rms=0.01796 score=0.08115 stable dom=75.4Hz tq=44%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_234005_Z/04_speed_29.9hz.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 75.4 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0014675234910431002,
    "ms": null,
    "n_samples": 4481,
    "peak_abs": 0.0452423095703125,
    "peaks": [
      {
        "freq_hz": 75.42959160901584,
        "magnitude": 0.00013551710408537995,
        "prominence": 42.27047680119048
      },
      {
        "freq_hz": 77.43807185896006,
        "magnitude": 0.0001343234096801292,
        "prominence": 41.89813980354425
      },
      {
        "freq_hz": 64.04820352599866,
        "magnitude": 0.00013033532093529617,
        "prominence": 40.65417570095138
      },
      {
        "freq_hz": 82.57085471992859,
        "magnitude": 0.00012268964432739462,
        "prominence": 38.26933728616287
      },
      {
        "freq_hz": 80.33920999776835,
        "magnitude": 0.00012076539730789287,
        "prominence": 37.669126415759656
      }
    ],
    "ring_score": 0.027429927865475573,
    "rms": 0.0179553032624708,
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
    "position_drift": 0.0061798095703125,
    "tripped_ferr": null
  }
}
```

**[    24.7s | speed | stall]** 29.9 Hz stable but no 15.0% improvement (speed_29.9hz: peak=0.04524 rms=0.01796 score=0.08115 stable dom=75.4Hz tq=44%) — reverting to 26.0 Hz (stall 1/2)

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

**[    26.2s | speed | write]** SDO write speed_gain_hz=29.9
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    30.9s | measure | measurement]** speed_29.9hz: peak=0.04654 rms=0.01797 score=0.08248 stable dom=64.1Hz tq=44%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_234005_Z/05_speed_29.9hz.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 64.1 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0017256972224406926,
    "ms": null,
    "n_samples": 4477,
    "peak_abs": 0.046539306640625,
    "peaks": [
      {
        "freq_hz": 64.10542774179137,
        "magnitude": 0.0001675292699028963,
        "prominence": 54.57525174789427
      },
      {
        "freq_hz": 69.24279651552379,
        "magnitude": 0.00015129118137860366,
        "prominence": 49.285443169181285
      },
      {
        "freq_hz": 68.12597721688631,
        "magnitude": 0.00014890578144513534,
        "prominence": 48.50836223303263
      },
      {
        "freq_hz": 66.11570247933884,
        "magnitude": 0.00014510177150233477,
        "prominence": 47.26914713706662
      },
      {
        "freq_hz": 67.23252177797632,
        "magnitude": 0.00013785465558942403,
        "prominence": 44.90828699828297
      }
    ],
    "ring_score": 0.028191153906829566,
    "rms": 0.017968016063250762,
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
    "position_drift": 0.0020599365234375,
    "tripped_ferr": null
  }
}
```

**[    30.9s | speed | stall]** 29.9 Hz stable but no 15.0% improvement (speed_29.9hz: peak=0.04654 rms=0.01797 score=0.08248 stable dom=64.1Hz tq=44%) — reverting to 26.0 Hz (stall 2/2)

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

**[    37.1s | measure | measurement]** pos_60.0rads: peak=0.04387 rms=0.01657 score=0.07700 stable dom=69.0Hz tq=44%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_234005_Z/06_pos_60.0rads.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 69.0 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.002474473822315192,
    "ms": null,
    "n_samples": 4476,
    "peak_abs": 0.0438690185546875,
    "peaks": [
      {
        "freq_hz": 69.03485254691688,
        "magnitude": 0.0002935960886435714,
        "prominence": 92.80904807380374
      },
      {
        "freq_hz": 67.02412868632707,
        "magnitude": 0.0002325961703024314,
        "prominence": 73.5262831705768
      },
      {
        "freq_hz": 71.0455764075067,
        "magnitude": 0.00021355816804264892,
        "prominence": 67.50815508474126
      },
      {
        "freq_hz": 69.4816800714924,
        "magnitude": 0.00017333412970253311,
        "prominence": 54.792881099731126
      },
      {
        "freq_hz": 67.47095621090259,
        "magnitude": 0.0001693845619439808,
        "prominence": 53.54437800942181
      }
    ],
    "ring_score": 0.0316676734327381,
    "rms": 0.016565300073087253,
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
    "position_drift": 0.00213623046875,
    "tripped_ferr": null
  }
}
```

**[    37.1s | position | stall]** 60.0 rad/s stable but no improvement (pos_60.0rads: peak=0.04387 rms=0.01657 score=0.07700 stable dom=69.0Hz tq=44%) — reverting to 50.0 (stall 1/2)

**[    37.9s | position | write]** SDO write pos_gain_rad_s=50
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    38.7s | position | write]** SDO write pos_gain_rad_s=60
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    43.3s | measure | measurement]** pos_60.0rads: peak=0.04128 rms=0.01662 score=0.07452 stable dom=69.1Hz tq=45%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_234005_Z/07_pos_60.0rads.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 69.1 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0025624431777387154,
    "ms": null,
    "n_samples": 4470,
    "peak_abs": 0.0412750244140625,
    "peaks": [
      {
        "freq_hz": 69.1275167785235,
        "magnitude": 0.00031985634708511974,
        "prominence": 100.75629823508658
      },
      {
        "freq_hz": 67.11409395973155,
        "magnitude": 0.00022726293910839355,
        "prominence": 71.58892633915434
      },
      {
        "freq_hz": 71.14093959731544,
        "magnitude": 0.00021686146455967854,
        "prominence": 68.31241148720396
      },
      {
        "freq_hz": 68.68008948545862,
        "magnitude": 0.00021054206802374932,
        "prominence": 66.32177097673
      },
      {
        "freq_hz": 65.99552572706936,
        "magnitude": 0.00019721878441518042,
        "prominence": 62.124872122075196
      }
    ],
    "ring_score": 0.03141689271067719,
    "rms": 0.016624253421342525,
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
    "position_drift": 0.00213623046875,
    "tripped_ferr": null
  }
}
```

**[    43.3s | position | accept]** 60.0 rad/s accepted (pos_60.0rads: peak=0.04128 rms=0.01662 score=0.07452 stable dom=69.1Hz tq=45%)

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

**[    48.8s | measure | measurement]** pos_62.4rads: peak=0.03975 rms=0.01596 score=0.07166 stable dom=69.2Hz tq=44%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_234005_Z/08_pos_62.4rads.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 69.2 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0021161648736024888,
    "ms": null,
    "n_samples": 4483,
    "peak_abs": 0.0397491455078125,
    "peaks": [
      {
        "freq_hz": 69.15012268570155,
        "magnitude": 0.0002885648416766012,
        "prominence": 89.34907177831771
      },
      {
        "freq_hz": 71.15770689270578,
        "magnitude": 0.00021194691015905708,
        "prominence": 65.62566520219919
      },
      {
        "freq_hz": 66.91947356680794,
        "magnitude": 0.0001992394428504051,
        "prominence": 61.69101951880775
      },
      {
        "freq_hz": 68.03479812625474,
        "magnitude": 0.00018398599693287266,
        "prominence": 56.968055951126516
      },
      {
        "freq_hz": 70.04238233325898,
        "magnitude": 0.00017382956962883804,
        "prominence": 53.823295324963794
      }
    ],
    "ring_score": 0.03111813363328516,
    "rms": 0.015956509687622904,
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
    "position_drift": 0.0051116943359375,
    "tripped_ferr": null
  }
}
```

**[    48.8s | position | stall]** 62.4 rad/s stable but no improvement (pos_62.4rads: peak=0.03975 rms=0.01596 score=0.07166 stable dom=69.2Hz tq=44%) — reverting to 60.0 (stall 1/2)

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

**[    50.3s | position | write]** SDO write pos_gain_rad_s=62.4
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    55.0s | measure | measurement]** pos_62.4rads: peak=0.04021 rms=0.01601 score=0.07222 stable dom=69.5Hz tq=43%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_234005_Z/09_pos_62.4rads.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 69.5 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.00185284805170721,
    "ms": null,
    "n_samples": 4473,
    "peak_abs": 0.0402069091796875,
    "peaks": [
      {
        "freq_hz": 69.52828079588643,
        "magnitude": 0.000169050317959032,
        "prominence": 52.99914661153355
      },
      {
        "freq_hz": 67.51620836127879,
        "magnitude": 0.00012668570919642373,
        "prominence": 39.717372651819005
      },
      {
        "freq_hz": 64.38631790744468,
        "magnitude": 0.00012296188009942098,
        "prominence": 38.54991099512948
      },
      {
        "freq_hz": 62.374245472837025,
        "magnitude": 0.00010715693949138486,
        "prominence": 33.5948871029243
      },
      {
        "freq_hz": 75.56449809970937,
        "magnitude": 0.00010434061786125625,
        "prominence": 32.71193908612972
      }
    ],
    "ring_score": 0.0301167637042334,
    "rms": 0.016006717812069176,
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
    "position_drift": 0.0016021728515625,
    "tripped_ferr": null
  }
}
```

**[    55.0s | position | stall]** 62.4 rad/s stable but no improvement (pos_62.4rads: peak=0.04021 rms=0.01601 score=0.07222 stable dom=69.5Hz tq=43%) — reverting to 60.0 (stall 2/2)

**[    55.8s | position | write]** SDO write pos_gain_rad_s=60
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    55.8s | integral | start]** integral tighten from 3.00 ms toward 3.00 ms (lower = stronger)

**[    55.8s | integral | skip]** already at/below floor

**[    55.8s | feedforward | start]** torque FF 200% (search 50-200%)

**[    56.6s | feedforward | write]** SDO write torque_ff_pct=173.9
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "torque_ff_pct"
  ]
}
```

**[    61.3s | measure | measurement]** ff_173.9pct: peak=0.04128 rms=0.01622 score=0.07371 stable dom=74.1Hz tq=43%
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_234005_Z/10_ff_173.9pct.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 74.1 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0020580493923062068,
    "ms": null,
    "n_samples": 4482,
    "peak_abs": 0.0412750244140625,
    "peaks": [
      {
        "freq_hz": 74.07407407407406,
        "magnitude": 0.00015657506792006063,
        "prominence": 53.33056536674305
      },
      {
        "freq_hz": 76.08210620258812,
        "magnitude": 0.00015477491431044286,
        "prominence": 52.717420432347026
      },
      {
        "freq_hz": 62.918340026773755,
        "magnitude": 0.0001524490584594178,
        "prominence": 51.92521763055714
      },
      {
        "freq_hz": 61.80276662204373,
        "magnitude": 0.00015114451250550624,
        "prominence": 51.480880136770956
      },
      {
        "freq_hz": 64.92637215528781,
        "magnitude": 0.00014502084902069578,
        "prominence": 49.39511744096708
      }
    ],
    "ring_score": 0.03008647294678498,
    "rms": 0.016219631606692538,
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
    "position_drift": 0.001678466796875,
    "tripped_ferr": null
  }
}
```

**[    61.3s | feedforward | stall]** 173.9% no better — back to 200%

**[    62.0s | feedforward | write]** SDO write torque_ff_pct=200
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "torque_ff_pct"
  ]
}
```

**[    67.9s | rest | standstill]** verify: rest FERR rms 0.09 um, torque rms 12.38%
```json
{
  "ferr_peak": 0.0002288818359375,
  "ferr_rms": 8.77343238277486e-05,
  "n": 1005.0,
  "torque_peak_pct": 13.5,
  "torque_rms_pct": 12.380725671753009
}
```

**[    67.9s | measure | measurement]** verify: peak=0.04295 rms=0.01660 score=0.07615 UNSTABLE dom=61.3Hz tq=43% [standstill torque rms 12.4% > 5%]
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_234005_Z/11_verify.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 61.3 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0020972169696164725,
    "ms": null,
    "n_samples": 4487,
    "peak_abs": 0.0429534912109375,
    "peaks": [
      {
        "freq_hz": 61.288165812346776,
        "magnitude": 0.00019773540366452953,
        "prominence": 65.7022991614807
      },
      {
        "freq_hz": 76.66592377980834,
        "magnitude": 0.0001928290853274318,
        "prominence": 64.07205799479337
      },
      {
        "freq_hz": 63.29396032984176,
        "magnitude": 0.00017939093955869585,
        "prominence": 59.60691388245727
      },
      {
        "freq_hz": 78.67171829730331,
        "magnitude": 0.00017886315109438253,
        "prominence": 59.43154358996719
      },
      {
        "freq_hz": 74.66012926231335,
        "magnitude": 0.00017585461105265138,
        "prominence": 58.43188447886299
      }
    ],
    "ring_score": 0.030699100044355936,
    "rms": 0.016599923343310844,
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
    "position_drift": 0.0054168701171875,
    "tripped_ferr": null
  }
}
```

**[    67.9s | verify | warning]** final tune unstable on verify (standstill torque rms 12.4% > 5%) — backing off speed & position by 0.75x

**[    68.8s | verify | write]** SDO write speed_gain_hz=19.5, pos_gain_rad_s=45
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

**[    74.6s | rest | standstill]** verify_backoff: rest FERR rms 0.31 um, torque rms 12.58%
```json
{
  "ferr_peak": 0.0006866455078125,
  "ferr_rms": 0.0003100335947965609,
  "n": 1005.0,
  "torque_peak_pct": 15.0,
  "torque_rms_pct": 12.579712799955063
}
```

**[    74.6s | measure | measurement]** verify_backoff: peak=0.06096 rms=0.02622 score=0.11340 UNSTABLE dom=79.6Hz tq=43% [standstill torque rms 12.6% > 5%]
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_234005_Z/12_verify_backoff.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 79.6 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0009493792626198622,
    "ms": null,
    "n_samples": 4486,
    "peak_abs": 0.0609588623046875,
    "peaks": [
      {
        "freq_hz": 79.58091841283995,
        "magnitude": 0.00018624762078715433,
        "prominence": 60.68377968818555
      },
      {
        "freq_hz": 67.98930004458316,
        "magnitude": 0.00018584264994212307,
        "prominence": 60.55183082657781
      },
      {
        "freq_hz": 77.57467677218013,
        "magnitude": 0.0001750870898248473,
        "prominence": 57.04742074165277
      },
      {
        "freq_hz": 65.98305840392332,
        "magnitude": 0.0001749061603567952,
        "prominence": 56.988469739046835
      },
      {
        "freq_hz": 78.68925546143558,
        "magnitude": 0.00015235613589957553,
        "prominence": 49.641150560731205
      }
    ],
    "ring_score": 0.025500708718069517,
    "rms": 0.026220814006405028,
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
    "position_drift": 0.007476806640625,
    "tripped_ferr": null
  }
}
```

**[    74.6s | verify | keep-best]** verify unstable (standstill torque rms 12.4% > 5%); backoff failed (standstill torque rms 12.6% > 5%) — restoring best stable step (15.1% better than baseline)
```json
{
  "backoff_score": 0.11340049031749755,
  "baseline_score": 0.08774254629585454,
  "best_score": 0.07452353125674754,
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
  "verify_score": 0.07615333789755918
}
```

**[    75.5s | verify | write]** SDO write speed_gain_hz=26, pos_gain_rad_s=60
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

**[    81.4s | rest | standstill]** verify_best: rest FERR rms 0.08 um, torque rms 12.54%
```json
{
  "ferr_peak": 0.0002288818359375,
  "ferr_rms": 8.365870114040887e-05,
  "n": 1008.0,
  "torque_peak_pct": 13.700000000000001,
  "torque_rms_pct": 12.542924711464243
}
```

**[    81.4s | measure | measurement]** verify_best: peak=0.04280 rms=0.01647 score=0.07575 UNSTABLE dom=68.7Hz tq=44% [standstill torque rms 12.5% > 5%]
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_234005_Z/13_verify_best.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 68.7 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.00163226411922199,
    "ms": null,
    "n_samples": 4495,
    "peak_abs": 0.0428009033203125,
    "peaks": [
      {
        "freq_hz": 68.74304783092325,
        "magnitude": 0.0001253875701528233,
        "prominence": 41.32310025642465
      },
      {
        "freq_hz": 66.74082313681868,
        "magnitude": 9.918888611825713e-05,
        "prominence": 32.68898408663784
      },
      {
        "freq_hz": 79.42157953281423,
        "magnitude": 9.871292449866734e-05,
        "prominence": 32.532124760784825
      },
      {
        "freq_hz": 70.7452725250278,
        "magnitude": 9.331117886056766e-05,
        "prominence": 30.75190941495079
      },
      {
        "freq_hz": 81.64627363737486,
        "magnitude": 9.207989150223085e-05,
        "prominence": 30.346122693898565
      }
    ],
    "ring_score": 0.029376595109673824,
    "rms": 0.01647344788067544,
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
    "position_drift": 0.0064849853515625,
    "tripped_ferr": null
  }
}
```

**[    81.4s | verify | best-check]** verify_best: peak=0.04280 rms=0.01647 score=0.07575 UNSTABLE dom=68.7Hz tq=44% [standstill torque rms 12.5% > 5%]

**[    81.4s | verify | best-rejected]** best step failed its re-check: standstill torque rms 12.5% > 5%

**[    81.4s | verify | revert]** still unstable after backoff and no salvageable best step — restoring baseline

**[    81.4s | verify | revert]** restoring baseline values for touched keys
```json
{
  "values": {
    "pos_gain_rad_s": 50.0,
    "speed_gain_hz": 26.0,
    "torque_ff_pct": 200.0
  }
}
```

**[    82.4s | verify | write]** SDO write pos_gain_rad_s=50, speed_gain_hz=26, torque_ff_pct=200
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

**[    82.4s | verify | revert-ok]** baseline restored

**[    88.3s | rest | standstill]** verify_baseline: rest FERR rms 0.10 um, torque rms 12.46%
```json
{
  "ferr_peak": 0.00030517578125,
  "ferr_rms": 9.915597749559264e-05,
  "n": 1010.0,
  "torque_peak_pct": 13.600000000000001,
  "torque_rms_pct": 12.458466444093908
}
```

**[    88.3s | measure | measurement]** verify_baseline: peak=0.05119 rms=0.01935 score=0.08990 UNSTABLE dom=68.6Hz tq=44% [standstill torque rms 12.5% > 5%]
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20261127_234005_Z/14_verify_baseline.csv",
  "fft": {
    "fs_hz": 1000.0,
    "gate_min_hz": 60.0,
    "gate_reason": "peak at 68.6 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.0015330890656520939,
    "ms": null,
    "n_samples": 4506,
    "peak_abs": 0.0511932373046875,
    "peaks": [
      {
        "freq_hz": 68.57523302263648,
        "magnitude": 0.00020182922958605828,
        "prominence": 61.83611270791402
      },
      {
        "freq_hz": 67.46560142032845,
        "magnitude": 0.00019721667933144952,
        "prominence": 60.42292702613799
      },
      {
        "freq_hz": 65.46826453617399,
        "magnitude": 0.00018063959676835271,
        "prominence": 55.34406729981192
      },
      {
        "freq_hz": 66.35596981802041,
        "magnitude": 0.0001752946584081851,
        "prominence": 53.70649373559608
      },
      {
        "freq_hz": 70.57256990679095,
        "magnitude": 0.0001276646109374728,
        "prominence": 39.113676878875985
      }
    ],
    "ring_score": 0.027734897474902476,
    "rms": 0.01935134179024069,
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
    "position_drift": 0.006561279296875,
    "tripped_ferr": null
  }
}
```

**[    88.3s | verify | baseline-check]** verify_baseline: peak=0.05119 rms=0.01935 score=0.08990 UNSTABLE dom=68.6Hz tq=44% [standstill torque rms 12.5% > 5%]

**[    88.4s | finalize | result]** campaign status: reverted
```json
{
  "baseline_score": 0.08774254629585454,
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
  "final_score": 0.08989592088516887,
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
  "measurements": 14,
  "notch_applied": false,
  "preset": null,
  "reason": "verify stayed unstable after backoff \u2014 baseline restored"
}
```


---

**FINAL STATUS: REVERTED** — 2026-11-27T23:41:34
**[    88.8s | finalize | ferr-window]** 6065 restored to 0.5 production window

