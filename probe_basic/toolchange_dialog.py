"""Manual tool-change dialog with ABORT CYCLE on the prompt."""

from __future__ import annotations

import os
import time

import linuxcnc
from qtpy import uic
from qtpyvcp import hal
from qtpyvcp.plugins import getPlugin
from qtpyvcp.widgets.dialogs.base_dialog import BaseDialog


class ToolChangeDialog(BaseDialog):
    """Same HAL contract as qtpyvcp ToolChangeDialog, plus abort."""

    def __init__(self, *args, **kwargs):
        super(ToolChangeDialog, self).__init__(stay_on_top=True)

        self.tt = getPlugin("tooltable")
        self.tool_number = 0
        self._aborting = False

        default_ui = os.path.join(os.path.dirname(__file__), "toolchange_dialog_pb.ui")
        self.ui_file = kwargs.get("ui_file", default_ui)
        self.ui = uic.loadUi(self.ui_file, self)

        if hasattr(self.ui, "btnAbort"):
            self.ui.btnAbort.clicked.connect(self.abort_cycle)

        self._cmd = linuxcnc.command()
        self._stat = linuxcnc.stat()

        comp = hal.getComponent("qtpyvcp_manualtoolchange")
        comp.addPin("number", "s32", "in")
        self.change_pin = comp.addPin("change", "bit", "in")
        self.changed_pin = comp.addPin("changed", "bit", "out")
        comp.addPin("change_button", "bit", "in")

        comp.addListener("number", self.prepare_tool)
        comp.addListener("change", self.on_change)
        comp.addListener("change_button", self.on_change_button)
        self.startTimer(100)
        self.hide()

    def timerEvent(self, timer):
        if not self.change_pin.value:
            self.changed_pin.value = False
            if self.isVisible():
                self.hide()

    def prepare_tool(self, tool_no):
        if self.tool_number == tool_no:
            return
        tool_data = self.tt.getToolTable().get(tool_no, {})
        tool_r = tool_data.get("R", "UNKNOWN")
        self.ui.lblToolNumber.setText(str(tool_no))
        self.ui.lblToolRemark.setText(tool_r)
        self.tool_number = tool_no

    def on_change(self, value=True):
        if value and not self._aborting:
            self.show()

    def on_change_button(self, value=True):
        if value:
            self.accept()

    def reject(self):
        # Ignore window close / Esc — use ABORT CYCLE explicitly.
        pass

    def accept(self):
        self.changed_pin.value = True

    def _wait_idle(self, timeout_s=5.0):
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            self._stat.poll()
            if self._stat.interp_state == linuxcnc.INTERP_IDLE:
                return True
            time.sleep(0.05)
        return False

    def abort_cycle(self):
        """Cancel tool change / job; park at tool-load XY if still enabled."""
        self._aborting = True
        try:
            # Drop the change request so LinuxCNC does not stay waiting on M6.
            self.changed_pin.value = True
            self.hide()

            self._cmd.abort()
            self._wait_idle()

            self._stat.poll()
            # After e-stop the machine is disabled — skip park moves
            # (would error: need to be enabled, in coord mode for linear move).
            if self._stat.estop or not self._stat.enabled:
                return

            self._cmd.mode(linuxcnc.MODE_MDI)
            self._cmd.wait_complete()
            self._cmd.mdi("o<abort_tool_change> call")
        finally:
            self._aborting = False
