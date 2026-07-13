"""Live signal plot — displays channels selected by the parent tab."""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QLabel, QVBoxLayout, QWidget

try:
    import pyqtgraph as pg
except ImportError:  # pragma: no cover - optional at runtime
    pg = None

from hal_signal_logger import HalSignalLogger


SCALE_MODES = [
    "Auto",
    "Symmetric",
    "Fixed ±0.25",
    "Fixed ±60",
    "Fixed ±100%",
]

AXIS_CHANNEL_ORDER = {
    "x": 0, "y": 1, "z": 2, "a": 3,
}

# Cap points sent to pyqtgraph — full 5k-point setData @ 100 Hz starved jog UI.
PLOT_MAX_POINTS = 800


def _channel_sort_key(channel_id: str) -> tuple:
    return (AXIS_CHANNEL_ORDER.get(channel_id[0], 9), channel_id)


PLOT_BG = "#1e2122"
PLOT_FG = "#eeeeec"


def _decimate(values: List[float], max_points: int = PLOT_MAX_POINTS) -> List[float]:
    n = len(values)
    if n <= max_points:
        return values
    step = n / float(max_points)
    return [values[int(i * step)] for i in range(max_points)]


def _auto_y_range(values: List[float], symmetric: bool = False) -> tuple:
    if not values:
        return (-1.0, 1.0)

    finite = [value for value in values if value == value]
    if not finite:
        return (-1.0, 1.0)

    if symmetric:
        limit = max(abs(min(finite)), abs(max(finite)), 1e-6)
        pad = limit * 0.1
        return (-limit - pad, limit + pad)

    ymin = min(finite)
    ymax = max(finite)
    if ymin == ymax:
        pad = max(abs(ymin) * 0.1, 1e-3)
        return (ymin - pad, ymax + pad)

    pad = (ymax - ymin) * 0.1
    return (ymin - pad, ymax + pad)


def _fixed_y_range(mode: str) -> tuple:
    if mode == "Fixed ±0.25":
        return (-0.25, 0.25)
    if mode == "Fixed ±60":
        return (-60.0, 60.0)
    if mode == "Fixed ±100%":
        return (-100.0, 100.0)
    return (-1.0, 1.0)


def _configure_plot_widget(plot: "pg.PlotWidget") -> None:
    plot.setBackground(PLOT_BG)
    plot.showGrid(x=True, y=True, alpha=0.3)
    for axis_name in ("left", "bottom"):
        axis = plot.getAxis(axis_name)
        axis.setPen(PLOT_FG)
        axis.setTextPen(PLOT_FG)


class LiveSignalPlotWidget(QWidget):
    """Plot area — one or more channels, controlled externally."""

    def __init__(self, logger: HalSignalLogger, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("SIGNAL_PLOT")
        self.logger = logger
        self.channel_map = logger.channel_by_id()
        self._curves: Dict[str, object] = {}
        self._visible: Set[str] = set()
        self._scale_mode = "Fixed ±0.25"
        self._y_unit = "value"
        self._last_yrange: Optional[Tuple[float, float]] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        if pg is None:
            root.addWidget(
                QLabel("pyqtgraph not installed — plots unavailable (logging still works).")
            )
            return

        self.plot = pg.PlotWidget()
        _configure_plot_widget(self.plot)
        self.plot.setLabel("bottom", "samples", color=PLOT_FG)
        self.plot.setLabel("left", "value", color=PLOT_FG)
        self.plot.setMinimumHeight(320)
        try:
            self.plot.enableAutoRange(x=False, y=False)
            self.plot.setMouseEnabled(x=False, y=False)
        except Exception:
            pass
        root.addWidget(self.plot, stretch=1)

        self.stat_label = QLabel("—")
        self.stat_label.setObjectName("lblStatPrimary")
        self.stat_label.setAlignment(Qt.AlignLeft)
        root.addWidget(self.stat_label, stretch=0)

        self._init_curves()

    def _init_curves(self) -> None:
        for channel in self.logger.get_channels():
            pen = pg.mkPen(color=channel.color, width=2)
            curve = self.plot.plot(pen=pen)
            curve.setVisible(False)
            self._curves[channel.id] = curve

    def set_visible_channels(self, channel_ids: Set[str]) -> None:
        new_visible = set(channel_ids)
        if new_visible == self._visible:
            return
        self._visible = new_visible
        for channel_id, curve in self._curves.items():
            curve.setVisible(channel_id in self._visible)

    def set_scale_mode(self, mode: str) -> None:
        if mode != self._scale_mode:
            self._last_yrange = None
        self._scale_mode = mode

    def set_y_unit(self, unit: str) -> None:
        """Y-axis label — e.g. ``mm``, ``%``, ``mm/min``."""
        label = (unit or "value").strip() or "value"
        if label == self._y_unit or pg is None or not hasattr(self, "plot"):
            self._y_unit = label
            return
        self._y_unit = label
        self.plot.setLabel("left", label, color=PLOT_FG)

    def refresh(self) -> None:
        if pg is None:
            return

        visible = sorted(self._visible, key=_channel_sort_key)
        buffers = self.logger.snapshot_buffers(visible)
        stats = self.logger.snapshot_live_stats(visible)
        plot_values: List[float] = []
        stat_lines: List[str] = []

        for channel_id in visible:
            curve = self._curves.get(channel_id)
            if curve is None:
                continue
            values = _decimate(buffers.get(channel_id, []))
            curve.setData(list(range(len(values))), values)
            plot_values.extend(values)

            channel = self.channel_map[channel_id]
            info = stats.get(channel_id, {})
            unit = f" {channel.units}" if channel.units else ""
            stat_lines.append(
                f"{channel.label.upper()}: last={info.get('last', 0.0):.4f}{unit}  "
                f"rms={info.get('rms', 0.0):.4f}{unit}  "
                f"peak={info.get('peak', 0.0):.4f}{unit}"
            )

        if len(stat_lines) == 1:
            self.stat_label.setText(stat_lines[0])
        elif stat_lines:
            self.stat_label.setText("   |   ".join(stat_lines))
        else:
            self.stat_label.setText("—")

        if self._scale_mode.startswith("Fixed"):
            ymin, ymax = _fixed_y_range(self._scale_mode)
        elif self._scale_mode == "Symmetric":
            ymin, ymax = _auto_y_range(plot_values, symmetric=True)
        else:
            ymin, ymax = _auto_y_range(plot_values, symmetric=False)

        xmax = max((len(buffers.get(cid, [])) for cid in visible), default=1)
        self.plot.setXRange(0, max(xmax - 1, 1), padding=0)

        yrange = (ymin, ymax)
        if yrange != self._last_yrange:
            self._last_yrange = yrange
            self.plot.setYRange(ymin, ymax, padding=0)


SignalPlotWidget = LiveSignalPlotWidget
