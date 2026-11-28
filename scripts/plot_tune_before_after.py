#!/usr/bin/env python3
"""Plot drive following error before vs after a one-click tune, one row per axis.

Usage:
  python3 scripts/plot_tune_before_after.py RUN_DIR [RUN_DIR ...] [-o out.png]
  RUN_DIR may be suffixed  :before.csv,after.csv  to pick captures by hand.

Defaults: before = 03_baseline_3.csv (the first baseline move can carry a
start-up spike), after = the *_verify.csv, or, when the journal says the
verify fell back to "keep-best", the step capture that was restored.
"""
import argparse
import glob
import json
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def load(path):
    with open(path) as f:
        hdr = f.readline()
    fs = float(re.search(r"fs_hz=([\d.]+)", hdr).group(1))
    y = np.loadtxt(path, skiprows=2) * 1000.0  # mm -> um
    return np.arange(len(y)) / fs, y


def pick(run):
    before = os.path.join(run, "03_baseline_3.csv")
    after = sorted(glob.glob(os.path.join(run, "*_verify.csv")))[-1]
    with open(os.path.join(run, "journal.md")) as f:
        txt = f.read()
    m = re.search(r"keep-best.*?```json\n(.*?)```", txt, re.S)
    if m:
        bv = json.loads(m.group(1))["best_values"]
        # restored step = last capture taken at the restored pos gain
        tag = "pos_%.1frads" % bv["pos_gain_rad_s"]
        cands = sorted(glob.glob(os.path.join(run, "*_%s.csv" % tag)))
        if cands:
            after = cands[0]
    return before, after


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("-o", "--out", default="tune_before_after.png")
    a = ap.parse_args()

    fig, axes = plt.subplots(len(a.runs), 2, figsize=(13, 3.2 * len(a.runs)),
                             gridspec_kw={"width_ratios": [4, 1]}, squeeze=False,
                             sharex="col")  # same time window on every row; own y scales
    tmax = float("inf")
    for row, spec in zip(axes, a.runs):
        run, _, files = spec.partition(":")
        if files:
            b, f = files.split(",")
            before, after = os.path.join(run, b), os.path.join(run, f)
        else:
            before, after = pick(run)
        axis = re.search(r"_([XYZA])/?$", run.rstrip("/") + "/").group(1)
        tb, yb = load(before)
        ta, ya = load(after)
        tmax = min(tmax, tb[-1], ta[-1])
        rms_b, rms_a = np.sqrt(np.mean(yb**2)), np.sqrt(np.mean(ya**2))
        pk_b, pk_a = np.max(np.abs(yb)), np.max(np.abs(ya))

        ax = row[0]
        ax.plot(tb, yb, color="#c0392b", lw=0.8, alpha=0.8, label="before")
        ax.plot(ta, ya, color="#2471a3", lw=0.9, label="after")
        ax.axhline(0, color="#888", lw=0.5)
        ax.set_ylabel("%s following error (µm)" % axis)
        ax.set_title("%s   %s  vs  %s" % (axis, os.path.basename(before),
                                           os.path.basename(after)),
                     fontsize=9, loc="left", color="#555")
        ax.legend(loc="upper right", fontsize=8)
        ax.grid(alpha=0.25)

        bx = row[1]
        x = np.arange(2)
        w = 0.38
        bx.bar(x - w / 2, [rms_b, pk_b], w, color="#c0392b", label="before")
        bx.bar(x + w / 2, [rms_a, pk_a], w, color="#2471a3", label="after")
        bx.set_xticks(x, ["RMS", "peak"])
        bx.set_ylabel("µm")
        for xi, (vb, va) in enumerate([(rms_b, rms_a), (pk_b, pk_a)]):
            bx.text(xi, max(vb, va) * 1.04, "%.1f×" % (vb / va),
                    ha="center", fontsize=9, fontweight="bold")
        bx.set_ylim(0, max(bx.get_ylim()[1], max(rms_b, pk_b, rms_a, pk_a) * 1.18))
        bx.tick_params(labelleft=True)
        ax.tick_params(labelleft=True)
        bx.grid(alpha=0.25, axis="y")
        print("%s  rms %.2f -> %.2f um (%.1fx)   peak %.2f -> %.2f um (%.1fx)"
              % (axis, rms_b, rms_a, rms_b / rms_a, pk_b, pk_a, pk_b / pk_a))
    axes[-1][0].set_xlim(0, tmax)  # same window on every row (shortest capture)
    axes[-1][0].set_xlabel("time (s)  —  cropped to the shortest capture; RMS/peak bars use each full capture")
    fig.suptitle("Drive following error (60F4) during the tune stimulus: before vs after one-click",
                 fontsize=11)
    fig.tight_layout()
    fig.savefig(a.out, dpi=130)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
