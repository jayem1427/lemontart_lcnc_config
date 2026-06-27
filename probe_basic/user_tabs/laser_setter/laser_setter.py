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


# Button objectName  ->  MDI command string
BUTTON_MDI = {
    'btnMeasureLength':   "o<laser_length> call",
    'btnMeasureDiameter': "o<laser_diameter> call",
    'btnMeasureFull':     "o<laser_full_tool> call",
    'btnMeasureRunout':   "o<laser_runout> call",
    'btnBrokenCheck':     "o<laser_broken_check> call",
    'btnCalibrate':       "o<laser_calibrate> call",
    'btnAirBlastToggle':  "o<laser_air_blast_toggle> call",
    'btnMuxToggle':       "o<laser_mux_toggle> call",
}


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

    def _make_handler(self, mdi_cmd):
        def handler(checked=False):
            self._issue_mdi(mdi_cmd)
        return handler

    def _issue_mdi(self, mdi_cmd):
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
            self._set_status("SENT: " + mdi_cmd)
            LOG.info("laser_setter: %s", mdi_cmd)
        except Exception as exc:
            LOG.error("laser_setter: MDI failed (%s): %s", mdi_cmd, exc)
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
