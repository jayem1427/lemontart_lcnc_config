import os
import sys

from qtpy import uic
from qtpy.QtCore import QTimer
from qtpy.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
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

from hal_signal_logger import (  # noqa: E402
    HalSignalLogger,
    default_preset_dir,
    list_presets,
    load_preset,
)
from signal_plot_widget import SignalPlotWidget  # noqa: E402


class UserTab(QWidget):
    def __init__(self, parent=None):
        super(UserTab, self).__init__(parent)
        ui_file = os.path.splitext(os.path.basename(__file__))[0] + ".ui"
        uic.loadUi(os.path.join(os.path.dirname(__file__), ui_file), self)

        self.logger = None
        self.plot_widget = None

        self._build_controls()
        self._load_preset_list()
        self._on_preset_changed()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(50)

    def _build_controls(self) -> None:
        root_layout = self.findChild(QVBoxLayout, "rootLayout")
        if root_layout is None:
            root_layout = QVBoxLayout(self)
            self.setLayout(root_layout)

        controls = QWidget(self)
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)

        controls_layout.addWidget(QLabel("Preset:"))
        self.preset_combo = QComboBox(controls)
        controls_layout.addWidget(self.preset_combo, stretch=2)

        self.state_label = QLabel("idle")
        controls_layout.addWidget(self.state_label, stretch=1)

        self.start_button = QPushButton("Start log")
        self.start_button.clicked.connect(self._start_manual)
        controls_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop log")
        self.stop_button.clicked.connect(self._stop_manual)
        controls_layout.addWidget(self.stop_button)

        root_layout.insertWidget(0, controls)
        self.plot_container = QWidget(self)
        self.plot_layout = QVBoxLayout(self.plot_container)
        self.plot_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(self.plot_container, stretch=1)

        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)

    def _load_preset_list(self) -> None:
        self.preset_combo.clear()
        for path in list_presets():
            self.preset_combo.addItem(
                os.path.splitext(os.path.basename(path))[0],
                path,
            )
        if self.preset_combo.count() == 0:
            self.preset_combo.addItem(
                "cut_ferr",
                os.path.join(default_preset_dir(), "cut_ferr.json"),
            )

    def _on_preset_changed(self) -> None:
        preset_path = self.preset_combo.currentData()
        if not preset_path or not os.path.isfile(preset_path):
            return

        if self.logger is not None and self.logger.state == "logging":
            self.logger.stop_manual()

        self.logger = HalSignalLogger(load_preset(preset_path))
        self._rebuild_plot()

    def _rebuild_plot(self) -> None:
        while self.plot_layout.count():
            item = self.plot_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self.plot_widget = SignalPlotWidget(self.logger, self.plot_container)
        self.plot_layout.addWidget(self.plot_widget)

    def _start_manual(self) -> None:
        if self.logger is None:
            return
        name = self.preset_combo.currentText()
        self.logger.start_manual(name)

    def _stop_manual(self) -> None:
        if self.logger is None:
            return
        self.logger.stop_manual()

    def _tick(self) -> None:
        if self.logger is None:
            return
        self.logger.poll()
        self.state_label.setText(self.logger.state)
        if self.plot_widget is not None:
            self.plot_widget.refresh()
