"""Clipboard helpers for Servo Tuning — copy live parameters / plot image.

Paste text uses the same labels and value wording as the Servo Tuning
parameter table (PARAM_DEFS label + Current-column formatting).
"""

from __future__ import annotations

import logging
import os
import tempfile
from typing import Dict, List, Optional

from a6_servo_tune import (
    FF_SOURCE_LABELS,
    NOTCH_LABELS,
    PARAM_BY_KEY,
    PARAM_DEFS,
    AxisTuneParams,
    axis_unit,
    unit_to_counts,
)

LOG = logging.getLogger(__name__)

LLM_PLAYBOOK_PATH = "SERVO_TUNING_LLM.md"

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

MANUAL_MODE_LABELS: Dict[int, str] = {
    0: "manual",
    1: "standard",
    2: "positioning",
}


def _unit_text(defn: dict, axis: str) -> str:
    unit = defn.get("unit", "")
    if unit == "mm|deg":
        return axis_unit(axis)
    return str(unit) if unit else ""


def format_param_display(key: str, value: float, axis: str) -> str:
    """Match Servo Tuning Current-column wording for one parameter."""
    defn = PARAM_BY_KEY[key]
    decimals = int(defn.get("decimals", 1))
    unit = _unit_text(defn, axis)
    ival = int(round(value))

    if key == "adaptive_notch":
        label = NOTCH_LABELS.get(ival, str(ival))
        return f"{ival} ({label})"
    if key in ("speed_ff_source", "torque_ff_source"):
        label = FF_SOURCE_LABELS.get(ival, str(ival))
        return f"{ival} ({label})"
    if key == "manual_mode":
        gloss = MANUAL_MODE_LABELS.get(ival, "?")
        return f"{ival} ({gloss})" if not unit else f"{ival} {unit} ({gloss})"
    if key == "gain_sw_mode":
        gloss = GAIN_SW_MODE_LABELS.get(ival, "unknown")
        return f"{ival} ({gloss})" if not unit else f"{ival} {unit} ({gloss})"
    if key == "following_error":
        counts = unit_to_counts(axis, value)
        return f"{value:.{decimals}f} {unit} ({counts} p)"

    if decimals == 0:
        text = f"{ival}"
    else:
        text = f"{value:.{decimals}f}"
    return f"{text} {unit}".rstrip() if unit else text


def _format_value_line(key: str, value: float, axis: str) -> str:
    """One line: '<PARAM_DEFS label>: <Current-column value>'."""
    label = str(PARAM_BY_KEY[key]["label"])
    return f"{label}: {format_param_display(key, value, axis)}"


def format_tuning_text(
    params: AxisTuneParams,
    axis: str,
    *,
    peak_abs: Optional[float] = None,
    peak_unit: str = "",
    plot_axes: Optional[List[str]] = None,
) -> str:
    """Clipboard text for COPY TUNING — labels match the parameter table."""
    lines: List[str] = [
        "SERVO TUNING",
        f"Follow {LLM_PLAYBOOK_PATH} — one bounded change; I will APPLY myself.",
        "",
        f"Edit axis: {axis}",
        f"Axis unit: {axis_unit(axis)}",
    ]
    if plot_axes:
        lines.append(f"Plotting: {' '.join(plot_axes)}")
    if peak_abs is not None and peak_abs == peak_abs:
        unit = peak_unit or axis_unit(axis)
        lines.append(f"Peak abs (edit axis): {peak_abs:g} {unit}")
    lines.append("")
    lines.append("PARAMETERS (same labels as Servo Tuning table):")

    last_group = None
    for defn in PARAM_DEFS:
        key = defn["key"]
        if key not in params.values:
            continue
        group = defn.get("group")
        if group and group != last_group:
            lines.append("")
            lines.append(f"[{group}]")
            last_group = group
        lines.append(_format_value_line(key, params.get(key), axis))

    lines.append("")
    lines.append(
        "Suggest the next small change (zone order: filter/notch → speed → "
        "integral → position). Do not auto-apply."
    )
    return "\n".join(lines)


def format_resonance_text_clipboard(report) -> str:
    """Re-export analysis formatter for Servo Tuning clipboard."""
    from resonance_analysis import format_resonance_text

    return format_resonance_text(report)


def copy_text_to_clipboard(text: str) -> None:
    from qtpy.QtGui import QGuiApplication

    app = QGuiApplication.instance()
    if app is None:
        raise RuntimeError("No QGuiApplication — clipboard needs a Qt app")
    app.clipboard().setText(text)


def copy_image_file_to_clipboard(png_path: str) -> None:
    from qtpy.QtGui import QGuiApplication, QImage

    app = QGuiApplication.instance()
    if app is None:
        raise RuntimeError("No QGuiApplication — clipboard needs a Qt app")
    image = QImage(png_path)
    if image.isNull():
        raise RuntimeError(f"failed to load PNG: {png_path}")
    app.clipboard().setImage(image)


def copy_plot_widget_to_clipboard(ferr_plot, *, title: str = "") -> str:
    """Export FerrPlotWidget to a temp PNG and put it on the clipboard.

    Returns the temp path written (caller may ignore).
    """
    fd, path = tempfile.mkstemp(prefix="servo_ferr_", suffix=".png")
    os.close(fd)
    try:
        ferr_plot.export_png(path, title=title or None)
        copy_image_file_to_clipboard(path)
    except Exception:
        try:
            os.remove(path)
        except OSError:
            pass
        raise
    return path
