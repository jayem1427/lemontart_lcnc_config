"""
Laser Tool Setter — user tab for Probe Basic.

DS-5V-M on Slave 2 DI5 (DB15 pin 11). Live LASER LED mirrors HAL signal
laser-beam-broken (clear vs tool in beam). CAPTURE stores BEAM X/Y while
the tool blocks the light. START OFFSET (+X, default 15 mm) is the clear
approach point away from the toolsetter. MEASURE DIAMETER tip-finds Z at
BEAM XY, then sweeps −X from START through the beam up to MAX TRAVEL.

Measure macros use M62 P0 to route the laser onto motion.probe-input for
continuous G38 moves; M63 P0 restores the contact probe mux. M66 P3 on
motion.digital-in-03 is still used for beam-at-START safety checks.
(#<_hal[laser-beam-broken]> is frozen at program start; do not use it in loops.)

Params live in #5501+ (never G30/toolsetter #5181-#5186).
#5516 = measured beam width offset (master pin − last raw diameter).
MDI dispatch uses linuxcnc.command() directly (not qtpyvcp.actions).
"""

import os
import subprocess
import time

import linuxcnc

from qtpy import uic
from qtpy.QtCore import Qt, QSize, QTimer
from qtpy.QtGui import QImage, QPixmap, QColor, QPalette, QFont, QFontDatabase
from qtpy.QtWidgets import QWidget, QMessageBox, QApplication

from qtpyvcp.utilities import logger

LOG = logger.getLogger(__name__)
MM_PER_INCH = 25.4
IMAGE_DISPLAY_SCALE = 0.92  # fill the tighter image slot after layout densify
PB_FONT = "BebasKai"
PB_FONT_PATH = "/usr/share/fonts/truetype/BebasKai.ttf"
HAL_LASER_BROKEN = "laser-beam-broken"
HAL_LASER_DIO = "motion.digital-in-03"  # live M66 source; also usable for capture gate
LED_CLEAR = "#c01c28"      # beam clear (nothing in slot)
LED_BROKEN = "#f5c211"     # tool breaking beam
LED_UNKNOWN = "#4a4f51"
# Persistent laser params in linuxcnc.var (must exist there or they are lost on exit)
LASER_VAR_PARAMS = (
    5501, 5502, 5503, 5504, 5505, 5506, 5507, 5508, 5509,
    5510, 5511, 5512, 5513, 5514, 5515, 5516, 5517, 5519,
)

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


def _hal_get_bit(name: str):
    """Read a HAL bit pin (`getp`) or signal (`gets`)."""
    for cmd in ("getp", "gets"):
        try:
            out = subprocess.check_output(
                ["halcmd", cmd, name], stderr=subprocess.STDOUT, text=True
            ).strip().upper()
            if out in ("TRUE", "1"):
                return True
            if out in ("FALSE", "0"):
                return False
        except Exception as exc:
            LOG.debug("laser_setter: hal %s %s failed: %s", cmd, name, exc)
    return None


def _hal_get_float(pin: str):
    """Read a HAL float pin (`getp`) or signal (`gets`)."""
    for cmd in ("getp", "gets"):
        try:
            out = subprocess.check_output(
                ["halcmd", cmd, pin], stderr=subprocess.STDOUT, text=True
            ).strip()
            return float(out)
        except Exception as exc:
            LOG.debug("laser_setter: hal %s float %s failed: %s", cmd, pin, exc)
    return None

# Button objectName  ->  MDI command string
BUTTON_MDI = {
    'btnMeasureLength':   "o<laser_length> call",
    'btnMeasureDiameter': "o<laser_diameter> call",
    'btnCalibrate':       None,  # handled in Python (beam width from master pin)
}

LINEAR_VALUE_WIDGETS = (
    'lblResLength',
    'lblResDiam',
    'leBeamWidth',
)

LINEAR_UNIT_WIDGETS = (
    'lblResLengthUnit',
    'lblResDiamUnit',
    'lblBeamDiaUnit',
    'lblMasterPinUnit',
    'lblStartXUnit',
    'lblStartYUnit',
    'lblZDropUnit',
    'lblBeamOffsetUnit',
    'lblMaxTravelUnit',
)

SETUP_SYNC_BUTTONS = {
    'btnMeasureLength',
    'btnMeasureDiameter',
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
        self._wire_beam_width_edit()
        self._init_units()
        self._last_raw_diam_mm = None
        self._beam_width_mm = 0.0
        self._load_saved_laser_params()

        self._beam_timer = QTimer(self)
        self._beam_timer.setInterval(200)
        self._beam_timer.timeout.connect(self._poll_beam_led)
        self._beam_timer.start()
        self._poll_beam_led()
        self._set_status("Ready")

    def _var_file_path(self):
        """Config-dir linuxcnc.var (PARAMETER_FILE)."""
        here = os.path.dirname(os.path.abspath(__file__))
        return os.path.abspath(os.path.join(here, "..", "..", "..", "linuxcnc.var"))

    def _read_var_file(self):
        """Return {param_number: float} from linuxcnc.var."""
        path = self._var_file_path()
        values = {}
        try:
            with open(path, "r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line or line.startswith(";"):
                        continue
                    parts = line.split()
                    if len(parts) < 2:
                        continue
                    try:
                        values[int(parts[0])] = float(parts[1])
                    except ValueError:
                        continue
        except OSError as exc:
            LOG.warning("laser_setter: cannot read %s: %s", path, exc)
        return values

    def _write_var_params(self, updates):
        """Merge param updates into linuxcnc.var (numbers must stay ascending)."""
        path = self._var_file_path()
        values = self._read_var_file()
        values.update(updates)
        for num in LASER_VAR_PARAMS:
            values.setdefault(num, 0.0)
        try:
            # Preserve leading comment lines; rewrite all params sorted.
            # Appending new keys at EOF breaks LinuxCNC ("Parameter file out of order").
            comments = []
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    for line in handle:
                        stripped = line.strip()
                        if stripped.startswith(";"):
                            comments.append(
                                line if line.endswith("\n") else line + "\n"
                            )
            except OSError:
                pass

            out_lines = list(comments)
            for num in sorted(values):
                out_lines.append("{}\t{:.6f}\n".format(num, values[num]))
            with open(path, "w", encoding="utf-8") as handle:
                handle.writelines(out_lines)
            LOG.info("laser_setter: wrote params %s to %s", sorted(updates), path)
            return True
        except OSError as exc:
            LOG.error("laser_setter: failed writing %s: %s", path, exc)
            return False

    def _load_saved_laser_params(self):
        """Populate BEAM X/Y, measure fields, and beam-width cal from linuxcnc.var."""
        values = self._read_var_file()
        x_mm = values.get(5501, 0.0)
        y_mm = values.get(5502, 0.0)
        rpm = values.get(5503, 0.0)
        z_drop = values.get(5507, 2.0)
        max_travel = values.get(5508, 30.0)
        start_offset = values.get(5509, 15.0)
        raw_diam = values.get(5512, 0.0)
        beam_width = values.get(5516, 0.0)
        master_pin = values.get(5517, 0.0)

        if abs(x_mm) > 1e-6 or abs(y_mm) > 1e-6:
            self._set_beam_xy_widgets(x_mm, y_mm)
        le_rpm = getattr(self, "leProbeRpm", None)
        if le_rpm is not None and rpm >= 0:
            le_rpm.setText("{:.0f}".format(rpm))
        for name, val in (
            ("leZDrop", z_drop),
            ("leMaxTravel", max_travel),
            ("leBeamOffset", start_offset),
        ):
            widget = getattr(self, name, None)
            if widget is not None and val > 0:
                widget.setText("{:.4f}".format(self._mm_to_ui(val)))
        if master_pin > 0:
            le_master = getattr(self, "leMasterPin", None)
            if le_master is not None:
                le_master.setText("{:.4f}".format(self._mm_to_ui(master_pin)))
        if raw_diam > 0:
            self._last_raw_diam_mm = raw_diam
        self._beam_width_mm = float(beam_width)
        le_bw = getattr(self, "leBeamWidth", None)
        if le_bw is not None:
            le_bw.setText("{:.4f}".format(self._mm_to_ui(self._beam_width_mm)))

    def _set_beam_xy_widgets(self, x_mm, y_mm):
        x_txt = "{:.4f}".format(self._mm_to_ui(x_mm))
        y_txt = "{:.4f}".format(self._mm_to_ui(y_mm))
        for name, txt in (("leStartX", x_txt), ("leStartY", y_txt)):
            widget = getattr(self, name, None)
            if widget is not None:
                widget.setText(txt)

    def _beam_is_broken(self):
        """True if tool is blocking beam (signal or digital-in-03)."""
        broken = _hal_get_bit(HAL_LASER_BROKEN)
        if broken is True:
            return True
        dio = _hal_get_bit(HAL_LASER_DIO)
        return dio is True

    def _mdi_set_numbered_params(self, assignments):
        """Write #N=value via MDI (reliable; does not use oword call args)."""
        if self._cmd is None or self._stat is None:
            self._set_status("ERROR: linuxcnc unavailable")
            return False
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
            # One statement per param keeps the interpreter happy
            for num, value in assignments:
                self._cmd.mdi("#{0}={1:.6f}".format(num, float(value)))
                self._cmd.wait_complete()
            return True
        except Exception as exc:
            LOG.error("laser_setter: MDI param write failed: %s", exc)
            self._set_status("ERROR: " + str(exc))
            return False

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
                btn.clicked.connect(self._calibrate_beam_width)
            else:
                btn.clicked.connect(self._make_handler(mdi_cmd))

    def _poll_beam_led(self):
        """UI LED mirrors HAL laser-beam-broken (clear vs tool in beam)."""
        led = getattr(self, 'ledLaserHealthy', None)
        if led is None:
            return
        broken = _hal_get_bit(HAL_LASER_BROKEN)
        if broken is None:
            color = LED_UNKNOWN
            tip = (
                "Cannot read HAL signal laser-beam-broken "
                "(try: halcmd gets laser-beam-broken)"
            )
        elif broken:
            color = LED_BROKEN
            tip = "laser-beam-broken = TRUE (tool blocking beam)"
        else:
            color = LED_CLEAR
            tip = "laser-beam-broken = FALSE (beam clear)"
        led.setStyleSheet(
            "background-color: %s; border-radius: 9px; border: 1px solid #2e3436;"
            % color
        )
        led.setToolTip(tip)
        led.setProperty("beamBroken", broken)
        led.style().unpolish(led)
        led.style().polish(led)

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

    def _parse_master_pin_mm(self):
        try:
            master = self._ui_to_mm(float(self.leMasterPin.text().strip()))
        except (AttributeError, ValueError):
            return None
        if master <= 0:
            return None
        return master

    def _calibrate_beam_width(self, checked=False):
        """MEASURED BEAM WIDTH = MASTER PIN − last raw diameter; used on later measures."""
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

            master_mm = self._parse_master_pin_mm()
            if master_mm is None:
                self._set_status("ERROR: enter MASTER PIN diameter (> 0)")
                return

            raw_mm = self._last_raw_diam_mm
            if raw_mm is None or raw_mm <= 0:
                values = self._read_var_file()
                raw_mm = values.get(5512, 0.0)
            if raw_mm is None or raw_mm <= 0:
                self._set_status(
                    "ERROR: MEASURE DIAMETER on the master pin first (need a raw reading)"
                )
                return

            # Offset applied as: corrected = raw + beam_width
            # With beam_width = master − raw_master → master pin reads back as master.
            beam_width = master_mm - float(raw_mm)
            self._beam_width_mm = beam_width
            self._last_raw_diam_mm = float(raw_mm)
            self.leBeamWidth.setText("{:.4f}".format(self._mm_to_ui(beam_width)))

            if not self._persist_beam_width(beam_width, master_mm=master_mm):
                return

            corrected = float(raw_mm) + beam_width
            self.lblResDiam.setText("{:.4f}".format(self._mm_to_ui(corrected)))
            self._set_status(
                "BEAM WIDTH {:.4f} (= master {:.4f} − raw {:.4f}) — applied to diameter".format(
                    self._mm_to_ui(beam_width),
                    self._mm_to_ui(master_mm),
                    self._mm_to_ui(raw_mm),
                )
            )
            LOG.info(
                "laser_setter: beam width=%.6f (master=%.6f raw=%.6f)",
                beam_width, master_mm, raw_mm,
            )
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
            "2. LASER LED follows HAL signal laser-beam-broken "
            "(halcmd gets laser-beam-broken).\n"
            "3. Jog until the tool blocks the beam (LED = broken) → "
            "CAPTURE BEAM.\n"
            "4. Set START OFFSET (+X from BEAM to clear START, default 15), "
            "MAX TRAVEL (−X from START through beam), Z DROP.\n"
            "5. PROBE RPM: 0 = static; >0 = M3 reverse on diameter pass "
            "(custom.hal swaps M3/M4 to the VFD).\n"
            "6. MEASURE DIAMETER (M62 P0 enables laser on probe-input for G38):\n"
            "   Z0 → G38 tip-find at BEAM XY → retract 5 mm → START (BEAM+offset) → "
            "tip−ZDROP → G38 pre-touch −X → X+2 mm → M3 → break→clear "
            "(stop at START−max travel) → M63 P0.\n"
            "7. Beam-width cal: enter MASTER PIN size → MEASURE DIAMETER on that pin → "
            "CALIBRATE BEAM. MEASURED BEAM WIDTH = master − raw; later diameters add "
            "that offset. You can also type a value into MEASURED BEAM WIDTH by hand "
            "for fine tuning (#5516).\n"
            "8. Optional: MEASURE LENGTH (uses #5504 BEAM Z if already taught).\n"
            "While measuring, M62 P0 routes laser-beam-broken to motion.probe-input; "
            "M63 P0 restores contact probe / toolsetter mux.",
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
        self._convert_numeric_widget('leBeamWidth', factor)
        self._convert_numeric_widget('leStartX', factor)
        self._convert_numeric_widget('leStartY', factor)
        self._convert_numeric_widget('leZDrop', factor)
        self._convert_numeric_widget('leBeamOffset', factor)
        self._convert_numeric_widget('leMaxTravel', factor)
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

    def _parse_beam_offset_mm(self):
        try:
            offset = self._ui_to_mm(float(self.leBeamOffset.text().strip()))
        except (AttributeError, ValueError):
            return None
        if offset <= 0:
            return None
        return offset

    def _parse_max_travel_mm(self):
        try:
            travel = self._ui_to_mm(float(self.leMaxTravel.text().strip()))
        except (AttributeError, ValueError):
            return None
        if travel <= 0:
            return None
        return travel

    def _sync_setup_params(self):
        setup = self._parse_setup_fields_mm()
        if setup is None:
            self._set_status("ERROR: invalid BEAM X/Y or probe RPM")
            return False
        x_pos, y_pos, rpm = setup
        if abs(x_pos) < 1e-6 and abs(y_pos) < 1e-6:
            self._set_status("ERROR: BEAM X/Y is 0,0 — press CAPTURE BEAM first")
            return False
        if not self._mdi_set_numbered_params(
            ((5501, x_pos), (5502, y_pos), (5503, rpm))
        ):
            return False
        self._write_var_params({5501: x_pos, 5502: y_pos, 5503: rpm})
        LOG.info(
            "laser_setter: setup synced X%.6f Y%.6f RPM%.0f (mm)",
            x_pos, y_pos, rpm,
        )
        return True

    def _sync_diam_params(self) -> bool:
        """Push Z DROP, MAX TRAVEL, START OFFSET into #5507-#5509."""
        z_drop = self._parse_z_drop_mm()
        if z_drop is None:
            self._set_status("ERROR: invalid Z DROP (must be > 0)")
            return False
        max_travel = self._parse_max_travel_mm()
        if max_travel is None:
            self._set_status("ERROR: invalid MAX TRAVEL (must be > 0)")
            return False
        beam_offset = self._parse_beam_offset_mm()
        if beam_offset is None:
            self._set_status("ERROR: invalid START OFFSET (must be > 0)")
            return False
        if beam_offset >= max_travel:
            self._set_status("ERROR: START OFFSET must be < MAX TRAVEL")
            return False
        if not self._mdi_set_numbered_params(
            ((5507, z_drop), (5508, max_travel), (5509, beam_offset))
        ):
            return False
        self._write_var_params(
            {5507: z_drop, 5508: max_travel, 5509: beam_offset}
        )
        return True

    def _make_handler(self, mdi_cmd):
        def handler(checked=False):
            btn = self.sender()
            btn_name = btn.objectName() if btn is not None else None
            if btn_name in SETUP_SYNC_BUTTONS and not self._sync_setup_params():
                return
            if btn_name == 'btnMeasureLength' and not self._sync_beam_z_param():
                return
            if btn_name == 'btnMeasureDiameter' and not self._sync_diam_params():
                return
            if btn_name == 'btnMeasureDiameter' and not self._sync_beam_width_param():
                return
            self._issue_mdi(mdi_cmd, btn_name)
        return handler

    def _parse_beam_width_mm(self):
        """Read MEASURED BEAM WIDTH from the editable field (may be negative)."""
        try:
            return self._ui_to_mm(float(self.leBeamWidth.text().strip()))
        except (AttributeError, ValueError):
            return None

    def _persist_beam_width(self, beam_width_mm, master_mm=None) -> bool:
        """Write #5516 (and optional master pin) to interpreter + linuxcnc.var."""
        assignments = [(5516, float(beam_width_mm))]
        updates = {5516: float(beam_width_mm)}
        if master_mm is not None:
            assignments.append((5517, float(master_mm)))
            updates[5517] = float(master_mm)
        if not self._mdi_set_numbered_params(assignments):
            return False
        if not self._write_var_params(updates):
            self._set_status(
                "BEAM WIDTH in interpreter but var file write failed — "
                "will be lost on restart"
            )
            return False
        self._beam_width_mm = float(beam_width_mm)
        return True

    def _wire_beam_width_edit(self):
        le = getattr(self, "leBeamWidth", None)
        if le is None:
            return
        le.editingFinished.connect(self._on_beam_width_edited)

    def _on_beam_width_edited(self):
        """Persist manual fine-tune of MEASURED BEAM WIDTH."""
        beam_width = self._parse_beam_width_mm()
        if beam_width is None:
            self._set_status("ERROR: invalid MEASURED BEAM WIDTH")
            self.leBeamWidth.setText("{:.4f}".format(self._mm_to_ui(self._beam_width_mm)))
            return
        if abs(beam_width - self._beam_width_mm) < 1e-9:
            return
        if not self._persist_beam_width(beam_width):
            return
        self._set_status(
            "BEAM WIDTH SET: {:.4f} (manual — applied to next diameter)".format(
                self._mm_to_ui(beam_width)
            )
        )
        LOG.info("laser_setter: manual beam width=%.6f mm", beam_width)

    def _sync_beam_width_param(self) -> bool:
        """Push MEASURED BEAM WIDTH (#5516) from the field before diameter measure."""
        beam_width = self._parse_beam_width_mm()
        if beam_width is None:
            self._set_status("ERROR: invalid MEASURED BEAM WIDTH")
            return False
        return self._persist_beam_width(beam_width)

    def _sync_beam_z_param(self) -> bool:
        """Ensure #5504 BEAM Z is loaded before length probe (from linuxcnc.var)."""
        values = self._read_var_file()
        beam_z = values.get(5504, 0.0)
        approach = values.get(5505, 10.0) or 10.0
        max_travel = values.get(5506, 30.0) or 30.0
        if abs(beam_z) < 1e-9:
            self._set_status(
                "ERROR: BEAM Z (#5504) is 0 — teach via MDI #5504=<G53 Z> first"
            )
            return False
        if not self._mdi_set_numbered_params(
            ((5504, beam_z), (5505, approach), (5506, max_travel))
        ):
            return False
        return True

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

    def _wait_complete_pump(self, timeout_s=120.0):
        """Wait for MDI without freezing Qt — keeps LASER LED polling alive."""
        deadline = time.monotonic() + float(timeout_s)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("MDI wait timed out after {:.0f}s".format(timeout_s))
            # Short chunks so QTimer can refresh the beam LED mid-measure
            rc = self._cmd.wait_complete(min(0.1, remaining))
            QApplication.processEvents()
            if rc != -1:
                return rc

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
            self._wait_complete_pump(10.0)
            self._cmd.mdi(mdi_cmd)
            self._set_status("MEASURING…")
            self._wait_complete_pump(120.0)

            if btn_name == 'btnMeasureLength':
                self._refresh_length_result()
            elif btn_name == 'btnMeasureDiameter':
                self._refresh_diameter_result()
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
            self.lblResLength.setText("{:.4f}".format(self._mm_to_ui(length_mm)))
            self._set_status(
                "LENGTH {:.4f} (beam_z - tip_z)".format(self._mm_to_ui(length_mm))
            )
        except Exception as exc:
            LOG.debug("laser_setter: length result refresh skipped: %s", exc)
            self._set_status("LENGTH: done (result refresh failed)")

    def _refresh_diameter_result(self):
        """Read corrected diameter from M68 E0; keep last raw for CALIBRATE BEAM."""
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
            # #5512 is always raw shadow width; M68 E0 is corrected (raw + #5516)
            if abs(self._beam_width_mm) > 1e-12:
                raw_mm = diameter_mm - self._beam_width_mm
            else:
                raw_mm = diameter_mm
            if raw_mm > 0:
                self._last_raw_diam_mm = float(raw_mm)
                self._write_var_params({5512: float(raw_mm)})
            self.lblResDiam.setText("{:.4f}".format(self._mm_to_ui(diameter_mm)))
            if abs(self._beam_width_mm) > 1e-12:
                self._set_status(
                    "DIAMETER {:.4f} (raw {:.4f} + beam width {:.4f})".format(
                        self._mm_to_ui(diameter_mm),
                        self._mm_to_ui(self._last_raw_diam_mm or 0.0),
                        self._mm_to_ui(self._beam_width_mm),
                    )
                )
            else:
                self._set_status(
                    "DIAMETER {:.4f} (raw — CALIBRATE BEAM to apply master-pin offset)".format(
                        self._mm_to_ui(diameter_mm)
                    )
                )
        except Exception as exc:
            LOG.debug("laser_setter: diameter result refresh skipped: %s", exc)
            self._set_status("DIAMETER: done (result refresh failed)")

    def _capture_start_xy(self, checked=False):
        """Capture BEAM X/Y (G53) and persist to #5501/#5502 + linuxcnc.var."""
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

            beam_ok = self._beam_is_broken()
            # Machine coords (G53) — macros move with G53
            x_mm = float(self._stat.actual_position[0])
            y_mm = float(self._stat.actual_position[1])
            if abs(x_mm) < 1e-6 and abs(y_mm) < 1e-6:
                self._set_status(
                    "ERROR: machine XY is 0,0 — home / jog to beam first"
                )
                return

            try:
                rpm = float(self.leProbeRpm.text().strip())
            except (AttributeError, ValueError):
                rpm = 0.0
            if rpm < 0:
                rpm = 0.0

            self._set_beam_xy_widgets(x_mm, y_mm)

            if not self._mdi_set_numbered_params(
                ((5501, x_mm), (5502, y_mm), (5503, rpm))
            ):
                return
            if not self._write_var_params({5501: x_mm, 5502: y_mm, 5503: rpm}):
                self._set_status(
                    "BEAM XY in interpreter but var file write failed — "
                    "will be lost on restart"
                )
                return

            if beam_ok:
                self._set_status(
                    "BEAM XY SAVED: X{:.4f} Y{:.4f} (START = BEAM + START OFFSET +X)".format(
                        self._mm_to_ui(x_mm), self._mm_to_ui(y_mm)
                    )
                )
            else:
                self._set_status(
                    "BEAM XY SAVED: X{:.4f} Y{:.4f} (WARNING: beam not broken — "
                    "re-capture with tool in beam if this was wrong)".format(
                        self._mm_to_ui(x_mm), self._mm_to_ui(y_mm)
                    )
                )
            LOG.info("laser_setter: BEAM XY captured X%.6f Y%.6f (G53 mm)", x_mm, y_mm)
        except Exception as exc:
            LOG.error("laser_setter: failed to capture BEAM XY: %s", exc)
            self._set_status("ERROR: " + str(exc))

    def _set_status(self, text):
        LOG.info("laser_setter: %s", text)
        lbl = getattr(self, 'lblStatus', None)
        if lbl is not None:
            lbl.setText(text)
            lbl.setToolTip(text)
