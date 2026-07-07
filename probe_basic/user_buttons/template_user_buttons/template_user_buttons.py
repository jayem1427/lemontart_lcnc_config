import os
import linuxcnc

from qtpy import uic
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QWidget,
)

from qtpyvcp.plugins import getPlugin
from qtpyvcp.utilities import logger

LOG = logger.getLogger(__name__)

STATUS = getPlugin('status')
CMD = linuxcnc.command()
STAT = linuxcnc.stat()

INI_FILE = linuxcnc.ini(os.getenv('INI_FILE_NAME'))

BUTTON_STYLE = 'QPushButton {\n    font: 15pt "Bebas Kai";\n}'
ENTRY_STYLE = 'QLineEdit {\n    font: 13pt "Bebas Kai";\n}'


class UserButton(QWidget):
    def __init__(self, parent=None):
        super(UserButton, self).__init__(parent)
        ui_file = os.path.splitext(os.path.basename(__file__))[0] + ".ui"
        uic.loadUi(os.path.join(os.path.dirname(__file__), ui_file), self)
        self._install_set_z_control()

    def _install_set_z_control(self):
        """Replace the unused middle-column label with a SET Z entry + button."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        self.set_z_entry = QLineEdit()
        self.set_z_entry.setPlaceholderText("Z mm")
        self.set_z_entry.setStyleSheet(ENTRY_STYLE)
        self.set_z_entry.setAlignment(Qt.AlignRight)
        self.set_z_entry.returnPressed.connect(self._set_wco_z)

        self.set_z_button = QPushButton("SET Z")
        self.set_z_button.setMinimumSize(55, 42)
        self.set_z_button.setMaximumHeight(42)
        self.set_z_button.setFocusPolicy(Qt.NoFocus)
        self.set_z_button.setStyleSheet(BUTTON_STYLE)
        self.set_z_button.setToolTip(
            "Set active WCO Z at the current position.\n"
            "Examples: 0.05 after a 50µm shim touch-off, -5.00 if 5 mm below the part."
        )
        self.set_z_button.clicked.connect(self._set_wco_z)

        layout.addWidget(self.set_z_entry, 1)
        layout.addWidget(self.set_z_button)

        self.gridLayout.replaceWidget(self.label, container)
        self.label.deleteLater()

    def _parse_z_value(self, text):
        text = text.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            raise ValueError(f"Invalid Z value: {text}")

    def _set_wco_z(self):
        try:
            value = self._parse_z_value(self.set_z_entry.text())
        except ValueError as exc:
            QMessageBox.warning(self, "Set WCO Z", str(exc))
            return

        if value is None:
            value, ok = QInputDialog.getDouble(
                self,
                "Set WCO Z",
                "Z coordinate at current position (mm):\n"
                "e.g. 0.05 for a 50µm shim, -5.00 if 5 mm below the part",
                0.0,
                -9999.0,
                9999.0,
                3,
            )
            if not ok:
                return
        else:
            ok = True

        self._run_mdi(f"o<set_wco_z> call [{value}]")
        if ok:
            self.set_z_entry.clear()

    def _run_mdi(self, cmd):
        try:
            STAT.poll()
            if STAT.estop:
                QMessageBox.warning(self, "Set WCO Z", "Machine is estopped.")
                return
            CMD.mode(linuxcnc.MODE_MDI)
            CMD.mdi(cmd)
        except linuxcnc.error as exc:
            LOG.error("Set WCO Z failed: %s", exc)
            QMessageBox.warning(self, "Set WCO Z", str(exc))
