"""Semi-auto tune trial helpers: NGC stimulus, plot export, LLM paste pack.

Used by the Servo Tuning tab. Does **not** auto-apply LLM suggestions.
Drive 60F4 (DRIVE FERR) is the tuning metric — LinuxCNC FERROR is untouched.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

LOG = logging.getLogger(__name__)

try:
    import linuxcnc
except ImportError:  # pragma: no cover
    linuxcnc = None  # type: ignore

from a6_servo_tune import (  # noqa: E402
    AXES,
    AxisTuneParams,
    NOTCH_LABELS,
    axis_unit,
    machine_is_on,
    repo_root,
)

# Frozen campaign stimuli — do not edit mid-session if comparing trials.
AXIS_TUNING_NGC: Dict[str, str] = {
    "X": "x_tuning.ngc",
    "Y": "y_tuning.ngc",
    "Z": "z_tuning.ngc",
    "A": "a_tuning.ngc",
}

# Keys highlighted in the LLM paste pack (1st set + switchover + notch).
PASTE_FOCUS_KEYS: Tuple[str, ...] = (
    "stiffness_level",
    "manual_mode",
    "inertia_ratio_pct",
    "pos_gain_rad_s",
    "speed_gain_hz",
    "integral_ms",
    "torque_filter_hz",
    "pos_gain_2_rad_s",
    "speed_gain_2_hz",
    "integral_2_ms",
    "torque_filter_2_hz",
    "gain_sw_mode",
    "adaptive_notch",
)

GAIN_SW_MODE_LABELS: Dict[int, str] = {
    0: "Fixed to 1st gain set",
    1: "Fixed to 2nd gain set",
    2: "Position deviation",
    3: "Torque command",
    4: "Speed command",
    5: "Acceleration",
    6: "Position command",
    7: "Reserved",
    8: "Reserved",
}

LLM_PLAYBOOK_PATH = "SERVO_TUNING_LLM.md"
SOFT_PRESET_NAME = "soft"

# Plot capture window during a trial (seconds of samples retained).
TRIAL_PLOT_WINDOW_S = 180.0
DEFAULT_PLOT_WINDOW_S = 5.0


@dataclass
class TrialArtifact:
    """Paths and text produced by one completed tune trial."""

    axis: str
    trial_id: str
    dir_path: str
    png_path: str
    meta_path: str
    paste_path: str
    csv_path: str
    paste_text: str
    ngc_path: str
    peak_abs: float
    sample_count: int
    notes: str = ""


def tuning_logs_dir() -> str:
    path = os.path.join(repo_root(), "logs", "tuning")
    os.makedirs(path, exist_ok=True)
    return path


def nc_files_dir() -> str:
    return os.path.join(repo_root(), "nc_files")


def resolve_tuning_ngc(axis: str) -> str:
    axis = axis.upper()
    if axis not in AXIS_TUNING_NGC:
        raise ValueError(f"unsupported axis {axis!r}")
    path = os.path.join(nc_files_dir(), AXIS_TUNING_NGC[axis])
    if not os.path.isfile(path):
        raise FileNotFoundError(f"tuning NGC missing: {path}")
    return os.path.abspath(path)


def make_trial_id(axis: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{stamp}_{axis.upper()}"


def trial_dir(trial_id: str) -> str:
    path = os.path.join(tuning_logs_dir(), trial_id)
    os.makedirs(path, exist_ok=True)
    return path


def short_gains_tag(params: AxisTuneParams) -> str:
    """Compact title burn-in: pos/speed/integral/filter."""
    parts: List[str] = []
    for key, fmt in (
        ("pos_gain_rad_s", "{:.0f}"),
        ("speed_gain_hz", "{:.0f}"),
        ("integral_ms", "{:.1f}"),
        ("torque_filter_hz", "{:.0f}"),
    ):
        if key in params.values:
            parts.append(fmt.format(params.get(key)))
        else:
            parts.append("?")
    return "/".join(parts)


def format_gains_block(params: AxisTuneParams, axis: str) -> str:
    """Structured gains for the LLM (text, not OCR)."""
    unit = axis_unit(axis)
    lines = [f"axis: {axis}", f"units: {unit}"]
    for key in PASTE_FOCUS_KEYS:
        if key not in params.values:
            continue
        value = params.get(key)
        if key == "gain_sw_mode":
            mode = int(value)
            label = GAIN_SW_MODE_LABELS.get(mode, "unknown")
            lines.append(f"{key}: {mode} ({label})")
        elif key == "adaptive_notch":
            mode = int(value)
            label = NOTCH_LABELS.get(mode, str(mode))
            lines.append(f"{key}: {mode} ({label})")
        elif key == "manual_mode":
            mode = int(value)
            label = {0: "manual", 1: "standard", 2: "positioning"}.get(
                mode, str(mode)
            )
            lines.append(f"{key}: {mode} ({label})")
        elif isinstance(value, float) and not value.is_integer():
            lines.append(f"{key}: {value:g}")
        else:
            lines.append(f"{key}: {value:g}")
    # Include any other live keys briefly so nothing important is hidden.
    extras = sorted(k for k in params.values.keys() if k not in PASTE_FOCUS_KEYS)
    if extras:
        lines.append("other:")
        for key in extras:
            lines.append(f"  {key}: {params.get(key):g}")
    return "\n".join(lines)


def build_paste_pack(
    *,
    axis: str,
    trial_id: str,
    params: AxisTuneParams,
    ngc_name: str,
    peak_abs: float,
    unit_label: str,
    png_name: str,
    operator_notes: str = "",
) -> str:
    """Text the operator pastes with (or after) the plot image."""
    notes = (operator_notes or "").strip() or "(none — add buzz y/n if relevant)"
    return "\n".join(
        [
            "SEMI-AUTO SERVO TUNE TRIAL",
            f"Follow {LLM_PLAYBOOK_PATH} — diagnose from the plot; one bounded change.",
            "",
            f"trial_id: {trial_id}",
            f"ngc: {ngc_name}  (frozen campaign move — do not change mid-compare)",
            f"plot: {png_name}  (drive FERR / CiA 60F4 — NOT LinuxCNC joint.f-error)",
            f"peak_abs: {peak_abs:g} {unit_label}",
            "",
            "CURRENT GAINS:",
            format_gains_block(params, axis),
            "",
            f"operator_notes: {notes}",
            "",
            "Please: Read the waveform → suggest the next small change "
            "(zone order: filter/notch → speed → integral → position). "
            "Do not auto-apply; I will edit Pending and APPLY myself.",
        ]
    )


def preflight_machine(axis: str) -> None:
    """Raise RuntimeError if it is unsafe to open/run a tuning program."""
    if linuxcnc is None:
        raise RuntimeError("linuxcnc Python module not available")
    if axis.upper() not in AXES:
        raise ValueError(f"unsupported axis {axis!r}")

    stat = linuxcnc.stat()
    stat.poll()

    if stat.task_state == linuxcnc.STATE_ESTOP:
        raise RuntimeError("Machine is in ESTOP — clear ESTOP first.")
    if not machine_is_on():
        raise RuntimeError("Machine must be ON (amps enabled) before a tune trial.")
    if stat.interp_state != linuxcnc.INTERP_IDLE:
        raise RuntimeError("Interpreter is busy — abort or wait for idle first.")
    if hasattr(stat, "queue") and int(getattr(stat, "queue", 0) or 0) > 0:
        # Some builds expose motion queue; non-zero means still draining.
        pass


def open_tuning_program(axis: str) -> str:
    """Switch to AUTO and open the axis tuning NGC. Does not Cycle Start."""
    preflight_machine(axis)
    path = resolve_tuning_ngc(axis)
    stat = linuxcnc.stat()
    cmd = linuxcnc.command()

    cmd.mode(linuxcnc.MODE_AUTO)
    cmd.wait_complete()
    cmd.program_open(path)
    cmd.wait_complete()

    # Confirm open landed.
    deadline = time.time() + 3.0
    while time.time() < deadline:
        stat.poll()
        if os.path.abspath(stat.file or "") == path or os.path.basename(
            stat.file or ""
        ) == os.path.basename(path):
            return path
        time.sleep(0.05)
    # Some UIs report relative paths — still OK if mode is AUTO and idle.
    stat.poll()
    if stat.task_mode != linuxcnc.MODE_AUTO:
        raise RuntimeError("failed to enter AUTO mode for tuning NGC")
    return path


def start_auto_run() -> None:
    """Issue Cycle Start (AUTO_RUN) — caller must have confirmed with the operator."""
    if linuxcnc is None:
        raise RuntimeError("linuxcnc Python module not available")
    stat = linuxcnc.stat()
    stat.poll()
    if stat.task_state == linuxcnc.STATE_ESTOP:
        raise RuntimeError("Machine is in ESTOP — clear ESTOP first.")
    if not machine_is_on():
        raise RuntimeError("Machine must be ON before AUTO_RUN.")
    if stat.interp_state != linuxcnc.INTERP_IDLE:
        raise RuntimeError("cannot AUTO_RUN — interpreter not idle")
    if stat.task_mode != linuxcnc.MODE_AUTO:
        raise RuntimeError("cannot AUTO_RUN — not in AUTO mode (open the NGC first)")
    cmd = linuxcnc.command()
    cmd.auto(linuxcnc.AUTO_RUN, 0)


def program_is_running() -> bool:
    if linuxcnc is None:
        return False
    try:
        stat = linuxcnc.stat()
        stat.poll()
        return (
            stat.task_mode == linuxcnc.MODE_AUTO
            and stat.interp_state != linuxcnc.INTERP_IDLE
        )
    except Exception:
        return False


def machine_still_safe() -> Tuple[bool, str]:
    """Return (ok, reason). ok False means abort the trial capture."""
    if linuxcnc is None:
        return False, "linuxcnc module missing"
    try:
        stat = linuxcnc.stat()
        stat.poll()
        if stat.task_state == linuxcnc.STATE_ESTOP:
            return False, "ESTOP"
        if not (bool(stat.enabled) and stat.task_state == linuxcnc.STATE_ON):
            return False, "machine disabled"
        return True, ""
    except Exception as exc:
        return False, str(exc)


def write_samples_csv(
    path: str,
    samples: Sequence[float],
    *,
    sample_ms: float,
    unit_label: str,
) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(f"t_s,drive_ferr_{unit_label}\n")
        dt = max(sample_ms, 1.0) / 1000.0
        for i, value in enumerate(samples):
            handle.write(f"{i * dt:.4f},{value:.6f}\n")


def write_trial_meta(path: str, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def save_trial_artifacts(
    *,
    axis: str,
    trial_id: str,
    params: AxisTuneParams,
    samples: Sequence[float],
    sample_ms: float,
    unit_label: str,
    unit_mode: str,
    ngc_path: str,
    png_path: str,
    operator_notes: str = "",
    auto_run: bool = False,
    waited_for_cycle_start: bool = False,
) -> TrialArtifact:
    """Write CSV / meta / paste pack next to the PNG."""
    directory = trial_dir(trial_id)
    csv_path = os.path.join(directory, "drive_ferr.csv")
    meta_path = os.path.join(directory, "meta.json")
    paste_path = os.path.join(directory, "paste_pack.txt")

    finite = [float(v) for v in samples if v == v]
    peak = max((abs(v) for v in finite), default=0.0)
    write_samples_csv(csv_path, finite, sample_ms=sample_ms, unit_label=unit_label)

    paste = build_paste_pack(
        axis=axis,
        trial_id=trial_id,
        params=params,
        ngc_name=os.path.basename(ngc_path),
        peak_abs=peak,
        unit_label=unit_label,
        png_name=os.path.basename(png_path),
        operator_notes=operator_notes,
    )
    with open(paste_path, "w", encoding="utf-8") as handle:
        handle.write(paste)
        handle.write("\n")

    meta = {
        "trial_id": trial_id,
        "axis": axis,
        "created": datetime.now().isoformat(timespec="seconds"),
        "ngc": ngc_path,
        "png": png_path,
        "csv": csv_path,
        "paste_pack": paste_path,
        "unit_mode": unit_mode,
        "unit_label": unit_label,
        "sample_ms": sample_ms,
        "sample_count": len(finite),
        "peak_abs": peak,
        "auto_run": auto_run,
        "waited_for_cycle_start": waited_for_cycle_start,
        "operator_notes": operator_notes,
        "gains": {k: params.get(k) for k in params.values.keys()},
        "gains_tag": short_gains_tag(params),
        "playbook": LLM_PLAYBOOK_PATH,
    }
    write_trial_meta(meta_path, meta)

    return TrialArtifact(
        axis=axis,
        trial_id=trial_id,
        dir_path=directory,
        png_path=png_path,
        meta_path=meta_path,
        paste_path=paste_path,
        csv_path=csv_path,
        paste_text=paste,
        ngc_path=ngc_path,
        peak_abs=peak,
        sample_count=len(finite),
        notes=operator_notes,
    )


def copy_trial_to_clipboard(png_path: str, paste_text: str) -> str:
    """Put image + paste text on the Qt clipboard. Returns a short status note."""
    try:
        from qtpy.QtGui import QGuiApplication, QImage
        from qtpy.QtCore import QMimeData
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(f"Qt clipboard unavailable: {exc}") from exc

    app = QGuiApplication.instance()
    if app is None:
        raise RuntimeError("No QGuiApplication — clipboard needs a Qt app")

    image = QImage(png_path)
    if image.isNull():
        raise RuntimeError(f"failed to load trial PNG: {png_path}")

    mime = QMimeData()
    mime.setImageData(image)
    mime.setText(paste_text)
    app.clipboard().setMimeData(mime)
    return "clipboard: image + paste pack text"


def copy_text_to_clipboard(text: str) -> None:
    from qtpy.QtGui import QGuiApplication

    app = QGuiApplication.instance()
    if app is None:
        raise RuntimeError("No QGuiApplication — clipboard needs a Qt app")
    app.clipboard().setText(text)
