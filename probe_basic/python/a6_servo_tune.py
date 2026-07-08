"""A6-EC servo tuning: SDO read/write, HAL ferr-lag, per-axis JSON presets."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

AXES: Dict[str, Dict[str, Any]] = {
    "X": {"joint": 0, "slave": 0, "linear": True, "scale": 13107.2},
    "Y": {"joint": 1, "slave": 1, "linear": True, "scale": 13107.2},
    "Z": {"joint": 2, "slave": 2, "linear": True, "scale": 13107.2},
    "A": {"joint": 3, "slave": 3, "linear": False, "scale": 364.088888889},
}

AXIS_ORDER = ("X", "Y", "Z", "A")

# EtherCAT object dictionary (A6 panel param mapping).
SDO_MANUAL_MODE = (0x2000, 0x05)  # C00.04
SDO_INERTIA_RATIO = (0x2000, 0x07)  # C00.06, %
SDO_POS_GAIN = (0x2001, 0x01)  # C01.00, 0.1 rad/s
SDO_SPEED_GAIN = (0x2001, 0x02)  # C01.01, 0.1 Hz
SDO_INTEGRAL = (0x2001, 0x03)  # C01.02, 0.01 ms
SDO_ADAPTIVE_NOTCH = (0x2001, 0x31)  # C01.30
SDO_FOLLOWING_ERROR = (0x6065, 0x00)

NOTCH_LABELS = {
    0: "Off",
    1: "Adaptive (once)",
    2: "Adaptive (persistent)",
    3: "Reset notch params",
    4: "Resonance test only",
}


def repo_root() -> str:
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
    )


def preset_root() -> str:
    return os.path.join(repo_root(), "config", "tuning", "presets")


def _sanitize_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", (value or "").strip())
    return cleaned.strip("_") or "preset"


def hal_getp(pin: str) -> float:
    try:
        out = subprocess.check_output(
            ["halcmd", "getp", pin],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return float(out.strip())
    except (subprocess.CalledProcessError, ValueError):
        return float("nan")


def hal_setp(pin: str, value: float) -> None:
    subprocess.check_call(
        ["halcmd", "setp", pin, str(value)],
        stderr=subprocess.DEVNULL,
    )


def ferr_lag_halpin(axis: str) -> str:
    joint = AXES[axis]["joint"]
    return f"ferr-lag.{joint}.value"


@dataclass
class AxisTuneParams:
    """Human-friendly tuning values for one axis."""

    inertia_ratio_pct: float = 100.0
    pos_gain_rad_s: float = 30.0
    speed_gain_hz: float = 20.0
    integral_ms: float = 31.84
    adaptive_notch: int = 1
    manual_mode: bool = True
    ferr_lag_ms: float = 2.0
    following_error: float = 0.1  # mm for XYZ, deg for A

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AxisTuneParams":
        return cls(
            inertia_ratio_pct=float(data.get("inertia_ratio_pct", 100.0)),
            pos_gain_rad_s=float(data.get("pos_gain_rad_s", 30.0)),
            speed_gain_hz=float(data.get("speed_gain_hz", 20.0)),
            integral_ms=float(data.get("integral_ms", 31.84)),
            adaptive_notch=int(data.get("adaptive_notch", 1)),
            manual_mode=bool(data.get("manual_mode", True)),
            ferr_lag_ms=float(data.get("ferr_lag_ms", 2.0)),
            following_error=float(data.get("following_error", 0.1)),
        )

    def pos_gain_raw(self) -> int:
        return max(1, min(30000, int(round(self.pos_gain_rad_s * 10.0))))

    def speed_gain_raw(self) -> int:
        return max(1, min(20000, int(round(self.speed_gain_hz * 10.0))))

    def integral_raw(self) -> int:
        return max(15, min(51200, int(round(self.integral_ms * 100.0))))

    def inertia_raw(self) -> int:
        return max(0, min(12000, int(round(self.inertia_ratio_pct))))

    def following_error_counts(self, axis: str) -> int:
        scale = float(AXES[axis]["scale"])
        return max(1, int(round(self.following_error * scale)))

    def ferr_lag_sec(self) -> float:
        return max(0.0, self.ferr_lag_ms / 1000.0)


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
    out = _run_ethercat(
        [
            "upload",
            "-p",
            str(slave),
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
            f"0x{index:04X}",
            str(subindex),
            str(int(value) & 0xFFFFFFFF),
        ]
    )


def read_axis_params(axis: str) -> AxisTuneParams:
    slave = AXES[axis]["slave"]
    scale = float(AXES[axis]["scale"])
    manual = ethercat_upload_u16(slave, *SDO_MANUAL_MODE)
    inertia = ethercat_upload_u16(slave, *SDO_INERTIA_RATIO)
    pos_raw = ethercat_upload_u16(slave, *SDO_POS_GAIN)
    spd_raw = ethercat_upload_u16(slave, *SDO_SPEED_GAIN)
    int_raw = ethercat_upload_u16(slave, *SDO_INTEGRAL)
    notch = ethercat_upload_u16(slave, *SDO_ADAPTIVE_NOTCH)
    fe_counts = ethercat_upload_u32(slave, *SDO_FOLLOWING_ERROR)
    lag_ms = hal_getp(ferr_lag_halpin(axis)) * 1000.0
    return AxisTuneParams(
        manual_mode=(manual == 0),
        inertia_ratio_pct=float(inertia),
        pos_gain_rad_s=pos_raw / 10.0,
        speed_gain_hz=spd_raw / 10.0,
        integral_ms=int_raw / 100.0,
        adaptive_notch=int(notch),
        ferr_lag_ms=lag_ms if lag_ms == lag_ms else 2.0,
        following_error=fe_counts / scale,
    )


def apply_axis_params(axis: str, params: AxisTuneParams) -> None:
    slave = AXES[axis]["slave"]
    manual = 0 if params.manual_mode else 1
    ethercat_download_u16(slave, *SDO_MANUAL_MODE, manual)
    ethercat_download_u16(slave, *SDO_INERTIA_RATIO, params.inertia_raw())
    ethercat_download_u16(slave, *SDO_POS_GAIN, params.pos_gain_raw())
    ethercat_download_u16(slave, *SDO_SPEED_GAIN, params.speed_gain_raw())
    ethercat_download_u16(slave, *SDO_INTEGRAL, params.integral_raw())
    ethercat_download_u16(slave, *SDO_ADAPTIVE_NOTCH, params.adaptive_notch)
    ethercat_download_u32(
        slave,
        *SDO_FOLLOWING_ERROR,
        params.following_error_counts(axis),
    )
    hal_setp(ferr_lag_halpin(axis), params.ferr_lag_sec())


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
