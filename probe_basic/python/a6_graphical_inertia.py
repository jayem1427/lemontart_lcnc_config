"""Graphical inertia identification for A6-EC drives.

Runs a trapezoidal move under LinuxCNC CSP, samples drive torque (6077) and
velocity (606C), then estimates load/motor inertia ratio for C00.06.

Primary estimator (v0.6, "physics fit"): fit the rigid-body model

    J·ω̇ = T − Fc·tanh(2ω) − b·ω

over the whole captured move so that integrating the measured torque
reproduces the measured velocity profile. This is immune to the A6
606C/6077 PDO sample-and-hold (10–36 ms), which makes every dV/dt-based
rule — including the classic Sigma II two-point worksheet — noise-dominated
on this hardware. Then:

    J_L = J_total − J_M
    ratio% = 100 * J_L / J_M        (→ C00.06, like Pn103)

The Sigma II two-point analysis (Tp − Tf, α cursors) still runs as a
cross-check and supplies the Tp/Tf/α-window plot overlays.

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
    FOLLOWING_ERROR_TUNING,
    hal_getp,
    hal_setp,
    machine_is_on,
    read_axis_params,
    read_drive_torque,
    read_drive_velocity,
    relax_following_error_for_tuning,
    restore_following_error_run,
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
ENGINE_VERSION = "0.6.1"

# --- Physics-fit estimator (primary since v0.6.0) -------------------------
# The A6 606C/6077 PDOs sample-and-hold for 10–36 ms, so ANY method that
# differentiates velocity (including the classic two-cursor Yaskawa rule)
# is noise-dominated on this hardware. Instead we integrate the measured
# torque through a rigid-body model J·ω̇ = T − Fc·tanh(2ω) − b·ω and fit
# (J, Fc, b) so the simulated velocity reproduces the measured profile.
# Integration is immune to the stair-stepping; on 2026-07-14/15 journals
# this clusters X at ~100% (IQR 89–118%) run-to-run where the two-point
# rule swung from −100% to +104000%.
PHYS_FIT_HZ = 250.0  # decimate to this rate before fitting (averaging LPF)
# Error gates use *cruise-weighted* RMS (rest + PDO-stepped ramps downweighted).
PHYS_ERR_GOOD = 0.18  # weighted RMS(vel error)/peak for quality=good
PHYS_ERR_MARGINAL = 0.28  # above this → reject unless J is strongly identified
PHYS_ERR_REJECT = 0.40  # hard reject regardless of identifiability
PHYS_IDENT_GOOD = 0.08  # error growth when J off ±40% (identifiability)
PHYS_IDENT_MARGINAL = 0.04
PHYS_MIN_PEAK_RPM_GOOD = 500.0  # linear axes: cruise speed floor for good
PHYS_MIN_PEAK_RPM_MARGINAL = 400.0

# Accel windows for the Yaskawa cross-check overlays (not the write decision).
MIN_ACCEL_S = 0.045
MIN_DECEL_S = 0.040
MIN_CRUISE_S = 0.040
# Physics fit wants a *softer* ID ramp: longer ramps → fewer 606C stair-steps
# during accel → lower velocity-fit residual. ~100 ms is the sweet spot.
PREFERRED_ACCEL_S = 0.100
# Second-pass ramp when the preferred move still fails the fit gates.
HARD_ID_ACCEL_S = 0.070
MIN_ID_ACCEL_UNIT_S2 = 80.0
# Soft clamp — very high F still works, but PDO stepping gets worse.
MAX_ID_FEED = 10000.0
# Below this on linear axes, inertial torque is often < ~4% rated on a
# soft ramp and the estimate becomes noise-dominated.
MIN_ID_FEED_LINEAR = 5000.0
# Pair ratios must agree within this relative span for quality=good.
MAX_LEG_RATIO_SPAN = 0.35
MIN_TA_PCT = 4.0
# Sanity band for a "good" write (outside → marginal, no C00.06 write).
MIN_RATIO_GOOD = 30.0
MAX_RATIO_GOOD = 500.0
# Accel torque relative spread above this → try Pn402-style flatten pass.
FLATNESS_CV_MAX = 0.18
# Auto-flatten sets limit to this fraction of unconstrained peak (above Tf).
AUTO_FLATTEN_FRAC = 0.90
AUTO_FLATTEN_MIN_MARGIN_PCT = 6.0
# Only treat a configured torque limit as Tp when the plateau actually rides it.
TORQUE_LIMIT_AS_TP_FRAC = 0.85
# Flat-torque window ΔV below this (vs peak) → fall back to full accel edge for α
# (A6 606C often stair-steps; a "flat" torque band can sit on one PDO hold).
MIN_ALPHA_DV_FRAC = 0.15
MIN_ALPHA_DV_RPM = 50.0

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


def _decimate_mean(values: Sequence[float], k: int) -> List[float]:
    """Mean-pool ``values`` in blocks of ``k`` (acts as anti-alias LPF)."""
    if k <= 1:
        return [float(v) for v in values]
    n = (len(values) // k) * k
    out: List[float] = []
    for i in range(0, n, k):
        s = 0.0
        for j in range(i, i + k):
            s += float(values[j])
        out.append(s / k)
    return out


def _simulate_velocity(
    torque_nm: Sequence[float],
    dt: float,
    j_total: float,
    coulomb_nm: float,
    viscous: float,
) -> List[float]:
    """Integrate J·ω̇ = T − Fc·tanh(2ω) − b·ω from rest → ω(t) [rad/s].

    Returns the midpoint of each step (matches mean-pooled measurements
    better than the endpoint and halves the sample-and-hold phase bias).
    """
    om: List[float] = []
    w = 0.0
    inv = dt / j_total
    for t_nm in torque_nm:
        w_prev = w
        w += (float(t_nm) - coulomb_nm * math.tanh(2.0 * w) - viscous * w) * inv
        om.append(0.5 * (w_prev + w))
    return om


def _vel_rmse(
    torque_nm: Sequence[float],
    omega_meas: Sequence[float],
    dt: float,
    j_total: float,
    coulomb_nm: float,
    viscous: float,
    weights: Optional[Sequence[float]] = None,
) -> float:
    sim = _simulate_velocity(torque_nm, dt, j_total, coulomb_nm, viscous)
    acc = 0.0
    wsum = 0.0
    for i, (s, m) in enumerate(zip(sim, omega_meas)):
        w = 1.0 if weights is None else float(weights[i])
        d = s - m
        acc += w * d * d
        wsum += w
    return math.sqrt(acc / max(wsum, 1e-30))


def _fit_weights(omega_meas: Sequence[float], dt: float) -> List[float]:
    """Downweight rest + steep PDO-stepped ramps; emphasize cruise.

    Hard ~60 ms ID ramps make 606C look like 0→peak jumps; those samples
    inflate unweighted RMS even when the fitted J is correct. Cruise is
    where friction and (via accel/decel impulse balance) inertia show up.
    """
    peak = max(abs(w) for w in omega_meas) or 1.0
    n = len(omega_meas)
    out: List[float] = []
    for i in range(n):
        w = abs(float(omega_meas[i]))
        if i + 1 < n:
            alpha = abs(float(omega_meas[i + 1]) - float(omega_meas[i])) / dt
        elif i > 0:
            alpha = abs(float(omega_meas[i]) - float(omega_meas[i - 1])) / dt
        else:
            alpha = 0.0
        if w < 0.05 * peak:
            out.append(0.15)  # rest — PDO offset noise, little J info
        elif alpha > 0.30 * peak / max(dt, 1e-3):
            out.append(0.35)  # steep stair-step edge
        else:
            out.append(1.0)  # cruise / gentle motion
    return out


def _nelder_mead(
    fn: Callable[[Sequence[float]], float],
    x0: Sequence[float],
    steps: Sequence[float],
    iters: int = 250,
    ftol: float = 1e-12,
) -> Tuple[List[float], float]:
    """Small dependency-free Nelder–Mead (3-ish params, smooth-ish cost)."""
    n = len(x0)
    simplex: List[List[float]] = [list(map(float, x0))]
    for i in range(n):
        v = list(map(float, x0))
        v[i] += steps[i]
        simplex.append(v)
    vals = [fn(v) for v in simplex]
    for _ in range(iters):
        order = sorted(range(n + 1), key=lambda i: vals[i])
        simplex = [simplex[i] for i in order]
        vals = [vals[i] for i in order]
        if abs(vals[-1] - vals[0]) < ftol * (abs(vals[0]) + 1e-30):
            break
        centroid = [
            sum(simplex[i][d] for i in range(n)) / n for d in range(n)
        ]
        reflect = [2.0 * centroid[d] - simplex[-1][d] for d in range(n)]
        f_r = fn(reflect)
        if f_r < vals[0]:
            expand = [3.0 * centroid[d] - 2.0 * simplex[-1][d] for d in range(n)]
            f_e = fn(expand)
            if f_e < f_r:
                simplex[-1], vals[-1] = expand, f_e
            else:
                simplex[-1], vals[-1] = reflect, f_r
        elif f_r < vals[-2]:
            simplex[-1], vals[-1] = reflect, f_r
        else:
            contract = [
                0.5 * (centroid[d] + simplex[-1][d]) for d in range(n)
            ]
            f_c = fn(contract)
            if f_c < vals[-1]:
                simplex[-1], vals[-1] = contract, f_c
            else:
                for i in range(1, n + 1):
                    simplex[i] = [
                        0.5 * (simplex[0][d] + simplex[i][d]) for d in range(n)
                    ]
                    vals[i] = fn(simplex[i])
    best = min(range(n + 1), key=lambda i: vals[i])
    return simplex[best], vals[best]


@dataclass
class PhysicsFit:
    """Result of the forward-simulation inertia fit."""

    j_total_kgm2: float
    coulomb_nm: float
    viscous_nm_per_rad_s: float
    err_frac: float  # RMS velocity error / peak velocity
    ident_frac: float  # cost growth with J off by ±40% (identifiability)
    peak_rpm: float
    sim_t_s: List[float]  # decimated timestamps for the sim overlay
    sim_vel_unit_per_min: List[float]  # simulated velocity (plot units)


def physics_fit_inertia(
    axis: str,
    torque_pct: Sequence[float],
    vel_unit_per_min: Sequence[float],
    sample_hz: float,
    rated_torque_nm: float,
) -> PhysicsFit:
    """Fit J·ω̇ = T − Fc·tanh(2ω) − b·ω to the whole captured move.

    Robust to 606C/6077 sample-and-hold because it integrates the torque
    instead of differentiating the stair-stepped velocity.
    """
    n = min(len(torque_pct), len(vel_unit_per_min))
    if n < 20:
        raise GraphicalInertiaError("not enough samples for physics fit")
    upr = unit_per_rev(axis)
    k = max(1, int(round(float(sample_hz) / PHYS_FIT_HZ)))
    dt = k / float(sample_hz)
    t_nm = _decimate_mean(
        [float(torque_pct[i]) / 100.0 * float(rated_torque_nm) for i in range(n)],
        k,
    )
    om_meas = _decimate_mean(
        [
            float(vel_unit_per_min[i]) / upr * (2.0 * math.pi / 60.0)
            for i in range(n)
        ],
        k,
    )
    peak_om = max(abs(w) for w in om_meas)
    if peak_om <= 0:
        raise GraphicalInertiaError("no motion in trace — physics fit impossible")
    # Fit on all samples (unweighted) — that recovers the ~100% X cluster.
    # Gate on cruise-weighted error so hard-ramp 606C stair-steps don't
    # reject a correct J (tonight's 235413: unweighted 22% / weighted ~18%).
    weights = _fit_weights(om_meas, dt)

    def cost(p: Sequence[float]) -> float:
        log_j, coulomb, viscous = p
        if coulomb < 0 or abs(viscous) > 2e-2 or not (-20.0 < log_j < 0.0):
            return 1e18
        e = _vel_rmse(t_nm, om_meas, dt, math.exp(log_j), coulomb, viscous)
        return e * e

    x0 = [math.log(1e-4), 0.05 * float(rated_torque_nm), 5e-4]
    x, _ = _nelder_mead(cost, x0, [0.7, 0.04 * float(rated_torque_nm), 5e-4])
    x, best = _nelder_mead(cost, x, [0.2, 0.015 * float(rated_torque_nm), 2e-4])
    j_total = math.exp(x[0])
    coulomb = float(x[1])
    viscous = float(x[2])

    e0_w = _vel_rmse(t_nm, om_meas, dt, j_total, coulomb, viscous, weights)
    err_frac = e0_w / peak_om
    e_up = _vel_rmse(t_nm, om_meas, dt, j_total * 1.4, coulomb, viscous, weights)
    e_dn = _vel_rmse(t_nm, om_meas, dt, j_total / 1.4, coulomb, viscous, weights)
    ident_frac = min(e_up, e_dn) / max(e0_w, 1e-12) - 1.0

    sim_om = _simulate_velocity(t_nm, dt, j_total, coulomb, viscous)
    to_unit = upr * 60.0 / (2.0 * math.pi)
    return PhysicsFit(
        j_total_kgm2=float(j_total),
        coulomb_nm=coulomb,
        viscous_nm_per_rad_s=viscous,
        err_frac=float(err_frac),
        ident_frac=float(ident_frac),
        peak_rpm=float(peak_om * 60.0 / (2.0 * math.pi)),
        sim_t_s=[i * dt for i in range(len(sim_om))],
        sim_vel_unit_per_min=[w * to_unit for w in sim_om],
    )


@dataclass
class AxisInertiaSettings:
    """Per-axis knobs shown on the INERTIA panel."""

    motor_inertia_kgm2: float = 0.0  # required > 0
    rated_torque_nm: float = 0.0  # required > 0
    stroke: float = 40.0  # mm or deg
    feed: float = 8000.0  # unit/min (G1 F)
    cycles: int = 1
    settle_s: float = 0.3
    # Fixed CiA torque clamp for the ID move (0 = none). When 0 and
    # auto_flatten is on, a probe pass may choose a Pn402-style limit.
    torque_limit_pct: float = 0.0
    # Two-pass flatten when accel torque is spiky (Sigma II Techniques).
    auto_flatten: bool = True
    write_to_drive: bool = True
    # Temporarily lower LinuxCNC ini.*.max_acceleration so the ID ramp is
    # long enough for T=Jα (0 = auto from feed → ~PREFERRED_ACCEL_S).
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
        return AxisInertiaSettings(stroke=15.0, feed=6000.0)
    if axis == "Z":
        return AxisInertiaSettings(stroke=15.0, feed=5000.0)
    if axis == "A":
        return AxisInertiaSettings(stroke=90.0, feed=3600.0)
    # X: high enough feed for T_A SNR on a ~120 ms ramp.
    return AxisInertiaSettings(stroke=40.0, feed=8000.0)


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
            "Physics-fit inertia ID (v0.6+): fits J·ω̇ = T − Fc·sgn(ω) − b·ω "
            "to the whole move; immune to A6 606C/6077 sample-and-hold. "
            "Motor inertia / rated torque are required datasheet values. "
            "Linear axes: stroke ~40, F8000–F10000, torque limit 0, cycles=1. "
            "Yaskawa Tp−Tf still shown as a cross-check overlay."
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
    # Geometry for Sigma II-style plot overlays (seconds from trace t=0).
    accel_t0_s: Optional[float] = None
    accel_t1_s: Optional[float] = None
    cruise_t0_s: Optional[float] = None
    cruise_t1_s: Optional[float] = None
    # Signed levels matching the analyzed leg polarity (for TQ overlay).
    tp_plot_pct: Optional[float] = None
    tf_plot_pct: Optional[float] = None
    # Physics-fit diagnostics (primary estimator since v0.6.0).
    method: str = "physics-fit"
    fit_err_frac: Optional[float] = None
    fit_ident_frac: Optional[float] = None
    coulomb_nm: Optional[float] = None
    viscous_nm_per_rad_s: Optional[float] = None
    # Simulated velocity overlay for the analysis plot (not journaled).
    sim_t_s: Optional[List[float]] = None
    sim_vel_unit_per_min: Optional[List[float]] = None

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
            "accel_t0_s": self.accel_t0_s,
            "accel_t1_s": self.accel_t1_s,
            "cruise_t0_s": self.cruise_t0_s,
            "cruise_t1_s": self.cruise_t1_s,
            "tp_plot_pct": self.tp_plot_pct,
            "tf_plot_pct": self.tf_plot_pct,
            "method": self.method,
            "fit_err_frac": self.fit_err_frac,
            "fit_ident_frac": self.fit_ident_frac,
            "coulomb_nm": self.coulomb_nm,
            "viscous_nm_per_rad_s": self.viscous_nm_per_rad_s,
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
    ramp = max(float(ramp_s), 0.020)
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
) -> Optional[Tuple[float, int, int]]:
    """Trapezoid cruise Tf: mean projected torque while near peak speed.

    Returns ``(tf_pct, i_lo, i_hi)`` or None if cruise is too short.
    """
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
    return _mean_proj_torque(tq, core, sign), int(core[0]), int(core[-1])


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
    """Yaskawa worksheet: Ta = Tp − Tf, α from constant-torque accel window."""
    a0, a1, sign = acc
    plateau_idx, t_acc_proj, flat_cv = _constant_torque_window(
        tq, rpm, a0, a1, peak_rpm, sign
    )
    # Techniques: "The torque limit IS the peak torque" only when the drive
    # is actually riding Pn402 / CiA clamp. An unused limit must not invent Tp.
    if (
        torque_limit_pct is not None
        and torque_limit_pct > 0
        and t_acc_proj >= TORQUE_LIMIT_AS_TP_FRAC * float(torque_limit_pct)
    ):
        t_peak = float(torque_limit_pct)
        notes_peak = f"Tp={t_peak:.1f}% (torque limit, riding)"
    elif torque_limit_pct is not None and torque_limit_pct > 0:
        t_peak = float(t_acc_proj)
        notes_peak = (
            f"Tp={t_peak:.1f}% (accel plateau; limit "
            f"{float(torque_limit_pct):.0f}% unused)"
        )
    else:
        t_peak = float(t_acc_proj)
        notes_peak = f"Tp={t_peak:.1f}% (accel plateau)"

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
    cruise_t0 = cruise_t1 = None
    if dec is not None:
        cruise = _cruise_friction_pct(
            tq, rpm, a1, dec[0], peak_rpm, sign, dt
        )
        if cruise is not None:
            tf_cruise, c0, c1 = cruise
            cruise_t0 = c0 * dt
            cruise_t1 = c1 * dt

    method = "trapezoid"
    cruise_tf = float(tf_cruise) if tf_cruise is not None else None
    if tf_cruise is not None:
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
    # Soft CSP ID ramps: if accel plateau never rises above cruise, Jα is
    # invisible in 6077. Accel/decel cancel would invent Ta from soft braking
    # (this mill's bogus ~6% ratios). Refuse and let the campaign harden α.
    if cruise_tf is not None and t_peak < cruise_tf + MIN_TA_PCT:
        raise GraphicalInertiaError(
            f"Jα invisible: accel Tp {t_peak:.1f}% < cruise Tf {cruise_tf:.1f}% "
            f"+ {MIN_TA_PCT:.0f}% — soft ID ramp hides inertia in friction "
            f"(need harder accel, not cancel-from-decel)"
        )
    # Cruise Tf usable but Ta still tiny, and we have a decel edge: workbook
    # triangle / directed cancel Ta = (Tp − Tdec) / 2.
    if t_inertial_pct < MIN_TA_PCT and t_dec_proj == t_dec_proj:
        t_friction = _triangle_friction_pct(t_peak, t_dec_proj)
        t_inertial_pct = t_peak - t_friction
        method = "accel/decel cancel (Tp−Tdec)/2"
    if t_inertial_pct < MIN_TA_PCT:
        raise GraphicalInertiaError(
            f"inertial torque too small (Ta={t_inertial_pct:.1f}% = "
            f"Tp {t_peak:.1f} − Tf {t_friction:.1f}). On soft CSP ID ramps "
            f"cruise friction often buries Jα — need a harder accel pass "
            f"or set C00.06 manually (~100–150% typical on X)."
        )

    # α: prefer Sigma II constant-torque vertical cursors; if that window sits
    # on a 606C stair-step hold (ΔV≈0), fall back to the full accel edge.
    i_lo, i_hi = plateau_idx[0], plateau_idx[-1]
    delta_t = max((i_hi - i_lo) * dt, dt)
    delta_rpm = abs(rpm[i_hi] - rpm[i_lo])
    alpha_note = "flat-torque window"
    min_dv = max(MIN_ALPHA_DV_RPM, MIN_ALPHA_DV_FRAC * peak_rpm)
    if delta_rpm < min_dv:
        i_lo, i_hi = a0, a1
        delta_t = max((i_hi - i_lo) * dt, dt)
        delta_rpm = abs(rpm[i_hi] - rpm[i_lo])
        alpha_note = "full accel edge (flat window ΔV too small)"
    if delta_t < MIN_ACCEL_S:
        raise GraphicalInertiaError(
            f"accel α window only {delta_t * 1000:.0f} ms — need "
            f"≥{MIN_ACCEL_S * 1000:.0f} ms (ID should auto-stretch "
            f"MAX_ACCELERATION / flatten torque)"
        )
    if delta_rpm < 5.0:
        raise GraphicalInertiaError("accel Δrpm too small for α")

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
        f"(ΔV={delta_rpm:.0f} rpm in {alpha_note})",
    ]
    if "cancel" in method:
        notes.append(
            "cruise Tp−Tf buried Jα on soft ID ramp — used accel/decel cancel"
        )
    quality = "good"
    if flat_cv > FLATNESS_CV_MAX and not (
        torque_limit_pct is not None
        and torque_limit_pct > 0
        and t_acc_proj >= TORQUE_LIMIT_AS_TP_FRAC * float(torque_limit_pct)
    ):
        quality = "marginal"
        notes.append(
            f"accel torque not flat (CV={flat_cv:.2f}) — enable auto-flatten "
            f"or set a torque limit (Sigma II Pn402 step)"
        )
    if "full accel edge" in alpha_note:
        quality = "marginal"
        notes.append(
            "α used full accel edge because flat-torque ΔV was tiny "
            "(606C hold) — trust ratio less; re-run or check PDO rate"
        )
    if delta_t < 0.85 * PREFERRED_ACCEL_S:
        notes.append(
            f"ramp window {delta_t * 1000:.0f} ms "
            f"(target ~{PREFERRED_ACCEL_S * 1000:.0f} ms)"
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
        accel_t0_s=float(i_lo * dt),
        accel_t1_s=float(i_hi * dt),
        cruise_t0_s=float(cruise_t0) if cruise_t0 is not None else None,
        cruise_t1_s=float(cruise_t1) if cruise_t1 is not None else None,
        tp_plot_pct=float(t_peak) * float(sign),
        tf_plot_pct=float(t_friction) * float(sign),
    )


def _analyze_yaskawa_legs(
    axis: str,
    torque_pct: Sequence[float],
    vel_unit_per_min: Sequence[float],
    sample_hz: float,
    motor_inertia_kgm2: float,
    rated_torque_nm: float,
    *,
    torque_limit_pct: Optional[float] = None,
) -> InertiaEstimate:
    """Classic Sigma II two-point rule (Tp − Tf, α from cursors).

    Kept as a cross-check/overlay source only: A6 606C/6077 sample-and-hold
    makes the two-point α unreliable, so the write decision uses the
    physics fit in :func:`analyze_torque_velocity` instead.
    """
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
            + " — check the TQ/VEL plot for a clear accel + decel pair; "
            "soft CSP ID ramps often need accel/decel cancel (automatic). "
            "If it keeps failing, set C00.06 manually (~100–150% typical on X)."
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
    """Inertia ratio from the physics fit (primary since v0.6.0).

    Fits J·ω̇ = T − Fc·tanh(2ω) − b·ω to the whole captured move so the
    simulated velocity reproduces the measured profile. Immune to A6
    606C/6077 sample-and-hold, which breaks any dV/dt-based rule. The
    classic Sigma II two-point analysis still runs as a cross-check and
    supplies the Tp/Tf/α plot overlays when it succeeds.
    """
    del commanded_alpha_rad_s2
    n = min(len(torque_pct), len(vel_unit_per_min))
    if n < 20:
        raise GraphicalInertiaError("not enough samples for inertia analysis")
    if sample_hz <= 0:
        raise GraphicalInertiaError("sample_hz must be > 0")
    if motor_inertia_kgm2 <= 0 or rated_torque_nm <= 0:
        raise GraphicalInertiaError("motor inertia and rated torque must be > 0")

    linear = bool(AXES[axis]["linear"])
    peak_rpm_meas = max(
        abs(unit_per_min_to_rpm(axis, float(v))) for v in vel_unit_per_min[:n]
    )
    if peak_rpm_meas < 30.0:
        raise GraphicalInertiaError(
            f"peak speed only {peak_rpm_meas:.1f} rpm — raise feed so cruise "
            f"is clear (prefer F{MIN_ID_FEED_LINEAR:.0f}–F{MAX_ID_FEED:.0f} "
            f"on linear axes)."
        )
    if linear and peak_rpm_meas < PHYS_MIN_PEAK_RPM_MARGINAL:
        raise GraphicalInertiaError(
            f"peak only {peak_rpm_meas:.0f} rpm — raise feed to "
            f"F{MIN_ID_FEED_LINEAR:.0f}–F{MAX_ID_FEED:.0f} on linear axes. "
            f"Slow moves are friction-dominated and the fit cannot separate "
            f"J from friction (F2000 runs → nonsense ratios)."
        )

    fit = physics_fit_inertia(
        axis, torque_pct, vel_unit_per_min, sample_hz, rated_torque_nm
    )
    j_load = fit.j_total_kgm2 - float(motor_inertia_kgm2)
    # Hard reject: catastrophic mismatch, OR weak error+ident together.
    # A correct J with high ramp residuals (hard ID accel + 606C stairs)
    # must still be allowed through as marginal when identifiability is OK.
    reject = fit.err_frac > PHYS_ERR_REJECT or fit.ident_frac < PHYS_IDENT_MARGINAL
    if not reject and fit.err_frac > PHYS_ERR_MARGINAL:
        reject = fit.ident_frac < PHYS_IDENT_GOOD
    if reject:
        raise GraphicalInertiaError(
            f"physics fit untrustworthy (vel error {fit.err_frac * 100:.0f}% "
            f"of peak, J-sensitivity {fit.ident_frac * 100:.0f}%) — trace does "
            f"not look like rigid body + friction. Re-run with stroke ~40, "
            f"F{MIN_ID_FEED_LINEAR:.0f}–F{MAX_ID_FEED:.0f}, torque limit 0, "
            f"and leave ID accel on auto (~{PREFERRED_ACCEL_S * 1000:.0f} ms)."
        )
    if j_load <= 0:
        raise GraphicalInertiaError(
            f"fitted J_total {fit.j_total_kgm2:.3e} ≤ motor inertia "
            f"{motor_inertia_kgm2:.3e} — trace inconsistent (check motor "
            f"inertia / rated torque settings)"
        )
    ratio_pct = 100.0 * j_load / float(motor_inertia_kgm2)

    tf_pct = 100.0 * fit.coulomb_nm / float(rated_torque_nm)
    notes = [
        f"physics fit J·ω̇ = T − Fc·sgn(ω) − b·ω over whole move "
        f"(integrates 6077, immune to 606C holds)",
        f"Fc={fit.coulomb_nm:.3f} Nm ({tf_pct:.1f}%) "
        f"b={fit.viscous_nm_per_rad_s:.1e} Nm·s",
        f"vel fit error {fit.err_frac * 100:.1f}% of peak; "
        f"J-sensitivity {fit.ident_frac * 100:.0f}%",
    ]

    quality = "good"
    # Hard ~60 ms ID ramps leave elevated cruise-weighted residuals from
    # 606C stairs even when J is correctly recovered (tonight's 235413:
    # ratio 99%, ident 13%, err 26%). Trust identifiability over residual
    # only when the ratio itself sits in the expected band.
    err_good = PHYS_ERR_GOOD
    if (
        fit.ident_frac >= 0.12
        and 80.0 <= ratio_pct <= 200.0
        and (not linear or fit.peak_rpm >= PHYS_MIN_PEAK_RPM_GOOD)
    ):
        err_good = max(err_good, 0.27)
    if fit.err_frac > err_good:
        quality = "marginal"
        notes.append(
            f"fit error {fit.err_frac * 100:.0f}% > "
            f"{err_good * 100:.0f}% — re-run with softer auto ID accel "
            f"(~{PREFERRED_ACCEL_S * 1000:.0f} ms)"
        )
    if fit.ident_frac < PHYS_IDENT_GOOD:
        quality = "marginal"
        notes.append(
            f"J barely constrains the fit (sensitivity "
            f"{fit.ident_frac * 100:.0f}% < {PHYS_IDENT_GOOD * 100:.0f}%) — "
            f"raise feed so inertia dominates friction"
        )
    if linear and fit.peak_rpm < PHYS_MIN_PEAK_RPM_GOOD:
        quality = "marginal"
        notes.append(
            f"peak only {fit.peak_rpm:.0f} rpm — prefer "
            f"F{MIN_ID_FEED_LINEAR:.0f}–F{MAX_ID_FEED:.0f} for a good write"
        )
    if ratio_pct < MIN_RATIO_GOOD or ratio_pct > MAX_RATIO_GOOD:
        quality = "marginal"
        notes.append(
            f"ratio {ratio_pct:.0f}% outside trusted band "
            f"[{MIN_RATIO_GOOD:.0f}, {MAX_RATIO_GOOD:.0f}]%"
        )

    # Cross-check + plot overlays from the classic two-point rule.
    t_peak_pct = tf_pct
    alpha = 0.0
    delta_rpm = fit.peak_rpm
    delta_t = 0.0
    overlay: Optional[InertiaEstimate] = None
    try:
        overlay = _analyze_yaskawa_legs(
            axis,
            torque_pct,
            vel_unit_per_min,
            sample_hz,
            motor_inertia_kgm2,
            rated_torque_nm,
            torque_limit_pct=torque_limit_pct,
        )
    except GraphicalInertiaError as exc:
        notes.append(f"two-point cross-check unavailable ({exc})")
    if overlay is not None:
        t_peak_pct = overlay.t_peak_pct
        tf_display = overlay.t_friction_pct
        alpha = overlay.alpha_rad_s2
        delta_rpm = overlay.delta_rpm
        delta_t = overlay.delta_t_s
        agree = abs(overlay.ratio_pct - ratio_pct) / max(abs(ratio_pct), 1.0)
        notes.append(
            f"two-point cross-check {overlay.ratio_pct:.0f}% "
            f"({'agrees' if agree < 0.5 else 'diverges — PDO holds; fit wins'})"
        )
        for note in overlay.notes:
            if "limit" in note.lower():
                notes.append(note)
    else:
        tf_display = tf_pct

    t_accel_nm = ((t_peak_pct - tf_display) / 100.0) * float(rated_torque_nm)
    return InertiaEstimate(
        ratio_pct=float(ratio_pct),
        j_load_kgm2=float(j_load),
        j_total_kgm2=float(fit.j_total_kgm2),
        t_peak_pct=float(t_peak_pct),
        t_friction_pct=float(tf_display),
        t_accel_nm=float(t_accel_nm),
        alpha_rad_s2=float(alpha),
        delta_rpm=float(delta_rpm),
        delta_t_s=float(delta_t),
        quality=quality,
        notes=notes,
        accel_t0_s=overlay.accel_t0_s if overlay else None,
        accel_t1_s=overlay.accel_t1_s if overlay else None,
        cruise_t0_s=overlay.cruise_t0_s if overlay else None,
        cruise_t1_s=overlay.cruise_t1_s if overlay else None,
        tp_plot_pct=overlay.tp_plot_pct if overlay else None,
        tf_plot_pct=overlay.tf_plot_pct if overlay else None,
        method="physics-fit",
        fit_err_frac=float(fit.err_frac),
        fit_ident_frac=float(fit.ident_frac),
        coulomb_nm=float(fit.coulomb_nm),
        viscous_nm_per_rad_s=float(fit.viscous_nm_per_rad_s),
        sim_t_s=list(fit.sim_t_s),
        sim_vel_unit_per_min=list(fit.sim_vel_unit_per_min),
    )


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
    """True when accel torque was spiky (Sigma II step 2 would clamp Pn402)."""
    return "not flat" in " ".join(estimate.notes).lower()


def probe_needs_harder_accel(exc: BaseException) -> bool:
    """True when soft ID ramp hid Jα above cruise (retry with HARD_ID_ACCEL_S)."""
    msg = str(exc).lower()
    return "jα invisible" in msg or "ja invisible" in msg or (
        "inertial torque too small" in msg and "harder accel" in msg
    )


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
    # Full campaign capture for the analysis plot (1 kHz journal samples).
    trace_t_s: Optional[List[float]] = None
    trace_torque_pct: Optional[List[float]] = None
    trace_vel_unit_per_min: Optional[List[float]] = None

    def summary(self) -> str:
        bits = [f"{self.status}: {self.reason}"]
        if self.estimate is not None:
            bits.append(
                f"ratio={self.estimate.ratio_pct:.0f}% ({self.estimate.quality})"
            )
        if self.written_ratio_pct is not None:
            bits.append(f"wrote C00.06={self.written_ratio_pct:.0f}%")
        return " | ".join(bits)


def load_trace_csv(
    path: str,
) -> Tuple[List[float], List[float], List[float], float]:
    """Load ``trace.csv`` → (t_s, torque_pct, vel_unit_per_min, sample_hz)."""
    sample_hz = 1000.0
    times: List[float] = []
    torque: List[float] = []
    vel: List[float] = []
    with open(path, encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("#"):
                if "fs_hz=" in line:
                    try:
                        sample_hz = float(line.split("fs_hz=", 1)[1].split()[0])
                    except ValueError:
                        pass
                continue
            if line.startswith("t_s"):
                continue
            parts = line.split(",")
            if len(parts) < 3:
                continue
            times.append(float(parts[0]))
            torque.append(float(parts[1]))
            vel.append(float(parts[2]))
    if not times:
        raise GraphicalInertiaError(f"empty inertia trace: {path}")
    return times, torque, vel, sample_hz


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
        ferr_relaxed = False
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
                raise GraphicalInertiaError(
                    f"Feed F{feed:g} is too slow for inertia ID on {axis}. "
                    f"Use F{MIN_ID_FEED_LINEAR:.0f}–F{MAX_ID_FEED:.0f} "
                    f"(low feed → tiny α → nonsense ratio like 1000%+). "
                    f"Stroke ~40 mm, Torque limit = 0."
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

            prior_ferr = relax_following_error_for_tuning(axis)
            ferr_relaxed = True
            journal.event(
                "baseline",
                "ferr-window",
                f"6065 raised to {FOLLOWING_ERROR_TUNING:g} {axis_unit(axis)} "
                f"for inertia ID (was {prior_ferr:g}); production window is 0.5",
                prior=prior_ferr,
                tuning=FOLLOWING_ERROR_TUNING,
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

                self._progress("analyze", "physics fit J·ω̇=T−friction (probe)…")
                try:
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
                except GraphicalInertiaError as exc:
                    if (
                        settings.id_accel_unit_s2 <= 0
                        and apply_accel_fn is not None
                        and probe_needs_harder_accel(exc)
                    ):
                        journal.event(
                            "analyze",
                            "ja_invisible",
                            str(exc),
                        )
                        hard_accel = target_id_accel(feed, HARD_ID_ACCEL_S)
                        self._check_cancel()
                        self._progress(
                            "accel",
                            f"Jα buried — harder ID accel "
                            f"{hard_accel:.0f} {axis_unit(axis)}/s² "
                            f"(~{HARD_ID_ACCEL_S * 1000:.0f} ms)…",
                        )
                        try:
                            # Restore soft ramp first if we already applied one.
                            if accel_prev is not None and restore_accel_fn is not None:
                                restore_accel_fn(accel_prev)
                            accel_prev = apply_accel_fn(axis, hard_accel)
                            id_accel = hard_accel
                            commanded_alpha = unit_accel_to_alpha(axis, id_accel)
                            journal.event(
                                "accel",
                                "hardened",
                                f"ini max_acceleration ← {id_accel:.1f}",
                                id_accel=id_accel,
                                commanded_alpha=commanded_alpha,
                                previous=accel_prev,
                                ramp_s=HARD_ID_ACCEL_S,
                            )
                        except Exception as accel_exc:
                            raise GraphicalInertiaError(
                                f"Jα invisible on soft ramp and harder accel "
                                f"failed ({accel_exc})"
                            ) from accel_exc
                        self._progress(
                            "move", "sampling torque + velocity (harder accel)…"
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
                        journal.save_csv(torque, velocity, self.cfg.sample_hz)
                        journal.event(
                            "move",
                            "done",
                            f"hard samples={len(torque)} "
                            f"aborted={meta.get('aborted')}",
                            meta=meta,
                        )
                        if meta.get("aborted"):
                            raise GraphicalInertiaError(
                                f"harder-accel move aborted: "
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
                                "too few samples on harder-accel pass"
                            )
                        tq = [p[0] for p in pairs]
                        vel = [p[1] for p in pairs]
                        self._progress("analyze", "physics fit (harder accel)…")
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
                        estimate.notes = list(estimate.notes)
                        estimate.notes.append(
                            f"second pass @ ~{HARD_ID_ACCEL_S * 1000:.0f} ms ID ramp "
                            f"(Jα was invisible on softer ramp)"
                        )
                    else:
                        raise
                journal.event(
                    "analyze",
                    "probe",
                    f"ratio={estimate.ratio_pct:.1f}% quality={estimate.quality}",
                    estimate=estimate.to_dict(),
                    commanded_alpha=commanded_alpha,
                    torque_limit_pct=active_limit,
                )

                # Sigma II Steps 1→2: if accel torque is spiky and no fixed
                # limit was set, re-run with Pn402-style clamp for a flat Tp.
                if (
                    active_limit is None
                    and settings.auto_flatten
                    and probe_needs_flatten(estimate)
                ):
                    limit = suggest_flatten_limit_pct(estimate)
                    apply_fn = getattr(self.io, "apply_torque_limit", None)
                    if limit is None or apply_fn is None:
                        journal.event(
                            "torque_limit",
                            "skipped",
                            "auto-flatten needed but no usable limit/IO",
                            suggested=limit,
                        )
                    else:
                        self._check_cancel()
                        self._progress(
                            "torque_limit",
                            f"auto-flatten pass @ {limit:.0f}% (Pn402-style)…",
                        )
                        try:
                            torque_prev, written = apply_fn(axis, limit)
                            if written:
                                active_limit = limit
                                journal.event(
                                    "torque_limit",
                                    "auto_flatten",
                                    f"probe Tp={estimate.t_peak_pct:.1f}% → "
                                    f"limit {limit:.0f}%",
                                    previous=torque_prev,
                                    written=written,
                                    limit_pct=limit,
                                )
                                self._progress(
                                    "move",
                                    "sampling torque + velocity (flattened)…",
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
                                    f"flatten samples={len(torque)} "
                                    f"aborted={meta.get('aborted')}",
                                    meta=meta,
                                )
                                if meta.get("aborted"):
                                    raise GraphicalInertiaError(
                                        f"flatten move aborted: "
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
                                        "too few samples on flatten pass"
                                    )
                                tq = [p[0] for p in pairs]
                                vel = [p[1] for p in pairs]
                                self._progress(
                                    "analyze", "physics fit (flattened)…"
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
                                    "auto-flatten: no CiA torque-limit objects "
                                    "writable",
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
                                f"auto-flatten failed: {exc}",
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
                f"physics-fit inertia ratio "
                f"{estimate.ratio_pct:.0f}% ({estimate.quality})"
            )
            status = "ok" if estimate.quality == "good" else "marginal"
            journal.finalize(
                status,
                {
                    "estimate": estimate.to_dict(),
                    "written_ratio_pct": written,
                    "baseline_ratio_pct": baseline,
                },
            )
            return GraphicalInertiaResult(
                axis=axis,
                status=status,
                reason=reason,
                estimate=estimate,
                written_ratio_pct=written,
                baseline_ratio_pct=baseline,
                journal_dir=journal.dir,
                trace_t_s=[i / self.cfg.sample_hz for i in range(len(tq))],
                trace_torque_pct=list(tq),
                trace_vel_unit_per_min=list(vel),
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
        finally:
            if ferr_relaxed:
                try:
                    restore_following_error_run(axis)
                    journal.event(
                        "finalize",
                        "ferr-window",
                        "6065 restored to 0.5 production window",
                    )
                except Exception:
                    LOG.exception("restore 6065 production window failed")

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
