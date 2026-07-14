#!/usr/bin/env python3
"""Visual breakdown of one-click auto-tune FERR scoring.

Uses:
  - config/logging/example_session.csv  (committed face-mill HAL log)
  - SimPlant buffers at gains mirroring the hardware X/Y one-click presets
    (raw journals are gitignored; presets + notes are the committed record)

Outputs PNGs + small CSVs under --out-dir (default docs/assets/auto_tune_scoring/).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.insert(0, os.path.join(ROOT, "probe_basic", "python"))

from a6_auto_tune import DEFAULT_STIMULI, SCORE_RMS_WEIGHT, OneClickConfig  # noqa: E402
from a6_auto_tune_sim import SIM_BASELINE, SimPlant  # noqa: E402
from resonance_analysis import analyze_ferr_resonance, compute_spectrum  # noqa: E402


# ---------------------------------------------------------------------------
# Scoring helpers (mirror a6_auto_tune.OneClickTuner without needing HAL)
# ---------------------------------------------------------------------------


@dataclass
class ScoredBuffer:
    label: str
    axis: str
    samples: np.ndarray
    fs_hz: float
    peak: float
    rms: float
    score: float
    gate_min_hz: float
    unstable: bool
    unstable_why: str
    report: Any
    note: str = ""
    gains: Optional[Dict[str, float]] = None

    @property
    def peak_term(self) -> float:
        return self.peak

    @property
    def rms_term(self) -> float:
        return SCORE_RMS_WEIGHT * self.rms


def gate_min_hz_for(axis: str, cfg: Optional[OneClickConfig] = None) -> float:
    cfg = cfg or OneClickConfig(axis=axis, stimulus=DEFAULT_STIMULI[axis])
    leg = max(cfg.stimulus.leg_time_s(), 1e-3)
    return min(
        cfg.gate_min_hz_cap,
        max(cfg.gate_min_hz_floor, cfg.gate_min_hz_factor / leg),
    )


def classify(
    report: Any,
    *,
    cfg: OneClickConfig,
    aborted: bool = False,
    abort_reason: str = "",
) -> Tuple[bool, str]:
    """Same rules as OneClickTuner._classify (non-verify)."""
    reasons: List[str] = []
    if aborted:
        reasons.append(f"move aborted: {abort_reason}")
    if report is not None:
        if report.n_samples < 64:
            reasons.append(f"short buffer ({int(report.n_samples)})")
        dom = report.dominant
        amp_floor = max(
            cfg.min_resonance_amplitude,
            cfg.resonance_vs_rms * float(report.rms),
        )
        if (
            dom is not None
            and dom.prominence >= cfg.min_prominence_ratio
            and dom.magnitude >= amp_floor
        ):
            reasons.append(
                f"resonance peak {dom.freq_hz:.1f} Hz "
                f"(mag {dom.magnitude:.4g}, x{dom.prominence:.1f} floor, "
                f"amp floor {amp_floor:.4g})"
            )
        if (
            report.hf_energy_ratio >= cfg.hf_fail
            and report.rms >= cfg.min_meaningful_rms
        ):
            reasons.append(f"HF energy {report.hf_energy_ratio:.0%}")
        if (
            report.ring_score >= cfg.ring_fail
            and report.rms >= cfg.min_meaningful_rms
        ):
            reasons.append(f"ring score {report.ring_score:.2f}")
    else:
        reasons.append("no FFT report")
    return (bool(reasons), "; ".join(reasons))


def score_samples(
    samples: Sequence[float],
    *,
    axis: str,
    label: str,
    fs_hz: float,
    note: str = "",
    gains: Optional[Dict[str, float]] = None,
    cfg: Optional[OneClickConfig] = None,
) -> ScoredBuffer:
    cfg = cfg or OneClickConfig(axis=axis, stimulus=DEFAULT_STIMULI[axis])
    gmin = gate_min_hz_for(axis, cfg)
    report = analyze_ferr_resonance(
        samples,
        axis=axis,
        fs_hz=fs_hz,
        min_hz=gmin,
        hf_fail=cfg.hf_fail,
        ring_fail=cfg.ring_fail,
        min_prominence_ratio=cfg.min_prominence_ratio,
    )
    unstable, why = classify(report, cfg=cfg)
    return ScoredBuffer(
        label=label,
        axis=axis,
        samples=np.asarray(samples, dtype=float),
        fs_hz=float(fs_hz),
        peak=float(report.peak_abs),
        rms=float(report.rms),
        score=float(report.peak_abs) + SCORE_RMS_WEIGHT * float(report.rms),
        gate_min_hz=gmin,
        unstable=unstable,
        unstable_why=why,
        report=report,
        note=note,
        gains=gains,
    )


def load_example_session(path: str) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
    """Return {axis: (t, ferr)} for X/Y/Z/A from the face-mill CSV."""
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    t = np.array([float(r["t"]) for r in rows], dtype=float)
    out: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
    for axis, col in (
        ("X", "x_ferr"),
        ("Y", "y_ferr"),
        ("Z", "z_ferr"),
        ("A", "a_ferr"),
    ):
        out[axis] = (t, np.array([float(r[col]) for r in rows], dtype=float))
    return out


def estimate_fs(t: np.ndarray) -> float:
    if t.size < 2:
        return 50.0
    dt = float(np.median(np.diff(t)))
    return 1.0 / dt if dt > 0 else 50.0


def write_ferr_csv(path: str, samples: np.ndarray, fs_hz: float) -> None:
    t = np.arange(samples.size) / float(fs_hz)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["t", "ferr"])
        for ti, vi in zip(t, samples):
            writer.writerow([f"{ti:.6f}", f"{vi:.8f}"])


# ---------------------------------------------------------------------------
# Figure styling
# ---------------------------------------------------------------------------

PALETTE = {
    "ink": "#1a1f24",
    "muted": "#5c6670",
    "pass": "#1f7a4c",
    "fail": "#b33a3a",
    "accent": "#c45c26",
    "band": "#d8e2ec",
    "peak": "#2c5f8a",
    "rms": "#8a5a2c",
    "grid": "#e6ebf0",
}


def _style_ax(ax: Any) -> None:
    ax.set_facecolor("#f7f5f2")
    ax.grid(True, color=PALETTE["grid"], linewidth=0.8)
    ax.tick_params(colors=PALETTE["muted"])
    for spine in ax.spines.values():
        spine.set_color("#c5ccd4")


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------


def fig_formula_and_session(
    session: Dict[str, Tuple[np.ndarray, np.ndarray]],
    out_path: str,
) -> List[ScoredBuffer]:
    """Panel: score formula + real face-mill FERR scored per axis."""
    scored: List[ScoredBuffer] = []
    fig = plt.figure(figsize=(14.5, 10.0), facecolor="#fbfaf8")
    fig.suptitle(
        "How auto-tune scores a FERR plot\n"
        "score = peak(|ferr|) + 2 × RMS(ferr)   ·   lower is better",
        fontsize=15,
        fontweight="bold",
        color=PALETTE["ink"],
        y=0.98,
    )

    gs = fig.add_gridspec(
        3,
        2,
        height_ratios=[0.9, 1.35, 1.35],
        hspace=0.45,
        wspace=0.28,
        left=0.07,
        right=0.97,
        top=0.88,
        bottom=0.06,
    )

    ax0 = fig.add_subplot(gs[0, :])
    ax0.set_xlim(0, 1)
    ax0.set_ylim(0, 1)
    ax0.axis("off")
    ax0.add_patch(
        plt.Rectangle(
            (0.0, 0.05),
            1.0,
            0.9,
            facecolor="#efe8df",
            edgecolor="#c9b8a4",
            linewidth=1.2,
            transform=ax0.transAxes,
            clip_on=False,
        )
    )
    ax0.text(
        0.02,
        0.72,
        "Acceptance (ladder step)",
        fontsize=11,
        fontweight="bold",
        color=PALETTE["ink"],
        transform=ax0.transAxes,
    )
    ax0.text(
        0.02,
        0.28,
        "Keep a gain step only when the FFT stability gate PASSes\n"
        "AND score improves by ≥ 3% vs the last accepted step.\n"
        "Integral phase uses a softer RMS gate (≥0.5%) with a peak-regress guard.",
        fontsize=9.5,
        color=PALETTE["muted"],
        transform=ax0.transAxes,
        linespacing=1.35,
    )
    ax0.text(
        0.58,
        0.55,
        "Data: config/logging/example_session.csv\n"
        "(face_mill_test · 50 Hz · 17 samples)\n"
        "Short buffers cannot run the FFT gate (≥64 samples\n"
        "needed) — time-domain score still applies.",
        fontsize=9,
        color=PALETTE["muted"],
        transform=ax0.transAxes,
        linespacing=1.35,
    )

    axes_order = ["X", "Y", "Z", "A"]
    plot_slots = [(1, 0), (1, 1), (2, 0), (2, 1)]
    for i, axis in enumerate(axes_order):
        t, ferr = session[axis]
        fs = estimate_fs(t)
        cfg = OneClickConfig(axis=axis, stimulus=DEFAULT_STIMULI[axis])
        sb = score_samples(
            ferr,
            axis=axis,
            label=f"example_{axis}",
            fs_hz=fs,
            note="face_mill_test",
            cfg=cfg,
        )
        scored.append(sb)

        r, c = plot_slots[i]
        ax = fig.add_subplot(gs[r, c])
        _style_ax(ax)
        unit = "deg" if axis == "A" else "mm"
        color = {"X": "#2c5f8a", "Y": "#1f7a4c", "Z": "#8a5a2c", "A": "#6b4c9a"}[
            axis
        ]
        ax.plot(t, ferr, color=color, lw=1.8)
        ax.axhline(sb.peak, color=PALETTE["peak"], ls="--", lw=1.0, alpha=0.85)
        ax.axhline(-sb.peak, color=PALETTE["peak"], ls="--", lw=1.0, alpha=0.85)
        ax.fill_between(
            t,
            -sb.rms,
            sb.rms,
            color=PALETTE["rms"],
            alpha=0.18,
            label=f"±RMS = {sb.rms:.4f}",
        )
        ax.set_title(
            f"{axis}  ·  peak={sb.peak:.4f}  RMS={sb.rms:.4f}  "
            f"score={sb.score:.4f} {unit}",
            fontsize=10,
            color=PALETTE["ink"],
            loc="left",
        )
        ax.set_xlabel("t (s)", fontsize=8)
        ax.set_ylabel(f"FERR ({unit})", fontsize=8)
        ax.text(
            0.98,
            0.92,
            f"peak + 2×RMS\n= {sb.peak:.4f} + 2×{sb.rms:.4f}\n= {sb.score:.4f}",
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=8,
            color=PALETTE["ink"],
            bbox=dict(
                boxstyle="round,pad=0.35",
                facecolor="white",
                edgecolor="#c5ccd4",
                alpha=0.92,
            ),
        )

    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    return scored


def fig_fft_gate_breakdown(
    cases: List[ScoredBuffer],
    out_path: str,
) -> None:
    """Time + FFT for baseline / better / ringing cases with gate overlays."""
    n = len(cases)
    fig, axes = plt.subplots(
        n,
        2,
        figsize=(14.5, 3.6 * n),
        facecolor="#fbfaf8",
        gridspec_kw={"wspace": 0.22, "hspace": 0.38},
    )
    if n == 1:
        axes = np.array([axes])
    fig.suptitle(
        "FFT stability gate on stimulus FERR buffers\n"
        "SimPlant traces at gains shaped like the hardware X one-click campaign "
        "(preset one_click_best_20260712)",
        fontsize=13,
        fontweight="bold",
        color=PALETTE["ink"],
        y=0.995,
    )

    for row, sb in enumerate(cases):
        ax_t, ax_f = axes[row]
        _style_ax(ax_t)
        _style_ax(ax_f)
        t = np.arange(sb.samples.size) / sb.fs_hz
        gate_color = PALETTE["fail"] if sb.unstable else PALETTE["pass"]
        verdict = "FAIL" if sb.unstable else "PASS"

        ax_t.plot(t, sb.samples, color=PALETTE["ink"], lw=0.9)
        ax_t.axhline(sb.peak, color=PALETTE["peak"], ls="--", lw=1.0)
        ax_t.axhline(-sb.peak, color=PALETTE["peak"], ls="--", lw=1.0)
        ax_t.fill_between(t, -sb.rms, sb.rms, color=PALETTE["rms"], alpha=0.15)
        gain_txt = ""
        if sb.gains:
            gain_txt = (
                f"  ·  C01.01={sb.gains.get('speed_gain_hz', 0):.1f} Hz"
                f"  C01.00={sb.gains.get('pos_gain_rad_s', 0):.1f} rad/s"
                f"  C01.02={sb.gains.get('integral_ms', 0):.2f} ms"
            )
        ax_t.set_title(
            f"{sb.label}: score={sb.score:.5f} "
            f"(peak={sb.peak:.5f}, 2×RMS={sb.rms_term:.5f})  [{verdict}]{gain_txt}",
            fontsize=9.5,
            color=gate_color,
            loc="left",
        )
        ax_t.set_xlabel("t (s)", fontsize=8)
        ax_t.set_ylabel("FERR (mm)", fontsize=8)
        if sb.note:
            ax_t.text(
                0.01,
                0.02,
                sb.note,
                transform=ax_t.transAxes,
                fontsize=8,
                color=PALETTE["muted"],
                va="bottom",
            )

        freqs, mag = compute_spectrum(sb.samples, fs_hz=sb.fs_hz)
        ax_f.fill_betweenx(
            [0, float(np.max(mag)) * 1.05 if mag.size else 1.0],
            0,
            sb.gate_min_hz,
            color=PALETTE["band"],
            alpha=0.9,
            label=f"ignored < {sb.gate_min_hz:.0f} Hz",
        )
        ax_f.plot(freqs, mag, color=PALETTE["ink"], lw=1.0)
        amp_floor = max(0.001, 0.10 * sb.rms)
        ax_f.axhline(
            amp_floor,
            color=PALETTE["accent"],
            ls=":",
            lw=1.2,
            label=f"amp floor {amp_floor:.4g}",
        )
        report = sb.report
        if report is not None and report.dominant is not None:
            dom = report.dominant
            ax_f.plot(
                [dom.freq_hz],
                [dom.magnitude],
                "o",
                color=PALETTE["fail"],
                ms=7,
                label=f"dom {dom.freq_hz:.0f} Hz ×{dom.prominence:.0f}",
            )
        ax_f.set_xlim(0, 400)
        ax_f.set_xlabel("Hz", fontsize=8)
        ax_f.set_ylabel("|FFT|", fontsize=8)
        ax_f.set_title(
            f"HF={report.hf_energy_ratio:.0%}  ring={report.ring_score:.2f}  "
            f"·  {verdict}"
            + (f"  ·  {sb.unstable_why}" if sb.unstable else "  ·  no gate trip"),
            fontsize=8.5,
            color=gate_color,
            loc="left",
        )
        ax_f.legend(loc="upper right", fontsize=7, framealpha=0.9)

    fig.savefig(out_path, dpi=140, bbox_inches="tight")
    plt.close(fig)


def fig_score_decision(
    baseline: ScoredBuffer,
    candidate: ScoredBuffer,
    ringing: ScoredBuffer,
    out_path: str,
    *,
    hardware_note: str,
) -> None:
    """Bar breakdown + accept/reject narrative."""
    fig = plt.figure(figsize=(13.5, 8.2), facecolor="#fbfaf8")
    fig.suptitle(
        "Ladder decision: decompose the score, then apply the gate",
        fontsize=14,
        fontweight="bold",
        color=PALETTE["ink"],
    )

    cases = [baseline, candidate, ringing]
    labels = [c.label for c in cases]
    peaks = [c.peak for c in cases]
    rms_terms = [c.rms_term for c in cases]
    scores = [c.score for c in cases]

    ax = fig.add_subplot(2, 1, 1)
    _style_ax(ax)
    x = np.arange(len(cases))
    w = 0.55
    ax.bar(x, peaks, w, label="peak(|ferr|)", color=PALETTE["peak"])
    ax.bar(
        x,
        rms_terms,
        w,
        bottom=peaks,
        label="2 × RMS",
        color=PALETTE["rms"],
    )
    for i, c in enumerate(cases):
        color = PALETTE["fail"] if c.unstable else PALETTE["pass"]
        ax.text(
            i,
            scores[i] + max(scores) * 0.03,
            f"{'FAIL' if c.unstable else 'PASS'}\n{c.score:.5f}",
            ha="center",
            va="bottom",
            fontsize=9,
            color=color,
            fontweight="bold",
        )
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylabel("score contribution (mm)", fontsize=10)
    ax.legend(loc="upper left", fontsize=9)
    ax.set_ylim(0, max(scores) * 1.28)

    # Decision table
    ax2 = fig.add_subplot(2, 1, 2)
    ax2.axis("off")
    improve = (baseline.score - candidate.score) / baseline.score * 100.0
    rows = [
        [
            "Step",
            "Gate",
            "Score",
            "Δ vs baseline",
            "Engine action",
        ],
        [
            baseline.label,
            "PASS",
            f"{baseline.score:.5f}",
            "—",
            "reference (backup preset)",
        ],
        [
            candidate.label,
            "PASS",
            f"{candidate.score:.5f}",
            f"{improve:+.1f}%",
            "ACCEPT (≥3% better + stable)",
        ],
        [
            ringing.label,
            "FAIL",
            f"{ringing.score:.5f}",
            f"{(baseline.score - ringing.score) / baseline.score * 100.0:+.1f}%",
            "REJECT — back off / try notch",
        ],
    ]
    table = ax2.table(
        cellText=rows[1:],
        colLabels=rows[0],
        loc="center",
        cellLoc="left",
        colWidths=[0.22, 0.1, 0.14, 0.16, 0.38],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9.5)
    table.scale(1.0, 1.7)
    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor("#c5ccd4")
        if r == 0:
            cell.set_facecolor("#efe8df")
            cell.set_text_props(fontweight="bold", color=PALETTE["ink"])
        elif c == 1:
            txt = cell.get_text().get_text()
            cell.set_text_props(
                color=PALETTE["pass"] if txt == "PASS" else PALETTE["fail"],
                fontweight="bold",
            )
        else:
            cell.set_facecolor("#ffffff")

    ax2.text(
        0.0,
        -0.05,
        hardware_note,
        transform=ax2.transAxes,
        fontsize=9,
        color=PALETTE["muted"],
        va="top",
        wrap=True,
    )
    fig.tight_layout(rect=[0, 0.08, 1, 0.95])
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def fig_short_stroke_lesson(out_path: str) -> None:
    """Show why gate_min_hz ignores stimulus harmonics on short Y strokes."""
    plant = SimPlant(
        resonance_hz=180.0,
        resonance_gain_threshold_hz=200.0,  # keep healthy — no mech resonance
        critical_speed_hz=250.0,
        noise_units=0.00025,
    )
    axis = "Y"
    spec = DEFAULT_STIMULI[axis]
    params = dict(SIM_BASELINE)
    params.update(
        {
            "speed_gain_hz": 40.0,
            "pos_gain_rad_s": 50.0,
            "integral_ms": 10.0,
        }
    )
    samples = plant.ferr_buffer(spec, 15.0, params, 1000.0, seed=7)
    cfg = OneClickConfig(axis=axis, stimulus=spec)
    proper = gate_min_hz_for(axis, cfg)
    naive_min = 25.0

    naive = analyze_ferr_resonance(
        samples, axis=axis, fs_hz=1000.0, min_hz=naive_min
    )
    fixed = analyze_ferr_resonance(
        samples, axis=axis, fs_hz=1000.0, min_hz=proper
    )

    fig, axes = plt.subplots(
        1, 2, figsize=(13.5, 5.2), facecolor="#fbfaf8", sharey=True
    )
    fig.suptitle(
        "Lesson from hardware/sim: short strokes fool a naive resonance gate\n"
        f"Y stimulus {spec.stroke:g} mm @ F{spec.feed:g} → leg {spec.leg_time_s():.3f}s "
        f"· proper gate_min_hz = max(25, 6/leg) = {proper:.0f} Hz",
        fontsize=12,
        fontweight="bold",
        color=PALETTE["ink"],
    )
    freqs, mag = compute_spectrum(samples, fs_hz=1000.0)

    # Historical bug: prominence-only + fixed 25 Hz floor (no amp floor).
    # Current engine: wider gate_min_hz AND magnitude ≥ amp floor.
    amp_floor = max(0.001, 0.10 * float(fixed.rms))
    naive_old_style_trip = (
        naive.dominant is not None and naive.dominant.prominence >= 4.0
    )
    fixed_trips = (
        fixed.dominant is not None
        and fixed.dominant.prominence >= 4.0
        and fixed.dominant.magnitude >= amp_floor
    )

    panels = (
        (
            axes[0],
            naive,
            naive_min,
            PALETTE["fail"] if naive_old_style_trip else PALETTE["pass"],
            (
                f"Old gate (prominence only, min_hz={naive_min:.0f}) → "
                f"FALSE FAIL at {naive.dominant.freq_hz:.0f} Hz"
                if naive_old_style_trip and naive.dominant is not None
                else f"Naive min_hz={naive_min:.0f}"
            ),
            False,  # apply_amp_floor for marker coloring
        ),
        (
            axes[1],
            fixed,
            proper,
            PALETTE["pass"] if not fixed_trips else PALETTE["fail"],
            (
                f"Engine gate_min_hz={proper:.0f} + amp floor → no trip"
                if not fixed_trips
                else f"Engine gate_min_hz={proper:.0f} → FAIL"
            ),
            True,
        ),
    )
    for ax, report, gmin, color, title, use_amp_floor in panels:
        _style_ax(ax)
        ax.fill_betweenx(
            [0, float(np.max(mag)) * 1.05],
            0,
            gmin,
            color=PALETTE["band"],
            alpha=0.95,
            label=f"ignored < {gmin:.0f} Hz",
        )
        ax.plot(freqs, mag, color=PALETTE["ink"], lw=1.0)
        ax.axhline(
            amp_floor,
            color=PALETTE["accent"],
            ls=":",
            lw=1.2,
            label=f"amp floor {amp_floor:.4g}",
        )
        if report.dominant is not None:
            trips = (
                report.dominant.prominence >= 4.0
                and (
                    (not use_amp_floor)
                    or report.dominant.magnitude >= amp_floor
                )
            )
            ax.plot(
                report.dominant.freq_hz,
                report.dominant.magnitude,
                "o",
                color=PALETTE["fail"] if trips else PALETTE["pass"],
                ms=8,
                label=(
                    f"dom {report.dominant.freq_hz:.0f} Hz "
                    f"×{report.dominant.prominence:.0f}"
                ),
            )
        ax.set_xlim(0, 200)
        ax.set_title(title, fontsize=9.5, color=color, loc="left")
        ax.set_xlabel("Hz")
        ax.set_ylabel("|FFT|")
        ax.legend(loc="upper right", fontsize=7, framealpha=0.9)
        ax.text(
            0.02,
            0.95,
            (
                "Old rule: prominence ≥4× median only\n"
                "(no amp floor — stimulus harmonics trip)"
                if not use_amp_floor
                else "Engine: prominence ≥4× AND mag ≥ amp floor\n"
                f"(amp floor = max(0.001, 10% RMS) = {amp_floor:.4g})"
            ),
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=8,
            color=PALETTE["muted"],
            bbox=dict(
                boxstyle="round,pad=0.3", facecolor="white", edgecolor="#c5ccd4"
            ),
        )

    fig.tight_layout(rect=[0, 0.02, 1, 0.88])
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def fig_ladder_from_campaign(scores: List[Tuple[str, float, bool]], out_path: str) -> None:
    fig, ax = plt.subplots(figsize=(12.5, 4.8), facecolor="#fbfaf8")
    _style_ax(ax)
    xs = np.arange(len(scores))
    vals = [s for _, s, _ in scores]
    colors = [PALETTE["fail"] if u else PALETTE["pass"] for _, _, u in scores]
    ax.plot(xs, vals, color="#9aa3ab", lw=1.2, zorder=1)
    ax.scatter(xs, vals, c=colors, s=55, zorder=2)
    for i, (label, score, unstable) in enumerate(scores):
        ax.annotate(
            label,
            (i, score),
            textcoords="offset points",
            xytext=(0, 8 if i % 2 == 0 else -14),
            ha="center",
            fontsize=7,
            color=PALETTE["muted"],
            rotation=25 if len(label) > 10 else 0,
        )
    ax.set_title(
        "Sim campaign score trail (PASS green / FAIL red) — same metric the engine journals",
        fontsize=12,
        fontweight="bold",
        color=PALETTE["ink"],
        loc="left",
    )
    ax.set_ylabel("score = peak + 2×RMS (mm)")
    ax.set_xticks([])
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Build cases
# ---------------------------------------------------------------------------


def build_sim_cases() -> Tuple[List[ScoredBuffer], List[Tuple[str, float, bool]]]:
    """Buffers at soft / best-like / ringing gains for axis X."""
    plant = SimPlant(
        resonance_hz=180.0,
        resonance_gain_threshold_hz=95.0,
        critical_speed_hz=160.0,
        noise_units=0.00025,
        resonance_base_amp=0.0045,
    )
    axis = "X"
    spec = DEFAULT_STIMULI[axis]
    cfg = OneClickConfig(axis=axis, stimulus=spec)
    fs = 1000.0

    soft = dict(SIM_BASELINE)
    soft.update(
        {
            "speed_gain_hz": 40.0,
            "pos_gain_rad_s": 55.0,
            "integral_ms": 12.0,
        }
    )
    # Shape like hardware best (150 / 224.6 / 5) but stay under sim critical.
    best = dict(SIM_BASELINE)
    best.update(
        {
            "speed_gain_hz": 88.0,
            "pos_gain_rad_s": 176.0,
            "integral_ms": 5.0,
        }
    )
    ring = dict(SIM_BASELINE)
    ring.update(
        {
            "speed_gain_hz": 120.0,
            "pos_gain_rad_s": 200.0,
            "integral_ms": 5.0,
        }
    )

    cases: List[ScoredBuffer] = []
    for label, params, note, seed in (
        (
            "1 · soft baseline",
            soft,
            "Starting gains — large tracking humps, score high, gate PASS",
            11,
        ),
        (
            "2 · climbed gains (stable)",
            best,
            "After speed+position ladder — smaller FERR, still below resonance threshold",
            12,
        ),
        (
            "3 · over-gain (rings)",
            ring,
            "Past resonance_gain_threshold — 180 Hz tone trips the gate → reject / notch / back off",
            13,
        ),
    ):
        buf = plant.ferr_buffer(spec, 40.0, params, fs, seed=seed)
        cases.append(
            score_samples(
                buf,
                axis=axis,
                label=label,
                fs_hz=fs,
                note=note,
                gains=params,
                cfg=cfg,
            )
        )

    # Mini ladder trail for the score plot
    trail: List[Tuple[str, float, bool]] = []
    speed = 40.0
    pos = 55.0
    for step in range(8):
        params = dict(SIM_BASELINE)
        params.update(
            {
                "speed_gain_hz": speed,
                "pos_gain_rad_s": pos,
                "integral_ms": 8.0,
            }
        )
        buf = plant.ferr_buffer(spec, 40.0, params, fs, seed=20 + step)
        sb = score_samples(
            buf,
            axis=axis,
            label=f"spd_{speed:.0f}",
            fs_hz=fs,
            gains=params,
            cfg=cfg,
        )
        trail.append((f"{speed:.0f}Hz/{pos:.0f}", sb.score, sb.unstable))
        if sb.unstable:
            break
        speed *= 1.25
        pos = min(pos * 1.2, speed * 2.0)

    return cases, trail


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        default=os.path.join(ROOT, "docs", "assets", "auto_tune_scoring"),
        help="Directory for PNGs, CSVs, and summary JSON",
    )
    parser.add_argument(
        "--also",
        action="append",
        default=[],
        help="Extra output directory (e.g. /opt/cursor/artifacts/...)",
    )
    parser.add_argument(
        "--session-csv",
        default=os.path.join(ROOT, "config", "logging", "example_session.csv"),
    )
    return parser.parse_args()


def copy_tree_files(src_dir: str, dest_dir: str) -> None:
    os.makedirs(dest_dir, exist_ok=True)
    for name in os.listdir(src_dir):
        src = os.path.join(src_dir, name)
        if os.path.isfile(src):
            with open(src, "rb") as r, open(os.path.join(dest_dir, name), "wb") as w:
                w.write(r.read())


def main() -> int:
    args = parse_args()
    out = args.out_dir
    os.makedirs(out, exist_ok=True)
    demo_csv_dir = os.path.join(
        ROOT, "config", "logging", "auto_tune_scoring_demo"
    )
    os.makedirs(demo_csv_dir, exist_ok=True)

    session = load_example_session(args.session_csv)
    session_scores = fig_formula_and_session(
        session, os.path.join(out, "01_score_formula_example_session.png")
    )

    cases, trail = build_sim_cases()
    demo_names = ("soft_baseline", "climbed_stable", "over_gain_ring")
    for i, sb in enumerate(cases):
        write_ferr_csv(
            os.path.join(demo_csv_dir, f"x_{demo_names[i]}.csv"),
            sb.samples,
            sb.fs_hz,
        )

    fig_fft_gate_breakdown(
        cases, os.path.join(out, "02_fft_gate_baseline_best_ring.png")
    )
    hardware_note = (
        "Hardware record (committed presets, journals gitignored):\n"
        "• X one_click_best_20260712 — score 0.00663 at 150 Hz / 224.6 rad/s / 5.0 ms "
        "(~49% better than baseline; verify HF false-fail then keep-best salvage).\n"
        "• Y one_click_best_20260712 — ~39% better at 164.6 Hz / 60 rad/s / 3.5 ms.\n"
        "Sim traces above use the same score + gate code paths; plant thresholds are "
        "caricatured so the PASS→PASS→FAIL story fits one figure."
    )
    fig_score_decision(
        cases[0],
        cases[1],
        cases[2],
        os.path.join(out, "03_ladder_accept_reject.png"),
        hardware_note=hardware_note,
    )
    fig_short_stroke_lesson(os.path.join(out, "04_short_stroke_gate_lesson.png"))
    fig_ladder_from_campaign(
        trail, os.path.join(out, "05_sim_campaign_score_trail.png")
    )

    summary = {
        "score_formula": "peak_abs + 2.0 * rms",
        "improvement_min_pct": 3.0,
        "example_session": {
            sb.axis: {
                "peak": sb.peak,
                "rms": sb.rms,
                "score": sb.score,
                "n_samples": int(sb.samples.size),
                "fs_hz": sb.fs_hz,
                "gate": "FAIL" if sb.unstable else "PASS",
                "why": sb.unstable_why,
            }
            for sb in session_scores
        },
        "sim_cases": [
            {
                "label": sb.label,
                "peak": sb.peak,
                "rms": sb.rms,
                "score": sb.score,
                "gate_min_hz": sb.gate_min_hz,
                "unstable": sb.unstable,
                "why": sb.unstable_why,
                "hf": float(sb.report.hf_energy_ratio),
                "ring": float(sb.report.ring_score),
                "gains": {
                    k: sb.gains.get(k)
                    for k in ("speed_gain_hz", "pos_gain_rad_s", "integral_ms")
                }
                if sb.gains
                else None,
            }
            for sb in cases
        ],
        "hardware_presets": {
            "X": "config/tuning/presets/X/one_click_best_20260712.json",
            "Y": "config/tuning/presets/Y/one_click_best_20260712.json",
        },
        "figures": [
            "01_score_formula_example_session.png",
            "02_fft_gate_baseline_best_ring.png",
            "03_ladder_accept_reject.png",
            "04_short_stroke_gate_lesson.png",
            "05_sim_campaign_score_trail.png",
        ],
    }
    with open(os.path.join(out, "summary.json"), "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
        handle.write("\n")

    readme = os.path.join(out, "README.md")
    with open(readme, "w", encoding="utf-8") as handle:
        handle.write(
            "# Auto-tune FERR scoring visuals\n\n"
            "Generated by `scripts/visualize_auto_tune_scoring.py`.\n\n"
            "| Figure | What it shows |\n"
            "|--------|----------------|\n"
            "| `01_score_formula_example_session.png` | "
            "`score = peak + 2×RMS` on real `example_session.csv` FERR |\n"
            "| `02_fft_gate_baseline_best_ring.png` | "
            "Time + FFT with ignored motion-harmonic band, amp floor, PASS/FAIL |\n"
            "| `03_ladder_accept_reject.png` | "
            "Score stack + accept/reject table |\n"
            "| `04_short_stroke_gate_lesson.png` | "
            "Why Y short strokes need `gate_min_hz ≈ 6/leg_time` |\n"
            "| `05_sim_campaign_score_trail.png` | "
            "Score vs gain climb until the gate trips |\n\n"
            "Demo FERR CSVs: `config/logging/auto_tune_scoring_demo/`.\n"
        )

    for extra in args.also:
        copy_tree_files(out, extra)
        print(f"also wrote copies to {extra}")

    print(f"wrote figures to {out}")
    for name in summary["figures"]:
        print(f"  - {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
