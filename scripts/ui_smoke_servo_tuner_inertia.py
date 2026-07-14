#!/usr/bin/env python3
"""Offscreen layout smoke test for Servo Tuning GAINS/INERTIA panel.

Does not import Probe Basic / qtpyvcp — recreates the param-group layout from
servo_tuner.py so we can catch clipping/overlap before hardware.
"""

from __future__ import annotations

import os
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QPalette
from PyQt5.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDoubleSpinBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
QSS = os.path.join(ROOT, "probe_basic", "user_tabs", "servo_tuner", "servo_tuner.qss")
OUT = os.path.join(ROOT, "logs", "tuning", "ui_smoke")
ARTIFACTS = "/opt/cursor/artifacts/ui_smoke_servo_tuner"


def caption(text: str, parent: QWidget) -> QLabel:
    lab = QLabel(text, parent)
    lab.setObjectName("lblCaption")
    return lab


def build_window(width: int, height: int) -> QWidget:
    root = QWidget()
    root.setObjectName("SERVO_TUNING")
    root.resize(width, height)
    palette = root.palette()
    palette.setColor(QPalette.Window, QColor("#2e3436"))
    root.setPalette(palette)
    root.setAutoFillBackground(True)

    layout = QVBoxLayout(root)
    layout.setContentsMargins(10, 10, 10, 10)
    layout.setSpacing(6)

    # Fake header / actions so vertical budget matches production-ish.
    header = QFrame(root)
    header.setObjectName("headerBar")
    hl = QHBoxLayout(header)
    title = QLabel("SERVO TUNING", header)
    title.setObjectName("lblTitle")
    hl.addWidget(title)
    layout.addWidget(header)

    actions = QFrame(root)
    actions.setObjectName("presetsBar")
    al = QHBoxLayout(actions)
    al.addWidget(caption("ONE-CLICK", actions))
    al.addWidget(QPushButton("ONE-CLICK TUNE X", actions))
    al.addWidget(QPushButton("CANCEL", actions))
    layout.addWidget(actions)

    body = QHBoxLayout()
    ferr = QGroupBox("DRIVE FERR (CiA 60F4)", root)
    ferr.setObjectName("grpFerr")
    fl = QVBoxLayout(ferr)
    plot = QLabel("FERR plot placeholder", ferr)
    plot.setObjectName("ferrPlot")
    plot.setMinimumHeight(320)
    plot.setAlignment(Qt.AlignCenter)
    fl.addWidget(plot)
    body.addWidget(ferr, stretch=3)

    params = QGroupBox("TUNING PARAMETERS", root)
    params.setObjectName("grpParams")
    pl = QVBoxLayout(params)
    pl.setSpacing(4)
    pl.setContentsMargins(8, 8, 8, 8)

    mode_row = QHBoxLayout()
    mode_row.addWidget(caption("PANEL", params))
    btn_gains = QPushButton("GAINS", params)
    btn_gains.setObjectName("btnAxis")
    btn_gains.setCheckable(True)
    btn_gains.setChecked(True)
    btn_inertia = QPushButton("INERTIA", params)
    btn_inertia.setObjectName("btnAxis")
    btn_inertia.setCheckable(True)
    group = QButtonGroup(params)
    group.addButton(btn_gains)
    group.addButton(btn_inertia)
    mode_row.addWidget(btn_gains)
    mode_row.addWidget(btn_inertia)
    mode_row.addStretch()
    pl.addLayout(mode_row)

    stack = QStackedWidget(params)

    # Gains page
    gains = QWidget(params)
    gl = QVBoxLayout(gains)
    gl.setContentsMargins(0, 0, 0, 0)
    apply = QPushButton("APPLY CHANGES", gains)
    apply.setObjectName("btnPrimary")
    gl.addWidget(apply, alignment=Qt.AlignLeft)
    table = QTableWidget(12, 5, gains)
    table.setObjectName("paramTable")
    table.setHorizontalHeaderLabels(
        ["Parameter", "Current", "Pending", "Unit", "Range"]
    )
    table.verticalHeader().setVisible(False)
    hdr = table.horizontalHeader()
    hdr.setSectionResizeMode(0, QHeaderView.Stretch)
    for col in (1, 3, 4):
        hdr.setSectionResizeMode(col, QHeaderView.ResizeToContents)
    hdr.setSectionResizeMode(2, QHeaderView.Fixed)
    hdr.resizeSection(2, 110)
    for r in range(12):
        table.setItem(r, 0, QTableWidgetItem(f"C01.{r:02d} example gain"))
        table.setItem(r, 1, QTableWidgetItem("12.3"))
        table.setItem(r, 3, QTableWidgetItem("Hz"))
        table.setItem(r, 4, QTableWidgetItem("0–400"))
    gl.addWidget(table, stretch=1)
    stack.addWidget(gains)

    # Inertia page (mirrors servo_tuner._build_inertia_page)
    inertia = QWidget(params)
    il = QVBoxLayout(inertia)
    il.setContentsMargins(0, 4, 0, 0)
    il.setSpacing(6)
    hint = QLabel(
        "Yaskawa-style graphical ID: enter motor datasheet J and rated "
        "torque, set the move, then BEGIN. We sample torque + velocity, "
        "solve T=Jα for C00.06, write it, then switch back to GAINS for "
        "one-click.",
        inertia,
    )
    hint.setObjectName("lblParamHint")
    hint.setWordWrap(True)
    il.addWidget(hint)

    for label, decimals, suffix in (
        ("Motor rotor inertia", 8, " kg·m²"),
        ("Rated torque", 4, " N·m"),
        ("Stroke", 2, " mm"),
        ("Feed (G1 F)", 1, " mm/min"),
        ("Cycles", 0, ""),
    ):
        row = QHBoxLayout()
        lab = QLabel(label, inertia)
        lab.setMinimumWidth(150)
        spin = QDoubleSpinBox(inertia)
        spin.setDecimals(decimals)
        spin.setRange(0, 100000)
        spin.setSuffix(suffix)
        if decimals == 8:
            spin.setValue(0.00014)
        row.addWidget(lab)
        row.addWidget(spin, stretch=1)
        il.addLayout(row)

    btn_row = QHBoxLayout()
    begin = QPushButton("BEGIN INERTIA AUTO-TUNE", inertia)
    begin.setObjectName("btnPrimary")
    cancel = QPushButton("CANCEL", inertia)
    cancel.setObjectName("btnDanger")
    cancel.setEnabled(False)
    btn_row.addWidget(begin)
    btn_row.addWidget(cancel)
    il.addLayout(btn_row)

    result = QLabel(
        "Result: —\nEnter J_M + rated torque, park mid-travel, then BEGIN.",
        inertia,
    )
    result.setObjectName("lblParamHint")
    result.setWordWrap(True)
    il.addWidget(result)
    il.addStretch(1)
    stack.addWidget(inertia)

    pl.addWidget(stack, stretch=1)
    body.addWidget(params, stretch=2)
    layout.addLayout(body, stretch=1)

    # stash for switching
    root._stack = stack
    root._btn_gains = btn_gains
    root._btn_inertia = btn_inertia
    root._params = params
    root._begin = begin
    return root


def grab(widget: QWidget, path: str) -> None:
    pix = widget.grab()
    for dest in (path,):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        ok = pix.save(dest)
        print(f"{'OK' if ok else 'FAIL'} {dest} ({pix.width()}x{pix.height()})")
    # Also copy to cloud artifacts for review.
    art = os.path.join(ARTIFACTS, os.path.basename(path))
    os.makedirs(ARTIFACTS, exist_ok=True)
    pix.save(art)


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication(sys.argv)
    if os.path.isfile(QSS):
        with open(QSS, encoding="utf-8") as handle:
            app.setStyleSheet(handle.read())

    sizes = [(1200, 760), (1100, 700), (900, 640)]
    for w, h in sizes:
        win = build_window(w, h)
        win.show()
        app.processEvents()
        grab(win, os.path.join(OUT, f"gains_{w}x{h}.png"))
        grab(win._params, os.path.join(OUT, f"gains_panel_{w}x{h}.png"))

        win._btn_inertia.setChecked(True)
        win._stack.setCurrentIndex(1)
        win._params.setTitle("INERTIA AUTO-TUNE")
        app.processEvents()
        grab(win, os.path.join(OUT, f"inertia_{w}x{h}.png"))
        grab(win._params, os.path.join(OUT, f"inertia_panel_{w}x{h}.png"))
        grab(win._begin, os.path.join(OUT, f"begin_btn_{w}x{h}.png"))
        win.close()

    print(f"artifacts under {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
