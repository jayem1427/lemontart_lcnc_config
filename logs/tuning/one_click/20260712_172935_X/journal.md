# One-click tune — axis X

- started: 2026-07-12T17:29:35
- engine: a6_auto_tune v1.0
- profile: balanced
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
    "improvement_min_pct": 3.0,
    "integral_improve_min_pct": 0.5,
    "integral_min_ms": 2.0,
    "integral_peak_guard_pct": 10.0,
    "integral_step_ratio": 0.7,
    "max_stall_steps": 2,
    "max_steps_per_phase": 8,
    "min_meaningful_rms": 0.0005,
    "min_prominence_ratio": 4.0,
    "min_resonance_amplitude": 0.001,
    "notch_depth_pct": 10.0,
    "notch_width_pct": 5.0,
    "pos_gain_max_rad_s": 400.0,
    "pos_step_ratio": 1.2,
    "pos_to_speed_ratio": 2.0,
    "profile": "balanced",
    "rescue_max_steps": 3,
    "resonance_vs_rms": 0.1,
    "ring_fail": 0.85,
    "sample_hz": 1000.0,
    "save_presets": true,
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
    }
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
  "position": 126.60000610351562
}
```

**[     0.0s | preflight | stimulus]** stimulus direction +40 mm
```json
{
  "direction": 1.0,
  "spec": "3x 0<->40 mm @ F3000 (~6.8s per measurement)"
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

**[     1.8s | baseline | backup]** baseline preset saved: pre_one_click_20260712_172937
```json
{
  "path": "/home/jon/linuxcnc/configs/ethercat_mill/config/tuning/presets/X/pre_one_click_20260712_172937.json"
}
```

**[     9.0s | measure | measurement]** baseline: peak=0.00977 rms=0.00161 score=0.01298 stable dom=28.6Hz
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_172935_X/01_baseline.csv",
  "fft": {
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 28.6 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.14576232568746236,
    "n_samples": 2062,
    "peak_abs": 0.009765625,
    "peaks": [
      {
        "freq_hz": 28.612997090203688,
        "magnitude": 0.00028120061766360793,
        "prominence": 10.115825625329066
      },
      {
        "freq_hz": 32.49272550921436,
        "magnitude": 0.00026196076807637853,
        "prominence": 9.423697119001252
      },
      {
        "freq_hz": 36.37245392822503,
        "magnitude": 0.0002107225446427188,
        "prominence": 7.5804688291309965
      },
      {
        "freq_hz": 40.252182347235696,
        "magnitude": 0.0001536960121693165,
        "prominence": 5.529013667648399
      },
      {
        "freq_hz": 27.643064985451023,
        "magnitude": 0.00012428875459393742,
        "prominence": 4.471125913975193
      }
    ],
    "ring_score": 0.45077660318026685,
    "rms": 0.001605218050659078
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
    "position_drift": 0.0,
    "tripped_ferr": null
  }
}
```

**[     9.0s | speed | cap]** speed gain capped at 150.0 Hz (0.25 x C01.03 torque filter 600 Hz)

**[     9.0s | speed | start]** speed ladder from 80.0 Hz, cap 150.0 Hz

**[     9.5s | speed | write]** SDO write speed_gain_hz=100
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    16.7s | measure | measurement]** speed_100.0hz: peak=0.00893 rms=0.00136 score=0.01165 stable dom=33.1Hz
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_172935_X/02_speed_100.0hz.csv",
  "fft": {
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 33.1 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.2560972673936682,
    "n_samples": 2023,
    "peak_abs": 0.0089263916015625,
    "peaks": [
      {
        "freq_hz": 33.11913000494315,
        "magnitude": 0.00033997682307834325,
        "prominence": 11.420438355288505
      },
      {
        "freq_hz": 29.1646070192783,
        "magnitude": 0.00032900561392175577,
        "prominence": 11.051895533100561
      },
      {
        "freq_hz": 37.073652990608004,
        "magnitude": 0.0002969658637244546,
        "prominence": 9.975622189717967
      },
      {
        "freq_hz": 41.02817597627286,
        "magnitude": 0.00025431359385242854,
        "prominence": 8.542855054664308
      },
      {
        "freq_hz": 44.982698961937714,
        "magnitude": 0.00021788454213535143,
        "prominence": 7.319137109101219
      }
    ],
    "ring_score": 0.5107704137724706,
    "rms": 0.0013605973573025927
  },
  "gains": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 130.0,
    "speed_gain_hz": 100.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": -0.000152587890625,
    "tripped_ferr": null
  }
}
```

**[    16.7s | speed | accept]** 100.0 Hz accepted (speed_100.0hz: peak=0.00893 rms=0.00136 score=0.01165 stable dom=33.1Hz)

**[    17.2s | speed | write]** SDO write speed_gain_hz=125
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "speed_gain_hz"
  ]
}
```

**[    24.4s | measure | measurement]** speed_125.0hz: peak=0.00793 rms=0.00122 score=0.01037 stable dom=29.4Hz
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_172935_X/03_speed_125.0hz.csv",
  "fft": {
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 29.4 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.24861363268338832,
    "n_samples": 2007,
    "peak_abs": 0.0079345703125,
    "peaks": [
      {
        "freq_hz": 29.397110114598902,
        "magnitude": 0.0002802249433916843,
        "prominence": 10.561846238382794
      },
      {
        "freq_hz": 33.383158943697055,
        "magnitude": 0.00026446519869669736,
        "prominence": 9.967852005713924
      },
      {
        "freq_hz": 37.369207772795214,
        "magnitude": 0.00021349137425082625,
        "prominence": 8.046617980421994
      },
      {
        "freq_hz": 41.35525660189337,
        "magnitude": 0.0001763222159778106,
        "prominence": 6.645690105343496
      },
      {
        "freq_hz": 45.341305430991525,
        "magnitude": 0.00012323048593422366,
        "prominence": 4.644630947428669
      }
    ],
    "ring_score": 0.49076266261921425,
    "rms": 0.0012175105322221134
  },
  "gains": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 130.0,
    "speed_gain_hz": 125.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": -0.000152587890625,
    "tripped_ferr": null
  }
}
```

**[    24.4s | speed | accept]** 125.0 Hz accepted (speed_125.0hz: peak=0.00793 rms=0.00122 score=0.01037 stable dom=29.4Hz)

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

**[    32.1s | measure | measurement]** speed_150.0hz: peak=0.00755 rms=0.00111 score=0.00977 stable dom=26.7Hz
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_172935_X/04_speed_150.0hz.csv",
  "fft": {
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 26.7 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.2434307685696043,
    "n_samples": 1908,
    "peak_abs": 0.0075531005859375,
    "peaks": [
      {
        "freq_hz": 26.72955974842767,
        "magnitude": 0.0002698322733263926,
        "prominence": 11.285658048873302
      },
      {
        "freq_hz": 34.59119496855345,
        "magnitude": 0.0002635821708209013,
        "prominence": 11.024249290099442
      },
      {
        "freq_hz": 30.398322851153036,
        "magnitude": 0.00024425316173372916,
        "prominence": 10.215818985257723
      },
      {
        "freq_hz": 38.78406708595387,
        "magnitude": 0.0002360309107376827,
        "prominence": 9.871925677057543
      },
      {
        "freq_hz": 42.97693920335429,
        "magnitude": 0.00020968186667272987,
        "prominence": 8.76988440687911
      }
    ],
    "ring_score": 0.5217249856485232,
    "rms": 0.0011067005911209876
  },
  "gains": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 130.0,
    "speed_gain_hz": 150.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": 7.62939453125e-05,
    "tripped_ferr": null
  }
}
```

**[    32.1s | speed | accept]** 150.0 Hz accepted (speed_150.0hz: peak=0.00755 rms=0.00111 score=0.00977 stable dom=26.7Hz)

**[    32.1s | speed | done]** reached cap

**[    32.1s | position | start]** position ladder from 130.0 rad/s toward ~300.0 (cap 360.0)

**[    32.6s | position | write]** SDO write pos_gain_rad_s=156
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    39.8s | measure | measurement]** pos_156.0rads: peak=0.00664 rms=0.00099 score=0.00861 stable dom=27.3Hz
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_172935_X/05_pos_156.0rads.csv",
  "fft": {
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 27.3 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.24367660229574947,
    "n_samples": 1871,
    "peak_abs": 0.0066375732421875,
    "peaks": [
      {
        "freq_hz": 27.25815072153928,
        "magnitude": 0.00024504883805342916,
        "prominence": 9.834592044826906
      },
      {
        "freq_hz": 31.533939070016032,
        "magnitude": 0.0001957619606665921,
        "prominence": 7.856552336035216
      },
      {
        "freq_hz": 35.809727418492784,
        "magnitude": 0.00017354496112722065,
        "prominence": 6.9649132298657515
      },
      {
        "freq_hz": 28.861571352218064,
        "magnitude": 0.00016858798822573068,
        "prominence": 6.765974085119484
      },
      {
        "freq_hz": 33.137359700694816,
        "magnitude": 0.0001651484496066987,
        "prominence": 6.627934421641336
      }
    ],
    "ring_score": 0.5150039660545851,
    "rms": 0.0009877225636929507
  },
  "gains": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 156.0,
    "speed_gain_hz": 150.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": 0.0,
    "tripped_ferr": null
  }
}
```

**[    39.8s | position | accept]** 156.0 rad/s accepted (pos_156.0rads: peak=0.00664 rms=0.00099 score=0.00861 stable dom=27.3Hz)

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

**[    47.5s | measure | measurement]** pos_187.2rads: peak=0.00572 rms=0.00076 score=0.00724 stable dom=27.1Hz
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_172935_X/06_pos_187.2rads.csv",
  "fft": {
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 27.1 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.325910563139705,
    "n_samples": 1883,
    "peak_abs": 0.0057220458984375,
    "peaks": [
      {
        "freq_hz": 27.084439723844927,
        "magnitude": 0.00017739424387215347,
        "prominence": 9.084523102046731
      },
      {
        "freq_hz": 35.58151885289432,
        "magnitude": 0.0001732077220824467,
        "prominence": 8.870127453768408
      },
      {
        "freq_hz": 31.33297928836962,
        "magnitude": 0.00016905709419322377,
        "prominence": 8.65756996529195
      },
      {
        "freq_hz": 39.83005841741901,
        "magnitude": 0.0001433479305380032,
        "prominence": 7.340979944882535
      },
      {
        "freq_hz": 44.07859798194371,
        "magnitude": 0.00012180320599297078,
        "prominence": 6.237654698333743
      }
    ],
    "ring_score": 0.5891921687747529,
    "rms": 0.0007612317665581539
  },
  "gains": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 187.2,
    "speed_gain_hz": 150.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": 0.0002288818359375,
    "tripped_ferr": null
  }
}
```

**[    47.5s | position | accept]** 187.2 rad/s accepted (pos_187.2rads: peak=0.00572 rms=0.00076 score=0.00724 stable dom=27.1Hz)

**[    48.0s | position | write]** SDO write pos_gain_rad_s=224.64
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    55.3s | measure | measurement]** pos_224.6rads: peak=0.00519 rms=0.00072 score=0.00663 stable dom=27.4Hz
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_172935_X/07_pos_224.6rads.csv",
  "fft": {
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 27.4 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.2961220541807053,
    "n_samples": 1860,
    "peak_abs": 0.00518798828125,
    "peaks": [
      {
        "freq_hz": 27.419354838709676,
        "magnitude": 0.00023579361628662756,
        "prominence": 12.99731142433094
      },
      {
        "freq_hz": 31.72043010752688,
        "magnitude": 0.0002136758291965087,
        "prominence": 11.7781445471502
      },
      {
        "freq_hz": 36.02150537634408,
        "magnitude": 0.00018064715152526535,
        "prominence": 9.95755238529471
      },
      {
        "freq_hz": 40.32258064516129,
        "magnitude": 0.0001385731787050361,
        "prominence": 7.638369465013215
      },
      {
        "freq_hz": 44.62365591397849,
        "magnitude": 0.00010853627195352405,
        "prominence": 5.982688376520866
      }
    ],
    "ring_score": 0.6023832308630744,
    "rms": 0.0007228512287536725
  },
  "gains": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 224.64,
    "speed_gain_hz": 150.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": 0.0,
    "tripped_ferr": null
  }
}
```

**[    55.3s | position | accept]** 224.6 rad/s accepted (pos_224.6rads: peak=0.00519 rms=0.00072 score=0.00663 stable dom=27.4Hz)

**[    55.8s | position | write]** SDO write pos_gain_rad_s=269.568
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    62.9s | measure | measurement]** pos_269.6rads: peak=0.00420 rms=0.00063 score=0.00545 UNSTABLE dom=36.2Hz [HF energy 37%]
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_172935_X/08_pos_269.6rads.csv",
  "fft": {
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 36.2 Hz; HF energy 37%",
    "gate_stable": false,
    "hf_energy_ratio": 0.3681683557001908,
    "n_samples": 1797,
    "peak_abs": 0.0041961669921875,
    "peaks": [
      {
        "freq_hz": 36.171396772398445,
        "magnitude": 0.00014294045900598896,
        "prominence": 7.5058854432120725
      },
      {
        "freq_hz": 31.7195325542571,
        "magnitude": 0.00014094324169067703,
        "prominence": 7.401010417077569
      },
      {
        "freq_hz": 28.937117417918756,
        "magnitude": 0.0001300354839246143,
        "prominence": 6.828237803895018
      },
      {
        "freq_hz": 27.26766833611575,
        "magnitude": 0.0001253529642656039,
        "prominence": 6.582356012339781
      },
      {
        "freq_hz": 40.62326099053979,
        "magnitude": 0.00011654754170636979,
        "prominence": 6.1199782260342435
      }
    ],
    "ring_score": 0.6852200572731344,
    "rms": 0.0006258891547485722
  },
  "gains": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 269.568,
    "speed_gain_hz": 150.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": -0.00030517578125,
    "tripped_ferr": null
  }
}
```

**[    63.0s | position | backoff]** unstable at 269.6 rad/s (HF energy 37%) — returning to 224.6

**[    63.5s | position | write]** SDO write pos_gain_rad_s=224.64
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "pos_gain_rad_s"
  ]
}
```

**[    63.5s | integral | start]** integral tighten from 5.00 ms toward 2.00 ms (lower = stronger)

**[    64.0s | integral | write]** SDO write integral_ms=3.5
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "integral_ms"
  ]
}
```

**[    71.2s | measure | measurement]** integral_3.50ms: peak=0.00481 rms=0.00063 score=0.00606 stable dom=29.0Hz
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_172935_X/09_integral_3.50ms.csv",
  "fft": {
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 29.0 Hz",
    "gate_stable": false,
    "hf_energy_ratio": 0.3380640161773006,
    "n_samples": 1726,
    "peak_abs": 0.0048065185546875,
    "peaks": [
      {
        "freq_hz": 28.968713789107763,
        "magnitude": 0.00021926899653748575,
        "prominence": 12.60537210240721
      },
      {
        "freq_hz": 37.07995365005794,
        "magnitude": 0.00015636555249369294,
        "prominence": 8.989168575159333
      },
      {
        "freq_hz": 42.294322132097335,
        "magnitude": 0.00015187019977509544,
        "prominence": 8.730738999413077
      },
      {
        "freq_hz": 34.183082271147164,
        "magnitude": 0.00014862559096919816,
        "prominence": 8.54421239523769
      },
      {
        "freq_hz": 47.50869061413673,
        "magnitude": 0.00010168438333002407,
        "prominence": 5.84564853727343
      }
    ],
    "ring_score": 0.6407878573898642,
    "rms": 0.000627727315869539
  },
  "gains": {
    "integral_ms": 3.5,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 224.64,
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

**[    71.2s | integral | accept]** 3.50 ms accepted (rms +13.2%, peak -7.4%)

**[    71.7s | integral | write]** SDO write integral_ms=2.45
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "integral_ms"
  ]
}
```

**[    78.9s | measure | measurement]** integral_2.45ms: peak=0.02800 rms=0.01524 score=0.05848 UNSTABLE dom=259.4Hz [resonance peak 259.4 Hz (mag 0.004122, x7.2 floor, amp floor 0.001524); HF energy 92%; ring score 1.38]
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_172935_X/10_integral_2.45ms.csv",
  "fft": {
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 259.4 Hz; HF energy 92%; ring score 1.38",
    "gate_stable": false,
    "hf_energy_ratio": 0.9235283092183713,
    "n_samples": 1800,
    "peak_abs": 0.0279998779296875,
    "peaks": [
      {
        "freq_hz": 259.44444444444446,
        "magnitude": 0.0041221553669234315,
        "prominence": 7.191419276703574
      },
      {
        "freq_hz": 263.33333333333337,
        "magnitude": 0.003968619673338335,
        "prominence": 6.923564368717903
      },
      {
        "freq_hz": 325.55555555555554,
        "magnitude": 0.0026273924455874373,
        "prominence": 4.583689598959701
      },
      {
        "freq_hz": 275.55555555555554,
        "magnitude": 0.0025770228908856495,
        "prominence": 4.495816009927136
      },
      {
        "freq_hz": 268.33333333333337,
        "magnitude": 0.0025410840877385737,
        "prominence": 4.43311798456706
      }
    ],
    "ring_score": 1.3760496249965235,
    "rms": 0.01524191506175755
  },
  "gains": {
    "integral_ms": 2.4499999999999997,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 224.64,
    "speed_gain_hz": 150.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": -0.01617431640625,
    "tripped_ferr": null
  }
}
```

**[    78.9s | integral | backoff]** unstable at 2.45 ms (resonance peak 259.4 Hz (mag 0.004122, x7.2 floor, amp floor 0.001524); HF energy 92%; ring score 1.38) — returning to 3.50 ms

**[    79.4s | integral | write]** SDO write integral_ms=3.5
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "integral_ms"
  ]
}
```

**[    86.6s | measure | measurement]** verify: peak=0.00465 rms=0.00059 score=0.00584 UNSTABLE dom=29.1Hz [HF energy 45%]
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_172935_X/11_verify.csv",
  "fft": {
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 29.1 Hz; HF energy 45%",
    "gate_stable": false,
    "hf_energy_ratio": 0.44978821570184796,
    "n_samples": 1752,
    "peak_abs": 0.0046539306640625,
    "peaks": [
      {
        "freq_hz": 29.10958904109589,
        "magnitude": 0.00021079819433281267,
        "prominence": 11.147941134334136
      },
      {
        "freq_hz": 33.67579908675799,
        "magnitude": 0.00019346342060626038,
        "prominence": 10.231201606786266
      },
      {
        "freq_hz": 38.242009132420094,
        "magnitude": 0.0001858828692392185,
        "prominence": 9.830308512454744
      },
      {
        "freq_hz": 42.80821917808219,
        "magnitude": 0.00015945148112836018,
        "prominence": 8.432499770823023
      },
      {
        "freq_hz": 47.37442922374429,
        "magnitude": 0.0001344939269225651,
        "prominence": 7.112633886659476
      }
    ],
    "ring_score": 0.713504326507781,
    "rms": 0.0005923012424318727
  },
  "gains": {
    "integral_ms": 3.5,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 224.64,
    "speed_gain_hz": 150.0
  },
  "meta": {
    "abort_reason": "",
    "aborted": false,
    "position_drift": 0.00030517578125,
    "tripped_ferr": null
  }
}
```

**[    86.6s | verify | warning]** final tune unstable on verify (HF energy 45%) — backing off speed & position by 0.75x

**[    87.2s | verify | write]** SDO write speed_gain_hz=112.5, pos_gain_rad_s=168.48
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

**[    89.5s | measure | measurement]** verify_backoff: peak=0.00580 rms=0.00093 score=0.00765 UNSTABLE dom=37.0Hz [move aborted: MDI leg reported RCS_ERROR; HF energy 36%]
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_172935_X/12_verify_backoff.csv",
  "fft": {
    "gate_min_hz": 25.0,
    "gate_reason": "peak at 37.0 Hz; HF energy 36%",
    "gate_stable": false,
    "hf_energy_ratio": 0.3599161805606252,
    "n_samples": 459,
    "peak_abs": 0.00579833984375,
    "peaks": [
      {
        "freq_hz": 37.03703703703704,
        "magnitude": 0.00028118022239430866,
        "prominence": 4.480988400504142
      }
    ],
    "ring_score": 0.5245433303240651,
    "rms": 0.0009270485389056376
  },
  "gains": {
    "integral_ms": 3.5,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 168.48,
    "speed_gain_hz": 112.5
  },
  "meta": {
    "abort_reason": "MDI leg reported RCS_ERROR",
    "aborted": true,
    "position_drift": 0.0035858154296875,
    "tripped_ferr": null
  }
}
```

**[    89.6s | verify | revert]** still unstable after backoff — restoring baseline

**[    89.6s | verify | revert]** restoring baseline values for touched keys
```json
{
  "values": {
    "integral_ms": 5.0,
    "pos_gain_rad_s": 130.0,
    "speed_gain_hz": 80.0
  }
}
```

**[    89.9s | verify | write]** SDO write integral_ms=5, pos_gain_rad_s=130, speed_gain_hz=80
```json
{
  "failed": [],
  "skipped": [],
  "written": [
    "integral_ms",
    "pos_gain_rad_s",
    "speed_gain_hz"
  ]
}
```

**[    89.9s | verify | revert-ok]** baseline restored

**[    90.0s | measure | measurement]** verify_baseline: peak=0.00000 rms=0.00000 score=0.00000 UNSTABLE [move aborted: MDI leg reported RCS_ERROR; short buffer (9)]
```json
{
  "csv": "/home/jon/linuxcnc/configs/ethercat_mill/logs/tuning/one_click/20260712_172935_X/13_verify_baseline.csv",
  "fft": {
    "gate_min_hz": 25.0,
    "gate_reason": "short buffer (9 samples)",
    "gate_stable": false,
    "hf_energy_ratio": 0.0,
    "n_samples": 9,
    "peak_abs": 0.0,
    "peaks": [],
    "ring_score": 0.0,
    "rms": 0.0
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
    "abort_reason": "MDI leg reported RCS_ERROR",
    "aborted": true,
    "position_drift": 0.000152587890625,
    "tripped_ferr": null
  }
}
```

**[    90.0s | verify | baseline-check]** verify_baseline: peak=0.00000 rms=0.00000 score=0.00000 UNSTABLE [move aborted: MDI leg reported RCS_ERROR; short buffer (9)]

**[    90.1s | finalize | result]** campaign status: reverted
```json
{
  "baseline_score": 0.012976061101318156,
  "baseline_values": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 130.0,
    "speed_gain_hz": 80.0
  },
  "final_score": 0.0,
  "final_values": {
    "integral_ms": 5.0,
    "manual_mode": 0.0,
    "notch3_depth_pct": 100.0,
    "notch3_freq_hz": 8000.0,
    "notch3_width_pct": 0.0,
    "pos_gain_rad_s": 130.0,
    "speed_gain_hz": 80.0
  },
  "improvement_pct": null,
  "measurements": 13,
  "notch_applied": false,
  "preset": null,
  "reason": "verify stayed unstable after backoff \u2014 baseline restored"
}
```


---

**FINAL STATUS: REVERTED** — 2026-07-12T17:31:05
