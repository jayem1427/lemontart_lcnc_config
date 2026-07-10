"""Servo Tuning tab — A6-EC SDO editor + live drive FERR (60F4) plot.

Probe Basic look (BebasKai / dark panel). LinuxCNC joint.f-error is untouched;
this page plots drive-native CiA 60F4 in pulses and mm/deg.
"""

from __future__ import annotations

import collections
import os
import sys
from typing import Deque, Dict, List, Optional

from qtpy import uic
from qtpy.QtCore import Qt, QTimer
from qtpy.QtGui import QColor, QFont, QFontDatabase, QPainter, QPen, QPalette
from qtpy.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QDoubleSpinBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
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
    UI_PARAM_DEFS,
    UI_PARAM_KEYS,
    PARAM_BY_KEY,
    AxisTuneParams,
    apply_axis_params,
    axis_unit,
    default_axis_params,
    delete_preset,
    format_params_summary,
    list_presets,
    load_preset,
    machine_is_on,
    read_axis_params,
    read_drive_ferr,
    save_preset,
    unit_to_counts,
)

try:
    import pyqtgraph as pg
except ImportError:  # pragma: no cover
    pg = None

FERR_SAMPLE_MS = 50
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
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
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
            self.plot.showGrid(x=True, y=True, alpha=0.3)
            for axis_name in ("left", "bottom"):
                axis = self.plot.getAxis(axis_name)
                axis.setPen(PLOT_FG)
                axis.setTextPen(PLOT_FG)
            self.plot.setLabel("bottom", "samples", color=PLOT_FG)
            self.plot.setLabel("left", self._unit_label, color=PLOT_FG)
            self.curve = self.plot.plot(pen=pg.mkPen(color=PLOT_LINE, width=2))
            self.plot.addLine(y=0, pen=pg.mkPen(color=PLOT_ZERO, width=1, style=Qt.DashLine))
            root.addWidget(self.plot)
        else:
            self._painter_mode = True
            self.plot = None
            self.curve = None

    def set_unit_label(self, unit: str) -> None:
        self._unit_label = unit
        if self.plot is not None:
            self.plot.setLabel("left", unit, color=PLOT_FG)

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
            self.curve.setData(list(range(len(values))), values)
            finite = [v for v in values if v == v]
            if finite:
                peak = max(abs(min(finite)), abs(max(finite)), 1e-6)
                pad = peak * 0.15
                self.plot.setYRange(-peak - pad, peak + pad, padding=0)
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
        self._did_initial_read = False
        self._ferr_unit_mode = "unit"  # "unit" (mm/deg) or "pulses"
        self._ferr_peak_pulses = 0.0
        self._ferr_peak_unit = 0.0
        self._pending_edits: Dict[str, QDoubleSpinBox] = {}
        self._current_labels: Dict[str, QLabel] = {}
        self._row_keys: List[str] = []

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
        root_layout.setSpacing(8)

        root_layout.addWidget(self._build_header(), stretch=0)

        body = QHBoxLayout()
        body.setSpacing(12)
        body.addLayout(self._build_params_column(), stretch=3)
        body.addWidget(self._build_presets_panel(), stretch=1)
        root_layout.addLayout(body, stretch=1)

        self.axis_buttons["X"].setChecked(True)
        self._refresh_preset_list()
        self._update_value_readouts()

    def _build_header(self) -> QFrame:
        header = QFrame(self)
        header.setObjectName("headerBar")
        header.setAttribute(Qt.WA_StyledBackground, True)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(14, 8, 14, 8)

        title = QLabel("SERVO TUNING", header)
        title.setObjectName("lblTitle")
        layout.addWidget(title)
        layout.addStretch()

        self.status_label = QLabel("READY", header)
        self.status_label.setObjectName("lblStatus")
        self.status_label.setProperty("state", "ok")
        layout.addWidget(self.status_label)
        return header

    def _build_params_column(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(8)

        axis_row = QHBoxLayout()
        axis_row.addWidget(self._caption("AXIS"))
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
            axis_row.addWidget(btn)
        axis_row.addStretch()
        col.addLayout(axis_row)

        action_row = QHBoxLayout()
        self.read_button = QPushButton("READ FROM DRIVE", self)
        self.read_button.setFocusPolicy(Qt.NoFocus)
        self.read_button.setToolTip(
            "Upload live SDOs into the table and store them as the revert baseline."
        )
        self.read_button.clicked.connect(self._read_from_drive)
        action_row.addWidget(self.read_button)

        self.apply_button = QPushButton("APPLY CHANGES", self)
        self.apply_button.setObjectName("btnPrimary")
        self.apply_button.setFocusPolicy(Qt.NoFocus)
        self.apply_button.setToolTip(
            "Disables motors, writes SDOs (C00/C01 need enable OFF), "
            "then re-enables motors if they were on."
        )
        self.apply_button.clicked.connect(self._apply_to_drive)
        action_row.addWidget(self.apply_button)

        self.revert_button = QPushButton("REVERT", self)
        self.revert_button.setFocusPolicy(Qt.NoFocus)
        self.revert_button.setToolTip(
            "Re-apply the last READ / APPLY baseline for this axis."
        )
        self.revert_button.clicked.connect(self._revert_to_baseline)
        action_row.addWidget(self.revert_button)

        self.defaults_button = QPushButton("LOAD DEFAULT", self)
        self.defaults_button.setFocusPolicy(Qt.NoFocus)
        self.defaults_button.setToolTip(
            "Load built-in defaults into Pending (not applied until APPLY)."
        )
        self.defaults_button.clicked.connect(self._load_form_defaults)
        action_row.addWidget(self.defaults_button)
        action_row.addStretch()
        col.addLayout(action_row)

        col.addWidget(self._build_ferr_group())
        col.addWidget(self._build_live_group())
        col.addWidget(self._build_param_table_group(), stretch=1)

        self.message_label = QLabel(
            "Drive FERR (60F4) plots live below. Edit inertia + feed-forward Pending → APPLY. "
            "FF source 0 = off; set source non-zero to enable. "
            "REVERT restores the last READ/APPLY baseline. "
            "LinuxCNC joint.f-error / INI FERROR are untouched.",
            self,
        )
        self.message_label.setObjectName("lblMessage")
        self.message_label.setWordWrap(True)
        col.addWidget(self.message_label)
        return col

    def _build_ferr_group(self) -> QGroupBox:
        group = QGroupBox("DRIVE FERR (CiA 60F4)", self)
        group.setObjectName("grpFerr")
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        top = QHBoxLayout()
        top.addWidget(self._caption("PLOT UNIT"))
        self.ferr_unit_group = QButtonGroup(self)
        self.btn_ferr_unit = QPushButton("MM / DEG", group)
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
        top.addWidget(self.btn_ferr_unit)
        top.addWidget(self.btn_ferr_pulses)
        top.addStretch()

        clear_btn = QPushButton("CLEAR PLOT", group)
        clear_btn.setFocusPolicy(Qt.NoFocus)
        clear_btn.clicked.connect(self._clear_ferr_plot)
        top.addWidget(clear_btn)
        layout.addLayout(top)

        readouts = QHBoxLayout()
        self.ferr_pulses_label = QLabel("PULSES: —", group)
        self.ferr_pulses_label.setObjectName("lblFerrValue")
        self.ferr_unit_value_label = QLabel("MM: —", group)
        self.ferr_unit_value_label.setObjectName("lblFerrValue")
        self.ferr_peak_label = QLabel("PEAK ABS: —", group)
        self.ferr_peak_label.setObjectName("lblFerrValue")
        readouts.addWidget(self.ferr_pulses_label)
        readouts.addWidget(self.ferr_unit_value_label)
        readouts.addWidget(self.ferr_peak_label)
        readouts.addStretch()
        layout.addLayout(readouts)

        self.ferr_plot = FerrPlotWidget(group)
        layout.addWidget(self.ferr_plot, stretch=1)

        hint = QLabel(
            "Both pulses and mm/deg are always shown. Toggle only changes the plot scale. "
            "Source: lcec ferr-fb → tune-drive-ferr (not joint.f-error).",
            group,
        )
        hint.setObjectName("lblParamHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        return group

    def _build_live_group(self) -> QGroupBox:
        group = QGroupBox("CURRENT ON DRIVE", self)
        group.setObjectName("grpLive")
        layout = QVBoxLayout(group)
        layout.setSpacing(4)

        self.live_label = QLabel("Not read yet — press READ FROM DRIVE.", group)
        self.live_label.setObjectName("lblLiveValues")
        self.live_label.setWordWrap(True)
        layout.addWidget(self.live_label)

        self.baseline_label = QLabel("Baseline: none", group)
        self.baseline_label.setObjectName("lblParamHint")
        self.baseline_label.setWordWrap(True)
        layout.addWidget(self.baseline_label)
        return group

    def _build_param_table_group(self) -> QGroupBox:
        group = QGroupBox("INERTIA + FEED-FORWARD (Pending → APPLY)", self)
        group.setObjectName("grpParams")
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        hint = QLabel(
            "C00.06 inertia, plus C01.13–18 feed-forward. "
            "Source is the enable: 0 = off, non-zero enables that FF path. "
            "APPLY writes only these SDOs (other gains left alone).",
            group,
        )
        hint.setObjectName("lblParamHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        table_actions = QHBoxLayout()
        copy_btn = QPushButton("COPY CURRENT → PENDING", group)
        copy_btn.setFocusPolicy(Qt.NoFocus)
        copy_btn.clicked.connect(self._copy_current_to_pending)
        table_actions.addWidget(copy_btn)
        table_actions.addStretch()
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
        header = self.param_table.horizontalHeader()
        header.setSectionResizeMode(COL_PARAM, QHeaderView.Stretch)
        header.setSectionResizeMode(COL_CURRENT, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(COL_PENDING, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(COL_UNIT, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(COL_RANGE, QHeaderView.ResizeToContents)
        self.param_table.setMinimumHeight(220)

        self._populate_param_table()
        layout.addWidget(self.param_table, stretch=1)
        return group

    def _populate_param_table(self) -> None:
        self.param_table.setRowCount(0)
        self._pending_edits.clear()
        self._current_labels.clear()
        self._row_keys.clear()

        last_group = None
        for defn in UI_PARAM_DEFS:
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
        if key in ("speed_ff_source", "torque_ff_source"):
            spin.setToolTip(
                "\n".join(f"{k}: {v}" for k, v in sorted(FF_SOURCE_LABELS.items()))
            )
        self.param_table.setCellWidget(row, COL_PENDING, spin)
        self._pending_edits[key] = spin

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

    def _build_presets_panel(self) -> QGroupBox:
        group = QGroupBox("AXIS PRESETS", self)
        group.setObjectName("grpPresets")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        hint = QLabel(
            "Saved under config/tuning/presets/<axis>/*.json — "
            "LOAD fills Pending; LOAD + APPLY writes the drive.",
            group,
        )
        hint.setObjectName("lblParamHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.preset_list = QListWidget(group)
        self.preset_list.itemDoubleClicked.connect(
            lambda _item: self._load_selected_preset(apply=False)
        )
        layout.addWidget(self.preset_list, stretch=1)

        self.preset_name_edit = QLineEdit(group)
        self.preset_name_edit.setPlaceholderText("Preset name")
        layout.addWidget(self.preset_name_edit)

        self.preset_notes_edit = QTextEdit(group)
        self.preset_notes_edit.setPlaceholderText("Notes (optional)")
        self.preset_notes_edit.setMaximumHeight(72)
        layout.addWidget(self.preset_notes_edit)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("SAVE", group)
        save_btn.setObjectName("btnPrimary")
        save_btn.setFocusPolicy(Qt.NoFocus)
        save_btn.clicked.connect(self._save_preset)
        btn_row.addWidget(save_btn)

        load_btn = QPushButton("LOAD", group)
        load_btn.setFocusPolicy(Qt.NoFocus)
        load_btn.clicked.connect(lambda: self._load_selected_preset(apply=False))
        btn_row.addWidget(load_btn)
        layout.addLayout(btn_row)

        btn_row2 = QHBoxLayout()
        load_apply_btn = QPushButton("LOAD + APPLY", group)
        load_apply_btn.setFocusPolicy(Qt.NoFocus)
        load_apply_btn.clicked.connect(lambda: self._load_selected_preset(apply=True))
        btn_row2.addWidget(load_apply_btn)

        delete_btn = QPushButton("DELETE", group)
        delete_btn.setObjectName("btnDanger")
        delete_btn.setFocusPolicy(Qt.NoFocus)
        delete_btn.clicked.connect(self._delete_preset)
        btn_row2.addWidget(delete_btn)
        layout.addLayout(btn_row2)

        refresh_btn = QPushButton("REFRESH LIST", group)
        refresh_btn.setFocusPolicy(Qt.NoFocus)
        refresh_btn.clicked.connect(self._refresh_preset_list)
        layout.addWidget(refresh_btn)
        return group

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
            self.read_button,
            self.apply_button,
            self.revert_button,
            self.defaults_button,
            *self.axis_buttons.values(),
        ):
            widget.setEnabled(not busy)
        if busy:
            self._set_status("BUSY", "busy")

    def _update_value_readouts(self) -> None:
        live = self._live.get(self._axis)
        if live is None:
            self.live_label.setText("Not read yet — press READ FROM DRIVE.")
        else:
            self.live_label.setText(format_params_summary(live, self._axis))

        baseline = self._baseline.get(self._axis)
        if baseline is None:
            self.baseline_label.setText("Baseline: none (READ or APPLY to set)")
            self.revert_button.setEnabled(False)
        else:
            self.baseline_label.setText(
                "Baseline (REVERT target): "
                + format_params_summary(baseline, self._axis)
            )
            self.revert_button.setEnabled(True)

    def _store_baseline(self, params: AxisTuneParams) -> None:
        self._baseline[self._axis] = params.copy()
        self._live[self._axis] = params.copy()
        self._update_value_readouts()

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
        if not checked:
            return
        if self.btn_ferr_unit.isChecked():
            self._ferr_unit_mode = "unit"
        else:
            self._ferr_unit_mode = "pulses"
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
        self.ferr_peak_label.setText("PEAK ABS: —")

    def _poll_ferr(self) -> None:
        if not self.isVisible():
            return
        try:
            counts, scaled = read_drive_ferr(self._axis)
        except Exception:
            return

        unit = axis_unit(self._axis)
        if counts == counts:
            self.ferr_pulses_label.setText(f"PULSES: {counts:.0f}")
            self._ferr_peak_pulses = max(self._ferr_peak_pulses, abs(counts))
        else:
            self.ferr_pulses_label.setText("PULSES: —")

        if scaled == scaled:
            self.ferr_unit_value_label.setText(f"{unit.upper()}: {scaled:.4f}")
            self._ferr_peak_unit = max(self._ferr_peak_unit, abs(scaled))
        else:
            self.ferr_unit_value_label.setText(f"{unit.upper()}: —")

        if self._ferr_unit_mode == "pulses":
            plot_val = counts
            peak_txt = (
                f"PEAK ABS: {self._ferr_peak_pulses:.0f} p / "
                f"{self._ferr_peak_unit:.4f} {unit}"
                if self._ferr_peak_pulses or self._ferr_peak_unit
                else "PEAK ABS: —"
            )
        else:
            plot_val = scaled
            peak_txt = (
                f"PEAK ABS: {self._ferr_peak_unit:.4f} {unit} / "
                f"{self._ferr_peak_pulses:.0f} p"
                if self._ferr_peak_pulses or self._ferr_peak_unit
                else "PEAK ABS: —"
            )
        self.ferr_peak_label.setText(peak_txt)
        if plot_val == plot_val:
            self.ferr_plot.push(plot_val)

    def _refresh_unit_columns(self) -> None:
        for row, key in enumerate(self._row_keys):
            if not key:
                continue
            defn = PARAM_BY_KEY.get(key)
            if not defn:
                continue
            item = self.param_table.item(row, COL_UNIT)
            if item is not None:
                item.setText(self._unit_text_for_defn(defn))

    def _format_current(self, key: str, value: float) -> str:
        defn = PARAM_BY_KEY[key]
        decimals = int(defn.get("decimals", 1))
        if key in ("speed_ff_source", "torque_ff_source"):
            label = FF_SOURCE_LABELS.get(int(value), str(int(value)))
            return f"{int(value)} ({label})"
        if key == "following_error":
            unit = axis_unit(self._axis)
            counts = unit_to_counts(self._axis, value)
            return f"{value:.{decimals}f} {unit} / {counts} p"
        if decimals == 0:
            return f"{int(round(value))}"
        return f"{value:.{decimals}f}"

    def _params_from_ui(self) -> AxisTuneParams:
        # Start from last live/baseline so non-UI catalog keys stay intact in presets.
        base = self._live.get(self._axis) or self._baseline.get(self._axis)
        values = dict(base.values) if base is not None else None
        params = AxisTuneParams(values=values)
        for key, spin in self._pending_edits.items():
            params.set(key, float(spin.value()))
        return params

    def _set_params_to_ui(self, params: AxisTuneParams) -> None:
        self._syncing = True
        for key, spin in self._pending_edits.items():
            spin.setValue(params.get(key))
        for key, label in self._current_labels.items():
            label.setText(self._format_current(key, params.get(key)))
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
        defaults = default_axis_params()
        self._syncing = True
        for key, spin in self._pending_edits.items():
            spin.setValue(defaults.get(key))
        self._syncing = False
        self.message_label.setText(
            "Pending loaded with built-in inertia/FF defaults (not applied). "
            "Press APPLY to write, or REVERT to restore the last baseline."
        )

    def _read_from_drive(self) -> None:
        self._set_busy(True)
        try:
            params = read_axis_params(self._axis)
            self._set_params_to_ui(params)
            self._store_baseline(params)
            self._set_status(f"READ {self._axis}", "ok")
            self.message_label.setText(
                f"Live values from slave {AXES[self._axis]['slave']} "
                f"loaded into Current/Pending and saved as REVERT baseline."
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
        if params is None:
            params = self._params_from_ui()
        was_on = machine_is_on()
        cycle_note = (
            "Motors are ON — they will be disabled, parameters written, "
            "then re-enabled."
            if was_on
            else "Motors are already OFF — parameters will be written as-is."
        )
        reply = QMessageBox.question(
            self,
            "Apply changes",
            f"Apply tuning to axis {self._axis} "
            f"(slave {AXES[self._axis]['slave']})?\n\n"
            f"{cycle_note}\n\n"
            "C00/C01 SDOs often reject writes while the servo is enabled.\n"
            "SDO changes are RAM-only until stored in the drive.\n"
            "Ensure the machine is idle (no running program).",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self._set_busy(True)
        self._set_status("APPLYING", "busy")
        self.message_label.setText(
            "Disabling motors / writing SDOs…"
            if was_on
            else "Writing SDOs…"
        )
        try:
            result = apply_axis_params(
                self._axis,
                params,
                cycle_enable=True,
                keys=UI_PARAM_KEYS,
            )
            self._set_params_to_ui(params)
            self._store_baseline(params)
            self._set_status(f"APPLIED {self._axis}", "ok")
            if result.get("cycled_enable"):
                self.message_label.setText(
                    f"Applied to slave {result['slave']}: "
                    "motors disabled → SDOs written → motors re-enabled. "
                    "Baseline updated."
                )
            else:
                self.message_label.setText(
                    f"Applied to slave {result['slave']} (motors stayed off). "
                    "Baseline updated. Enable the machine when ready to test."
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
        if baseline is None:
            QMessageBox.information(
                self,
                "Revert",
                "No baseline yet. Press READ FROM DRIVE first "
                "(or APPLY once to set a baseline).",
            )
            return
        self._set_params_to_ui(baseline)
        self.message_label.setText(
            "Form restored to baseline — confirm APPLY to write it back to the drive."
        )
        self._apply_to_drive(baseline)

    def _refresh_preset_list(self) -> None:
        self.preset_list.clear()
        for name in list_presets(self._axis):
            self.preset_list.addItem(name)
        if self.preset_list.count() and self.preset_list.currentRow() < 0:
            self.preset_list.setCurrentRow(0)

    def _selected_preset_name(self) -> str:
        item = self.preset_list.currentItem()
        return item.text() if item is not None else ""

    def _save_preset(self) -> None:
        name = self.preset_name_edit.text().strip() or self._selected_preset_name()
        if not name:
            QMessageBox.information(self, "Save preset", "Enter a preset name.")
            return
        notes = self.preset_notes_edit.toPlainText().strip()
        try:
            path = save_preset(self._axis, name, self._params_from_ui(), notes=notes)
            self.preset_name_edit.setText(name)
            self._refresh_preset_list()
            items = self.preset_list.findItems(name, Qt.MatchExactly)
            if items:
                self.preset_list.setCurrentItem(items[0])
            self.message_label.setText(f"Saved preset: {path}")
        except Exception as exc:
            LOG.exception("save_preset failed")
            QMessageBox.warning(self, "Save failed", str(exc))

    def _load_selected_preset(self, apply: bool = False) -> None:
        name = self._selected_preset_name()
        if not name:
            QMessageBox.information(self, "Load preset", "Select a preset from the list.")
            return
        try:
            preset = load_preset(self._axis, name)
            self._set_params_to_ui(preset.params)
            self.preset_name_edit.setText(preset.name)
            self.preset_notes_edit.setPlainText(preset.notes)
            self.message_label.setText(
                f"Loaded preset {preset.name!r} for axis {self._axis}."
            )
            if apply:
                self._apply_to_drive(preset.params)
        except Exception as exc:
            LOG.exception("load_preset failed")
            QMessageBox.warning(self, "Load failed", str(exc))

    def _delete_preset(self) -> None:
        name = self._selected_preset_name()
        if not name:
            return
        reply = QMessageBox.question(
            self,
            "Delete preset",
            f"Delete preset {name!r} for axis {self._axis}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            delete_preset(self._axis, name)
            self._refresh_preset_list()
            self.message_label.setText(f"Deleted preset {name!r}.")
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
                params = read_axis_params(self._axis)
                self._set_params_to_ui(params)
                self._store_baseline(params)
                self.message_label.setText(
                    f"Auto-read slave {AXES[self._axis]['slave']} on tab open. "
                    "Edit Pending → APPLY, or REVERT to undo."
                )
            except Exception as exc:
                LOG.info("servo_tuner: initial read skipped: %s", exc)
                self.message_label.setText(
                    "Could not auto-read drive (EtherCAT / sudo?). "
                    "Press READ FROM DRIVE when ready. FERR plot still polls HAL."
                )
