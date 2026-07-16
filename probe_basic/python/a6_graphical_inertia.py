"""Graphical inertia identification (Yaskawa Sigma II Graphical Analysis) for A6-EC.

Runs a trapezoidal move under LinuxCNC CSP, samples drive torque (6077) and
velocity (606C), then estimates load/motor inertia ratio for C00.06.

Primary estimator (v0.6) matches the Sigma II Parameter Calculator worksheet:

    T_a = T_p − T_f                 (accel peak − cruise friction)
    α   = Δω / Δt                   (fixed mid-ramp RPM band — not torque-gated)
    J_L = T_a / α − J_M
    ratio% = 100 * J_L / J_M        (→ C00.06, like Pn103)

Hardening vs v0.5:
  * Always clamp for a trusted write (fixed Torque limit, or probe→Pn402 flatten).
  * α from a fixed 25–75% peak-RPM band (torque only validates, does not pick Δt).
  * Cruise Tf required for quality=good (triangle fallback → marginal).
  * Reject legs that do not track the clamp / lack a usable α band.

C00.06 is written only when quality is ``good``. See
docs/GRAPHICAL_INERTIA_TUNE.md. Separate from F30.10 and one-click gains.
"""

from __future__ import annotations

import json
import logging
import math
import os
import threading
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from a6_servo_tune import (
    AXES,
    AxisTuneParams,
    apply_axis_params,
    axis_unit,
    ethercat_download_u16,
    ethercat_upload_u16,
    hal_getp,
    hal_setp,
    machine_is_on,
    read_axis_params,
    read_drive_torque,
    read_drive_velocity,
)

# CiA 402 torque limits (0.1% rated torque per count). Optional — not all
# firmware exposes every object; we probe and soft-skip.
SDO_MAX_TORQUE = (0x6072, 0x00)
SDO_TORQUE_LIMIT_POS = (0x60E0, 0x00)
SDO_TORQUE_LIMIT_NEG = (0x60E1, 0x00)

try:
    import linuxcnc
except ImportError:  # pragma: no cover
    linuxcnc = None  # type: ignore

LOG = logging.getLogger(__name__)
ENGINE_VERSION = "0.6.0"

# Accel windows shorter than this are unusable for measured α on A6 (606C
# stepping). The Sigma II example used ~3 ms; we keep a longer floor here.
MIN_ACCEL_S = 0.080
MIN_DECEL_S = 0.070
MIN_CRUISE_S = 0.040
# Target ramp length for ID moves. Sized so the fixed 25–75% α band is
# ≥ ~90 ms (0.5 * PREFERRED_ACCEL_S) with margin above MIN_ACCEL_S.
PREFERRED_ACCEL_S = 0.180
# α is measured only inside this fraction-of-peak-RPM band (fixed cursors).
ALPHA_BAND_LO = 0.25
ALPHA_BAND_HI = 0.75
MIN_ID_ACCEL_UNIT_S2 = 80.0
# Soft clamp — very high F still works, but PDO stepping gets worse.
MAX_ID_FEED = 10000.0
# Below this on linear axes, inertial torque is often < ~4% rated on a
# ~180 ms ramp and the estimate becomes noise-dominated.
MIN_ID_FEED_LINEAR = 5000.0
# Default linear ID recipe (stroke leaves room for accel+cruise+decel).
DEFAULT_LINEAR_STROKE_MM = 50.0
DEFAULT_LINEAR_FEED = 8000.0
# Pair ratios must agree within this relative span for quality=good.
MAX_LEG_RATIO_SPAN = 0.35
MIN_TA_PCT = 4.0
# Sanity band for a "good" write (outside → marginal, no C00.06 write).
MIN_RATIO_GOOD = 30.0
MAX_RATIO_GOOD = 500.0
# Accel torque relative spread above this → not flat enough for good.
FLATNESS_CV_MAX = 0.18
# When clamped, |mean(T) − limit| / limit above this → not tracking clamp.
LIMIT_TRACK_TOL = 0.20
# Auto-flatten sets limit to this fraction of unconstrained peak (above Tf).
AUTO_FLATTEN_FRAC = 0.90
AUTO_FLATTEN_MIN_MARGIN_PCT = 6.0

# Ballscrew / rotary geometry on this machine (matches INI SCALE comments).
MM_PER_MOTOR_REV = 10.0
DEG_PER_MOTOR_REV = 360.0
ENCODER_COUNTS_PER_REV = 131072.0

DEFAULT_SETTINGS_NAME = "inertia_settings.json"


class GraphicalInertiaError(RuntimeError):
    pass


class GraphicalInertiaCancelled(RuntimeError):
    pass


def default_journal_root() -> str:
    here = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return os.path.join(here, "logs", "tuning", "graphical_inertia")


def default_settings_path() -> str:
    here = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return os.path.join(here, "config", "tuning", DEFAULT_SETTINGS_NAME)


def unit_per_rev(axis: str) -> float:
    return MM_PER_MOTOR_REV if AXES[axis]["linear"] else DEG_PER_MOTOR_REV


def unit_per_min_to_rpm(axis: str, unit_per_min: float) -> float:
    return float(unit_per_min) / unit_per_rev(axis)


def rpm_to_rad_s(rpm: float) -> float:
    return float(rpm) * (2.0 * math.pi / 60.0)


def yaskawa_worksheet_ratio(
    *,
    tp_pct: float,
    tf_pct: float,
    delta_v_rpm: float,
    delta_t_ms: float,
    rated_torque_nm: float,
    motor_inertia_kgm2: float,
) -> Dict[str, float]:
    """Exact Sigma II Parameter Calculator Inertia-sheet formulas.

    Matches BIFF formulas:
      Ta_Nm = (Tp% − Tf%) / 100 * Trated
      α     = ΔV_rpm * 2π / 60 / (Δt_ms / 1000)
      JL    = Ta_Nm / α − JM
      Pn103 = 100 * JL / JM
    """
    ta_nm = ((float(tp_pct) - float(tf_pct)) / 100.0) * float(rated_torque_nm)
    alpha = rpm_to_rad_s(float(delta_v_rpm)) / (float(delta_t_ms) / 1000.0)
    if alpha <= 0:
        raise GraphicalInertiaError("Δt/ΔV produce non-positive α")
    j_total = abs(ta_nm) / alpha
    j_load = j_total - float(motor_inertia_kgm2)
    ratio = 100.0 * j_load / float(motor_inertia_kgm2)
    return {
        "ta_nm": float(ta_nm),
        "alpha_rad_s2": float(alpha),
        "j_load_kgm2": float(j_load),
        "j_total_kgm2": float(j_total),
        "ratio_pct": float(ratio),  # Pn103
    }


@dataclass
class AxisInertiaSettings:
    """Per-axis knobs shown on the INERTIA panel."""

    motor_inertia_kgm2: float = 0.0  # required > 0
    rated_torque_nm: float = 0.0  # required > 0
    stroke: float = 40.0  # mm or deg
    feed: float = 8000.0  # unit/min (G1 F)
    cycles: int = 1
    settle_s: float = 0.3
    # Fixed CiA torque clamp for the ID move (0 = probe then always flatten).
    # When >0, that limit IS Tp (workbook). Trusted writes require a clamp.
    torque_limit_pct: float = 0.0
    # When torque_limit_pct==0, always run probe→Pn402-style flatten (Sigma II).
    # Set False only for debug; quality cannot be good without a clamp.
    auto_flatten: bool = True
    write_to_drive: bool = True
    # Temporarily lower LinuxCNC ini.*.max_acceleration so the ID ramp is
    # long enough for the fixed α band (0 = auto from feed → ~PREFERRED_ACCEL_S).
    id_accel_unit_s2: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "motor_inertia_kgm2": self.motor_inertia_kgm2,
            "rated_torque_nm": self.rated_torque_nm,
            "stroke": self.stroke,
            "feed": self.feed,
            "cycles": self.cycles,
            "settle_s": self.settle_s,
            "torque_limit_pct": self.torque_limit_pct,
            "auto_flatten": self.auto_flatten,
            "write_to_drive": self.write_to_drive,
            "id_accel_unit_s2": self.id_accel_unit_s2,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AxisInertiaSettings":
        return cls(
            motor_inertia_kgm2=float(data.get("motor_inertia_kgm2", 0.0)),
            rated_torque_nm=float(data.get("rated_torque_nm", 0.0)),
            stroke=float(data.get("stroke", 40.0)),
            feed=float(data.get("feed", 8000.0)),
            cycles=max(1, int(data.get("cycles", 1))),
            settle_s=float(data.get("settle_s", 0.3)),
            torque_limit_pct=float(data.get("torque_limit_pct", 0.0)),
            auto_flatten=bool(data.get("auto_flatten", True)),
            write_to_drive=bool(data.get("write_to_drive", True)),
            id_accel_unit_s2=float(data.get("id_accel_unit_s2", 0.0)),
        )

    def validate(self) -> None:
        if self.motor_inertia_kgm2 <= 0:
            raise GraphicalInertiaError(
                "Motor rotor inertia (kg·m²) must be > 0 — enter the value "
                "from the motor datasheet / nameplate."
            )
        if self.rated_torque_nm <= 0:
            raise GraphicalInertiaError(
                "Rated torque (N·m) must be > 0 — enter the motor rated torque."
            )
        if self.stroke <= 0 or self.feed <= 0:
            raise GraphicalInertiaError("Stroke and feed must be > 0.")


def default_settings_for_axis(axis: str) -> AxisInertiaSettings:
    """Conservative motion defaults; motor constants left blank until filled."""
    if axis == "Y":
        # 30 mm @ F6000 / ~180 ms ramp → ~9 mm accel + cruise room for Tf.
        return AxisInertiaSettings(stroke=30.0, feed=6000.0)
    if axis == "Z":
        return AxisInertiaSettings(stroke=30.0, feed=5000.0)
    if axis == "A":
        return AxisInertiaSettings(stroke=90.0, feed=3600.0)
    # X recipe: F8000, 50 mm, ~180 ms ramp (fixed 25–75% α band ≥ ~90 ms).
    return AxisInertiaSettings(
        stroke=DEFAULT_LINEAR_STROKE_MM, feed=DEFAULT_LINEAR_FEED
    )


def load_all_settings(path: Optional[str] = None) -> Dict[str, AxisInertiaSettings]:
    path = path or default_settings_path()
    out = {a: default_settings_for_axis(a) for a in AXES}
    if not os.path.isfile(path):
        return out
    try:
        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle)
        axes = raw.get("axes", raw)
        for axis, data in axes.items():
            if axis in out and isinstance(data, dict):
                out[axis] = AxisInertiaSettings.from_dict(data)
    except Exception:
        LOG.exception("failed to load inertia settings from %s", path)
    return out


def save_all_settings(
    settings: Dict[str, AxisInertiaSettings], path: Optional[str] = None
) -> str:
    path = path or default_settings_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {
        "version": 1,
        "notes": (
            "Yaskawa Sigma II Graphical Analysis (Tp−Tf), engine v0.6. "
            "Motor inertia / rated torque are required datasheet values. "
            "Linear recipe: F8000 / ~50 mm / ~180 ms ramp (auto id_accel). "
            "Always clamps (fixed Torque limit, or probe→flatten). "
            "α from fixed 25–75% RPM band; cruise Tf required for good writes."
        ),
        "axes": {a: settings[a].to_dict() for a in sorted(settings)},
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)
    return path


@dataclass
class InertiaEstimate:
    ratio_pct: float
    j_load_kgm2: float
    j_total_kgm2: float
    t_peak_pct: float
    t_friction_pct: float
    t_accel_nm: float
    alpha_rad_s2: float
    delta_rpm: float
    delta_t_s: float
    quality: str  # good | marginal | bad
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ratio_pct": self.ratio_pct,
            "j_load_kgm2": self.j_load_kgm2,
            "j_total_kgm2": self.j_total_kgm2,
            "t_peak_pct": self.t_peak_pct,
            "t_friction_pct": self.t_friction_pct,
            "t_accel_nm": self.t_accel_nm,
            "alpha_rad_s2": self.alpha_rad_s2,
            "delta_rpm": self.delta_rpm,
            "delta_t_s": self.delta_t_s,
            "quality": self.quality,
            "notes": list(self.notes),
        }


def _median(values: Sequence[float]) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return 0.5 * (ordered[mid - 1] + ordered[mid])


def _mean(values: Sequence[float]) -> float:
    if not values:
        return float("nan")
    return float(sum(values) / len(values))


def _find_rest_to_cruise_legs(
    rpm: Sequence[float], peak_rpm: float, dt: float
) -> List[Tuple[int, int, int]]:
    """Return (i_lo, i_hi, sign) for each rest→cruise rising edge."""
    n = len(rpm)
    abs_rpm = [abs(r) for r in rpm]
    lo_thr = 0.08 * peak_rpm
    hi_thr = 0.90 * peak_rpm
    legs: List[Tuple[int, int, int]] = []
    i = 0
    while i < n:
        if abs_rpm[i] > lo_thr:
            i += 1
            continue
        j = i
        while j + 1 < n and abs_rpm[j + 1] <= lo_thr:
            j += 1
        k = j + 1
        while k < n and abs_rpm[k] < hi_thr:
            k += 1
        if k >= n:
            break
        if abs_rpm[k] - abs_rpm[j] < 0.5 * peak_rpm:
            i = k + 1
            continue
        sign = 1 if rpm[k] >= 0.0 else -1
        legs.append((j, k, sign))
        i = k + 1
        while i < n and abs_rpm[i] > lo_thr:
            i += 1
    return legs


def _find_cruise_to_rest_legs(
    rpm: Sequence[float], peak_rpm: float, dt: float
) -> List[Tuple[int, int, int]]:
    """Return (i_hi, i_lo, sign) for each cruise→rest falling edge.

    i_hi = last sample still near cruise, i_lo = first sample near rest.
    """
    n = len(rpm)
    abs_rpm = [abs(r) for r in rpm]
    lo_thr = 0.08 * peak_rpm
    hi_thr = 0.90 * peak_rpm
    legs: List[Tuple[int, int, int]] = []
    i = 0
    while i < n:
        if abs_rpm[i] < hi_thr:
            i += 1
            continue
        j = i
        while j + 1 < n and abs_rpm[j + 1] >= 0.85 * peak_rpm:
            j += 1
        k = j + 1
        while k < n and abs_rpm[k] > lo_thr:
            k += 1
        if k >= n:
            break
        if abs_rpm[j] - abs_rpm[k] < 0.5 * peak_rpm:
            i = k + 1
            continue
        sign = 1 if rpm[j] >= 0.0 else -1
        legs.append((j, k, sign))
        i = k + 1
    return legs


def unit_accel_to_alpha(axis: str, accel_unit_s2: float) -> float:
    """Linear (mm/s²) or rotary (deg/s²) trajectory accel → motor α (rad/s²)."""
    return float(accel_unit_s2) / unit_per_rev(axis) * (2.0 * math.pi)


def target_id_accel(feed_unit_per_min: float, ramp_s: float = PREFERRED_ACCEL_S) -> float:
    """Trajectory accel that makes 0→feed take ``ramp_s`` seconds."""
    v = abs(float(feed_unit_per_min)) / 60.0
    ramp = max(float(ramp_s), MIN_ACCEL_S)
    return max(MIN_ID_ACCEL_UNIT_S2, v / ramp)


def _ini_accel_pins(axis: str) -> List[str]:
    joint = int(AXES[axis]["joint"])
    letter = axis.lower()
    return [f"ini.{joint}.max_acceleration", f"ini.{letter}.max_acceleration"]


def read_ini_accel(axis: str) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for pin in _ini_accel_pins(axis):
        val = hal_getp(pin)
        if val == val and val > 0:
            out[pin] = float(val)
    return out


def apply_ini_accel(axis: str, accel_unit_s2: float) -> Dict[str, float]:
    previous = read_ini_accel(axis)
    if not previous:
        previous = {}
    written = False
    for pin in _ini_accel_pins(axis):
        try:
            if pin not in previous:
                cur = hal_getp(pin)
                if cur == cur and cur > 0:
                    previous[pin] = float(cur)
            hal_setp(pin, float(accel_unit_s2))
            written = True
        except Exception:
            LOG.debug("ini accel setp failed for %s", pin, exc_info=True)
    if not written:
        raise GraphicalInertiaError(
            "could not set ini.*.max_acceleration — is LinuxCNC running?"
        )
    return previous


def restore_ini_accel(previous: Optional[Dict[str, float]]) -> None:
    if not previous:
        return
    for pin, value in previous.items():
        try:
            hal_setp(pin, float(value))
        except Exception:
            LOG.exception("restore ini accel failed for %s", pin)


def _midband_indices(
    rpm: Sequence[float], i0: int, i1: int, peak_rpm: float
) -> List[int]:
    """20–80% band for torque plateau helpers; soft-falls back to full edge."""
    lo = min(i0, i1)
    hi = max(i0, i1)
    band = [
        i
        for i in range(lo, hi + 1)
        if 0.20 * peak_rpm <= abs(rpm[i]) <= 0.80 * peak_rpm
    ]
    if len(band) < 4:
        band = list(range(lo, hi + 1))
    return band


def _rpm_band_indices(
    rpm: Sequence[float],
    i0: int,
    i1: int,
    peak_rpm: float,
    lo_frac: float,
    hi_frac: float,
) -> List[int]:
    lo = min(i0, i1)
    hi = max(i0, i1)
    band = [
        i
        for i in range(lo, hi + 1)
        if lo_frac * peak_rpm <= abs(rpm[i]) <= hi_frac * peak_rpm
    ]
    if len(band) < 4:
        raise GraphicalInertiaError(
            f"RPM band {lo_frac:.0%}–{hi_frac:.0%} of peak has <4 samples "
            f"on accel edge — lengthen ID ramp / raise feed"
        )
    return band


def _alpha_band_indices(
    rpm: Sequence[float], i0: int, i1: int, peak_rpm: float
) -> List[int]:
    """Fixed mid-ramp cursors for α (independent of torque shape)."""
    return _rpm_band_indices(
        rpm, i0, i1, peak_rpm, ALPHA_BAND_LO, ALPHA_BAND_HI
    )


def _mean_proj_torque(
    tq: Sequence[float], indices: Sequence[int], sign: int
) -> float:
    if not indices:
        return float("nan")
    return _mean([float(tq[i]) * float(sign) for i in indices])


def _stdev(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    mu = _mean(values)
    return math.sqrt(_mean([(v - mu) ** 2 for v in values]))


def _constant_torque_window(
    tq: Sequence[float],
    rpm: Sequence[float],
    i0: int,
    i1: int,
    peak_rpm: float,
    sign: int,
    *,
    rel_tol: float = 0.15,
) -> Tuple[List[int], float, float]:
    """Indices inside accel where projected torque is near the plateau.

    Sigma II Techniques: place vertical cursors only while torque is constant.
    Returns (indices, plateau_torque_proj, coeff_of_variation).
    """
    band = _midband_indices(rpm, i0, i1, peak_rpm)
    if not band:
        raise GraphicalInertiaError("no mid-band samples on accel edge")
    proj = [float(tq[i]) * float(sign) for i in band]
    # Upper half of mid-band samples ≈ peak plateau (rejects soft start).
    ordered = sorted(proj)
    n_hi = max(2, len(ordered) // 2)
    plateau = _mean(ordered[-n_hi:])
    if plateau <= 0:
        raise GraphicalInertiaError("accel plateau torque ≤ 0 after projection")
    kept = [
        i
        for i, p in zip(band, proj)
        if abs(p - plateau) <= rel_tol * max(abs(plateau), 1.0)
    ]
    if len(kept) < 4:
        kept = band
        plateau = _mean(proj)
    cv = _stdev([float(tq[i]) * float(sign) for i in kept]) / max(abs(plateau), 1e-6)
    return kept, float(plateau), float(cv)


def _cruise_friction_pct(
    tq: Sequence[float],
    rpm: Sequence[float],
    a1: int,
    d0: int,
    peak_rpm: float,
    sign: int,
    dt: float,
) -> Optional[float]:
    """Trapezoid cruise Tf: mean projected torque while near peak speed."""
    lo = a1
    hi = d0
    if hi <= lo + 2:
        return None
    cruise = [
        i
        for i in range(lo, hi + 1)
        if abs(rpm[i]) >= 0.85 * peak_rpm
    ]
    if len(cruise) * dt < MIN_CRUISE_S:
        return None
    # Drop first/last 10% to avoid accel/decel bleed.
    trim = max(1, len(cruise) // 10)
    core = cruise[trim:-trim] if len(cruise) > 2 * trim + 2 else cruise
    return _mean_proj_torque(tq, core, sign)


def _triangle_friction_pct(t_acc: float, t_dec: float) -> float:
    """Sigma II note: Tf = (T_acc + T_dec) / 2 (signed; decel may be negative)."""
    return 0.5 * (float(t_acc) + float(t_dec))


def _estimate_leg(
    tq: Sequence[float],
    rpm: Sequence[float],
    acc: Tuple[int, int, int],
    dec: Optional[Tuple[int, int, int]],
    peak_rpm: float,
    dt: float,
    motor_inertia_kgm2: float,
    rated_torque_nm: float,
    *,
    torque_limit_pct: Optional[float] = None,
) -> InertiaEstimate:
    """Yaskawa worksheet: Ta = Tp − Tf, α from fixed mid-ramp RPM band."""
    a0, a1, sign = acc
    alpha_idx = _alpha_band_indices(rpm, a0, a1, peak_rpm)
    i_lo, i_hi = alpha_idx[0], alpha_idx[-1]
    delta_t = max((i_hi - i_lo) * dt, dt)
    delta_rpm = abs(rpm[i_hi] - rpm[i_lo])
    if delta_t < MIN_ACCEL_S:
        raise GraphicalInertiaError(
            f"fixed α band ({ALPHA_BAND_LO:.0%}–{ALPHA_BAND_HI:.0%} peak) only "
            f"{delta_t * 1000:.0f} ms — need ≥{MIN_ACCEL_S * 1000:.0f} ms "
            f"(ID should stretch MAX_ACCELERATION toward "
            f"~{PREFERRED_ACCEL_S * 1000:.0f} ms)"
        )
    if delta_rpm < 5.0:
        raise GraphicalInertiaError("accel Δrpm too small inside fixed α band")

    proj_alpha = [float(tq[i]) * float(sign) for i in alpha_idx]
    mean_tq_alpha = _mean(proj_alpha)
    flat_cv = _stdev(proj_alpha) / max(abs(mean_tq_alpha), 1e-6)
    clamped = torque_limit_pct is not None and torque_limit_pct > 0

    # Techniques: "The torque limit IS the peak torque" when Pn402 is used.
    if clamped:
        t_peak = float(torque_limit_pct)
        notes_peak = f"Tp={t_peak:.1f}% (torque limit)"
        track_err = abs(mean_tq_alpha - t_peak) / max(abs(t_peak), 1.0)
    else:
        # Probe-only: upper half of α-band samples ≈ unconstrained peak.
        ordered = sorted(proj_alpha)
        n_hi = max(2, len(ordered) // 2)
        t_peak = _mean(ordered[-n_hi:])
        if t_peak <= 0:
            raise GraphicalInertiaError(
                "accel α-band torque ≤ 0 after projection"
            )
        notes_peak = f"Tp={t_peak:.1f}% (α-band upper half, unclamped probe)"
        track_err = 0.0

    t_dec_proj = float("nan")
    if dec is not None:
        d0, d1, _ = dec
        try:
            _dec_idx, t_dec_proj, _ = _constant_torque_window(
                tq, rpm, d0, d1, peak_rpm, sign
            )
        except GraphicalInertiaError:
            # Soft CSP braking — fall back to directed lower-quartile feel.
            band = _midband_indices(rpm, d0, d1, peak_rpm)
            proj = sorted(float(tq[i]) * float(sign) for i in band)
            n = max(1, len(proj) // 4)
            t_dec_proj = _mean(proj[:n])

    tf_cruise = None
    if dec is not None:
        tf_cruise = _cruise_friction_pct(
            tq, rpm, a1, dec[0], peak_rpm, sign, dt
        )

    has_cruise = tf_cruise is not None
    if has_cruise:
        t_friction = float(tf_cruise)
        method = "trapezoid cruise Tf"
    elif t_dec_proj == t_dec_proj:  # not NaN
        t_friction = _triangle_friction_pct(t_peak, t_dec_proj)
        method = "triangle Tf=(Tacc+Tdec)/2"
    else:
        raise GraphicalInertiaError(
            "need cruise friction or a decel edge for Tf (Sigma II trapezoid/triangle)"
        )

    t_inertial_pct = t_peak - t_friction
    if t_inertial_pct < MIN_TA_PCT:
        raise GraphicalInertiaError(
            f"inertial torque too small (Ta={t_inertial_pct:.1f}% = "
            f"Tp {t_peak:.1f} − Tf {t_friction:.1f}) — raise feed "
            f"(prefer F{MIN_ID_FEED_LINEAR:.0f}–F{MAX_ID_FEED:.0f} on linear) "
            f"so Ta ≥ {MIN_TA_PCT:.0f}%"
        )

    alpha = rpm_to_rad_s(delta_rpm) / delta_t
    t_accel_nm = (t_inertial_pct / 100.0) * float(rated_torque_nm)
    j_total = abs(t_accel_nm) / alpha
    j_load = j_total - float(motor_inertia_kgm2)
    if j_load <= 0:
        raise GraphicalInertiaError(
            f"computed J_load ≤ 0 (J_total={j_total:.4e}, J_M={motor_inertia_kgm2:.4e})"
        )
    ratio_pct = 100.0 * j_load / float(motor_inertia_kgm2)
    notes = [
        f"Yaskawa {method}",
        notes_peak,
        f"Tf={t_friction:.1f}% Ta={t_inertial_pct:.1f}%",
        f"α={alpha:.0f} rad/s² over {delta_t * 1000:.0f} ms "
        f"(ΔV={delta_rpm:.0f} rpm in fixed "
        f"{ALPHA_BAND_LO:.0%}–{ALPHA_BAND_HI:.0%} RPM band)",
        f"α-band torque mean={mean_tq_alpha:.1f}% CV={flat_cv:.2f}",
    ]
    quality = "good"
    if not clamped:
        quality = "marginal"
        notes.append(
            "no torque clamp — probe-only estimate; flatten / set Torque limit "
            "required for a trusted C00.06 write"
        )
    else:
        if track_err > LIMIT_TRACK_TOL:
            quality = "marginal"
            notes.append(
                f"α-band torque mean {mean_tq_alpha:.1f}% not tracking limit "
                f"{t_peak:.1f}% (err={track_err * 100:.0f}% > "
                f"{LIMIT_TRACK_TOL * 100:.0f}%)"
            )
        if flat_cv > FLATNESS_CV_MAX:
            quality = "marginal"
            notes.append(
                f"accel torque not flat in α band (CV={flat_cv:.2f}) — "
                f"lower the clamp or lengthen the ramp"
            )
    if not has_cruise:
        quality = "marginal"
        notes.append(
            "no cruise Tf — triangle fallback not trusted for write "
            "(lengthen stroke / lower feed for a clear cruise)"
        )
    if delta_t < 0.85 * (PREFERRED_ACCEL_S * (ALPHA_BAND_HI - ALPHA_BAND_LO)):
        notes.append(
            f"α-band window {delta_t * 1000:.0f} ms "
            f"(target ~{PREFERRED_ACCEL_S * (ALPHA_BAND_HI - ALPHA_BAND_LO) * 1000:.0f} ms)"
        )
    if peak_rpm < 400.0:
        quality = "marginal"
        notes.append(
            f"peak only {peak_rpm:.0f} rpm — raise feed for SNR "
            f"(prefer ≥{MIN_ID_FEED_LINEAR:.0f} unit/min on linear)"
        )
    if ratio_pct < MIN_RATIO_GOOD or ratio_pct > MAX_RATIO_GOOD:
        quality = "marginal"
        notes.append(
            f"ratio {ratio_pct:.0f}% outside trusted band "
            f"[{MIN_RATIO_GOOD:.0f}, {MAX_RATIO_GOOD:.0f}]%"
        )
    if ratio_pct > 12000:
        notes.append("ratio > 12000% (C00.06 max) — will clamp on write")

    return InertiaEstimate(
        ratio_pct=float(ratio_pct),
        j_load_kgm2=float(j_load),
        j_total_kgm2=float(j_total),
        t_peak_pct=float(t_peak),
        t_friction_pct=float(t_friction),
        t_accel_nm=float(t_accel_nm),
        alpha_rad_s2=float(alpha),
        delta_rpm=float(delta_rpm),
        delta_t_s=float(delta_t),
        quality=quality,
        notes=notes,
    )


def analyze_torque_velocity(
    axis: str,
    torque_pct: Sequence[float],
    vel_unit_per_min: Sequence[float],
    sample_hz: float,
    motor_inertia_kgm2: float,
    rated_torque_nm: float,
    commanded_alpha_rad_s2: Optional[float] = None,
    *,
    torque_limit_pct: Optional[float] = None,
) -> InertiaEstimate:
    """Inertia ratio via Sigma II Graphical Analysis (Tp − Tf).

    ``commanded_alpha_rad_s2`` is accepted for journaling/compat; the ratio
    uses measured α inside the fixed mid-ramp RPM band.
    ``torque_limit_pct`` must be set for quality=``good`` (clamp IS Tp).
    """
    del commanded_alpha_rad_s2
    n = min(len(torque_pct), len(vel_unit_per_min))
    if n < 20:
        raise GraphicalInertiaError("not enough samples for inertia analysis")
    if sample_hz <= 0:
        raise GraphicalInertiaError("sample_hz must be > 0")
    if motor_inertia_kgm2 <= 0 or rated_torque_nm <= 0:
        raise GraphicalInertiaError("motor inertia and rated torque must be > 0")

    tq = [float(torque_pct[i]) for i in range(n)]
    vel = [float(vel_unit_per_min[i]) for i in range(n)]
    rpm = [unit_per_min_to_rpm(axis, v) for v in vel]
    dt = 1.0 / float(sample_hz)

    peak_rpm = max(abs(r) for r in rpm)
    if peak_rpm < 30.0:
        raise GraphicalInertiaError(
            f"peak speed only {peak_rpm:.1f} rpm — raise feed so cruise is clear "
            f"(prefer F{MIN_ID_FEED_LINEAR:.0f}–F{MAX_ID_FEED:.0f} on linear axes)."
        )

    acc_legs = _find_rest_to_cruise_legs(rpm, peak_rpm, dt)
    dec_legs = _find_cruise_to_rest_legs(rpm, peak_rpm, dt)
    if not acc_legs:
        raise GraphicalInertiaError(
            "need at least one accel edge — use a trapezoid/triangle with "
            "clear speed change."
        )

    estimates: List[InertiaEstimate] = []
    errors: List[str] = []
    for a0, a1, asign in acc_legs:
        candidates = [
            (d0, d1, dsign)
            for d0, d1, dsign in dec_legs
            if dsign == asign and d0 >= a1
        ]
        dec = candidates[0] if candidates else None
        try:
            estimates.append(
                _estimate_leg(
                    tq,
                    rpm,
                    (a0, a1, asign),
                    dec,
                    peak_rpm,
                    dt,
                    motor_inertia_kgm2,
                    rated_torque_nm,
                    torque_limit_pct=torque_limit_pct,
                )
            )
        except GraphicalInertiaError as exc:
            errors.append(str(exc))

    usable = [e for e in estimates if e.quality != "bad"]
    if not usable:
        usable = estimates
    if not usable:
        detail = "; ".join(errors[:3]) if errors else "no valid accel legs"
        raise GraphicalInertiaError(
            detail
            + f" — use F{MIN_ID_FEED_LINEAR:.0f}–F{MAX_ID_FEED:.0f}, "
            f"stroke with cruise, let ID stretch accel / auto-flatten."
        )

    ratios = sorted(e.ratio_pct for e in usable)
    mid_ratio = _median(ratios)
    best = min(usable, key=lambda e: abs(e.ratio_pct - mid_ratio))
    best.ratio_pct = float(mid_ratio)
    best.j_load_kgm2 = float(motor_inertia_kgm2) * mid_ratio / 100.0
    best.j_total_kgm2 = best.j_load_kgm2 + float(motor_inertia_kgm2)
    best.notes = list(best.notes)
    if len(usable) > 1:
        span = (ratios[-1] - ratios[0]) / max(abs(mid_ratio), 1.0)
        best.notes.append(
            f"median of {len(usable)} legs (range {ratios[0]:.0f}–{ratios[-1]:.0f}%)"
        )
        if span > MAX_LEG_RATIO_SPAN:
            best.quality = "marginal"
            best.notes.append(
                f"leg spread {span * 100:.0f}% > {MAX_LEG_RATIO_SPAN * 100:.0f}% "
                f"— re-run (F{MIN_ID_FEED_LINEAR:.0f}–F{MAX_ID_FEED:.0f}, cycles=1)"
            )
    order = {"good": 0, "marginal": 1, "bad": 2}
    worst = max(usable, key=lambda e: order.get(e.quality, 9))
    if order.get(worst.quality, 0) > order.get(best.quality, 0):
        best.quality = worst.quality
        for note in worst.notes:
            if note not in best.notes:
                best.notes.append(note)
    if mid_ratio < MIN_RATIO_GOOD or mid_ratio > MAX_RATIO_GOOD:
        best.quality = "marginal"
        note = (
            f"ratio {mid_ratio:.0f}% outside trusted band "
            f"[{MIN_RATIO_GOOD:.0f}, {MAX_RATIO_GOOD:.0f}]%"
        )
        if note not in best.notes:
            best.notes.append(note)
    if mid_ratio > 12000 and "ratio > 12000%" not in " ".join(best.notes):
        best.notes.append("ratio > 12000% (C00.06 max) — will clamp on write")
    return best


def suggest_flatten_limit_pct(estimate: InertiaEstimate) -> Optional[float]:
    """Pn402-style limit from a probe estimate: below Tp, above Tf + margin."""
    tp = float(estimate.t_peak_pct)
    tf = float(estimate.t_friction_pct)
    if tp <= tf + AUTO_FLATTEN_MIN_MARGIN_PCT:
        return None
    # Techniques: as high as possible while still flat; higher → more accurate.
    candidate = AUTO_FLATTEN_FRAC * tp
    floor = tf + AUTO_FLATTEN_MIN_MARGIN_PCT
    limit = max(floor, min(candidate, tp - 1.0))
    if limit <= tf + 1.0:
        return None
    return float(limit)


def probe_needs_flatten(estimate: InertiaEstimate) -> bool:
    """True when a probe pass should be followed by a clamped re-run.

    v0.6 always flattens when no fixed limit is set (not only when spiky).
    Kept for journaling / callers that want the old CV-based hint.
    """
    return True


def probe_was_spiky(estimate: InertiaEstimate) -> bool:
    """True when accel torque looked non-flat on the probe pass."""
    blob = " ".join(estimate.notes).lower()
    return "not flat" in blob or "unclamped probe" in blob


def _pct_to_cia_torque_raw(pct: float) -> int:
    """Percent of rated → CiA 0.1%-rated integer (100% → 1000)."""
    return max(1, min(3000, int(round(float(pct) * 10.0))))


def _cia_torque_raw_to_pct(raw: int) -> float:
    return float(raw) / 10.0


def read_cia_torque_limit_pct(slave: int) -> Optional[Dict[str, float]]:
    """Read 6072 / 60E0 / 60E1 when present. Returns None if none readable."""
    out: Dict[str, float] = {}
    for name, (index, sub) in (
        ("max", SDO_MAX_TORQUE),
        ("pos", SDO_TORQUE_LIMIT_POS),
        ("neg", SDO_TORQUE_LIMIT_NEG),
    ):
        try:
            out[name] = _cia_torque_raw_to_pct(ethercat_upload_u16(slave, index, sub))
        except Exception:
            LOG.debug("torque limit %s unread on slave %s", name, slave, exc_info=True)
    return out or None


def write_cia_torque_limit_pct(slave: int, pct: float) -> List[str]:
    """Write the same % to every readable CiA torque-limit object. Returns names written."""
    raw = _pct_to_cia_torque_raw(pct)
    written: List[str] = []
    for name, (index, sub) in (
        ("max", SDO_MAX_TORQUE),
        ("pos", SDO_TORQUE_LIMIT_POS),
        ("neg", SDO_TORQUE_LIMIT_NEG),
    ):
        try:
            ethercat_download_u16(slave, index, sub, raw)
            written.append(name)
        except Exception:
            LOG.debug(
                "torque limit %s write failed on slave %s", name, slave, exc_info=True
            )
    return written


def restore_cia_torque_limits(slave: int, previous: Dict[str, float]) -> None:
    for name, (index, sub) in (
        ("max", SDO_MAX_TORQUE),
        ("pos", SDO_TORQUE_LIMIT_POS),
        ("neg", SDO_TORQUE_LIMIT_NEG),
    ):
        if name not in previous:
            continue
        try:
            ethercat_download_u16(
                slave, index, sub, _pct_to_cia_torque_raw(previous[name])
            )
        except Exception:
            LOG.exception("restore torque limit %s failed on slave %s", name, slave)


@dataclass
class GraphicalInertiaResult:
    axis: str
    status: str  # ok | failed | cancelled | dry-run
    reason: str
    estimate: Optional[InertiaEstimate] = None
    written_ratio_pct: Optional[float] = None
    baseline_ratio_pct: Optional[float] = None
    journal_dir: Optional[str] = None

    def summary(self) -> str:
        bits = [f"{self.status}: {self.reason}"]
        if self.estimate is not None:
            bits.append(
                f"ratio={self.estimate.ratio_pct:.0f}% ({self.estimate.quality})"
            )
        if self.written_ratio_pct is not None:
            bits.append(f"wrote C00.06={self.written_ratio_pct:.0f}%")
        return " | ".join(bits)


class _Journal:
    def __init__(self, root: str, axis: str) -> None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.dir = os.path.join(root, f"{stamp}_{axis}")
        self._events: List[Dict[str, Any]] = []
        self._t0 = time.time()
        self._md: Optional[str] = None
        self._json: Optional[str] = None
        try:
            os.makedirs(self.dir, exist_ok=True)
            self._md = os.path.join(self.dir, "journal.md")
            self._json = os.path.join(self.dir, "journal.json")
            with open(self._md, "w", encoding="utf-8") as handle:
                handle.write(
                    f"# Graphical inertia tune — axis {axis}\n\n"
                    f"- started: {datetime.now().isoformat(timespec='seconds')}\n"
                    f"- engine: a6_graphical_inertia v{ENGINE_VERSION}\n\n"
                )
        except Exception:
            LOG.exception("graphical inertia journal init failed")

    def event(self, phase: str, kind: str, message: str, **data: Any) -> None:
        entry = {
            "t": round(time.time() - self._t0, 3),
            "phase": phase,
            "kind": kind,
            "message": message,
        }
        if data:
            entry["data"] = data
        self._events.append(entry)
        LOG.info("ginertia[%s/%s]: %s", phase, kind, message)
        if self._md:
            try:
                with open(self._md, "a", encoding="utf-8") as handle:
                    handle.write(
                        f"**[{entry['t']:8.1f}s | {phase} | {kind}]** {message}\n"
                    )
                    if data:
                        handle.write(
                            "```json\n"
                            + json.dumps(data, indent=2, sort_keys=True, default=str)
                            + "\n```\n"
                        )
                    handle.write("\n")
                    handle.flush()
            except Exception:
                LOG.exception("journal append failed")
        if self._json:
            try:
                tmp = self._json + ".tmp"
                with open(tmp, "w", encoding="utf-8") as handle:
                    json.dump({"events": self._events}, handle, indent=2, default=str)
                os.replace(tmp, self._json)
            except Exception:
                LOG.exception("journal json failed")

    def save_csv(
        self, torque: Sequence[float], velocity: Sequence[float], sample_hz: float
    ) -> Optional[str]:
        if not self._md:
            return None
        path = os.path.join(self.dir, "trace.csv")
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(f"# fs_hz={sample_hz:g}\n")
                handle.write("t_s,torque_pct,vel_unit_per_min\n")
                for i, (tq, vel) in enumerate(zip(torque, velocity)):
                    handle.write(f"{i / sample_hz:.6f},{tq:.4f},{vel:.4f}\n")
            return path
        except Exception:
            LOG.exception("trace csv failed")
            return None

    def finalize(self, status: str, summary: Dict[str, Any]) -> None:
        self.event("finalize", "result", f"status={status}", **summary)


class HardwareGraphicalInertiaIO:
    """MDI move + HAL torque/velocity sampling."""

    name = "hardware"

    def __init__(self) -> None:
        if linuxcnc is None:
            raise GraphicalInertiaError(
                "linuxcnc module unavailable — run inside LinuxCNC"
            )
        self._stat = linuxcnc.stat()
        self._cmd = linuxcnc.command()

    def machine_ready(self) -> Tuple[bool, str]:
        try:
            self._stat.poll()
        except Exception as exc:
            return False, f"linuxcnc status unavailable: {exc}"
        if self._stat.task_state == linuxcnc.STATE_ESTOP:
            return False, "machine is in ESTOP"
        if not machine_is_on():
            return False, "machine is not ON"
        if self._stat.interp_state != linuxcnc.INTERP_IDLE:
            return False, "program / MDI still running"
        return True, "ok"

    def axis_state(self, axis: str) -> Dict[str, Any]:
        idx = {"X": 0, "Y": 1, "Z": 2, "A": 3}[axis]
        joint = AXES[axis]["joint"]
        self._stat.poll()
        return {
            "homed": bool(self._stat.joint[joint]["homed"]),
            "position": float(self._stat.actual_position[idx]),
            "min_limit": float(self._stat.axis[idx]["min_position_limit"]),
            "max_limit": float(self._stat.axis[idx]["max_position_limit"]),
        }

    def read_inertia_ratio(self, axis: str) -> float:
        params, _ok, _fail = read_axis_params(axis)
        if "inertia_ratio_pct" not in params.values:
            raise GraphicalInertiaError("C00.06 unread")
        return float(params.values["inertia_ratio_pct"])

    def write_inertia_ratio(self, axis: str, pct: float) -> None:
        clamped = max(0.0, min(12000.0, float(pct)))
        params = AxisTuneParams(values={"inertia_ratio_pct": clamped})
        result = apply_axis_params(
            axis, params, cycle_enable=True, keys=["inertia_ratio_pct"]
        )
        if "inertia_ratio_pct" not in result.get("written_keys", []):
            raise GraphicalInertiaError(
                f"C00.06 write failed: {result.get('failed_keys')}"
            )

    def apply_torque_limit(
        self, axis: str, pct: float
    ) -> Tuple[Optional[Dict[str, float]], List[str]]:
        """Temporarily clamp CiA torque limits. Returns (previous, written_names)."""
        slave = int(AXES[axis]["slave"])
        previous = read_cia_torque_limit_pct(slave)
        written = write_cia_torque_limit_pct(slave, pct)
        return previous, written

    def restore_torque_limit(
        self, axis: str, previous: Optional[Dict[str, float]]
    ) -> None:
        if not previous:
            return
        restore_cia_torque_limits(int(AXES[axis]["slave"]), previous)

    def apply_id_accel(
        self, axis: str, accel_unit_s2: float
    ) -> Dict[str, float]:
        return apply_ini_accel(axis, accel_unit_s2)

    def restore_id_accel(self, previous: Optional[Dict[str, float]]) -> None:
        restore_ini_accel(previous)

    def run_move_and_sample(
        self,
        axis: str,
        signed_stroke: float,
        feed: float,
        cycles: int,
        sample_hz: float,
        settle_s: float,
        cancel: threading.Event,
    ) -> Tuple[List[float], List[float], Dict[str, Any]]:
        meta: Dict[str, Any] = {"aborted": False, "abort_reason": ""}
        self._ensure_mdi()
        torque: List[float] = []
        velocity: List[float] = []
        period = 1.0 / float(sample_hz)
        sampler_stop = threading.Event()

        def _sample_loop() -> None:
            next_t = time.monotonic()
            while not sampler_stop.is_set():
                try:
                    torque.append(float(read_drive_torque(axis)))
                    velocity.append(float(read_drive_velocity(axis)))
                except Exception:
                    torque.append(float("nan"))
                    velocity.append(float("nan"))
                next_t += period
                sleep = next_t - time.monotonic()
                if sleep > 0:
                    time.sleep(sleep)

        thread = threading.Thread(target=_sample_loop, daemon=True)
        thread.start()
        leg_timeout = max(5.0, abs(signed_stroke) / max(feed / 60.0, 1e-3) * 3.0)
        try:
            self._mdi("G21")
            self._cmd.wait_complete(2.0)
            self._mdi("G91")
            self._cmd.wait_complete(2.0)
            for _ in range(max(1, cycles)):
                if cancel.is_set():
                    meta.update(aborted=True, abort_reason="cancelled")
                    self._cmd.abort()
                    break
                for sign in (1.0, -1.0):
                    if cancel.is_set():
                        meta.update(aborted=True, abort_reason="cancelled")
                        self._cmd.abort()
                        break
                    self._mdi(
                        f"G1 {axis}{sign * abs(signed_stroke):.4f} F{feed:.1f}"
                    )
                    ok, why = self._wait_leg(leg_timeout, cancel)
                    if not ok:
                        meta.update(aborted=True, abort_reason=why)
                        break
                if meta["aborted"]:
                    break
            if settle_s > 0 and not meta["aborted"]:
                time.sleep(settle_s)
        finally:
            sampler_stop.set()
            thread.join(timeout=2.0)
            try:
                self._mdi("G90")
                self._cmd.wait_complete(3.0)
            except Exception:
                LOG.exception("G90 restore failed")
        return torque, velocity, meta

    def _ensure_mdi(self) -> None:
        self._stat.poll()
        if self._stat.task_mode != linuxcnc.MODE_MDI:
            self._cmd.mode(linuxcnc.MODE_MDI)
            self._cmd.wait_complete(3.0)

    def _mdi(self, code: str) -> None:
        self._cmd.mdi(code)

    def _wait_leg(
        self, timeout: float, cancel: threading.Event
    ) -> Tuple[bool, str]:
        deadline = time.monotonic() + timeout
        while True:
            rc = self._cmd.wait_complete(0.1)
            if rc != -1:
                self._stat.poll()
                if self._stat.task_state != linuxcnc.STATE_ON:
                    return False, "machine dropped STATE_ON"
                return True, ""
            if cancel.is_set():
                self._cmd.abort()
                return False, "cancelled"
            self._stat.poll()
            if self._stat.task_state != linuxcnc.STATE_ON:
                self._cmd.abort()
                return False, "machine dropped STATE_ON"
            if time.monotonic() > deadline:
                self._cmd.abort()
                return False, "leg timeout"


@dataclass
class GraphicalInertiaConfig:
    axis: str
    settings: AxisInertiaSettings
    dry_run: bool = False
    sample_hz: float = 1000.0

    @classmethod
    def for_axis(
        cls, axis: str, settings: AxisInertiaSettings, **kwargs: Any
    ) -> "GraphicalInertiaConfig":
        if axis not in AXES:
            raise ValueError(f"unknown axis {axis!r}")
        return cls(axis=axis, settings=settings, **kwargs)


class GraphicalInertiaTuner:
    def __init__(
        self,
        config: GraphicalInertiaConfig,
        io: Optional[Any] = None,
        *,
        journal_root: Optional[str] = None,
        progress: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self.cfg = config
        self.io = io if io is not None else HardwareGraphicalInertiaIO()
        self.journal_root = journal_root or default_journal_root()
        self._progress_fn = progress
        self._cancel = threading.Event()
        self._journal: Optional[_Journal] = None

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> GraphicalInertiaResult:
        axis = self.cfg.axis
        settings = self.cfg.settings
        journal = _Journal(self.journal_root, axis)
        self._journal = journal
        try:
            settings.validate()
            self._progress("preflight", "checking machine…")
            ok, why = self.io.machine_ready()
            if not ok:
                return self._fail(why)

            state = self.io.axis_state(axis)
            journal.event("preflight", "state", "axis state", state=state)
            signed = self._pick_stroke(settings.stroke, state)

            feed = float(settings.feed)
            if feed > MAX_ID_FEED:
                journal.event(
                    "preflight",
                    "clamp",
                    f"feed {feed:g} → {MAX_ID_FEED:g} (MAX_ID_FEED)",
                    feed_requested=feed,
                    feed_used=MAX_ID_FEED,
                )
                feed = MAX_ID_FEED
            if AXES[axis]["linear"] and feed < MIN_ID_FEED_LINEAR:
                journal.event(
                    "preflight",
                    "warning",
                    f"feed {feed:g} < {MIN_ID_FEED_LINEAR:g} — inertial "
                    f"torque may be too small for a trusted estimate",
                    feed=feed,
                )

            journal.event(
                "preflight",
                "plan",
                f"stroke {signed:g} {axis_unit(axis)} @ F{feed:g}",
                settings=settings.to_dict(),
                signed_stroke=signed,
                feed_used=feed,
            )

            baseline = None
            try:
                baseline = float(self.io.read_inertia_ratio(axis))
                journal.event(
                    "baseline", "read", f"C00.06={baseline:.0f}%", ratio_pct=baseline
                )
            except Exception as exc:
                journal.event("baseline", "warning", f"C00.06 unread: {exc}")

            if self.cfg.dry_run:
                journal.finalize("dry-run", {"settings": settings.to_dict()})
                return GraphicalInertiaResult(
                    axis=axis,
                    status="dry-run",
                    reason="dry-run — no move / no write",
                    baseline_ratio_pct=baseline,
                    journal_dir=journal.dir,
                )

            self._check_cancel()
            torque_prev: Optional[Dict[str, float]] = None
            accel_prev: Optional[Dict[str, float]] = None

            id_accel = float(settings.id_accel_unit_s2)
            if id_accel <= 0:
                id_accel = target_id_accel(feed, PREFERRED_ACCEL_S)
            commanded_alpha = unit_accel_to_alpha(axis, id_accel)

            apply_accel_fn = getattr(self.io, "apply_id_accel", None)
            restore_accel_fn = getattr(self.io, "restore_id_accel", None)
            if apply_accel_fn is not None:
                self._progress(
                    "accel",
                    f"ID accel {id_accel:.0f} {axis_unit(axis)}/s² "
                    f"(~{PREFERRED_ACCEL_S * 1000:.0f} ms ramp)…",
                )
                try:
                    accel_prev = apply_accel_fn(axis, id_accel)
                    journal.event(
                        "accel",
                        "applied",
                        f"ini max_acceleration ← {id_accel:.1f}",
                        id_accel=id_accel,
                        commanded_alpha=commanded_alpha,
                        previous=accel_prev,
                    )
                except Exception as exc:
                    journal.event(
                        "accel",
                        "warning",
                        f"could not lower MAX_ACCELERATION: {exc}",
                    )
                    accel_prev = None
                    # Fall back: still pass commanded α from current ini if readable.
                    try:
                        cur = read_ini_accel(axis)
                        if cur:
                            commanded_alpha = unit_accel_to_alpha(
                                axis, min(cur.values())
                            )
                    except Exception:
                        pass

            if settings.torque_limit_pct > 0:
                self._progress(
                    "torque_limit",
                    f"applying torque limit {settings.torque_limit_pct:.0f}%…",
                )
                apply_fn = getattr(self.io, "apply_torque_limit", None)
                if apply_fn is None:
                    journal.event(
                        "torque_limit",
                        "skipped",
                        "IO has no apply_torque_limit",
                    )
                else:
                    try:
                        torque_prev, written = apply_fn(
                            axis, settings.torque_limit_pct
                        )
                        if not written:
                            journal.event(
                                "torque_limit",
                                "warning",
                                "no CiA 6072/60E0/60E1 objects writable — "
                                "limit not applied",
                            )
                            torque_prev = None
                        else:
                            journal.event(
                                "torque_limit",
                                "applied",
                                f"wrote {settings.torque_limit_pct:.0f}% to {written}",
                                previous=torque_prev,
                                written=written,
                            )
                    except Exception as exc:
                        journal.event(
                            "torque_limit",
                            "warning",
                            f"could not apply torque limit: {exc}",
                        )
                        torque_prev = None

            active_limit: Optional[float] = (
                float(settings.torque_limit_pct)
                if settings.torque_limit_pct > 0
                else None
            )

            try:
                self._progress("move", "sampling torque + velocity (probe)…")
                torque, velocity, meta = self.io.run_move_and_sample(
                    axis,
                    signed,
                    feed,
                    settings.cycles,
                    self.cfg.sample_hz,
                    settings.settle_s,
                    self._cancel,
                )
                journal.save_csv(torque, velocity, self.cfg.sample_hz)
                journal.event(
                    "move",
                    "done",
                    f"samples={len(torque)} aborted={meta.get('aborted')}",
                    meta=meta,
                )
                if meta.get("aborted"):
                    raise GraphicalInertiaError(
                        f"move aborted: {meta.get('abort_reason')}"
                    )
                if self._cancel.is_set():
                    raise GraphicalInertiaCancelled("cancelled")

                pairs = [
                    (t, v)
                    for t, v in zip(torque, velocity)
                    if t == t and v == v
                ]
                if len(pairs) < 20:
                    raise GraphicalInertiaError(
                        "too few valid torque/velocity samples"
                    )
                tq = [p[0] for p in pairs]
                vel = [p[1] for p in pairs]

                self._progress("analyze", "Yaskawa Tp−Tf (probe)…")
                estimate = analyze_torque_velocity(
                    axis,
                    tq,
                    vel,
                    self.cfg.sample_hz,
                    settings.motor_inertia_kgm2,
                    settings.rated_torque_nm,
                    commanded_alpha_rad_s2=commanded_alpha,
                    torque_limit_pct=active_limit,
                )
                journal.event(
                    "analyze",
                    "probe",
                    f"ratio={estimate.ratio_pct:.1f}% quality={estimate.quality}",
                    estimate=estimate.to_dict(),
                    commanded_alpha=commanded_alpha,
                    torque_limit_pct=active_limit,
                )

                # Sigma II Steps 1→2: always clamp for a trusted write when
                # no fixed Torque limit was set (v0.6 — not only when spiky).
                if active_limit is None and settings.auto_flatten:
                    limit = suggest_flatten_limit_pct(estimate)
                    apply_fn = getattr(self.io, "apply_torque_limit", None)
                    if limit is None or apply_fn is None:
                        journal.event(
                            "torque_limit",
                            "skipped",
                            "always-clamp needed but no usable limit/IO",
                            suggested=limit,
                            probe_spiky=probe_was_spiky(estimate),
                        )
                    else:
                        self._check_cancel()
                        self._progress(
                            "torque_limit",
                            f"clamp pass @ {limit:.0f}% (Pn402-style)…",
                        )
                        try:
                            torque_prev, written = apply_fn(axis, limit)
                            if written:
                                active_limit = limit
                                journal.event(
                                    "torque_limit",
                                    "auto_flatten",
                                    f"probe Tp={estimate.t_peak_pct:.1f}% → "
                                    f"limit {limit:.0f}% (always clamp)",
                                    previous=torque_prev,
                                    written=written,
                                    limit_pct=limit,
                                    probe_spiky=probe_was_spiky(estimate),
                                )
                                self._progress(
                                    "move",
                                    "sampling torque + velocity (clamped)…",
                                )
                                torque, velocity, meta = self.io.run_move_and_sample(
                                    axis,
                                    signed,
                                    feed,
                                    settings.cycles,
                                    self.cfg.sample_hz,
                                    settings.settle_s,
                                    self._cancel,
                                )
                                journal.save_csv(
                                    torque, velocity, self.cfg.sample_hz
                                )
                                journal.event(
                                    "move",
                                    "done",
                                    f"clamp samples={len(torque)} "
                                    f"aborted={meta.get('aborted')}",
                                    meta=meta,
                                )
                                if meta.get("aborted"):
                                    raise GraphicalInertiaError(
                                        f"clamp move aborted: "
                                        f"{meta.get('abort_reason')}"
                                    )
                                if self._cancel.is_set():
                                    raise GraphicalInertiaCancelled("cancelled")
                                pairs = [
                                    (t, v)
                                    for t, v in zip(torque, velocity)
                                    if t == t and v == v
                                ]
                                if len(pairs) < 20:
                                    raise GraphicalInertiaError(
                                        "too few samples on clamp pass"
                                    )
                                tq = [p[0] for p in pairs]
                                vel = [p[1] for p in pairs]
                                self._progress(
                                    "analyze", "Yaskawa Tp−Tf (clamped)…"
                                )
                                estimate = analyze_torque_velocity(
                                    axis,
                                    tq,
                                    vel,
                                    self.cfg.sample_hz,
                                    settings.motor_inertia_kgm2,
                                    settings.rated_torque_nm,
                                    commanded_alpha_rad_s2=commanded_alpha,
                                    torque_limit_pct=active_limit,
                                )
                                journal.event(
                                    "analyze",
                                    "flatten",
                                    f"ratio={estimate.ratio_pct:.1f}% "
                                    f"quality={estimate.quality}",
                                    estimate=estimate.to_dict(),
                                    torque_limit_pct=active_limit,
                                )
                            else:
                                journal.event(
                                    "torque_limit",
                                    "warning",
                                    "always-clamp: no CiA torque-limit objects "
                                    "writable — cannot produce quality=good",
                                )
                                torque_prev = None
                        except GraphicalInertiaCancelled:
                            raise
                        except GraphicalInertiaError:
                            raise
                        except Exception as exc:
                            journal.event(
                                "torque_limit",
                                "warning",
                                f"always-clamp failed: {exc}",
                            )
                elif active_limit is None and not settings.auto_flatten:
                    journal.event(
                        "torque_limit",
                        "warning",
                        "auto_flatten=false and Torque limit=0 — estimate "
                        "cannot be quality=good (no clamp)",
                    )
            finally:
                restore_fn = getattr(self.io, "restore_torque_limit", None)
                if torque_prev is not None and restore_fn is not None:
                    try:
                        restore_fn(axis, torque_prev)
                        journal.event(
                            "torque_limit",
                            "restored",
                            "restored previous CiA torque limits",
                            previous=torque_prev,
                        )
                    except Exception as exc:
                        journal.event(
                            "torque_limit",
                            "warning",
                            f"restore failed: {exc} — check 6072/60E0/60E1 on drive",
                        )
                if accel_prev is not None and restore_accel_fn is not None:
                    try:
                        restore_accel_fn(accel_prev)
                        journal.event(
                            "accel",
                            "restored",
                            "restored previous ini max_acceleration",
                            previous=accel_prev,
                        )
                    except Exception as exc:
                        journal.event(
                            "accel",
                            "warning",
                            f"accel restore failed: {exc} — check "
                            f"ini.*.max_acceleration",
                        )

            if estimate.quality == "bad":
                raise GraphicalInertiaError(
                    "measurement quality bad — "
                    + ("; ".join(estimate.notes) or "ragged torque plateau")
                )

            written = None
            if settings.write_to_drive and estimate.quality == "good":
                self._progress("write", f"writing C00.06={estimate.ratio_pct:.0f}%…")
                self.io.write_inertia_ratio(axis, estimate.ratio_pct)
                written = max(0.0, min(12000.0, estimate.ratio_pct))
                journal.event(
                    "write", "ok", f"C00.06 ← {written:.0f}%", ratio_pct=written
                )
            elif settings.write_to_drive and estimate.quality != "good":
                journal.event(
                    "write",
                    "skipped",
                    f"quality={estimate.quality} — not writing C00.06 "
                    f"(estimated {estimate.ratio_pct:.0f}%). Re-run or set manually.",
                    estimate_ratio_pct=estimate.ratio_pct,
                    quality=estimate.quality,
                )
            else:
                journal.event(
                    "write",
                    "skipped",
                    "write_to_drive=false",
                    estimate_ratio_pct=estimate.ratio_pct,
                )

            reason = (
                f"Yaskawa graphical analysis ratio "
                f"{estimate.ratio_pct:.0f}% ({estimate.quality})"
            )
            journal.finalize(
                "ok",
                {
                    "estimate": estimate.to_dict(),
                    "written_ratio_pct": written,
                    "baseline_ratio_pct": baseline,
                },
            )
            return GraphicalInertiaResult(
                axis=axis,
                status="ok",
                reason=reason,
                estimate=estimate,
                written_ratio_pct=written,
                baseline_ratio_pct=baseline,
                journal_dir=journal.dir,
            )
        except GraphicalInertiaCancelled as exc:
            journal.event("cancel", "abort", str(exc))
            journal.finalize("cancelled", {"reason": str(exc)})
            return GraphicalInertiaResult(
                axis=axis,
                status="cancelled",
                reason=str(exc),
                journal_dir=journal.dir,
            )
        except Exception as exc:
            LOG.exception("graphical inertia failed")
            journal.event(
                "error",
                "fail",
                str(exc),
                traceback=traceback.format_exc(),
            )
            journal.finalize("failed", {"reason": str(exc)})
            return GraphicalInertiaResult(
                axis=axis,
                status="failed",
                reason=str(exc),
                journal_dir=journal.dir,
            )

    def _fail(self, reason: str) -> GraphicalInertiaResult:
        if self._journal:
            self._journal.event("preflight", "fail", reason)
            self._journal.finalize("failed", {"reason": reason})
        return GraphicalInertiaResult(
            axis=self.cfg.axis,
            status="failed",
            reason=reason,
            journal_dir=self._journal.dir if self._journal else None,
        )

    def _progress(self, phase: str, message: str) -> None:
        if self._journal:
            self._journal.event(phase, "progress", message)
        if self._progress_fn is not None:
            try:
                self._progress_fn(phase, message)
            except Exception:
                LOG.debug("progress callback failed", exc_info=True)

    def _check_cancel(self) -> None:
        if self._cancel.is_set():
            raise GraphicalInertiaCancelled("cancelled")

    def _pick_stroke(self, stroke: float, state: Dict[str, Any]) -> float:
        """Choose +/− stroke that fits soft limits when homed."""
        mag = abs(float(stroke))
        if not state.get("homed"):
            return mag
        pos = float(state.get("position", 0.0))
        lo = float(state.get("min_limit", pos - mag))
        hi = float(state.get("max_limit", pos + mag))
        # Prefer the direction with more room; require clearance both ways for
        # out-and-back when cycles≥1 (return uses opposite sign).
        room_pos = hi - pos
        room_neg = pos - lo
        margin = 2.0 * mag + 1.0
        if room_pos >= margin and room_neg >= margin:
            return mag
        if room_pos >= margin:
            return mag
        if room_neg >= margin:
            return -mag
        raise GraphicalInertiaError(
            f"stroke {mag:g} does not fit soft limits at {pos:g} "
            f"(min={lo:g}, max={hi:g}) — park mid-travel or shorten stroke"
        )
