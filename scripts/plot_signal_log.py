#!/usr/bin/env python3
"""Plot a CSV file produced by hal_signal_logger."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", help="CSV log file to plot")
    parser.add_argument(
        "--preset",
        help="Optional preset JSON for titles/colors/y-axis groups",
    )
    return parser.parse_args()


def load_csv(path: str) -> tuple:
    with open(path, "r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        if not rows:
            raise SystemExit("CSV has no rows")
        return reader.fieldnames or [], rows


def main() -> int:
    args = parse_args()
    columns, rows = load_csv(args.csv_path)

    try:
        import pyqtgraph as pg
        from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget
    except ImportError:
        print("Install pyqtgraph and qtpy to use plot_signal_log.py", file=sys.stderr)
        return 1

    signal_columns = [
        name
        for name in columns
        if name not in {"t", "line", "feed", "motion_type", "enabled"}
    ]

    plot_groups = [{"id": "all", "title": os.path.basename(args.csv_path), "channels": signal_columns}]
    colors = {}

    if args.preset and os.path.isfile(args.preset):
        with open(args.preset, "r", encoding="utf-8") as handle:
            preset = json.load(handle)
        if preset.get("plot_groups"):
            plot_groups = preset["plot_groups"]
        for channel in preset.get("channels", []):
            colors[channel["id"]] = channel.get("color", "#ffffff")

    app = QApplication([])
    window = QWidget()
    window.setWindowTitle(f"Signal log: {os.path.basename(args.csv_path)}")
    layout = QVBoxLayout(window)

    xs = [float(row["t"]) for row in rows]

    for group in plot_groups:
        plot = pg.PlotWidget(title=group.get("title", group["id"]))
        plot.showGrid(x=True, y=True, alpha=0.25)
        plot.setLabel("bottom", "time", units="s")
        plot.addLegend()

        for channel_id in group.get("channels", []):
            if channel_id not in columns:
                continue
            ys = [float(row[channel_id]) for row in rows]
            pen = pg.mkPen(color=colors.get(channel_id, "#ffffff"), width=2)
            plot.plot(xs, ys, pen=pen, name=channel_id)

        mode = group.get("y_mode", "auto")
        if mode == "fixed":
            ymin = group.get("y_min")
            ymax = group.get("y_max")
            if ymin is not None and ymax is not None:
                plot.setYRange(float(ymin), float(ymax), padding=0)
        elif mode == "sym":
            values = []
            for channel_id in group.get("channels", []):
                if channel_id in columns:
                    values.extend(float(row[channel_id]) for row in rows)
            if values:
                limit = max(max(abs(v) for v in values), 1e-6)
                plot.setYRange(-limit * 1.1, limit * 1.1, padding=0)

        layout.addWidget(plot)

    window.resize(1100, 800)
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
