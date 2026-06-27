"""
Laser Tool Setter — user tab for Probe Basic.

SKELETON ONLY. Buttons are wired to NGC subroutines that currently do nothing
except emit a DEBUG message. Real probing / calibration / runout logic will
land in later commits.

Lifecycle:
  PB scans USER_TABS_PATH on launch, imports this module, instantiates
  UserTab() and adds it as a main-window tab. The .ui file is loaded at
  runtime via uic.loadUi (no compile step needed).

MDI dispatch:
  Uses linuxcnc.command() directly rather than qtpyvcp.actions to stay
  decoupled from qtpyvcp API drift across the PyQt5 -> PySide6 transition.
  Trade-off: no fancy queueing, no integration with PB's MDI history.
  Acceptable for a skeleton; revisit once the macros do real work.
"""

import os

import linuxcnc

from qtpy import uic
from qtpy.QtWidgets import QWidget

from qtpyvcp.utilities import logger

LOG = logger.getLogger(__name__)
MM_PER_INCH = 25.4


# Button objectName  ->  MDI command string
BUTTON_MDI = {
    'btnMeasureLength':   "o<laser_length> call",
    'btnMeasureDiameter': "o<laser_diameter> call",
    'btnMeasureFull':     "o<laser_full_tool> call",
    'btnMeasureRunout':   "o<laser_runout> call",
    'btnBrokenCheck':     "o<laser_broken_check> call",
    'btnCalibrate':       "o<laser_calibrate> call",
    'btnAirBlastToggle':  "o<laser_air_blast_toggle> call",
    'btnUpdateToolTable': "o<laser_update_tool_table> call",
}

REQUIRES_Z_FIRST = {
    'btnMeasureDiameter',
    'btnMeasureRunout',
    'btnBrokenCheck',
}

LINEAR_VALUE_WIDGETS = (
    'lblResLength',
    'lblResDiam',
    'lblResRunout',
    'lblBeamX',
    'lblBeamY',
    'lblBeamZ',
    'lblZOffset',
    'lblBeamDia',
)

LINEAR_UNIT_WIDGETS = (
    'lblResLengthUnit',
    'lblResDiamUnit',
    'lblResRunoutUnit',
    'lblBeamXUnit',
    'lblBeamYUnit',
    'lblBeamZUnit',
    'lblZOffsetUnit',
    'lblBeamDiaUnit',
    'lblMasterPinUnit',
)


class UserTab(QWidget):
    def __init__(self, parent=None):
        super(UserTab, self).__init__(parent)

        here = os.path.dirname(os.path.abspath(__file__))
        uic.loadUi(os.path.join(here, "laser_setter.ui"), self)

        self._load_stylesheet(here)

        try:
            self._cmd = linuxcnc.command()
            self._stat = linuxcnc.stat()
        except Exception as exc:
            LOG.error("laser_setter: linuxcnc init failed: %s", exc)
            self._cmd = None
            self._stat = None

        self._wire_buttons()
        self._wire_abort()
        self._wire_start_position()
        self._init_units()
        self._z_touched = False

    def _load_stylesheet(self, here):
        qss_path = os.path.join(here, "laser_setter.qss")
        if not os.path.exists(qss_path):
            LOG.warning("laser_setter: stylesheet %s missing, using defaults", qss_path)
            return
        try:
            with open(qss_path, 'r') as fh:
                self.setStyleSheet(fh.read())
        except IOError as exc:
            LOG.error("laser_setter: failed to read stylesheet: %s", exc)

    def _wire_buttons(self):
        for obj_name, mdi_cmd in BUTTON_MDI.items():
            btn = getattr(self, obj_name, None)
            if btn is None:
                LOG.warning("laser_setter: button %s missing from .ui", obj_name)
                continue
            btn.clicked.connect(self._make_handler(mdi_cmd))

    def _wire_abort(self):
        btn = getattr(self, 'btnAbortSafe', None)
        if btn is None:
            return
        btn.clicked.connect(self._abort)

    def _wire_start_position(self):
        btn = getattr(self, 'btnGetStartPos', None)
        if btn is None:
            return
        btn.clicked.connect(self._capture_start_xy)

    def _init_units(self):
        self._display_units = 'mm'
        cmb = getattr(self, 'cmbUnits', None)
        if cmb is not None:
            cmb.clear()
            cmb.addItems(['mm', 'in'])
            cmb.setCurrentText(self._display_units)
            cmb.currentTextChanged.connect(self._on_units_changed)
        self._set_linear_unit_labels(self._display_units)

    def _on_units_changed(self, new_units):
        if new_units not in ('mm', 'in'):
            return
        old_units = getattr(self, '_display_units', 'mm')
        if old_units == new_units:
            return
        self._convert_linear_values(old_units, new_units)
        self._display_units = new_units
        self._set_linear_unit_labels(new_units)
        self._set_status("UNITS: " + new_units.upper())

    def _set_linear_unit_labels(self, units):
        for widget_name in LINEAR_UNIT_WIDGETS:
            widget = getattr(self, widget_name, None)
            if widget is not None:
                widget.setText(units)

    def _convert_linear_values(self, old_units, new_units):
        if old_units == new_units:
            return
        factor = 1.0 / MM_PER_INCH if old_units == 'mm' else MM_PER_INCH
        self._convert_numeric_widget('leMasterPin', factor)
        for widget_name in LINEAR_VALUE_WIDGETS:
            self._convert_numeric_widget(widget_name, factor)

    def _convert_numeric_widget(self, widget_name, factor):
        widget = getattr(self, widget_name, None)
        if widget is None:
            return
        try:
            value = float(widget.text().strip())
        except (AttributeError, ValueError):
            return
        widget.setText("{:.4f}".format(value * factor))

    def _make_handler(self, mdi_cmd):
        def handler(checked=False):
            btn = self.sender()
            btn_name = btn.objectName() if btn is not None else None
            if btn_name in REQUIRES_Z_FIRST and not self._z_touched:
                self._set_status("BLOCKED: TOUCH Z FIRST")
                LOG.warning("laser_setter: blocked %s until Z touch", btn_name)
                return
            self._issue_mdi(mdi_cmd, btn_name)
        return handler

    def _issue_mdi(self, mdi_cmd, btn_name=None):
        if self._cmd is None or self._stat is None:
            LOG.error("laser_setter: linuxcnc unavailable, cannot issue: %s", mdi_cmd)
            self._set_status("ERROR: linuxcnc unavailable")
            return
        try:
            self._stat.poll()
            if self._stat.estop:
                self._set_status("BLOCKED: E-STOP")
                LOG.warning("laser_setter: estop active, blocked: %s", mdi_cmd)
                return
            if not self._stat.enabled:
                self._set_status("BLOCKED: machine off")
                LOG.warning("laser_setter: not enabled, blocked: %s", mdi_cmd)
                return
            self._cmd.mode(linuxcnc.MODE_MDI)
            self._cmd.wait_complete()
            self._cmd.mdi(mdi_cmd)
            if btn_name in ('btnMeasureLength', 'btnMeasureFull'):
                self._z_touched = True
            self._set_status("SENT: " + mdi_cmd)
            LOG.info("laser_setter: %s", mdi_cmd)
        except Exception as exc:
            LOG.error("laser_setter: MDI failed (%s): %s", mdi_cmd, exc)
            self._set_status("ERROR: " + str(exc))

    def _capture_start_xy(self, checked=False):
        if self._cmd is None or self._stat is None:
            self._set_status("ERROR: linuxcnc unavailable")
            return
        try:
            self._stat.poll()
            if self._stat.estop:
                self._set_status("BLOCKED: E-STOP")
                return
            if not self._stat.enabled:
                self._set_status("BLOCKED: machine off")
                return

            x_pos = float(self._stat.position[0])
            y_pos = float(self._stat.position[1])

            self._cmd.mode(linuxcnc.MODE_MDI)
            self._cmd.wait_complete()
            self._cmd.mdi(
                "o<laser_set_start_xy> call [{:.6f}] [{:.6f}]".format(x_pos, y_pos)
            )
            self._set_status("START XY SET: X{:.4f} Y{:.4f}".format(x_pos, y_pos))
            LOG.info("laser_setter: start XY set to X%.6f Y%.6f", x_pos, y_pos)
        except Exception as exc:
            LOG.error("laser_setter: failed to capture start XY: %s", exc)
            self._set_status("ERROR: " + str(exc))

    def _abort(self, checked=False):
        if self._cmd is None:
            return
        try:
            self._cmd.abort()
            self._set_status("ABORTED")
            LOG.info("laser_setter: abort")
        except Exception as exc:
            LOG.error("laser_setter: abort failed: %s", exc)

    def _set_status(self, text):
        lbl = getattr(self, 'lblStatusBar', None)
        if lbl is not None:
            lbl.setText(text)
