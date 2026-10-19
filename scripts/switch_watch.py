#!/usr/bin/env python3
"""Compact home/limit switch watch — run while LinuxCNC is up.

  source ~/src/linuxcnc-tpnext/scripts/rip-environment   # if using tpnext
  python3 scripts/switch_watch.py
"""
from __future__ import annotations

import tkinter as tk

import hal

ROWS = [
    ("X", "joint.0.home-sw-in", "joint.0.neg-lim-sw-in", "joint.0.pos-lim-sw-in"),
    ("Y", "joint.1.home-sw-in", "joint.1.neg-lim-sw-in", "joint.1.pos-lim-sw-in"),
    ("Z", "joint.2.home-sw-in", "joint.2.neg-lim-sw-in", "joint.2.pos-lim-sw-in"),
    ("A", "joint.3.home-sw-in", "joint.3.neg-lim-sw-in", "joint.3.pos-lim-sw-in"),
]

RAW = [
    ("X home DI", "lcec.0.0.di-2"),
    ("X lim DI", "lcec.0.0.di-5"),
    ("Y lim DI (was Z-)", "lcec.0.0.di-1"),
    ("Y/Z home DI", "lcec.0.1.di-4"),
]


class SwitchWatch(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Home / Limit watch")
        self.configure(bg="#1e1e1e")
        # Unique name so relaunch works if a prior instance left a HAL component.
        import os
        self.h = hal.component(f"switch-watch-{os.getpid()}")
        self.h.ready()

        hdr = ("Axis", "HOME", "NEG LIM", "POS LIM")
        for c, text in enumerate(hdr):
            tk.Label(
                self, text=text, fg="#aaa", bg="#1e1e1e", font=("DejaVu Sans", 11, "bold")
            ).grid(row=0, column=c, padx=10, pady=6, sticky="w")

        self.cells: dict[str, tk.Label] = {}
        for r, (axis, home, neg, pos) in enumerate(ROWS, start=1):
            tk.Label(
                self, text=axis, fg="#fff", bg="#1e1e1e", font=("DejaVu Sans", 14, "bold")
            ).grid(row=r, column=0, padx=10, pady=4, sticky="w")
            for c, pin in enumerate((home, neg, pos), start=1):
                lab = tk.Label(
                    self,
                    text="—",
                    width=8,
                    fg="#888",
                    bg="#2a2a2a",
                    font=("DejaVu Sans Mono", 13, "bold"),
                )
                lab.grid(row=r, column=c, padx=6, pady=4)
                self.cells[pin] = lab

        tk.Label(
            self,
            text="Raw DI (TRUE=idle for NC)",
            fg="#888",
            bg="#1e1e1e",
            font=("DejaVu Sans", 10),
        ).grid(row=5, column=0, columnspan=4, sticky="w", padx=10, pady=(12, 2))

        self.raw_cells: dict[str, tk.Label] = {}
        for i, (name, pin) in enumerate(RAW):
            row = 6 + i
            tk.Label(
                self, text=name, fg="#ccc", bg="#1e1e1e", font=("DejaVu Sans", 10)
            ).grid(row=row, column=0, columnspan=2, sticky="w", padx=10)
            lab = tk.Label(
                self,
                text="—",
                width=8,
                fg="#888",
                bg="#2a2a2a",
                font=("DejaVu Sans Mono", 11, "bold"),
            )
            lab.grid(row=row, column=2, padx=6, pady=2)
            self.raw_cells[pin] = lab

        self.after(50, self._tick)

    def _paint(self, lab: tk.Label, val: bool, tripped_is_true: bool = True) -> None:
        active = bool(val) if tripped_is_true else not bool(val)
        if active:
            lab.configure(text="TRIP", fg="#111", bg="#f0c000")
        else:
            lab.configure(text="ok", fg="#8f8", bg="#1a3a1a")

    def _tick(self) -> None:
        try:
            for pin, lab in self.cells.items():
                self._paint(lab, hal.get_value(pin), tripped_is_true=True)
            for pin, lab in self.raw_cells.items():
                # raw NC: idle often TRUE; show raw TRUE/FALSE
                v = bool(hal.get_value(pin))
                lab.configure(
                    text="TRUE" if v else "FALSE",
                    fg="#111" if not v else "#8f8",
                    bg="#f0c000" if not v else "#1a3a1a",
                )
        except Exception as exc:  # noqa: BLE001 — show disconnect
            self.title(f"Home / Limit watch — {exc}")
        self.after(50, self._tick)


if __name__ == "__main__":
    SwitchWatch().mainloop()
