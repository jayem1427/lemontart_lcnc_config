import os
import sys

from qtpy import uic
from qtpy.QtCore import Qt
from qtpy.QtCore import QTimer
from qtpy.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from qtpyvcp.utilities import logger

LOG = logger.getLogger(__name__)

PYTHON_DIR = os.path.join(
    os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)),
    "python",
)
if PYTHON_DIR not in sys.path:
    sys.path.insert(0, PYTHON_DIR)

from hal_signal_logger import HalSignalLogger, default_config_path, load_config  # noqa: E402
from signal_plot_widget import SignalPlotWidget  # noqa: E402


class UserTab(QWidget):
    def __init__(self, parent=None):
        super(UserTab, self).__init__(parent)
        ui_file = os.path.splitext(os.path.basename(__file__))[0] + ".ui"
        uic.loadUi(os.path.join(os.path.dirname(__file__), ui_file), self)

        self.logger = HalSignalLogger(
            load_config(default_config_path()),
            on_session_saved=self._on_session_saved,
        )
        self.plot_widget = None
        self._updating_controls = False

        self._build_controls()
        self._rebuild_plot()
        self._sync_controls()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(50)

    def _build_controls(self) -> None:
        root_layout = self.findChild(QVBoxLayout, "rootLayout")
        if root_layout is None:
            root_layout = QVBoxLayout(self)
            self.setLayout(root_layout)

        controls = QWidget(self)
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)

        row1 = QHBoxLayout()
        self.arm_checkbox = QCheckBox("Log signals for next program", controls)
        self.arm_checkbox.toggled.connect(self._on_arm_toggled)
        row1.addWidget(self.arm_checkbox)
        row1.addStretch()
        controls_layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.live_start_button = QPushButton("Start live log", controls)
        self.live_start_button.clicked.connect(self._start_live)
        row2.addWidget(self.live_start_button)

        self.live_stop_button = QPushButton("Stop live log", controls)
        self.live_stop_button.clicked.connect(self._stop_live)
        row2.addWidget(self.live_stop_button)

        self.status_label = QLabel("idle", controls)
        row2.addWidget(self.status_label, stretch=1)
        controls_layout.addLayout(row2)

        self.message_label = QLabel("", controls)
        self.message_label.setWordWrap(True)
        self.message_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        controls_layout.addWidget(self.message_label)

        root_layout.insertWidget(0, controls)
        self.plot_container = QWidget(self)
        self.plot_layout = QVBoxLayout(self.plot_container)
        self.plot_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(self.plot_container, stretch=1)

    def _rebuild_plot(self) -> None:
        while self.plot_layout.count():
            item = self.plot_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self.plot_widget = SignalPlotWidget(self.logger, self.plot_container)
        self.plot_layout.addWidget(self.plot_widget)

    def _sync_controls(self) -> None:
        self._updating_controls = True
        status = self.logger.status
        self.arm_checkbox.setChecked(self.logger.is_armed())
        self.arm_checkbox.setEnabled(status != "logging")
        self.live_start_button.setEnabled(status == "idle")
        self.live_stop_button.setEnabled(self.logger.is_live_session)
        self.status_label.setText(status)
        self._updating_controls = False

    def _on_arm_toggled(self, checked: bool) -> None:
        if self._updating_controls:
            return
        if checked:
            self.logger.arm_for_next_program()
            self.message_label.setText("Armed — logging starts when the next program runs.")
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
