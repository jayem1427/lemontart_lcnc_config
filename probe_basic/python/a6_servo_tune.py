"""A6-EC servo tuning: SDO read/write and per-axis JSON presets.

LinuxCNC joint.f-error / FERROR limits are left alone. Plot drive-native
following error (CiA 60F4 → tune-drive-ferr.N.out) on the Logging tab as DRIVE.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

LOG = logging.getLogger(__name__)

try:
    import linuxcnc
except ImportError:  # pragma: no cover - only available under LinuxCNC
    linuxcnc = None  # type: ignore

AXES: Dict[str, Dict[str, Any]] = {
    "X": {"joint": 0, "slave": 0, "linear": True, "scale": 13107.2},
    "Y": {"joint": 1, "slave": 1, "linear": True, "scale": 13107.2},
    "Z": {"joint": 2, "slave": 2, "linear": True, "scale": 13107.2},
    "A": {"joint": 3, "slave": 3, "linear": False, "scale": 364.088888889},
}

AXIS_ORDER = ("X", "Y", "Z", "A")

# EtherCAT object dictionary (A6 panel param mapping).
# Panel Cxx.yy → SDO subindex is typically yy+1 (hex).
SDO_MANUAL_MODE = (0x2000, 0x05)  # C00.04
SDO_STIFFNESS = (0x2000, 0x06)  # C00.05
SDO_INERTIA_RATIO = (0x2000, 0x07)  # C00.06, %
SDO_POS_GAIN = (0x2001, 0x01)  # C01.00, 0.1 rad/s
SDO_SPEED_GAIN = (0x2001, 0x02)  # C01.01, 0.1 Hz
SDO_INTEGRAL = (0x2001, 0x03)  # C01.02, 0.01 ms
SDO_TORQUE_FILTER = (0x2001, 0x04)  # C01.03, Hz
SDO_POS_GAIN_2 = (0x2001, 0x09)  # C01.08
SDO_SPEED_GAIN_2 = (0x2001, 0x0A)  # C01.09
SDO_INTEGRAL_2 = (0x2001, 0x0B)  # C01.0A
SDO_TORQUE_FILTER_2 = (0x2001, 0x0C)  # C01.0B
SDO_SPEED_FB_FILTER = (0x2001, 0x11)  # C01.10
SDO_SPEED_FB_LPF = (0x2001, 0x12)  # C01.11
SDO_SPEED_FF_SOURCE = (0x2001, 0x14)  # C01.13
SDO_SPEED_FF_PCT = (0x2001, 0x15)  # C01.14, 0.1%
SDO_SPEED_FF_FILTER = (0x2001, 0x16)  # C01.15, Hz
SDO_TORQUE_FF_SOURCE = (0x2001, 0x17)  # C01.16
SDO_TORQUE_FF_PCT = (0x2001, 0x18)  # C01.17, 0.1%
SDO_TORQUE_FF_FILTER = (0x2001, 0x19)  # C01.18, Hz
SDO_PDFF = (0x2001, 0x1C)  # C01.1B, 0.1%
SDO_DAMPING = (0x2001, 0x1D)  # C01.1C, 0.1%
SDO_ADAPTIVE_NOTCH = (0x2001, 0x31)  # C01.30
SDO_ADAPTIVE_NOTCH_TIMES = (0x2001, 0x32)  # C01.31
SDO_ADAPTIVE_NOTCH_FREQ = (0x2001, 0x33)  # C01.32, Hz (read-only test result)
SDO_ADAPTIVE_NOTCH_AMP = (0x2001, 0x34)  # C01.33, 0.1% (read-only)
# Torque-loop notches 1..5: freq Hz, width 0.1%, depth 0.1% (8000 Hz = off).
SDO_NOTCH1_FREQ = (0x2001, 0x41)  # C01.40
SDO_NOTCH1_WIDTH = (0x2001, 0x42)  # C01.41
SDO_NOTCH1_DEPTH = (0x2001, 0x43)  # C01.42
SDO_NOTCH2_FREQ = (0x2001, 0x44)  # C01.43
SDO_NOTCH2_WIDTH = (0x2001, 0x45)  # C01.44
SDO_NOTCH2_DEPTH = (0x2001, 0x46)  # C01.45
SDO_NOTCH3_FREQ = (0x2001, 0x47)  # C01.46
SDO_NOTCH3_WIDTH = (0x2001, 0x48)  # C01.47
SDO_NOTCH3_DEPTH = (0x2001, 0x49)  # C01.48
SDO_NOTCH4_FREQ = (0x2001, 0x4A)  # C01.49
SDO_NOTCH4_WIDTH = (0x2001, 0x4B)  # C01.4A
SDO_NOTCH4_DEPTH = (0x2001, 0x4C)  # C01.4B
SDO_NOTCH5_FREQ = (0x2001, 0x4D)  # C01.4C
SDO_NOTCH5_WIDTH = (0x2001, 0x4E)  # C01.4D
SDO_NOTCH5_DEPTH = (0x2001, 0x4F)  # C01.4E
SDO_GAIN_SW_MODE = (0x2001, 0x39)  # C01.38
SDO_GAIN_SW_TIME = (0x2001, 0x3A)  # C01.39, 0.1 ms
SDO_GAIN_SW_THRESH = (0x2001, 0x3B)  # C01.3A
SDO_GAIN_SW_WIDTH = (0x2001, 0x3C)  # C01.3B
SDO_FOLLOWING_ERROR = (0x6065, 0x00)
SDO_FOLLOWING_ERROR_TIME = (0x6066, 0x00)

# A6: notch frequency 8000 Hz disables that notch set.
NOTCH_DISABLED_HZ = 8000

NOTCH_LABELS = {
    0: "Off",
    1: "Adaptive (once)",
    2: "Adaptive (persistent)",
    3: "Reset notch params",
    4: "Resonance test only",
}

# C01.13 / C01.16 — source selects the FF path; 0 disables that feed-forward.
FF_SOURCE_LABELS = {
    0: "Off (disabled)",
    1: "Internal command",
    2: "External / reserved",
    5: "Special / reserved",
}

# UI / snapshot parameter catalog.
# scale: multiply raw→display; write uses round(display/scale) unless axis_unit.
PARAM_DEFS: List[Dict[str, Any]] = [
    # --- Rigidity ---
    {
        "key": "stiffness_level",
        "label": "C00.05 stiffness level",
        "group": "Rigidity",
        "sdo": SDO_STIFFNESS,
        "bits": 16,
        "scale": 1.0,
        "unit": "",
        "min": 1,
        "max": 31,
        "default": 12,
        "decimals": 0,
    },
    {
        "key": "manual_mode",
        "label": "C00.04 auto-tuning mode",
        "group": "Rigidity",
        "sdo": SDO_MANUAL_MODE,
        "bits": 16,
        "scale": 1.0,
        "unit": "{0,1,2}",
        "min": 0,
        "max": 2,
        "default": 0,
        "decimals": 0,
        "note": "0=manual 1=standard 2=positioning",
    },
    {
        "key": "inertia_ratio_pct",
        "label": "C00.06 load inertia ratio",
        "group": "Rigidity",
        "sdo": SDO_INERTIA_RATIO,
        "bits": 16,
        "scale": 1.0,
        "unit": "%",
        "min": 0,
        "max": 12000,
        "default": 100,
        "decimals": 0,
    },
    # --- 1st gains ---
    {
        "key": "pos_gain_rad_s",
        "label": "C01.00 1st position loop gain",
        "group": "1st Gains",
        "sdo": SDO_POS_GAIN,
        "bits": 16,
        "scale": 0.1,
        "unit": "rad/s",
        "min": 0.1,
        "max": 2000.0,
        "default": 30.0,
        "decimals": 1,
    },
    {
        "key": "speed_gain_hz",
        "label": "C01.01 1st speed loop gain",
        "group": "1st Gains",
        "sdo": SDO_SPEED_GAIN,
        "bits": 16,
        "scale": 0.1,
        "unit": "Hz",
        "min": 0.1,
        "max": 2000.0,
        "default": 20.0,
        "decimals": 1,
    },
    {
        "key": "integral_ms",
        "label": "C01.02 1st speed integral time",
        "group": "1st Gains",
        "sdo": SDO_INTEGRAL,
        "bits": 16,
        "scale": 0.01,
        "unit": "ms",
        "min": 0.15,
        "max": 512.0,
        "default": 31.84,
        "decimals": 2,
    },
    {
        "key": "torque_filter_hz",
        "label": "C01.03 1st torque filter",
        "group": "1st Gains",
        "sdo": SDO_TORQUE_FILTER,
        "bits": 16,
        "scale": 1.0,
        "unit": "Hz",
        "min": 5,
        "max": 16000,
        "default": 200,
        "decimals": 0,
    },
    # --- 2nd gains ---
    {
        "key": "pos_gain_2_rad_s",
        "label": "C01.08 2nd position loop gain",
        "group": "2nd Gains",
        "sdo": SDO_POS_GAIN_2,
        "bits": 16,
        "scale": 0.1,
        "unit": "rad/s",
        "min": 0.1,
        "max": 2000.0,
        "default": 56.0,
        "decimals": 1,
    },
    {
        "key": "speed_gain_2_hz",
        "label": "C01.09 2nd speed loop gain",
        "group": "2nd Gains",
        "sdo": SDO_SPEED_GAIN_2,
        "bits": 16,
        "scale": 0.1,
        "unit": "Hz",
        "min": 0.1,
        "max": 2000.0,
        "default": 35.0,
        "decimals": 1,
    },
    {
        "key": "integral_2_ms",
        "label": "C01.0A 2nd speed integral time",
        "group": "2nd Gains",
        "sdo": SDO_INTEGRAL_2,
        "bits": 16,
        "scale": 0.01,
        "unit": "ms",
        "min": 0.15,
        "max": 512.0,
        "default": 22.74,
        "decimals": 2,
    },
    {
        "key": "torque_filter_2_hz",
        "label": "C01.0B 2nd torque filter",
        "group": "2nd Gains",
        "sdo": SDO_TORQUE_FILTER_2,
        "bits": 16,
        "scale": 1.0,
        "unit": "Hz",
        "min": 5,
        "max": 16000,
        "default": 280,
        "decimals": 0,
    },
    # --- Feed-forward ---
    {
        "key": "speed_ff_source",
        "label": "C01.13 speed FF source",
        "group": "Feed-forward",
        "sdo": SDO_SPEED_FF_SOURCE,
        "bits": 16,
        "scale": 1.0,
        "unit": "{0,1,2,5}",
        "min": 0,
        "max": 5,
        "default": 0,
        "decimals": 0,
        "note": "0=off (disabled). Non-zero enables speed FF (typical 1).",
    },
    {
        "key": "speed_ff_pct",
        "label": "C01.14 speed FF percent",
        "group": "Feed-forward",
        "sdo": SDO_SPEED_FF_PCT,
        "bits": 16,
        "scale": 0.1,
        "unit": "%",
        "min": 0.0,
        "max": 200.0,
        "default": 0.0,
        "decimals": 1,
    },
    {
        "key": "speed_ff_filter_hz",
        "label": "C01.15 speed FF filter",
        "group": "Feed-forward",
        "sdo": SDO_SPEED_FF_FILTER,
        "bits": 16,
        "scale": 1.0,
        "unit": "Hz",
        "min": 5,
        "max": 16000,
        "default": 318,
        "decimals": 0,
    },
    {
        "key": "torque_ff_source",
        "label": "C01.16 torque FF source",
        "group": "Feed-forward",
        "sdo": SDO_TORQUE_FF_SOURCE,
        "bits": 16,
        "scale": 1.0,
        "unit": "{0,1,2,5}",
        "min": 0,
        "max": 5,
        "default": 0,
        "decimals": 0,
        "note": "0=off (disabled). Non-zero enables torque FF (typical 1).",
    },
    {
        "key": "torque_ff_pct",
        "label": "C01.17 torque FF percent",
        "group": "Feed-forward",
        "sdo": SDO_TORQUE_FF_PCT,
        "bits": 16,
        "scale": 0.1,
        "unit": "%",
        "min": 0.0,
        "max": 200.0,
        "default": 0.0,
        "decimals": 1,
    },
    {
        "key": "torque_ff_filter_hz",
        "label": "C01.18 torque FF filter",
        "group": "Feed-forward",
        "sdo": SDO_TORQUE_FF_FILTER,
        "bits": 16,
        "scale": 1.0,
        "unit": "Hz",
        "min": 5,
        "max": 16000,
        "default": 318,
        "decimals": 0,
    },
    # --- Advanced ---
    {
        "key": "speed_fb_filter",
        "label": "C01.10 speed feedback filter",
        "group": "Advanced",
        "sdo": SDO_SPEED_FB_FILTER,
        "bits": 16,
        "scale": 1.0,
        "unit": "{0..4}",
        "min": 0,
        "max": 4,
        "default": 0,
        "decimals": 0,
        # A6 rejects writes (SDO abort 0x06010002 read-only) — display only.
        "writable": False,
        "note": "Read-only on this drive firmware — shown for reference only.",
    },
    {
        "key": "speed_fb_lpf_hz",
        "label": "C01.11 speed feedback LPF",
        "group": "Advanced",
        "sdo": SDO_SPEED_FB_LPF,
        "bits": 16,
        "scale": 1.0,
        "unit": "Hz",
        "min": 10,
        "max": 16000,
        "default": 8000,
        "decimals": 0,
    },
    {
        "key": "pdff_pct",
        "label": "C01.1B PDFF coefficient",
        "group": "Advanced",
        "sdo": SDO_PDFF,
        "bits": 16,
        "scale": 0.1,
        "unit": "%",
        "min": 0.0,
        "max": 100.0,
        "default": 100.0,
        "decimals": 1,
    },
    {
        "key": "damping_pct",
        "label": "C01.1C damping coefficient",
        "group": "Advanced",
        "sdo": SDO_DAMPING,
        "bits": 16,
        "scale": 0.1,
        "unit": "%",
        "min": 0.0,
        "max": 100.0,
        "default": 0.0,
        "decimals": 1,
    },
    {
        "key": "adaptive_notch",
        "label": "C01.30 adaptive notch mode",
        "group": "Notch",
        "sdo": SDO_ADAPTIVE_NOTCH,
        "bits": 16,
        "scale": 1.0,
        "unit": "{0..4}",
        "min": 0,
        "max": 4,
        "default": 0,
        "decimals": 0,
        "note": "0=off 1=once 2=persistent 3=reset 4=resonance test only",
    },
    {
        "key": "adaptive_notch_times",
        "label": "C01.31 adaptive notch test times",
        "group": "Notch",
        "sdo": SDO_ADAPTIVE_NOTCH_TIMES,
        "bits": 16,
        "scale": 1.0,
        "unit": "",
        "min": 0,
        "max": 65535,
        "default": 0,
        "decimals": 0,
    },
    {
        "key": "adaptive_notch_freq_hz",
        "label": "C01.32 adaptive notch test frequency",
        "group": "Notch",
        "sdo": SDO_ADAPTIVE_NOTCH_FREQ,
        "bits": 16,
        "scale": 1.0,
        "unit": "Hz",
        "min": 0,
        "max": 8000,
        "default": 0,
        "decimals": 0,
        "writable": False,
        "note": "Read-only — result of C01.30 mode 4 / adaptive detection.",
    },
    {
        "key": "adaptive_notch_amp_pct",
        "label": "C01.33 adaptive notch test amplitude",
        "group": "Notch",
        "sdo": SDO_ADAPTIVE_NOTCH_AMP,
        "bits": 16,
        "scale": 0.1,
        "unit": "%",
        "min": 0.0,
        "max": 500.0,
        "default": 0.0,
        "decimals": 1,
        "writable": False,
        "note": "Read-only adaptive test amplitude.",
    },
    {
        "key": "notch1_freq_hz",
        "label": "C01.40 1st notch frequency",
        "group": "Notch",
        "sdo": SDO_NOTCH1_FREQ,
        "bits": 16,
        "scale": 1.0,
        "unit": "Hz",
        "min": 10,
        "max": 8000,
        "default": 8000,
        "decimals": 0,
        "note": "8000 Hz disables this notch. Adaptive may overwrite 1st/2nd.",
    },
    {
        "key": "notch1_width_pct",
        "label": "C01.41 1st notch width",
        "group": "Notch",
        "sdo": SDO_NOTCH1_WIDTH,
        "bits": 16,
        "scale": 0.1,
        "unit": "%",
        "min": 0.0,
        "max": 400.0,
        "default": 0.0,
        "decimals": 1,
    },
    {
        "key": "notch1_depth_pct",
        "label": "C01.42 1st notch depth",
        "group": "Notch",
        "sdo": SDO_NOTCH1_DEPTH,
        "bits": 16,
        "scale": 0.1,
        "unit": "%",
        "min": 1.0,
        "max": 100.0,
        "default": 100.0,
        "decimals": 1,
        "note": "Lower % = deeper notch (stronger suppression).",
    },
    {
        "key": "notch2_freq_hz",
        "label": "C01.43 2nd notch frequency",
        "group": "Notch",
        "sdo": SDO_NOTCH2_FREQ,
        "bits": 16,
        "scale": 1.0,
        "unit": "Hz",
        "min": 10,
        "max": 8000,
        "default": 8000,
        "decimals": 0,
    },
    {
        "key": "notch2_width_pct",
        "label": "C01.44 2nd notch width",
        "group": "Notch",
        "sdo": SDO_NOTCH2_WIDTH,
        "bits": 16,
        "scale": 0.1,
        "unit": "%",
        "min": 0.0,
        "max": 400.0,
        "default": 0.0,
        "decimals": 1,
    },
    {
        "key": "notch2_depth_pct",
        "label": "C01.45 2nd notch depth",
        "group": "Notch",
        "sdo": SDO_NOTCH2_DEPTH,
        "bits": 16,
        "scale": 0.1,
        "unit": "%",
        "min": 1.0,
        "max": 100.0,
        "default": 100.0,
        "decimals": 1,
    },
    {
        "key": "notch3_freq_hz",
        "label": "C01.46 3rd notch frequency",
        "group": "Notch",
        "sdo": SDO_NOTCH3_FREQ,
        "bits": 16,
        "scale": 1.0,
        "unit": "Hz",
        "min": 10,
        "max": 8000,
        "default": 8000,
        "decimals": 0,
        "note": "Preferred manual notch — adaptive uses 1st/2nd.",
    },
    {
        "key": "notch3_width_pct",
        "label": "C01.47 3rd notch width",
        "group": "Notch",
        "sdo": SDO_NOTCH3_WIDTH,
        "bits": 16,
        "scale": 0.1,
        "unit": "%",
        "min": 0.0,
        "max": 400.0,
        "default": 0.0,
        "decimals": 1,
    },
    {
        "key": "notch3_depth_pct",
        "label": "C01.48 3rd notch depth",
        "group": "Notch",
        "sdo": SDO_NOTCH3_DEPTH,
        "bits": 16,
        "scale": 0.1,
        "unit": "%",
        "min": 1.0,
        "max": 100.0,
        "default": 100.0,
        "decimals": 1,
    },
    {
        "key": "notch4_freq_hz",
        "label": "C01.49 4th notch frequency",
        "group": "Notch",
        "sdo": SDO_NOTCH4_FREQ,
        "bits": 16,
        "scale": 1.0,
        "unit": "Hz",
        "min": 10,
        "max": 8000,
        "default": 8000,
        "decimals": 0,
    },
    {
        "key": "notch4_width_pct",
        "label": "C01.4A 4th notch width",
        "group": "Notch",
        "sdo": SDO_NOTCH4_WIDTH,
        "bits": 16,
        "scale": 0.1,
        "unit": "%",
        "min": 0.0,
        "max": 400.0,
        "default": 0.0,
        "decimals": 1,
    },
    {
        "key": "notch4_depth_pct",
        "label": "C01.4B 4th notch depth",
        "group": "Notch",
        "sdo": SDO_NOTCH4_DEPTH,
        "bits": 16,
        "scale": 0.1,
        "unit": "%",
        "min": 1.0,
        "max": 100.0,
        "default": 100.0,
        "decimals": 1,
    },
    {
        "key": "notch5_freq_hz",
        "label": "C01.4C 5th notch frequency",
        "group": "Notch",
        "sdo": SDO_NOTCH5_FREQ,
        "bits": 16,
        "scale": 1.0,
        "unit": "Hz",
        "min": 10,
        "max": 8000,
        "default": 8000,
        "decimals": 0,
    },
    {
        "key": "notch5_width_pct",
        "label": "C01.4D 5th notch width",
        "group": "Notch",
        "sdo": SDO_NOTCH5_WIDTH,
        "bits": 16,
        "scale": 0.1,
        "unit": "%",
        "min": 0.0,
        "max": 400.0,
        "default": 0.0,
        "decimals": 1,
    },
    {
        "key": "notch5_depth_pct",
        "label": "C01.4E 5th notch depth",
        "group": "Notch",
        "sdo": SDO_NOTCH5_DEPTH,
        "bits": 16,
        "scale": 0.1,
        "unit": "%",
        "min": 1.0,
        "max": 100.0,
        "default": 100.0,
        "decimals": 1,
    },
    {
        "key": "gain_sw_mode",
        "label": "C01.38 gain switchover mode",
        "group": "Advanced",
        "sdo": SDO_GAIN_SW_MODE,
        "bits": 16,
        "scale": 1.0,
        "unit": "{0..8}",
        "min": 0,
        "max": 8,
        "default": 0,
        "decimals": 0,
        # A6 rejects writes (SDO abort 0x06010002 read-only) — display only.
        "writable": False,
        "note": "Read-only on this drive firmware — shown for reference only.",
    },
    {
        "key": "gain_sw_time_ms",
        "label": "C01.39 gain switchover time",
        "group": "Advanced",
        "sdo": SDO_GAIN_SW_TIME,
        "bits": 16,
        "scale": 0.1,
        "unit": "ms",
        "min": 1.0,
        "max": 1000.0,
        "default": 5.0,
        "decimals": 1,
    },
    {
        "key": "gain_sw_thresh",
        "label": "C01.3A gain switchover threshold",
        "group": "Advanced",
        "sdo": SDO_GAIN_SW_THRESH,
        "bits": 16,
        "scale": 1.0,
        "unit": "",
        "min": 0,
        "max": 65535,
        "default": 10,
        "decimals": 0,
    },
    {
        "key": "gain_sw_width",
        "label": "C01.3B gain switchover width",
        "group": "Advanced",
        "sdo": SDO_GAIN_SW_WIDTH,
        "bits": 16,
        "scale": 1.0,
        "unit": "",
        "min": 0,
        "max": 65535,
        "default": 10,
        "decimals": 0,
    },
    # --- Limits (drive 6065/6066) ---
    {
        "key": "following_error",
        "label": "6065 following error window",
        "group": "Limits",
        "sdo": SDO_FOLLOWING_ERROR,
        "bits": 32,
        "scale": "axis_unit",  # counts ↔ mm/deg via SCALE
        "unit": "mm|deg",
        "min": 0.001,
        "max": 50.0,
        "default": 1.0,
        "decimals": 3,
    },
    {
        "key": "following_error_time_ms",
        "label": "6066 following error timeout",
        "group": "Limits",
        "sdo": SDO_FOLLOWING_ERROR_TIME,
        "bits": 16,
        "scale": 1.0,
        "unit": "ms",
        "min": 0,
        "max": 1000,
        "default": 250,
        "decimals": 0,
    },
]

PARAM_BY_KEY = {p["key"]: p for p in PARAM_DEFS}


def repo_root() -> str:
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
    )


def preset_root() -> str:
    return os.path.join(repo_root(), "config", "tuning", "presets")


def _sanitize_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", (value or "").strip())
    return cleaned.strip("_") or "preset"


def drive_ferr_halpin(axis: str) -> str:
    """Scaled drive FERR (mm or deg) from 60F4."""
    joint = AXES[axis]["joint"]
    return f"tune-drive-ferr.{joint}.out"


def drive_ferr_counts_halpin(axis: str) -> str:
    """Raw 60F4 counts (s32) before SCALE divide."""
    slave = AXES[axis]["slave"]
    return f"lcec.0.{slave}.ferr-fb"


def axis_unit(axis: str) -> str:
    return "mm" if AXES[axis]["linear"] else "deg"


def counts_to_unit(axis: str, counts: float) -> float:
    scale = float(AXES[axis]["scale"])
    if scale == 0:
        return float("nan")
    return float(counts) / scale


def unit_to_counts(axis: str, value: float) -> int:
    scale = float(AXES[axis]["scale"])
    return int(round(float(value) * scale))


def default_param_values() -> Dict[str, float]:
    return {p["key"]: float(p["default"]) for p in PARAM_DEFS}


def default_axis_params() -> "AxisTuneParams":
    return AxisTuneParams(values=default_param_values())


class AxisTuneParams:
    """Human-friendly tuning values for one axis (catalog-backed values dict)."""

    def __init__(self, values: Optional[Dict[str, float]] = None, **legacy: Any) -> None:
        """Accept values=dict or legacy kwargs (manual_mode bool, pos_gain_rad_s, …)."""
        if legacy:
            data = dict(legacy)
            if values:
                for key, val in values.items():
                    data.setdefault(key, val)
            self.values = self._coerce_values(data)
        elif values is None:
            self.values = default_param_values()
        else:
            self.values = self._coerce_values(values)

    @staticmethod
    def _coerce_values(data: Dict[str, Any]) -> Dict[str, float]:
        values = default_param_values()
        for key in list(values.keys()):
            if key in data and key != "manual_mode":
                values[key] = float(data[key])
        if "manual_mode" in data:
            mm = data["manual_mode"]
            if isinstance(mm, bool):
                values["manual_mode"] = 0.0 if mm else 1.0
            else:
                values["manual_mode"] = float(mm)
        elif "manual_mode_bool" in data:
            values["manual_mode"] = 0.0 if data["manual_mode_bool"] else 1.0
        return values

    # --- Legacy attribute accessors (older UI / presets) ---
    @property
    def inertia_ratio_pct(self) -> float:
        return float(self.values.get("inertia_ratio_pct", 100.0))

    @property
    def pos_gain_rad_s(self) -> float:
        return float(self.values.get("pos_gain_rad_s", 30.0))

    @property
    def speed_gain_hz(self) -> float:
        return float(self.values.get("speed_gain_hz", 20.0))

    @property
    def integral_ms(self) -> float:
        return float(self.values.get("integral_ms", 31.84))

    @property
    def adaptive_notch(self) -> int:
        return int(self.values.get("adaptive_notch", 1))

    @property
    def manual_mode(self) -> bool:
        """Legacy bool: True means C00.04 == 0 (manual)."""
        return int(self.values.get("manual_mode", 0)) == 0

    @property
    def following_error(self) -> float:
        return float(self.values.get("following_error", 1.0))

    def get(self, key: str) -> float:
        default = PARAM_BY_KEY[key]["default"] if key in PARAM_BY_KEY else 0.0
        return float(self.values.get(key, default))

    def set(self, key: str, value: float) -> None:
        self.values[key] = float(value)

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {k: float(v) for k, v in self.values.items()}
        # Keep numeric C00.04 (0/1/2). Older presets may still store a bool;
        # from_dict / _coerce_values accept both.
        if "manual_mode" in self.values:
            out["manual_mode"] = float(self.values.get("manual_mode", 0.0))
            out["manual_mode_bool"] = self.manual_mode
        return out

    @classmethod
    def from_dict(
        cls, data: Dict[str, Any], *, fill_defaults: bool = True
    ) -> "AxisTuneParams":
        if fill_defaults:
            return cls(values=cls._coerce_values(data))
        values: Dict[str, float] = {}
        for key, val in data.items():
            if key in PARAM_BY_KEY:
                if key == "manual_mode" and isinstance(val, bool):
                    values[key] = 0.0 if val else 1.0
                else:
                    try:
                        values[key] = float(val)
                    except (TypeError, ValueError):
                        continue
        if "manual_mode" not in values and "manual_mode_bool" in data:
            values["manual_mode"] = 0.0 if data["manual_mode_bool"] else 1.0
        params = cls.__new__(cls)
        params.values = values
        return params

    def copy(self) -> "AxisTuneParams":
        # Shallow copy without re-filling catalog defaults (preserves partial reads).
        clone = AxisTuneParams.__new__(AxisTuneParams)
        clone.values = dict(self.values)
        return clone

    def following_error_counts(self, axis: str) -> int:
        return max(1, unit_to_counts(axis, self.following_error))


@dataclass
class AxisPreset:
    name: str
    axis: str
    params: AxisTuneParams
    created: str = field(default_factory=lambda: _utc_now())
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "axis": self.axis,
            "created": self.created,
            "notes": self.notes,
            "params": self.params.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AxisPreset":
        return cls(
            name=data["name"],
            axis=data["axis"],
            created=data.get("created", _utc_now()),
            notes=data.get("notes", ""),
            # Never invent catalog defaults for keys absent from the JSON.
            params=AxisTuneParams.from_dict(
                data.get("params", {}), fill_defaults=False
            ),
        )


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _raw_to_display(defn: Dict[str, Any], raw: int, axis: str) -> float:
    scale = defn["scale"]
    if scale == "axis_unit":
        return counts_to_unit(axis, float(raw))
    return float(raw) * float(scale)


def _display_to_raw(defn: Dict[str, Any], value: float, axis: str) -> int:
    scale = defn["scale"]
    if scale == "axis_unit":
        return max(1, unit_to_counts(axis, value))
    scale_f = float(scale)
    if scale_f == 0:
        return int(round(value))
    return int(round(float(value) / scale_f))


def _run_ethercat(args: List[str]) -> str:
    """Run ethercat CLI; retry with sudo -n if permission denied."""
    for prefix in ([], ["sudo", "-n"]):
        cmd = prefix + ["ethercat"] + args
        try:
            return subprocess.check_output(
                cmd, stderr=subprocess.STDOUT, text=True
            ).strip()
        except subprocess.CalledProcessError as exc:
            text = (exc.output or "").lower()
            if prefix or "permission" not in text and "denied" not in text:
                raise RuntimeError(exc.output or str(exc)) from exc
    raise RuntimeError(
        "ethercat command failed (try passwordless sudo for ethercat)"
    )


def ethercat_upload_u16(slave: int, index: int, subindex: int) -> int:
    # A6 vendor objects often lack SDO dictionary info — --type is mandatory.
    out = _run_ethercat(
        [
            "upload",
            "-p",
            str(slave),
            "-t",
            "uint16",
            f"0x{index:04X}",
            str(subindex),
        ]
    )
    return int(out.split()[0], 0)


def ethercat_upload_u32(slave: int, index: int, subindex: int) -> int:
    out = _run_ethercat(
        [
            "upload",
            "-p",
            str(slave),
            "-t",
            "uint32",
            f"0x{index:04X}",
            str(subindex),
        ]
    )
    return int(out.split()[0], 0)


def ethercat_download_u16(
    slave: int, index: int, subindex: int, value: int
) -> None:
    _run_ethercat(
        [
            "download",
            "-p",
            str(slave),
            "-t",
            "uint16",
            f"0x{index:04X}",
            str(subindex),
            str(int(value) & 0xFFFF),
        ]
    )


def ethercat_download_u32(
    slave: int, index: int, subindex: int, value: int
) -> None:
    _run_ethercat(
        [
            "download",
            "-p",
            str(slave),
            "-t",
            "uint32",
            f"0x{index:04X}",
            str(subindex),
            str(int(value) & 0xFFFFFFFF),
        ]
    )


_hal_comp = None


def _ensure_hal_component():
    global _hal_comp
    if _hal_comp is not None:
        return _hal_comp if _hal_comp is not False else None
    try:
        import hal as linuxcnc_hal

        name = "pb_a6_tune"
        suffix = 0
        while linuxcnc_hal.component_exists(f"{name}{suffix}" if suffix else name):
            suffix += 1
        comp_name = f"{name}{suffix}" if suffix else name
        _hal_comp = linuxcnc_hal.component(comp_name)
        _hal_comp.ready()
        return _hal_comp
    except Exception:
        _hal_comp = False
        return None


def hal_getp(pin: str) -> float:
    """Read a HAL pin via in-process API when possible; else halcmd."""
    try:
        import hal as linuxcnc_hal

        if _ensure_hal_component() is not None:
            val = linuxcnc_hal.get_value(pin)
            if isinstance(val, bool):
                return 1.0 if val else 0.0
            return float(val)
    except Exception:
        pass
    try:
        output = subprocess.check_output(
            ["halcmd", "getp", pin],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        text = output.strip()
        if not text:
            return float("nan")
        if text in ("TRUE", "TRUE\n"):
            return 1.0
        if text in ("FALSE", "FALSE\n"):
            return 0.0
        if text.lower().startswith("0x"):
            val = int(text, 16)
            if val >= 0x80000000:
                val -= 0x100000000
            return float(val)
        return float(text)
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError):
        return float("nan")


def hal_getp_s32(pin: str) -> float:
    """Read an s32 HAL pin as a signed integer (encoder counts / 60F4)."""
    raw = hal_getp(pin)
    if raw != raw:
        return raw
    val = int(round(raw))
    # Guard against unsigned wrap if a tool printed s32 as u32.
    if val >= 0x80000000:
        val -= 0x100000000
    return float(val)


def read_drive_ferr(axis: str) -> Tuple[float, float]:
    """Return (counts, mm_or_deg) for live 60F4 following error.

    Pulses always come from the raw lcec ``ferr-fb`` s32 pin for that axis
    slave — never from the scaled float path (which is mm/deg).
    """
    counts = hal_getp_s32(drive_ferr_counts_halpin(axis))
    scaled = hal_getp(drive_ferr_halpin(axis))
    if counts == counts:
        # Authoritative mm/deg from pulses ÷ joint SCALE.
        scaled = counts_to_unit(axis, counts)
    elif scaled == scaled:
        counts = float(unit_to_counts(axis, scaled))
    return counts, scaled


def read_axis_params(axis: str) -> Tuple["AxisTuneParams", List[str], List[str]]:
    """Upload catalog SDOs.

    Returns (params, ok_keys, failed_keys). Failed keys are omitted from
    params.values so APPLY cannot accidentally write catalog defaults over
    unread drive values.
    """
    slave = AXES[axis]["slave"]
    values: Dict[str, float] = {}
    ok_keys: List[str] = []
    failed_keys: List[str] = []
    for defn in PARAM_DEFS:
        key = defn["key"]
        try:
            index, sub = defn["sdo"]
            if defn["bits"] == 32:
                raw = ethercat_upload_u32(slave, index, sub)
            else:
                raw = ethercat_upload_u16(slave, index, sub)
            values[key] = _raw_to_display(defn, raw, axis)
            ok_keys.append(key)
        except Exception as exc:
            failed_keys.append(key)
            LOG.warning("SDO read failed axis=%s key=%s: %s", axis, key, exc)
    if failed_keys:
        LOG.warning(
            "partial SDO read on axis %s (%d/%d ok): failed %s",
            axis,
            len(ok_keys),
            len(PARAM_DEFS),
            ", ".join(failed_keys[:8]),
        )
    # Build without filling missing keys from catalog defaults.
    params = AxisTuneParams.__new__(AxisTuneParams)
    params.values = {k: float(v) for k, v in values.items()}
    return params, ok_keys, failed_keys


def _lcnc_stat_cmd():
    if linuxcnc is None:
        raise RuntimeError("linuxcnc Python module not available")
    return linuxcnc.stat(), linuxcnc.command()


def machine_is_on() -> bool:
    """True when LinuxCNC machine is ON (amps may be enabled)."""
    if linuxcnc is None:
        return False
    try:
        stat, _ = _lcnc_stat_cmd()
        stat.poll()
        return bool(stat.enabled) and stat.task_state == linuxcnc.STATE_ON
    except Exception:
        return False


def wait_for_machine(want_on: bool, timeout_s: float = 8.0) -> bool:
    """Wait until machine enabled state matches want_on."""
    if linuxcnc is None:
        return False
    deadline = time.time() + timeout_s
    stat, _ = _lcnc_stat_cmd()
    while time.time() < deadline:
        stat.poll()
        is_on = bool(stat.enabled) and stat.task_state == linuxcnc.STATE_ON
        if is_on == want_on:
            return True
        time.sleep(0.05)
    return False


def set_machine_enabled(enable: bool) -> None:
    """Turn machine ON or OFF via linuxcnc.command (disables/enables amps)."""
    if linuxcnc is None:
        raise RuntimeError("linuxcnc Python module not available")
    _, cmd = _lcnc_stat_cmd()
    if enable:
        cmd.state(linuxcnc.STATE_ON)
    else:
        cmd.state(linuxcnc.STATE_OFF)
    if not wait_for_machine(enable, timeout_s=8.0):
        state = "ON" if enable else "OFF"
        raise RuntimeError(f"timed out waiting for machine {state}")


def cia402_enable_pin(axis: str) -> str:
    return f"cia402.{AXES[axis]['joint']}.enable"


def wait_for_axis_disabled(axis: str, timeout_s: float = 5.0) -> bool:
    """Wait until the axis amp enable is FALSE (safe for C00/C01 SDO writes)."""
    pin = cia402_enable_pin(axis)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        val = hal_getp(pin)
        if val == val and val < 0.5:
            # Extra settle after enable drops — A6 needs a beat before SDO accept.
            time.sleep(0.15)
            return True
        time.sleep(0.05)
    return False


def _sdo_download(defn: Dict[str, Any], slave: int, raw: int) -> None:
    index, sub = defn["sdo"]
    if defn["bits"] == 32:
        ethercat_download_u32(slave, index, sub, raw)
    else:
        ethercat_download_u16(slave, index, sub, raw)


def _sdo_upload(defn: Dict[str, Any], slave: int) -> int:
    index, sub = defn["sdo"]
    if defn["bits"] == 32:
        return ethercat_upload_u32(slave, index, sub)
    return ethercat_upload_u16(slave, index, sub)


def write_axis_sdos(
    axis: str,
    params: AxisTuneParams,
    keys: Optional[List[str]] = None,
    *,
    retries: int = 3,
) -> Dict[str, Any]:
    """Write drive SDOs with per-key retry + verify.

    Never aborts the whole batch on one failure — RO / flaky keys are reported
    in ``failed`` so the rest still apply. Skips catalog entries marked
    ``writable: False``.
    """
    slave = AXES[axis]["slave"]
    if keys is None:
        keys = [p["key"] for p in PARAM_DEFS]
    written: List[str] = []
    failed: List[Tuple[str, str]] = []
    skipped: List[str] = []

    for key in keys:
        defn = PARAM_BY_KEY.get(key)
        if defn is None:
            continue
        if defn.get("writable", True) is False:
            skipped.append(key)
            continue
        if key not in params.values:
            LOG.warning("skip write %s: no value in params", key)
            skipped.append(key)
            continue

        value = float(params.values[key])
        raw = _display_to_raw(defn, value, axis)
        if defn["bits"] != 32 and defn["scale"] != "axis_unit":
            scale_f = float(defn["scale"])
            lo = int(round(float(defn["min"]) / scale_f))
            hi = int(round(float(defn["max"]) / scale_f))
            raw = max(lo, min(hi, raw))

        last_err = ""
        ok = False
        for attempt in range(1, retries + 1):
            try:
                _sdo_download(defn, slave, raw)
                time.sleep(0.02)
                got = _sdo_upload(defn, slave)
                if got == raw:
                    ok = True
                    break
                last_err = f"verify mismatch wrote={raw} read={got}"
                LOG.warning(
                    "SDO verify fail axis=%s key=%s attempt=%d %s",
                    axis,
                    key,
                    attempt,
                    last_err,
                )
            except Exception as exc:
                last_err = str(exc).strip() or repr(exc)
                LOG.warning(
                    "SDO write fail axis=%s key=%s attempt=%d: %s",
                    axis,
                    key,
                    attempt,
                    last_err,
                )
                # Read-only / not allowed — don't burn retries.
                low = last_err.lower()
                if "0x06010002" in low or "read-only" in low:
                    break
                time.sleep(0.05 * attempt)

        if ok:
            written.append(key)
        else:
            failed.append((key, last_err or "unknown error"))

    return {
        "written": written,
        "failed": failed,
        "skipped": skipped,
    }


def apply_axis_params(
    axis: str,
    params: AxisTuneParams,
    *,
    cycle_enable: bool = True,
    keys: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Apply tuning parameters to one axis.

    Many A6 C00/C01 SDOs prefer the servo disabled. When cycle_enable is True:
      1. notes whether the machine was ON
      2. turns machine OFF if needed and waits for cia402 enable to drop
      3. writes SDOs with per-key retry/verify (continues after individual fails)
      4. restores machine ON if it was ON before
    """
    was_on = machine_is_on() if cycle_enable else False
    disabled_here = False
    try:
        if cycle_enable and was_on:
            set_machine_enabled(False)
            disabled_here = True
            if not wait_for_axis_disabled(axis, timeout_s=5.0):
                LOG.warning(
                    "axis %s enable still TRUE after machine OFF — writing anyway",
                    axis,
                )
            else:
                time.sleep(0.1)

        result = write_axis_sdos(axis, params, keys=keys)

        if cycle_enable and was_on:
            set_machine_enabled(True)
            disabled_here = False

        return {
            "axis": axis,
            "slave": AXES[axis]["slave"],
            "cycled_enable": bool(cycle_enable and was_on),
            "machine_on": machine_is_on() if cycle_enable else was_on,
            "written_keys": result["written"],
            "failed_keys": result["failed"],
            "skipped_keys": result["skipped"],
        }
    except Exception:
        if disabled_here and was_on:
            try:
                set_machine_enabled(True)
            except Exception:
                pass
        raise


def format_params_summary(params: AxisTuneParams, axis: str = "X") -> str:
    """Short human summary of live / baseline values for the UI."""
    unit = axis_unit(axis)
    if "adaptive_notch" in params.values:
        notch = NOTCH_LABELS.get(params.adaptive_notch, str(params.adaptive_notch))
    else:
        notch = "?"
    if "manual_mode" in params.values:
        mode_raw = int(params.get("manual_mode"))
        mode = {0: "manual", 1: "standard", 2: "positioning"}.get(
            mode_raw, f"mode{mode_raw}"
        )
    else:
        mode = "?"
    bits = []
    if "stiffness_level" in params.values:
        bits.append(f"C00.05={int(params.get('stiffness_level'))}")
    if "inertia_ratio_pct" in params.values:
        bits.append(f"C00.06={params.inertia_ratio_pct:.0f}%")
    if "pos_gain_rad_s" in params.values:
        bits.append(f"C01.00={params.pos_gain_rad_s:.1f} rad/s")
    if "speed_gain_hz" in params.values:
        bits.append(f"C01.01={params.speed_gain_hz:.1f} Hz")
    if "integral_ms" in params.values:
        bits.append(f"C01.02={params.integral_ms:.2f} ms")
    bits.append(f"notch={notch}")
    if "following_error" in params.values:
        bits.append(f"6065={params.following_error:.3f} {unit}")
    bits.append(f"({mode})")
    return "  ".join(bits)


def preset_dir(axis: str) -> str:
    return os.path.join(preset_root(), axis)


def preset_path(axis: str, name: str) -> str:
    safe = _sanitize_name(name)
    return os.path.join(preset_dir(axis), f"{safe}.json")


def list_presets(axis: str) -> List[str]:
    folder = preset_dir(axis)
    if not os.path.isdir(folder):
        return []
    names = []
    for entry in sorted(os.listdir(folder)):
        if entry.endswith(".json"):
            names.append(entry[:-5])
    return names


def save_preset(axis: str, name: str, params: AxisTuneParams, notes: str = "") -> str:
    os.makedirs(preset_dir(axis), exist_ok=True)
    safe = _sanitize_name(name)
    preset = AxisPreset(name=safe, axis=axis, params=params, notes=notes)
    path = preset_path(axis, safe)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(preset.to_dict(), handle, indent=2)
        handle.write("\n")
    return path


def load_preset(axis: str, name: str) -> AxisPreset:
    path = preset_path(axis, name)
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    # Do not fill missing preset keys with catalog defaults — APPLY must not
    # invent values for keys the preset never stored.
    params = AxisTuneParams.from_dict(data.get("params", {}), fill_defaults=False)
    preset = AxisPreset(
        name=data["name"],
        axis=data["axis"],
        created=data.get("created", _utc_now()),
        notes=data.get("notes", ""),
        params=params,
    )
    if preset.axis != axis:
        raise ValueError(f"preset {name!r} is for axis {preset.axis}, not {axis}")
    return preset


def delete_preset(axis: str, name: str) -> None:
    path = preset_path(axis, name)
    if os.path.isfile(path):
        os.remove(path)
