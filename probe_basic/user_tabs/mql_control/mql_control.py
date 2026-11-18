"""
MQL — Microject PWM coolant tab for Probe Basic.

Sliders set M201 P<Hz> Q<duty %>. coolant.hal turns analog E4/E5 into
period_ms = 1000 / Hz and pulse_ms = period_ms * duty / 100 on the Modbus
holding registers; M8/M9 switch the injector coil. See docs/COOLANT.md.

Named presets live in probe_basic/mql_presets.json. SAVE TO TOOL writes
[T<n>] in [COOLANT]PROFILE_FILE, which M202 re-reads on every call.
MDI dispatch uses linuxcnc.command() directly (same as Laser Setter).
"""

import json
import os
import sys

import linuxcnc

from qtpy import uic
from qtpy.QtCore import Qt, QRectF, QTimer, Signal
from qtpy.QtGui import QColor, QFont, QFontDatabase, QPainter, QPainterPath, QPen
from qtpy.QtWidgets import (
    QAbstractSpinBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from qtpyvcp.utilities import logger

LOG = logger.getLogger(__name__)

PB_FONT = "BebasKai"
PB_FONT_PATH = "/usr/share/fonts/truetype/BebasKai.ttf"

CONFIG_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir, os.pardir)
)
PYTHON_DIR = os.path.join(CONFIG_DIR, "probe_basic", "python")
if PYTHON_DIR not in sys.path:
    sys.path.insert(0, PYTHON_DIR)

from coolant_profiles import load_profiles, recipe_for_tool, save_tool_recipe  # noqa: E402

PRESETS_PATH = os.path.join(CONFIG_DIR, "probe_basic", "mql_presets.json")
DEFAULT_PROFILE_FILE = "probe_basic/coolant_tools.ini"

# limit1.4 in coolant.hal clamps E4 to this range.
FREQ_MIN = 1.0
FREQ_MAX = 50.0
FREQ_STEP = 0.5
DUTY_MIN = 0.0
DUTY_MAX = 100.0
DUTY_STEP = 0.1
# Squared slider mapping puts most of the travel in the useful 0-25 % band.
DUTY_CURVE = 2.0
SHORT_PULSE_MS = 1.0
PREVIEW_WINDOW_MS = 500.0
SLIDER_STEPS = 1000
POLL_MS = 250
LIVE_DEBOUNCE_MS = 300
MDI_WAIT_S = 3.0

ACCENT = QColor("#5ec8ff")
IDLE_TRACE = QColor("#8a9aa8")


def _ini():
    path = os.environ.get("INI_FILE_NAME")
    if not path:
        return None
    try:
        return linuxcnc.ini(path)
    except Exception as exc:
        LOG.debug("mql: cannot open INI %s: %s", path, exc)
        return None


def _ini_float(ini, section, key, fallback):
    if ini is None:
        return float(fallback)
    try:
        return float(ini.find(section, key))
    except (TypeError, ValueError):
        return float(fallback)


def _pulse_ms(freq, duty):
    if freq <= 0:
        return 0.0
    return (1000.0 / freq) * duty / 100.0


def _fmt(value):
    return "{:g}".format(round(float(value), 2))


def _repolish(widget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class SetpointControl(QFrame):
    """Big value readout, slider and +/- steppers for one M201 word."""

    valueChanged = Signal(float)  # every change, including mid-drag
    committed = Signal(float)     # slider released, stepper tapped, or value typed

    def __init__(self, code, title, unit, lo, hi, step, decimals, curve=1.0, hint="", parent=None):
        super(SetpointControl, self).__init__(parent)
        self.setObjectName("setpointCard")
        self._lo = float(lo)
        self._hi = float(hi)
        self._step = float(step)
        self._decimals = int(decimals)
        self._curve = float(curve)
        self._value = self._lo
        self._syncing = False

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        badge = QLabel(code)
        badge.setObjectName("setpointCode")
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedSize(48, 48)

        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title_lbl = QLabel(title)
        title_lbl.setObjectName("setpointTitle")
        title_box.addWidget(title_lbl)
        if hint:
            hint_lbl = QLabel(hint)
            hint_lbl.setObjectName("setpointHint")
            title_box.addWidget(hint_lbl)

        self.spin = QDoubleSpinBox()
        self.spin.setObjectName("setpointValue")
        self.spin.setRange(self._lo, self._hi)
        self.spin.setDecimals(self._decimals)
        self.spin.setSingleStep(self._step)
        self.spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.spin.setKeyboardTracking(False)
        self.spin.setMinimumWidth(168)
        self.spin.setFixedHeight(50)
        self.spin.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        line_edit = self.spin.lineEdit()
        if line_edit is not None:
            line_edit.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            line_edit.setMinimumHeight(40)

        unit_lbl = QLabel(unit)
        unit_lbl.setObjectName("setpointUnit")

        header = QHBoxLayout()
        header.setSpacing(12)
        header.addWidget(badge)
        header.addLayout(title_box)
        header.addStretch(1)
        header.addWidget(self.spin)
        header.addWidget(unit_lbl)

        self.btn_minus = QPushButton("\u2212")
        self.btn_plus = QPushButton("+")
        for btn in (self.btn_minus, self.btn_plus):
            btn.setObjectName("btnStep")
            btn.setAutoRepeat(True)
            btn.setAutoRepeatDelay(400)
            btn.setAutoRepeatInterval(80)
            btn.setFixedSize(52, 44)
            btn.setFocusPolicy(Qt.NoFocus)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setObjectName("setpointSlider")
        self.slider.setRange(0, SLIDER_STEPS)
        self.slider.setSingleStep(1)
        self.slider.setPageStep(SLIDER_STEPS // 20)

        slider_row = QHBoxLayout()
        slider_row.setSpacing(10)
        slider_row.addWidget(self.btn_minus)
        slider_row.addWidget(self.slider, 1)
        slider_row.addWidget(self.btn_plus)

        scale_row = QHBoxLayout()
        scale_row.setContentsMargins(62, 0, 62, 0)
        lo_lbl = QLabel("{} {}".format(_fmt(self._lo), unit))
        hi_lbl = QLabel("{} {}".format(_fmt(self._hi), unit))
        for lbl in (lo_lbl, hi_lbl):
            lbl.setObjectName("setpointScale")
        scale_row.addWidget(lo_lbl)
        scale_row.addStretch(1)
        if self._curve != 1.0:
            mid = self._from_frac(0.5)
            mid_lbl = QLabel("{} {}".format(_fmt(mid), unit))
            mid_lbl.setObjectName("setpointScale")
            scale_row.addWidget(mid_lbl)
            scale_row.addStretch(1)
        scale_row.addWidget(hi_lbl)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 6)
        layout.setSpacing(2)
        layout.addLayout(header)
        layout.addLayout(slider_row)
        layout.addLayout(scale_row)

        self.slider.valueChanged.connect(self._on_slider)
        self.slider.sliderReleased.connect(self._emit_commit)
        self.spin.valueChanged.connect(self._on_spin)
        self.btn_minus.clicked.connect(lambda: self._nudge(-1))
        self.btn_plus.clicked.connect(lambda: self._nudge(1))

        self.setValue(self._lo)

    def value(self):
        return self._value

    def setValue(self, value, emit=False):
        self._value = self._snap(value)
        self._syncing = True
        try:
            self.slider.setValue(self._to_slider(self._value))
            self.spin.setValue(self._value)
        finally:
            self._syncing = False
        if emit:
            self.valueChanged.emit(self._value)

    def _snap(self, value):
        value = min(self._hi, max(self._lo, float(value)))
        return round(round(value / self._step) * self._step, self._decimals)

    def _from_frac(self, frac):
        return self._snap(self._lo + (self._hi - self._lo) * (frac ** self._curve))

    def _to_slider(self, value):
        frac = (value - self._lo) / (self._hi - self._lo)
        frac = min(1.0, max(0.0, frac)) ** (1.0 / self._curve)
        return int(round(frac * SLIDER_STEPS))

    def _on_slider(self, pos):
        if self._syncing:
            return
        self._value = self._from_frac(pos / float(SLIDER_STEPS))
        self._syncing = True
        try:
            self.spin.setValue(self._value)
        finally:
            self._syncing = False
        self.valueChanged.emit(self._value)
        if not self.slider.isSliderDown():
            self._emit_commit()

    def _on_spin(self, value):
        if self._syncing:
            return
        self.setValue(value, emit=True)
        self._emit_commit()

    def _nudge(self, direction):
        self.setValue(self._value + direction * self._step, emit=True)
        self._emit_commit()

    def _emit_commit(self):
        self.committed.emit(self._value)


class PulsePreview(QWidget):
    """Injector valve timeline over a fixed window, drawn to scale."""

    def __init__(self, parent=None):
        super(PulsePreview, self).__init__(parent)
        self.setObjectName("pulsePreview")
        self.setMinimumHeight(64)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._freq = 10.0
        self._duty = 1.0
        self._spraying = False

    def set_params(self, freq, duty, spraying):
        self._freq = float(freq)
        self._duty = float(duty)
        self._spraying = bool(spraying)
        self.update()

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        plot = QRectF(self.rect()).adjusted(8, 6, -8, -22)

        painter.setPen(QPen(QColor("#4a4f51"), 1))
        painter.setBrush(QColor("#23282a"))
        painter.drawRoundedRect(plot, 6, 6)

        label_font = QFont(PB_FONT, 10)
        painter.setFont(label_font)
        grid_ms = 100.0
        steps = int(PREVIEW_WINDOW_MS / grid_ms)
        for i in range(steps + 1):
            x = plot.left() + plot.width() * (i * grid_ms / PREVIEW_WINDOW_MS)
            if 0 < i < steps:
                painter.setPen(QPen(QColor("#363c3e"), 1, Qt.DashLine))
                painter.drawLine(int(x), int(plot.top() + 4), int(x), int(plot.bottom() - 4))
            painter.setPen(QColor("#9a9e9f"))
            text = "{:.0f} MS".format(i * grid_ms) if i == steps else "{:.0f}".format(i * grid_ms)
            align = Qt.AlignRight if i == steps else (Qt.AlignLeft if i == 0 else Qt.AlignHCenter)
            box = QRectF(x - 40, plot.bottom() + 3, 80, 16)
            if i == 0:
                box.moveLeft(x)
            elif i == steps:
                box.moveRight(x)
            painter.drawText(box, align | Qt.AlignTop, text)

        painter.setClipRect(plot.adjusted(1, 1, -1, -1))
        color = ACCENT if self._spraying else IDLE_TRACE
        low_y = plot.bottom() - 10
        high_y = plot.top() + 14
        pulse = _pulse_ms(self._freq, self._duty)

        def x_at(t_ms):
            return plot.left() + plot.width() * (t_ms / PREVIEW_WINDOW_MS)

        path = QPainterPath()
        path.moveTo(plot.left() + 1, low_y)
        if pulse > 0:
            period = 1000.0 / self._freq
            fill = QColor(color)
            fill.setAlpha(60)
            t = 0.0
            while t < PREVIEW_WINDOW_MS:
                x0 = x_at(t)
                x1 = max(x_at(min(t + pulse, PREVIEW_WINDOW_MS)), x0 + 1.5)
                painter.fillRect(QRectF(x0, high_y, x1 - x0, low_y - high_y), fill)
                path.lineTo(x0, low_y)
                path.lineTo(x0, high_y)
                path.lineTo(x1, high_y)
                path.lineTo(x1, low_y)
                t += period
        path.lineTo(plot.right() - 1, low_y)
        painter.setPen(QPen(color, 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)
        painter.setClipping(False)

        painter.setPen(QColor("#b8bcbe"))
        painter.setFont(QFont(PB_FONT, 11))
        tag = "SPRAYING" if self._spraying else "PREVIEW (M8 OFF)"
        if pulse <= 0:
            tag = "NO PULSE (Q0)"
        painter.drawText(plot.adjusted(10, 4, -10, 0), Qt.AlignRight | Qt.AlignTop, tag)


class UserTab(QWidget):
    def __init__(self, parent=None):
        super(UserTab, self).__init__(parent)
        here = os.path.dirname(os.path.abspath(__file__))
        uic.loadUi(os.path.join(here, "mql_control.ui"), self)

        self.setObjectName("MQL")
        self._ensure_font()
        self._load_stylesheet(here)
        self._apply_panel_background()

        try:
            self._cmd = linuxcnc.command()
            self._stat = linuxcnc.stat()
        except Exception as exc:
            LOG.error("mql: linuxcnc init failed: %s", exc)
            self._cmd = None
            self._stat = None

        ini = _ini()
        self._default_freq = _ini_float(ini, "COOLANT", "DEFAULT_FREQ", 10.0)
        self._default_duty = _ini_float(ini, "COOLANT", "DEFAULT_DUTY", 1.0)
        self._profile_path = self._resolve_profile_path(ini)

        self._active = None
        self._spraying = False
        self._tool_in_spindle = 0
        self._presets = self._load_presets()

        self._live_timer = QTimer(self)
        self._live_timer.setSingleShot(True)
        self._live_timer.setInterval(LIVE_DEBOUNCE_MS)
        self._live_timer.timeout.connect(self._apply)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(POLL_MS)
        self._poll_timer.timeout.connect(self._poll)

        self._build_ui()
        self._refresh_preset_list()
        self._poll()
        self._load_active_into_controls()
        if self._tool_in_spindle > 0:
            self.spin_tool.setValue(self._tool_in_spindle)
        self._refresh_tool_info()
        self._update_derived()

    # ---- setup -----------------------------------------------------------

    def _ensure_font(self):
        if os.path.exists(PB_FONT_PATH):
            QFontDatabase.addApplicationFont(PB_FONT_PATH)
        self.setFont(QFont(PB_FONT))

    def _load_stylesheet(self, here):
        path = os.path.join(here, "mql_control.qss")
        try:
            with open(path, "r") as fh:
                self.setStyleSheet(fh.read())
        except IOError as exc:
            LOG.warning("mql: stylesheet %s not loaded: %s", path, exc)

    def _apply_panel_background(self):
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor(46, 52, 54))
        self.setPalette(palette)

    def _resolve_profile_path(self, ini):
        rel = None
        if ini is not None:
            rel = ini.find("COOLANT", "PROFILE_FILE")
        rel = rel or DEFAULT_PROFILE_FILE
        if os.path.isabs(rel):
            return rel
        base = os.path.dirname(os.path.abspath(os.environ["INI_FILE_NAME"])) \
            if os.environ.get("INI_FILE_NAME") else CONFIG_DIR
        return os.path.join(base, rel)

    def _card(self, name, title=None):
        frame = QFrame()
        frame.setObjectName(name)
        frame.setAttribute(Qt.WA_StyledBackground, True)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 8, 14, 10)
        layout.setSpacing(6)
        if title:
            lbl = QLabel(title)
            lbl.setObjectName("cardTitle")
            layout.addWidget(lbl)
        return frame, layout

    def _stat_tile(self, caption):
        tile = QFrame()
        tile.setObjectName("statTile")
        tile.setAttribute(Qt.WA_StyledBackground, True)
        box = QVBoxLayout(tile)
        box.setContentsMargins(10, 3, 10, 3)
        box.setSpacing(0)
        value = QLabel("-")
        value.setObjectName("statValue")
        cap = QLabel(caption)
        cap.setObjectName("statCaption")
        box.addWidget(value)
        box.addWidget(cap)
        return tile, value

    def _build_ui(self):
        root = self.rootLayout

        header = QFrame()
        header.setObjectName("headerBar")
        header.setAttribute(Qt.WA_StyledBackground, True)
        hbox = QHBoxLayout(header)
        hbox.setContentsMargins(16, 8, 12, 8)
        hbox.setSpacing(12)
        title = QLabel("MQL COOLANT")
        title.setObjectName("lblTitle")
        subtitle = QLabel("MICROJECT \u00b7 M201 P<HZ> Q<DUTY %>")
        subtitle.setObjectName("lblSubtitle")
        self.lbl_active = QLabel()
        self.lbl_active.setObjectName("pill")
        self.lbl_spray = QLabel()
        self.lbl_spray.setObjectName("pill")
        # Status line lives in the header so the tab fits Probe Basic's 619 px tab area.
        self.lbl_message = QLabel()
        self.lbl_message.setObjectName("lblMessage")
        self.lbl_message.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_message.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        hbox.addWidget(title)
        hbox.addWidget(subtitle)
        hbox.addWidget(self.lbl_message, 1)
        hbox.addWidget(self.lbl_active)
        hbox.addWidget(self.lbl_spray)
        root.addWidget(header)

        body = QHBoxLayout()
        body.setSpacing(10)
        root.addLayout(body, 1)

        left = QVBoxLayout()
        left.setSpacing(10)
        body.addLayout(left, 3)

        self.freq = SetpointControl(
            "P", "PULSE RATE", "HZ", FREQ_MIN, FREQ_MAX, FREQ_STEP, 1,
            hint="INJECTOR OPENINGS PER SECOND",
        )
        self.duty = SetpointControl(
            "Q", "DUTY CYCLE", "%", DUTY_MIN, DUTY_MAX, DUTY_STEP, 1, curve=DUTY_CURVE,
            hint="SHARE OF EACH PERIOD THE VALVE IS OPEN",
        )
        for ctrl in (self.freq, self.duty):
            ctrl.valueChanged.connect(self._update_derived)
            ctrl.committed.connect(self._on_committed)
            left.addWidget(ctrl)

        preview_card, preview_box = self._card("previewCard", "PULSE TRAIN \u00b7 FIRST 500 MS")
        self.preview = PulsePreview()
        preview_box.addWidget(self.preview, 1)
        tiles = QHBoxLayout()
        tiles.setSpacing(8)
        tile, self.val_period = self._stat_tile("PERIOD (MS)")
        tiles.addWidget(tile)
        self.tile_pulse, self.val_pulse = self._stat_tile("PULSE LENGTH (MS)")
        tiles.addWidget(self.tile_pulse)
        tile, self.val_open = self._stat_tile("OPEN TIME (MS / SEC)")
        tiles.addWidget(tile)
        tile, self.val_ppm = self._stat_tile("PULSES / MIN")
        tiles.addWidget(tile)
        preview_box.addLayout(tiles)
        left.addWidget(preview_card, 1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.btn_spray_on = QPushButton("M8 SPRAY ON")
        self.btn_spray_on.setObjectName("btnSprayOn")
        self.btn_spray_on.setProperty("baseTip", "Sends the current setpoint (M201) then M8")
        self.btn_spray_off = QPushButton("M9 OFF")
        self.btn_spray_off.setObjectName("btnSprayOff")
        self.lbl_gcode = QLabel()
        self.lbl_gcode.setObjectName("lblGcode")
        self.lbl_gcode.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_gcode.setAlignment(Qt.AlignCenter)
        self.lbl_gcode.setMinimumHeight(44)
        self.lbl_gcode.setToolTip("Paste into a program or MDI for the same result")
        self.btn_live = QPushButton("LIVE")
        self.btn_live.setObjectName("btnLive")
        self.btn_live.setCheckable(True)
        self.btn_live.setToolTip("Send M201 automatically whenever a setpoint changes")
        self.btn_revert = QPushButton("REVERT")
        self.btn_revert.setToolTip("Reload the values the machine is using now")
        self.btn_apply = QPushButton("APPLY")
        self.btn_apply.setObjectName("btnApply")
        actions.addWidget(self.btn_spray_on)
        actions.addWidget(self.btn_spray_off)
        actions.addStretch(1)
        actions.addWidget(self.lbl_gcode)
        actions.addStretch(1)
        actions.addWidget(self.btn_live)
        actions.addWidget(self.btn_revert)
        actions.addWidget(self.btn_apply)
        left.addLayout(actions)

        right = QVBoxLayout()
        right.setSpacing(10)
        body.addLayout(right, 2)

        preset_card, preset_box = self._card("presetCard", "PRESETS")
        self.preset_list = QListWidget()
        self.preset_list.setObjectName("presetList")
        self.preset_list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        preset_box.addWidget(self.preset_list, 1)
        name_row = QHBoxLayout()
        self.le_name = QLineEdit()
        self.le_name.setObjectName("leName")
        self.le_name.setPlaceholderText("PRESET NAME")
        self.btn_save = QPushButton("SAVE")
        name_row.addWidget(self.le_name, 1)
        name_row.addWidget(self.btn_save)
        preset_box.addLayout(name_row)
        preset_btns = QHBoxLayout()
        self.btn_load = QPushButton("LOAD")
        self.btn_delete = QPushButton("DELETE")
        self.btn_delete.setObjectName("btnDelete")
        preset_btns.addWidget(self.btn_load, 1)
        preset_btns.addWidget(self.btn_delete, 1)
        preset_box.addLayout(preset_btns)
        right.addWidget(preset_card, 3)

        tool_card, tool_box = self._card("toolCard", "TOOL RECIPE \u00b7 M202")
        hint = QLabel("M202 LOADS THE RECIPE FOR THE TOOL IN THE SPINDLE")
        hint.setObjectName("setpointHint")
        hint.setWordWrap(True)
        tool_box.addWidget(hint)
        tool_row = QHBoxLayout()
        t_lbl = QLabel("T")
        t_lbl.setObjectName("setpointCode")
        t_lbl.setAlignment(Qt.AlignCenter)
        t_lbl.setFixedSize(48, 48)
        self.spin_tool = QSpinBox()
        self.spin_tool.setObjectName("spinTool")
        self.spin_tool.setRange(1, 9999)
        self.spin_tool.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin_tool.setAlignment(Qt.AlignCenter)
        self.spin_tool.setFixedHeight(48)
        tool_edit = self.spin_tool.lineEdit()
        if tool_edit is not None:
            tool_edit.setAlignment(Qt.AlignCenter)
            tool_edit.setMinimumHeight(36)
        self.btn_in_spindle = QPushButton("IN SPINDLE")
        tool_row.addWidget(t_lbl)
        tool_row.addWidget(self.spin_tool, 1)
        tool_row.addWidget(self.btn_in_spindle, 1)
        tool_box.addLayout(tool_row)
        self.lbl_tool_info = QLabel()
        self.lbl_tool_info.setObjectName("lblToolInfo")
        self.lbl_tool_info.setWordWrap(True)
        tool_box.addWidget(self.lbl_tool_info)
        tool_btns = QHBoxLayout()
        self.btn_tool_load = QPushButton("LOAD")
        self.btn_tool_save = QPushButton("SAVE TO TOOL")
        tool_btns.addWidget(self.btn_tool_load, 1)
        tool_btns.addWidget(self.btn_tool_save, 1)
        tool_box.addLayout(tool_btns)
        right.addWidget(tool_card, 0)


        self.btn_apply.clicked.connect(self._apply)
        self.btn_revert.clicked.connect(self._load_active_into_controls)
        self.btn_live.toggled.connect(self._on_live_toggled)
        self.btn_spray_on.clicked.connect(self._spray_on)
        self.btn_spray_off.clicked.connect(self._spray_off)
        self.btn_save.clicked.connect(self._save_preset)
        self.le_name.returnPressed.connect(self._save_preset)
        self.btn_load.clicked.connect(self._load_selected_preset)
        self.btn_delete.clicked.connect(self._delete_selected_preset)
        self.preset_list.itemDoubleClicked.connect(lambda _item: self._load_selected_preset())
        self.preset_list.currentRowChanged.connect(self._on_preset_selected)
        self.spin_tool.valueChanged.connect(self._refresh_tool_info)
        self.btn_in_spindle.clicked.connect(self._select_spindle_tool)
        self.btn_tool_load.clicked.connect(self._load_tool_recipe)
        self.btn_tool_save.clicked.connect(self._save_tool_recipe)

    # ---- visibility ------------------------------------------------------

    def showEvent(self, event):  # noqa: N802
        super(UserTab, self).showEvent(event)
        self._poll()
        self._poll_timer.start()

    def hideEvent(self, event):  # noqa: N802
        super(UserTab, self).hideEvent(event)
        self._poll_timer.stop()

    # ---- machine state ---------------------------------------------------

    def _poll(self):
        if self._stat is None:
            self._set_pill(self.lbl_spray, "LINUXCNC OFFLINE", "warn")
            self._set_pill(self.lbl_active, "MACHINE: ?", "")
            return
        try:
            self._stat.poll()
        except Exception as exc:
            LOG.debug("mql: stat poll failed: %s", exc)
            return

        aout = getattr(self._stat, "aout", ())
        if len(aout) > 5:
            raw_freq, raw_duty = float(aout[4]), float(aout[5])
            if abs(raw_freq) < 1e-9 and abs(raw_duty) < 1e-9:
                self._active = None
            else:
                self._active = (min(FREQ_MAX, max(FREQ_MIN, raw_freq)), raw_duty)
        self._spraying = bool(self._stat.flood or self._stat.mist)
        self._tool_in_spindle = int(self._stat.tool_in_spindle)

        if self._active is None:
            self._set_pill(self.lbl_active, "MACHINE: NOT SET", "warn")
        else:
            self._set_pill(
                self.lbl_active,
                "MACHINE: {} HZ \u00b7 {} %".format(_fmt(self._active[0]), _fmt(self._active[1])),
                "pending" if self._is_pending() else "",
            )
        if self._spraying:
            self._set_pill(self.lbl_spray, "SPRAY ON", "on")
        else:
            self._set_pill(self.lbl_spray, "SPRAY OFF", "")

        self.btn_in_spindle.setText(
            "IN SPINDLE (T{})".format(self._tool_in_spindle) if self._tool_in_spindle > 0
            else "IN SPINDLE (EMPTY)"
        )
        self.btn_in_spindle.setEnabled(self._tool_in_spindle > 0)

        blocked = self._mdi_blocked_reason()
        for btn in (self.btn_apply, self.btn_spray_on, self.btn_spray_off):
            btn.setEnabled(blocked is None)
            btn.setToolTip(blocked or btn.property("baseTip") or "")
        self._update_pending()
        self.preview.set_params(self.freq.value(), self.duty.value(), self._spraying)

    def _set_pill(self, label, text, state):
        if label.text() != text:
            label.setText(text)
        if label.property("state") != state:
            label.setProperty("state", state)
            _repolish(label)

    def _is_pending(self):
        if self._active is None:
            return True
        return (abs(self._active[0] - self.freq.value()) > 1e-6
                or abs(self._active[1] - self.duty.value()) > 1e-6)

    def _update_pending(self):
        pending = self._is_pending()
        if bool(self.btn_apply.property("pending")) != pending:
            self.btn_apply.setProperty("pending", pending)
            _repolish(self.btn_apply)

    def _mdi_blocked_reason(self):
        if self._cmd is None or self._stat is None:
            return "LINUXCNC UNAVAILABLE"
        if self._stat.task_state == linuxcnc.STATE_ESTOP:
            return "E-STOP"
        if not self._stat.enabled:
            return "MACHINE OFF"
        if self._stat.interp_state != linuxcnc.INTERP_IDLE:
            return "PROGRAM RUNNING - PUT M201 IN THE G-CODE INSTEAD"
        return None

    def _send_mdi(self, *lines):
        try:
            self._stat.poll()
        except Exception:
            pass
        blocked = self._mdi_blocked_reason()
        if blocked:
            self._message("BLOCKED: " + blocked, "error")
            return False
        try:
            self._cmd.mode(linuxcnc.MODE_MDI)
            self._cmd.wait_complete(MDI_WAIT_S)
            for line in lines:
                self._cmd.mdi(line)
                self._cmd.wait_complete(MDI_WAIT_S)
        except Exception as exc:
            LOG.error("mql: MDI %s failed: %s", lines, exc)
            self._message("ERROR: {}".format(exc), "error")
            return False
        LOG.info("mql: MDI %s", " / ".join(lines))
        return True

    # ---- setpoint --------------------------------------------------------

    def _gcode(self):
        return "M201 P{} Q{}".format(_fmt(self.freq.value()), _fmt(self.duty.value()))

    def _update_derived(self, *_args):
        freq = self.freq.value()
        duty = self.duty.value()
        period = 1000.0 / freq
        pulse = _pulse_ms(freq, duty)
        self.val_period.setText("{:.1f}".format(period))
        self.val_pulse.setText("{:.2f}".format(pulse))
        self.val_open.setText("{:.0f}".format(duty * 10.0))
        self.val_ppm.setText("{:.0f}".format(freq * 60.0))

        short = 0 < pulse < SHORT_PULSE_MS
        if bool(self.tile_pulse.property("warn")) != short:
            self.tile_pulse.setProperty("warn", short)
            _repolish(self.tile_pulse)
            for child in self.tile_pulse.findChildren(QLabel):
                _repolish(child)
        self.tile_pulse.setToolTip(
            "Under {:g} ms (firmware default) - the injector may not fully open".format(SHORT_PULSE_MS)
            if short else ""
        )

        self.lbl_gcode.setText(self._gcode())
        self.preview.set_params(freq, duty, self._spraying)
        self._update_pending()

    def _on_committed(self, *_args):
        self._update_derived()
        if self.btn_live.isChecked():
            self._live_timer.start()

    def _on_live_toggled(self, checked):
        if checked:
            self._message("LIVE: SETPOINT CHANGES ARE SENT AUTOMATICALLY", "info")
            if self._is_pending():
                self._live_timer.start()
        else:
            self._live_timer.stop()
            self._message("LIVE OFF: PRESS APPLY TO SEND", "info")

    def _apply(self):
        self._live_timer.stop()
        cmd = self._gcode()
        if self._send_mdi(cmd):
            self._message("SENT: " + cmd, "ok")
            self._poll()

    def _spray_on(self):
        cmd = self._gcode()
        if self._send_mdi(cmd, "M8"):
            self._message("SPRAY ON: {} + M8".format(cmd), "ok")
            self._poll()

    def _spray_off(self):
        if self._send_mdi("M9"):
            self._message("SPRAY OFF: M9", "ok")
            self._poll()

    def _set_controls(self, freq, duty):
        self.freq.setValue(freq)
        self.duty.setValue(duty)
        self._update_derived()

    def _load_active_into_controls(self, *_args):
        if self._active is None:
            self._set_controls(self._default_freq, self._default_duty)
            self._message(
                "MACHINE HAS NO SETPOINT YET - SHOWING INI DEFAULT {} HZ / {} %".format(
                    _fmt(self._default_freq), _fmt(self._default_duty)),
                "info",
            )
        else:
            self._set_controls(*self._active)
            self._message("LOADED MACHINE SETPOINT", "info")

    # ---- presets ---------------------------------------------------------

    def _load_presets(self):
        try:
            with open(PRESETS_PATH, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            presets = []
            for entry in data.get("presets", []):
                presets.append({
                    "name": str(entry["name"]),
                    "freq": float(entry["freq"]),
                    "duty": float(entry["duty"]),
                })
            return presets
        except FileNotFoundError:
            return [{"name": "Default", "freq": self._default_freq, "duty": self._default_duty}]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            LOG.error("mql: cannot read %s: %s", PRESETS_PATH, exc)
            return []

    def _write_presets(self):
        tmp = PRESETS_PATH + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({"presets": self._presets}, fh, indent=2)
                fh.write("\n")
            os.replace(tmp, PRESETS_PATH)
            return True
        except OSError as exc:
            LOG.error("mql: cannot write %s: %s", PRESETS_PATH, exc)
            self._message("ERROR: cannot write presets ({})".format(exc), "error")
            return False

    def _refresh_preset_list(self, select_name=None):
        self.preset_list.blockSignals(True)
        self.preset_list.clear()
        select_row = -1
        for row, preset in enumerate(self._presets):
            pulse = _pulse_ms(preset["freq"], preset["duty"])
            item = QListWidgetItem("{}\n{} HZ  \u00b7  {} %  \u00b7  {:.2f} MS PULSE".format(
                preset["name"], _fmt(preset["freq"]), _fmt(preset["duty"]), pulse))
            self.preset_list.addItem(item)
            if select_name is not None and preset["name"].lower() == select_name.lower():
                select_row = row
        self.preset_list.blockSignals(False)
        if select_row >= 0:
            self.preset_list.setCurrentRow(select_row)

    def _selected_preset(self):
        row = self.preset_list.currentRow()
        if 0 <= row < len(self._presets):
            return row, self._presets[row]
        return -1, None

    def _on_preset_selected(self, row):
        if 0 <= row < len(self._presets):
            self.le_name.setText(self._presets[row]["name"])

    def _save_preset(self):
        name = self.le_name.text().strip()
        if not name:
            self._message("ENTER A PRESET NAME FIRST", "error")
            self.le_name.setFocus()
            return
        entry = {"name": name, "freq": self.freq.value(), "duty": self.duty.value()}
        for idx, preset in enumerate(self._presets):
            if preset["name"].lower() == name.lower():
                self._presets[idx] = entry
                verb = "UPDATED"
                break
        else:
            self._presets.append(entry)
            verb = "SAVED"
        if self._write_presets():
            self._refresh_preset_list(select_name=name)
            self._message("{} PRESET \"{}\": {}".format(verb, name, self._gcode()), "ok")

    def _load_selected_preset(self):
        _row, preset = self._selected_preset()
        if preset is None:
            self._message("SELECT A PRESET FIRST", "error")
            return
        self._set_controls(preset["freq"], preset["duty"])
        self._message("LOADED PRESET \"{}\"{}".format(
            preset["name"], "" if self.btn_live.isChecked() else " - PRESS APPLY TO SEND"), "info")
        self._on_committed()

    def _delete_selected_preset(self):
        row, preset = self._selected_preset()
        if preset is None:
            self._message("SELECT A PRESET FIRST", "error")
            return
        answer = QMessageBox.question(
            self, "Delete preset", "Delete preset \"{}\"?".format(preset["name"]),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        del self._presets[row]
        if self._write_presets():
            self._refresh_preset_list()
            self.le_name.clear()
            self._message("DELETED PRESET \"{}\"".format(preset["name"]), "ok")

    # ---- per-tool recipes (M202) ------------------------------------------

    def _tool_recipe(self, tool):
        default, tools = load_profiles(self._profile_path)
        return recipe_for_tool(default, tools, tool), tool in tools

    def _refresh_tool_info(self, *_args):
        tool = self.spin_tool.value()
        try:
            recipe, own = self._tool_recipe(tool)
        except Exception as exc:
            self.lbl_tool_info.setText("CANNOT READ {}: {}".format(
                os.path.basename(self._profile_path), exc))
            return
        self.lbl_tool_info.setText("T{}: {} HZ \u00b7 {} %  ({})".format(
            tool, _fmt(recipe.freq), _fmt(recipe.duty),
            "OWN ENTRY" if own else "USES [DEFAULT]"))

    def _select_spindle_tool(self):
        if self._tool_in_spindle > 0:
            self.spin_tool.setValue(self._tool_in_spindle)

    def _load_tool_recipe(self):
        tool = self.spin_tool.value()
        try:
            recipe, _own = self._tool_recipe(tool)
        except Exception as exc:
            self._message("ERROR: {}".format(exc), "error")
            return
        self._set_controls(max(FREQ_MIN, recipe.freq), recipe.duty)
        self._message("LOADED T{} RECIPE".format(tool), "info")
        self._on_committed()

    def _save_tool_recipe(self):
        tool = self.spin_tool.value()
        freq, duty = self.freq.value(), self.duty.value()
        try:
            save_tool_recipe(self._profile_path, tool, {"FREQ": freq, "DUTY": duty})
        except Exception as exc:
            LOG.error("mql: save T%d failed: %s", tool, exc)
            self._message("ERROR: {}".format(exc), "error")
            return
        self._refresh_tool_info()
        self._message("SAVED T{}: {} HZ / {} % - M202 USES IT NEXT CALL".format(
            tool, _fmt(freq), _fmt(duty)), "ok")

    # ---- status line -----------------------------------------------------

    def _message(self, text, state="info"):
        LOG.info("mql: %s", text)
        self.lbl_message.setText(text)
        self.lbl_message.setToolTip(text)
        self.lbl_message.setProperty("state", state)
        _repolish(self.lbl_message)
