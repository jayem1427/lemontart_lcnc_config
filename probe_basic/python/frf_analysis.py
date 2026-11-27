"""Sensitivity function |S(f)| from a captured move: a measured stability margin.

For a position loop, following error E = S(f) x command R. With the realtime
capture we have both (joint motor-pos-cmd and drive 60F4), so

    |S(f)| ~= |P_RE(f) / P_RR(f)|      (H1 estimate, Welch averaging)

wherever the move put enough energy into R for the two to be coherent. The
peak Ms of |S| bounds the margins of the loop, whatever the plant:

    gain margin  >= Ms / (Ms - 1)          (Ms 2.0 -> >= 6 dB)
    phase margin >= 2 asin(1 / (2 Ms))     (Ms 2.0 -> >= 29 deg)

Ms <= 2 is the usual "well damped" target; Ms > 2.5 means the loop is close
to ringing at f(Ms). A pure delay between LinuxCNC's command and the drive's
interpolated target (EtherCAT cycle) changes only the phase of R, so |S| is
unaffected.

Both signals are differenced before the FFT. That leaves S unchanged (both are
multiplied by the same jw) but removes the ramp, which otherwise leaks across
the spectrum.

Only numpy is needed. This is a *measurement* of margin, not a model; the
engine journals it and can gate on it (``ms_max``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None  # type: ignore


@dataclass
class SensitivityReport:
    fs_hz: float
    n_samples: int
    coherent_bins: int
    ms: Optional[float] = None  # peak |S| over coherent bins
    f_ms_hz: Optional[float] = None
    bandwidth_hz: Optional[float] = None  # first coherent f where |S| >= 0.707
    gain_margin_db_min: Optional[float] = None
    phase_margin_deg_min: Optional[float] = None
    reason: str = ""
    freqs_hz: List[float] = field(default_factory=list)
    s_mag: List[float] = field(default_factory=list)
    coherence: List[float] = field(default_factory=list)

    def ok(self) -> bool:
        return self.ms is not None

    def summary(self) -> str:
        if self.ms is None:
            return f"|S| n/a ({self.reason})"
        bw = f", bw~{self.bandwidth_hz:.0f} Hz" if self.bandwidth_hz else ""
        return (
            f"Ms {self.ms:.2f} @ {self.f_ms_hz:.0f} Hz "
            f"(GM>={self.gain_margin_db_min:.1f} dB, "
            f"PM>={self.phase_margin_deg_min:.0f} deg{bw}; "
            f"{self.coherent_bins} coherent bins)"
        )


def margins_from_ms(ms: float):
    """(gain margin dB lower bound, phase margin deg lower bound)."""
    if ms <= 1.0:
        return math.inf, 180.0
    gm = 20.0 * math.log10(ms / (ms - 1.0))
    pm = math.degrees(2.0 * math.asin(min(1.0, 1.0 / (2.0 * ms))))
    return gm, pm


def _welch_cross(x, y, fs, nperseg):
    step = nperseg // 2
    win = np.hanning(nperseg)
    scale = 1.0 / (fs * (win * win).sum())
    pxx = None
    pyy = None
    pxy = None
    count = 0
    for start in range(0, len(x) - nperseg + 1, step):
        xs = x[start:start + nperseg]
        ys = y[start:start + nperseg]
        xs = (xs - xs.mean()) * win
        ys = (ys - ys.mean()) * win
        fx = np.fft.rfft(xs)
        fy = np.fft.rfft(ys)
        a = (fx.conj() * fx).real
        b = (fy.conj() * fy).real
        c = fx.conj() * fy
        if pxx is None:
            pxx, pyy, pxy = a, b, c
        else:
            pxx = pxx + a
            pyy = pyy + b
            pxy = pxy + c
        count += 1
    if count == 0:
        return None
    freqs = np.fft.rfftfreq(nperseg, d=1.0 / fs)
    return freqs, pxx * scale / count, pyy * scale / count, pxy * scale / count, count


def sensitivity(
    cmd: Sequence[float],
    ferr: Sequence[float],
    fs_hz: float,
    *,
    nperseg: int = 512,
    f_min: float = 5.0,
    f_max_frac: float = 0.45,
    min_coherence: float = 0.7,
    min_bins: int = 3,
    min_cmd_power_frac: float = 1e-4,
) -> SensitivityReport:
    """Estimate |S(f)| = |E/R| from a command and following-error capture.

    ``cmd`` and ``ferr`` must be in the same units (mm, or deg) and aligned
    sample for sample (same capture rows).
    """
    if np is None:
        return SensitivityReport(fs_hz, 0, 0, reason="numpy missing")
    x = np.asarray(cmd, dtype=float)
    y = np.asarray(ferr, dtype=float)
    n = min(x.size, y.size)
    rep = SensitivityReport(fs_hz=float(fs_hz), n_samples=int(n), coherent_bins=0)
    if n < nperseg * 2:
        rep.reason = f"too few samples ({n} < {nperseg * 2})"
        return rep
    x = np.diff(x[:n])
    y = np.diff(y[:n])
    if not (np.isfinite(x).all() and np.isfinite(y).all()):
        rep.reason = "non-finite samples"
        return rep
    res = _welch_cross(x, y, float(fs_hz), nperseg)
    if res is None:
        rep.reason = "no segments"
        return rep
    freqs, pxx, pyy, pxy, _count = res
    with np.errstate(divide="ignore", invalid="ignore"):
        h = np.abs(pxy) / pxx
        coh = (np.abs(pxy) ** 2) / (pxx * pyy)
    band = (freqs >= f_min) & (freqs <= f_max_frac * fs_hz)
    strong = pxx >= min_cmd_power_frac * float(np.max(pxx[band])) if band.any() else band
    good = band & strong & np.isfinite(h) & np.isfinite(coh) & (coh >= min_coherence)
    rep.coherent_bins = int(good.sum())
    rep.freqs_hz = [float(f) for f in freqs[band]]
    rep.s_mag = [float(v) for v in np.nan_to_num(h[band])]
    rep.coherence = [float(v) for v in np.nan_to_num(coh[band])]
    if rep.coherent_bins < min_bins:
        rep.reason = (
            f"only {rep.coherent_bins} coherent bins (the move did not excite "
            "enough frequencies)"
        )
        return rep
    idx = np.nonzero(good)[0]
    k = idx[int(np.argmax(h[idx]))]
    rep.ms = float(h[k])
    rep.f_ms_hz = float(freqs[k])
    crossing = idx[h[idx] >= 1.0 / math.sqrt(2.0)]
    rep.bandwidth_hz = float(freqs[crossing[0]]) if crossing.size else None
    rep.gain_margin_db_min, rep.phase_margin_deg_min = margins_from_ms(rep.ms)
    rep.reason = "ok"
    return rep
