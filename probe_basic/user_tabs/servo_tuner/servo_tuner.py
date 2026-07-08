import os
import sys

from qtpy import uic
from qtpy.QtCore import Qt
from qtpy.QtGui import QColor, QFont, QFontDatabase, QPalette
from qtpy.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from qtpyvcp.utilities import logger

LOG = logger.getLogger(__name__)

PB_FONT = "BebasKai"
PB_FONT_PATH = "/usr/share/fonts/truetype/BebasKai.ttf"

PYTHON_DIR = os.path.join(
    os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)),
    "python",
)
if PYTHON_DIR not in sys.path:
    sys.path.insert(0, PYTHON_DIR)

from a6_servo_tune import (  # noqa: E402
    AXES,
    AXIS_ORDER,
    NOTCH_LABELS,
    AxisTuneParams,
    apply_axis_params,
    delete_preset,
    list_presets,
    load_preset,
    read_axis_params,
    save_preset,
)

SLIDER_STEPS = 1000


class UserTab(QWidget):
    def __init__(self, parent=None):
        super(UserTab, self).__init__(parent)
        ui_file = os.path.splitext(os.path.basename(__file__))[0] + ".ui"
        here = os.path.dirname(os.path.abspath(__file__))
        uic.loadUi(os.path.join(here, ui_file), self)

        self.setObjectName("SERVO_TUNING")
        self._ensure_font()
        self._load_stylesheet(here)
        self._apply_panel_background()

        self._axis = "X"
        self._syncing = False
        self._param_widgets = {}

        self._build_ui()
        self._set_params_to_ui(AxisTuneParams())
        self._refresh_preset_list()

    def _ensure_font(self):
        if os.path.exists(PB_FONT_PATH):
            QFontDatabase.addApplicationFont(PB_FONT_PATH)
        self.setFont(QFont(PB_FONT))

    def _load_stylesheet(self, here):
        qss_path = os.path.join(here, "servo_tuner.qss")
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as handle:
                self.setStyleSheet(handle.read())

    def _apply_panel_background(self):
        panel = QColor(46, 52, 54)
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), panel)
        self.setPalette(palette)

    def _build_ui(self) -> None:
        root_layout = self.findChild(QVBoxLayout, "rootLayout")
        if root_layout is None:
            root_layout = QVBoxLayout(self)
            self.setLayout(root_layout)
        root_layout.setSpacing(8)

        root_layout.addWidget(self._build_header(), stretch=0)

        body = QHBoxLayout()
        body.setSpacing(12)
        body.addLayout(self._build_params_column(), stretch=3)
        body.addWidget(self._build_presets_panel(), stretch=1)
        root_layout.addLayout(body, stretch=1)

    def _build_header(self) -> QFrame:
        header = QFrame(self)
        header.setObjectName("headerBar")
        header.setAttribute(Qt.WA_StyledBackground, True)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(14, 8, 14, 8)

        title = QLabel("SERVO TUNING", header)
        title.setObjectName("lblTitle")
        layout.addWidget(title)
        layout.addStretch()

        self.status_label = QLabel("READY", header)
        self.status_label.setObjectName("lblStatus")
        self.status_label.setProperty("state", "ok")
        layout.addWidget(self.status_label)
        return header

    def _build_params_column(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(8)

        axis_row = QHBoxLayout()
        axis_row.addWidget(self._caption("AXIS"))
        self.axis_group = QButtonGroup(self)
        self.axis_buttons = {}
        for axis in AXIS_ORDER:
            btn = QPushButton(axis, self)
            btn.setObjectName("btnAxis")
            btn.setCheckable(True)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setMinimumWidth(44)
            self.axis_group.addButton(btn)
            btn.toggled.connect(
                lambda checked, ax=axis: self._on_axis_selected(ax, checked)
            )
            self.axis_buttons[axis] = btn
            axis_row.addWidget(btn)
        axis_row.addStretch()
        col.addLayout(axis_row)

        action_row = QHBoxLayout()
        self.read_button = QPushButton("READ FROM DRIVE", self)
        self.read_button.setFocusPolicy(Qt.NoFocus)
        self.read_button.clicked.connect(self._read_from_drive)
        action_row.addWidget(self.read_button)

        self.apply_button = QPushButton("APPLY TO DRIVE", self)
        self.apply_button.setObjectName("btnPrimary")
        self.apply_button.setFocusPolicy(Qt.NoFocus)
        self.apply_button.clicked.connect(self._apply_to_drive)
        action_row.addWidget(self.apply_button)

        self.defaults_button = QPushButton("RESET FORM", self)
        self.defaults_button.setFocusPolicy(Qt.NoFocus)
        self.defaults_button.clicked.connect(self._reset_form_defaults)
        action_row.addWidget(self.defaults_button)
        action_row.addStretch()
        col.addLayout(action_row)

        scroll = QScrollArea(self)
        scroll.setObjectName("paramScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_body = QWidget()
        scroll_body.setObjectName("paramScrollBody")
        scroll_layout = QVBoxLayout(scroll_body)
        scroll_layout.setSpacing(10)
        scroll_layout.setContentsMargins(0, 0, 4, 0)

        scroll_layout.addWidget(self._build_drive_group(scroll_body))
        scroll_layout.addWidget(self._build_hal_group(scroll_body))
        scroll_layout.addWidget(self._build_limits_group(scroll_body))
        scroll_layout.addStretch()

        scroll.setWidget(scroll_body)
        col.addWidget(scroll, stretch=1)

        self.message_label = QLabel(
            "Use Signal Logging tab with x_tuning.ngc to compare before/after.",
            self,
        )
        self.message_label.setObjectName("lblMessage")
        self.message_label.setWordWrap(True)
        col.addWidget(self.message_label)
        return col

    def _build_drive_group(self, parent: QWidget) -> QGroupBox:
        group = QGroupBox("DRIVE LOOP (C00 / C01)", parent)
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        self.manual_checkbox = QCheckBox("Manual gain mode (C00.04)", group)
        self.manual_checkbox.setChecked(True)
        self.manual_checkbox.toggled.connect(self._on_manual_toggled)
        layout.addWidget(self.manual_checkbox)
        self._param_widgets["manual_mode"] = self.manual_checkbox

        self._add_slider_param(
            layout,
            "inertia_ratio_pct",
            "Load inertia ratio (C00.06)",
            0.0,
            200.0,
            1.0,
            "%",
            "Typical range 70–130%",
        )
        self._add_slider_param(
            layout,
            "pos_gain_rad_s",
            "Position loop gain (C01.00)",
            5.0,
            60.0,
            0.5,
            "rad/s",
            "Higher = stiffer tracking",
        )
        self._add_slider_param(
            layout,
            "speed_gain_hz",
            "Speed loop gain (C01.01)",
            5.0,
            40.0,
            0.1,
            "Hz",
            "Primary noise / ringing lever — lower to soften",
        )
        self._add_slider_param(
            layout,
            "integral_ms",
            "Speed integral (C01.02)",
            5.0,
            80.0,
            0.01,
            "ms",
        )

        notch_row = QHBoxLayout()
        notch_label = QLabel("Adaptive notch (C01.30)", group)
        notch_label.setObjectName("lblParamName")
        notch_row.addWidget(notch_label)
        notch_row.addStretch()

        self.notch_combo = QComboBox(group)
        for value, label in sorted(NOTCH_LABELS.items()):
            self.notch_combo.addItem(f"{value} — {label}", value)
        self.notch_combo.currentIndexChanged.connect(self._on_notch_changed)
        notch_row.addWidget(self.notch_combo)
        layout.addLayout(notch_row)
        self._param_widgets["adaptive_notch"] = self.notch_combo
        return group

    def _build_hal_group(self, parent: QWidget) -> QGroupBox:
        group = QGroupBox("FEEDBACK COMPENSATION (HAL)", parent)
        layout = QVBoxLayout(group)
        self._add_slider_param(
            layout,
            "ferr_lag_ms",
            "Pipeline delay (ferr-lag.N)",
            0.0,
            10.0,
            0.1,
            "ms",
            "Advance feedback by vel_cmd × lag. Set 0 to disable.",
        )
        return group

    def _build_limits_group(self, parent: QWidget) -> QGroupBox:
        group = QGroupBox("FOLLOWING ERROR LIMIT (6065)", parent)
        layout = QVBoxLayout(group)
        self.fe_spin = QDoubleSpinBox(group)
        self.fe_spin.setDecimals(3)
        self.fe_spin.setRange(0.001, 5.0)
        self.fe_spin.setSingleStep(0.01)
        self.fe_spin.valueChanged.connect(self._on_fe_changed)

        row = QHBoxLayout()
        self.fe_label = QLabel("Max deviation", group)
        self.fe_label.setObjectName("lblParamName")
        row.addWidget(self.fe_label)
        row.addStretch()
        row.addWidget(self.fe_spin)
        self.fe_unit_label = QLabel("mm", group)
        self.fe_unit_label.setObjectName("lblParamHint")
        row.addWidget(self.fe_unit_label)
        layout.addLayout(row)
        self._param_widgets["following_error"] = self.fe_spin
        return group

    def _build_presets_panel(self) -> QGroupBox:
        group = QGroupBox("AXIS PRESETS", self)
        group.setObjectName("grpPresets")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        hint = QLabel(
            "Saved under config/tuning/presets/<axis>/*.json",
            group,
        )
        hint.setObjectName("lblParamHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.preset_list = QListWidget(group)
        self.preset_list.itemDoubleClicked.connect(
            lambda _item: self._load_selected_preset(apply=False)
        )
        layout.addWidget(self.preset_list, stretch=1)

        self.preset_name_edit = QLineEdit(group)
        self.preset_name_edit.setPlaceholderText("Preset name")
        layout.addWidget(self.preset_name_edit)

        self.preset_notes_edit = QTextEdit(group)
        self.preset_notes_edit.setPlaceholderText("Notes (optional)")
        self.preset_notes_edit.setMaximumHeight(72)
        layout.addWidget(self.preset_notes_edit)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("SAVE", group)
        save_btn.setObjectName("btnPrimary")
        save_btn.setFocusPolicy(Qt.NoFocus)
        save_btn.clicked.connect(self._save_preset)
        btn_row.addWidget(save_btn)

        load_btn = QPushButton("LOAD", group)
        load_btn.setFocusPolicy(Qt.NoFocus)
        load_btn.clicked.connect(lambda: self._load_selected_preset(apply=False))
        btn_row.addWidget(load_btn)
        layout.addLayout(btn_row)

        btn_row2 = QHBoxLayout()
        load_apply_btn = QPushButton("LOAD + APPLY", group)
        load_apply_btn.setFocusPolicy(Qt.NoFocus)
        load_apply_btn.clicked.connect(lambda: self._load_selected_preset(apply=True))
        btn_row2.addWidget(load_apply_btn)

        delete_btn = QPushButton("DELETE", group)
        delete_btn.setObjectName("btnDanger")
        delete_btn.setFocusPolicy(Qt.NoFocus)
        delete_btn.clicked.connect(self._delete_preset)
        btn_row2.addWidget(delete_btn)
        layout.addLayout(btn_row2)

        refresh_btn = QPushButton("REFRESH LIST", group)
        refresh_btn.setFocusPolicy(Qt.NoFocus)
        refresh_btn.clicked.connect(self._refresh_preset_list)
        layout.addWidget(refresh_btn)
        return group

    def _caption(self, text: str) -> QLabel:
        label = QLabel(text, self)
        label.setObjectName("lblCaption")
        return label

    def _add_slider_param(
        self,
        parent_layout: QVBoxLayout,
        key: str,
        title: str,
        vmin: float,
        vmax: float,
        step: float,
        unit: str,
        hint: str = "",
    ) -> None:
        row_widget = QWidget(self)
        row = QVBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        top = QHBoxLayout()
        name = QLabel(title, row_widget)
        name.setObjectName("lblParamName")
        top.addWidget(name)
        top.addStretch()

        spin = QDoubleSpinBox(row_widget)
        spin.setDecimals(max(0, len(str(step).split(".")[-1]) if "." in str(step) else 0))
        spin.setRange(vmin, vmax)
        spin.setSingleStep(step)
        spin.setSuffix(f" {unit}")
        top.addWidget(spin)
        row.addLayout(top)

        slider = QSlider(Qt.Horizontal, row_widget)
        slider.setRange(0, SLIDER_STEPS)
        row.addWidget(slider)

        if hint:
            hint_label = QLabel(hint, row_widget)
            hint_label.setObjectName("lblParamHint")
            hint_label.setWordWrap(True)
            row.addWidget(hint_label)

        def spin_to_slider(value: float) -> None:
            if self._syncing:
                return
            self._syncing = True
            if vmax <= vmin:
                slider.setValue(0)
            else:
                frac = (value - vmin) / (vmax - vmin)
                slider.setValue(int(round(frac * SLIDER_STEPS)))
            self._syncing = False

        def slider_to_spin(pos: int) -> None:
            if self._syncing:
                return
            self._syncing = True
            frac = pos / float(SLIDER_STEPS)
            spin.setValue(vmin + frac * (vmax - vmin))
            self._syncing = False

        spin.valueChanged.connect(spin_to_slider)
        slider.valueChanged.connect(slider_to_spin)
        spin_to_slider(spin.value())

        self._param_widgets[key] = spin
        parent_layout.addWidget(row_widget)

    def _set_status(self, text: str, state: str = "ok") -> None:
        self.status_label.setText(text)
        self.status_label.setProperty("state", state)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _set_busy(self, busy: bool) -> None:
        for widget in (
            self.read_button,
            self.apply_button,
            self.defaults_button,
            *self.axis_buttons.values(),
        ):
            widget.setEnabled(not busy)
        if busy:
            self._set_status("BUSY", "busy")

    def _on_axis_selected(self, axis: str, checked: bool) -> None:
        if self._syncing or not checked:
            return
        self._axis = axis
        linear = AXES[axis]["linear"]
        self.fe_unit_label.setText("mm" if linear else "deg")
        self._refresh_preset_list()
        self._set_status(f"AXIS {axis}", "ok")

    def _on_manual_toggled(self, _checked: bool) -> None:
        pass

    def _on_notch_changed(self, _index: int) -> None:
        pass

    def _on_fe_changed(self, _value: float) -> None:
        pass

    def _params_from_ui(self) -> AxisTuneParams:
        notch_combo = self._param_widgets["adaptive_notch"]
        return AxisTuneParams(
            manual_mode=self.manual_checkbox.isChecked(),
            inertia_ratio_pct=self._param_widgets["inertia_ratio_pct"].value(),
            pos_gain_rad_s=self._param_widgets["pos_gain_rad_s"].value(),
            speed_gain_hz=self._param_widgets["speed_gain_hz"].value(),
            integral_ms=self._param_widgets["integral_ms"].value(),
            adaptive_notch=int(notch_combo.currentData()),
            ferr_lag_ms=self._param_widgets["ferr_lag_ms"].value(),
            following_error=self.fe_spin.value(),
        )

    def _set_params_to_ui(self, params: AxisTuneParams) -> None:
        self._syncing = True
        self.manual_checkbox.setChecked(params.manual_mode)
        self._param_widgets["inertia_ratio_pct"].setValue(params.inertia_ratio_pct)
        self._param_widgets["pos_gain_rad_s"].setValue(params.pos_gain_rad_s)
        self._param_widgets["speed_gain_hz"].setValue(params.speed_gain_hz)
        self._param_widgets["integral_ms"].setValue(params.integral_ms)

        notch_idx = self.notch_combo.findData(params.adaptive_notch)
        if notch_idx >= 0:
            self.notch_combo.setCurrentIndex(notch_idx)

        self._param_widgets["ferr_lag_ms"].setValue(params.ferr_lag_ms)
        self.fe_spin.setValue(params.following_error)
        self._syncing = False

    def _reset_form_defaults(self) -> None:
        self._set_params_to_ui(AxisTuneParams())
        self.message_label.setText("Form reset to built-in defaults (not applied).")

    def _read_from_drive(self) -> None:
        self._set_busy(True)
        try:
            params = read_axis_params(self._axis)
            self._set_params_to_ui(params)
            self._set_status(f"READ {self._axis}", "ok")
            self.message_label.setText(
                f"Read live values from slave {AXES[self._axis]['slave']} "
                f"and ferr-lag.{AXES[self._axis]['joint']}."
            )
        except Exception as exc:
            LOG.exception("read_axis_params failed")
            self._set_status("ERROR", "error")
            self.message_label.setText(str(exc))
            QMessageBox.warning(self, "Read failed", str(exc))
        finally:
            self._set_busy(False)
            if self.status_label.text() == "BUSY":
                self._set_status(f"AXIS {self._axis}", "ok")

    def _apply_to_drive(self) -> None:
        params = self._params_from_ui()
        reply = QMessageBox.question(
            self,
            "Apply tuning",
            f"Write these parameters to axis {self._axis} "
            f"(slave {AXES[self._axis]['slave']})?\n\n"
            "SDO changes are RAM-only until stored in the drive.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self._set_busy(True)
        try:
            apply_axis_params(self._axis, params)
            self._set_status(f"APPLIED {self._axis}", "ok")
            self.message_label.setText(
                f"Applied to slave {AXES[self._axis]['slave']}. "
                "Log a move on the Signal Logging tab to verify."
            )
        except Exception as exc:
            LOG.exception("apply_axis_params failed")
            self._set_status("ERROR", "error")
            self.message_label.setText(str(exc))
            QMessageBox.warning(self, "Apply failed", str(exc))
        finally:
            self._set_busy(False)
            if self.status_label.text() == "BUSY":
                self._set_status(f"AXIS {self._axis}", "ok")

    def _refresh_preset_list(self) -> None:
        self.preset_list.clear()
        for name in list_presets(self._axis):
            self.preset_list.addItem(name)
        if self.preset_list.count() and self.preset_list.currentRow() < 0:
            self.preset_list.setCurrentRow(0)

    def _selected_preset_name(self) -> str:
        item = self.preset_list.currentItem()
        return item.text() if item is not None else ""

    def _save_preset(self) -> None:
        name = self.preset_name_edit.text().strip() or self._selected_preset_name()
        if not name:
            QMessageBox.information(self, "Save preset", "Enter a preset name.")
            return
        notes = self.preset_notes_edit.toPlainText().strip()
        try:
            path = save_preset(self._axis, name, self._params_from_ui(), notes=notes)
            self.preset_name_edit.setText(name)
            self._refresh_preset_list()
            items = self.preset_list.findItems(name, Qt.MatchExactly)
            if items:
                self.preset_list.setCurrentItem(items[0])
            self.message_label.setText(f"Saved preset: {path}")
        except Exception as exc:
            LOG.exception("save_preset failed")
            QMessageBox.warning(self, "Save failed", str(exc))

    def _load_selected_preset(self, apply: bool = False) -> None:
        name = self._selected_preset_name()
        if not name:
            QMessageBox.information(self, "Load preset", "Select a preset from the list.")
            return
        try:
            preset = load_preset(self._axis, name)
            self._set_params_to_ui(preset.params)
            self.preset_name_edit.setText(preset.name)
            self.preset_notes_edit.setPlainText(preset.notes)
            self.message_label.setText(f"Loaded preset {preset.name!r} for axis {self._axis}.")
            if apply:
                self._apply_to_drive()
        except Exception as exc:
            LOG.exception("load_preset failed")
            QMessageBox.warning(self, "Load failed", str(exc))

    def _delete_preset(self) -> None:
        name = self._selected_preset_name()
        if not name:
            return
        reply = QMessageBox.question(
            self,
            "Delete preset",
            f"Delete preset {name!r} for axis {self._axis}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            delete_preset(self._axis, name)
            self._refresh_preset_list()
            self.message_label.setText(f"Deleted preset {name!r}.")
        except Exception as exc:
            QMessageBox.warning(self, "Delete failed", str(exc))

    def showEvent(self, event):
        super().showEvent(event)
        if not any(btn.isChecked() for btn in self.axis_buttons.values()):
            self._syncing = True
            self.axis_buttons["X"].setChecked(True)
            self._syncing = False
