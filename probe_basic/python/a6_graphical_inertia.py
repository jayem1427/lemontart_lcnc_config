"""Graphical inertia identification (Yaskawa-style T=Jα) for A6-EC.

Runs a trapezoidal move under LinuxCNC CSP, samples drive torque (6077) and
velocity (606C), then estimates load/motor inertia ratio for C00.06:

    T_A   = T_peak - T_friction
    α     = Δω / Δt   (from feedback speed during the accel plateau)
    J_tot = T_A / α
    J_L   = J_tot - J_M
    ratio% = 100 * J_L / J_M

See docs/GRAPHICAL_INERTIA_TUNE.md and the Yaskawa "Inertia by Graphical
Analysis" eLV. Separate from F30.10 and from one-click gain tuning.
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
    machine_is_on,
    read_axis_params,
    read_drive_torque,
    read_drive_velocity,
)

try:
    import linuxcnc
except ImportError:  # pragma: no cover
    linuxcnc = None  # type: ignore

LOG = logging.getLogger(__name__)
ENGINE_VERSION = "0.1.0"

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


@dataclass
class AxisInertiaSettings:
    """Per-axis knobs shown on the INERTIA panel."""

    motor_inertia_kgm2: float = 0.0  # required > 0
    rated_torque_nm: float = 0.0  # required > 0
    stroke: float = 40.0  # mm or deg
    feed: float = 3000.0  # unit/min (G1 F)
    cycles: int = 1
    settle_s: float = 0.3
    # Optional analysis hints (0 = auto).
    torque_limit_pct: float = 0.0  # reserved / documented; not written yet
    write_to_drive: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "motor_inertia_kgm2": self.motor_inertia_kgm2,
            "rated_torque_nm": self.rated_torque_nm,
            "stroke": self.stroke,
            "feed": self.feed,
            "cycles": self.cycles,
            "settle_s": self.settle_s,
            "torque_limit_pct": self.torque_limit_pct,
            "write_to_drive": self.write_to_drive,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AxisInertiaSettings":
        return cls(
            motor_inertia_kgm2=float(data.get("motor_inertia_kgm2", 0.0)),
            rated_torque_nm=float(data.get("rated_torque_nm", 0.0)),
            stroke=float(data.get("stroke", 40.0)),
            feed=float(data.get("feed", 3000.0)),
            cycles=max(1, int(data.get("cycles", 1))),
            settle_s=float(data.get("settle_s", 0.3)),
            torque_limit_pct=float(data.get("torque_limit_pct", 0.0)),
            write_to_drive=bool(data.get("write_to_drive", True)),
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
        return AxisInertiaSettings(stroke=15.0, feed=2000.0)
    if axis == "Z":
        return AxisInertiaSettings(stroke=15.0, feed=1500.0)
    if axis == "A":
        return AxisInertiaSettings(stroke=90.0, feed=3600.0)
    return AxisInertiaSettings(stroke=40.0, feed=3000.0)


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
            "Motor inertia / rated torque are required datasheet values. "
            "Stroke/feed define the identification move (G1)."
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


def analyze_torque_velocity(
    axis: str,
    torque_pct: Sequence[float],
    vel_unit_per_min: Sequence[float],
    sample_hz: float,
    motor_inertia_kgm2: float,
    rated_torque_nm: float,
) -> InertiaEstimate:
    """Yaskawa graphical analysis on sampled torque (%) + velocity (unit/min)."""
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

    # Smooth-ish derivative via simple diff for phase detection.
    d_rpm = [0.0] * n
    for i in range(1, n):
        d_rpm[i] = (rpm[i] - rpm[i - 1]) / dt

    peak_rpm = max(abs(r) for r in rpm)
    if peak_rpm < 30.0:
        raise GraphicalInertiaError(
            f"peak speed only {peak_rpm:.1f} rpm — raise feed or stroke so the "
            f"move reaches a clear cruise (need ≥ ~150 rpm ideally)."
        )

    # Accel phase: rising |rpm| with positive d(|rpm|)/dt, away from zero and cruise.
    accel_idx = [
        i
        for i in range(n)
        if abs(rpm[i]) > 0.05 * peak_rpm
        and abs(rpm[i]) < 0.90 * peak_rpm
        and (rpm[i] * d_rpm[i] > 0)  # speeding up in the signed sense
        and abs(d_rpm[i]) > 50.0  # rpm/s — ignore flat bits
    ]
    cruise_idx = [
        i
        for i in range(n)
        if abs(rpm[i]) > 0.85 * peak_rpm and abs(d_rpm[i]) < 80.0
    ]

    notes: List[str] = []
    if len(accel_idx) < 8:
        raise GraphicalInertiaError(
            "could not find a clean acceleration window — try a longer stroke "
            "or lower accel (INI) so torque can plateau."
        )
    if len(cruise_idx) < 5:
        notes.append("short cruise — friction estimate may be noisy")
        # Fall back to samples near peak speed.
        cruise_idx = sorted(
            range(n), key=lambda i: abs(abs(rpm[i]) - peak_rpm)
        )[: max(5, n // 20)]

    # Use central portion of accel window for plateau torque (reject spikes).
    a0 = accel_idx[len(accel_idx) // 4]
    a1 = accel_idx[(3 * len(accel_idx)) // 4]
    plateau = [i for i in accel_idx if a0 <= i <= a1] or accel_idx
    t_peak = _median([tq[i] for i in plateau])
    t_fric = _median([tq[i] for i in cruise_idx])
    t_accel_pct = t_peak - t_fric
    if abs(t_accel_pct) < 1.0:
        raise GraphicalInertiaError(
            f"acceleration torque too small ({t_accel_pct:.2f}% rated) after "
            f"subtracting friction — check torque/velocity pins or raise accel."
        )

    # Δrpm / Δt across the plateau (cursor method).
    i_lo = min(plateau, key=lambda i: abs(rpm[i]))
    i_hi = max(plateau, key=lambda i: abs(rpm[i]))
    if i_hi == i_lo:
        i_lo, i_hi = plateau[0], plateau[-1]
    delta_rpm = abs(rpm[i_hi] - rpm[i_lo])
    delta_t = abs(i_hi - i_lo) * dt
    if delta_t < 1e-4 or delta_rpm < 5.0:
        raise GraphicalInertiaError(
            "acceleration window too short to measure Δrpm/Δt reliably"
        )
    alpha = rpm_to_rad_s(delta_rpm) / delta_t  # rad/s²

    t_accel_nm = (t_accel_pct / 100.0) * float(rated_torque_nm)
    # Use absolute torque magnitude for inertia (direction handled by α sign).
    j_total = abs(t_accel_nm) / alpha
    j_load = j_total - float(motor_inertia_kgm2)
    if j_load <= 0:
        raise GraphicalInertiaError(
            f"computed J_load ≤ 0 (J_total={j_total:.4e}, J_M={motor_inertia_kgm2:.4e}). "
            f"Check rated torque / rotor inertia datasheet values."
        )
    ratio_pct = 100.0 * j_load / float(motor_inertia_kgm2)

    # Quality heuristics (measurement trace, not closed-loop goodness).
    plateau_vals = [tq[i] for i in plateau]
    spread = max(plateau_vals) - min(plateau_vals) if plateau_vals else 999.0
    quality = "good"
    if spread > 25.0:
        quality = "bad"
        notes.append(
            f"torque plateau very ragged (spread {spread:.0f}%) — "
            f"soften gains or set a drive torque limit and retry"
        )
    elif spread > 12.0:
        quality = "marginal"
        notes.append(f"torque plateau somewhat ragged (spread {spread:.0f}%)")
    if peak_rpm < 150.0:
        quality = "marginal" if quality == "good" else quality
        notes.append(f"peak only {peak_rpm:.0f} rpm (prefer ≥150)")
    if ratio_pct > 12000:
        notes.append("ratio > 12000% (C00.06 max) — will clamp on write")

    return InertiaEstimate(
        ratio_pct=float(ratio_pct),
        j_load_kgm2=float(j_load),
        j_total_kgm2=float(j_total),
        t_peak_pct=float(t_peak),
        t_friction_pct=float(t_fric),
        t_accel_nm=float(t_accel_nm),
        alpha_rad_s2=float(alpha),
        delta_rpm=float(delta_rpm),
        delta_t_s=float(delta_t),
        quality=quality,
        notes=notes,
    )


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
            journal.event(
                "preflight",
                "plan",
                f"stroke {signed:g} {axis_unit(axis)} @ F{settings.feed:g}",
                settings=settings.to_dict(),
                signed_stroke=signed,
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
            self._progress("move", "sampling torque + velocity…")
            torque, velocity, meta = self.io.run_move_and_sample(
                axis,
                signed,
                settings.feed,
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

            self._progress("analyze", "computing J from T=Jα…")
            # Drop NaNs
            pairs = [
                (t, v)
                for t, v in zip(torque, velocity)
                if t == t and v == v
            ]
            if len(pairs) < 20:
                raise GraphicalInertiaError("too few valid torque/velocity samples")
            tq = [p[0] for p in pairs]
            vel = [p[1] for p in pairs]
            estimate = analyze_torque_velocity(
                axis,
                tq,
                vel,
                self.cfg.sample_hz,
                settings.motor_inertia_kgm2,
                settings.rated_torque_nm,
            )
            journal.event(
                "analyze",
                "estimate",
                f"ratio={estimate.ratio_pct:.1f}% quality={estimate.quality}",
                estimate=estimate.to_dict(),
            )
            if estimate.quality == "bad":
                raise GraphicalInertiaError(
                    "measurement quality bad — "
                    + ("; ".join(estimate.notes) or "ragged torque plateau")
                )

            written = None
            if settings.write_to_drive:
                self._progress("write", f"writing C00.06={estimate.ratio_pct:.0f}%…")
                self.io.write_inertia_ratio(axis, estimate.ratio_pct)
                written = max(0.0, min(12000.0, estimate.ratio_pct))
                journal.event(
                    "write", "ok", f"C00.06 ← {written:.0f}%", ratio_pct=written
                )
            else:
                journal.event("write", "skipped", "write_to_drive=False")

            reason = (
                f"estimated {estimate.ratio_pct:.0f}% "
                f"(T_A={estimate.t_accel_nm:.3f} N·m, α={estimate.alpha_rad_s2:.0f} rad/s²)"
            )
            journal.finalize(
                "ok",
                {
                    "estimate": estimate.to_dict(),
                    "written_ratio_pct": written,
                    "baseline_ratio_pct": baseline,
                },
            )
            self._progress("done", reason)
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
            journal.finalize("cancelled", {"reason": str(exc)})
            return GraphicalInertiaResult(
                axis=axis,
                status="cancelled",
                reason=str(exc) or "cancelled",
                journal_dir=journal.dir,
            )
        except GraphicalInertiaError as exc:
            LOG.warning("graphical inertia failed: %s", exc)
            journal.event("error", "failed", str(exc))
            journal.finalize("failed", {"reason": str(exc)})
            return GraphicalInertiaResult(
                axis=axis,
                status="failed",
                reason=str(exc),
                journal_dir=journal.dir,
            )
        except Exception as exc:
            LOG.exception("graphical inertia crashed")
            journal.event(
                "error",
                "exception",
                f"{type(exc).__name__}: {exc}",
                traceback=traceback.format_exc(),
            )
            journal.finalize("failed", {"reason": str(exc)})
            return GraphicalInertiaResult(
                axis=axis,
                status="failed",
                reason=str(exc),
                journal_dir=journal.dir,
            )

    def _pick_stroke(self, stroke: float, state: Dict[str, Any]) -> float:
        stroke = abs(float(stroke))
        pos = state.get("position")
        lo = state.get("min_limit")
        hi = state.get("max_limit")
        homed = state.get("homed")
        if homed and pos is not None and lo is not None and hi is not None:
            room_pos = float(hi) - float(pos)
            room_neg = float(pos) - float(lo)
            # Prefer the direction with more room; require full stroke clearance.
            if room_pos >= stroke and room_pos >= room_neg:
                return stroke
            if room_neg >= stroke:
                return -stroke
            raise GraphicalInertiaError(
                f"need {stroke:g} {axis_unit(self.cfg.axis)} clearance; "
                f"room +{room_pos:.1f} / -{room_neg:.1f}. Park mid-travel."
            )
        # Unhomed: go positive and rely on operator clearance confirm.
        return stroke

    def _fail(self, reason: str) -> GraphicalInertiaResult:
        if self._journal:
            self._journal.finalize("failed", {"reason": reason})
        return GraphicalInertiaResult(
            axis=self.cfg.axis,
            status="failed",
            reason=reason,
            journal_dir=self._journal.dir if self._journal else None,
        )

    def _check_cancel(self) -> None:
        if self._cancel.is_set():
            raise GraphicalInertiaCancelled("cancelled")

    def _progress(self, phase: str, message: str) -> None:
        if self._progress_fn:
            try:
                self._progress_fn(phase, message)
            except Exception:
                LOG.exception("progress callback failed")
