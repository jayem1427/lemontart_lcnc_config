"""FFT / resonance scoring for drive FERR buffers (Servo Tuning).

Designed for ~1 kHz CiA 60F4 samples from FerrPlotWidget. Nyquist ≈ 500 Hz,
so only mechanical modes below that are visible — still enough for most
table / ballscrew resonances; higher motor modes need drive adaptive notch
or a torque channel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None  # type: ignore

# A6: frequency 8000 Hz disables a torque-loop notch.
NOTCH_DISABLED_HZ = 8000.0
DEFAULT_FS_HZ = 1000.0


@dataclass
class ResonancePeak:
    freq_hz: float
    magnitude: float
    prominence: float


@dataclass
class ResonanceReport:
    axis: str
    fs_hz: float
    n_samples: float
    duration_s: float
    peak_abs: float
    rms: float
    dominant: Optional[ResonancePeak]
    peaks: List[ResonancePeak] = field(default_factory=list)
    hf_energy_ratio: float = 0.0
    ring_score: float = 0.0
    stable: bool = True
    reason: str = ""
    freqs_hz: Optional[Any] = None  # np.ndarray | None
    magnitude: Optional[Any] = None
    suggested_notch: Dict[str, float] = field(default_factory=dict)

    def summary_line(self) -> str:
        if self.n_samples < 64:
            return f"{self.axis}: need ≥64 samples (have {int(self.n_samples)})"
        dom = self.dominant
        if dom is None:
            return (
                f"{self.axis}: stable · peak={self.peak_abs:g} rms={self.rms:g} "
                f"HF={self.hf_energy_ratio:.1%} · no strong resonance peak"
            )
        gate = "PASS" if self.stable else "FAIL"
        return (
            f"{self.axis}: {gate} · dom={dom.freq_hz:.1f} Hz "
            f"(mag={dom.magnitude:.3g}) · peak={self.peak_abs:g} "
            f"rms={self.rms:g} HF={self.hf_energy_ratio:.1%} "
            f"ring={self.ring_score:.2f}"
        )


def _require_numpy() -> None:
    if np is None:
        raise RuntimeError(
            "numpy is required for resonance FFT "
            "(install python3-numpy / python3-pyqtgraph)"
        )


def compute_spectrum(
    samples: Sequence[float],
    fs_hz: float = DEFAULT_FS_HZ,
) -> Tuple[Any, Any]:
    """Return (freqs_hz, magnitude) for a real FFT of demeaned + Hann-windowed data."""
    _require_numpy()
    x = np.asarray(samples, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 8:
        return np.array([]), np.array([])
    x = x - np.mean(x)
    window = np.hanning(x.size)
    # Preserve amplitude scale roughly vs unwindowed coherent gain.
    scale = 2.0 / max(np.sum(window), 1e-12)
    spectrum = np.abs(np.fft.rfft(x * window)) * scale
    freqs = np.fft.rfftfreq(x.size, d=1.0 / float(fs_hz))
    return freqs, spectrum


def find_resonance_peaks(
    freqs_hz: Any,
    magnitude: Any,
    *,
    min_hz: float = 25.0,
    max_hz: Optional[float] = None,
    max_peaks: int = 5,
    min_prominence_ratio: float = 4.0,
) -> List[ResonancePeak]:
    """Pick local maxima above a noise-floor prominence threshold."""
    _require_numpy()
    if freqs_hz is None or magnitude is None or len(freqs_hz) < 5:
        return []
    freqs = np.asarray(freqs_hz, dtype=float)
    mag = np.asarray(magnitude, dtype=float)
    nyquist = float(freqs[-1]) if len(freqs) else 0.0
    hi = nyquist * 0.95 if max_hz is None else min(float(max_hz), nyquist)
    lo = max(float(min_hz), 0.0)
    mask = (freqs >= lo) & (freqs <= hi)
    if not np.any(mask):
        return []

    band_f = freqs[mask]
    band_m = mag[mask]
    if band_m.size < 5:
        return []

    # Robust noise floor from median of band (ignore DC already removed).
    floor = float(np.median(band_m))
    if floor <= 0.0:
        floor = float(np.mean(band_m)) + 1e-15
    thresh = floor * float(min_prominence_ratio)

    candidates: List[ResonancePeak] = []
    for i in range(1, band_m.size - 1):
        if band_m[i] >= band_m[i - 1] and band_m[i] >= band_m[i + 1]:
            if band_m[i] >= thresh:
                candidates.append(
                    ResonancePeak(
                        freq_hz=float(band_f[i]),
                        magnitude=float(band_m[i]),
                        prominence=float(band_m[i] / floor),
                    )
                )
    candidates.sort(key=lambda p: p.magnitude, reverse=True)
    return candidates[: max(1, int(max_peaks))]


def hf_energy_ratio(
    freqs_hz: Any,
    magnitude: Any,
    *,
    split_hz: float = 40.0,
) -> float:
    """Fraction of spectral energy above split_hz (ring / buzz indicator)."""
    _require_numpy()
    if freqs_hz is None or magnitude is None or len(freqs_hz) < 2:
        return 0.0
    freqs = np.asarray(freqs_hz, dtype=float)
    mag = np.asarray(magnitude, dtype=float)
    power = mag * mag
    total = float(np.sum(power))
    if total <= 0.0:
        return 0.0
    return float(np.sum(power[freqs >= split_hz]) / total)


def ring_score(samples: Sequence[float], fs_hz: float = DEFAULT_FS_HZ) -> float:
    """Rough post-transient HF activity: std of high-passed-ish diff energy.

    Higher = more sparkly / oscillatory content relative to overall amplitude.
    """
    _require_numpy()
    x = np.asarray(samples, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 16:
        return 0.0
    # First difference emphasizes HF; normalize by signal RMS.
    d = np.diff(x)
    rms = float(np.sqrt(np.mean(x * x))) + 1e-15
    return float(np.sqrt(np.mean(d * d)) / rms)


def suggest_manual_notch(
    freq_hz: float,
    *,
    notch_index: int = 3,
    width_pct: float = 5.0,
    depth_pct: float = 10.0,
) -> Dict[str, float]:
    """Pending-map for a manual A6 notch set (default 3rd — leaves 1/2 for adaptive).

    Depth: lower % = deeper notch (A6 C01.4x depth level).
    Frequency 8000 disables the notch.
    """
    n = int(notch_index)
    if n < 1 or n > 5:
        raise ValueError("notch_index must be 1..5")
    # Keys match PARAM_DEFS: notch{n}_freq_hz / _width_pct / _depth_pct
    freq = float(max(10.0, min(8000.0, round(freq_hz))))
    if abs(freq - NOTCH_DISABLED_HZ) < 0.5:
        freq = 7999.0
    return {
        f"notch{n}_freq_hz": freq,
        f"notch{n}_width_pct": float(max(0.0, min(400.0, width_pct))),
        f"notch{n}_depth_pct": float(max(1.0, min(100.0, depth_pct))),
    }


def analyze_ferr_resonance(
    samples: Sequence[float],
    *,
    axis: str = "X",
    fs_hz: float = DEFAULT_FS_HZ,
    min_hz: float = 25.0,
    max_hz: Optional[float] = None,
    hf_fail: float = 0.35,
    ring_fail: float = 0.85,
    min_prominence_ratio: float = 4.0,
) -> ResonanceReport:
    """Full resonance report from a FERR sample buffer."""
    _require_numpy()
    x = np.asarray(samples, dtype=float)
    x = x[np.isfinite(x)]
    n = int(x.size)
    duration = n / float(fs_hz) if fs_hz > 0 else 0.0
    if n == 0:
        return ResonanceReport(
            axis=axis,
            fs_hz=float(fs_hz),
            n_samples=0,
            duration_s=0.0,
            peak_abs=0.0,
            rms=0.0,
            dominant=None,
            stable=False,
            reason="no samples — START PLOT and run x_resonance.ngc first",
        )

    peak_abs = float(np.max(np.abs(x)))
    rms = float(np.sqrt(np.mean(x * x)))
    freqs, mag = compute_spectrum(x, fs_hz=fs_hz)
    peaks = find_resonance_peaks(
        freqs,
        mag,
        min_hz=min_hz,
        max_hz=max_hz,
        min_prominence_ratio=min_prominence_ratio,
    )
    hf = hf_energy_ratio(freqs, mag)
    ring = ring_score(x, fs_hz=fs_hz)
    dominant = peaks[0] if peaks else None

    stable = True
    reasons: List[str] = []
    if n < 64:
        stable = False
        reasons.append(f"short buffer ({n} samples)")
    if dominant is not None and dominant.prominence >= min_prominence_ratio:
        # A clear spectral peak is a resonance candidate — gate FAIL for auto-tune.
        stable = False
        reasons.append(f"peak at {dominant.freq_hz:.1f} Hz")
    if hf >= hf_fail:
        stable = False
        reasons.append(f"HF energy {hf:.0%}")
    if ring >= ring_fail:
        stable = False
        reasons.append(f"ring score {ring:.2f}")
    if not reasons:
        reasons.append("no strong resonance signature")

    suggested: Dict[str, float] = {}
    if dominant is not None and 40.0 <= dominant.freq_hz <= 500.0:
        suggested = suggest_manual_notch(dominant.freq_hz, notch_index=3)

    return ResonanceReport(
        axis=axis,
        fs_hz=float(fs_hz),
        n_samples=float(n),
        duration_s=duration,
        peak_abs=peak_abs,
        rms=rms,
        dominant=dominant,
        peaks=peaks,
        hf_energy_ratio=hf,
        ring_score=ring,
        stable=stable,
        reason="; ".join(reasons),
        freqs_hz=freqs,
        magnitude=mag,
        suggested_notch=suggested,
    )


def format_resonance_text(report: ResonanceReport) -> str:
    """Clipboard / log text for COPY RESONANCE."""
    lines = [
        "SERVO RESONANCE ANALYSIS",
        f"Axis: {report.axis}",
        f"Samples: {int(report.n_samples)} @ {report.fs_hz:g} Hz "
        f"({report.duration_s:.2f} s)",
        f"Peak abs: {report.peak_abs:g}",
        f"RMS: {report.rms:g}",
        f"HF energy (≥40 Hz): {report.hf_energy_ratio:.1%}",
        f"Ring score: {report.ring_score:.3f}",
        f"Stability gate: {'PASS' if report.stable else 'FAIL'}",
        f"Reason: {report.reason}",
        "",
        "Peaks (Hz, mag, prominence):",
    ]
    if not report.peaks:
        lines.append("  (none above threshold)")
    else:
        for i, p in enumerate(report.peaks, 1):
            lines.append(
                f"  {i}. {p.freq_hz:.1f} Hz  mag={p.magnitude:.4g}  "
                f"×{p.prominence:.1f} floor"
            )
    if report.suggested_notch:
        lines.append("")
        lines.append("Suggested manual notch (3rd set — leaves 1/2 for adaptive):")
        for key, val in report.suggested_notch.items():
            lines.append(f"  {key}: {val:g}")
        lines.append(
            "Apply via Pending → APPLY, or ANALYZE → USE SUGGESTED NOTCH 3."
        )
    lines.append("")
    lines.append(
        "Stimulus: nc_files/x_resonance.ngc (or axis equivalent). "
        "Nyquist limited by FERR sample rate (~500 Hz @ 1 kHz)."
    )
    return "\n".join(lines)
