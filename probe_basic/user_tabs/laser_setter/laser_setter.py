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
from qtpy.QtCore import Qt, QSize
from qtpy.QtGui import QImage, QPixmap, QColor, QPalette, QFont, QFontDatabase
from qtpy.QtWidgets import QWidget, QMessageBox

from qtpyvcp.utilities import logger

LOG = logger.getLogger(__name__)
MM_PER_INCH = 25.4
IMAGE_DISPLAY_SCALE = 0.624  # 20% larger than prior 0.52 setting
PB_FONT = "BebasKai"
PB_FONT_PATH = "/usr/share/fonts/truetype/BebasKai.ttf"

# Chroma key for green-screen tool setter photos. Uses green-channel dominance
# (not luminance/white) so the silver calibration plate is preserved.
_CHROMA_NEUTRAL_SPREAD = 35
_CHROMA_DOMINANCE_THRESH = 20
_CHROMA_FEATHER = 60
_CHROMA_MIN_GREEN = 60
_GREEN_SCREEN_SAMPLE_RATIO = 0.04


def _pixel_greenness(r, g, b):
    """Return 0.0-1.0 green-screen strength; 0 for neutral grays/silver/white."""
    spread = max(abs(r - g), abs(b - g), abs(r - b))
    if g < _CHROMA_MIN_GREEN or spread < _CHROMA_NEUTRAL_SPREAD:
        return 0.0
    dominance = g - max(r, b)
    if dominance <= _CHROMA_DOMINANCE_THRESH:
        return 0.0
    return min(1.0, (dominance - _CHROMA_DOMINANCE_THRESH) / float(_CHROMA_FEATHER))


# Button objectName  ->  MDI command string
BUTTON_MDI = {
    'btnMeasureLength':   "o<laser_length> call",
    'btnMeasureDiameter': "o<laser_diameter> call",
    'btnMeasureRunout':   "o<laser_runout> call",
    'btnBrokenCheck':     "o<laser_broken_check> call",
    'btnCalibrate':       "o<laser_calibrate> call",
    'btnAirBlastToggle':  "o<laser_air_blast_toggle> call",
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
    'lblStartXUnit',
    'lblStartYUnit',
)

SETUP_SYNC_BUTTONS = {
    'btnMeasureLength',
    'btnMeasureDiameter',
    'btnMeasureRunout',
    'btnBrokenCheck',
    'btnCalibrate',
}


class UserTab(QWidget):
    def __init__(self, parent=None):
        super(UserTab, self).__init__(parent)

        here = os.path.dirname(os.path.abspath(__file__))
        uic.loadUi(os.path.join(here, "laser_setter.ui"), self)

        self._ensure_font()

        panel = QColor(46, 52, 54)
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), panel)
        self.setPalette(palette)
        for group_name in ('grpMeasure', 'grpResults', 'grpCalibration', 'headerBar', 'footerBar'):
            widget = getattr(self, group_name, None)
            if widget is not None:
                widget.setAttribute(Qt.WA_StyledBackground, True)

        self._load_stylesheet(here)
        self._tool_setter_pixmap = None
        self._load_tool_setter_image(here)

        try:
            self._cmd = linuxcnc.command()
            self._stat = linuxcnc.stat()
        except Exception as exc:
            LOG.error("laser_setter: linuxcnc init failed: %s", exc)
            self._cmd = None
            self._stat = None

        self._wire_buttons()
        self._wire_help()
        self._wire_start_position()
        self._init_units()
        self._z_touched = False

    def _ensure_font(self):
        """Probe Basic uses BebasKai; Qt family name has no space."""
        if os.path.exists(PB_FONT_PATH):
            QFontDatabase.addApplicationFont(PB_FONT_PATH)
        self.setFont(QFont(PB_FONT))

    def _load_tool_setter_image(self, here):
        image_path = os.path.join(here, "kexin_tool_setter.png")
        lbl = getattr(self, 'lblToolSetterImage', None)
        if lbl is None:
            return
        if not os.path.exists(image_path):
            LOG.warning("laser_setter: image %s missing", image_path)
            return
        lbl.setAutoFillBackground(False)
        lbl.setAlignment(Qt.AlignCenter)
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            LOG.warning("laser_setter: failed to load image %s", image_path)
            return
        self._tool_setter_pixmap = self._maybe_chroma_key_pixmap(pixmap)
        self._update_tool_setter_image()

    def _maybe_chroma_key_pixmap(self, pixmap):
        image = pixmap.toImage().convertToFormat(QImage.Format_RGBA8888)
        if not self._image_has_green_screen(image):
            return pixmap
        LOG.info("laser_setter: applying green-screen chroma key to tool setter image")
        return QPixmap.fromImage(self._chroma_key_image(image))

    def _image_has_green_screen(self, image):
        width = image.width()
        height = image.height()
        if width <= 0 or height <= 0:
            return False
        step = max(4, min(width, height) // 50)
        green_hits = 0
        samples = 0
        for y in range(0, height, step):
            for x in range(0, width, step):
                color = QColor(image.pixel(x, y))
                if _pixel_greenness(color.red(), color.green(), color.blue()) >= 0.5:
                    green_hits += 1
                samples += 1
        return samples > 0 and (green_hits / float(samples)) >= _GREEN_SCREEN_SAMPLE_RATIO

    def _chroma_key_image(self, image):
        keyed = image.convertToFormat(QImage.Format_RGBA8888)
        width = keyed.width()
        height = keyed.height()
        for y in range(height):
            for x in range(width):
                color = QColor(keyed.pixel(x, y))
                r, g, b, a = color.red(), color.green(), color.blue(), color.alpha()
                greenness = _pixel_greenness(r, g, b)
                if greenness <= 0.0:
                    continue
                new_alpha = int(a * (1.0 - greenness))
                if new_alpha == a:
                    continue
                color.setAlpha(max(0, min(255, new_alpha)))
                keyed.setPixel(x, y, color.rgba())
        return keyed

    def _update_tool_setter_image(self):
        lbl = getattr(self, 'lblToolSetterImage', None)
        if lbl is None or self._tool_setter_pixmap is None or self._tool_setter_pixmap.isNull():
            return
        slot = lbl.size()
        target = QSize(
            max(1, int(slot.width() * IMAGE_DISPLAY_SCALE)),
            max(1, int(slot.height() * IMAGE_DISPLAY_SCALE)),
        )
        lbl.setPixmap(self._tool_setter_pixmap.scaled(
            target,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        ))

    def resizeEvent(self, event):
        super(UserTab, self).resizeEvent(event)
        self._update_tool_setter_image()

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

    def _wire_help(self):
        btn = getattr(self, 'btnHelp', None)
        if btn is None:
            return
        btn.clicked.connect(self._show_help_placeholder)

    def _show_help_placeholder(self, checked=False):
        QMessageBox.information(
            self,
            "Laser Tool Setter Help",
            "Help documentation for the laser tool setter is coming soon.",
        )

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
        self._convert_numeric_widget('leStartX', factor)
        self._convert_numeric_widget('leStartY', factor)
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

    def _parse_setup_fields(self):
        try:
            x_pos = float(self.leStartX.text().strip())
            y_pos = float(self.leStartY.text().strip())
            rpm = float(self.leProbeRpm.text().strip())
        except (AttributeError, ValueError):
            return None
        if rpm <= 0:
            return None
        return x_pos, y_pos, rpm

    def _sync_setup_params(self):
        setup = self._parse_setup_fields()
        if setup is None:
            self._set_status("ERROR: invalid start X/Y or probe RPM")
            return False
        if self._cmd is None or self._stat is None:
            self._set_status("ERROR: linuxcnc unavailable")
            return False

        x_pos, y_pos, rpm = setup
        try:
            self._stat.poll()
            if self._stat.estop:
                self._set_status("BLOCKED: E-STOP")
                return False
            if not self._stat.enabled:
                self._set_status("BLOCKED: machine off")
                return False
            self._cmd.mode(linuxcnc.MODE_MDI)
            self._cmd.wait_complete()
            self._cmd.mdi(
                "o<laser_set_start_xy> call [{:.6f}] [{:.6f}] [{:.0f}]".format(
                    x_pos, y_pos, rpm
                )
            )
            LOG.info(
                "laser_setter: setup synced X%.6f Y%.6f RPM%.0f",
                x_pos, y_pos, rpm,
            )
            return True
        except Exception as exc:
            LOG.error("laser_setter: failed to sync setup params: %s", exc)
            self._set_status("ERROR: " + str(exc))
            return False

    def _make_handler(self, mdi_cmd):
        def handler(checked=False):
            btn = self.sender()
            btn_name = btn.objectName() if btn is not None else None
            if btn_name in REQUIRES_Z_FIRST and not self._z_touched:
                self._set_status("BLOCKED: TOUCH Z FIRST")
                LOG.warning("laser_setter: blocked %s until Z touch", btn_name)
                return
            if btn_name in SETUP_SYNC_BUTTONS and not self._sync_setup_params():
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
            if btn_name == 'btnMeasureLength':
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

            self.leStartX.setText("{:.4f}".format(x_pos))
            self.leStartY.setText("{:.4f}".format(y_pos))
            if not self._sync_setup_params():
                return
            self._set_status("START XY SET: X{:.4f} Y{:.4f}".format(x_pos, y_pos))
            LOG.info("laser_setter: start XY captured X%.6f Y%.6f", x_pos, y_pos)
        except Exception as exc:
            LOG.error("laser_setter: failed to capture start XY: %s", exc)
            self._set_status("ERROR: " + str(exc))

    def _set_status(self, text):
        LOG.info("laser_setter: %s", text)
