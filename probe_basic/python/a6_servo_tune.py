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
SDO_GAIN_SW_MODE = (0x2001, 0x39)  # C01.38
SDO_GAIN_SW_TIME = (0x2001, 0x3A)  # C01.39, 0.1 ms
SDO_GAIN_SW_THRESH = (0x2001, 0x3B)  # C01.3A
SDO_GAIN_SW_WIDTH = (0x2001, 0x3C)  # C01.3B
SDO_FOLLOWING_ERROR = (0x6065, 0x00)
SDO_FOLLOWING_ERROR_TIME = (0x6066, 0x00)

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
        "group": "Advanced",
        "sdo": SDO_ADAPTIVE_NOTCH,
        "bits": 16,
        "scale": 1.0,
        "unit": "{0..4}",
        "min": 0,
        "max": 4,
        "default": 1,
        "decimals": 0,
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
        out["manual_mode"] = float(self.values.get("manual_mode", 0.0))
        out["manual_mode_bool"] = self.manual_mode
        return out

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AxisTuneParams":
        return cls(values=cls._coerce_values(data))

    def copy(self) -> "AxisTuneParams":
        return AxisTuneParams(values=dict(self.values))

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
            params=AxisTuneParams.from_dict(data.get("params", {})),
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


def hal_getp(pin: str) -> float:
    """Read a HAL pin via halcmd getp; NaN on failure."""
    try:
        output = subprocess.check_output(
            ["halcmd", "getp", pin],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return float(output.strip())
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError):
        return float("nan")


def read_drive_ferr(axis: str) -> Tuple[float, float]:
    """Return (counts, mm_or_deg) for live 60F4 following error."""
    counts = hal_getp(drive_ferr_counts_halpin(axis))
    scaled = hal_getp(drive_ferr_halpin(axis))
    if scaled != scaled and counts == counts:
        scaled = counts_to_unit(axis, counts)
    if counts != counts and scaled == scaled:
        counts = float(unit_to_counts(axis, scaled))
    return counts, scaled


def read_axis_params(axis: str) -> AxisTuneParams:
    """Upload catalog SDOs; soft-fail individual entries to defaults."""
    slave = AXES[axis]["slave"]
    values = default_param_values()
    errors: List[str] = []
    for defn in PARAM_DEFS:
        key = defn["key"]
        try:
            index, sub = defn["sdo"]
            if defn["bits"] == 32:
                raw = ethercat_upload_u32(slave, index, sub)
            else:
                raw = ethercat_upload_u16(slave, index, sub)
            values[key] = _raw_to_display(defn, raw, axis)
        except Exception as exc:
            errors.append(f"{key}: {exc}")
            values[key] = float(defn["default"])
    if errors:
        LOG.warning(
            "partial SDO read on axis %s (%d errors): %s",
            axis,
            len(errors),
            "; ".join(errors[:5]),
        )
    return AxisTuneParams(values=values)


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


def write_axis_sdos(axis: str, params: AxisTuneParams) -> None:
    """Write drive SDOs from the param catalog. Call with motors disabled for C00/C01."""
    slave = AXES[axis]["slave"]
    for defn in PARAM_DEFS:
        key = defn["key"]
        value = params.get(key)
        raw = _display_to_raw(defn, value, axis)
        index, sub = defn["sdo"]
        if defn["bits"] == 32:
            ethercat_download_u32(slave, index, sub, raw)
        else:
            scale = defn["scale"]
            if scale != "axis_unit":
                scale_f = float(scale)
                lo = int(round(float(defn["min"]) / scale_f))
                hi = int(round(float(defn["max"]) / scale_f))
                raw = max(lo, min(hi, raw))
            ethercat_download_u16(slave, index, sub, raw)


def apply_axis_params(
    axis: str,
    params: AxisTuneParams,
    *,
    cycle_enable: bool = True,
) -> Dict[str, Any]:
    """
    Apply tuning parameters to one axis.

    Many A6 C00/C01 SDOs reject writes while the servo is enabled. When
    cycle_enable is True (default), this:
      1. notes whether the machine was ON
      2. turns machine OFF (disables amps) if needed
      3. writes SDOs
      4. restores machine ON if it was ON before

    Returns a small status dict for the UI.
    """
    was_on = machine_is_on() if cycle_enable else False
    disabled_here = False
    try:
        if cycle_enable and was_on:
            set_machine_enabled(False)
            disabled_here = True
            # Brief settle so drives leave Operation Enabled before SDO writes.
            time.sleep(0.25)

        write_axis_sdos(axis, params)

        if cycle_enable and was_on:
            set_machine_enabled(True)
            disabled_here = False

        return {
            "axis": axis,
            "slave": AXES[axis]["slave"],
            "cycled_enable": bool(cycle_enable and was_on),
            "machine_on": machine_is_on() if cycle_enable else was_on,
        }
    except Exception:
        # Best-effort restore if we disabled the machine for this apply.
        if disabled_here and was_on:
            try:
                set_machine_enabled(True)
            except Exception:
                pass
        raise


def format_params_summary(params: AxisTuneParams, axis: str = "X") -> str:
    """Short human summary of live / baseline values for the UI."""
    unit = axis_unit(axis)
    notch = NOTCH_LABELS.get(params.adaptive_notch, str(params.adaptive_notch))
    mode_raw = int(params.get("manual_mode"))
    mode = {0: "manual", 1: "standard", 2: "positioning"}.get(
        mode_raw, f"mode{mode_raw}"
    )
    return (
        f"C00.05={int(params.get('stiffness_level'))}  "
        f"C00.06={params.inertia_ratio_pct:.0f}%  "
        f"C01.00={params.pos_gain_rad_s:.1f} rad/s  "
        f"C01.01={params.speed_gain_hz:.1f} Hz  "
        f"C01.02={params.integral_ms:.2f} ms  "
        f"notch={notch}  "
        f"6065={params.following_error:.3f} {unit}  "
        f"({mode})"
    )


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
        preset = AxisPreset.from_dict(json.load(handle))
    if preset.axis != axis:
        raise ValueError(f"preset {name!r} is for axis {preset.axis}, not {axis}")
    return preset


def delete_preset(axis: str, name: str) -> None:
    path = preset_path(axis, name)
    if os.path.isfile(path):
        os.remove(path)
