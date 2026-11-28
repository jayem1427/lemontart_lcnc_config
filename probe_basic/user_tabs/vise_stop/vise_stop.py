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
P_AXIS, P_SIDE, P_LENGTH, P_WCS = 5580, 5581, 5585, 5586
VISE_PARAMS = (P_AXIS, P_SIDE, P_LENGTH, P_WCS)
# Default view: jaws along Y, pin at the back (+Y side, away from the operator)
# = vise_Y_neg.png. REVERT: was {P_AXIS: 0.0, P_SIDE: 1.0} (jaws along X, pin on -X).
DEFAULTS = {P_AXIS: 1.0, P_SIDE: -1.0, P_LENGTH: 0.0, P_WCS: 2.0}
# Set-and-forget, edited in linuxcnc.var only (the tab never writes them):
# 5583 pin depth below the vise WCS Z0, 5587 spindle-nose clearance above it.
P_DEPTH, P_NOSE_CLR = 5583, 5587
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
        w, h = self.width(), self.height()
        pm = self._pixmap(self._name())
        if not pm.isNull():
            k = min(w / float(pm.width()), h / float(pm.height()))
            iw, ih = pm.width() * k, pm.height() * k
            self._img_rect = QRectF((w - iw) / 2.0, (h - ih) / 2.0, iw, ih)
            p.drawPixmap(self._img_rect, pm, QRectF(pm.rect()))
        else:
            self._img_rect = QRectF()
            p.setPen(C_DIM)
            p.setFont(_font(14))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, "IMAGES MISSING: " + IMG_DIR)
        if self.st.get("bad", False):
            p.setPen(QPen(C_BAD, 3))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(1.5, 1.5, w - 3, h - 3), 4, 4)
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
        var = self._read_var()  # set-and-forget values: read once, edit in linuxcnc.var
        self._depth = var.get(P_DEPTH, 0.0)
        self._nose_clr = var.get(P_NOSE_CLR, 0.0)
        self._action_msg = ""
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
    def _panel(self, title):
        """Probe Basic style panel: title strip on top, body below."""
        panel = QFrame()
        panel.setObjectName("panel")
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        lbl = QLabel(title)
        lbl.setObjectName("panelTitle")
        outer.addWidget(lbl)
        body = QVBoxLayout()
        body.setContentsMargins(14, 12, 14, 12)
        body.setSpacing(10)
        outer.addLayout(body, 1)
        return panel, body

    def _toggle_pair(self, texts):
        group = QButtonGroup(self)
        group.setExclusive(True)
        row = QHBoxLayout()
        row.setSpacing(6)
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
        spin.setFixedHeight(40)
        return spin

    def _field_label(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("fieldLabel")
        return lbl

    def _build_ui(self):
        root = self.layout()
        panels = QHBoxLayout()
        panels.setSpacing(8)

        # --- left: everything you touch
        left, ll = self._panel("VISE STOP")
        left.setFixedWidth(620)
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(9)

        self.grpAxis, axis_row, _ = self._toggle_pair(["X", "Y"])
        grid.addWidget(self._field_label("JAW AXIS"), 0, 0)
        grid.addLayout(axis_row, 0, 1)

        self.cmbWcs = QComboBox()
        self.cmbWcs.addItems(WCS_NAMES)
        self.cmbWcs.setFixedHeight(40)
        grid.addWidget(self._field_label("VISE WCS"), 1, 0)
        grid.addWidget(self.cmbWcs, 1, 1)

        sep = QFrame()
        sep.setObjectName("sep")
        sep.setFixedHeight(2)
        grid.addWidget(sep, 2, 0, 1, 2)

        self.spnLength = self._spin(0.0, 1000.0)
        grid.addWidget(self._field_label("PART LENGTH"), 3, 0)
        grid.addWidget(self.spnLength, 3, 1)

        self.grpSide, side_row, self.sideButtons = self._toggle_pair(["-X", "+X"])
        grid.addWidget(self._field_label("PIN SIDE"), 4, 0)
        grid.addLayout(side_row, 4, 1)
        grid.setColumnStretch(1, 1)
        ll.addLayout(grid)

        # DRO-style readout of where the pin parks (vise WCS)
        dro = QFrame()
        dro.setObjectName("dro")
        dl = QGridLayout(dro)
        dl.setContentsMargins(12, 6, 12, 6)
        dl.setVerticalSpacing(0)
        self.droAxis, self.droVal = [], []
        for row in range(3):
            ax = QLabel("")
            ax.setObjectName("droAxis")
            val = QLabel("")
            val.setObjectName("droValue")
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            dl.addWidget(ax, row, 0)
            dl.addWidget(val, row, 1)
            self.droAxis.append(ax)
            self.droVal.append(val)
        self.droMsg = QLabel("")
        self.droMsg.setObjectName("droMsg")
        self.droMsg.setWordWrap(True)
        dl.addWidget(self.droMsg, 3, 0, 1, 2)
        dl.setColumnStretch(1, 1)
        ll.addWidget(dro)

        ll.addStretch(1)
        self.lblStatus = QLabel("")
        self.lblStatus.setObjectName("lblStatus")
        self.lblStatus.setWordWrap(True)
        ll.addWidget(self.lblStatus)

        acts = QHBoxLayout()
        acts.setSpacing(8)
        self.btnGo = QPushButton("GO TO STOP")
        self.btnGo.setObjectName("btnGo")
        self.btnGo.setMinimumHeight(72)
        self.btnRetract = QPushButton("RETRACT")
        self.btnRetract.setObjectName("btnRetract")
        self.btnRetract.setMinimumHeight(72)
        acts.addWidget(self.btnGo, 3)
        acts.addWidget(self.btnRetract, 2)
        ll.addLayout(acts)
        panels.addWidget(left)

        # --- right: the picture (tap a side to put the pin there)
        right, rl = self._panel("PIN POSITION")
        self.viewTop = ViseRenderView()
        rl.addWidget(self.viewTop, 1)
        panels.addWidget(right, 1)

        root.addLayout(panels, 1)

        self.grpAxis.buttonClicked.connect(self._on_axis)
        self.grpSide.buttonClicked.connect(self._on_edit)
        self.cmbWcs.currentIndexChanged.connect(self._on_edit)
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
        self.spnLength.setValue(v[P_LENGTH])
        self._relabel_side()

    # ------------------------------------------------------------ values
    def _axis_name(self):
        return "Y" if self.grpAxis.checkedId() == 1 else "X"

    def _relabel_side(self):
        axis = self._axis_name()
        self.sideButtons[0].setText("-" + axis)
        self.sideButtons[1].setText("+" + axis)

    def _collect(self):
        v = self._vals
        v[P_AXIS] = float(max(self.grpAxis.checkedId(), 0))
        v[P_SIDE] = -1.0 if self.grpSide.checkedId() == 1 else 1.0
        v[P_WCS] = float(self.cmbWcs.currentIndex() + 1)
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
        self._action_msg = ""
        self._refresh_readout()

    def _tool(self):
        """(tool number, diameter, length offset) of the tool in the spindle."""
        if self._stat is None:
            return 0, 0.0, 0.0
        tn = int(self._stat.tool_in_spindle)
        if tn <= 0:
            return 0, 0.0, 0.0
        for entry in self._stat.tool_table:
            if int(entry.id) == tn:
                return tn, float(entry.diameter), float(entry.zoffset)
        return tn, 0.0, 0.0

    def _pin_pos(self, dia):
        """Pin center along the jaws in the vise WCS, or None if it can't be worked out."""
        v = self._vals
        if dia <= 0 or v[P_LENGTH] <= 0:
            return None
        return -v[P_SIDE] * (v[P_LENGTH] / 2.0 + dia / 2.0)

    def _why_not(self, tn, dia, tlen=None):
        if tn == PROBE_TOOL:
            return "TOUCH PROBE LOADED - LOAD THE STOP PIN"
        if tn <= 0:
            return "LOAD THE STOP PIN (M600)"
        if dia <= 0:
            return "T{} HAS NO DIAMETER IN THE TOOL TABLE".format(tn)
        if self._vals[P_LENGTH] <= 0:
            return "ENTER THE PART LENGTH"
        if self._depth <= 0 or self._nose_clr <= 0:
            return "#5583 / #5587 NOT SET IN LINUXCNC.VAR"
        # Tool lengths are measured from the spindle nose (#3010): length = stickout.
        if tlen is not None and tlen - self._depth < self._nose_clr:
            return "T{} TOO SHORT - SPINDLE NOSE WOULD COME WITHIN {:g} MM OF {} Z0".format(
                tn, self._nose_clr, WCS_NAMES[int(self._vals[P_WCS]) - 1])
        return ""

    def _refresh_readout(self):
        v = self._vals
        axis = self._axis_name()
        clamp = "X" if axis == "Y" else "Y"
        wcs = WCS_NAMES[int(v[P_WCS]) - 1]
        tn, tdia, tlen = self._tool()
        probe = self._stat is not None and tn == PROBE_TOOL
        self.viewTop.set_state(axis=int(v[P_AXIS] >= 0.5), side=1 if v[P_SIDE] > 0 else -1,
                               bad=probe or (tn > 0 and tdia <= 0))
        why = self._why_not(tn, tdia, tlen)
        pin = None if why else self._pin_pos(tdia)
        rows = [(axis, pin), (clamp, 0.0), ("Z", -self._depth)] if pin is not None else []
        for i in range(3):
            self.droAxis[i].setText("{} {}".format(wcs, rows[i][0]) if rows else "")
            self.droVal[i].setText("{:.3f}".format(rows[i][1]) if rows else "")
            self.droAxis[i].setVisible(bool(rows))
            self.droVal[i].setVisible(bool(rows))
        self.droMsg.setText(why)
        self.droMsg.setVisible(bool(why))
        self._show_status()

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
        tn, dia, tlen = self._tool()
        why = self._why_not(tn, dia, tlen)
        if why:
            self._set_status("BLOCKED: " + why)
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
        """Result of the last button press; cleared by the next edit."""
        self._action_msg = text
        self._show_status()

    def _show_status(self):
        text = self._action_msg
        if not text and self._stat is not None and self._pending is None:
            try:
                if self._stat.estop:
                    text = "E-STOP"
                elif not self._stat.enabled:
                    text = "MACHINE OFF"
                elif not all(self._stat.homed[:3]):
                    text = "HOME X Y Z FIRST"
            except Exception:
                pass
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
