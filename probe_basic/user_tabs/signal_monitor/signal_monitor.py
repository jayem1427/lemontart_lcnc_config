import os
import sys

from qtpy import uic
from qtpy.QtCore import Qt
from qtpy.QtCore import QTimer
from qtpy.QtGui import QColor, QFont, QFontDatabase, QPalette
from qtpy.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
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

from hal_signal_logger import HalSignalLogger, default_config_path, load_config  # noqa: E402
from signal_plot_widget import LiveSignalPlotWidget, SCALE_MODES  # noqa: E402

AXIS_SIGNALS = {
    "X": {"FERR": "x_ferr", "DRIVE": "x_ferr_drive", "TORQUE": "x_torque", "VEL": "x_vel"},
    "Y": {"FERR": "y_ferr", "DRIVE": "y_ferr_drive", "TORQUE": "y_torque", "VEL": "y_vel"},
    "Z": {"FERR": "z_ferr", "DRIVE": "z_ferr_drive", "TORQUE": "z_torque", "VEL": "z_vel"},
    "A": {"FERR": "a_ferr", "DRIVE": "a_ferr_drive", "TORQUE": "a_torque", "VEL": "a_vel"},
}

SIGNAL_Y_DEFAULTS = {
    "FERR": "Fixed ±0.25",
    "DRIVE": "Fixed ±0.25",
    "TORQUE": "Fixed ±100%",
    "VEL": "Symmetric",
}

AXIS_ORDER = ("X", "Y", "Z", "A")
RATE_HZ_OPTIONS = (25, 50, 100, 200, 500, 1000)


class UserTab(QWidget):
    def __init__(self, parent=None):
        super(UserTab, self).__init__(parent)
        ui_file = os.path.splitext(os.path.basename(__file__))[0] + ".ui"
        here = os.path.dirname(os.path.abspath(__file__))
        uic.loadUi(os.path.join(here, ui_file), self)

        self.setObjectName("SIGNAL_LOGGING")
        self._ensure_font()
        self._load_stylesheet(here)
        self._apply_panel_background()

        self.logger = HalSignalLogger(
            load_config(default_config_path()),
            on_session_saved=self._on_session_saved,
        )
        self.plot_widget = None
        self._updating_controls = False
        self._syncing_selection = False
        self._current_signal = "FERR"

        self._build_controls()
        self._rebuild_plot()
        self._sync_controls()
        self._apply_plot_view()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(10)

    def _ensure_font(self):
        if os.path.exists(PB_FONT_PATH):
            QFontDatabase.addApplicationFont(PB_FONT_PATH)
        self.setFont(QFont(PB_FONT))

    def _load_stylesheet(self, here):
        qss_path = os.path.join(here, "signal_monitor.qss")
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as handle:
                self.setStyleSheet(handle.read())

    def _apply_panel_background(self):
        panel = QColor(46, 52, 54)
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), panel)
        self.setPalette(palette)

    def _build_controls(self) -> None:
        root_layout = self.findChild(QVBoxLayout, "rootLayout")
        if root_layout is None:
            root_layout = QVBoxLayout(self)
            self.setLayout(root_layout)
        root_layout.setSpacing(8)

        header = QFrame(self)
        header.setObjectName("headerBar")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 8, 14, 8)

        title = QLabel("SIGNAL LOGGING", header)
        title.setObjectName("lblTitle")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.status_label = QLabel("IDLE", header)
        self.status_label.setObjectName("lblStatus")
        header_layout.addWidget(self.status_label)
        root_layout.addWidget(header, stretch=0)

        panel = QGroupBox("LOGGING", self)
        panel.setObjectName("grpLogging")
        panel.setAttribute(Qt.WA_StyledBackground, True)
        panel_body = QHBoxLayout(panel)
        panel_body.setSpacing(12)
        panel_body.setContentsMargins(10, 14, 10, 10)

        left_col = QVBoxLayout()
        left_col.setSpacing(8)

        row_log = QHBoxLayout()
        self.arm_checkbox = QCheckBox("LOG NEXT PROGRAM", panel)
        self.arm_checkbox.toggled.connect(self._on_arm_toggled)
        row_log.addWidget(self.arm_checkbox)

        self.live_start_button = QPushButton("START LIVE", panel)
        self.live_start_button.setObjectName("btnStartLive")
        self.live_start_button.setFocusPolicy(Qt.NoFocus)
        self.live_start_button.clicked.connect(self._start_live)
        row_log.addWidget(self.live_start_button)

        self.live_stop_button = QPushButton("STOP", panel)
        self.live_stop_button.setObjectName("btnStopLive")
        self.live_stop_button.setFocusPolicy(Qt.NoFocus)
        self.live_stop_button.clicked.connect(self._stop_live)
        row_log.addWidget(self.live_stop_button)
        row_log.addStretch()
        left_col.addLayout(row_log)

        row_view = QHBoxLayout()
        row_view.addWidget(self._caption_label("AXIS", panel))

        self.axis_buttons = {}
        for axis in AXIS_ORDER:
            btn = QPushButton(axis, panel)
            btn.setObjectName("btnAxis")
            btn.setCheckable(True)
            btn.setAutoExclusive(False)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setMinimumWidth(44)
            btn.setToolTip("Click to toggle this axis on the plot")
            btn.toggled.connect(
                lambda checked, ax=axis: self._on_axis_toggled(ax, checked)
            )
            self.axis_buttons[axis] = btn
            row_view.addWidget(btn)

        row_view.addSpacing(16)
        row_view.addWidget(self._caption_label("SIGNAL", panel))

        self.signal_group = QButtonGroup(panel)
        self.signal_group.setExclusive(True)
        self.signal_buttons = {}
        for signal in ("FERR", "DRIVE", "TORQUE", "VEL"):
            btn = QPushButton(signal, panel)
            btn.setObjectName("btnSignal")
            btn.setCheckable(True)
            btn.setFocusPolicy(Qt.NoFocus)
            self.signal_group.addButton(btn)
            btn.toggled.connect(
                lambda checked, sig=signal: self._on_signal_toggled(sig, checked)
            )
            self.signal_buttons[signal] = btn
            row_view.addWidget(btn)

        self._syncing_selection = True
        self.axis_buttons["X"].setChecked(True)
        self.signal_buttons["FERR"].setChecked(True)
        self._syncing_selection = False

        row_view.addSpacing(16)
        row_view.addWidget(self._caption_label("Y SCALE", panel))

        self.scale_combo = QComboBox(panel)
        self.scale_combo.setObjectName("cmbYScale")
        self.scale_combo.addItems(SCALE_MODES)
        self.scale_combo.setCurrentText(SIGNAL_Y_DEFAULTS["FERR"])
        self.scale_combo.currentTextChanged.connect(self._on_scale_changed)
        row_view.addWidget(self.scale_combo)

        row_view.addSpacing(16)
        row_view.addWidget(self._caption_label("RATE", panel))

        self.rate_combo = QComboBox(panel)
        self.rate_combo.setObjectName("cmbRate")
        for hz in RATE_HZ_OPTIONS:
            self.rate_combo.addItem(f"{hz} Hz", hz)
        default_hz = int(self.logger.rate_hz)
        idx = self.rate_combo.findData(default_hz)
        self.rate_combo.setCurrentIndex(idx if idx >= 0 else self.rate_combo.findData(100))
        self.rate_combo.currentIndexChanged.connect(self._on_rate_changed)
        row_view.addWidget(self.rate_combo)
        left_col.addLayout(row_view)

        self.message_label = QLabel("", panel)
        self.message_label.setObjectName("lblMessage")
        self.message_label.setWordWrap(True)
        self.message_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        left_col.addWidget(self.message_label)

        panel_body.addLayout(left_col, stretch=1)
        panel_body.addWidget(self._build_legend_panel(panel), stretch=0)

        self._update_fixed_legend()
        root_layout.addWidget(panel, stretch=0)

        self.plot_container = QWidget(self)
        self.plot_layout = QVBoxLayout(self.plot_container)
        self.plot_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(self.plot_container, stretch=7)

    def _caption_label(self, text: str, parent: QWidget) -> QLabel:
        label = QLabel(text, parent)
        label.setObjectName("lblCaption")
        return label

    def _build_legend_panel(self, parent: QWidget) -> QFrame:
        box = QFrame(parent)
        box.setObjectName("legendPanel")
        box.setAttribute(Qt.WA_StyledBackground, True)

        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(4)

        self.legend_title = QLabel("LEGEND", box)
        self.legend_title.setObjectName("legendTitle")
        layout.addWidget(self.legend_title)

        self._legend_rows = {}
        for axis in AXIS_ORDER:
            row_widget = QWidget(box)
            row = QHBoxLayout(row_widget)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(8)

            swatch = QLabel(row_widget)
            swatch.setObjectName("legendSwatch")
            swatch.setFixedSize(16, 16)

            text = QLabel(row_widget)
            text.setObjectName("legendLabel")

            row.addWidget(swatch)
            row.addWidget(text, stretch=1)
            layout.addWidget(row_widget)

            self._legend_rows[axis] = (swatch, text)

        layout.addStretch()
        return box

    def _update_fixed_legend(self) -> None:
        if not hasattr(self, "_legend_rows"):
            return

        titles = {
            "FERR": "FERR",
            "DRIVE": "DRIVE FERR",
            "TORQUE": "TORQUE",
            "VEL": "VELOCITY",
        }
        self.legend_title.setText(titles.get(self._current_signal, "LEGEND"))

        channels = self.logger.channel_by_id()
        for axis in AXIS_ORDER:
            swatch, text = self._legend_rows[axis]
            channel_id = AXIS_SIGNALS[axis][self._current_signal]
            channel = channels.get(channel_id)
            if channel is None:
                continue

            unit = f" ({channel.units})" if channel.units else ""
            active = self.axis_buttons[axis].isChecked()
            border = "2px solid white" if active else "1px solid #8a8484"
            swatch.setStyleSheet(
                "background-color: {0}; border: {1}; border-radius: 2px;".format(
                    channel.color, border
                )
            )
            text.setText("{0}{1}".format(channel.label, unit))
            text.setProperty("active", "true" if active else "false")
            text.style().unpolish(text)
            text.style().polish(text)

    def _rebuild_plot(self) -> None:
        while self.plot_layout.count():
            item = self.plot_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self.plot_widget = LiveSignalPlotWidget(self.logger, self.plot_container)
        self.plot_layout.addWidget(self.plot_widget)

    def _selected_axes(self) -> set:
        return {axis for axis, btn in self.axis_buttons.items() if btn.isChecked()}

    def _active_channel_ids(self) -> set:
        axes = self._selected_axes()
        if not axes:
            return set()
        return {AXIS_SIGNALS[axis][self._current_signal] for axis in axes}

    def _apply_plot_view(self) -> None:
        if self.plot_widget is None:
            return
        channels = self._active_channel_ids()
        self.plot_widget.set_visible_channels(channels)
        self.plot_widget.set_scale_mode(self.scale_combo.currentText())
        self.plot_widget.refresh()
        self._update_fixed_legend()

    def _suggested_scale(self) -> str:
        axes = self._selected_axes()
        if self._current_signal == "FERR" or self._current_signal == "DRIVE":
            if axes == {"A"}:
                return "Fixed ±60"
            if "A" in axes:
                return "Symmetric"
            return "Fixed ±0.25"
        return SIGNAL_Y_DEFAULTS.get(self._current_signal, "Auto")

    def _on_axis_toggled(self, axis: str, checked: bool) -> None:
        if self._syncing_selection:
            return
        self._maybe_update_scale()

    def _maybe_update_scale(self) -> None:
        suggested = self._suggested_scale()
        if self.scale_combo.currentText() != suggested:
            self._syncing_selection = True
            self.scale_combo.setCurrentText(suggested)
            self._syncing_selection = False
        self._apply_plot_view()

    def _on_signal_toggled(self, signal: str, checked: bool) -> None:
        if self._syncing_selection or not checked:
            return
        self._current_signal = signal
        self._update_fixed_legend()
        self._maybe_update_scale()

    def _on_scale_changed(self, _text: str) -> None:
        if self._syncing_selection:
            return
        self._apply_plot_view()

    def _on_rate_changed(self, _index: int) -> None:
        if self._syncing_selection:
            return
        hz = self.rate_combo.currentData()
        if hz is not None:
            self.logger.set_rate_hz(float(hz))

    def _sync_controls(self) -> None:
        self._updating_controls = True
        status = self.logger.status
        self.arm_checkbox.setChecked(self.logger.is_armed())
        self.arm_checkbox.setEnabled(status != "logging")
        self.live_start_button.setEnabled(status == "idle")
        self.live_stop_button.setEnabled(self.logger.is_live_session)

        if self.logger.is_armed():
            self.status_label.setText("ARMED")
            self.status_label.setProperty("state", "armed")
        elif status == "logging":
            self.status_label.setText("LOGGING")
            self.status_label.setProperty("state", "logging")
        else:
            self.status_label.setText(status.upper())
            self.status_label.setProperty("state", status)

        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self._updating_controls = False

    def _on_arm_toggled(self, checked: bool) -> None:
        if self._updating_controls:
            return
        if checked:
            self.logger.arm_for_next_program()
            self.message_label.setText("Armed — starts when next program runs in AUTO.")
        else:
            self.logger.disarm()
            if self.logger.status == "idle":
                self.message_label.setText("")
        self._sync_controls()

    def _start_live(self) -> None:
        self.logger.start_live()
        self.message_label.setText("Live logging — all signals to one CSV.")
        self._sync_controls()

    def _stop_live(self) -> None:
        self.logger.stop()

    def _on_session_saved(self, csv_path: str, _summary_path: str) -> None:
        self.message_label.setText(f"Log saved: {csv_path}")
        QMessageBox.information(
            self,
            "Signal log saved",
            f"Log saved:\n{csv_path}",
        )
        self._sync_controls()

    def _tick(self) -> None:
        self.logger.poll()
        self._sync_controls()
        if self.plot_widget is not None:
            self.plot_widget.refresh()
