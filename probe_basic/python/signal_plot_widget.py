"""Reusable pyqtgraph plotting for HAL signal logger presets."""

from __future__ import annotations

from typing import Dict, List, Optional

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

try:
    import pyqtgraph as pg
except ImportError:  # pragma: no cover - optional at runtime
    pg = None

from hal_signal_logger import ChannelConfig, HalSignalLogger, PlotGroupConfig


def _auto_y_range(values: List[float], mode: str) -> tuple:
    if not values:
        return (-1.0, 1.0)

    finite = [value for value in values if value == value]
    if not finite:
        return (-1.0, 1.0)

    if mode == "sym":
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


class PlotGroupPanel(QGroupBox):
    def __init__(
        self,
        group: PlotGroupConfig,
        channels: Dict[str, ChannelConfig],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(group.title, parent)
        self.group = group
        self.channels = channels
        self.curves: Dict[str, object] = {}
        self.stats_labels: Dict[str, QLabel] = {}

        layout = QVBoxLayout(self)
        if pg is None:
            layout.addWidget(
                QLabel("pyqtgraph not installed. Use: pip install pyqtgraph")
            )
            return

        self.plot = pg.PlotWidget()
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.plot.setLabel("bottom", "samples")
        self.plot.addLegend(offset=(10, 10))
        layout.addWidget(self.plot, stretch=3)

        stats_box = QWidget()
        stats_layout = QGridLayout(stats_box)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(stats_box, stretch=0)

        for row, channel_id in enumerate(group.channels):
            channel = channels.get(channel_id)
            if channel is None:
                continue
            pen = pg.mkPen(color=channel.color, width=2)
            self.curves[channel_id] = self.plot.plot(
                name=f"{channel.label} ({channel.units})".strip(),
                pen=pen,
            )
            label = QLabel(f"{channel.label}: —")
            label.setAlignment(Qt.AlignLeft)
            self.stats_labels[channel_id] = label
            stats_layout.addWidget(label, row, 0)

    def refresh(self, logger: HalSignalLogger) -> None:
        if pg is None:
            return

        buffers = logger.get_buffers()
        stats = logger.live_stats
        all_values: List[float] = []

        for channel_id, curve in self.curves.items():
            values = list(buffers.get(channel_id, []))
            xs = list(range(len(values)))
            curve.setData(xs, values)
            all_values.extend(values)

            channel = self.channels[channel_id]
            info = stats.get(channel_id, {})
            unit = channel.units or ""
            self.stats_labels[channel_id].setText(
                f"{channel.label}: last={info.get('last', 0.0):.4f}{unit} "
                f"rms={info.get('rms', 0.0):.4f} peak={info.get('peak', 0.0):.4f} "
                f"max={info.get('session_max', 0.0):.4f}{unit}"
            )

        mode = self.group.y_mode
        if mode == "fixed":
            ymin = self.group.y_min if self.group.y_min is not None else -1.0
            ymax = self.group.y_max if self.group.y_max is not None else 1.0
            self.plot.setYRange(ymin, ymax, padding=0)
        else:
            ymin, ymax = _auto_y_range(all_values, mode)
            self.plot.setYRange(ymin, ymax, padding=0)


class SignalPlotWidget(QWidget):
    """Stacked live plots driven by a HalSignalLogger instance."""

    def __init__(self, logger: HalSignalLogger, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.logger = logger
        self.channel_map = logger.channel_by_id()
        self.group_panels: List[PlotGroupPanel] = []

        layout = QVBoxLayout(self)
        for group in logger.get_plot_groups():
            panel = PlotGroupPanel(group, self.channel_map, self)
            self.group_panels.append(panel)
            layout.addWidget(panel)

    def refresh(self) -> None:
        for panel in self.group_panels:
            panel.refresh(self.logger)
