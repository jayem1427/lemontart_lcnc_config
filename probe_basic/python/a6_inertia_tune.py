"""Drive-internal (F30.10) inertia auto-tune for A6-EC / LinuxCNC.

Tries to run the servo's offline inertia identification over EtherCAT and
read the resulting load inertia ratio (C00.06). See docs/INERTIA_TUNE.md.

Critical safety knobs (not blind vendor defaults):
  - C07.04 revolutions — computed from soft-limit room at the current pose
  - drive 6065 — temporarily widened so CSP hold + F30 motion do not Er47
Everything else uses conservative defaults shown in the confirm dialog.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from a6_servo_tune import (
    AXES,
    SDO_FOLLOWING_ERROR,
    AxisTuneParams,
    apply_axis_params,
    axis_unit,
    ethercat_download_u16,
    ethercat_download_u32,
    ethercat_upload_u16,
    ethercat_upload_u32,
    machine_is_on,
    read_axis_params,
    set_machine_enabled,
    unit_to_counts,
    wait_for_axis_disabled,
)

try:
    import linuxcnc
except ImportError:  # pragma: no cover
    linuxcnc = None  # type: ignore

LOG = logging.getLogger(__name__)

ENGINE_VERSION = "0.1.0"

# Panel / EtherCAT map (A6-EC manual):
#   C07.* → 0x2007, sub = yy+1
#   F30.* → 0x2030, sub = yy+1
SDO_C07_MODE = (0x2007, 0x01)  # C07.00
SDO_C07_SPEED = (0x2007, 0x02)  # C07.01, rpm
SDO_C07_ACCEL = (0x2007, 0x03)  # C07.02, ms
SDO_C07_TORQUE = (0x2007, 0x04)  # C07.03, 0.1%
SDO_C07_REVS = (0x2007, 0x05)  # C07.04, 0.01 rev
SDO_F30_INERTIA = (0x2030, 0x11)  # F30.10, 1 = enable

# 17-bit encoder, 10 mm pitch on XYZ; A SCALE is counts/deg → 360°/rev.
MM_PER_MOTOR_REV = 10.0
DEG_PER_MOTOR_REV = 360.0

MIN_REVS = 0.5  # vendor failure floor
MAX_REVS_CAP = 2.0  # vendor default; never ask for more than this
TRAVEL_SAFETY = 0.75  # keep 25% soft-limit margin each side

# Conservative identification defaults (shown to the operator; overridable).
DEFAULT_SPEED_RPM = 300  # >150 rpm vendor minimum, softer than 500 default
DEFAULT_ACCEL_MS = 100
DEFAULT_TORQUE_01PCT = 120  # 12.0% — slightly under vendor 15%

# While F30 moves under CSP, widen 6065 so the drive does not Er47.
TEMP_FERROR_UNIT = 50.0  # mm or deg


class InertiaTuneError(RuntimeError):
    """Fatal campaign error (nothing committed, or reverted)."""


class InertiaTuneCancelled(RuntimeError):
    """Operator cancelled."""


def default_journal_root() -> str:
    here = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return os.path.join(here, "logs", "tuning", "inertia")


def motor_unit_per_rev(axis: str) -> float:
    """Axis units (mm or deg) per motor revolution."""
    if AXES[axis]["linear"]:
        return MM_PER_MOTOR_REV
    return DEG_PER_MOTOR_REV


def units_to_revs(axis: str, distance: float) -> float:
    return abs(float(distance)) / motor_unit_per_rev(axis)


def revs_to_units(axis: str, revs: float) -> float:
    return abs(float(revs)) * motor_unit_per_rev(axis)


def revs_to_raw(revs: float) -> int:
    """C07.04 raw = revolutions × 100 (0.01 r)."""
    return max(10, int(round(float(revs) * 100.0)))


def raw_to_revs(raw: int) -> float:
    return float(raw) / 100.0


@dataclass
class InertiaTunePlan:
    """Resolved C07.* + travel numbers for one campaign."""

    axis: str
    speed_rpm: int = DEFAULT_SPEED_RPM
    accel_ms: int = DEFAULT_ACCEL_MS
    torque_01pct: int = DEFAULT_TORQUE_01PCT
    revolutions: float = 1.0
    stroke_unit: float = 10.0
    room_pos: float = 0.0
    room_neg: float = 0.0
    position: Optional[float] = None
    min_limit: Optional[float] = None
    max_limit: Optional[float] = None
    homed: Optional[bool] = None

    def describe(self) -> str:
        unit = axis_unit(self.axis)
        return (
            f"{self.revolutions:.2f} rev (~{self.stroke_unit:.1f} {unit} stroke), "
            f"{self.speed_rpm} rpm, accel {self.accel_ms} ms, "
            f"torque {self.torque_01pct / 10.0:.1f}%"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "axis": self.axis,
            "speed_rpm": self.speed_rpm,
            "accel_ms": self.accel_ms,
            "torque_01pct": self.torque_01pct,
            "revolutions": self.revolutions,
            "stroke_unit": self.stroke_unit,
            "room_pos": self.room_pos,
            "room_neg": self.room_neg,
            "position": self.position,
            "min_limit": self.min_limit,
            "max_limit": self.max_limit,
            "homed": self.homed,
        }


def plan_inertia_tune(
    axis: str,
    *,
    position: Optional[float],
    min_limit: Optional[float],
    max_limit: Optional[float],
    homed: Optional[bool] = None,
    speed_rpm: int = DEFAULT_SPEED_RPM,
    accel_ms: int = DEFAULT_ACCEL_MS,
    torque_01pct: int = DEFAULT_TORQUE_01PCT,
    max_revs: float = MAX_REVS_CAP,
    min_revs: float = MIN_REVS,
    safety: float = TRAVEL_SAFETY,
) -> InertiaTunePlan:
    """Pick C07.04 from soft-limit room; keep other C07 values at safe defaults.

    Raises InertiaTuneError when there is not enough clearance for ≥ min_revs
    in *both* directions (F30 oscillates).
    """
    if axis not in AXES:
        raise InertiaTuneError(f"unknown axis {axis!r}")

    plan = InertiaTunePlan(
        axis=axis,
        speed_rpm=int(speed_rpm),
        accel_ms=int(accel_ms),
        torque_01pct=int(torque_01pct),
        position=position,
        min_limit=min_limit,
        max_limit=max_limit,
        homed=homed,
    )

    if position is None or min_limit is None or max_limit is None:
        if homed is False:
            raise InertiaTuneError(
                f"axis {axis} is not homed — cannot compute a safe F30 travel "
                f"from soft limits. Home first, park mid-travel, then retry."
            )
        raise InertiaTuneError(
            f"axis {axis}: position / soft limits unavailable — cannot plan "
            f"a safe C07.04 stroke"
        )

    room_pos = float(max_limit) - float(position)
    room_neg = float(position) - float(min_limit)
    plan.room_pos = room_pos
    plan.room_neg = room_neg
    room = min(room_pos, room_neg) * float(safety)
    if room <= 0:
        raise InertiaTuneError(
            f"axis {axis} has no bidirectional clearance at pos={position:g} "
            f"(limits {min_limit:g}..{max_limit:g})"
        )

    revs = min(float(max_revs), units_to_revs(axis, room))
    if revs + 1e-9 < float(min_revs):
        need = revs_to_units(axis, min_revs)
        raise InertiaTuneError(
            f"axis {axis}: only ~{room:.2f} {axis_unit(axis)} safe room each "
            f"way (after {safety:.0%} margin); need ≥{need:.1f} "
            f"{axis_unit(axis)} ({min_revs:g} rev) for F30. Park closer to "
            f"mid-travel and retry."
        )

    plan.revolutions = round(revs, 2)
    plan.stroke_unit = round(revs_to_units(axis, plan.revolutions), 2)
    return plan


@dataclass
class InertiaTuneResult:
    axis: str
    status: str  # ok | failed | cancelled | dry-run
    reason: str
    journal_dir: Optional[str] = None
    baseline_ratio_pct: Optional[float] = None
    final_ratio_pct: Optional[float] = None
    plan: Optional[InertiaTunePlan] = None

    def summary(self) -> str:
        bits = [f"{self.status}: {self.reason}"]
        if self.baseline_ratio_pct is not None and self.final_ratio_pct is not None:
            bits.append(
                f"C00.06 {self.baseline_ratio_pct:.0f}% → {self.final_ratio_pct:.0f}%"
            )
        elif self.final_ratio_pct is not None:
            bits.append(f"C00.06 → {self.final_ratio_pct:.0f}%")
        return " | ".join(bits)


class _Journal:
    def __init__(self, root: str, axis: str, plan: InertiaTunePlan) -> None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.dir = os.path.join(root, f"{stamp}_{axis}")
        self._events: List[Dict[str, Any]] = []
        self._t0 = time.time()
        self._md_path: Optional[str] = None
        self._json_path: Optional[str] = None
        try:
            os.makedirs(self.dir, exist_ok=True)
            self._md_path = os.path.join(self.dir, "journal.md")
            self._json_path = os.path.join(self.dir, "journal.json")
            with open(self._md_path, "w", encoding="utf-8") as handle:
                handle.write(
                    f"# Inertia tune (F30.10) — axis {axis}\n\n"
                    f"- started: {datetime.now().isoformat(timespec='seconds')}\n"
                    f"- engine: a6_inertia_tune v{ENGINE_VERSION}\n"
                    f"- plan: {plan.describe()}\n\n"
                )
            self.event("setup", "config", "campaign plan", plan=plan.to_dict())
        except Exception:
            LOG.exception("inertia journal init failed")

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
        LOG.info("inertia[%s/%s]: %s", phase, kind, message)
        if self._md_path is None:
            return
        try:
            with open(self._md_path, "a", encoding="utf-8") as handle:
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
                os.fsync(handle.fileno())
        except Exception:
            LOG.exception("inertia journal.md append failed")
        try:
            if self._json_path:
                tmp = self._json_path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as handle:
                    json.dump({"events": self._events}, handle, indent=2, default=str)
                os.replace(tmp, self._json_path)
        except Exception:
            LOG.exception("inertia journal.json write failed")

    def finalize(self, status: str, summary: Dict[str, Any]) -> None:
        self.event("finalize", "result", f"status: {status}", **summary)
        if self._md_path is None:
            return
        try:
            with open(self._md_path, "a", encoding="utf-8") as handle:
                handle.write(
                    f"\n---\n\n**FINAL STATUS: {status.upper()}** — "
                    f"{datetime.now().isoformat(timespec='seconds')}\n"
                )
        except Exception:
            LOG.exception("inertia journal finalize failed")


class HardwareInertiaIO:
    """Real-machine IO for F30 inertia identification."""

    name = "hardware"

    def __init__(self) -> None:
        if linuxcnc is None:
            raise InertiaTuneError(
                "linuxcnc Python module not available — "
                "run inside the LinuxCNC environment"
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
            return False, "machine is not ON (turn it on first)"
        if self._stat.interp_state != linuxcnc.INTERP_IDLE:
            return False, "a program / MDI command is still running"
        return True, "ok"

    def axis_state(self, axis: str) -> Dict[str, Any]:
        idx = {"X": 0, "Y": 1, "Z": 2, "A": 3}.get(axis, 0)
        joint = AXES[axis]["joint"]
        state: Dict[str, Any] = {
            "homed": None,
            "position": None,
            "min_limit": None,
            "max_limit": None,
            "fault": None,
        }
        try:
            self._stat.poll()
            state["homed"] = bool(self._stat.joint[joint]["homed"])
            state["position"] = float(self._stat.actual_position[idx])
            state["min_limit"] = float(self._stat.axis[idx]["min_position_limit"])
            state["max_limit"] = float(self._stat.axis[idx]["max_position_limit"])
        except Exception:
            LOG.exception("axis_state read failed")
        try:
            from a6_servo_tune import hal_getp

            state["fault"] = bool(
                hal_getp(f"cia402.{AXES[axis]['joint']}.drv-fault")
            )
        except Exception:
            state["fault"] = None
        return state

    def read_inertia_ratio(self, axis: str) -> float:
        params = read_axis_params(axis)
        if "inertia_ratio_pct" not in params.values:
            raise InertiaTuneError("C00.06 inertia ratio unread")
        return float(params.values["inertia_ratio_pct"])

    def read_u16(self, axis: str, index: int, sub: int) -> int:
        return ethercat_upload_u16(AXES[axis]["slave"], index, sub)

    def write_u16(self, axis: str, index: int, sub: int, value: int) -> None:
        ethercat_download_u16(AXES[axis]["slave"], index, sub, int(value))

    def write_inertia_ratio(self, axis: str, pct: float) -> None:
        params = AxisTuneParams(values={"inertia_ratio_pct": float(pct)})
        result = apply_axis_params(
            axis, params, cycle_enable=True, keys=["inertia_ratio_pct"]
        )
        if "inertia_ratio_pct" not in result.get("written_keys", []):
            failed = result.get("failed_keys", [])
            raise InertiaTuneError(f"failed to write C00.06: {failed}")

    def set_machine(self, enable: bool) -> None:
        set_machine_enabled(enable)
        if not enable:
            # Best-effort per-axis settle; machine OFF should drop all enables.
            for axis in AXES:
                wait_for_axis_disabled(axis, timeout_s=2.0)

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


@dataclass
class InertiaTuneConfig:
    axis: str
    speed_rpm: int = DEFAULT_SPEED_RPM
    accel_ms: int = DEFAULT_ACCEL_MS
    torque_01pct: int = DEFAULT_TORQUE_01PCT
    dry_run: bool = False
    timeout_s: float = 90.0
    temp_ferror_unit: float = TEMP_FERROR_UNIT
    poll_s: float = 0.25
    motion_detect_unit: float = 0.05  # mm/deg — proof F30 actually moved

    @classmethod
    def for_axis(cls, axis: str, **kwargs: Any) -> "InertiaTuneConfig":
        if axis not in AXES:
            raise ValueError(f"unknown axis {axis!r}")
        return cls(axis=axis, **kwargs)


class InertiaTuner:
    """State machine: PREFLIGHT → PLAN → ARM → RUN → CAPTURE → RESTORE."""

    def __init__(
        self,
        config: InertiaTuneConfig,
        io: Optional[Any] = None,
        *,
        journal_root: Optional[str] = None,
        progress: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self.cfg = config
        self.io = io if io is not None else HardwareInertiaIO()
        self.journal_root = journal_root or default_journal_root()
        self._progress_fn = progress
        self._cancel = threading.Event()
        self._journal: Optional[_Journal] = None
        self._plan: Optional[InertiaTunePlan] = None
        self._baseline_ratio: Optional[float] = None
        self._saved_ferror: Optional[int] = None
        self._saved_c07: Dict[str, int] = {}
        self._ferror_widened = False
        self._c07_written = False
        self._f30_armed = False

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> InertiaTuneResult:
        axis = self.cfg.axis
        try:
            self._progress("preflight", "checking machine…")
            ok, why = self.io.machine_ready()
            if not ok:
                return self._fail(why)

            state = self.io.axis_state(axis)
            plan = plan_inertia_tune(
                axis,
                position=state.get("position"),
                min_limit=state.get("min_limit"),
                max_limit=state.get("max_limit"),
                homed=state.get("homed"),
                speed_rpm=self.cfg.speed_rpm,
                accel_ms=self.cfg.accel_ms,
                torque_01pct=self.cfg.torque_01pct,
            )
            self._plan = plan
            self._journal = _Journal(self.journal_root, axis, plan)
            self._journal.event("preflight", "ok", "machine ready", state=state)

            self._check_cancel()
            self._baseline_ratio = float(self.io.read_inertia_ratio(axis))
            self._journal.event(
                "baseline",
                "read",
                f"C00.06 = {self._baseline_ratio:.0f}%",
                ratio_pct=self._baseline_ratio,
            )

            if self.cfg.dry_run:
                self._journal.finalize(
                    "dry-run",
                    {
                        "baseline_ratio_pct": self._baseline_ratio,
                        "plan": plan.to_dict(),
                    },
                )
                return InertiaTuneResult(
                    axis=axis,
                    status="dry-run",
                    reason=f"would run F30.10 with {plan.describe()}",
                    journal_dir=self._journal.dir,
                    baseline_ratio_pct=self._baseline_ratio,
                    final_ratio_pct=self._baseline_ratio,
                    plan=plan,
                )

            self._arm_c07(plan)
            self._widen_ferror()
            final = self._run_f30(plan)
            self._restore_safety()

            changed = abs(final - self._baseline_ratio) >= 1.0
            status = "ok"
            reason = (
                f"F30 complete — C00.06 {self._baseline_ratio:.0f}% → {final:.0f}%"
                if changed
                else (
                    f"F30 finished but C00.06 unchanged at {final:.0f}% "
                    f"(drive may have rejected the estimate — check journal)"
                )
            )
            self._journal.finalize(
                status,
                {
                    "baseline_ratio_pct": self._baseline_ratio,
                    "final_ratio_pct": final,
                    "changed": changed,
                    "plan": plan.to_dict(),
                },
            )
            self._progress("done", reason)
            return InertiaTuneResult(
                axis=axis,
                status=status,
                reason=reason,
                journal_dir=self._journal.dir,
                baseline_ratio_pct=self._baseline_ratio,
                final_ratio_pct=final,
                plan=plan,
            )
        except InertiaTuneCancelled as exc:
            self._restore_safety(best_effort=True)
            if self._journal:
                self._journal.finalize(
                    "cancelled",
                    {"reason": str(exc), "baseline_ratio_pct": self._baseline_ratio},
                )
            return InertiaTuneResult(
                axis=axis,
                status="cancelled",
                reason=str(exc) or "cancelled",
                journal_dir=self._journal.dir if self._journal else None,
                baseline_ratio_pct=self._baseline_ratio,
                plan=self._plan,
            )
        except InertiaTuneError as exc:
            LOG.warning("inertia tune failed: %s", exc)
            if self._journal:
                self._journal.event("error", "failed", str(exc))
            self._restore_safety(best_effort=True)
            if self._journal:
                self._journal.finalize(
                    "failed",
                    {"reason": str(exc), "baseline_ratio_pct": self._baseline_ratio},
                )
            return InertiaTuneResult(
                axis=axis,
                status="failed",
                reason=str(exc),
                journal_dir=self._journal.dir if self._journal else None,
                baseline_ratio_pct=self._baseline_ratio,
                plan=self._plan,
            )
        except Exception as exc:
            LOG.exception("inertia tune failed")
            if self._journal:
                self._journal.event(
                    "error",
                    "exception",
                    f"{type(exc).__name__}: {exc}",
                    traceback=traceback.format_exc(),
                )
            self._restore_safety(best_effort=True)
            if self._journal:
                self._journal.finalize(
                    "failed",
                    {"reason": str(exc), "baseline_ratio_pct": self._baseline_ratio},
                )
            return InertiaTuneResult(
                axis=axis,
                status="failed",
                reason=str(exc),
                journal_dir=self._journal.dir if self._journal else None,
                baseline_ratio_pct=self._baseline_ratio,
                plan=self._plan,
            )

    # -- phases ---------------------------------------------------------------

    def _arm_c07(self, plan: InertiaTunePlan) -> None:
        """Write C07.* at stop (machine OFF), snapshot prior values."""
        axis = self.cfg.axis
        self._progress("arm", "writing C07 inertia-ID limits (machine OFF)…")
        self._check_cancel()

        # Snapshot existing C07 (best-effort — some may be unread).
        for name, sdo in (
            ("mode", SDO_C07_MODE),
            ("speed", SDO_C07_SPEED),
            ("accel", SDO_C07_ACCEL),
            ("torque", SDO_C07_TORQUE),
            ("revs", SDO_C07_REVS),
        ):
            try:
                self._saved_c07[name] = int(self.io.read_u16(axis, sdo[0], sdo[1]))
            except Exception as exc:
                self._j().event(
                    "arm", "warning", f"could not snapshot C07 {name}: {exc}"
                )

        was_on = True
        try:
            was_on = bool(self.io.machine_ready()[0])
        except Exception:
            was_on = machine_is_on()

        self.io.set_machine(False)
        try:
            revs_raw = revs_to_raw(plan.revolutions)
            writes = [
                (SDO_C07_SPEED, plan.speed_rpm, "C07.01 speed"),
                (SDO_C07_ACCEL, plan.accel_ms, "C07.02 accel"),
                (SDO_C07_TORQUE, plan.torque_01pct, "C07.03 torque"),
                (SDO_C07_REVS, revs_raw, "C07.04 revolutions"),
            ]
            for (index, sub), value, label in writes:
                self.io.write_u16(axis, index, sub, value)
                got = self.io.read_u16(axis, index, sub)
                if got != int(value):
                    raise InertiaTuneError(
                        f"{label} verify failed wrote={value} read={got}"
                    )
                self._j().event(
                    "arm",
                    "write",
                    f"{label} = {value}",
                    sdo=f"0x{index:04X}:{sub:02X}",
                    value=value,
                )
            self._c07_written = True
        finally:
            if was_on:
                self.io.set_machine(True)

    def _widen_ferror(self) -> None:
        """Temporarily raise 6065 so CSP hold + F30 motion does not Er47."""
        axis = self.cfg.axis
        self._progress("arm", "widening drive 6065 for F30 motion…")
        try:
            self._saved_ferror = int(self._read_ferror_counts(axis))
        except Exception as exc:
            raise InertiaTuneError(f"could not read 6065: {exc}") from exc

        target = max(1, unit_to_counts(axis, self.cfg.temp_ferror_unit))
        self._write_ferror_counts(axis, target)
        self._ferror_widened = True
        self._j().event(
            "arm",
            "ferror",
            f"6065 {self._saved_ferror} → {target} counts "
            f"(~{self.cfg.temp_ferror_unit:g} {axis_unit(axis)})",
            previous=self._saved_ferror,
            temporary=target,
        )

    def _run_f30(self, plan: InertiaTunePlan) -> float:
        axis = self.cfg.axis
        self._progress("run", f"triggering F30.10 ({plan.describe()})…")
        self._check_cancel()

        ok, why = self.io.machine_ready()
        if not ok:
            raise InertiaTuneError(f"machine not ready to run F30: {why}")

        start_pos = self.io.axis_state(axis).get("position")
        index, sub = SDO_F30_INERTIA

        try:
            self.io.write_u16(axis, index, sub, 1)
            self._f30_armed = True
            self._j().event("run", "trigger", "F30.10 = 1 (enable)")
        except Exception as exc:
            raise InertiaTuneError(
                f"F30.10 write failed — EtherCAT may not start keypad "
                f"inertia ID on this firmware ({exc}). C07 limits were set; "
                f"you can still run F30 from the drive panel / vendor tool, "
                f"then re-read C00.06."
            ) from exc

        deadline = time.monotonic() + float(self.cfg.timeout_s)
        saw_motion = False
        stable_reads = 0
        last_ratio = self._baseline_ratio if self._baseline_ratio is not None else 0.0
        f30_clear = False

        while time.monotonic() < deadline:
            self._check_cancel()
            self.io.sleep(self.cfg.poll_s)

            state = self.io.axis_state(axis)
            if state.get("fault"):
                raise InertiaTuneError(
                    "drive fault during F30 (Er51.x = inertia ID failure is "
                    "common — soften C07 speed/torque or check mechanics)"
                )

            pos = state.get("position")
            if (
                start_pos is not None
                and pos is not None
                and abs(pos - start_pos) >= self.cfg.motion_detect_unit
            ):
                if not saw_motion:
                    self._j().event(
                        "run",
                        "motion",
                        f"axis moved Δ={pos - start_pos:+.3f} {axis_unit(axis)}",
                        position=pos,
                    )
                    self._progress("run", "F30 motion detected…")
                saw_motion = True

            try:
                flag = int(self.io.read_u16(axis, index, sub))
                if flag == 0 and self._f30_armed:
                    f30_clear = True
            except Exception:
                flag = -1

            try:
                ratio = float(self.io.read_inertia_ratio(axis))
            except Exception:
                continue

            if abs(ratio - last_ratio) < 0.5 and (
                saw_motion or f30_clear or abs(ratio - (self._baseline_ratio or 0)) >= 1.0
            ):
                stable_reads += 1
            else:
                stable_reads = 0
            last_ratio = ratio

            # Done: F30 cleared, or ratio changed and held stable after motion.
            if f30_clear and stable_reads >= 3:
                self._j().event(
                    "run",
                    "complete",
                    f"F30 cleared; C00.06={ratio:.0f}%",
                    ratio_pct=ratio,
                    saw_motion=saw_motion,
                )
                self._f30_armed = False
                return ratio
            if saw_motion and abs(ratio - (self._baseline_ratio or 0)) >= 1.0 and stable_reads >= 4:
                self._j().event(
                    "run",
                    "complete",
                    f"ratio settled at {ratio:.0f}% (F30 flag={flag})",
                    ratio_pct=ratio,
                    f30_flag=flag,
                )
                try:
                    self.io.write_u16(axis, index, sub, 0)
                except Exception:
                    pass
                self._f30_armed = False
                return ratio

            self._progress(
                "run",
                f"waiting… C00.06={ratio:.0f}% motion={'yes' if saw_motion else 'no'}",
            )

        # Timeout — try to clear F30 and report.
        try:
            self.io.write_u16(axis, index, sub, 0)
            self._f30_armed = False
        except Exception:
            pass
        final = float(self.io.read_inertia_ratio(axis))
        if abs(final - (self._baseline_ratio or 0)) >= 1.0:
            self._j().event(
                "run",
                "timeout-changed",
                f"timeout but C00.06 changed → {final:.0f}%",
                ratio_pct=final,
                saw_motion=saw_motion,
            )
            return final
        raise InertiaTuneError(
            f"F30 timed out after {self.cfg.timeout_s:.0f}s "
            f"(motion={'yes' if saw_motion else 'no'}, C00.06={final:.0f}%). "
            f"If the axis never moved, EtherCAT may not start F30.10 — use "
            f"the drive panel (C07 already configured) and re-read C00.06."
        )

    def _restore_safety(self, *, best_effort: bool = False) -> None:
        """Clear F30, restore 6065, optionally restore C07."""
        axis = self.cfg.axis
        errors: List[str] = []

        if self._f30_armed:
            try:
                self.io.write_u16(axis, SDO_F30_INERTIA[0], SDO_F30_INERTIA[1], 0)
                self._f30_armed = False
                if self._journal:
                    self._j().event("restore", "f30", "F30.10 cleared to 0")
            except Exception as exc:
                errors.append(f"F30.10 clear: {exc}")

        if self._ferror_widened and self._saved_ferror is not None:
            try:
                # Prefer machine OFF for 6065 write reliability.
                was_on = False
                try:
                    was_on = bool(self.io.machine_ready()[0])
                except Exception:
                    was_on = machine_is_on()
                if was_on:
                    self.io.set_machine(False)
                self._write_ferror_counts(axis, int(self._saved_ferror))
                self._ferror_widened = False
                if self._journal:
                    self._j().event(
                        "restore",
                        "ferror",
                        f"6065 restored to {self._saved_ferror}",
                    )
                if was_on:
                    self.io.set_machine(True)
            except Exception as exc:
                errors.append(f"6065 restore: {exc}")

        if errors and not best_effort:
            raise InertiaTuneError(
                "CRITICAL — safety restore incomplete: " + "; ".join(errors)
            )
        if errors and self._journal:
            self._j().event(
                "restore",
                "CRITICAL",
                "safety restore incomplete",
                errors=errors,
                saved_ferror=self._saved_ferror,
                saved_c07=self._saved_c07,
            )

    # -- helpers --------------------------------------------------------------

    def _read_ferror_counts(self, axis: str) -> int:
        """6065 is uint32 on A6-EC; sim IO may only expose write_u16/read_u16."""
        index, sub = SDO_FOLLOWING_ERROR
        if hasattr(self.io, "read_u32"):
            return int(self.io.read_u32(axis, index, sub))
        try:
            return int(ethercat_upload_u32(AXES[axis]["slave"], index, sub))
        except Exception:
            return int(self.io.read_u16(axis, index, sub))

    def _write_ferror_counts(self, axis: str, counts: int) -> None:
        index, sub = SDO_FOLLOWING_ERROR
        if hasattr(self.io, "write_u32"):
            self.io.write_u32(axis, index, sub, int(counts))
            got = int(self.io.read_u32(axis, index, sub))
            if got != int(counts):
                raise InertiaTuneError(
                    f"6065 verify failed wrote={counts} read={got}"
                )
            return
        try:
            ethercat_download_u32(AXES[axis]["slave"], index, sub, int(counts))
            got = ethercat_upload_u32(AXES[axis]["slave"], index, sub)
            if got != int(counts):
                raise InertiaTuneError(
                    f"6065 verify failed wrote={counts} read={got}"
                )
        except InertiaTuneError:
            raise
        except Exception:
            self.io.write_u16(axis, index, sub, int(counts) & 0xFFFF)

    def _fail(self, reason: str) -> InertiaTuneResult:
        return InertiaTuneResult(
            axis=self.cfg.axis,
            status="failed",
            reason=reason,
            plan=self._plan,
        )

    def _check_cancel(self) -> None:
        if self._cancel.is_set():
            raise InertiaTuneCancelled("cancelled by operator")

    def _progress(self, phase: str, message: str) -> None:
        if self._progress_fn is not None:
            try:
                self._progress_fn(phase, message)
            except Exception:
                LOG.exception("progress callback failed")

    def _j(self) -> _Journal:
        assert self._journal is not None
        return self._journal
