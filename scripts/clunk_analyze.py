#!/usr/bin/env python3
"""Look for a "clunk" at direction reversals in drive following error.

  python3 scripts/clunk_analyze.py logs/clunk/<stamp>_<AXIS>.csv[.gz]

Input: clunk_capture.py CSV (t_s, pos_cmd_mm, ferr_mm). Following error only.
Blocks are split on the 0.5 s dwells (expect 12: a-f with G61, then G64).
Per reversal, window -50..+150 ms:
  peak  = max |ferr|
  jump  = max |diff ferr| (mm per servo cycle)
  ring  = RMS of (ferr - 20 ms moving average), +20..+150 ms
Baseline: same numbers from mid-stroke windows on the long strokes.
Candidate: jump or ring > median + 5*MAD of its block, or > 3x baseline.
Writes <csv stem>_report.md, _run.png and _overlay.png next to the CSV.
"""
import gzip
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

BLOCK_NAMES = ["a", "b", "c", "d", "e", "f"]
BLOCK_DESC = {"a": "±20 F1000", "b": "±20 F3000", "c": "±20 F6000",
              "d": "±20 F12000", "e": "±2 F3000", "f": "±0.1 F500"}
PRE, POST = 0.050, 0.150
RING_FROM = 0.020
MA = 0.020
V_EPS = 1e-3     # mm/s: below this the command is standing still
DWELL_MIN = 0.35  # s of stillness that separates blocks
UM = 1000.0


def load(path):
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt") as f:
        first = f.readline()
    meta = json.loads(first[1:]) if first.startswith("#") else {}
    d = np.loadtxt(path, delimiter=",", skiprows=2 if meta else 1, usecols=(0, 1, 2))
    return meta, d[:, 0], d[:, 1], d[:, 2]


def moving_avg(x, n):
    k = np.ones(n) / n
    return np.convolve(np.pad(x, (n // 2, n - 1 - n // 2), mode="edge"), k, "valid")


def segments(moving):
    """[start, end) index runs where moving is True."""
    m = np.concatenate([[False], moving, [False]]).astype(int)
    d = np.diff(m)
    return list(zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]))


def main():
    path = sys.argv[1]
    meta, t, pos, ferr = load(path)
    fs = 1.0 / np.median(np.diff(t))
    v = np.gradient(pos) * fs
    sgn = np.where(v > V_EPS, 1, np.where(v < -V_EPS, -1, 0))
    # runs of constant non-zero sign (a reversal can flip + to - with no
    # standstill sample in between, so split on sign changes, not on zeros)
    edges = np.nonzero(np.diff(sgn))[0] + 1
    bounds = np.concatenate([[0], edges, [len(sgn)]])
    segs = [(a, b, int(sgn[a])) for a, b in zip(bounds[:-1], bounds[1:]) if sgn[a] != 0]
    # merge into direction legs (a leg may be split by a zero sample)
    legs = []
    for a, b, s in segs:
        if legs and legs[-1][2] == s and (a - legs[-1][1]) / fs < 0.005:
            legs[-1] = (legs[-1][0], b, s)
        else:
            legs.append((a, b, s))
    # blocks: split where the command stands still >= DWELL_MIN
    blocks, cur = [], [legs[0]]
    for prev, leg in zip(legs, legs[1:]):
        if (leg[0] - prev[1]) / fs >= DWELL_MIN:
            blocks.append(cur)
            cur = []
        cur.append(leg)
    blocks.append(cur)
    # 12 blocks per pass (a-f with G61, then G64); the stress program repeats
    # the pass, so label as a-G61, ..., f-G64, then a-G61-p2, ...
    labels = []
    whole = len(blocks) % 12 == 0
    for i in range(len(blocks)):
        mode = "G61" if (i % 12) < 6 else "G64"
        pas = i // 12 + 1
        labels.append(f"{BLOCK_NAMES[i % 6]}-{mode}" + (f"-p{pas}" if pas > 1 else "")
                      if whole else f"blk{i}")
    warn = [] if whole else [f"found {len(blocks)} blocks, expected a multiple of 12"]

    npre, npost, nring = int(PRE * fs), int(POST * fs), int(RING_FROM * fs)
    nma = max(int(MA * fs), 1)
    trend = moving_avg(ferr, nma)
    resid = ferr - trend
    dferr = np.abs(np.diff(ferr, prepend=ferr[0]))

    def window_stats(i0, i1, ring0):
        i0, i1 = max(i0, 0), min(i1, len(ferr))
        r = resid[max(ring0, i0):i1]
        return (np.max(np.abs(ferr[i0:i1])), np.max(dferr[i0 + 1:i1]),
                float(np.sqrt(np.mean(r ** 2))) if r.size else np.nan)

    revs = []  # dict per reversal
    for bi, blk in enumerate(blocks):
        for l0, l1 in zip(blk, blk[1:]):
            if l0[2] == l1[2]:
                continue
            ir = (l0[1] + l1[0]) // 2  # middle of the stop between the legs
            pk, jp, rg = window_stats(ir - npre, ir + npost, ir + nring)
            revs.append(dict(block=labels[bi], bi=bi, i=ir, t=t[ir],
                             dir="+→-" if l0[2] > 0 else "-→+",
                             peak=pk, jump=jp, ring=rg))
    # mid-stroke baseline: long legs only, a 100 ms window in the middle with
    # >= 150 ms to either end of the leg
    base = []
    for bi, blk in enumerate(blocks):
        if labels[bi][0] not in "abcd":
            continue
        for a, b, _s in blk:
            mid, half = (a + b) // 2, int(0.05 * fs)
            if (mid - half - a) / fs >= 0.15 and (b - mid - half) / fs >= 0.15:
                base.append(window_stats(mid - half, mid + half, mid - half))
    base = np.array(base) if base else np.full((1, 3), np.nan)
    b_peak, b_jump, b_ring = np.nanmedian(base, axis=0)

    for bi in range(len(blocks)):
        rs = [r for r in revs if r["bi"] == bi]
        for key in ("jump", "ring"):
            x = np.array([r[key] for r in rs])
            if not x.size:
                continue
            med = np.median(x)
            mad = np.median(np.abs(x - med))
            lim = med + 5 * mad if mad > 0 else np.inf
            bl = 3 * (b_jump if key == "jump" else b_ring)
            for r in rs:
                r.setdefault("why", [])
                r.setdefault("mad", False)
                r.setdefault("b3", False)
                if r[key] > lim:
                    r["why"].append(f"{key}>med+5MAD")
                    r["mad"] = True
                if np.isfinite(bl) and r[key] > bl:
                    r["why"].append(f"{key}>3x base")
                    r["b3"] = True

    # ---- report -------------------------------------------------------------
    stem = path[:-len(".csv.gz")] if path.endswith(".csv.gz") else os.path.splitext(path)[0]
    L = [f"# Clunk analysis: {os.path.basename(path)}", ""]
    L.append(f"capture: fs {fs:.1f} Hz, {len(t)} samples, {t[-1]:.1f} s; "
             f"overruns {meta.get('overruns', '?')}, expected "
             f"{meta.get('expected_samples', '?')} samples, "
             f"error: {meta.get('capture_error', 'none')}")
    L += [f"WARNING: {w}" for w in warn]
    L.append(f"mid-stroke baseline ({len(base)} windows): peak {b_peak*UM:.2f} um, "
             f"jump {b_jump*UM:.3f} um/cycle, ring {b_ring*UM:.3f} um rms")
    L.append("")
    L.append("| block | n rev | peak med/max µm | jump med/max µm | ring med/max µm | n >3x base | n >med+5MAD (t s) |")
    L.append("|---|---|---|---|---|---|---|")
    for bi, lab in enumerate(labels):
        rs = [r for r in revs if r["bi"] == bi]
        if not rs:
            L.append(f"| {lab} | 0 | | | | |")
            continue
        f = lambda k: f"{np.median([r[k] for r in rs])*UM:.2f} / {max(r[k] for r in rs)*UM:.2f}"
        nb3 = sum(r["b3"] for r in rs)
        mads = [r for r in rs if r["mad"]]
        ct = ", ".join(f"{r['t']:.2f}" for r in mads)
        L.append(f"| {lab} ({BLOCK_DESC.get(lab[0], '')}) | {len(rs)} | {f('peak')} | "
                 f"{f('jump')} | {f('ring')} | {nb3} | {len(mads)}{': ' + ct if ct else ''} |")
    L += ["", "Asymmetry (median +→- minus median -→+, µm):", "",
          "| block | peak | jump | ring |", "|---|---|---|---|"]
    for bi, lab in enumerate(labels):
        rs = [r for r in revs if r["bi"] == bi]
        pm = [r for r in rs if r["dir"] == "+→-"]
        mp = [r for r in rs if r["dir"] == "-→+"]
        if pm and mp:
            d = {k: (np.median([r[k] for r in pm]) - np.median([r[k] for r in mp])) * UM
                 for k in ("peak", "jump", "ring")}
            L.append(f"| {lab} | {d['peak']:+.2f} | {d['jump']:+.3f} | {d['ring']:+.3f} |")
    cand_all = [r for r in revs if r["mad"]]
    L += ["", "Outliers within their block (med+5MAD):", ""]
    L += [f"- {r['block']} t={r['t']:.3f}s {r['dir']} peak {r['peak']*UM:.2f} "
          f"jump {r['jump']*UM:.3f} ring {r['ring']*UM:.3f}: {', '.join(r['why'])}"
          for r in cand_all] or ["- none"]
    with open(stem + "_report.md", "w") as fh:
        fh.write("\n".join(L) + "\n")
    with open(stem + "_reversals.json", "w") as fh:
        json.dump([{k: (float(v) if isinstance(v, (np.floating, float)) else v)
                    for k, v in r.items() if k != "i"} for r in revs], fh, indent=0, default=int)
    print("\n".join(L))

    # ---- plots --------------------------------------------------------------
    fig, ax = plt.subplots(2, 1, figsize=(16, 7), sharex=True,
                           gridspec_kw={"height_ratios": [3, 1]})
    ax[0].plot(t, ferr * UM, lw=0.5, color="#2471a3")
    for r in revs:
        ax[0].axvline(r["t"], color="#c0392b" if r["why"] else "#bbb",
                      lw=1.0 if r["why"] else 0.3, zorder=0)
    ax[0].set_ylabel("following error (µm)")
    ax[0].set_title(f"{os.path.basename(path)}: reversals grey, clunk candidates red")
    ax[1].plot(t, pos, lw=0.6, color="#555")
    ax[1].set_ylabel("pos cmd (mm)")
    ax[1].set_xlabel("time (s)")
    for bi, blk in enumerate(blocks):
        ax[1].text(t[blk[0][0]], ax[1].get_ylim()[1], labels[bi], fontsize=7, va="top")
    fig.tight_layout()
    fig.savefig(stem + "_run.png", dpi=110)

    nb = len(blocks)
    cols = 6 if nb % 12 == 0 else min(nb, 4)
    rows = int(np.ceil(nb / cols))
    fig, axs = plt.subplots(rows, cols, figsize=(3.2 * cols, 2.8 * rows), squeeze=False)
    tw = np.arange(-npre, npost) / fs * 1000
    for bi in range(nb):
        a = axs[bi // cols][bi % cols]
        for r in [r for r in revs if r["bi"] == bi]:
            i0, i1 = r["i"] - npre, r["i"] + npost
            if i0 < 0 or i1 > len(ferr):
                continue
            col = "#c0392b" if r["dir"] == "+→-" else "#2471a3"
            a.plot(tw, ferr[i0:i1] * UM, color=col, lw=1.6 if r["why"] else 0.6,
                   alpha=0.9 if r["why"] else 0.5)
        a.axvline(0, color="#888", lw=0.5)
        a.set_title(f"{labels[bi]} {BLOCK_DESC.get(labels[bi][0], '')}", fontsize=8)
        a.tick_params(labelsize=7)
    axs[-1][0].set_xlabel("ms from reversal (red +→-, blue -→+; thick = candidate)", fontsize=7)
    axs[0][0].set_ylabel("ferr µm", fontsize=7)
    fig.tight_layout()
    fig.savefig(stem + "_overlay.png", dpi=110)
    print("wrote", stem + "_report.md", stem + "_run.png", stem + "_overlay.png")


if __name__ == "__main__":
    main()
