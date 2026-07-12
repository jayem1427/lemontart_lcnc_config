"""Servo Tuning tab — A6-EC SDO editor + live drive FERR (60F4) plot.

Probe Basic look (BebasKai / dark panel). LinuxCNC joint.f-error is untouched;
this page plots drive-native CiA 60F4 in pulses and mm/deg.
"""

from __future__ import annotations

import collections
import os
import sys
import time
from typing import Deque, Dict, List, Optional

from qtpy import uic
from qtpy.QtCore import Qt, QTimer
from qtpy.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter, QPen, QPalette
from qtpy.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
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
    DEFAULT_PLOT_WINDOW_S,
    SOFT_PRESET_NAME,
    TRIAL_PLOT_WINDOW_S,
    build_paste_pack,
    copy_text_to_clipboard,
    copy_trial_to_clipboard,
    machine_still_safe,
    make_trial_id,
    open_tuning_program,
    preflight_machine,
    program_is_running,
    resolve_tuning_ngc,
    save_trial_artifacts,
    short_gains_tag,
    start_auto_run,
    trial_dir,
)

TRIAL_SAMPLE_MS = 10

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

COL_PARAM = 0
COL_CURRENT = 1
COL_PENDING = 2
COL_UNIT = 3
COL_RANGE = 4


class FerrPlotWidget(QWidget):
    """Simple live FERR strip chart (pyqtgraph when available, else QPainter)."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("ferrPlot")
        self.setMinimumHeight(320)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._sample_ms = float(FERR_SAMPLE_MS)
        self._window_s = float(FERR_WINDOW_S)
        self._title = ""
        self._samples: Deque[float] = collections.deque(maxlen=FERR_BUFFER)
        self._unit_label = "mm"
        self._waiting = True

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
            self.plot.setLabel("bottom", "time (s)", color=PLOT_FG, **{"font-size": "12pt"})
            self.plot.setLabel("left", self._unit_label, color=PLOT_FG, **{"font-size": "12pt"})
            self.curve = self.plot.plot(pen=pg.mkPen(color=PLOT_LINE, width=2.5))
            self.plot.addLine(y=0, pen=pg.mkPen(color=PLOT_ZERO, width=1, style=Qt.DashLine))
            self.plot.setMinimumHeight(280)
            root.addWidget(self.plot)
        else:
            self._painter_mode = True
            self.plot = None
            self.curve = None

    def set_window_seconds(
        self, window_s: float, sample_ms: Optional[float] = None
    ) -> None:
        self._window_s = float(window_s)
        if sample_ms is not None:
            self._sample_ms = float(sample_ms)
        buf = max(
            1,
            int(self._window_s * (1000.0 / max(self._sample_ms, 1.0))),
        )
        old = list(self._samples)
        self._samples = collections.deque(old[-buf:], maxlen=buf)

    def set_title(self, title: str) -> None:
        self._title = str(title or "")
        if self.plot is not None:
            try:
                self.plot.setTitle(
                    self._title, color=PLOT_FG, **{"font-size": "12pt"}
                )
            except Exception:
                pass

    def get_samples(self) -> List[float]:
        return list(self._samples)

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

        # QPainter fallback (painter mode or exporter failure).
        values = list(self._samples)
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
        if values:
            peak = max(abs(min(values)), abs(max(values)), 1e-6)
            pad = peak * 0.15
            y_max = peak + pad
            n = len(values)
            w = max(1, plot_rect.width() - 4)
            h = max(1, plot_rect.height() - 4)
            painter.setPen(QPen(QColor(PLOT_LINE), 2))
            if n == 1:
                x = plot_rect.left() + 2
                y = mid_y - (values[0] / y_max) * (h / 2.0)
                painter.drawPoint(int(x), int(y))
            else:
                for i in range(1, n):
                    x0 = plot_rect.left() + 2 + ((i - 1) / (n - 1)) * w
                    x1 = plot_rect.left() + 2 + (i / (n - 1)) * w
                    y0 = mid_y - (values[i - 1] / y_max) * (h / 2.0)
                    y1 = mid_y - (values[i] / y_max) * (h / 2.0)
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
        self._unit_label = unit
        if self.plot is not None:
            # Explicitly clear SI "units=" so pyqtgraph doesn't keep a stale "mm".
            self.plot.setLabel("left", text=unit, units="", color=PLOT_FG)
            axis = self.plot.getAxis("left")
            axis.enableAutoSIPrefix(False)
            axis.setLabel(text=unit, units="")
            self.plot.setYRange(-1, 1, padding=0)  # reset until new samples arrive

    def clear(self) -> None:
        self._samples.clear()
        self._waiting = True
        if self.curve is not None:
            self.curve.setData([], [])
        self.update()

    def push(self, value: float) -> None:
        if value != value:  # NaN
            return
        self._samples.append(float(value))
        self._waiting = False
        values = list(self._samples)
        if self.curve is not None:
            dt = self._sample_ms / 1000.0
            xs = [i * dt for i in range(len(values))]
            self.curve.setData(xs, values)
            finite = [v for v in values if v == v]
            if finite:
                peak = max(abs(min(finite)), abs(max(finite)), 1e-6)
                pad = max(peak * 0.15, 1e-4)
                self.plot.setYRange(-peak - pad, peak + pad, padding=0)
                if xs:
                    self.plot.setXRange(
                        xs[0], max(xs[-1], self._window_s * 0.25), padding=0
                    )
        else:
            self.update()

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
        if self._waiting or not self._samples:
            painter.drawText(rect, Qt.AlignCenter, "waiting for samples")
            painter.end()
            return

        values = list(self._samples)
        peak = max(abs(min(values)), abs(max(values)), 1e-6)
        pad = peak * 0.15
        y_max = peak + pad
        n = len(values)
        if n < 2:
            painter.end()
            return

        painter.setPen(QPen(QColor(PLOT_LINE), 2))
        w = max(1, rect.width() - 8)
        h = max(1, rect.height() - 8)
        points = []
        for i, val in enumerate(values):
            x = rect.left() + 4 + (i / (n - 1)) * w
            y = mid_y - (val / y_max) * (h / 2.0)
            points.append((x, y))
        for i in range(1, len(points)):
            painter.drawLine(
                int(points[i - 1][0]),
                int(points[i - 1][1]),
                int(points[i][0]),
                int(points[i][1]),
            )
        painter.end()


class UserTab(QWidget):
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
        self._syncing = False
        self._baseline: Dict[str, AxisTuneParams] = {}
        self._live: Dict[str, AxisTuneParams] = {}
        self._ok_keys: Dict[str, List[str]] = {}
        self._failed_keys: Dict[str, List[str]] = {}
        self._did_initial_read = False
        self._ferr_unit_mode = "unit"  # "unit" (mm/deg) or "pulses"
        self._ferr_peak_pulses = 0.0
        self._ferr_peak_unit = 0.0
        self._pending_edits: Dict[str, QDoubleSpinBox] = {}
        self._current_labels: Dict[str, QLabel] = {}
        self._row_keys: List[str] = []
        # If True, next APPLY may write catalog defaults (unused — DEFAULT removed).
        self._allow_default_write = False
        self._logging_active = False  # live FERR plot only (no CSV / disk writes)
        self._logging_before_trial = False

        # Semi-auto tune trial state
        self._trial_active = False
        self._trial_id: Optional[str] = None
        self._trial_ngc: Optional[str] = None
        self._trial_params: Optional[AxisTuneParams] = None
        self._trial_seen_running = False
        self._trial_auto_run = False
        self._trial_wait_start_ms = 0
        self._last_paste_text = ""

        self._build_ui()
        self._ferr_timer = QTimer(self)
        self._ferr_timer.setInterval(FERR_SAMPLE_MS)
        self._ferr_timer.timeout.connect(self._poll_ferr)
        self._ferr_timer.start()

        self._trial_poll = QTimer(self)
        self._trial_poll.setInterval(200)
        self._trial_poll.timeout.connect(self._poll_trial)

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
        root_layout.addWidget(self._build_semiauto_group(), stretch=0)

        body = QHBoxLayout()
        body.setSpacing(10)
        body.addWidget(self._build_ferr_group(), stretch=3)
        body.addWidget(self._build_param_table_group(), stretch=2)
        root_layout.addLayout(body, stretch=1)

        self.message_label = QLabel(
            "READ loads drive SDOs into Pending. Edit Pending, then APPLY in the "
            "parameters box to write the drive. START PLOT runs the live FERR trace "
            "(nothing is written to disk). Tune Trial opens the axis NGC, captures "
            "drive FERR, and saves a paste pack under logs/tuning/.",
            self,
        )
        self.message_label.setObjectName("lblMessage")
        self.message_label.setWordWrap(True)
        root_layout.addWidget(self.message_label, stretch=0)

        self.axis_buttons["X"].setChecked(True)
        self._refresh_preset_list()
        self._update_value_readouts()
        self._sync_log_button()
        self._sync_trial_controls()

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
            "Starts on (none) — drive values come from READ, not a preset."
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
            "Save current drive tuning (last READ / live values) under the name "
            "in the box. READ first if you have not yet."
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

        # Keep notes field for save/load API compatibility (hidden).
        self.preset_notes_edit = QLineEdit(bar)
        self.preset_notes_edit.hide()
        return bar

    def _build_toolbar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(6)

        row.addWidget(self._caption("AXIS"))
        self.axis_group = QButtonGroup(self)
        self.axis_buttons = {}
        for axis in AXIS_ORDER:
            btn = QPushButton(axis, self)
            btn.setObjectName("btnAxis")
            btn.setCheckable(True)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setMinimumWidth(44)
            self.axis_group.addButton(btn)
            btn.toggled.connect(
                lambda checked, ax=axis: self._on_axis_selected(ax, checked)
            )
            self.axis_buttons[axis] = btn
            row.addWidget(btn)

        row.addSpacing(8)

        self.read_button = QPushButton("READ", self)
        self.read_button.setFocusPolicy(Qt.NoFocus)
        self.read_button.setToolTip(
            "Read live SDOs from the selected axis into Current + Pending."
        )
        self.read_button.clicked.connect(self._read_from_drive)
        row.addWidget(self.read_button)

        row.addSpacing(8)

        self.log_button = QPushButton("START PLOT", self)
        self.log_button.setObjectName("btnLog")
        self.log_button.setFocusPolicy(Qt.NoFocus)
        self.log_button.setCheckable(True)
        self.log_button.setToolTip(
            "Start/stop the live FERR plot (no CSV — nothing saved to disk)."
        )
        self.log_button.clicked.connect(self._toggle_logging)
        row.addWidget(self.log_button)

        self.log_status_label = QLabel("PLOT: idle", self)
        self.log_status_label.setObjectName("lblParamHint")
        row.addWidget(self.log_status_label)

        row.addStretch()
        return row

    def _build_semiauto_group(self) -> QGroupBox:
        """Compact semi-auto Tune Trial strip (keeps remote toolbar/presets intact)."""
        group = QGroupBox("SEMI-AUTO TUNE TRIAL", self)
        group.setObjectName("grpSemiAuto")
        layout = QHBoxLayout(group)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(6)

        self.tune_trial_button = QPushButton("TUNE TRIAL", group)
        self.tune_trial_button.setObjectName("btnPrimary")
        self.tune_trial_button.setFocusPolicy(Qt.NoFocus)
        self.tune_trial_button.setToolTip(
            "Open axis tuning NGC, capture drive FERR, export PNG + paste pack."
        )
        self.tune_trial_button.clicked.connect(self._start_tune_trial)
        layout.addWidget(self.tune_trial_button)

        self.cancel_trial_button = QPushButton("CANCEL TRIAL", group)
        self.cancel_trial_button.setObjectName("btnDanger")
        self.cancel_trial_button.setFocusPolicy(Qt.NoFocus)
        self.cancel_trial_button.setEnabled(False)
        self.cancel_trial_button.setToolTip(
            "Stop waiting/export only — does not abort machine motion."
        )
        self.cancel_trial_button.clicked.connect(self._cancel_tune_trial)
        layout.addWidget(self.cancel_trial_button)

        self.copy_paste_button = QPushButton("COPY PASTE PACK", group)
        self.copy_paste_button.setFocusPolicy(Qt.NoFocus)
        self.copy_paste_button.setToolTip(
            "Re-copy the last trial paste-pack text to the clipboard."
        )
        self.copy_paste_button.clicked.connect(self._copy_paste_pack)
        layout.addWidget(self.copy_paste_button)

        self.load_soft_button = QPushButton("LOAD SOFT BASELINE", group)
        self.load_soft_button.setFocusPolicy(Qt.NoFocus)
        self.load_soft_button.setToolTip(
            "Load preset named 'soft' into Pending if it exists "
            "(+ Fixed 1st / manual when writable). Save one with SAVE AS PRESET first."
        )
        self.load_soft_button.clicked.connect(self._load_soft_baseline)
        layout.addWidget(self.load_soft_button)

        self.auto_cycle_check = QCheckBox("AUTO CYCLE START", group)
        self.auto_cycle_check.setFocusPolicy(Qt.NoFocus)
        self.auto_cycle_check.setToolTip(
            "If checked, issues Cycle Start after a second confirm. "
            "Default is wait for manual Cycle Start."
        )
        layout.addWidget(self.auto_cycle_check)

        self.trial_notes_edit = QLineEdit(group)
        self.trial_notes_edit.setPlaceholderText("notes (buzz y/n, …)")
        self.trial_notes_edit.setMinimumWidth(140)
        self.trial_notes_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.trial_notes_edit, stretch=1)

        self.trial_status_label = QLabel("Trial: idle", group)
        self.trial_status_label.setObjectName("lblParamHint")
        layout.addWidget(self.trial_status_label)
        return group

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
        layout.addWidget(self.ferr_plot, stretch=1)

        self.baseline_label = QLabel(
            "Plot is paused until START PLOT. Live pulses/mm still update above.",
            group,
        )
        self.baseline_label.setObjectName("lblParamHint")
        self.baseline_label.setWordWrap(True)
        layout.addWidget(self.baseline_label)
        return group

    def _build_param_table_group(self) -> QGroupBox:
        group = QGroupBox("TUNING PARAMETERS", self)
        group.setObjectName("grpParams")
        layout = QVBoxLayout(group)
        layout.setSpacing(4)
        layout.setContentsMargins(8, 8, 8, 8)

        table_actions = QHBoxLayout()
        copy_btn = QPushButton("COPY CURRENT → PENDING", group)
        copy_btn.setFocusPolicy(Qt.NoFocus)
        copy_btn.clicked.connect(self._copy_current_to_pending)
        table_actions.addWidget(copy_btn)
        table_actions.addStretch()

        self.apply_button = QPushButton("APPLY TO DRIVE", group)
        self.apply_button.setObjectName("btnPrimary")
        self.apply_button.setFocusPolicy(Qt.NoFocus)
        self.apply_button.setToolTip(
            "Write Pending values to the selected axis drive "
            "(motors cycle OFF→ON if needed). Only keys from the last READ."
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
        trial = bool(self._trial_active)
        for widget in (
            self.read_button,
            self.apply_button,
            self.log_button,
            *self.axis_buttons.values(),
        ):
            widget.setEnabled(not busy and not trial)
        self._sync_trial_controls(busy=busy)
        if busy:
            self._set_status("BUSY", "busy")

    def _sync_trial_controls(self, busy: bool = False) -> None:
        if not hasattr(self, "tune_trial_button"):
            return
        trial = bool(self._trial_active)
        self.tune_trial_button.setEnabled(not busy and not trial)
        # CANCEL stays enabled while a trial is active (even if other UI is busy).
        self.cancel_trial_button.setEnabled(trial)
        self.copy_paste_button.setEnabled(not busy and not trial)
        self.load_soft_button.setEnabled(not busy and not trial)
        self.auto_cycle_check.setEnabled(not busy and not trial)
        self.trial_notes_edit.setEnabled(not busy and not trial)

    def _update_value_readouts(self) -> None:
        live = self._live.get(self._axis)
        if live is None:
            self.live_label.setText("Not read yet — press READ")
        else:
            self.live_label.setText(format_params_summary(live, self._axis))

        if self._logging_active:
            self.baseline_label.setText(
                "Plot ON — live FERR trace. Press STOP PLOT to freeze."
            )
        else:
            self.baseline_label.setText(
                "Plot paused until START PLOT. Live pulses/mm still update above."
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

    def _on_axis_selected(self, axis: str, checked: bool) -> None:
        if self._syncing or not checked:
            return
        self._axis = axis
        self._clear_ferr_plot()
        self._refresh_unit_columns()
        self._refresh_preset_list()
        if axis in self._live:
            self._set_params_to_ui(self._live[axis])
        self._update_value_readouts()
        self._update_ferr_unit_button_labels()
        self._set_status(f"AXIS {axis}", "ok")

    def _on_ferr_unit_toggled(self, checked: bool) -> None:
        # QButtonGroup fires toggled(False) on the button that was deselected
        # first — only handle the newly checked button.
        if not checked:
            return
        if self.btn_ferr_pulses.isChecked():
            self._ferr_unit_mode = "pulses"
        else:
            self._ferr_unit_mode = "unit"
        self._clear_ferr_plot()
        self._update_ferr_plot_label()

    def _update_ferr_unit_button_labels(self) -> None:
        unit = axis_unit(self._axis).upper()
        self.btn_ferr_unit.setText(unit)
        self._update_ferr_plot_label()

    def _update_ferr_plot_label(self) -> None:
        if self._ferr_unit_mode == "pulses":
            self.ferr_plot.set_unit_label("pulses")
        else:
            self.ferr_plot.set_unit_label(axis_unit(self._axis))

    def _clear_ferr_plot(self) -> None:
        self._ferr_peak_pulses = 0.0
        self._ferr_peak_unit = 0.0
        self.ferr_plot.clear()
        self.ferr_peak_label.setText("PEAK: —")

    def _scaled_ferr_from_counts(self, counts: float) -> float:
        """Always convert raw 60F4 counts → mm/deg via joint SCALE."""
        if counts != counts:
            return float("nan")
        return counts_to_unit(self._axis, counts)

    def _poll_ferr(self) -> None:
        if not self.isVisible():
            return
        try:
            counts, scaled_hal = read_drive_ferr(self._axis)
        except Exception:
            return

        unit = axis_unit(self._axis)
        scale = float(AXES[self._axis]["scale"])
        pin = drive_ferr_counts_halpin(self._axis)
        # Prefer counts→unit so plot/readouts match joint SCALE even if HAL
        # scaled pin is missing or misconfigured.
        if counts == counts:
            scaled = self._scaled_ferr_from_counts(counts)
        else:
            scaled = scaled_hal

        self.ferr_scale_label.setText(
            f"{pin}  SCALE={scale:g}/{unit}"
        )

        if counts == counts:
            # Integer encoder counts — never show float leftovers.
            self.ferr_pulses_label.setText(f"PULSES: {int(round(counts))}")
            if self._logging_active:
                self._ferr_peak_pulses = max(self._ferr_peak_pulses, abs(counts))
        else:
            self.ferr_pulses_label.setText("PULSES: —")

        if scaled == scaled:
            self.ferr_unit_value_label.setText(f"{unit.upper()}: {scaled:.4f}")
            if self._logging_active:
                self._ferr_peak_unit = max(self._ferr_peak_unit, abs(scaled))
        else:
            self.ferr_unit_value_label.setText(f"{unit.upper()}: —")

        if self._ferr_unit_mode == "pulses":
            plot_val = counts
            peak_txt = (
                f"PEAK: {self._ferr_peak_pulses:.0f} p / "
                f"{self._ferr_peak_unit:.4f} {unit}"
                if self._ferr_peak_pulses or self._ferr_peak_unit
                else "PEAK: —"
            )
        else:
            plot_val = scaled
            peak_txt = (
                f"PEAK: {self._ferr_peak_unit:.4f} {unit} / "
                f"{self._ferr_peak_pulses:.0f} p"
                if self._ferr_peak_pulses or self._ferr_peak_unit
                else "PEAK: —"
            )
        self.ferr_peak_label.setText(peak_txt)
        # Plot only while START PLOT is active — nothing written to disk.
        if self._logging_active and plot_val == plot_val:
            self.ferr_plot.push(plot_val)

    def _toggle_logging(self) -> None:
        """Start/stop live FERR plot only — no CSV, nothing written to disk."""
        want_on = self.log_button.isChecked()
        if want_on:
            self._clear_ferr_plot()
            self._logging_active = True
            self.message_label.setText("Plot ON — live FERR trace (not saved).")
        else:
            self._logging_active = False
            self.message_label.setText("Plot stopped / frozen.")
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
            self.log_status_label.setText("PLOT: live")
        else:
            self.log_button.setText("START PLOT")
            self.log_button.setObjectName("btnLog")
            self.log_status_label.setText("PLOT: idle")
        self.log_button.style().unpolish(self.log_button)
        self.log_button.style().polish(self.log_button)

    def _trial_unit_label(self) -> str:
        if self._ferr_unit_mode == "pulses":
            return "pulses"
        return axis_unit(self._axis)

    def _start_tune_trial(self) -> None:
        if self._trial_active:
            return

        auto_run = bool(self.auto_cycle_check.isChecked())
        ngc_name = f"{self._axis.lower()}_tuning.ngc"
        reply = QMessageBox.question(
            self,
            "Tune Trial",
            f"Start a tune trial on axis {self._axis}?\n\n"
            f"Will open {ngc_name} in AUTO and capture drive FERR (CiA 60F4).\n"
            "Machine must be clear — the axis will move through the NGC envelope.\n\n"
            + (
                "AUTO CYCLE START is ON — motion will start after a second confirm."
                if auto_run
                else "Default: press Cycle Start yourself after the program opens."
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        if auto_run:
            reply2 = QMessageBox.question(
                self,
                "AUTO CYCLE START",
                "Issue Cycle Start automatically after the NGC opens?\n\n"
                "Only Yes if the machine is clear and you intend motion now.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply2 != QMessageBox.Yes:
                return

        try:
            preflight_machine(self._axis)
            ngc_path = resolve_tuning_ngc(self._axis)
        except Exception as exc:
            QMessageBox.warning(self, "Tune Trial blocked", str(exc))
            self.trial_status_label.setText(f"Trial: blocked — {exc}")
            return

        live = self._live.get(self._axis)
        if live is None or not self._ok_keys.get(self._axis):
            QMessageBox.information(
                self,
                "Tune Trial",
                "READ FROM DRIVE first so the paste pack has live gains.",
            )
            return

        trial_id = make_trial_id(self._axis)
        params = live.copy()
        gains_tag = short_gains_tag(params)
        unit_label = self._trial_unit_label()
        title = f"{self._axis} · {trial_id} · {gains_tag} · {unit_label}"

        self._logging_before_trial = bool(self._logging_active)
        self._trial_active = True
        self._trial_id = trial_id
        self._trial_ngc = ngc_path
        self._trial_params = params
        self._trial_seen_running = False
        self._trial_auto_run = auto_run
        self._trial_wait_start_ms = int(time.time() * 1000)

        # Capture at 10 ms into a 180 s window — avoid 1 kHz × 180 s UI death.
        self._ferr_timer.setInterval(TRIAL_SAMPLE_MS)
        self.ferr_plot.set_window_seconds(TRIAL_PLOT_WINDOW_S, sample_ms=TRIAL_SAMPLE_MS)
        self._clear_ferr_plot()
        self.ferr_plot.set_title(title)
        self._logging_active = True
        self._sync_log_button()
        self._set_busy(False)  # refreshes enables with trial=True
        self._sync_trial_controls()

        try:
            open_tuning_program(self._axis)
        except Exception as exc:
            LOG.exception("open_tuning_program failed")
            self._abort_trial_setup(f"open failed: {exc}")
            QMessageBox.warning(self, "Tune Trial failed", str(exc))
            return

        if auto_run:
            try:
                start_auto_run()
                self.trial_status_label.setText("Trial: AUTO_RUN issued — capturing…")
                self.message_label.setText(
                    f"Tune Trial {trial_id}: AUTO_RUN — capturing drive FERR."
                )
            except Exception as exc:
                LOG.exception("start_auto_run failed")
                self._abort_trial_setup(f"AUTO_RUN failed: {exc}")
                QMessageBox.warning(self, "AUTO_RUN failed", str(exc))
                return
        else:
            self.trial_status_label.setText("Trial: waiting for Cycle Start…")
            self.message_label.setText(
                f"Tune Trial {trial_id}: program open — press Cycle Start when ready. "
                "CANCEL TRIAL stops capture only (does not abort motion)."
            )

        self._set_status("TRIAL", "busy")
        self._trial_poll.start()

    def _abort_trial_setup(self, reason: str) -> None:
        """Roll back trial arming when NGC open / AUTO_RUN fails before capture."""
        self._trial_poll.stop()
        self._trial_active = False
        self._trial_id = None
        self._trial_ngc = None
        self._trial_params = None
        self._trial_seen_running = False
        self._restore_plot_after_trial()
        self._logging_active = bool(self._logging_before_trial)
        self._sync_log_button()
        self._sync_trial_controls()
        self.trial_status_label.setText(f"Trial: aborted — {reason}")
        self._set_status(f"AXIS {self._axis}", "ok")

    def _cancel_tune_trial(self) -> None:
        if not self._trial_active:
            return
        # Does NOT abort LinuxCNC motion — only stops waiting/export.
        self._finish_trial(aborted=True, reason="cancelled (motion not aborted)")

    def _poll_trial(self) -> None:
        if not self._trial_active:
            return

        ok, reason = machine_still_safe()
        if not ok:
            self._finish_trial(aborted=True, reason=reason)
            return

        running = program_is_running()
        if not self._trial_seen_running:
            if running:
                self._trial_seen_running = True
                self.trial_status_label.setText("Trial: capturing…")
                self.message_label.setText(
                    f"Tune Trial {self._trial_id}: program running — capturing FERR."
                )
            return

        if not running:
            self._finish_trial(aborted=False, reason="")

    def _finish_trial(self, aborted: bool = False, reason: str = "") -> None:
        if not self._trial_active:
            return

        self._trial_poll.stop()
        trial_id = self._trial_id or make_trial_id(self._axis)
        ngc_path = self._trial_ngc or ""
        params = self._trial_params or self._live.get(self._axis) or self._params_from_ui()
        notes = self.trial_notes_edit.text().strip()
        unit_label = self._trial_unit_label()
        samples = self.ferr_plot.get_samples()
        waited = not self._trial_auto_run
        auto_run = bool(self._trial_auto_run)
        gains_tag = short_gains_tag(params)
        title = f"{self._axis} · {trial_id} · {gains_tag} · {unit_label}"

        directory = trial_dir(trial_id)
        png_path = os.path.join(directory, "drive_ferr.png")
        clip_note = ""
        try:
            self.ferr_plot.export_png(png_path, title=title)
            artifact = save_trial_artifacts(
                axis=self._axis,
                trial_id=trial_id,
                params=params,
                samples=samples,
                sample_ms=float(TRIAL_SAMPLE_MS),
                unit_label=unit_label,
                unit_mode=self._ferr_unit_mode,
                ngc_path=ngc_path,
                png_path=png_path,
                operator_notes=notes,
                auto_run=auto_run,
                waited_for_cycle_start=waited,
            )
            self._last_paste_text = artifact.paste_text
            try:
                clip_note = copy_trial_to_clipboard(png_path, artifact.paste_text)
            except Exception as clip_exc:
                LOG.warning("clipboard copy failed: %s", clip_exc)
                clip_note = f"clipboard failed ({clip_exc}) — files saved"
            if aborted:
                self.trial_status_label.setText(
                    f"Trial: aborted — {reason or 'stopped'} · saved {trial_id}"
                )
                self.message_label.setText(
                    f"Tune Trial aborted ({reason or 'stopped'}). "
                    f"Artifacts under {directory}. {clip_note}"
                )
                self._set_status("TRIAL ABORT", "error")
            else:
                self.trial_status_label.setText(
                    f"Trial: done · peak {artifact.peak_abs:g} {unit_label}"
                )
                self.message_label.setText(
                    f"Tune Trial {trial_id} complete — peak "
                    f"{artifact.peak_abs:g} {unit_label}, "
                    f"{artifact.sample_count} samples. "
                    f"Saved {directory}. {clip_note}"
                )
                self._set_status("TRIAL OK", "ok")
        except Exception as exc:
            LOG.exception("finish_trial save failed")
            self.trial_status_label.setText(f"Trial: save failed — {exc}")
            self.message_label.setText(f"Tune Trial save failed: {exc}")
            self._set_status("ERROR", "error")
            QMessageBox.warning(self, "Trial save failed", str(exc))

        self._trial_active = False
        self._trial_id = None
        self._trial_ngc = None
        self._trial_params = None
        self._trial_seen_running = False
        self._trial_auto_run = False

        self._restore_plot_after_trial()
        # Leave plot ON so the operator can inspect the captured waveform.
        self._logging_active = True
        self._sync_log_button()
        self._sync_trial_controls()
        self._update_value_readouts()

    def _restore_plot_after_trial(self) -> None:
        self._ferr_timer.setInterval(FERR_SAMPLE_MS)
        self.ferr_plot.set_window_seconds(
            DEFAULT_PLOT_WINDOW_S, sample_ms=FERR_SAMPLE_MS
        )

    def _copy_paste_pack(self) -> None:
        text = self._last_paste_text
        if not text:
            # Build a fresh pack from current Pending/live if no prior trial.
            live = self._live.get(self._axis) or self._params_from_ui()
            try:
                ngc = resolve_tuning_ngc(self._axis)
            except Exception:
                ngc = f"{self._axis.lower()}_tuning.ngc"
            text = build_paste_pack(
                axis=self._axis,
                trial_id="(no trial yet)",
                params=live,
                ngc_name=os.path.basename(ngc),
                peak_abs=max(
                    self._ferr_peak_unit if self._ferr_unit_mode != "pulses"
                    else self._ferr_peak_pulses,
                    0.0,
                ),
                unit_label=self._trial_unit_label(),
                png_name="(none)",
                operator_notes=self.trial_notes_edit.text().strip(),
            )
        try:
            copy_text_to_clipboard(text)
            self._last_paste_text = text
            self.message_label.setText("Paste pack text copied to clipboard.")
            self.trial_status_label.setText("Trial: paste pack copied")
        except Exception as exc:
            QMessageBox.warning(self, "Clipboard", str(exc))

    def _load_soft_baseline(self) -> None:
        if not self._ok_keys.get(self._axis):
            QMessageBox.information(
                self,
                "Soft baseline",
                "READ FROM DRIVE first so missing preset keys keep live values.",
            )
            return
        try:
            preset = load_preset(self._axis, SOFT_PRESET_NAME)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Soft baseline",
                f"Could not load preset {SOFT_PRESET_NAME!r}: {exc}",
            )
            return

        ok = set(self._ok_keys[self._axis])
        merged = self._live[self._axis].copy()
        for key, value in preset.params.values.items():
            if key in ok:
                merged.set(key, value)

        # Force Fixed 1st + manual only when key was readable and is writable.
        for key, value in (("gain_sw_mode", 0.0), ("manual_mode", 0.0)):
            if key not in ok:
                continue
            defn = PARAM_BY_KEY.get(key, {})
            if defn.get("writable", True) is False:
                continue
            merged.set(key, value)

        self._allow_default_write = False
        self._set_params_to_ui(merged)
        self.preset_name_edit.setText(SOFT_PRESET_NAME)
        self.message_label.setText(
            f"Soft baseline loaded into Pending for {self._axis} "
            f"(preset {SOFT_PRESET_NAME!r} + Fixed 1st/manual when writable). "
            "Nothing written until APPLY."
        )
        self.trial_status_label.setText("Trial: soft baseline in Pending")

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

    def _copy_current_to_pending(self) -> None:
        live = self._live.get(self._axis)
        if live is None:
            QMessageBox.information(
                self, "Copy", "No current values yet — press READ FROM DRIVE first."
            )
            return
        self._set_params_to_ui(live)
        self.message_label.setText("Pending copied from Current.")

    def _load_form_defaults(self) -> None:
        reply = QMessageBox.question(
            self,
            "Load defaults",
            "Fill Pending with built-in catalog defaults?\n\n"
            "APPLY after this will overwrite ALL 28 tuning SDOs on the drive "
            "with those defaults (RAM only — not EEPROM).\n\n"
            "Prefer READ FROM DRIVE unless you really want a factory-ish reset.",
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
        self.message_label.setText(
            "Pending loaded with built-in defaults. APPLY will write all 28 SDOs. "
            "REVERT still uses the last successful READ baseline if present."
        )

    def _read_from_drive(self) -> None:
        self._set_busy(True)
        try:
            params, ok_keys, failed_keys = read_axis_params(self._axis)
            self._ingest_read(params, ok_keys, failed_keys)
            self._set_status(f"READ {self._axis}", "ok")
            if failed_keys:
                self.message_label.setText(
                    f"Read slave {AXES[self._axis]['slave']}: "
                    f"{len(ok_keys)}/{len(PARAM_DEFS)} ok. "
                    f"APPLY will only write the {len(ok_keys)} successful keys "
                    f"(skipped: {', '.join(failed_keys[:6])}"
                    f"{'…' if len(failed_keys) > 6 else ''})."
                )
            else:
                self.message_label.setText(
                    f"Live values from slave {AXES[self._axis]['slave']} "
                    f"loaded ({len(ok_keys)} SDOs). APPLY writes only these."
                )
        except Exception as exc:
            LOG.exception("read_axis_params failed")
            self._set_status("ERROR", "error")
            self.message_label.setText(str(exc))
            QMessageBox.warning(self, "Read failed", str(exc))
        finally:
            self._set_busy(False)
            self._update_value_readouts()
            if self.status_label.text() == "BUSY":
                self._set_status(f"AXIS {self._axis}", "ok")

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
                "Press READ FROM DRIVE first so APPLY cannot write invented defaults.",
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

        was_on = machine_is_on()
        cycle_note = (
            "Motors are ON — they will be disabled, parameters written, "
            "then re-enabled."
            if was_on
            else "Motors are already OFF — parameters will be written as-is."
        )
        # Show exactly what will be written so catalog defaults can't sneak in unseen.
        preview_lines = []
        for key in keys[:12]:
            defn = PARAM_BY_KEY[key]
            val = float(params.values[key])
            unit = defn.get("unit", "")
            if unit == "mm|deg":
                unit = axis_unit(self._axis)
            preview_lines.append(f"  {defn['label']}: {val:g} {unit}".rstrip())
        if len(keys) > 12:
            preview_lines.append(f"  … and {len(keys) - 12} more")
        preview = "\n".join(preview_lines)

        default_note = ""
        if self._allow_default_write:
            default_note = (
                "\n\nWARNING: Pending came from LOAD DEFAULT — "
                "this will push catalog defaults to the drive for all listed SDOs."
            )
        reply = QMessageBox.question(
            self,
            "Apply changes",
            f"Apply tuning to axis {self._axis} "
            f"(slave {AXES[self._axis]['slave']})?\n\n"
            f"Will write {len(keys)} SDO(s) ONLY (unread keys untouched):\n"
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
        self.message_label.setText(
            f"Writing {len(keys)} SDO(s)…"
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
                self.message_label.setText(
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
                self.message_label.setText(
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
            self.message_label.setText(str(exc))
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
                "No baseline yet. Press READ FROM DRIVE first "
                "(or APPLY once to set a baseline).",
            )
            return
        self._allow_default_write = False
        self._set_params_to_ui(baseline)
        self.message_label.setText(
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
        """Save current drive tuning (last READ) as a named preset JSON."""
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
                "READ from the drive first so the preset captures live tuning "
                "(not empty / catalog defaults).",
            )
            return
        # Prefer live drive snapshot; fall back to Pending if somehow empty.
        params = live.copy()
        pending = self._params_from_ui()
        for key, value in pending.values.items():
            if key in self._ok_keys.get(self._axis, []):
                params.set(key, value)
        notes = self.preset_notes_edit.text().strip()
        try:
            path = save_preset(self._axis, name, params, notes=notes)
            self.preset_name_edit.setText(name)
            self._refresh_preset_list()
            idx = self.preset_combo.findText(name)
            if idx >= 0:
                self.preset_combo.setCurrentIndex(idx)
            self.message_label.setText(
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
                "or READ to use live drive values.",
            )
            return
        if not self._ok_keys.get(self._axis):
            QMessageBox.information(
                self,
                "Load preset",
                "READ first so missing preset keys keep live drive values "
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
            self.preset_notes_edit.setText(preset.notes)
            skipped = [
                k for k in preset.params.values.keys()
                if k not in self._ok_keys[self._axis]
            ]
            msg = (
                f"Loaded preset {preset.name!r} for axis {self._axis} "
                f"({len(preset.params.values)} keys overlaid on last READ)."
            )
            if skipped:
                msg += f" Skipped unread keys: {', '.join(skipped)}."
            self.message_label.setText(msg)
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
            self.message_label.setText(
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
        self._update_ferr_unit_button_labels()
        if not self._did_initial_read:
            self._did_initial_read = True
            try:
                params, ok_keys, failed_keys = read_axis_params(self._axis)
                self._ingest_read(params, ok_keys, failed_keys)
                if failed_keys:
                    self.message_label.setText(
                        f"Auto-read slave {AXES[self._axis]['slave']}: "
                        f"{len(ok_keys)}/{len(PARAM_DEFS)} ok. "
                        "APPLY only writes successful keys."
                    )
                else:
                    self.message_label.setText(
                        f"Auto-read slave {AXES[self._axis]['slave']} on tab open "
                        f"({len(ok_keys)} SDOs). Edit Pending → APPLY."
                    )
            except Exception as exc:
                LOG.info("servo_tuner: initial read skipped: %s", exc)
                self.message_label.setText(
                    "Could not auto-read drive (EtherCAT / sudo?). "
                    "Press READ FROM DRIVE when ready. FERR plot still polls HAL. "
                    "APPLY is blocked until a successful READ."
                )
