# One-click tune — axis X

- started: 2026-07-12T18:11:36
- engine: a6_auto_tune v1.0
- profile: conservative
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
  "position": 127.88990783691406
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
    "pos_gain_rad_s": 130.0,
    "speed_fb_filter": 0.0,
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

**[     1.7s | baseline | backup]** baseline preset saved: pre_one_click_20260712_181138
```json
{
  "path": "/home/jon/linuxcnc/configs/ethercat_mill/config/tuning/presets/X/pre_one_click_20260712_181138.json"
}
```

**[     8.9s | measure | measurement]** baseline: peak=0.01053 rms=0.00155 score=0.01362 stable dom=32.2Hz
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_181136_X/01_baseline.csv",
  "fft": {
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 32.2 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.3087717924686356,
    "n_samples": 1737,
    "peak_abs": 0.010528564453125,
    "peaks": [
      {
        "freq_hz": 32.23949337938975,
        "magnitude": 0.00027939594296274363,
        "prominence": 6.956448887789331
      },
      {
        "freq_hz": 33.966609096142776,
        "magnitude": 0.00027549133599899685,
        "prominence": 6.859231303016338
      },
      {
        "freq_hz": 42.602187679907885,
        "magnitude": 0.0002304155545657136,
        "prominence": 5.736926639989748
      },
      {
        "freq_hz": 30.512377662636727,
        "magnitude": 0.00022189008714100254,
        "prominence": 5.524658066024006
      },
      {
        "freq_hz": 36.26943005181347,
        "magnitude": 0.000210911693830473,
        "prominence": 5.251316115797725
      }
    ],
    "ring_score": 0.5306468621724418,
    "rms": 0.0015471810207702795
  },
  "gains": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 130.0,
    "speed_gain_hz": 80.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": -0.000152587890625,
    "tripped_ferr": null
  }
}
```

**[     9.0s | speed | start]** speed ladder from 80.0 Hz, cap 120.0 Hz

**[     9.5s | speed | write]** SDO write speed_gain_hz=92
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    16.7s | measure | measurement]** speed_92.0hz: peak=0.00999 rms=0.00141 score=0.01281 stable dom=27.3Hz
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_181136_X/02_speed_92.0hz.csv",
  "fft": {
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 27.3 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.25500042177995896,
    "n_samples": 1829,
    "peak_abs": 0.0099945068359375,
    "peaks": [
      {
        "freq_hz": 27.33734281027884,
        "magnitude": 0.00028046122340136655,
        "prominence": 8.298315040611426
      },
      {
        "freq_hz": 31.711317659923456,
        "magnitude": 0.00026190816342093335,
        "prominence": 7.7493652256679715
      },
      {
        "freq_hz": 36.08529250956807,
        "magnitude": 0.00025682738194132053,
        "prominence": 7.599034549437578
      },
      {
        "freq_hz": 40.45926735921269,
        "magnitude": 0.0001967387858223566,
        "prominence": 5.821127090802445
      },
      {
        "freq_hz": 44.28649535265173,
        "magnitude": 0.00017305219154790992,
        "prominence": 5.1202857440213005
      }
    ],
    "ring_score": 0.5117045818136475,
    "rms": 0.0014092274159722181
  },
  "gains": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 130.0,
    "speed_gain_hz": 92.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": 0.0,
    "tripped_ferr": null
  }
}
```

**[    16.7s | speed | accept]** 92.0 Hz accepted (speed_92.0hz: peak=0.00999 rms=0.00141 score=0.01281 stable dom=27.3Hz)

**[    17.2s | speed | write]** SDO write speed_gain_hz=105.8
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    24.4s | measure | measurement]** speed_105.8hz: peak=0.00931 rms=0.00133 score=0.01197 stable dom=28.3Hz
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_181136_X/03_speed_105.8hz.csv",
  "fft": {
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 28.3 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.31459747371839225,
    "n_samples": 1801,
    "peak_abs": 0.009307861328125,
    "peaks": [
      {
        "freq_hz": 28.317601332593007,
        "magnitude": 0.0003452092077528516,
        "prominence": 9.841120036684362
      },
      {
        "freq_hz": 32.75957801221544,
        "magnitude": 0.00031181835288869277,
        "prominence": 8.889223611369564
      },
      {
        "freq_hz": 37.20155469183787,
        "magnitude": 0.00027812913235769545,
        "prominence": 7.928821467562213
      },
      {
        "freq_hz": 41.643531371460305,
        "magnitude": 0.0002430341442815181,
        "prominence": 6.92834412632358
      },
      {
        "freq_hz": 46.08550805108273,
        "magnitude": 0.0001928452153530101,
        "prominence": 5.497573269099864
      }
    ],
    "ring_score": 0.6102795407028149,
    "rms": 0.0013289250404266864
  },
  "gains": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 130.0,
    "speed_gain_hz": 105.8
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": -0.000152587890625,
    "tripped_ferr": null
  }
}
```

**[    24.4s | speed | accept]** 105.8 Hz accepted (speed_105.8hz: peak=0.00931 rms=0.00133 score=0.01197 stable dom=28.3Hz)

**[    24.9s | speed | write]** SDO write speed_gain_hz=120
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    32.2s | measure | measurement]** speed_120.0hz: peak=0.00893 rms=0.00125 score=0.01144 stable dom=28.3Hz
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_181136_X/04_speed_120.0hz.csv",
  "fft": {
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 28.3 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.3400934275968596,
    "n_samples": 1804,
    "peak_abs": 0.0089263916015625,
    "peaks": [
      {
        "freq_hz": 28.27050997782705,
        "magnitude": 0.0003217078978309465,
        "prominence": 9.599907650653833
      },
      {
        "freq_hz": 32.70509977827051,
        "magnitude": 0.00026949932386162255,
        "prominence": 8.041980437622799
      },
      {
        "freq_hz": 36.58536585365854,
        "magnitude": 0.00025529391914182225,
        "prominence": 7.618084803198847
      },
      {
        "freq_hz": 41.019955654102,
        "magnitude": 0.00022623957540525267,
        "prominence": 6.751090182917597
      },
      {
        "freq_hz": 45.45454545454545,
        "magnitude": 0.00017698220240220863,
        "prominence": 5.281228127521253
      }
    ],
    "ring_score": 0.613715695810573,
    "rms": 0.0012549750981416918
  },
  "gains": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 130.0,
    "speed_gain_hz": 120.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": -0.0002288818359375,
    "tripped_ferr": null
  }
}
```

**[    32.2s | speed | accept]** 120.0 Hz accepted (speed_120.0hz: peak=0.00893 rms=0.00125 score=0.01144 stable dom=28.3Hz)

**[    32.2s | speed | done]** reached cap

**[    32.2s | position | start]** position ladder from 130.0 rad/s toward ~240.0 (cap 250.0)

**[    32.8s | position | write]** SDO write pos_gain_rad_s=156
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    40.0s | measure | measurement]** pos_156.0rads: peak=0.00778 rms=0.00115 score=0.01008 stable dom=33.1Hz
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_181136_X/05_pos_156.0rads.csv",
  "fft": {
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 33.1 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.3242126569849135,
    "n_samples": 1482,
    "peak_abs": 0.007781982421875,
    "peaks": [
      {
        "freq_hz": 33.063427800269906,
        "magnitude": 0.00028265749183230135,
        "prominence": 7.472043690087093
      },
      {
        "freq_hz": 28.34008097165992,
        "magnitude": 0.000282353438261151,
        "prominence": 7.464006041578167
      },
      {
        "freq_hz": 37.7867746288799,
        "magnitude": 0.0002467167877723909,
        "prominence": 6.521952081875022
      },
      {
        "freq_hz": 42.51012145748988,
        "magnitude": 0.0001827107257525879,
        "prominence": 4.829953441604988
      }
    ],
    "ring_score": 0.5769709729473055,
    "rms": 0.0011481268896079762
  },
  "gains": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 156.0,
    "speed_gain_hz": 120.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": -0.0003814697265625,
    "tripped_ferr": null
  }
}
```

**[    40.0s | position | accept]** 156.0 rad/s accepted (pos_156.0rads: peak=0.00778 rms=0.00115 score=0.01008 stable dom=33.1Hz)

**[    40.5s | position | write]** SDO write pos_gain_rad_s=187.2
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    47.7s | measure | measurement]** pos_187.2rads: peak=0.01289 rms=0.00103 score=0.01496 stable dom=29.1Hz
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_181136_X/06_pos_187.2rads.csv",
  "fft": {
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 29.1 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.29575785963313145,
    "n_samples": 1755,
    "peak_abs": 0.0128936767578125,
    "peaks": [
      {
        "freq_hz": 29.05982905982906,
        "magnitude": 0.00024159749775806908,
        "prominence": 9.045798571933755
      },
      {
        "freq_hz": 33.61823361823362,
        "magnitude": 0.00018583213252153563,
        "prominence": 6.957853680529553
      },
      {
        "freq_hz": 37.60683760683761,
        "magnitude": 0.0001580822989175043,
        "prominence": 5.918855315413571
      },
      {
        "freq_hz": 87.17948717948718,
        "magnitude": 0.00011321243674493831,
        "prominence": 4.2388555681897575
      },
      {
        "freq_hz": 78.06267806267806,
        "magnitude": 0.00011171776887444767,
        "prominence": 4.182892801133542
      }
    ],
    "ring_score": 0.6802030071297527,
    "rms": 0.0010331838176181201
  },
  "gains": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 187.2,
    "speed_gain_hz": 120.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": -0.00030517578125,
    "tripped_ferr": null
  }
}
```

**[    47.7s | position | stall]** 187.2 rad/s stable but no improvement (pos_187.2rads: peak=0.01289 rms=0.00103 score=0.01496 stable dom=29.1Hz) — reverting to 156.0 (stall 1/2)

**[    48.2s | position | write]** SDO write pos_gain_rad_s=156
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    48.7s | position | write]** SDO write pos_gain_rad_s=187.2
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    55.9s | measure | measurement]** pos_187.2rads: peak=0.00694 rms=0.00089 score=0.00873 stable dom=25.8Hz
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_181136_X/07_pos_187.2rads.csv",
  "fft": {
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 25.8 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.3131041793420967,
    "n_samples": 1706,
    "peak_abs": 0.0069427490234375,
    "peaks": [
      {
        "freq_hz": 25.79132473622509,
        "magnitude": 0.00018772081842267422,
        "prominence": 7.319891530436663
      },
      {
        "freq_hz": 29.308323563892145,
        "magnitude": 0.000182087985984063,
        "prominence": 7.100247684824817
      },
      {
        "freq_hz": 33.99765533411489,
        "magnitude": 0.00017221672694135948,
        "prominence": 6.715332756003559
      },
      {
        "freq_hz": 38.10082063305979,
        "magnitude": 0.0001646111319476732,
        "prominence": 6.418763995830867
      },
      {
        "freq_hz": 42.790152403282534,
        "magnitude": 0.00011742537157102836,
        "prominence": 4.578826099542123
      }
    ],
    "ring_score": 0.6072371267092251,
    "rms": 0.0008941146113321513
  },
  "gains": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 187.2,
    "speed_gain_hz": 120.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": -7.62939453125e-05,
    "tripped_ferr": null
  }
}
```

**[    55.9s | position | accept]** 187.2 rad/s accepted (pos_187.2rads: peak=0.00694 rms=0.00089 score=0.00873 stable dom=25.8Hz)

**[    56.4s | position | write]** SDO write pos_gain_rad_s=224.64
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    63.6s | measure | measurement]** pos_224.6rads: peak=0.00587 rms=0.00074 score=0.00736 UNSTABLE dom=35.0Hz [HF energy 41%]
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_181136_X/08_pos_224.6rads.csv",
  "fft": {
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 35.0 Hz; HF energy 41%",
    "gate_stable": false,
    "hf_energy_ratio": 0.4067140486207045,
    "n_samples": 1771,
    "peak_abs": 0.0058746337890625,
    "peaks": [
      {
        "freq_hz": 35.00846979107848,
        "magnitude": 0.0001590557686764604,
        "prominence": 6.924464945029072
      },
      {
        "freq_hz": 39.52569169960474,
        "magnitude": 0.00014779004576336463,
        "prominence": 6.434013677267619
      },
      {
        "freq_hz": 30.49124788255223,
        "magnitude": 0.0001423404074885923,
        "prominence": 6.196764632415249
      },
      {
        "freq_hz": 44.042913608130995,
        "magnitude": 0.00012599636615137917,
        "prominence": 5.48522966426299
      },
      {
        "freq_hz": 25.974025974025974,
        "magnitude": 0.0001247361633585033,
        "prominence": 5.430366957078525
      }
    ],
    "ring_score": 0.6928598947991088,
    "rms": 0.0007409625079243825
  },
  "gains": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 224.64,
    "speed_gain_hz": 120.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": -0.000152587890625,
    "tripped_ferr": null
  }
}
```

**[    63.6s | position | backoff]** unstable at 224.6 rad/s (HF energy 41%) — returning to 187.2

**[    64.1s | position | write]** SDO write pos_gain_rad_s=187.2
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    64.1s | integral | skip]** best already 35.9% better than baseline (≥30%) — skipping integral tighten

**[    71.3s | measure | measurement]** verify: peak=0.00671 rms=0.00087 score=0.00845 stable dom=28.4Hz
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_181136_X/09_verify.csv",
  "fft": {
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 28.4 Hz; HF energy 38%",
    "gate_stable": false,
    "hf_energy_ratio": 0.37586737636781237,
    "n_samples": 1793,
    "peak_abs": 0.0067138671875,
    "peaks": [
      {
        "freq_hz": 28.44394868934746,
        "magnitude": 0.0002097212680085722,
        "prominence": 7.729778219599799
      },
      {
        "freq_hz": 32.90574456218628,
        "magnitude": 0.00018041149236686682,
        "prominence": 6.6494964364124565
      },
      {
        "freq_hz": 37.3675404350251,
        "magnitude": 0.00016529562457480657,
        "prominence": 6.092365026999837
      },
      {
        "freq_hz": 41.271611823759066,
        "magnitude": 0.00013761548880048167,
        "prominence": 5.0721475132701555
      },
      {
        "freq_hz": 45.73340769659788,
        "magnitude": 0.00011737264311998789,
        "prominence": 4.326049088777485
      }
    ],
    "ring_score": 0.6151375330266724,
    "rms": 0.0008696888648129918
  },
  "gains": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 187.2,
    "speed_gain_hz": 120.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": -0.00030517578125,
    "tripped_ferr": null
  }
}
```

**[    71.3s | verify | ok]** verify: peak=0.00671 rms=0.00087 score=0.00845 stable dom=28.4Hz

**[    71.3s | finalize | preset]** final tune saved as preset one_click_20260712_181247
```json
{
  "path": "/home/jon/linuxcnc/configs/ethercat_mill/config/tuning/presets/X/one_click_20260712_181247.json"
}
```

**[    71.4s | finalize | result]** campaign status: improved
```json
{
  "baseline_score": 0.013622926494665559,
  "baseline_values": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 130.0,
    "speed_gain_hz": 80.0
  },
  "final_score": 0.008453244917125983,
  "final_values": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 187.2,
    "speed_gain_hz": 120.0
  },
  "improvement_pct": 37.948392216341404,
  "measurements": 9,
  "notch_applied": false,
  "preset": "one_click_20260712_181247",
  "reason": "score improved 37.9%"
}
```


---

**FINAL STATUS: IMPROVED** — 2026-07-12T18:12:47
