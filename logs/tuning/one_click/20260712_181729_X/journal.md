# One-click tune — axis X

- started: 2026-07-12T18:17:29
- engine: a6_auto_tune v1.0
- profile: aggressive
- stimulus: 3x 0<->40 mm @ F3000 (~6.8s per measurement)
- dry run: False

**[     0.0s | setup | config]** campaign configuration
```json
{
  "config": {
    "allow_notch": true,
    "axis": "X",
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
      "axis": "X",
      "cycles": 3,
      "dwell_s": 0.25,
      "feed": 3000.0,
      "settle_s": 0.5,
      "stroke": 40.0
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
  "max_limit": 370.0,
  "min_limit": -254.0,
  "position": 127.88998413085938
}
```

**[     0.0s | preflight | stimulus]** stimulus direction +40 mm
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
    "pos_gain_rad_s": 187.20000000000002,
    "speed_fb_filter": 0.0,
    "speed_fb_lpf_hz": 8000.0,
    "speed_ff_filter_hz": 318.0,
    "speed_ff_pct": 100.0,
    "speed_ff_source": 1.0,
    "speed_gain_2_hz": 115.0,
    "speed_gain_hz": 120.0,
    "stiffness_level": 18.0,
    "torque_ff_filter_hz": 1000.0,
    "torque_ff_pct": 120.0,
    "torque_ff_source": 1.0,
    "torque_filter_2_hz": 920.0,
    "torque_filter_hz": 600.0
  }
}
```

**[     1.8s | baseline | backup]** baseline preset saved: pre_one_click_20260712_181731
```json
{
  "path": "/home/jon/linuxcnc/configs/ethercat_mill/config/tuning/presets/X/pre_one_click_20260712_181731.json"
}
```

**[     9.0s | measure | measurement]** baseline: peak=0.00679 rms=0.00090 score=0.00859 UNSTABLE dom=26.2Hz [HF energy 37%]
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_181729_X/01_baseline.csv",
  "fft": {
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 26.2 Hz; HF energy 37%",
    "gate_stable": false,
    "hf_energy_ratio": 0.373921353728278,
    "n_samples": 1944,
    "peak_abs": 0.0067901611328125,
    "peaks": [
      {
        "freq_hz": 26.234567901234566,
        "magnitude": 0.00023287356711465776,
        "prominence": 9.332741309626403
      },
      {
        "freq_hz": 30.349794238683128,
        "magnitude": 0.00021686310737620875,
        "prominence": 8.69109923389196
      },
      {
        "freq_hz": 34.465020576131685,
        "magnitude": 0.00021452743270879626,
        "prominence": 8.597493730594644
      },
      {
        "freq_hz": 38.58024691358025,
        "magnitude": 0.00016035837200774176,
        "prominence": 6.426591138376093
      },
      {
        "freq_hz": 42.181069958847736,
        "magnitude": 0.00013408044942026618,
        "prominence": 5.373465802160716
      }
    ],
    "ring_score": 0.6627665539225435,
    "rms": 0.0008974394721255681
  },
  "gains": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 187.20000000000002,
    "speed_gain_hz": 120.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": 0.0,
    "tripped_ferr": null
  }
}
```

**[     9.0s | rescue | start]** baseline unstable (HF energy 37%) — rescue before ladder

**[     9.0s | rescue | backoff]** speed gain 120.0 -> 90.0 Hz (attempt 1)

**[     9.5s | rescue | write]** SDO write speed_gain_hz=90
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    16.6s | measure | measurement]** rescue_soften_1: peak=0.00793 rms=0.00104 score=0.01002 stable dom=27.3Hz
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_181729_X/02_rescue_soften_1.csv",
  "fft": {
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 27.3 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.3329663070790998,
    "n_samples": 1870,
    "peak_abs": 0.0079345703125,
    "peaks": [
      {
        "freq_hz": 27.27272727272727,
        "magnitude": 0.0002514709107550175,
        "prominence": 8.026882983106459
      },
      {
        "freq_hz": 31.01604278074866,
        "magnitude": 0.00021108846469364954,
        "prominence": 6.7378863030014156
      },
      {
        "freq_hz": 35.29411764705882,
        "magnitude": 0.00021077275479603022,
        "prominence": 6.727808929053112
      },
      {
        "freq_hz": 39.572192513368975,
        "magnitude": 0.0001553231884137847,
        "prominence": 4.95787387184134
      },
      {
        "freq_hz": 89.83957219251336,
        "magnitude": 0.00013227790582135668,
        "prominence": 4.2222747278821045
      }
    ],
    "ring_score": 0.5942704595964304,
    "rms": 0.0010446531773049472
  },
  "gains": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 187.20000000000002,
    "speed_gain_hz": 90.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": -0.000457763671875,
    "tripped_ferr": null
  }
}
```

**[    16.7s | rescue | ok]** baseline stabilized

**[    16.7s | speed | cap]** speed gain capped at 150.0 Hz (0.25 x C01.03 torque filter 600 Hz)

**[    16.7s | speed | start]** speed ladder from 90.0 Hz, cap 150.0 Hz

**[    17.2s | speed | write]** SDO write speed_gain_hz=126
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    24.4s | measure | measurement]** speed_126.0hz: peak=0.00648 rms=0.00084 score=0.00816 stable dom=27.3Hz
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_181729_X/03_speed_126.0hz.csv",
  "fft": {
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 27.3 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.29461327556058825,
    "n_samples": 1866,
    "peak_abs": 0.0064849853515625,
    "peaks": [
      {
        "freq_hz": 27.331189710610932,
        "magnitude": 0.00022962511735479316,
        "prominence": 10.414689434041861
      },
      {
        "freq_hz": 31.618435155412648,
        "magnitude": 0.0001987826487323245,
        "prominence": 9.015823596617448
      },
      {
        "freq_hz": 35.90568060021436,
        "magnitude": 0.0001795212925160664,
        "prominence": 8.142221242564727
      },
      {
        "freq_hz": 39.657020364415864,
        "magnitude": 0.00014279100313210094,
        "prominence": 6.4763122115181275
      },
      {
        "freq_hz": 43.944265809217576,
        "magnitude": 0.00011599458473906317,
        "prominence": 5.2609557264654265
      }
    ],
    "ring_score": 0.5958244782859807,
    "rms": 0.0008364074818909803
  },
  "gains": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 187.20000000000002,
    "speed_gain_hz": 125.99999999999999
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": -0.00030517578125,
    "tripped_ferr": null
  }
}
```

**[    24.4s | speed | accept]** 126.0 Hz accepted (speed_126.0hz: peak=0.00648 rms=0.00084 score=0.00816 stable dom=27.3Hz)

**[    24.9s | speed | write]** SDO write speed_gain_hz=150
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    32.1s | measure | measurement]** speed_150.0hz: peak=0.00610 rms=0.00085 score=0.00781 stable dom=27.0Hz
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_181729_X/04_speed_150.0hz.csv",
  "fft": {
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 27.0 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.3028905864802387,
    "n_samples": 1743,
    "peak_abs": 0.006103515625,
    "peaks": [
      {
        "freq_hz": 26.965002868617322,
        "magnitude": 0.00022160476098779508,
        "prominence": 10.635578720900492
      },
      {
        "freq_hz": 31.554790590935166,
        "magnitude": 0.00021755958755629855,
        "prominence": 10.441436860957573
      },
      {
        "freq_hz": 35.570854847963275,
        "magnitude": 0.00021225267015303787,
        "prominence": 10.18673954508716
      },
      {
        "freq_hz": 39.58691910499139,
        "magnitude": 0.00015630079833522007,
        "prominence": 7.501415752188555
      },
      {
        "freq_hz": 44.17670682730923,
        "magnitude": 0.00013266173125197513,
        "prominence": 6.366895186241211
      }
    ],
    "ring_score": 0.6061412740654379,
    "rms": 0.0008517816293987182
  },
  "gains": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 187.20000000000002,
    "speed_gain_hz": 150.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": -0.0003814697265625,
    "tripped_ferr": null
  }
}
```

**[    32.1s | speed | accept]** 150.0 Hz accepted (speed_150.0hz: peak=0.00610 rms=0.00085 score=0.00781 stable dom=27.0Hz)

**[    32.1s | speed | done]** reached cap

**[    32.1s | position | start]** position ladder from 187.2 rad/s toward ~300.0 (cap 360.0)

**[    32.6s | position | write]** SDO write pos_gain_rad_s=224.64
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    39.8s | measure | measurement]** pos_224.6rads: peak=0.00526 rms=0.00069 score=0.00665 UNSTABLE dom=28.7Hz [HF energy 51%]
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_181729_X/05_pos_224.6rads.csv",
  "fft": {
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 28.7 Hz; HF energy 51%",
    "gate_stable": false,
    "hf_energy_ratio": 0.5128340591419233,
    "n_samples": 1815,
    "peak_abs": 0.0052642822265625,
    "peaks": [
      {
        "freq_hz": 28.650137741046834,
        "magnitude": 0.0001536698423480056,
        "prominence": 6.554010958858946
      },
      {
        "freq_hz": 33.057851239669425,
        "magnitude": 0.00013147594022298024,
        "prominence": 5.6074421622446575
      },
      {
        "freq_hz": 37.46556473829201,
        "magnitude": 0.00012639305303543982,
        "prominence": 5.390657282265791
      },
      {
        "freq_hz": 30.853994490358126,
        "magnitude": 0.00010805029583446246,
        "prominence": 4.608339620751937
      },
      {
        "freq_hz": 26.446280991735538,
        "magnitude": 0.00010797655571324178,
        "prominence": 4.605194608333083
      }
    ],
    "ring_score": 0.7438987079277982,
    "rms": 0.0006943623162646589
  },
  "gains": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 224.64000000000001,
    "speed_gain_hz": 150.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": -0.000457763671875,
    "tripped_ferr": null
  }
}
```

**[    39.8s | position | backoff]** unstable at 224.6 rad/s (HF energy 51%) — returning to 187.2

**[    40.3s | position | write]** SDO write pos_gain_rad_s=187.2
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    40.3s | integral | start]** integral tighten from 5.00 ms toward 1.00 ms (lower = stronger)

**[    40.8s | integral | write]** SDO write integral_ms=3.5
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "integral_ms"
  ]
}
```

**[    48.0s | measure | measurement]** integral_3.50ms: peak=0.00534 rms=0.00077 score=0.00688 UNSTABLE dom=28.1Hz [HF energy 40%]
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_181729_X/06_integral_3.50ms.csv",
  "fft": {
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 28.1 Hz; HF energy 40%",
    "gate_stable": false,
    "hf_energy_ratio": 0.39951399024195355,
    "n_samples": 1818,
    "peak_abs": 0.005340576171875,
    "peaks": [
      {
        "freq_hz": 28.052805280528055,
        "magnitude": 0.00019042801090177837,
        "prominence": 8.119809834752099
      },
      {
        "freq_hz": 31.353135313531354,
        "magnitude": 0.00016366027230603947,
        "prominence": 6.978439161002524
      },
      {
        "freq_hz": 35.75357535753576,
        "magnitude": 0.00015998935106341822,
        "prominence": 6.8219118609100455
      },
      {
        "freq_hz": 40.15401540154016,
        "magnitude": 0.00014533380661976795,
        "prominence": 6.197002566612069
      },
      {
        "freq_hz": 44.00440044004401,
        "magnitude": 0.0001384135269890973,
        "prominence": 5.9019233167776655
      }
    ],
    "ring_score": 0.6951611201558191,
    "rms": 0.0007700385240857022
  },
  "gains": {
    "integral_ms": 3.5,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 187.20000000000002,
    "speed_gain_hz": 150.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": -0.0002288818359375,
    "tripped_ferr": null
  }
}
```

**[    48.0s | integral | backoff]** unstable at 3.50 ms (HF energy 40%) — returning to 5.00 ms

**[    48.5s | integral | write]** SDO write integral_ms=5
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "integral_ms"
  ]
}
```

**[    55.7s | measure | measurement]** verify: peak=0.00595 rms=0.00081 score=0.00758 stable dom=28.9Hz
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_181729_X/07_verify.csv",
  "fft": {
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 28.9 Hz; HF energy 39%",
    "gate_stable": false,
    "hf_energy_ratio": 0.3925188336047741,
    "n_samples": 1766,
    "peak_abs": 0.005950927734375,
    "peaks": [
      {
        "freq_hz": 28.878822197055495,
        "magnitude": 0.00023746280899738975,
        "prominence": 9.040765795548324
      },
      {
        "freq_hz": 33.4088335220838,
        "magnitude": 0.00019769820471436276,
        "prominence": 7.5268340948605905
      },
      {
        "freq_hz": 37.37259343148358,
        "magnitude": 0.00019636495510803954,
        "prominence": 7.476074156962661
      },
      {
        "freq_hz": 41.90260475651189,
        "magnitude": 0.00016257157865733426,
        "prominence": 6.189481097520739
      },
      {
        "freq_hz": 46.4326160815402,
        "magnitude": 0.00013024876892639767,
        "prominence": 4.958875960382485
      }
    ],
    "ring_score": 0.6618744665116642,
    "rms": 0.0008141451483696084
  },
  "gains": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 187.20000000000002,
    "speed_gain_hz": 150.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": -0.000152587890625,
    "tripped_ferr": null
  }
}
```

**[    55.7s | verify | ok]** verify: peak=0.00595 rms=0.00081 score=0.00758 stable dom=28.9Hz

**[    55.7s | finalize | preset]** final tune saved as preset one_click_20260712_181824
```json
{
  "path": "/home/jon/linuxcnc/configs/ethercat_mill/config/tuning/presets/X/one_click_20260712_181824.json"
}
```

**[    55.8s | finalize | result]** campaign status: improved
```json
{
  "baseline_score": 0.008585040077063635,
  "baseline_values": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 187.20000000000002,
    "speed_gain_hz": 120.0
  },
  "final_score": 0.007579218031114217,
  "final_values": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 187.20000000000002,
    "speed_gain_hz": 150.0
  },
  "improvement_pct": 11.715985445852954,
  "measurements": 7,
  "notch_applied": false,
  "preset": "one_click_20260712_181824",
  "reason": "baseline was unstable; final tune is stable"
}
```


---

**FINAL STATUS: IMPROVED** — 2026-07-12T18:18:25
