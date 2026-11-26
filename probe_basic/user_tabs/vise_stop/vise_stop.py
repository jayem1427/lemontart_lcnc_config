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

import json
import os

import linuxcnc

from qtpy import uic
from qtpy.QtCore import QRectF, Qt, QTimer, Signal
from qtpy.QtGui import QColor, QFont, QFontDatabase, QPainter, QPen, QPixmap
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

# 5582, 5584 and 5587 belonged to the old "captured stop" design and are unused.
P_AXIS, P_SIDE, P_STOP_Z, P_LENGTH, P_WCS = 5580, 5581, 5583, 5585, 5586
VISE_PARAMS = (P_AXIS, P_SIDE, P_STOP_Z, P_LENGTH, P_WCS)
DEFAULTS = {P_AXIS: 0.0, P_SIDE: 1.0, P_STOP_Z: 5.0, P_LENGTH: 0.0, P_WCS: 2.0}
PROBE_TOOL = 99  # #3014
WCS_NAMES = ["G54", "G55", "G56", "G57", "G58", "G59"]
POLL_MS = 250

GO_MDI = "o<vise_stop_go> call"
RETRACT_MDI = "o<vise_stop_retract> call"


# ---------------------------------------------------------------- graphics
# Rendered images of the H67 (tools/vise_render/make_images.py), one per
# jaw axis / pin side.  The live numbers are painted on top.
IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")

C_PIN = QColor("#fcaf3e")
C_BAD = QColor("#ef2929")
C_ORIGIN = QColor("#73d216")
C_TEXT = QColor(238, 238, 236)
C_DIM = QColor("#9a9e9f")


def _font(pt):
    f = QFont("BebasKai")
    f.setPointSizeF(pt)
    return f


class ViseRenderView(QWidget):
    """Shows the render matching the settings. Tap a side of the vise to put the pin there."""
    sideClicked = Signal(int)

    def __init__(self, parent=None):
        super(ViseRenderView, self).__init__(parent)
        self.st = {}
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(420, 300)
        self.setCursor(Qt.PointingHandCursor)
        self._cache = {}
        self._img_rect = QRectF()
        try:
            with open(os.path.join(IMG_DIR, "meta.json"), "r", encoding="utf-8") as fh:
                self._meta = json.load(fh)
        except (OSError, ValueError) as exc:
            LOG.warning("vise_stop: no image meta: %s", exc)
            self._meta = {"size": [720, 400], "images": {}}

    def set_state(self, **st):
        if st != self.st:
            self.st = st
            self.update()

    def _name(self):
        st = self.st
        return "vise_{}_{}.png".format("Y" if st.get("axis") == 1 else "X",
                                       "neg" if st.get("side", 1) < 0 else "pos")

    def _pixmap(self, name):
        if name not in self._cache:
            self._cache[name] = QPixmap(os.path.join(IMG_DIR, name))
        return self._cache[name]

    def mousePressEvent(self, ev):
        info = self._meta["images"].get(self._name())
        r = self._img_rect
        if not info or r.width() <= 0:
            return
        k = r.width() / float(self._meta["size"][0])
        cx = r.left() + info["center"][0] * k
        cy = r.top() + info["center"][1] * k
        du, dv = info["u_dir"]
        along = (ev.pos().x() - cx) * du + (ev.pos().y() - cy) * dv
        self.sideClicked.emit(1 if along > 0 else -1)

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        st = self.st
        w, h = self.width(), self.height()
        bad_tool = st.get("bad_tool", False) or st.get("dia", 0) <= 0
        low_z = st.get("stop_z", 5.0) <= 0.5
        bad = bad_tool or low_z

        pm = self._pixmap(self._name())
        top, bottom = 30, 30
        if not pm.isNull():
            avail_h = h - top - bottom
            k = min(w / float(pm.width()), avail_h / float(pm.height()))
            iw, ih = pm.width() * k, pm.height() * k
            self._img_rect = QRectF((w - iw) / 2.0, top + (avail_h - ih) / 2.0, iw, ih)
            p.drawPixmap(self._img_rect, pm, QRectF(pm.rect()))
        else:
            self._img_rect = QRectF()
            p.setPen(C_DIM)
            p.setFont(_font(14))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, "IMAGES MISSING: " + IMG_DIR)

        tool = st.get("tool", 0)
        if st.get("bad_tool"):
            pin_txt = "STOP PIN: PROBE LOADED"
        elif tool <= 0:
            pin_txt = "STOP PIN: NO TOOL LOADED"
        elif st.get("dia", 0) <= 0:
            pin_txt = "STOP PIN: T{} HAS NO DIAMETER".format(tool)
        else:
            pin_txt = "STOP PIN: T{}  DIA {:.3f}".format(tool, st.get("dia", 0))
        p.setFont(_font(14))
        p.setPen(C_BAD if bad_tool else C_PIN)
        p.drawText(QRectF(8, 2, w / 2.0, 26), Qt.AlignLeft | Qt.AlignVCenter, pin_txt)
        p.setPen(C_ORIGIN)
        p.drawText(QRectF(w / 2.0, 2, w / 2.0 - 8, 26), Qt.AlignRight | Qt.AlignVCenter,
                   "ORIGIN {}  X0 Y0 Z0".format(st.get("wcs", "G55")))
        p.setFont(_font(12))
        p.setPen(C_BAD if low_z else C_TEXT)
        z_txt = ("PIN TIP Z {:.3f} - AT OR BELOW Z0, WILL HIT THE PARALLELS".format(st.get("stop_z", 0))
                 if low_z else "PIN TIP Z {:.3f} ABOVE Z0 (PARALLEL TOP)".format(st.get("stop_z", 0)))
        p.drawText(QRectF(8, h - 28, w * 0.62, 26), Qt.AlignLeft | Qt.AlignVCenter, z_txt)
        p.setPen(C_DIM)
        p.drawText(QRectF(w * 0.55, h - 28, w * 0.45 - 8, 26), Qt.AlignRight | Qt.AlignVCenter,
                   "TAP A SIDE TO PUT THE PIN THERE")
        if bad:
            p.setPen(QPen(C_BAD, 3))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(1.5, 1.5, w - 3, h - 3), 6, 6)
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
        setup, sl = self._card("setupCard", "VISE - SET ONCE")
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        self.grpAxis, axis_row, _ = self._toggle_pair(["X", "Y"])
        grid.addWidget(self._field_label("JAWS RUN ALONG"), 0, 0)
        grid.addLayout(axis_row, 0, 1)

        self.cmbWcs = QComboBox()
        self.cmbWcs.addItems(WCS_NAMES)
        self.cmbWcs.setFixedHeight(44)
        grid.addWidget(self._field_label("VISE WCS (VISE CENTER)"), 1, 0)
        grid.addWidget(self.cmbWcs, 1, 1)

        self.spnStopZ = self._spin(-200.0, 200.0)
        grid.addWidget(self._field_label("PIN TIP Z (VISE WCS)"), 2, 0)
        grid.addWidget(self.spnStopZ, 2, 1)

        part_title = QLabel("THIS PART")
        part_title.setObjectName("cardTitle")
        part_title.setAlignment(Qt.AlignCenter)
        grid.addWidget(part_title, 3, 0, 1, 2)

        self.spnLength = self._spin(0.0, 1000.0)
        grid.addWidget(self._field_label("PART LENGTH ALONG JAWS"), 4, 0)
        grid.addWidget(self.spnLength, 4, 1)

        self.grpSide, side_row, self.sideButtons = self._toggle_pair(["PIN ON -X", "PIN ON +X"])
        grid.addWidget(self._field_label("STOP PIN SIDE"), 5, 0)
        grid.addLayout(side_row, 5, 1)

        self.lblPin = QLabel("-")
        self.lblPin.setObjectName("value")
        grid.addWidget(self._field_label("PIN GOES TO"), 6, 0)
        grid.addWidget(self.lblPin, 6, 1)
        grid.setColumnStretch(1, 1)
        sl.addLayout(grid)
        sl.addStretch(1)
        cards.addWidget(setup, 5)

        # --- PREVIEW: what GO TO STOP will do
        preview, pl = self._card("originCard", "WHAT GO TO STOP DOES")
        self.viewTop = ViseRenderView()
        pl.addWidget(self.viewTop, 1)
        cards.addWidget(preview, 7)

        # --- RUN (every part)
        run, rl = self._card("runCard", "EVERY PART")
        steps = QLabel(
            "1  LOAD THE STOP PIN (M600)\n"
            "2  GO TO STOP\n"
            "3  PUSH PART AGAINST PIN - CLAMP\n"
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
        self.cmbWcs.currentIndexChanged.connect(self._on_edit)
        self.spnStopZ.valueChanged.connect(self._on_edit)
        self.spnLength.valueChanged.connect(self._on_edit)
        self.btnGo.clicked.connect(self._go)
        self.btnRetract.clicked.connect(self._retract)
        self.viewTop.sideClicked.connect(self._on_view_side)

    def _load_widgets(self):
        v = self._vals
        self.grpAxis.button(1 if v[P_AXIS] >= 0.5 else 0).setChecked(True)
        self.grpSide.button(1 if v[P_SIDE] < 0 else 0).setChecked(True)
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
        self.sideButtons[0].setText("PIN ON -" + axis)
        self.sideButtons[1].setText("PIN ON +" + axis)

    def _collect(self):
        v = self._vals
        v[P_AXIS] = float(max(self.grpAxis.checkedId(), 0))
        v[P_SIDE] = -1.0 if self.grpSide.checkedId() == 1 else 1.0
        v[P_WCS] = float(self.cmbWcs.currentIndex() + 1)
        v[P_STOP_Z] = float(self.spnStopZ.value())
        v[P_LENGTH] = float(self.spnLength.value())
        return v

    def _on_view_side(self, pin_side):
        # pin on the + side means the part sits toward - (#5581 = -1)
        self.grpSide.button(1 if pin_side > 0 else 0).setChecked(True)
        self._on_edit()

    def _on_axis(self, *_):
        self._relabel_side()
        self._on_edit()

    def _on_edit(self, *_):
        if self._loading:
            return
        self._collect()
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

    def _pin_pos(self, dia):
        """Pin center along the jaws in the vise WCS, or None if it can't be worked out."""
        v = self._vals
        if dia <= 0 or v[P_LENGTH] <= 0:
            return None
        return -v[P_SIDE] * (v[P_LENGTH] / 2.0 + dia / 2.0)

    def _why_not(self, tn, dia):
        if tn == PROBE_TOOL:
            return "TOUCH PROBE LOADED - LOAD THE STOP PIN"
        if tn <= 0:
            return "LOAD THE STOP PIN (M600)"
        if dia <= 0:
            return "T{} HAS NO DIAMETER IN THE TOOL TABLE".format(tn)
        if self._vals[P_LENGTH] <= 0:
            return "ENTER THE PART LENGTH"
        return ""

    def _refresh_readout(self):
        v = self._vals
        axis = self._axis_name()
        clamp = "X" if axis == "Y" else "Y"
        wcs = WCS_NAMES[int(v[P_WCS]) - 1]
        tn, tdia = self._tool()
        probe = self._stat is not None and tn == PROBE_TOOL
        view = dict(axis=int(v[P_AXIS] >= 0.5), side=1 if v[P_SIDE] > 0 else -1,
                    dia=0.0 if probe else tdia, length=v[P_LENGTH], stop_z=v[P_STOP_Z],
                    wcs=wcs, tool=tn, bad_tool=probe)
        self.viewTop.set_state(**view)
        pin = None if probe else self._pin_pos(tdia)
        if pin is None:
            self.lblPin.setText(self._why_not(tn, tdia))
        else:
            self.lblPin.setText("{} {}{:.3f} {}0".format(wcs, axis, pin, clamp))

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

    def _go(self, *_):
        if not self._ready():
            return
        tn, dia = self._tool()
        if tn == PROBE_TOOL:
            self._set_status("BLOCKED: TOUCH PROBE LOADED - LOAD THE STOP PIN")
            return
        if self._pin_pos(dia) is None:
            self._set_status("BLOCKED: " + self._why_not(tn, dia))
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
