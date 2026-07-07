"""Live signal plot with per-channel checkboxes and Y-scale options."""

from __future__ import annotations

from typing import Dict, List, Optional, Set

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

try:
    import pyqtgraph as pg
except ImportError:  # pragma: no cover - optional at runtime
    pg = None

from hal_signal_logger import ChannelConfig, HalSignalLogger


SCALE_MODES = [
    "Auto",
    "Symmetric",
    "Fixed ±0.25",
    "Fixed ±60",
    "Fixed ±100%",
]


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


class LiveSignalPlotWidget(QWidget):
    """Single live plot — pick channels and Y-scale on the fly."""

    def __init__(self, logger: HalSignalLogger, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.logger = logger
        self.channel_map = logger.channel_by_id()
        self._checkboxes: Dict[str, QCheckBox] = {}
        self._curves: Dict[str, object] = {}
        self._stats_labels: Dict[str, QLabel] = {}
        self._updating_checks = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        if pg is None:
            root.addWidget(
                QLabel("pyqtgraph not installed — plots unavailable (logging still works).")
            )
            return

        root.addWidget(self._build_channel_panel())
        root.addWidget(self._build_plot_controls())
        self.plot = pg.PlotWidget()
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.plot.setLabel("bottom", "samples")
        self.plot.addLegend(offset=(10, 10))
        root.addWidget(self.plot, stretch=3)

        self.stats_box = QWidget()
        self.stats_layout = QGridLayout(self.stats_box)
        self.stats_layout.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.stats_box, stretch=0)

        self._init_curves()
        self._apply_default_selection()

    def _build_channel_panel(self) -> QGroupBox:
        box = QGroupBox("Signals to plot")
        layout = QVBoxLayout(box)

        quick_row = QHBoxLayout()
        for label, channel_ids in (
            ("All FErr", ["x_ferr", "y_ferr", "z_ferr", "a_ferr"]),
            ("XYZ FErr", ["x_ferr", "y_ferr", "z_ferr"]),
            ("Torque", ["x_torque", "y_torque", "z_torque", "a_torque"]),
            ("Velocity", ["x_vel", "y_vel", "z_vel", "a_vel"]),
            ("All", list(self.channel_map.keys())),
        ):
            btn = QPushButton(label)
            btn.clicked.connect(lambda _checked=False, ids=channel_ids: self._select_channels(set(ids)))
            quick_row.addWidget(btn)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(lambda: self._select_channels(set()))
        quick_row.addWidget(clear_btn)
        quick_row.addStretch()
        layout.addLayout(quick_row)

        grid = QGridLayout()
        groups = (
            ("Following error", "ferr"),
            ("Torque", "torque"),
            ("Velocity", "velocity"),
        )
        col = 0
        for title, group_id in groups:
            group_box = QGroupBox(title)
            group_layout = QVBoxLayout(group_box)
            for channel in self.logger.get_channels():
                if channel.group != group_id:
                    continue
                cb = QCheckBox(channel.label)
                cb.setToolTip(channel.pin)
                cb.toggled.connect(self._on_channel_toggled)
                self._checkboxes[channel.id] = cb
                group_layout.addWidget(cb)
            grid.addWidget(group_box, 0, col)
            col += 1
        layout.addLayout(grid)
        return box

    def _build_plot_controls(self) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Y scale:"))
        self.scale_combo = QComboBox()
        self.scale_combo.addItems(SCALE_MODES)
        self.scale_combo.currentTextChanged.connect(lambda _text: self.refresh())
        layout.addWidget(self.scale_combo)
        layout.addStretch()
        self.hint_label = QLabel("Plots update while logging is active.")
        self.hint_label.setStyleSheet("color: gray;")
        layout.addWidget(self.hint_label)
        return row

    def _init_curves(self) -> None:
        for row, channel in enumerate(self.logger.get_channels()):
            pen = pg.mkPen(color=channel.color, width=2)
            label = f"{channel.label} ({channel.units})".strip()
            self._curves[channel.id] = self.plot.plot(name=label, pen=pen)
            stat = QLabel(f"{channel.label}: —")
            stat.setAlignment(Qt.AlignLeft)
            self._stats_labels[channel.id] = stat
            self.stats_layout.addWidget(stat, row, 0)

    def _apply_default_selection(self) -> None:
        self._select_channels({"x_ferr", "y_ferr", "z_ferr"})
        self.scale_combo.setCurrentText("Fixed ±0.25")

    def _select_channels(self, channel_ids: Set[str]) -> None:
        self._updating_checks = True
        for channel_id, checkbox in self._checkboxes.items():
            checkbox.setChecked(channel_id in channel_ids)
        self._updating_checks = False
        self._sync_curve_visibility()
        self.refresh()

    def _on_channel_toggled(self) -> None:
        if self._updating_checks:
            return
        self._sync_curve_visibility()
        self.refresh()

    def _sync_curve_visibility(self) -> None:
        visible = self._visible_channels()
        for channel_id, curve in self._curves.items():
            curve.setVisible(channel_id in visible)
            self._stats_labels[channel_id].setVisible(channel_id in visible)

    def _visible_channels(self) -> Set[str]:
        return {
            channel_id
            for channel_id, checkbox in self._checkboxes.items()
            if checkbox.isChecked()
        }

    def refresh(self) -> None:
        if pg is None:
            return

        visible = self._visible_channels()
        buffers = self.logger.get_buffers()
        stats = self.logger.live_stats
        plot_values: List[float] = []
        scale_mode = self.scale_combo.currentText()

        for channel_id in visible:
            curve = self._curves.get(channel_id)
            if curve is None:
                continue
            values = list(buffers.get(channel_id, []))
            xs = list(range(len(values)))
            curve.setData(xs, values)
            plot_values.extend(values)

            channel = self.channel_map[channel_id]
            info = stats.get(channel_id, {})
            unit = channel.units or ""
            self._stats_labels[channel_id].setText(
                f"{channel.label}: last={info.get('last', 0.0):.4f}{unit} "
                f"rms={info.get('rms', 0.0):.4f} peak={info.get('peak', 0.0):.4f}"
            )

        if scale_mode.startswith("Fixed"):
            ymin, ymax = _fixed_y_range(scale_mode)
        elif scale_mode == "Symmetric":
            ymin, ymax = _auto_y_range(plot_values, symmetric=True)
        else:
            ymin, ymax = _auto_y_range(plot_values, symmetric=False)

        self.plot.setYRange(ymin, ymax, padding=0)
        self.hint_label.setText(
            "Logging active — live plot"
            if self.logger.state == "logging"
            else "Start live log or arm for program to see data"
        )


# Backward-compatible alias
SignalPlotWidget = LiveSignalPlotWidget
