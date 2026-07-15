"""
Laser Tool Setter — user tab for Probe Basic.

DS-5V-M on Slave 2 DI5 (DB15 pin 11). Live LASER LED mirrors HAL
laser-beam-broken (clear vs tool in beam). MEASURE DIAMETER tip-finds Z,
drops by user Z DROP, then cross-feeds +X for break→clear width.

Measure macros read #<_hal[laser-beam-broken]> directly — they do NOT use
motion.probe-input / G38, so contact probe and toolsetter stay isolated.

Params live in #5501+ (never G30/toolsetter #5181-#5186).
MDI dispatch uses linuxcnc.command() directly (not qtpyvcp.actions).
"""

import os
import subprocess

import linuxcnc

from qtpy import uic
from qtpy.QtCore import Qt, QSize, QTimer
from qtpy.QtGui import QImage, QPixmap, QColor, QPalette, QFont, QFontDatabase
from qtpy.QtWidgets import QWidget, QMessageBox

from qtpyvcp.utilities import logger

LOG = logger.getLogger(__name__)
MM_PER_INCH = 25.4
IMAGE_DISPLAY_SCALE = 0.624  # 20% larger than prior 0.52 setting
PB_FONT = "BebasKai"
PB_FONT_PATH = "/usr/share/fonts/truetype/BebasKai.ttf"
HAL_LASER_BROKEN = "laser-beam-broken"
LED_CLEAR = "#c01c28"      # beam clear (nothing in slot)
LED_BROKEN = "#f5c211"     # tool breaking beam
LED_UNKNOWN = "#4a4f51"

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


def _hal_get_bit(pin: str):
    try:
        out = subprocess.check_output(
            ["halcmd", "getp", pin], stderr=subprocess.STDOUT, text=True
        ).strip().upper()
        if out in ("TRUE", "1"):
            return True
        if out in ("FALSE", "0"):
            return False
    except Exception as exc:
        LOG.debug("laser_setter: hal getp %s failed: %s", pin, exc)
    return None


def _hal_get_float(pin: str):
    try:
        out = subprocess.check_output(
            ["halcmd", "getp", pin], stderr=subprocess.STDOUT, text=True
        ).strip()
        return float(out)
    except Exception as exc:
        LOG.debug("laser_setter: hal getp float %s failed: %s", pin, exc)
    return None


# Button objectName  ->  MDI command string
BUTTON_MDI = {
    'btnMeasureLength':   "o<laser_length> call",
    'btnMeasureDiameter': "o<laser_diameter> call",
    'btnMeasureRunout':   "o<laser_runout> call",
    'btnBrokenCheck':     "o<laser_broken_check> call",
    'btnCalibrate':       None,  # handled in Python (stores BEAM Z)
    'btnAirBlastToggle':  "o<laser_air_blast_toggle> call",
}

# Skeleton actions — still callable but do not imply a real measure succeeded.
SKELETON_BUTTONS = {
    'btnMeasureRunout',
    'btnBrokenCheck',
    'btnAirBlastToggle',
}

REQUIRES_Z_FIRST = {
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
    'lblZDropUnit',
)

SETUP_SYNC_BUTTONS = {
    'btnMeasureLength',
    'btnMeasureDiameter',
    'btnMeasureRunout',
    'btnBrokenCheck',
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

        self._beam_timer = QTimer(self)
        self._beam_timer.setInterval(200)
        self._beam_timer.timeout.connect(self._poll_beam_led)
        self._beam_timer.start()
        self._poll_beam_led()
        self._set_status("Ready")

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
            if obj_name == 'btnCalibrate':
                btn.clicked.connect(self._calibrate_beam_z)
            else:
                btn.clicked.connect(self._make_handler(mdi_cmd))
            if obj_name in SKELETON_BUTTONS and btn is not None:
                btn.setToolTip("Skeleton — not implemented yet")

    def _poll_beam_led(self):
        """UI LED mirrors HAL laser-beam-broken (clear vs tool in beam)."""
        led = getattr(self, 'ledLaserHealthy', None)
        if led is None:
            return
        broken = _hal_get_bit(HAL_LASER_BROKEN)
        if broken is None:
            color = LED_UNKNOWN
            tip = "Laser HAL pin unread — is LinuxCNC running?"
        elif broken:
            color = LED_BROKEN
            tip = "Beam BROKEN (tool in laser)"
        else:
            color = LED_CLEAR
            tip = "Beam CLEAR (nothing in laser)"
        led.setStyleSheet(
            "background-color: %s; border-radius: 9px; border: 1px solid #2e3436;"
            % color
        )
        led.setToolTip(tip)

    def _ui_to_mm(self, value):
        """Convert a displayed linear value to machine mm."""
        if getattr(self, '_display_units', 'mm') == 'in':
            return value * MM_PER_INCH
        return value

    def _mm_to_ui(self, value_mm):
        """Convert machine mm to the current display unit."""
        if getattr(self, '_display_units', 'mm') == 'in':
            return value_mm / MM_PER_INCH
        return value_mm

    def _calibrate_beam_z(self, checked=False):
        """Store current machine Z as BEAM Z while tip is breaking the beam."""
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

            broken = _hal_get_bit(HAL_LASER_BROKEN)
            if broken is not True:
                if broken is None:
                    self._set_status("BLOCKED: cannot read laser-beam-broken")
                else:
                    self._set_status("BLOCKED: jog tip into beam first (wait for beam broken)")
                return

            # actual_position is machine coords (G53)
            z_mach = float(self._stat.actual_position[2])
            self.lblBeamZ.setText("{:.4f}".format(self._mm_to_ui(z_mach)))

            self._cmd.mode(linuxcnc.MODE_MDI)
            self._cmd.wait_complete()
            self._cmd.mdi(
                "o<laser_set_beam_z> call [{:.6f}] [10] [30]".format(z_mach)
            )
            self._cmd.wait_complete()
            self._z_touched = True
            self._set_status(
                "BEAM Z SET: {:.4f} (tip in beam — ready for MEASURE LENGTH)".format(
                    self._mm_to_ui(z_mach)
                )
            )
            LOG.info("laser_setter: calibrated BEAM Z G53=%.6f", z_mach)
        except Exception as exc:
            LOG.error("laser_setter: calibrate failed: %s", exc)
            self._set_status("ERROR: " + str(exc))

    def _wire_help(self):
        btn = getattr(self, 'btnHelp', None)
        if btn is None:
            return
        btn.clicked.connect(self._show_help_placeholder)

    def _show_help_placeholder(self, checked=False):
        QMessageBox.information(
            self,
            "Laser Tool Setter Help",
            "1. Hardwire DS-5V-M Select to GND; 5 V power; signal → Slave 2 DI5 "
            "(DB15 pin 11) via level shift.\n"
            "2. LASER LED follows HAL laser-beam-broken (clear vs tool in beam).\n"
            "3. CAPTURE START X/Y over the slot center; set Z DROP (default 2 mm).\n"
            "4. Jog to a safe Z above the beam → MEASURE DIAMETER:\n"
            "   tip-find → side start → drop Z → cross +X (break→clear) → diameter.\n"
            "5. Optional: CALIBRATE / MEASURE LENGTH for length experiments.\n"
            "Laser measure does NOT use motion.probe-input (contact path stays clean).\n"
            "Runout / broken-check still skeleton.",
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
        self._set_status("UNITS: " + new_units.upper() + " (params still synced as mm)")

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
        self._convert_numeric_widget('leZDrop', factor)
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

    def _parse_setup_fields_mm(self):
        try:
            x_pos = self._ui_to_mm(float(self.leStartX.text().strip()))
            y_pos = self._ui_to_mm(float(self.leStartY.text().strip()))
            rpm = float(self.leProbeRpm.text().strip())
        except (AttributeError, ValueError):
            return None
        if rpm < 0:
            return None
        return x_pos, y_pos, rpm

    def _parse_z_drop_mm(self):
        try:
            z_drop = self._ui_to_mm(float(self.leZDrop.text().strip()))
        except (AttributeError, ValueError):
            return None
        if z_drop <= 0:
            return None
        return z_drop

    def _sync_setup_params(self):
        setup = self._parse_setup_fields_mm()
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
            self._cmd.wait_complete()
            LOG.info(
                "laser_setter: setup synced X%.6f Y%.6f RPM%.0f (mm)",
                x_pos, y_pos, rpm,
            )
            return True
        except Exception as exc:
            LOG.error("laser_setter: failed to sync setup params: %s", exc)
            self._set_status("ERROR: " + str(exc))
            return False

    def _sync_diam_params(self) -> bool:
        """Push Z DROP (+ default search) into #5507/#5508 before diameter."""
        z_drop = self._parse_z_drop_mm()
        if z_drop is None:
            self._set_status("ERROR: invalid Z DROP (must be > 0)")
            return False
        if self._cmd is None:
            return False
        # Half-travel from START XY; must exceed expected tool radius.
        search = 10.0
        try:
            self._cmd.mode(linuxcnc.MODE_MDI)
            self._cmd.wait_complete()
            self._cmd.mdi(
                "o<laser_set_diam_params> call [{:.6f}] [{:.6f}]".format(
                    z_drop, search
                )
            )
            self._cmd.wait_complete()
            return True
        except Exception as exc:
            self._set_status("ERROR: " + str(exc))
            return False

    def _make_handler(self, mdi_cmd):
        def handler(checked=False):
            btn = self.sender()
            btn_name = btn.objectName() if btn is not None else None
            if btn_name in REQUIRES_Z_FIRST and not self._z_touched:
                self._set_status("BLOCKED: tip-find / CALIBRATE first")
                LOG.warning("laser_setter: blocked %s until Z touch", btn_name)
                return
            if btn_name in SETUP_SYNC_BUTTONS and not self._sync_setup_params():
                return
            if btn_name == 'btnMeasureLength' and not self._sync_beam_z_param():
                return
            if btn_name == 'btnMeasureDiameter' and not self._sync_diam_params():
                return
            self._issue_mdi(mdi_cmd, btn_name)
        return handler

    def _sync_beam_z_param(self) -> bool:
        """Push Beam Z label into #5504 before length probe (always mm)."""
        try:
            beam_z = self._ui_to_mm(float(self.lblBeamZ.text().strip()))
        except (AttributeError, ValueError):
            self._set_status("ERROR: set BEAM Z via CALIBRATE first")
            return False
        if abs(beam_z) < 1e-9:
            self._set_status("ERROR: BEAM Z is 0 — CALIBRATE with tip in beam")
            return False
        if self._cmd is None:
            return False
        try:
            self._cmd.mode(linuxcnc.MODE_MDI)
            self._cmd.wait_complete()
            self._cmd.mdi(
                "o<laser_set_beam_z> call [{:.6f}] [10] [30]".format(beam_z)
            )
            self._cmd.wait_complete()
            return True
        except Exception as exc:
            self._set_status("ERROR: " + str(exc))
            return False

    def _read_aout(self, index):
        """Read motion analog out published by M68."""
        try:
            self._stat.poll()
            if hasattr(self._stat, "aout") and len(self._stat.aout) > index:
                return float(self._stat.aout[index])
        except Exception:
            pass
        pin = "motion.analog-out-{:02d}".format(index)
        return _hal_get_float(pin)

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
            self._cmd.wait_complete(120.0)

            if btn_name == 'btnMeasureLength':
                self._refresh_length_result()
            elif btn_name == 'btnMeasureDiameter':
                self._refresh_diameter_result()
            elif btn_name in SKELETON_BUTTONS:
                self._set_status("SKELETON: " + mdi_cmd + " (no measure logic yet)")
            else:
                self._set_status("DONE: " + mdi_cmd)
            LOG.info("laser_setter: %s", mdi_cmd)
        except Exception as exc:
            LOG.error("laser_setter: MDI failed (%s): %s", mdi_cmd, exc)
            self._set_status("ERROR: " + str(exc))

    def _measure_succeeded(self) -> bool:
        success = self._read_aout(1)
        return success is not None and success >= 0.5

    def _refresh_length_result(self):
        """Pull length published by laser_length via M68 E0; gate on E1 success."""
        try:
            if not self._measure_succeeded():
                self._set_status("LENGTH FAILED (see DEBUG / retract to approach)")
                return
            length_mm = self._read_aout(0)
            if length_mm is None:
                self._set_status("LENGTH: success flag set but no result on aout[0]")
                return
            self._z_touched = True
            self.lblResLength.setText("{:.4f}".format(self._mm_to_ui(length_mm)))
            self._set_status(
                "LENGTH {:.4f} (beam_z - tip_z)".format(self._mm_to_ui(length_mm))
            )
        except Exception as exc:
            LOG.debug("laser_setter: length result refresh skipped: %s", exc)
            self._set_status("LENGTH: done (result refresh failed)")

    def _refresh_diameter_result(self):
        """Read diameter published by laser_diameter via M68 E0; gate on E1."""
        try:
            if not self._measure_succeeded():
                self._set_status(
                    "DIAMETER FAILED (miss, blocked, oversize, or crash-risk abort)"
                )
                return
            diameter_mm = self._read_aout(0)
            if diameter_mm is None or diameter_mm <= 0:
                self._set_status("DIAMETER: success flag set but no result on aout[0]")
                return
            self._z_touched = True
            self.lblResDiam.setText("{:.4f}".format(self._mm_to_ui(diameter_mm)))
            self._set_status(
                "DIAMETER {:.4f} (raw break→clear)".format(self._mm_to_ui(diameter_mm))
            )
        except Exception as exc:
            LOG.debug("laser_setter: diameter result refresh skipped: %s", exc)
            self._set_status("DIAMETER: done (result refresh failed)")

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

            # Machine coords (G53) — macros move with G53
            x_mm = float(self._stat.actual_position[0])
            y_mm = float(self._stat.actual_position[1])

            self.leStartX.setText("{:.4f}".format(self._mm_to_ui(x_mm)))
            self.leStartY.setText("{:.4f}".format(self._mm_to_ui(y_mm)))
            if not self._sync_setup_params():
                return
            self._set_status(
                "START XY SET: X{:.4f} Y{:.4f}".format(
                    self._mm_to_ui(x_mm), self._mm_to_ui(y_mm)
                )
            )
            LOG.info("laser_setter: start XY captured X%.6f Y%.6f (G53 mm)", x_mm, y_mm)
        except Exception as exc:
            LOG.error("laser_setter: failed to capture start XY: %s", exc)
            self._set_status("ERROR: " + str(exc))

    def _set_status(self, text):
        LOG.info("laser_setter: %s", text)
        lbl = getattr(self, 'lblStatus', None)
        if lbl is not None:
            lbl.setText(text)
            lbl.setToolTip(text)
