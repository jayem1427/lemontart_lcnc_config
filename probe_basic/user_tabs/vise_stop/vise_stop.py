"""
VISE STOP - self-centering vise with the spindle tool as a hard stop.

The self-centering vise holds the clamp axis and Z (calibrated once into the
vise WCS with normal Probe Basic probing). The only loose axis is along the
jaws. GO TO STOP writes that axis of the vise WCS from the stored stop
position and the loaded tool's diameter, then parks the tool at the stop.
Slide the part against it, clamp, RETRACT, run.

Settings live in #5580-#5587 (see probe_basic/subroutines/vise_stop_go.ngc).
They are pushed to the interpreter by MDI and merged into linuxcnc.var on
GO TO STOP and CAPTURE STOP, so LinuxCNC keeps them on exit.
Docs: docs/VISE_STOP.md
"""

import os

import linuxcnc

from qtpy import uic
from qtpy.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from qtpy.QtGui import QBrush, QColor, QFont, QFontDatabase, QPainter, QPen, QTransform
from qtpy.QtWidgets import (
    QAbstractSpinBox,
    QButtonGroup,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from qtpyvcp.utilities import logger

LOG = logger.getLogger(__name__)

PB_FONT_PATH = "/usr/share/fonts/truetype/BebasKai.ttf"
CONFIG_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir, os.pardir)
)
VAR_FILE = os.path.join(CONFIG_DIR, "linuxcnc.var")

P_AXIS, P_SIDE, P_STOP, P_STOP_Z, P_MODE, P_LENGTH, P_WCS, P_LAST = range(5580, 5588)
VISE_PARAMS = (P_AXIS, P_SIDE, P_STOP, P_STOP_Z, P_MODE, P_LENGTH, P_WCS, P_LAST)
DEFAULTS = {P_AXIS: 0.0, P_SIDE: 1.0, P_STOP: 0.0, P_STOP_Z: 5.0,
            P_MODE: 0.0, P_LENGTH: 0.0, P_WCS: 2.0, P_LAST: 0.0}
PROBE_TOOL = 99  # #3014
WCS_NAMES = ["G54", "G55", "G56", "G57", "G58", "G59"]
POLL_MS = 250

GO_MDI = "o<vise_stop_go> call"
RETRACT_MDI = "o<vise_stop_retract> call"


# ---------------------------------------------------------------- graphics
# Schematic of the H67 self-centering vise seen from above, plus a side view.
# Sizes are rough (mm) and only set proportions; the pin is drawn at its real
# diameter so the user sees which side of it the part goes.
BODY_U, BODY_V = 67.0, 110.0          # u = along the jaws (free axis), v = clamp axis
JAW_IN, JAW_OUT = 16.0, 38.0          # jaw inner / outer face, from the vise center
NOMINAL_PART = 40.0                   # drawn part length when none is given

C_BG = QColor("#23282a")
C_BODY = QColor("#4a4f51")
C_SLOT = QColor("#2e3436")
C_JAW = QColor("#8a8e90")
C_EDGE = QColor("#1b1f20")
C_PART = QColor(94, 200, 255, 150)
C_PART_EDGE = QColor("#5ec8ff")
C_PIN = QColor("#fcaf3e")
C_BAD = QColor("#ef2929")
C_ORIGIN = QColor("#73d216")
C_TEXT = QColor(238, 238, 236)
C_DIM = QColor("#9a9e9f")


def _font(pt):
    f = QFont("BebasKai")
    f.setPointSizeF(pt)
    return f


def _arrow(p, a, b, head=9.0):
    """Line a->b with a filled head at b (screen coords)."""
    p.drawLine(a, b)
    dx, dy = b.x() - a.x(), b.y() - a.y()
    n = max((dx * dx + dy * dy) ** 0.5, 1e-6)
    ux, uy = dx / n, dy / n
    left = QPointF(b.x() - head * ux + head * 0.5 * uy, b.y() - head * uy - head * 0.5 * ux)
    right = QPointF(b.x() - head * ux - head * 0.5 * uy, b.y() - head * uy + head * 0.5 * ux)
    p.save()
    p.setBrush(p.pen().color())
    p.drawPolygon(b, left, right)
    p.restore()


class _ViewBase(QWidget):
    def __init__(self, parent=None):
        super(_ViewBase, self).__init__(parent)
        self.st = {}
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_state(self, **st):
        if st != self.st:
            self.st = st
            self.update()

    def _geometry(self):
        """Pin radius, part length, pin u, origin u - all in the vise frame."""
        st = self.st
        side = st.get("side", 1)
        dia = st.get("dia", 0.0)
        r = dia / 2.0 if dia > 0 else 3.0
        length = st.get("length", 0.0)
        if not (st.get("mode") == 1 and length > 0):
            length = NOMINAL_PART
        u_pin = -side * (length / 2.0 + r)          # part centered in the vise
        u_org = 0.0 if st.get("mode") == 1 else -side * length / 2.0
        return side, r, length, u_pin, u_org

    def _bg(self, p):
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen)
        p.setBrush(C_BG)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 6, 6)


class ViseTopView(_ViewBase):
    """Top-down view in machine orientation (+X right, +Y up). Click a side to put the part there."""
    sideClicked = Signal(int)

    def __init__(self, parent=None):
        super(ViseTopView, self).__init__(parent)
        self.setMinimumSize(360, 200)
        self.setCursor(Qt.PointingHandCursor)
        self._xf = QTransform()

    def _transform(self, half_u, half_v):
        axis_y = self.st.get("axis", 0) == 1
        w, h = self.width(), self.height() - 26          # bottom strip for the axis legend
        span_x, span_y = (half_v, half_u) if axis_y else (half_u, half_v)
        s = min((w - 40) / (2 * span_x), (h - 44) / (2 * span_y))
        cx, cy = w / 2.0, h / 2.0 + 14
        if axis_y:   # u -> screen up, v -> screen right
            return QTransform(0, -s, s, 0, cx, cy), s
        return QTransform(s, 0, 0, -s, cx, cy), s      # u -> right, v -> up

    def mousePressEvent(self, ev):
        inv, ok = self._xf.inverted()
        if ok:
            u = inv.map(QPointF(ev.pos())).x()
            self.sideClicked.emit(1 if u > 0 else -1)

    def paintEvent(self, _ev):
        p = QPainter(self)
        self._bg(p)
        st = self.st
        side, r, length, u_pin, u_org = self._geometry()
        half_u = max(BODY_U / 2.0, length / 2.0 + 2 * r) + 10
        half_v = BODY_V / 2.0 + 10
        xf, s = self._transform(half_u, half_v)
        self._xf = xf
        axis = "Y" if st.get("axis", 0) == 1 else "X"
        clamp = "X" if axis == "Y" else "Y"
        m = xf.map

        def rect(u0, v0, u1, v1, fill, edge=C_EDGE, width=1.5, style=Qt.SolidLine):
            p.setPen(QPen(edge, width, style) if edge is not None else Qt.NoPen)
            p.setBrush(fill if fill is not None else Qt.NoBrush)
            p.drawPolygon(m(QPointF(u0, v0)), m(QPointF(u1, v0)), m(QPointF(u1, v1)), m(QPointF(u0, v1)))

        def circle(u, v, rad, fill, edge=C_EDGE, width=1.5, style=Qt.SolidLine):
            p.setPen(QPen(edge, width, style) if edge is not None else Qt.NoPen)
            p.setBrush(fill if fill is not None else Qt.NoBrush)
            p.drawEllipse(m(QPointF(u, v)), rad * s, rad * s)

        bu, bv = BODY_U / 2.0, BODY_V / 2.0
        # body, center slot, screw end
        rect(-bu, -bv, bu, bv, C_BODY)
        rect(-bu * 0.45, -JAW_OUT, bu * 0.45, JAW_OUT, C_SLOT, None)
        rect(-6, -bv - 7, 6, -bv, C_JAW)
        # jaws with serrations and two bolts each
        for sgn in (1, -1):
            rect(-bu, sgn * JAW_IN, bu, sgn * JAW_OUT, C_JAW)
            p.setPen(QPen(C_EDGE, 1, Qt.DotLine))
            p.drawLine(m(QPointF(-bu, sgn * (JAW_IN + 2.5))), m(QPointF(bu, sgn * (JAW_IN + 2.5))))
            for bu_ in (-20.0, 20.0):
                circle(bu_, sgn * (JAW_OUT - 9), 4.5, C_SLOT)
        # part
        rect(-length / 2.0, -JAW_IN, length / 2.0, JAW_IN, C_PART, C_PART_EDGE, 2)
        # spindle nose (generic) and the stop pin
        circle(u_pin, 0, 18, None, C_DIM, 1.2, Qt.DashLine)
        bad = st.get("bad_tool", False) or st.get("dia", 0) <= 0
        circle(u_pin, 0, r, C_BAD if bad else C_PIN, C_EDGE, 1.5)
        c = m(QPointF(u_pin, 0))
        p.setPen(QPen(C_BAD if bad else C_PIN, 2))
        p.setBrush(Qt.NoBrush)
        halo = max(r * s + 6, 12)
        p.drawEllipse(c, halo, halo)
        p.setPen(QPen(C_EDGE, 1.2))
        p.drawLine(QPointF(c.x() - r * s, c.y()), QPointF(c.x() + r * s, c.y()))
        p.drawLine(QPointF(c.x(), c.y() - r * s), QPointF(c.x(), c.y() + r * s))
        # origin target
        o = m(QPointF(u_org, 0))
        p.setPen(QPen(C_ORIGIN, 2.5))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(o, 9, 9)
        p.drawLine(QPointF(o.x() - 15, o.y()), QPointF(o.x() + 15, o.y()))
        p.drawLine(QPointF(o.x(), o.y() - 15), QPointF(o.x(), o.y() + 15))

        # ---- screen-space text and arrows
        p.setFont(_font(12))
        far = m(QPointF(side * (length / 2.0 + 12), 0))
        near = m(QPointF(side * (length / 2.0 + 1), 0))
        p.setPen(QPen(C_PART_EDGE, 3))
        _arrow(p, far, near)                                   # push toward the pin
        p.setPen(C_TEXT)
        pc = m(QPointF(0, 0))
        p.drawText(QRectF(pc.x() - 60, pc.y() - 32, 120, 20), Qt.AlignCenter, "PART")
        wcs = st.get("wcs", "G55")
        tool = st.get("tool", 0)
        if st.get("bad_tool"):
            pin_txt = "STOP PIN: PROBE LOADED"
        elif tool <= 0:
            pin_txt = "STOP PIN: NO TOOL"
        elif st.get("dia", 0) <= 0:
            pin_txt = "STOP PIN: T{} HAS NO DIAMETER".format(tool)
        else:
            pin_txt = "STOP PIN: T{}  DIA {:.3f}".format(tool, st.get("dia", 0))
        p.setFont(_font(13))
        p.setPen(C_BAD if bad else C_PIN)
        p.drawText(QRectF(12, 8, self.width() / 2.0, 22), Qt.AlignLeft, pin_txt)
        p.setPen(C_ORIGIN)
        p.drawText(QRectF(self.width() / 2.0, 8, self.width() / 2.0 - 12, 22), Qt.AlignRight,
                   "ORIGIN: {} {}0 {}0".format(wcs, axis, clamp))
        p.setFont(_font(11))
        p.setPen(C_EDGE)
        for sgn in (1, -1):
            jc = m(QPointF(0, sgn * (JAW_IN + JAW_OUT) / 2.0))
            p.drawText(QRectF(jc.x() - 30, jc.y() - 10, 60, 20), Qt.AlignCenter, "JAW")
        # machine axis legend
        y0 = self.height() - 14
        p.setPen(QPen(C_TEXT, 2))
        _arrow(p, QPointF(16, y0), QPointF(50, y0), 7)
        _arrow(p, QPointF(16, y0), QPointF(16, y0 - 30), 7)
        p.setFont(_font(11))
        p.drawText(QPointF(55, y0 + 4), "+X")
        p.drawText(QPointF(22, y0 - 26), "+Y")
        p.setPen(C_DIM)
        p.drawText(QRectF(70, y0 - 10, self.width() - 80, 20), Qt.AlignRight | Qt.AlignVCenter,
                   "TOP VIEW - LOOKING DOWN - TAP A SIDE TO PUT THE PART THERE")
        p.end()


class ViseSideView(_ViewBase):
    """Side view along the jaws: where the pin tip ends up relative to Z0."""

    def __init__(self, parent=None):
        super(ViseSideView, self).__init__(parent)
        self.setMinimumSize(360, 120)

    def paintEvent(self, _ev):
        p = QPainter(self)
        self._bg(p)
        st = self.st
        side, r, length, u_pin, _u_org = self._geometry()
        stop_z = st.get("stop_z", 5.0)
        part_h = 15.0
        z_lo, z_hi = -22.0, max(part_h, stop_z) + 40.0
        half_u = max(BODY_U / 2.0, length / 2.0 + 2 * r) + 10
        w, h = self.width(), self.height()
        s = min((w - 40) / (2 * half_u), (h - 24) / (z_hi - z_lo))
        cx = w / 2.0
        zy = lambda z: h - 10 - (z - z_lo) * s   # noqa: E731
        ux = lambda u: cx + u * s                 # noqa: E731
        axis = "Y" if st.get("axis", 0) == 1 else "X"

        def box(u0, z0, u1, z1, fill, edge=C_EDGE):
            p.setPen(QPen(edge, 1.5) if edge is not None else Qt.NoPen)
            p.setBrush(fill)
            p.drawRect(QRectF(QPointF(ux(u0), zy(z1)), QPointF(ux(u1), zy(z0))))

        bu = BODY_U / 2.0
        box(-bu, -22, bu, -8, C_BODY)                     # vise body
        box(-bu, -8, bu, 10, QColor(138, 142, 144, 110))  # back jaw (behind the part)
        box(-length / 2.0 + 2, -8, length / 2.0 - 2, 0, QColor("#6b7072"))   # parallels
        box(-length / 2.0, 0, length / 2.0, part_h, C_PART, C_PART_EDGE)     # part
        bad = st.get("bad_tool", False) or st.get("dia", 0) <= 0 or stop_z <= 0.5
        pin_col = C_BAD if bad else C_PIN
        box(u_pin - r, stop_z, u_pin + r, stop_z + 22, pin_col)              # pin
        box(u_pin - 9, stop_z + 22, u_pin + 9, stop_z + 30, QColor("#9a9e9f"))   # collet nut
        box(u_pin - 18, stop_z + 30, u_pin + 18, z_hi + 5, QColor("#5a5f61"))    # spindle nose

        p.setFont(_font(11))
        dash = QPen(C_DIM, 1.2, Qt.DashLine)
        p.setPen(dash)
        p.drawLine(QPointF(8, zy(0)), QPointF(w - 8, zy(0)))
        p.setPen(QPen(pin_col, 1.2, Qt.DashLine))
        p.drawLine(QPointF(8, zy(stop_z)), QPointF(w - 8, zy(stop_z)))
        p.setPen(C_DIM)
        p.drawText(QRectF(10, zy(0) + 1, 260, 16), Qt.AlignLeft, "Z0 = PARALLEL TOP")
        p.setPen(pin_col)
        p.drawText(QRectF(w - 270, zy(stop_z) - 17, 260, 16), Qt.AlignRight,
                   "PIN TIP  Z {:.3f}".format(stop_z))
        p.setPen(C_DIM)
        p.drawText(QRectF(10, 4, w - 20, 16), Qt.AlignRight,
                   "SIDE VIEW - +{} TO THE RIGHT".format(axis))
        if stop_z <= 0.5:
            p.setPen(C_BAD)
            p.setFont(_font(13))
            p.drawText(QRectF(10, 4, w - 20, 18), Qt.AlignLeft, "PIN TIP AT OR BELOW Z0 - CHECK STOP Z")
        p.end()


class UserTab(QWidget):
    def __init__(self, parent=None):
        super(UserTab, self).__init__(parent)
        here = os.path.dirname(os.path.abspath(__file__))
        uic.loadUi(os.path.join(here, "vise_stop.ui"), self)
        self.setObjectName("VISE")
        if os.path.exists(PB_FONT_PATH):
            QFontDatabase.addApplicationFont(PB_FONT_PATH)
        try:
            with open(os.path.join(here, "vise_stop.qss"), "r", encoding="utf-8") as fh:
                self.setStyleSheet(fh.read())
        except OSError as exc:
            LOG.warning("vise_stop: no stylesheet: %s", exc)
        self.setAttribute(Qt.WA_StyledBackground, True)

        try:
            self._cmd = linuxcnc.command()
            self._stat = linuxcnc.stat()
        except Exception as exc:
            LOG.error("vise_stop: linuxcnc init failed: %s", exc)
            self._cmd = None
            self._stat = None

        self._vals = dict(DEFAULTS)
        self._vals.update({k: v for k, v in self._read_var().items() if k in VISE_PARAMS})
        self._pending = None  # "go" / "retract" while an MDI is running
        self._loading = True

        self._build_ui()
        self._load_widgets()
        self._loading = False
        self._refresh_readout()

        self._timer = QTimer(self)
        self._timer.setInterval(POLL_MS)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    # ------------------------------------------------------------------ UI
    def _card(self, name, title):
        card = QFrame()
        card.setObjectName(name)
        card.setProperty("card", True)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 10, 16, 14)
        lay.setSpacing(10)
        lbl = QLabel(title)
        lbl.setObjectName("cardTitle")
        lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(lbl)
        return card, lay

    def _toggle_pair(self, texts):
        group = QButtonGroup(self)
        group.setExclusive(True)
        row = QHBoxLayout()
        row.setSpacing(8)
        buttons = []
        for i, text in enumerate(texts):
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setObjectName("toggle")
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            group.addButton(btn, i)
            row.addWidget(btn)
            buttons.append(btn)
        return group, row, buttons

    def _spin(self, lo, hi, decimals=3):
        spin = QDoubleSpinBox()
        spin.setRange(lo, hi)
        spin.setDecimals(decimals)
        spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        spin.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        spin.setKeyboardTracking(False)
        spin.setFixedHeight(44)
        spin.setMinimumWidth(150)
        return spin

    def _field_label(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("fieldLabel")
        return lbl

    def _build_ui(self):
        root = self.layout()

        # header
        header = QFrame()
        header.setObjectName("headerBar")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(14, 4, 14, 4)
        title = QLabel("VISE STOP")
        title.setObjectName("lblTitle")
        sub = QLabel("SPINDLE TOOL AS A HARD STOP - SAME WCS EVERY PART")
        sub.setObjectName("lblSubtitle")
        hl.addWidget(title)
        hl.addSpacing(14)
        hl.addWidget(sub)
        hl.addStretch(1)
        self.pillTool = QLabel("NO TOOL")
        self.pillTool.setObjectName("pill")
        self.pillHomed = QLabel("NOT HOMED")
        self.pillHomed.setObjectName("pill")
        hl.addWidget(self.pillTool)
        hl.addWidget(self.pillHomed)
        root.addWidget(header)

        cards = QHBoxLayout()
        cards.setSpacing(8)

        # --- SETUP (once per vise mount)
        setup, sl = self._card("setupCard", "SETUP - ONCE PER VISE MOUNT")
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        self.grpAxis, axis_row, _ = self._toggle_pair(["X", "Y"])
        grid.addWidget(self._field_label("ALONG THE JAWS"), 0, 0)
        grid.addLayout(axis_row, 0, 1)

        self.grpSide, side_row, self.sideButtons = self._toggle_pair(["PART +X", "PART -X"])
        grid.addWidget(self._field_label("PART SIDE OF STOP"), 1, 0)
        grid.addLayout(side_row, 1, 1)

        self.cmbWcs = QComboBox()
        self.cmbWcs.addItems(WCS_NAMES)
        self.cmbWcs.setFixedHeight(44)
        grid.addWidget(self._field_label("VISE WCS"), 2, 0)
        grid.addWidget(self.cmbWcs, 2, 1)

        self.spnStopZ = self._spin(-200.0, 200.0)
        grid.addWidget(self._field_label("STOP Z (TIP, VISE WCS)"), 3, 0)
        grid.addWidget(self.spnStopZ, 3, 1)

        self.lblStop = QLabel("NOT CAPTURED")
        self.lblStop.setObjectName("value")
        self.btnCapture = QPushButton("CAPTURE STOP")
        self.btnCapture.setObjectName("btnCapture")
        cap_row = QHBoxLayout()
        cap_row.addWidget(self.lblStop, 1)
        cap_row.addWidget(self.btnCapture)
        grid.addWidget(self._field_label("STOP POSITION (G53)"), 4, 0)
        grid.addLayout(cap_row, 4, 1)
        self.grpMode, mode_row, _ = self._toggle_pair(["PART EDGE", "PART CENTER"])
        grid.addWidget(self._field_label("WCS ORIGIN AT"), 5, 0)
        grid.addLayout(mode_row, 5, 1)
        self.spnLength = self._spin(0.0, 1000.0)
        grid.addWidget(self._field_label("PART LENGTH (CENTER ONLY)"), 6, 0)
        grid.addWidget(self.spnLength, 6, 1)
        grid.setColumnStretch(1, 1)
        sl.addLayout(grid)
        sl.addStretch(1)
        cards.addWidget(setup, 5)

        # --- PREVIEW: what GO TO STOP will do
        preview, pl = self._card("originCard", "WHAT GO TO STOP DOES")
        self.viewTop = ViseTopView()
        self.viewSide = ViseSideView()
        pl.addWidget(self.viewTop, 3)
        pl.addWidget(self.viewSide, 2)
        org_row = QHBoxLayout()
        self.lblOrigin = QLabel("-")
        self.lblOrigin.setObjectName("bigValue")
        self.lblFormula = QLabel("")
        self.lblFormula.setObjectName("hint")
        self.lblFormula.setWordWrap(True)
        org_row.addWidget(self.lblOrigin)
        org_row.addSpacing(12)
        org_row.addWidget(self.lblFormula, 1)
        pl.addLayout(org_row)
        cards.addWidget(preview, 7)

        # --- RUN (every part)
        run, rl = self._card("runCard", "EVERY PART")
        steps = QLabel(
            "1  LOAD THE STOP PIN (M600)\n"
            "2  GO TO STOP\n"
            "3  SLIDE PART AGAINST PIN - CLAMP\n"
            "4  RETRACT - LOAD TOOL - RUN"
        )
        steps.setObjectName("steps")
        rl.addWidget(steps)
        self.btnGo = QPushButton("GO TO STOP")
        self.btnGo.setObjectName("btnGo")
        self.btnGo.setMinimumHeight(70)
        rl.addWidget(self.btnGo)
        self.btnRetract = QPushButton("RETRACT")
        self.btnRetract.setObjectName("btnRetract")
        self.btnRetract.setMinimumHeight(56)
        rl.addWidget(self.btnRetract)
        rl.addStretch(1)
        cards.addWidget(run, 3)

        root.addLayout(cards, 1)

        self.lblStatus = QLabel("")
        self.lblStatus.setObjectName("lblStatus")
        root.addWidget(self.lblStatus)

        self.grpAxis.buttonClicked.connect(self._on_axis)
        self.grpSide.buttonClicked.connect(self._on_edit)
        self.grpMode.buttonClicked.connect(self._on_edit)
        self.cmbWcs.currentIndexChanged.connect(self._on_edit)
        self.spnStopZ.valueChanged.connect(self._on_edit)
        self.spnLength.valueChanged.connect(self._on_edit)
        self.btnCapture.clicked.connect(self._capture_stop)
        self.btnGo.clicked.connect(self._go)
        self.btnRetract.clicked.connect(self._retract)
        self.viewTop.sideClicked.connect(self._on_view_side)

    def _load_widgets(self):
        v = self._vals
        self.grpAxis.button(1 if v[P_AXIS] >= 0.5 else 0).setChecked(True)
        self.grpSide.button(1 if v[P_SIDE] < 0 else 0).setChecked(True)
        self.grpMode.button(1 if v[P_MODE] >= 0.5 else 0).setChecked(True)
        wcs = int(round(v[P_WCS]))
        self.cmbWcs.setCurrentIndex(min(max(wcs, 1), 6) - 1)
        self.spnStopZ.setValue(v[P_STOP_Z])
        self.spnLength.setValue(v[P_LENGTH])
        self._relabel_side()

    # ------------------------------------------------------------ values
    def _axis_name(self):
        return "Y" if self.grpAxis.checkedId() == 1 else "X"

    def _relabel_side(self):
        axis = self._axis_name()
        self.sideButtons[0].setText("PART +" + axis)
        self.sideButtons[1].setText("PART -" + axis)

    def _collect(self):
        v = self._vals
        v[P_AXIS] = float(max(self.grpAxis.checkedId(), 0))
        v[P_SIDE] = -1.0 if self.grpSide.checkedId() == 1 else 1.0
        v[P_MODE] = float(max(self.grpMode.checkedId(), 0))
        v[P_WCS] = float(self.cmbWcs.currentIndex() + 1)
        v[P_STOP_Z] = float(self.spnStopZ.value())
        v[P_LENGTH] = float(self.spnLength.value())
        return v

    def _on_view_side(self, side):
        self.grpSide.button(1 if side < 0 else 0).setChecked(True)
        self._on_edit()

    def _on_axis(self, *_):
        self._relabel_side()
        self._on_edit()

    def _on_edit(self, *_):
        if self._loading:
            return
        self._collect()
        self.spnLength.setEnabled(self._vals[P_MODE] >= 0.5)
        self._write_var(self._vals)
        self._refresh_readout()

    def _tool(self):
        """(tool number, diameter) of the tool in the spindle, or (0, 0)."""
        if self._stat is None:
            return 0, 0.0
        tn = int(self._stat.tool_in_spindle)
        if tn <= 0:
            return 0, 0.0
        for entry in self._stat.tool_table:
            if int(entry.id) == tn:
                return tn, float(entry.diameter)
        return tn, 0.0

    def _origin(self, dia):
        v = self._vals
        if abs(v[P_STOP]) < 1e-4 or dia <= 0:
            return None
        origin = v[P_STOP] + v[P_SIDE] * dia / 2.0
        if v[P_MODE] >= 0.5:
            if v[P_LENGTH] <= 0:
                return None
            origin += v[P_SIDE] * v[P_LENGTH] / 2.0
        return origin

    def _refresh_readout(self):
        v = self._vals
        axis = self._axis_name()
        wcs = WCS_NAMES[int(v[P_WCS]) - 1]
        self.spnLength.setEnabled(v[P_MODE] >= 0.5)
        tn, tdia = self._tool()
        probe = self._stat is not None and tn == PROBE_TOOL
        view = dict(axis=int(v[P_AXIS] >= 0.5), side=1 if v[P_SIDE] > 0 else -1,
                    dia=0.0 if probe else tdia, mode=int(v[P_MODE] >= 0.5),
                    length=v[P_LENGTH], stop_z=v[P_STOP_Z], wcs=wcs, tool=tn,
                    bad_tool=probe)
        self.viewTop.set_state(**view)
        self.viewSide.set_state(**view)
        if abs(v[P_STOP]) < 1e-4:
            self.lblStop.setText("NOT CAPTURED")
        else:
            self.lblStop.setText("{} {:.4f}".format(axis, v[P_STOP]))
        _, dia = self._tool()
        origin = self._origin(dia)
        if origin is None:
            self.lblOrigin.setText("{} {}  -".format(wcs, axis))
            if abs(v[P_STOP]) < 1e-4:
                self.lblFormula.setText("CAPTURE THE STOP POSITION FIRST")
            elif dia <= 0:
                self.lblFormula.setText("LOAD THE STOP PIN - NEEDS A DIAMETER IN THE TOOL TABLE")
            else:
                self.lblFormula.setText("ENTER THE PART LENGTH")
            return
        self.lblOrigin.setText("{} {}  {:.4f}".format(wcs, axis, origin))
        sign = "+" if v[P_SIDE] > 0 else "-"
        text = "STOP {:.4f} {} PIN R {:.4f}".format(v[P_STOP], sign, dia / 2.0)
        if v[P_MODE] >= 0.5:
            text += " {} HALF LENGTH {:.4f}".format(sign, v[P_LENGTH] / 2.0)
        self.lblFormula.setText(text + "  (MACHINE)")

    # ---------------------------------------------------------- linuxcnc
    def _ready(self, need_homed=True):
        if self._cmd is None or self._stat is None:
            self._set_status("ERROR: LINUXCNC UNAVAILABLE")
            return False
        self._stat.poll()
        if self._stat.estop:
            self._set_status("BLOCKED: E-STOP")
            return False
        if not self._stat.enabled:
            self._set_status("BLOCKED: MACHINE OFF")
            return False
        if self._stat.interp_state != linuxcnc.INTERP_IDLE:
            self._set_status("BLOCKED: MACHINE BUSY")
            return False
        if need_homed and not all(self._stat.homed[:3]):
            self._set_status("BLOCKED: HOME X Y Z FIRST")
            return False
        return True

    def _push_params(self):
        """Write #5580-#5587 to the interpreter and linuxcnc.var."""
        self._collect()
        try:
            self._cmd.mode(linuxcnc.MODE_MDI)
            self._cmd.wait_complete()
            for num in VISE_PARAMS:
                self._cmd.mdi("#{}={:.6f}".format(num, self._vals[num]))
                self._cmd.wait_complete()
        except Exception as exc:
            LOG.error("vise_stop: param push failed: %s", exc)
            self._set_status("ERROR: " + str(exc))
            return False
        return self._write_var(self._vals)

    def _capture_stop(self, *_):
        if not self._ready():
            return
        axis = 1 if self._vals[P_AXIS] >= 0.5 else 0
        self._vals[P_STOP] = float(self._stat.actual_position[axis])
        if self._push_params():
            self._refresh_readout()
            self._set_status("STOP CAPTURED: {} {:.4f}".format(self._axis_name(), self._vals[P_STOP]))

    def _go(self, *_):
        if not self._ready():
            return
        tn, dia = self._tool()
        if tn == PROBE_TOOL:
            self._set_status("BLOCKED: TOUCH PROBE LOADED - LOAD THE STOP PIN")
            return
        if self._origin(dia) is None:
            self._refresh_readout()
            self._set_status("BLOCKED: " + self.lblFormula.text())
            return
        if not self._push_params():
            return
        self._issue(GO_MDI, "go", "MOVING TO STOP...")

    def _retract(self, *_):
        if not self._ready(need_homed=False):
            return
        self._issue(RETRACT_MDI, "retract", "RETRACTING...")

    def _issue(self, mdi, tag, text):
        try:
            self._cmd.mode(linuxcnc.MODE_MDI)
            self._cmd.wait_complete()
            self._cmd.mdi(mdi)
            self._pending = tag
            self._set_status(text)
        except Exception as exc:
            LOG.error("vise_stop: %s failed: %s", mdi, exc)
            self._set_status("ERROR: " + str(exc))

    def _poll(self):
        if self._stat is None or not self.isVisible() and self._pending is None:
            return
        try:
            self._stat.poll()
        except Exception:
            return
        tn, dia = self._tool()
        self.pillTool.setText("T{}  DIA {:.4f}".format(tn, dia) if tn > 0 else "NO TOOL")
        homed = all(self._stat.homed[:3])
        self.pillHomed.setText("HOMED" if homed else "NOT HOMED")
        self.pillHomed.setProperty("state", "on" if homed else "warn")
        self.pillHomed.style().unpolish(self.pillHomed)
        self.pillHomed.style().polish(self.pillHomed)
        self._refresh_readout()

        if self._pending and self._stat.interp_state == linuxcnc.INTERP_IDLE:
            tag, self._pending = self._pending, None
            z_mach = float(self._stat.actual_position[2])
            if tag == "go":
                if z_mach > -1.0:
                    self._set_status("STOPPED BEFORE THE STOP - SEE THE ERROR MESSAGE")
                else:
                    self._set_status(
                        "AT STOP - SLIDE THE PART AGAINST THE PIN, CLAMP, THEN RETRACT")
            else:
                self._set_status("RETRACTED - LOAD YOUR TOOL AND RUN")

    def _set_status(self, text):
        self.lblStatus.setText(text)

    # ---------------------------------------------------------- var file
    def _read_var(self):
        values = {}
        try:
            with open(VAR_FILE, "r", encoding="utf-8") as fh:
                for line in fh:
                    parts = line.split()
                    if len(parts) >= 2 and not parts[0].startswith(";"):
                        try:
                            values[int(parts[0])] = float(parts[1])
                        except ValueError:
                            pass
        except OSError as exc:
            LOG.warning("vise_stop: cannot read %s: %s", VAR_FILE, exc)
        return values

    def _write_var(self, updates):
        """Merge into linuxcnc.var, sorted ascending (LinuxCNC refuses unsorted files)."""
        values = self._read_var()
        values.update({k: updates[k] for k in VISE_PARAMS if k in updates})
        comments = []
        try:
            with open(VAR_FILE, "r", encoding="utf-8") as fh:
                comments = [l if l.endswith("\n") else l + "\n"
                            for l in fh if l.strip().startswith(";")]
        except OSError:
            pass
        try:
            with open(VAR_FILE, "w", encoding="utf-8") as fh:
                fh.writelines(comments)
                for num in sorted(values):
                    fh.write("{}\t{:.6f}\n".format(num, values[num]))
            return True
        except OSError as exc:
            LOG.error("vise_stop: cannot write %s: %s", VAR_FILE, exc)
            self._set_status("ERROR: CANNOT WRITE LINUXCNC.VAR")
            return False
