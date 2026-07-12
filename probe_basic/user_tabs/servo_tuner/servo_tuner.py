"""Servo Tuning tab — A6-EC SDO editor + live drive FERR (60F4) plot.

Probe Basic look (BebasKai / dark panel). LinuxCNC joint.f-error is untouched;
this page plots drive-native CiA 60F4 in pulses and mm/deg.
"""

from __future__ import annotations

import collections
import os
import sys
import threading
import time
from typing import Deque, Dict, List, Optional

from qtpy import uic
from qtpy.QtCore import Qt, QTimer, Signal
from qtpy.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter, QPen, QPalette
from qtpy.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from qtpyvcp.utilities import logger

LOG = logger.getLogger(__name__)

PB_FONT = "BebasKai"
PB_FONT_PATH = "/usr/share/fonts/truetype/BebasKai.ttf"

PYTHON_DIR = os.path.join(
    os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)),
    "python",
)
if PYTHON_DIR not in sys.path:
    sys.path.insert(0, PYTHON_DIR)

from a6_servo_tune import (  # noqa: E402
    AXES,
    AXIS_ORDER,
    FF_SOURCE_LABELS,
    NOTCH_LABELS,
    PARAM_DEFS,
    PARAM_BY_KEY,
    AxisTuneParams,
    apply_axis_params,
    axis_unit,
    counts_to_unit,
    default_axis_params,
    delete_preset,
    format_params_summary,
    list_presets,
    load_preset,
    machine_is_on,
    read_axis_params,
    drive_ferr_counts_halpin,
    read_drive_ferr,
    save_preset,
    unit_to_counts,
)
from tune_trial import (  # noqa: E402
    copy_plot_widget_to_clipboard,
    copy_text_to_clipboard,
    format_param_display,
    format_tuning_text,
)
from resonance_analysis import (  # noqa: E402
    analyze_ferr_resonance,
    format_resonance_text,
)
from a6_auto_tune import (  # noqa: E402
    HardwareTuneIO,
    OneClickConfig,
    OneClickTuner,
    PROFILES,
    default_journal_root,
    estimate_campaign_seconds,
)

try:
    import pyqtgraph as pg
except ImportError:  # pragma: no cover
    pg = None

FERR_SAMPLE_MS = 1
FERR_WINDOW_S = 5.0
FERR_BUFFER = int(FERR_WINDOW_S * (1000.0 / FERR_SAMPLE_MS))
PLOT_BG = "#1e2122"
PLOT_FG = "#eeeeec"
PLOT_LINE = "#8ae234"
PLOT_ZERO = "#6e7375"

AXIS_PLOT_COLORS = {
    "X": "#8ae234",  # green
    "Y": "#729fcf",  # blue
    "Z": "#fcaf3e",  # orange
    "A": "#ad7fa8",  # purple
}

COL_PARAM = 0
COL_CURRENT = 1
COL_PENDING = 2
COL_UNIT = 3
COL_RANGE = 4


class FerrPlotWidget(QWidget):
    """Live multi-axis FERR strip chart (pyqtgraph when available, else QPainter)."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("ferrPlot")
        self.setMinimumHeight(320)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._sample_ms = float(FERR_SAMPLE_MS)
        self._window_s = float(FERR_WINDOW_S)
        self._title = ""
        self._unit_label = "mm"
        self._waiting = True
        self._buf_len = max(
            1, int(self._window_s * (1000.0 / max(self._sample_ms, 1.0)))
        )
        self._series: Dict[str, Deque[float]] = {}
        self._curves: Dict[str, object] = {}
        self._legend = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        if pg is not None:
            self._painter_mode = False
            self.plot = pg.PlotWidget()
            self.plot.setBackground(PLOT_BG)
            self.plot.showGrid(x=True, y=True, alpha=0.35)
            for axis_name in ("left", "bottom"):
                axis = self.plot.getAxis(axis_name)
                axis.setPen(PLOT_FG)
                axis.setTextPen(PLOT_FG)
                try:
                    axis.setStyle(tickFont=QFont(PB_FONT, 11))
                except Exception:
                    pass
            self.plot.setLabel(
                "bottom", "time (s)", color=PLOT_FG, **{"font-size": "12pt"}
            )
            self.plot.setLabel(
                "left", self._unit_label, color=PLOT_FG, **{"font-size": "12pt"}
            )
            self.plot.addLine(
                y=0, pen=pg.mkPen(color=PLOT_ZERO, width=1, style=Qt.DashLine)
            )
            try:
                self._legend = self.plot.addLegend(offset=(10, 10))
            except Exception:
                self._legend = None
            # Manual Y scale only — autoRange fights unit toggles and looks "random".
            try:
                self.plot.enableAutoRange(x=False, y=False)
                self.plot.setMouseEnabled(x=False, y=True)
                axis = self.plot.getAxis("left")
                axis.enableAutoSIPrefix(False)
            except Exception:
                pass
            self.plot.setMinimumHeight(280)
            root.addWidget(self.plot)
            # Back-compat alias used by older single-curve call sites.
            self.curve = None
        else:
            self._painter_mode = True
            self.plot = None
            self.curve = None
        self._plot_unit = "mm"  # "mm"/"deg"/"pulses" — matches buffered sample units

    def _ensure_series(self, axis: str) -> Deque[float]:
        if axis not in self._series:
            self._series[axis] = collections.deque(maxlen=self._buf_len)
            if self.plot is not None and pg is not None:
                color = AXIS_PLOT_COLORS.get(axis, PLOT_LINE)
                curve = self.plot.plot(
                    pen=pg.mkPen(color=color, width=2.5), name=axis
                )
                self._curves[axis] = curve
        return self._series[axis]

    def set_active_axes(self, axes: List[str]) -> None:
        """Keep only these axis series (drop curves for others)."""
        wanted = [a for a in axes if a in AXIS_ORDER]
        for axis in list(self._series.keys()):
            if axis not in wanted:
                self._series.pop(axis, None)
                curve = self._curves.pop(axis, None)
                if curve is not None and self.plot is not None:
                    try:
                        self.plot.removeItem(curve)
                    except Exception:
                        pass
        for axis in wanted:
            self._ensure_series(axis)
        self._waiting = not any(self._series.values())
        self._refresh_all()

    def set_window_seconds(
        self, window_s: float, sample_ms: Optional[float] = None
    ) -> None:
        self._window_s = float(window_s)
        if sample_ms is not None:
            self._sample_ms = float(sample_ms)
        self._buf_len = max(
            1, int(self._window_s * (1000.0 / max(self._sample_ms, 1.0)))
        )
        for axis, old in list(self._series.items()):
            self._series[axis] = collections.deque(
                list(old)[-self._buf_len :], maxlen=self._buf_len
            )
        self._refresh_all()

    def set_title(self, title: str) -> None:
        self._title = str(title or "")
        if self.plot is not None:
            try:
                self.plot.setTitle(
                    self._title, color=PLOT_FG, **{"font-size": "12pt"}
                )
            except Exception:
                pass

    def get_samples(self, axis: Optional[str] = None) -> List[float]:
        if axis is None:
            # Prefer a single series if only one; else first in AXIS_ORDER.
            if len(self._series) == 1:
                return list(next(iter(self._series.values())))
            for name in AXIS_ORDER:
                if name in self._series:
                    return list(self._series[name])
            return []
        return list(self._series.get(axis, []))

    def export_png(self, path: str, title: Optional[str] = None) -> None:
        """Write the current strip chart to PNG (ImageExporter or QImage fallback)."""
        burn = self._title if title is None else str(title)
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)

        if self.plot is not None and pg is not None:
            prev_title = self._title
            if burn:
                self.set_title(burn)
            try:
                from pyqtgraph.exporters import ImageExporter

                exporter = ImageExporter(self.plot.plotItem)
                exporter.export(path)
                if os.path.isfile(path):
                    return
            except Exception as exc:
                LOG.warning("ImageExporter failed (%s) — QImage fallback", exc)
            finally:
                if burn != prev_title:
                    self.set_title(prev_title)

        self._export_png_painter(path, burn)

    def _export_png_painter(self, path: str, burn: str) -> None:
        width, height = 960, 360
        image = QImage(width, height, QImage.Format_RGB32)
        image.fill(QColor(PLOT_BG))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        margin_l, margin_r, margin_t, margin_b = 48, 16, 36, 28
        plot_rect = image.rect().adjusted(margin_l, margin_t, -margin_r, -margin_b)
        painter.setPen(QPen(QColor("#8a8484"), 1))
        painter.drawRect(plot_rect)
        painter.setPen(QColor(PLOT_FG))
        painter.setFont(QFont(PB_FONT, 12))
        if burn:
            painter.drawText(
                image.rect().adjusted(8, 4, -8, 0),
                Qt.AlignTop | Qt.AlignLeft,
                burn,
            )
        mid_y = plot_rect.center().y()
        painter.setPen(QPen(QColor(PLOT_ZERO), 1, Qt.DashLine))
        painter.drawLine(plot_rect.left() + 2, mid_y, plot_rect.right() - 2, mid_y)

        all_vals: List[float] = []
        for values in self._series.values():
            all_vals.extend(v for v in values if v == v)
        if all_vals:
            peak = max(abs(min(all_vals)), abs(max(all_vals)), 1e-6)
            pad = peak * 0.15
            y_max = peak + pad
            w = max(1, plot_rect.width() - 4)
            h = max(1, plot_rect.height() - 4)
            for axis, values in self._series.items():
                seq = list(values)
                if len(seq) < 2:
                    continue
                color = AXIS_PLOT_COLORS.get(axis, PLOT_LINE)
                painter.setPen(QPen(QColor(color), 2))
                n = len(seq)
                for i in range(1, n):
                    x0 = plot_rect.left() + 2 + ((i - 1) / (n - 1)) * w
                    x1 = plot_rect.left() + 2 + (i / (n - 1)) * w
                    y0 = mid_y - (seq[i - 1] / y_max) * (h / 2.0)
                    y1 = mid_y - (seq[i] / y_max) * (h / 2.0)
                    painter.drawLine(int(x0), int(y0), int(x1), int(y1))
        else:
            painter.setPen(QColor(PLOT_FG))
            painter.drawText(plot_rect, Qt.AlignCenter, "no samples")
        painter.setPen(QColor(PLOT_FG))
        painter.setFont(QFont(PB_FONT, 10))
        painter.drawText(
            image.rect().adjusted(8, 0, -8, -4),
            Qt.AlignBottom | Qt.AlignLeft,
            f"{self._unit_label}  ·  {self._window_s:g}s window",
        )
        painter.end()
        if not image.save(path):
            raise RuntimeError(f"failed to write PNG: {path}")

    def set_unit_label(self, unit: str) -> None:
        """Update the Y-axis label only — never touches buffered samples or Y range."""
        self._unit_label = str(unit or "")
        self._plot_unit = self._unit_label
        if self.plot is not None:
            try:
                axis = self.plot.getAxis("left")
                axis.enableAutoSIPrefix(False)
                axis.setLabel(text=self._unit_label, units="")
                self.plot.setLabel(
                    "left", text=self._unit_label, units="", color=PLOT_FG
                )
            except Exception:
                pass

    def reset_y_scale(self) -> None:
        """Neutral empty-plot scale for the current unit (after clear / unit switch)."""
        if self.plot is None:
            return
        try:
            self.plot.enableAutoRange(x=False, y=False)
        except Exception:
            pass
        if self._plot_unit == "pulses":
            self.plot.setYRange(-50.0, 50.0, padding=0)
        else:
            self.plot.setYRange(-0.01, 0.01, padding=0)
        self.plot.setXRange(0.0, max(self._window_s * 0.25, 0.5), padding=0)

    def clear(self) -> None:
        for buf in self._series.values():
            buf.clear()
        self._waiting = True
        for curve in self._curves.values():
            try:
                curve.setData([], [])
            except Exception:
                pass
        self.reset_y_scale()
        self.update()

    def push(self, value: float, axis: str = "X") -> None:
        """Append one sample for ``axis`` and refresh that curve."""
        if value != value:  # NaN
            return
        # Ignore absurd FERR spikes (bad HAL read / wrong pin) so one sample
        # cannot lock the Y scale at ±1e8 until the buffer rolls over.
        if self._plot_unit == "pulses":
            if abs(value) > 5_000_000:  # ~380 mm at 13107 c/mm — not real FERR
                return
        elif abs(value) > 50.0:  # mm/deg — FERR past this is nonsense for the plot
            return
        buf = self._ensure_series(axis)
        buf.append(float(value))
        self._waiting = False
        self._refresh_axis(axis)

    def push_many(self, samples: Dict[str, float]) -> None:
        """Append one sample per axis, then autoscale once (avoids mid-frame flicker)."""
        any_pushed = False
        for axis, value in samples.items():
            if value != value:
                continue
            if self._plot_unit == "pulses":
                if abs(value) > 5_000_000:
                    continue
            elif abs(value) > 50.0:
                continue
            buf = self._ensure_series(axis)
            buf.append(float(value))
            any_pushed = True
            curve = self._curves.get(axis)
            if curve is not None:
                values = list(buf)
                dt = self._sample_ms / 1000.0
                xs = [i * dt for i in range(len(values))]
                curve.setData(xs, values)
        if any_pushed:
            self._waiting = False
            self._autoscale()
        elif self._painter_mode:
            self.update()

    def _refresh_axis(self, axis: str) -> None:
        values = list(self._series.get(axis, []))
        curve = self._curves.get(axis)
        if curve is not None:
            dt = self._sample_ms / 1000.0
            xs = [i * dt for i in range(len(values))]
            curve.setData(xs, values)
            self._autoscale()
        else:
            self.update()

    def _refresh_all(self) -> None:
        for axis in list(self._series.keys()):
            values = list(self._series.get(axis, []))
            curve = self._curves.get(axis)
            if curve is not None:
                dt = self._sample_ms / 1000.0
                xs = [i * dt for i in range(len(values))]
                curve.setData(xs, values)
        self._autoscale()
        if self._painter_mode:
            self.update()

    def _autoscale(self) -> None:
        if self.plot is None:
            return
        try:
            self.plot.enableAutoRange(x=False, y=False)
        except Exception:
            pass
        finite: List[float] = []
        max_n = 0
        for values in self._series.values():
            seq = list(values)
            max_n = max(max_n, len(seq))
            finite.extend(v for v in seq if v == v)
        if finite:
            peak = max(abs(min(finite)), abs(max(finite)), 1e-9)
            if self._plot_unit == "pulses":
                floor = 10.0
            else:
                floor = 1e-4
            pad = max(peak * 0.15, floor * 0.15)
            y_max = max(peak + pad, floor)
            self.plot.setYRange(-y_max, y_max, padding=0)
        else:
            self.reset_y_scale()
            return
        if max_n > 0:
            dt = self._sample_ms / 1000.0
            x_end = max((max_n - 1) * dt, self._window_s * 0.25)
            self.plot.setXRange(0.0, x_end, padding=0)

    def paintEvent(self, event):  # noqa: N802
        if not self._painter_mode:
            return super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(2, 2, -2, -2)
        painter.fillRect(rect, QColor(PLOT_BG))
        painter.setPen(QPen(QColor("#8a8484"), 1))
        painter.drawRect(rect)

        mid_y = rect.center().y()
        painter.setPen(QPen(QColor(PLOT_ZERO), 1, Qt.DashLine))
        painter.drawLine(rect.left() + 4, mid_y, rect.right() - 4, mid_y)

        painter.setPen(QColor(PLOT_FG))
        painter.setFont(QFont(PB_FONT, 10))
        all_vals: List[float] = []
        for values in self._series.values():
            all_vals.extend(list(values))
        if self._waiting or not all_vals:
            painter.drawText(rect, Qt.AlignCenter, "waiting for samples")
            painter.end()
            return

        peak = max(abs(min(all_vals)), abs(max(all_vals)), 1e-6)
        pad = peak * 0.15
        y_max = peak + pad
        w = max(1, rect.width() - 8)
        h = max(1, rect.height() - 8)
        for axis, values in self._series.items():
            seq = list(values)
            n = len(seq)
            if n < 2:
                continue
            color = AXIS_PLOT_COLORS.get(axis, PLOT_LINE)
            painter.setPen(QPen(QColor(color), 2))
            for i in range(1, n):
                x0 = rect.left() + 4 + ((i - 1) / (n - 1)) * w
                x1 = rect.left() + 4 + (i / (n - 1)) * w
                y0 = mid_y - (seq[i - 1] / y_max) * (h / 2.0)
                y1 = mid_y - (seq[i] / y_max) * (h / 2.0)
                painter.drawLine(int(x0), int(y0), int(x1), int(y1))
        painter.end()


class UserTab(QWidget):
    # One-click tuner worker -> GUI thread marshalling (Qt queues these).
    ocProgress = Signal(str, str)
    ocFinished = Signal(object)

    def __init__(self, parent=None):
        super(UserTab, self).__init__(parent)
        ui_file = os.path.splitext(os.path.basename(__file__))[0] + ".ui"
        here = os.path.dirname(os.path.abspath(__file__))
        uic.loadUi(os.path.join(here, ui_file), self)

        self.setObjectName("SERVO_TUNING")
        self._ensure_font()
        self._load_stylesheet(here)
        self._apply_panel_background()

        self._axis = "X"
        self._plot_axes: List[str] = ["X"]  # multi-select for FERR plot
        self._syncing = False
        self._baseline: Dict[str, AxisTuneParams] = {}
        self._live: Dict[str, AxisTuneParams] = {}
        self._ok_keys: Dict[str, List[str]] = {}
        self._failed_keys: Dict[str, List[str]] = {}
        self._did_initial_read = False
        self._ferr_unit_mode = "unit"  # "unit" (mm/deg) or "pulses"
        self._ferr_peak_pulses: Dict[str, float] = {a: 0.0 for a in AXIS_ORDER}
        self._ferr_peak_unit: Dict[str, float] = {a: 0.0 for a in AXIS_ORDER}
        self._pending_edits: Dict[str, QDoubleSpinBox] = {}
        self._current_labels: Dict[str, QLabel] = {}
        self._row_keys: List[str] = []
        # If True, next APPLY may write catalog defaults (unused — DEFAULT removed).
        self._allow_default_write = False
        self._logging_active = False  # live FERR plot only (no CSV / disk writes)
        self._resonance_report = None
        self._oc_tuner: Optional[OneClickTuner] = None  # running one-click job
        self.ocProgress.connect(self._on_one_click_progress)
        self.ocFinished.connect(self._on_one_click_finished)

        self._build_ui()
        self._ferr_timer = QTimer(self)
        self._ferr_timer.setInterval(FERR_SAMPLE_MS)
        self._ferr_timer.timeout.connect(self._poll_ferr)
        self._ferr_timer.start()

    def _ensure_font(self):
        if PB_FONT in QFontDatabase().families():
            return
        if os.path.isfile(PB_FONT_PATH):
            QFontDatabase.addApplicationFont(PB_FONT_PATH)

    def _load_stylesheet(self, here):
        qss_path = os.path.join(here, "servo_tuner.qss")
        if os.path.isfile(qss_path):
            with open(qss_path, "r", encoding="utf-8") as handle:
                self.setStyleSheet(handle.read())

    def _apply_panel_background(self):
        panel = QColor("#2e3436")
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), panel)
        self.setPalette(palette)

    def _build_ui(self) -> None:
        root_layout = self.findChild(QVBoxLayout, "rootLayout")
        if root_layout is None:
            root_layout = QVBoxLayout(self)
            self.setLayout(root_layout)
        root_layout.setSpacing(6)

        root_layout.addWidget(self._build_header(), stretch=0)
        root_layout.addWidget(self._build_presets_bar(), stretch=0)
        root_layout.addLayout(self._build_toolbar(), stretch=0)
        root_layout.addWidget(self._build_clipboard_bar(), stretch=0)
        root_layout.addWidget(self._build_one_click_bar(), stretch=0)

        body = QHBoxLayout()
        body.setSpacing(10)
        ferr = self._build_ferr_group()
        params = self._build_param_table_group()
        # Same vertical policy so both boxes share one bottom edge.
        for panel in (ferr, params):
            panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            panel.setMinimumHeight(0)
        body.addWidget(ferr, stretch=3)
        body.addWidget(params, stretch=2)
        root_layout.addLayout(body, stretch=1)

        self.axis_buttons["X"].setChecked(True)
        self.ferr_plot.set_active_axes(list(self._plot_axes))
        self._refresh_preset_list()
        self._update_value_readouts()
        self._sync_log_button()
        self._update_plot_axis_hint()

    def _build_header(self) -> QFrame:
        header = QFrame(self)
        header.setObjectName("headerBar")
        header.setAttribute(Qt.WA_StyledBackground, True)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(14, 6, 14, 6)

        title = QLabel("SERVO TUNING", header)
        title.setObjectName("lblTitle")
        layout.addWidget(title)
        layout.addStretch()

        self.live_label = QLabel("Not read yet", header)
        self.live_label.setObjectName("lblLiveValues")
        self.live_label.setWordWrap(False)
        layout.addWidget(self.live_label, stretch=1)

        self.status_label = QLabel("READY", header)
        self.status_label.setObjectName("lblStatus")
        self.status_label.setProperty("state", "ok")
        layout.addWidget(self.status_label)
        return header

    def _build_presets_bar(self) -> QFrame:
        """Preset strip: optional named snapshots. Starts with no preset selected."""
        bar = QFrame(self)
        bar.setObjectName("presetsBar")
        bar.setAttribute(Qt.WA_StyledBackground, True)
        self._presets_bar = bar  # disabled as a block while one-click runs
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(6)

        layout.addWidget(self._caption("PRESET"))
        self.preset_combo = QComboBox(bar)
        self.preset_combo.setObjectName("presetCombo")
        self.preset_combo.setMinimumWidth(160)
        self.preset_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.preset_combo.setToolTip(
            "Named snapshots under config/tuning/presets/<axis>/. "
            "Starts on (none) — drive values come from auto-read, not a preset."
        )
        layout.addWidget(self.preset_combo, stretch=1)

        load_btn = QPushButton("LOAD", bar)
        load_btn.setFocusPolicy(Qt.NoFocus)
        load_btn.setToolTip(
            "Load the selected preset into Pending only (does not write the drive)."
        )
        load_btn.clicked.connect(lambda: self._load_selected_preset(apply=False))
        layout.addWidget(load_btn)

        save_btn = QPushButton("SAVE AS PRESET", bar)
        save_btn.setObjectName("btnPrimary")
        save_btn.setFocusPolicy(Qt.NoFocus)
        save_btn.setToolTip(
            "Save current drive tuning (last auto-read / Pending) under the name "
            "in the box."
        )
        save_btn.clicked.connect(self._save_preset)
        layout.addWidget(save_btn)

        self.preset_name_edit = QLineEdit(bar)
        self.preset_name_edit.setPlaceholderText("new preset name…")
        self.preset_name_edit.setMaximumWidth(160)
        layout.addWidget(self.preset_name_edit)

        delete_btn = QPushButton("DELETE", bar)
        delete_btn.setObjectName("btnDanger")
        delete_btn.setFocusPolicy(Qt.NoFocus)
        delete_btn.setToolTip("Delete the selected preset JSON from disk.")
        delete_btn.clicked.connect(self._delete_preset)
        layout.addWidget(delete_btn)
        return bar

    def _build_toolbar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(6)

        row.addWidget(self._caption("PLOT / EDIT"))
        self.axis_buttons = {}
        for axis in AXIS_ORDER:
            btn = QPushButton(axis, self)
            btn.setObjectName("btnAxis")
            btn.setCheckable(True)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setMinimumWidth(44)
            btn.setToolTip(
                f"Toggle {axis} on the FERR plot. Click on = plot + edit that axis; "
                "click again = remove from plot. Multiple axes can plot at once."
            )
            btn.toggled.connect(
                lambda checked, ax=axis: self._on_axis_toggled(ax, checked)
            )
            self.axis_buttons[axis] = btn
            row.addWidget(btn)

        row.addSpacing(8)

        self.log_button = QPushButton("START PLOT", self)
        self.log_button.setObjectName("btnLog")
        self.log_button.setFocusPolicy(Qt.NoFocus)
        self.log_button.setCheckable(True)
        self.log_button.setToolTip(
            "Start/stop the live FERR plot for all checked axes "
            "(no CSV — nothing saved to disk)."
        )
        self.log_button.clicked.connect(self._toggle_logging)
        row.addWidget(self.log_button)

        self.log_status_label = QLabel("PLOT: idle", self)
        self.log_status_label.setObjectName("lblParamHint")
        row.addWidget(self.log_status_label)

        row.addStretch()
        return row

    def _build_clipboard_bar(self) -> QFrame:
        """COPY TUNING (text) and COPY PLOT (image) for LLM paste."""
        bar = QFrame(self)
        bar.setObjectName("clipboardBar")
        bar.setAttribute(Qt.WA_StyledBackground, True)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(6)

        layout.addWidget(self._caption("CLIPBOARD"))

        self.copy_tuning_button = QPushButton("COPY TUNING", bar)
        self.copy_tuning_button.setObjectName("btnPrimary")
        self.copy_tuning_button.setFocusPolicy(Qt.NoFocus)
        self.copy_tuning_button.setToolTip(
            "Copy live parameters for the edit axis as text "
            "(same labels as the parameter table)."
        )
        self.copy_tuning_button.clicked.connect(self._copy_tuning)
        layout.addWidget(self.copy_tuning_button)

        self.copy_plot_button = QPushButton("COPY PLOT", bar)
        self.copy_plot_button.setFocusPolicy(Qt.NoFocus)
        self.copy_plot_button.setToolTip(
            "Copy the current FERR plot image to the clipboard."
        )
        self.copy_plot_button.clicked.connect(self._copy_plot)
        layout.addWidget(self.copy_plot_button)

        self.copy_resonance_button = QPushButton("COPY RESONANCE", bar)
        self.copy_resonance_button.setFocusPolicy(Qt.NoFocus)
        self.copy_resonance_button.setToolTip(
            "Copy last FFT resonance report (run ANALYZE first)."
        )
        self.copy_resonance_button.clicked.connect(self._copy_resonance)
        layout.addWidget(self.copy_resonance_button)

        layout.addStretch()
        return bar

    def _build_one_click_bar(self) -> QFrame:
        """ONE-CLICK strip: profile combo + start/cancel + live progress.

        Runs the OneClickTuner campaign (a6_auto_tune.py) for the edit axis
        in a worker thread. See ONE_CLICK_TUNING.md.
        """
        bar = QFrame(self)
        bar.setObjectName("presetsBar")  # reuse the strip styling
        bar.setAttribute(Qt.WA_StyledBackground, True)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(6)

        layout.addWidget(self._caption("ONE-CLICK"))

        self.oc_profile_combo = QComboBox(bar)
        self.oc_profile_combo.setObjectName("presetCombo")
        for name in ("conservative", "balanced", "aggressive"):
            if name in PROFILES:
                self.oc_profile_combo.addItem(name.upper())
        self.oc_profile_combo.setCurrentText("BALANCED")
        self.oc_profile_combo.setToolTip(
            "Ladder aggressiveness: gain caps, step sizes, and how much "
            "improvement each step must show to keep climbing."
        )
        layout.addWidget(self.oc_profile_combo)

        self.one_click_button = QPushButton(f"ONE-CLICK TUNE {self._axis}", bar)
        self.one_click_button.setObjectName("btnPrimary")
        self.one_click_button.setFocusPolicy(Qt.NoFocus)
        self.one_click_button.setToolTip(
            "Auto-tune the edit axis: baseline snapshot -> speed/position/"
            "integral gain ladder with FFT stability gates and auto notch -> "
            "verify. THE AXIS MOVES. Everything is journaled under "
            "logs/tuning/one_click/ and reverts to baseline on cancel/failure."
        )
        self.one_click_button.clicked.connect(self._start_one_click)
        layout.addWidget(self.one_click_button)

        self.one_click_cancel_button = QPushButton("CANCEL", bar)
        self.one_click_cancel_button.setObjectName("btnDanger")
        self.one_click_cancel_button.setFocusPolicy(Qt.NoFocus)
        self.one_click_cancel_button.setEnabled(False)
        self.one_click_cancel_button.setToolTip(
            "Stop the campaign: motion aborts, every touched SDO is restored "
            "to its baseline value, journal is finalized."
        )
        self.one_click_cancel_button.clicked.connect(self._cancel_one_click)
        layout.addWidget(self.one_click_cancel_button)

        self.oc_status_label = QLabel("idle — tunes the EDIT axis", bar)
        self.oc_status_label.setObjectName("lblParamHint")
        layout.addWidget(self.oc_status_label, stretch=1)

        return bar

    def _build_ferr_group(self) -> QGroupBox:
        group = QGroupBox("DRIVE FERR (CiA 60F4)", self)
        group.setObjectName("grpFerr")
        layout = QVBoxLayout(group)
        layout.setSpacing(4)
        layout.setContentsMargins(8, 8, 8, 8)

        top = QHBoxLayout()
        top.addWidget(self._caption("PLOT"))
        self.ferr_unit_group = QButtonGroup(self)
        self.btn_ferr_unit = QPushButton("MM", group)
        self.btn_ferr_unit.setObjectName("btnAxis")
        self.btn_ferr_unit.setCheckable(True)
        self.btn_ferr_unit.setChecked(True)
        self.btn_ferr_unit.setFocusPolicy(Qt.NoFocus)
        self.btn_ferr_pulses = QPushButton("PULSES", group)
        self.btn_ferr_pulses.setObjectName("btnAxis")
        self.btn_ferr_pulses.setCheckable(True)
        self.btn_ferr_pulses.setFocusPolicy(Qt.NoFocus)
        self.ferr_unit_group.addButton(self.btn_ferr_unit)
        self.ferr_unit_group.addButton(self.btn_ferr_pulses)
        self.btn_ferr_unit.toggled.connect(self._on_ferr_unit_toggled)
        self.btn_ferr_pulses.toggled.connect(self._on_ferr_unit_toggled)
        top.addWidget(self.btn_ferr_unit)
        top.addWidget(self.btn_ferr_pulses)

        clear_btn = QPushButton("CLEAR", group)
        clear_btn.setFocusPolicy(Qt.NoFocus)
        clear_btn.clicked.connect(self._clear_ferr_plot)
        top.addWidget(clear_btn)
        top.addStretch()
        layout.addLayout(top)

        readouts = QHBoxLayout()
        self.ferr_pulses_label = QLabel("PULSES: —", group)
        self.ferr_pulses_label.setObjectName("lblFerrValue")
        self.ferr_unit_value_label = QLabel("MM: —", group)
        self.ferr_unit_value_label.setObjectName("lblFerrValue")
        self.ferr_peak_label = QLabel("PEAK: —", group)
        self.ferr_peak_label.setObjectName("lblFerrValue")
        self.ferr_scale_label = QLabel("SCALE: —", group)
        self.ferr_scale_label.setObjectName("lblParamHint")
        readouts.addWidget(self.ferr_pulses_label)
        readouts.addWidget(self.ferr_unit_value_label)
        readouts.addWidget(self.ferr_peak_label)
        readouts.addWidget(self.ferr_scale_label)
        readouts.addStretch()
        layout.addLayout(readouts)

        self.ferr_plot = FerrPlotWidget(group)
        self.ferr_plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.ferr_plot, stretch=1)

        # --- Resonance / FFT strip ---
        layout.addWidget(self._caption("RESONANCE"))
        res_row = QHBoxLayout()
        self.analyze_resonance_button = QPushButton("ANALYZE", group)
        self.analyze_resonance_button.setObjectName("btnPrimary")
        self.analyze_resonance_button.setFocusPolicy(Qt.NoFocus)
        self.analyze_resonance_button.setToolTip(
            "FFT the edit-axis FERR buffer (run x_resonance.ngc with START PLOT). "
            "Nyquist ≈ 500 Hz at 1 kHz sampling."
        )
        self.analyze_resonance_button.clicked.connect(self._analyze_resonance)
        res_row.addWidget(self.analyze_resonance_button)

        self.suggest_notch_button = QPushButton("USE SUGGESTED NOTCH 3", group)
        self.suggest_notch_button.setFocusPolicy(Qt.NoFocus)
        self.suggest_notch_button.setEnabled(False)
        self.suggest_notch_button.setToolTip(
            "Load FFT peak into Pending for C01.46/47/48 (3rd notch). "
            "Then APPLY TO DRIVE yourself."
        )
        self.suggest_notch_button.clicked.connect(self._apply_suggested_notch_pending)
        res_row.addWidget(self.suggest_notch_button)
        res_row.addStretch()
        layout.addLayout(res_row)

        self.resonance_label = QLabel(
            "RESONANCE: run START PLOT + nc_files/x_resonance.ngc → ANALYZE",
            group,
        )
        self.resonance_label.setObjectName("lblParamHint")
        self.resonance_label.setWordWrap(True)
        layout.addWidget(self.resonance_label)

        self._resonance_report = None
        self._spectrum_curve = None
        self.spectrum_plot = None
        if pg is not None:
            self.spectrum_plot = pg.PlotWidget()
            self.spectrum_plot.setBackground(PLOT_BG)
            self.spectrum_plot.showGrid(x=True, y=True, alpha=0.35)
            self.spectrum_plot.setMinimumHeight(120)
            self.spectrum_plot.setMaximumHeight(180)
            self.spectrum_plot.setLabel(
                "bottom", "Hz", color=PLOT_FG, **{"font-size": "11pt"}
            )
            self.spectrum_plot.setLabel(
                "left", "mag", color=PLOT_FG, **{"font-size": "11pt"}
            )
            for axis_name in ("left", "bottom"):
                axis = self.spectrum_plot.getAxis(axis_name)
                axis.setPen(PLOT_FG)
                axis.setTextPen(PLOT_FG)
            self._spectrum_curve = self.spectrum_plot.plot(
                pen=pg.mkPen("#fcaf3e", width=2)
            )
            layout.addWidget(self.spectrum_plot)

        return group

    def _build_param_table_group(self) -> QGroupBox:
        group = QGroupBox("TUNING PARAMETERS", self)
        group.setObjectName("grpParams")
        layout = QVBoxLayout(group)
        layout.setSpacing(4)
        layout.setContentsMargins(8, 8, 8, 8)

        table_actions = QHBoxLayout()
        table_actions.addStretch()

        self.apply_button = QPushButton("APPLY TO DRIVE", group)
        self.apply_button.setObjectName("btnPrimary")
        self.apply_button.setFocusPolicy(Qt.NoFocus)
        self.apply_button.setToolTip(
            "Write changed Pending values to the edit-axis drive "
            "(motors cycle OFF→ON if needed). Unchanged / unread keys are skipped."
        )
        self.apply_button.clicked.connect(lambda: self._apply_to_drive())
        table_actions.addWidget(self.apply_button)
        layout.addLayout(table_actions)

        self.param_table = QTableWidget(0, 5, group)
        self.param_table.setObjectName("paramTable")
        self.param_table.setHorizontalHeaderLabels(
            ["Parameter", "Current", "Pending", "Unit", "Range"]
        )
        self.param_table.verticalHeader().setVisible(False)
        self.param_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.param_table.setFocusPolicy(Qt.NoFocus)
        self.param_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.param_table.setAlternatingRowColors(True)
        self.param_table.setWordWrap(False)
        self.param_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        header = self.param_table.horizontalHeader()
        header.setSectionResizeMode(COL_PARAM, QHeaderView.Stretch)
        header.setSectionResizeMode(COL_CURRENT, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(COL_PENDING, QHeaderView.Fixed)
        header.resizeSection(COL_PENDING, 110)
        header.setSectionResizeMode(COL_UNIT, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(COL_RANGE, QHeaderView.ResizeToContents)
        self.param_table.verticalHeader().setDefaultSectionSize(28)

        self._populate_param_table()
        layout.addWidget(self.param_table, stretch=1)
        return group

    def _populate_param_table(self) -> None:
        self.param_table.setRowCount(0)
        self._pending_edits.clear()
        self._current_labels.clear()
        self._row_keys.clear()

        last_group = None
        for defn in PARAM_DEFS:
            group_name = defn["group"]
            if group_name != last_group:
                self._add_group_header_row(group_name)
                last_group = group_name
            self._add_param_row(defn)

    def _add_group_header_row(self, title: str) -> None:
        row = self.param_table.rowCount()
        self.param_table.insertRow(row)
        item = QTableWidgetItem(title.upper())
        item.setFlags(Qt.ItemIsEnabled)
        item.setForeground(QColor("#8ae234"))
        font = item.font()
        font.setBold(True)
        item.setFont(font)
        self.param_table.setItem(row, COL_PARAM, item)
        self.param_table.setSpan(row, COL_PARAM, 1, 5)
        self._row_keys.append("")

    def _add_param_row(self, defn: Dict) -> None:
        row = self.param_table.rowCount()
        self.param_table.insertRow(row)
        key = defn["key"]
        self._row_keys.append(key)

        name = QTableWidgetItem(defn["label"])
        name.setFlags(Qt.ItemIsEnabled)
        if defn.get("note"):
            name.setToolTip(str(defn["note"]))
        self.param_table.setItem(row, COL_PARAM, name)

        current_lbl = QLabel("—")
        current_lbl.setObjectName("lblCurrentValue")
        current_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.param_table.setCellWidget(row, COL_CURRENT, current_lbl)
        self._current_labels[key] = current_lbl

        spin = QDoubleSpinBox()
        spin.setObjectName("pendingSpin")
        spin.setDecimals(int(defn.get("decimals", 1)))
        spin.setRange(float(defn["min"]), float(defn["max"]))
        step = 10 ** (-int(defn.get("decimals", 1))) if defn.get("decimals", 1) else 1.0
        if defn.get("decimals", 1) == 0:
            step = 1.0
        elif defn.get("decimals", 1) == 1:
            step = 0.1
        elif defn.get("decimals", 1) == 2:
            step = 0.01
        elif defn.get("decimals", 1) >= 3:
            step = 0.001
        spin.setSingleStep(step)
        spin.setValue(float(defn["default"]))
        spin.setAlignment(Qt.AlignRight)
        spin.setButtonSymbols(QDoubleSpinBox.UpDownArrows)
        if key == "adaptive_notch":
            spin.setToolTip(
                "\n".join(f"{k}: {v}" for k, v in sorted(NOTCH_LABELS.items()))
            )
        elif key in ("speed_ff_source", "torque_ff_source"):
            tip = "\n".join(
                f"{k}: {v}" for k, v in sorted(FF_SOURCE_LABELS.items())
            )
            if defn.get("note"):
                tip = f"{defn['note']}\n{tip}"
            spin.setToolTip(tip)
        elif key == "inertia_ratio_pct":
            spin.setToolTip(
                "Manual load inertia ratio (%). Enter measured/estimated value — "
                "this is not the F30 inertia auto-tune."
            )
        elif defn.get("note"):
            spin.setToolTip(str(defn["note"]))
        self.param_table.setCellWidget(row, COL_PENDING, spin)
        self._pending_edits[key] = spin
        if defn.get("writable", True) is False:
            spin.setEnabled(False)
            spin.setToolTip(
                defn.get("note")
                or "Read-only on this drive — not written by APPLY."
            )
        if defn.get("scale") == "axis_unit":
            spin.setSuffix(f" {axis_unit(self._axis)}")

        unit_text = self._unit_text_for_defn(defn)
        unit_item = QTableWidgetItem(unit_text)
        unit_item.setFlags(Qt.ItemIsEnabled)
        unit_item.setTextAlignment(Qt.AlignCenter)
        self.param_table.setItem(row, COL_UNIT, unit_item)

        range_item = QTableWidgetItem(
            f"{defn['min']:g} .. {defn['max']:g}"
        )
        range_item.setFlags(Qt.ItemIsEnabled)
        range_item.setTextAlignment(Qt.AlignCenter)
        self.param_table.setItem(row, COL_RANGE, range_item)

    def _unit_text_for_defn(self, defn: Dict) -> str:
        unit = defn.get("unit", "")
        if unit == "mm|deg":
            return axis_unit(self._axis)
        return unit

    def _caption(self, text: str) -> QLabel:
        label = QLabel(text, self)
        label.setObjectName("lblCaption")
        return label

    def _set_status(self, text: str, state: str = "ok") -> None:
        self.status_label.setText(text)
        self.status_label.setProperty("state", state)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _set_busy(self, busy: bool) -> None:
        for widget in (
            self.apply_button,
            self.log_button,
            self.copy_tuning_button,
            self.copy_plot_button,
            *self.axis_buttons.values(),
        ):
            widget.setEnabled(not busy)
        if busy:
            self._set_status("BUSY", "busy")

    def _notify(self, text: str) -> None:
        """Status feedback without a bottom message strip (avoids wrap/overlap)."""
        clean = " ".join(str(text).split())
        LOG.info("servo_tuner: %s", clean)
        # Keep the compact header chip; full detail stays in the log.
        short = clean if len(clean) <= 48 else clean[:45] + "…"
        # Don't clobber transient BUSY/APPLYING chips mid-action.
        if self.status_label.text() not in ("BUSY", "APPLYING"):
            self._set_status(short, "ok")

    def _update_value_readouts(self) -> None:
        live = self._live.get(self._axis)
        if live is None:
            self.live_label.setText(f"Edit {self._axis}: waiting for auto-read…")
        else:
            self.live_label.setText(
                f"Edit {self._axis}: " + format_params_summary(live, self._axis)
            )
        self._update_plot_axis_hint()

    def _update_plot_axis_hint(self) -> None:
        """Reflect edit/plot selection in the toolbar plot status line."""
        if not hasattr(self, "log_status_label"):
            return
        plotted = " ".join(self._plot_axes) if self._plot_axes else "—"
        if self._logging_active:
            self.log_status_label.setText(
                f"PLOT: live · edit {self._axis} · {plotted}"
            )
        else:
            self.log_status_label.setText(
                f"PLOT: idle · edit {self._axis} · {plotted}"
            )

    def _store_baseline(self, params: AxisTuneParams) -> None:
        self._baseline[self._axis] = params.copy()
        self._live[self._axis] = params.copy()
        self._update_value_readouts()

    def _ingest_read(
        self,
        params: AxisTuneParams,
        ok_keys: List[str],
        failed_keys: List[str],
    ) -> None:
        self._ok_keys[self._axis] = list(ok_keys)
        self._failed_keys[self._axis] = list(failed_keys)
        self._allow_default_write = False
        self._set_params_to_ui(params)
        self._store_baseline(params)

    def _writable_keys(self) -> List[str]:
        """Keys APPLY is allowed to write for the current axis."""
        if self._allow_default_write:
            keys = [p["key"] for p in PARAM_DEFS]
        else:
            keys = list(self._ok_keys.get(self._axis, []))
        # Never attempt drive-rejected read-only SDOs (they abort mid-batch).
        return [
            k
            for k in keys
            if PARAM_BY_KEY.get(k, {}).get("writable", True) is not False
        ]

    def _set_edit_axis(self, axis: str) -> None:
        """Switch parameter table / APPLY focus without changing plot set."""
        if axis == self._axis:
            return
        self._axis = axis
        if hasattr(self, "one_click_button") and self._oc_tuner is None:
            self.one_click_button.setText(f"ONE-CLICK TUNE {axis}")
        self._refresh_unit_columns()
        self._refresh_preset_list()
        if axis in self._live:
            self._set_params_to_ui(self._live[axis])
            self._update_value_readouts()
            self._update_ferr_unit_button_labels()
            self._set_status(f"EDIT {axis}", "ok")
        else:
            for label in self._current_labels.values():
                label.setText("—")
            self._update_value_readouts()
            self._update_ferr_unit_button_labels()
            self._set_status(f"EDIT {axis}", "ok")
            # Auto-read when first focusing an axis that has no snapshot yet.
            self._read_from_drive(quiet=True)

    def _on_axis_toggled(self, axis: str, checked: bool) -> None:
        if self._syncing:
            return
        if checked:
            if axis not in self._plot_axes:
                self._plot_axes.append(axis)
                # Keep AXIS_ORDER sorting for stable legend/colors.
                self._plot_axes = [a for a in AXIS_ORDER if a in self._plot_axes]
            self.ferr_plot.set_active_axes(list(self._plot_axes))
            self._set_edit_axis(axis)
        else:
            if axis in self._plot_axes:
                self._plot_axes = [a for a in self._plot_axes if a != axis]
            self.ferr_plot.set_active_axes(list(self._plot_axes))
            # If we turned off the edit axis, move edit focus to another plotted axis.
            if axis == self._axis and self._plot_axes:
                self._set_edit_axis(self._plot_axes[0])
            elif not self._plot_axes:
                # No axes plotted — keep last edit axis for params; plot is empty.
                self._update_plot_axis_hint()
        self._update_plot_axis_hint()

    def _on_ferr_unit_toggled(self, checked: bool) -> None:
        # QButtonGroup fires toggled(False) on the button that was deselected
        # first — only handle the newly checked button.
        if not checked:
            return
        if self.btn_ferr_pulses.isChecked():
            self._ferr_unit_mode = "pulses"
        else:
            self._ferr_unit_mode = "unit"
        # Drop old-unit samples before the label/scale change so mm and pulse
        # values never share a buffer (that was the random out-of-scale bug).
        self._clear_ferr_plot()
        self._update_ferr_plot_label()

    def _update_ferr_unit_button_labels(self) -> None:
        unit = axis_unit(self._axis).upper()
        self.btn_ferr_unit.setText(unit)
        # Label only — do not reset Y range while the buffer still has data.
        self._update_ferr_plot_label()

    def _update_ferr_plot_label(self) -> None:
        if self._ferr_unit_mode == "pulses":
            self.ferr_plot.set_unit_label("pulses")
        else:
            # Mixed linear/rotary when multi-plotting — use edit axis unit.
            self.ferr_plot.set_unit_label(axis_unit(self._axis))

    def _clear_ferr_plot(self) -> None:
        self._ferr_peak_pulses = {a: 0.0 for a in AXIS_ORDER}
        self._ferr_peak_unit = {a: 0.0 for a in AXIS_ORDER}
        self.ferr_plot.clear()
        self.ferr_peak_label.setText("PEAK: —")

    def _scaled_ferr_from_counts(self, axis: str, counts: float) -> float:
        """Always convert raw 60F4 counts → mm/deg via joint SCALE."""
        if counts != counts:
            return float("nan")
        return counts_to_unit(axis, counts)

    def _poll_ferr(self) -> None:
        if not self.isVisible():
            return

        # Live readout always follows the edit-focus axis.
        self._update_focus_ferr_readout()

        if not self._logging_active or not self._plot_axes:
            return

        frame: Dict[str, float] = {}
        for axis in list(self._plot_axes):
            try:
                counts, scaled_hal = read_drive_ferr(axis)
            except Exception:
                continue
            if counts == counts:
                scaled = self._scaled_ferr_from_counts(axis, counts)
            else:
                scaled = scaled_hal
            if counts == counts:
                self._ferr_peak_pulses[axis] = max(
                    self._ferr_peak_pulses.get(axis, 0.0), abs(counts)
                )
            if scaled == scaled:
                self._ferr_peak_unit[axis] = max(
                    self._ferr_peak_unit.get(axis, 0.0), abs(scaled)
                )
            plot_val = counts if self._ferr_unit_mode == "pulses" else scaled
            if plot_val == plot_val:
                frame[axis] = plot_val

        if frame:
            self.ferr_plot.push_many(frame)

        self._refresh_peak_label()

    def _update_focus_ferr_readout(self) -> None:
        axis = self._axis
        try:
            counts, scaled_hal = read_drive_ferr(axis)
        except Exception:
            return
        unit = axis_unit(axis)
        scale = float(AXES[axis]["scale"])
        pin = drive_ferr_counts_halpin(axis)
        if counts == counts:
            scaled = self._scaled_ferr_from_counts(axis, counts)
        else:
            scaled = scaled_hal
        self.ferr_scale_label.setText(f"{pin}  SCALE={scale:g}/{unit}")
        if counts == counts:
            self.ferr_pulses_label.setText(f"{axis} PULSES: {int(round(counts))}")
        else:
            self.ferr_pulses_label.setText(f"{axis} PULSES: —")
        if scaled == scaled:
            self.ferr_unit_value_label.setText(f"{axis} {unit.upper()}: {scaled:.4f}")
        else:
            self.ferr_unit_value_label.setText(f"{axis} {unit.upper()}: —")
        if not self._logging_active:
            self._refresh_peak_label()

    def _refresh_peak_label(self) -> None:
        bits = []
        for axis in self._plot_axes or [self._axis]:
            unit = axis_unit(axis)
            if self._ferr_unit_mode == "pulses":
                peak = self._ferr_peak_pulses.get(axis, 0.0)
                if peak:
                    bits.append(f"{axis}:{peak:.0f}p")
            else:
                peak = self._ferr_peak_unit.get(axis, 0.0)
                if peak:
                    bits.append(f"{axis}:{peak:.4f}{unit}")
        self.ferr_peak_label.setText(
            "PEAK: " + (" ".join(bits) if bits else "—")
        )

    def _toggle_logging(self) -> None:
        """Start/stop live FERR plot only — no CSV, nothing written to disk."""
        want_on = self.log_button.isChecked()
        if want_on:
            if not self._plot_axes:
                self.log_button.blockSignals(True)
                self.log_button.setChecked(False)
                self.log_button.blockSignals(False)
                QMessageBox.information(
                    self,
                    "Start plot",
                    "Check at least one axis button (X/Y/Z/A) to plot.",
                )
                self._sync_log_button()
                return
            self._clear_ferr_plot()
            self.ferr_plot.set_active_axes(list(self._plot_axes))
            self._logging_active = True
            self._notify(
                "Plot ON — live FERR for: " + " ".join(self._plot_axes)
            )
        else:
            self._logging_active = False
            self._notify("Plot stopped / frozen.")
        self._update_value_readouts()
        self._sync_log_button()

    def _sync_log_button(self) -> None:
        if not hasattr(self, "log_button"):
            return
        active = bool(self._logging_active)
        self.log_button.blockSignals(True)
        self.log_button.setChecked(active)
        self.log_button.blockSignals(False)
        if active:
            self.log_button.setText("STOP PLOT")
            self.log_button.setObjectName("btnDanger")
        else:
            self.log_button.setText("START PLOT")
            self.log_button.setObjectName("btnLog")
        self.log_button.style().unpolish(self.log_button)
        self.log_button.style().polish(self.log_button)
        self._update_plot_axis_hint()

    def _copy_tuning(self) -> None:
        """Copy edit-axis parameters to clipboard using table labels."""
        live = self._live.get(self._axis)
        if live is None or not live.values:
            # Try an auto-read once.
            self._read_from_drive(quiet=True)
            live = self._live.get(self._axis)
        if live is None or not live.values:
            QMessageBox.information(
                self,
                "Copy tuning",
                "No live parameters yet — wait for auto-read, or APPLY once to refresh.",
            )
            return
        # Overlay Pending edits so clipboard matches what you'd APPLY.
        pending = self._params_from_ui()
        merged = live.copy()
        for key, value in pending.values.items():
            merged.set(key, value)
        if self._ferr_unit_mode == "pulses":
            peak = self._ferr_peak_pulses.get(self._axis, 0.0)
            peak_unit = "pulses"
        else:
            peak = self._ferr_peak_unit.get(self._axis, 0.0)
            peak_unit = axis_unit(self._axis)
        text_out = format_tuning_text(
            merged,
            self._axis,
            peak_abs=peak,
            peak_unit=peak_unit,
            plot_axes=list(self._plot_axes),
        )
        try:
            copy_text_to_clipboard(text_out)
            self._notify(
                f"COPY TUNING — {self._axis} parameters on clipboard "
                f"({len(merged.values)} keys, table labels)."
            )
        except Exception as exc:
            LOG.exception("copy tuning failed")
            QMessageBox.warning(self, "Clipboard", str(exc))

    def _copy_plot(self) -> None:
        """Copy the current FERR plot image to the clipboard."""
        title = (
            f"{self._axis} FERR · plotting "
            + (" ".join(self._plot_axes) if self._plot_axes else "—")
        )
        try:
            path = copy_plot_widget_to_clipboard(self.ferr_plot, title=title)
            self._notify(
                f"COPY PLOT — FERR image on clipboard ({path})."
            )
        except Exception as exc:
            LOG.exception("copy plot failed")
            QMessageBox.warning(self, "Clipboard", str(exc))

    def _analyze_resonance(self) -> None:
        samples = self.ferr_plot.get_samples(self._axis)
        fs = 1000.0 / max(float(getattr(self.ferr_plot, "_sample_ms", 1.0)), 1e-6)
        try:
            report = analyze_ferr_resonance(
                samples, axis=self._axis, fs_hz=fs
            )
        except Exception as exc:
            LOG.exception("resonance analyze failed")
            QMessageBox.warning(self, "Resonance", str(exc))
            return

        self._resonance_report = report
        self.resonance_label.setText(report.summary_line() + f" · {report.reason}")
        self.suggest_notch_button.setEnabled(bool(report.suggested_notch))

        if (
            self._spectrum_curve is not None
            and report.freqs_hz is not None
            and report.magnitude is not None
            and len(report.freqs_hz) > 1
        ):
            try:
                self._spectrum_curve.setData(
                    list(report.freqs_hz), list(report.magnitude)
                )
                self.spectrum_plot.setXRange(
                    0.0, min(500.0, float(report.freqs_hz[-1]))
                )
            except Exception:
                LOG.exception("spectrum plot update failed")

        gate = "PASS" if report.stable else "FAIL"
        self._set_status(f"RESONANCE {gate}", "ok" if report.stable else "error")
        self._notify(f"RESONANCE {gate} — {report.summary_line()}")
        LOG.info("resonance: %s", report.summary_line())

    def _apply_suggested_notch_pending(self) -> None:
        report = self._resonance_report
        if report is None or not report.suggested_notch:
            QMessageBox.information(
                self,
                "Resonance",
                "No suggestion yet — ANALYZE a buffer that shows a clear peak.",
            )
            return
        missing = [
            k for k in report.suggested_notch if k not in self._pending_edits
        ]
        if missing:
            QMessageBox.warning(
                self,
                "Resonance",
                "Notch Pending spins missing (unread SDO keys?): "
                + ", ".join(missing),
            )
            return
        for key, val in report.suggested_notch.items():
            spin = self._pending_edits.get(key)
            if spin is None or not spin.isEnabled():
                continue
            spin.setValue(float(val))
        self._set_status("NOTCH 3 PENDING", "ok")
        self._notify(
            f"Suggested notch 3 loaded into Pending for {self._axis} — "
            "APPLY TO DRIVE when ready."
        )

    def _copy_resonance(self) -> None:
        report = self._resonance_report
        if report is None:
            samples = self.ferr_plot.get_samples(self._axis)
            if len(samples) < 64:
                QMessageBox.information(
                    self,
                    "Clipboard",
                    "No resonance report yet. START PLOT, run the resonance NGC, "
                    "then ANALYZE (or COPY after ANALYZE).",
                )
                return
            fs = 1000.0 / max(
                float(getattr(self.ferr_plot, "_sample_ms", 1.0)), 1e-6
            )
            try:
                report = analyze_ferr_resonance(
                    samples, axis=self._axis, fs_hz=fs
                )
                self._resonance_report = report
            except Exception as exc:
                QMessageBox.warning(self, "Clipboard", str(exc))
                return
        try:
            copy_text_to_clipboard(format_resonance_text(report))
            self._set_status("RESONANCE COPIED", "ok")
            self._notify(f"COPY RESONANCE — {report.summary_line()}")
        except Exception as exc:
            LOG.exception("copy resonance failed")
            QMessageBox.warning(self, "Clipboard", str(exc))

    # ------------------------------------------------------------------
    # One-click auto-tune (a6_auto_tune.OneClickTuner in a worker thread)
    # ------------------------------------------------------------------

    def _start_one_click(self) -> None:
        if self._oc_tuner is not None:
            return
        axis = self._axis
        profile = self.oc_profile_combo.currentText().strip().lower()

        if not machine_is_on():
            QMessageBox.warning(
                self,
                "One-click tune",
                "Machine must be ON (and out of ESTOP) before auto-tuning.",
            )
            return

        try:
            cfg = OneClickConfig.for_axis(axis, profile)
        except Exception as exc:
            QMessageBox.warning(self, "One-click tune", str(exc))
            return
        stim = cfg.stimulus
        est_min = max(1.0, estimate_campaign_seconds(cfg) / 60.0)
        unit = axis_unit(axis)

        reply = QMessageBox.question(
            self,
            f"One-click tune {axis}",
            f"Auto-tune axis {axis} ({profile.upper()} profile)?\n\n"
            f"THE AXIS WILL MOVE: {stim.describe()}\n"
            f"Strokes are RELATIVE to the current position — make sure there "
            f"is at least {stim.stroke:g} {unit} of clearance (direction is "
            f"picked from soft limits when homed).\n\n"
            f"What it does: snapshots + backs up the current tune, then climbs "
            f"speed / position gains and tightens the integral with an FFT "
            f"stability gate between steps (auto notch if a resonance shows), "
            f"then verifies. Worst case ~{est_min:.0f} min; usually much less."
            f"\n\nSafety: writes are RAM-only via the normal APPLY path "
            f"(motors cycle OFF/ON per step); motion aborts if drive FERR "
            f"nears the 6065 window; CANCEL or any failure restores the "
            f"baseline. Everything is journaled under logs/tuning/one_click/."
            f"\n\nKeep a hand near ESTOP.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            io = HardwareTuneIO()
        except Exception as exc:
            QMessageBox.warning(self, "One-click tune", str(exc))
            return

        tuner = OneClickTuner(
            cfg,
            io=io,
            progress=lambda phase, msg: self.ocProgress.emit(phase, msg),
        )
        self._oc_tuner = tuner
        self._set_one_click_running(True)

        # Show the live FERR trace for the axis being tuned.
        if axis not in self._plot_axes:
            self.axis_buttons[axis].setChecked(True)
        self._logging_active = True
        self._sync_log_button()

        self._notify(f"One-click tune started on {axis} ({profile}).")
        worker = threading.Thread(
            target=self._one_click_worker, args=(tuner,), daemon=True
        )
        worker.start()

    def _one_click_worker(self, tuner: OneClickTuner) -> None:
        try:
            result = tuner.run()
        except Exception as exc:  # engine returns results; this is belt+braces
            LOG.exception("one-click worker crashed")
            result = exc
        self.ocFinished.emit(result)

    def _cancel_one_click(self) -> None:
        tuner = self._oc_tuner
        if tuner is None:
            return
        tuner.cancel()
        self.one_click_cancel_button.setEnabled(False)
        self.oc_status_label.setText(
            "cancelling — aborting motion and restoring baseline…"
        )
        self._set_status("CANCELLING", "busy")

    def _on_one_click_progress(self, phase: str, message: str) -> None:
        text = f"{phase}: {message}"
        self.oc_status_label.setText(
            text if len(text) <= 110 else text[:107] + "…"
        )
        LOG.info("one-click: %s", text)

    def _on_one_click_finished(self, result) -> None:
        self._oc_tuner = None
        self._set_one_click_running(False)

        if isinstance(result, BaseException):
            self._set_status("ERROR", "error")
            self.oc_status_label.setText(f"crashed: {result}")
            QMessageBox.warning(
                self,
                "One-click tune",
                f"Tuner crashed unexpectedly: {result}\n\n"
                f"Check the newest journal under {default_journal_root()} — "
                "it records everything up to the crash.",
            )
            return

        # Refresh Current/Pending from the drive so the table shows reality.
        self._read_from_drive(quiet=True)
        self._refresh_preset_list()

        status = getattr(result, "status", "?")
        ok = status in ("improved", "no-change", "dry-run")
        self._set_status(f"TUNE {status.upper()}", "ok" if ok else "error")
        first_line = result.summary().splitlines()[0]
        self.oc_status_label.setText(first_line)

        icon_fn = QMessageBox.information if ok else QMessageBox.warning
        icon_fn(
            self,
            f"One-click tune {result.axis}: {status}",
            result.summary()
            + "\n\nGains are RAM-only — store to drive EEPROM (vendor tool / "
            "panel) if you want them to survive power loss."
            + "\nJournal (keep it — it is how we learn from failures):\n"
            + str(result.journal_dir),
        )

    def _set_one_click_running(self, running: bool) -> None:
        """Lock everything that could fight the campaign; keep CANCEL alive."""
        for widget in (
            self.one_click_button,
            self.oc_profile_combo,
            self.apply_button,
            self.log_button,
            self.copy_tuning_button,
            self.copy_plot_button,
            self.copy_resonance_button,
            self.analyze_resonance_button,
            self.suggest_notch_button,
            self._presets_bar,
            *self.axis_buttons.values(),
        ):
            widget.setEnabled(not running)
        self.one_click_cancel_button.setEnabled(running)
        if running:
            self._set_status("TUNING", "busy")
            self.one_click_button.setText(f"TUNING {self._axis}…")
        else:
            self.one_click_button.setText(f"ONE-CLICK TUNE {self._axis}")
            # suggest_notch is only meaningful after an ANALYZE.
            self.suggest_notch_button.setEnabled(
                bool(self._resonance_report)
                and bool(getattr(self._resonance_report, "suggested_notch", None))
            )

    def _refresh_unit_columns(self) -> None:
        unit = axis_unit(self._axis)
        for row, key in enumerate(self._row_keys):
            if not key:
                continue
            defn = PARAM_BY_KEY.get(key)
            if not defn:
                continue
            item = self.param_table.item(row, COL_UNIT)
            if item is not None:
                item.setText(self._unit_text_for_defn(defn))
            spin = self._pending_edits.get(key)
            if spin is not None and defn.get("scale") == "axis_unit":
                spin.setSuffix(f" {unit}")
                spin.setToolTip(
                    f"Drive 6065 window in {unit} "
                    f"(written as encoder counts via SCALE={AXES[self._axis]['scale']:g})."
                )
            elif spin is not None:
                spin.setSuffix("")

    def _format_current(self, key: str, value: float) -> str:
        defn = PARAM_BY_KEY[key]
        decimals = int(defn.get("decimals", 1))
        unit = self._unit_text_for_defn(defn)
        if key == "adaptive_notch":
            label = NOTCH_LABELS.get(int(value), str(int(value)))
            return f"{int(value)} ({label})"
        if key in ("speed_ff_source", "torque_ff_source"):
            label = FF_SOURCE_LABELS.get(int(value), str(int(value)))
            return f"{int(value)} ({label})"
        if key == "following_error":
            counts = unit_to_counts(self._axis, value)
            return f"{value:.{decimals}f} {unit} ({counts} p)"
        if decimals == 0:
            text = f"{int(round(value))}"
        else:
            text = f"{value:.{decimals}f}"
        return f"{text} {unit}".rstrip() if unit else text

    def _params_from_ui(self) -> AxisTuneParams:
        # Only include keys we are allowed to write — never pad with catalog defaults.
        values: Dict[str, float] = {}
        for key in self._writable_keys():
            spin = self._pending_edits.get(key)
            if spin is None:
                continue
            values[key] = float(spin.value())
        params = AxisTuneParams.__new__(AxisTuneParams)
        params.values = values
        return params

    def _set_params_to_ui(self, params: AxisTuneParams) -> None:
        self._syncing = True
        failed = set(self._failed_keys.get(self._axis, []))
        ok = set(self._ok_keys.get(self._axis, []))
        for key, spin in self._pending_edits.items():
            defn = PARAM_BY_KEY.get(key, {})
            readonly = defn.get("writable", True) is False
            if key in params.values:
                spin.setValue(params.get(key))
                spin.setEnabled(not readonly)
            elif self._allow_default_write and key in PARAM_BY_KEY:
                spin.setValue(float(PARAM_BY_KEY[key]["default"]))
                spin.setEnabled(not readonly)
            else:
                # Keep pending editable only after a successful read of that key.
                spin.setEnabled(
                    (not readonly)
                    and (key in ok or self._allow_default_write)
                )
            if readonly:
                spin.setEnabled(False)
        for key, label in self._current_labels.items():
            if key in failed:
                label.setText("READ FAIL")
            elif key in params.values:
                label.setText(self._format_current(key, params.get(key)))
            else:
                label.setText("—")
        self._syncing = False

    def _load_form_defaults(self) -> None:
        reply = QMessageBox.question(
            self,
            "Load defaults",
            "Fill Pending with built-in catalog defaults?\n\n"
            "APPLY after this will overwrite ALL 28 tuning SDOs on the drive "
            "with those defaults (RAM only — not EEPROM).\n\n"
            "Prefer the auto-read values unless you really want a factory-ish reset.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self._allow_default_write = True
        self._failed_keys[self._axis] = []
        self._ok_keys[self._axis] = [p["key"] for p in PARAM_DEFS]
        defaults = default_axis_params()
        self._set_params_to_ui(defaults)
        self._notify(
            "Pending loaded with built-in defaults. APPLY will write all 28 SDOs. "
            "REVERT still uses the last successful auto-read baseline if present."
        )

    def _read_from_drive(self, quiet: bool = False) -> None:
        """Upload SDOs for the edit axis into Current + Pending.

        Called automatically on tab open and when focusing an unread axis.
        ``quiet`` suppresses the failure dialog (used for background auto-read).
        """
        self._set_busy(True)
        try:
            params, ok_keys, failed_keys = read_axis_params(self._axis)
            self._ingest_read(params, ok_keys, failed_keys)
            self._set_status(f"READ {self._axis}", "ok")
            if failed_keys:
                self._notify(
                    f"Auto-read slave {AXES[self._axis]['slave']}: "
                    f"{len(ok_keys)}/{len(PARAM_DEFS)} ok. "
                    f"APPLY writes only the {len(ok_keys)} successful keys "
                    f"(skipped: {', '.join(failed_keys[:6])}"
                    f"{'…' if len(failed_keys) > 6 else ''})."
                )
            else:
                self._notify(
                    f"Auto-read slave {AXES[self._axis]['slave']} "
                    f"({len(ok_keys)} SDOs). Edit Pending → APPLY."
                )
        except Exception as exc:
            LOG.exception("read_axis_params failed")
            self._set_status("ERROR", "error")
            self._notify(str(exc))
            if not quiet:
                QMessageBox.warning(self, "Read failed", str(exc))
        finally:
            self._set_busy(False)
            self._update_value_readouts()
            if self.status_label.text() == "BUSY":
                self._set_status(f"EDIT {self._axis}", "ok")

    @staticmethod
    def _values_differ(key: str, pending: float, current: float) -> bool:
        """True if Pending differs from Current at the param's display precision."""
        decimals = int(PARAM_BY_KEY.get(key, {}).get("decimals", 1))
        return round(pending, decimals) != round(current, decimals)

    def _changed_keys(
        self, params: AxisTuneParams, keys: List[str]
    ) -> List[str]:
        """Writable keys whose Pending value differs from last Current/live."""
        live = self._live.get(self._axis)
        if live is None:
            return list(keys)
        changed: List[str] = []
        for key in keys:
            if key not in params.values:
                continue
            if key not in live.values:
                changed.append(key)
                continue
            if self._values_differ(key, params.get(key), live.get(key)):
                changed.append(key)
        return changed

    def _apply_to_drive(self, params: AxisTuneParams = None) -> None:
        # Qt clicked(bool) must never bind to this arg — guard anyway.
        if not isinstance(params, AxisTuneParams):
            params = None
        keys = self._writable_keys()
        if not keys:
            QMessageBox.warning(
                self,
                "Apply blocked",
                "No successfully-read parameters for this axis yet.\n\n"
                "No auto-read yet for this axis — wait a moment after selecting it, or reopen the tab.",
            )
            return
        if params is None:
            params = self._params_from_ui()
        # Never write keys we don't have values for.
        keys = [k for k in keys if k in params.values]
        if not keys:
            QMessageBox.warning(
                self,
                "Apply blocked",
                "Nothing to write — Pending has no values for writable keys.",
            )
            return

        # Only show / write parameters that actually changed vs Current.
        keys = self._changed_keys(params, keys)
        if not keys:
            QMessageBox.information(
                self,
                "Nothing changed",
                "Pending matches Current — no SDOs to write.",
            )
            return

        was_on = machine_is_on()
        cycle_note = (
            "Motors are ON — they will be disabled, parameters written, "
            "then re-enabled."
            if was_on
            else "Motors are already OFF — parameters will be written as-is."
        )
        live = self._live.get(self._axis)
        preview_lines = []
        for key in keys[:20]:
            defn = PARAM_BY_KEY[key]
            new_txt = format_param_display(key, params.get(key), self._axis)
            if live is not None and key in live.values:
                old_txt = format_param_display(key, live.get(key), self._axis)
                preview_lines.append(f"  {defn['label']}: {old_txt} → {new_txt}")
            else:
                preview_lines.append(f"  {defn['label']}: → {new_txt}")
        if len(keys) > 20:
            preview_lines.append(f"  … and {len(keys) - 20} more")
        preview = "\n".join(preview_lines)

        default_note = ""
        if self._allow_default_write:
            default_note = (
                "\n\nWARNING: Pending came from LOAD DEFAULT — "
                "this will push catalog defaults for the listed changed SDOs."
            )
        reply = QMessageBox.question(
            self,
            "Apply changes",
            f"Apply tuning to axis {self._axis} "
            f"(slave {AXES[self._axis]['slave']})?\n\n"
            f"Will write {len(keys)} changed SDO(s) "
            f"(unchanged / unread keys untouched):\n"
            f"{preview}\n\n"
            f"{cycle_note}\n\n"
            "RAM only until you store EEPROM on the drive.\n"
            "ethercat-conf.xml no longer overwrites C00/C01 on startup."
            f"{default_note}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self._set_busy(True)
        self._set_status("APPLYING", "busy")
        self._notify(
            f"Writing {len(keys)} changed SDO(s)…"
            + (" (motors cycling)" if was_on else "")
        )
        try:
            result = apply_axis_params(
                self._axis, params, cycle_enable=True, keys=keys
            )
            written = result.get("written_keys", keys)
            failed = result.get("failed_keys") or []
            skipped = result.get("skipped_keys") or []
            # Refresh from drive so Current matches reality.
            fresh, ok_keys, failed_keys = read_axis_params(self._axis)
            self._ingest_read(fresh, ok_keys, failed_keys)
            if failed:
                self._set_status(f"PARTIAL {self._axis}", "error")
                fail_txt = ", ".join(
                    f"{k}" for k, _err in failed[:8]
                )
                self._notify(
                    f"Wrote {len(written)} SDO(s); FAILED {len(failed)}: {fail_txt}"
                    + ("…" if len(failed) > 8 else "")
                    + (
                        f"; skipped read-only {len(skipped)}."
                        if skipped
                        else "."
                    )
                    + " Re-read complete — check Current vs Pending."
                )
                QMessageBox.warning(
                    self,
                    "Partial apply",
                    "Some parameters did not stick on the drive:\n\n"
                    + "\n".join(
                        f"• {PARAM_BY_KEY.get(k, {}).get('label', k)}: {err[:120]}"
                        for k, err in failed[:12]
                    )
                    + (
                        "\n\nRead-only params are skipped automatically now "
                        "(C01.10 / C01.38)."
                        if any(
                            k in ("speed_fb_filter", "gain_sw_mode")
                            for k, _ in failed
                        )
                        or skipped
                        else ""
                    ),
                )
            else:
                self._set_status(f"APPLIED {self._axis}", "ok")
                self._notify(
                    f"Wrote {len(written)} SDO(s) to slave {result['slave']}"
                    + (
                        "; motors cycled OFF→ON."
                        if result.get("cycled_enable")
                        else " (motors stayed off)."
                    )
                    + (
                        f" Skipped {len(skipped)} read-only."
                        if skipped
                        else ""
                    )
                    + " Re-read + verify complete."
                )
        except Exception as exc:
            LOG.exception("apply_axis_params failed")
            self._set_status("ERROR", "error")
            self._notify(str(exc))
            QMessageBox.warning(self, "Apply failed", str(exc))
        finally:
            self._set_busy(False)
            self._update_value_readouts()
            if self.status_label.text() == "BUSY":
                self._set_status(f"AXIS {self._axis}", "ok")

    def _revert_to_baseline(self) -> None:
        baseline = self._baseline.get(self._axis)
        if baseline is None or not self._ok_keys.get(self._axis):
            QMessageBox.information(
                self,
                "Revert",
                "No baseline yet. Wait for auto-read on this axis "
                "(or APPLY once to set a baseline).",
            )
            return
        self._allow_default_write = False
        self._set_params_to_ui(baseline)
        self._notify(
            "Form restored to baseline — confirm APPLY to write it back to the drive."
        )
        self._apply_to_drive(baseline)

    def _refresh_preset_list(self) -> None:
        previous = self._selected_preset_name()
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self.preset_combo.addItem("(none)")
        names = list_presets(self._axis)
        self.preset_combo.addItems(names)
        if previous and previous in names:
            self.preset_combo.setCurrentText(previous)
        else:
            self.preset_combo.setCurrentIndex(0)  # (none)
        self.preset_combo.blockSignals(False)

    def _selected_preset_name(self) -> str:
        name = self.preset_combo.currentText().strip()
        if not name or name == "(none)":
            return ""
        return name

    def _save_preset(self) -> None:
        """Save current drive tuning (last auto-read) as a named preset JSON."""
        name = self.preset_name_edit.text().strip() or self._selected_preset_name()
        if not name or name == "(none)":
            QMessageBox.information(
                self,
                "Save as preset",
                "Type a new preset name in the box (e.g. finish_10um), then SAVE AS PRESET.",
            )
            self.preset_name_edit.setFocus()
            return
        live = self._live.get(self._axis)
        if live is None or not live.values:
            QMessageBox.information(
                self,
                "Save as preset",
                "Wait for auto-read so the preset captures live tuning "
                "(not empty / catalog defaults).",
            )
            return
        # Prefer live drive snapshot; fall back to Pending if somehow empty.
        params = live.copy()
        pending = self._params_from_ui()
        for key, value in pending.values.items():
            if key in self._ok_keys.get(self._axis, []):
                params.set(key, value)
        try:
            path = save_preset(self._axis, name, params, notes="")
            self.preset_name_edit.setText(name)
            self._refresh_preset_list()
            idx = self.preset_combo.findText(name)
            if idx >= 0:
                self.preset_combo.setCurrentIndex(idx)
            self._notify(
                f"Saved current tuning as preset {name!r}: {path}"
            )
        except Exception as exc:
            LOG.exception("save_preset failed")
            QMessageBox.warning(self, "Save failed", str(exc))

    def _load_selected_preset(self, apply: bool = False) -> None:
        name = self._selected_preset_name()
        if not name:
            QMessageBox.information(
                self,
                "Load preset",
                "No preset selected (none). Pick a named preset first, "
                "or wait for auto-read to use live drive values.",
            )
            return
        if not self._ok_keys.get(self._axis):
            QMessageBox.information(
                self,
                "Load preset",
                "Wait for auto-read so missing preset keys keep live drive values "
                "instead of catalog defaults.",
            )
            return
        try:
            preset = load_preset(self._axis, name)
            # Overlay preset keys onto last live read — never invent the rest.
            merged = self._live[self._axis].copy()
            for key, value in preset.params.values.items():
                if key in self._ok_keys[self._axis]:
                    merged.set(key, value)
            self._allow_default_write = False
            self._set_params_to_ui(merged)
            self.preset_name_edit.setText(preset.name)
            skipped = [
                k for k in preset.params.values.keys()
                if k not in self._ok_keys[self._axis]
            ]
            msg = (
                f"Loaded preset {preset.name!r} for axis {self._axis} "
                f"({len(preset.params.values)} keys overlaid on last auto-read)."
            )
            if skipped:
                msg += f" Skipped unread keys: {', '.join(skipped)}."
            self._notify(msg)
            if apply:
                self._apply_to_drive(merged)
        except Exception as exc:
            LOG.exception("load_preset failed")
            QMessageBox.warning(self, "Load failed", str(exc))

    def _delete_preset(self) -> None:
        name = self._selected_preset_name()
        if not name:
            QMessageBox.information(
                self,
                "Delete preset",
                "Select a named preset to delete (not none).",
            )
            return
        reply = QMessageBox.question(
            self,
            "Delete preset",
            f"Delete preset {name!r} for axis {self._axis}?\n\n"
            f"Removes config/tuning/presets/{self._axis}/{name}.json from disk.\n"
            "Does not change what is on the drive.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            delete_preset(self._axis, name)
            self.preset_name_edit.clear()
            self._refresh_preset_list()
            self._notify(
                f"Deleted preset {name!r}. Combo is back on (none)."
            )
        except Exception as exc:
            QMessageBox.warning(self, "Delete failed", str(exc))

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        if not any(btn.isChecked() for btn in self.axis_buttons.values()):
            self._syncing = True
            self.axis_buttons["X"].setChecked(True)
            self._syncing = False
            self._plot_axes = ["X"]
            self._axis = "X"
            self.ferr_plot.set_active_axes(["X"])
            self._update_plot_axis_hint()
        self._update_ferr_unit_button_labels()
        if not self._did_initial_read:
            self._did_initial_read = True
            try:
                params, ok_keys, failed_keys = read_axis_params(self._axis)
                self._ingest_read(params, ok_keys, failed_keys)
                if failed_keys:
                    self._notify(
                        f"Auto-read slave {AXES[self._axis]['slave']}: "
                        f"{len(ok_keys)}/{len(PARAM_DEFS)} ok. "
                        "APPLY only writes successful keys."
                    )
                else:
                    self._notify(
                        f"Auto-read slave {AXES[self._axis]['slave']} on tab open "
                        f"({len(ok_keys)} SDOs). Edit Pending → APPLY."
                    )
            except Exception as exc:
                LOG.info("servo_tuner: initial read skipped: %s", exc)
                self._notify(
                    "Could not auto-read drive (EtherCAT / sudo?). "
                    "Re-open this tab or change axis to retry. FERR plot still polls HAL. "
                    "APPLY is blocked until a successful auto-read."
                )
