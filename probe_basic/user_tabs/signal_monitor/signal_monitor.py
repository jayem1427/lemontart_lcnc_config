import os
import sys
import time
from typing import Optional

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
    "X": {"DRIVE": "x_ferr_drive", "TORQUE": "x_torque", "VEL": "x_vel", "POS": "x_pos"},
    "Y": {"DRIVE": "y_ferr_drive", "TORQUE": "y_torque", "VEL": "y_vel", "POS": "y_pos"},
    "Z": {"DRIVE": "z_ferr_drive", "TORQUE": "z_torque", "VEL": "z_vel", "POS": "z_pos"},
    "A": {"DRIVE": "a_ferr_drive", "TORQUE": "a_torque", "VEL": "a_vel", "POS": "a_pos"},
}

# SPINDLE mode reuses the four toggle slots as VFD channel picks (not machine axes).
SPINDLE_SIGNALS = {
    "X": "spindle_rpm_cmd",
    "Y": "spindle_rpm_fb",
    "Z": "spindle_amps",
    "A": "spindle_at_speed",
}
SPINDLE_BUTTON_LABELS = {
    "X": "CMD",
    "Y": "FB",
    "Z": "A",
    "A": "RDY",
}
SPINDLE_BUTTON_TIPS = {
    "X": "Commanded spindle RPM (spindle.0.speed-out-abs)",
    "Y": "VFD speed feedback → spindle.0.speed-in (RPM)",
    "Z": "VFD output current (mult2.6.out, amps)",
    "A": "At-speed flag (spindle.0.at-speed)",
}

SIGNAL_Y_DEFAULTS = {
    "DRIVE": "Fixed ±0.25",
    "TORQUE": "Fixed ±100%",
    "VEL": "Symmetric",
    "POS": "Auto",
    "SPINDLE": "Auto",
}

SIGNAL_UNITS = {
    "DRIVE": "mm",
    "TORQUE": "%",
    "VEL": "mm/min",
    "POS": "mm",
    "SPINDLE": "rpm",
}

AXIS_ORDER = ("X", "Y", "Z", "A")
AXIS_BUTTON_DEFAULTS = {axis: axis for axis in AXIS_ORDER}
RATE_HZ_OPTIONS = (25, 50, 100, 200, 500, 1000)
# HAL reads must run on the UI thread (same as Servo Tuning). Keep the timer
# fast enough to catch the sample rate; plot redraw stays slower.
POLL_MS_LOGGING = 10
POLL_MS_ARMED = 100
PLOT_REFRESH_MS = 100


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
        self._current_signal = "DRIVE"
        self._last_status = None
        self._last_plot_refresh = 0.0

        # Timer before first _sync_controls (which calls _sync_timer).
        # Idle = stopped; only runs while logging or armed.
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

        self._build_controls()
        self._rebuild_plot()
        self._sync_controls()
        self._apply_plot_view()
        self._sync_timer()

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        self._sync_timer()

    def hideEvent(self, event):  # noqa: N802
        super().hideEvent(event)
        self._sync_timer()

    def _sync_timer(self) -> None:
        """Poll while logging or armed (even if another tab is focused).

        Plot refresh stays gated to visible+logging in ``_tick``. Leaving the
        Logging tab must not pause CSV capture or miss an armed program start.
        """
        logging = self.logger.status == "logging"
        armed = self.logger.is_armed()
        want = bool(logging or armed)
        if not want:
            if self.timer.isActive():
                self.timer.stop()
            return
        interval = POLL_MS_LOGGING if logging else POLL_MS_ARMED
        if self.timer.interval() != interval:
            self.timer.setInterval(interval)
        if not self.timer.isActive():
            self.timer.start()

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
        # Drive PDOs + host actual position (joint.pos-fb via linuxcnc.stat).
        for signal, label in (
            ("DRIVE", "DRIVE mm"),
            ("TORQUE", "TORQUE %"),
            ("VEL", "VEL mm/min"),
            ("POS", "POS mm"),
            ("SPINDLE", "SPINDLE"),
        ):
            btn = QPushButton(label, panel)
            btn.setObjectName("btnSignal")
            btn.setCheckable(True)
            btn.setFocusPolicy(Qt.NoFocus)
            if signal == "DRIVE":
                btn.setToolTip(
                    "Drive following error (CiA 60F4) — mm on XYZ, deg on A "
                    "(same signal as Servo Tuning)"
                )
            elif signal == "TORQUE":
                btn.setToolTip("Drive torque feedback (CiA 6077), % of rated torque")
            elif signal == "VEL":
                btn.setToolTip(
                    "Drive velocity feedback (CiA 606C) — mm/min on XYZ, deg/min on A"
                )
            elif signal == "POS":
                btn.setToolTip(
                    "Actual joint position (joint.N.pos-fb) — mm on XYZ, deg on A"
                )
            elif signal == "SPINDLE":
                btn.setToolTip(
                    "H100 VFD: commanded RPM, feedback RPM, output amps, at-speed. "
                    "Toggles become CMD / FB / A / RDY. Fault + raw freq also go to CSV."
                )
            self.signal_group.addButton(btn)
            btn.toggled.connect(
                lambda checked, sig=signal: self._on_signal_toggled(sig, checked)
            )
            self.signal_buttons[signal] = btn
            row_view.addWidget(btn)

        self._syncing_selection = True
        self.axis_buttons["X"].setChecked(True)
        self.signal_buttons["DRIVE"].setChecked(True)
        self._syncing_selection = False
        self._sync_axis_button_labels()

        row_view.addSpacing(16)
        row_view.addWidget(self._caption_label("Y SCALE", panel))

        self.scale_combo = QComboBox(panel)
        self.scale_combo.setObjectName("cmbYScale")
        self.scale_combo.addItems(SCALE_MODES)
        self.scale_combo.setCurrentText(SIGNAL_Y_DEFAULTS["DRIVE"])
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

    def _sync_axis_button_labels(self) -> None:
        """Axis toggles become VFD channel picks in SPINDLE mode."""
        spindle = self._current_signal == "SPINDLE"
        for axis, btn in self.axis_buttons.items():
            if spindle:
                btn.setText(SPINDLE_BUTTON_LABELS[axis])
                btn.setToolTip(SPINDLE_BUTTON_TIPS[axis])
            else:
                btn.setText(AXIS_BUTTON_DEFAULTS[axis])
                btn.setToolTip("Click to toggle this axis on the plot")

    def _channel_id_for_toggle(self, axis: str) -> Optional[str]:
        if self._current_signal == "SPINDLE":
            return SPINDLE_SIGNALS.get(axis)
        return AXIS_SIGNALS[axis].get(self._current_signal)

    def _update_fixed_legend(self) -> None:
        if not hasattr(self, "_legend_rows"):
            return

        titles = {
            "DRIVE": "DRIVE FERR (mm / deg)",
            "TORQUE": "TORQUE (% rated)",
            "VEL": "VELOCITY (mm/min / deg/min)",
            "POS": "POSITION (mm / deg)",
            "SPINDLE": "SPINDLE / VFD",
        }
        self.legend_title.setText(titles.get(self._current_signal, "LEGEND"))

        channels = self.logger.channel_by_id()
        for axis in AXIS_ORDER:
            swatch, text = self._legend_rows[axis]
            channel_id = self._channel_id_for_toggle(axis)
            channel = channels.get(channel_id) if channel_id else None
            if channel is None:
                swatch.setStyleSheet(
                    "background-color: #555; border: 1px solid #8a8484; "
                    "border-radius: 2px;"
                )
                text.setText(axis)
                continue

            unit = f"  {channel.units}" if channel.units else ""
            active = self.axis_buttons[axis].isChecked()
            border = "2px solid white" if active else "1px solid #8a8484"
            swatch.setStyleSheet(
                "background-color: {0}; border: {1}; border-radius: 2px;".format(
                    channel.color, border
                )
            )
            text.setText("{0}{1}".format(channel.label.upper(), unit))
            text.setProperty("active", "true" if active else "false")
            text.style().unpolish(text)
            text.style().polish(text)

    def _active_channel_ids(self) -> set:
        axes = self._selected_axes()
        if not axes:
            return set()
        out = set()
        for axis in axes:
            cid = self._channel_id_for_toggle(axis)
            if cid:
                out.add(cid)
        return out

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

    def _apply_plot_view(self) -> None:
        if self.plot_widget is None:
            return
        channels = self._active_channel_ids()
        self.plot_widget.set_visible_channels(channels)
        self.plot_widget.set_scale_mode(self.scale_combo.currentText())
        self.plot_widget.set_y_unit(self._plot_y_unit(channels))
        self.plot_widget.refresh()
        self._update_fixed_legend()

    def _plot_y_unit(self, channel_ids: set) -> str:
        """Y-axis unit from visible channels (mixed → hint string)."""
        channels = self.logger.channel_by_id()
        units = []
        for cid in sorted(channel_ids):
            ch = channels.get(cid)
            if ch is not None and ch.units and ch.units not in units:
                units.append(ch.units)
        if not units:
            return SIGNAL_UNITS.get(self._current_signal, "value")
        if len(units) == 1:
            return units[0]
        return " / ".join(units)

    def _suggested_scale(self) -> str:
        if self._current_signal == "SPINDLE":
            # Prefer Auto — RPM and amps do not share a fixed scale.
            return "Auto"
        axes = self._selected_axes()
        if self._current_signal == "DRIVE":
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
        prev = self._current_signal
        self._current_signal = signal
        self._sync_axis_button_labels()
        # Entering SPINDLE: default to cmd+fb RPM (not amps on the same Y scale).
        if signal == "SPINDLE" and prev != "SPINDLE":
            self._syncing_selection = True
            self.axis_buttons["X"].setChecked(True)
            self.axis_buttons["Y"].setChecked(True)
            self.axis_buttons["Z"].setChecked(False)
            self.axis_buttons["A"].setChecked(False)
            self._syncing_selection = False
        elif signal != "SPINDLE" and prev == "SPINDLE":
            self._syncing_selection = True
            for axis, btn in self.axis_buttons.items():
                btn.setChecked(axis == "X")
            self._syncing_selection = False
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
        status = self.logger.status
        armed = self.logger.is_armed()
        # Avoid 100 Hz unpolish/polish — only update widgets when state changes.
        state_key = (status, armed, self.logger.is_live_session)
        if state_key == self._last_status:
            return
        self._last_status = state_key

        self._updating_controls = True
        self.arm_checkbox.setChecked(armed)
        self.arm_checkbox.setEnabled(status != "logging")
        self.live_start_button.setEnabled(status == "idle")
        self.live_stop_button.setEnabled(self.logger.is_live_session)

        if armed:
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
        self._sync_timer()

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
        self._last_status = None
        self._sync_controls()

    def _start_live(self) -> None:
        try:
            self.logger.start_live()
        except RuntimeError as exc:
            QMessageBox.warning(self, "Signal logging", str(exc))
            self.message_label.setText(str(exc))
            self._last_status = None
            self._sync_controls()
            return
        self.message_label.setText("Live logging — HAL sampled on UI thread (same as Servo Tuning).")
        self._last_status = None
        self._sync_controls()

    def _stop_live(self) -> None:
        self.logger.stop()
        self._last_status = None
        self._sync_controls()

    def _on_session_saved(self, csv_path: str, _summary_path: str) -> None:
        self.message_label.setText(f"Log saved: {csv_path}")
        QMessageBox.information(
            self,
            "Signal log saved",
            f"Log saved:\n{csv_path}",
        )
        self._last_status = None
        self._sync_controls()

    def _tick(self) -> None:
        prev_error = self.logger.last_error
        self.logger.poll()
        if self.logger.last_error and self.logger.last_error != prev_error:
            self.message_label.setText(self.logger.last_error)
        self._sync_controls()
        if self.plot_widget is None or self.logger.status != "logging":
            return
        if not self.isVisible():
            return
        now = time.monotonic()
        if (now - self._last_plot_refresh) * 1000.0 < PLOT_REFRESH_MS:
            return
        self._last_plot_refresh = now
        self.plot_widget.refresh()
