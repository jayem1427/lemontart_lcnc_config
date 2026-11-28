"""One-click per-axis auto-tuning for StepperOnline A6-EC servo drives.

Automates the manual gain ladder documented in docs/SERVO_TUNING.md, one axis at a
time, using the pieces this repo already trusts:

- SDO read/write with retry + verify        (a6_servo_tune.py)
- drive-native following error (CiA 60F4)   (lcec ferr-fb -> counts_to_unit)
- FFT stability gate + notch suggestion     (resonance_analysis.py)

The campaign for one axis:

    PREFLIGHT   sanity: EtherCAT reads OK, machine ON, interp idle, numpy up,
                envelope fits soft limits (when homed)
    BASELINE    read all SDOs, save a `pre_one_click_*` backup preset, measure
                the starting FERR with the stimulus move
    RESCUE      if the baseline is already unstable (ringing), soften speed
                gain / try a notch until the gate passes
    SPEED       climb C01.01 speed loop gain until the stability gate trips or
                improvement stalls, then back off to the last good value.
                A clear FFT resonance peak triggers an automatic 3rd-notch
                attempt (C01.46/47/48) before giving up on the climb.
    POSITION    climb C01.00 position loop gain toward ~2x speed gain (rad/s
                vs Hz rule of thumb from docs/SERVO_TUNING.md), same gating
    INTEGRAL    tighten C01.02 speed integral (lower ms = stronger) while RMS
                keeps improving and nothing rings
    VERIFY      re-measure with the final gains; if unstable, back off once,
                then revert to baseline if still bad
    FINALIZE    save a `one_click_*` preset on success and write the journal

Every step is journaled to ``logs/tuning/one_click/<stamp>_<axis>/`` as it
happens (crash-safe append), including raw FERR sample CSVs per measurement,
so failed runs can be analyzed afterwards. See docs/ONE_CLICK_TUNING.md.

Safety model:

- Writes go through apply_axis_params (machine OFF -> write+verify -> ON),
  the same hardened path as the Servo Tuning APPLY button.
- Only SDO keys that were successfully auto-read at baseline are ever written.
- Moves are short relative MDI strokes with a watchdog that aborts motion if
  |drive FERR| crosses a fraction of the 6065 fault window.
- Cancel or any error reverts every touched SDO to its baseline value.
- Nothing touches LinuxCNC joint FERROR / INI limits. Every SDO write is
  stored to drive EEPROM by the drive itself (A6-EC C13.10 "EtherCAT parameter
  storage" = 1, the factory default), exactly like the APPLY button; the
  backup preset is the undo.
"""

from __future__ import annotations

import json
import logging
import math
import os
import threading
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from a6_servo_tune import (  # noqa: E402
    ethercat_upload_u16,
    AXES,
    FOLLOWING_ERROR_AUTOTUNE,
    PARAM_BY_KEY,
    AxisTuneParams,
    apply_axis_params,
    axis_unit,
    counts_to_unit,
    drive_ferr_counts_halpin,
    hal_getp,
    hal_getp_s32,
    machine_is_on,
    read_axis_params,
    relax_following_error_for_tuning,
    repo_root,
    restore_following_error_run,
    save_preset,
)
from frf_analysis import sensitivity
from resonance_analysis import (
    ResonanceReport,
    analyze_ferr_resonance,
    np as _np,
    suggest_manual_notch,
)

try:
    import linuxcnc
except ImportError:  # pragma: no cover - only available under LinuxCNC
    linuxcnc = None  # type: ignore

LOG = logging.getLogger(__name__)

ENGINE_VERSION = "2.1"

# SDO keys the engine is allowed to touch. Everything else is read-only to us.
CORE_GAIN_KEYS = ("speed_gain_hz", "pos_gain_rad_s", "integral_ms")
NOTCH3_KEYS = ("notch3_freq_hz", "notch3_width_pct", "notch3_depth_pct")
MODE_KEY = "manual_mode"
FF_KEYS = ("torque_ff_pct",)
TOUCHABLE_KEYS = CORE_GAIN_KEYS + NOTCH3_KEYS + FF_KEYS + (MODE_KEY,)

NOTCH_DISABLED_HZ = 8000.0

# Score weighting: peak dominates practical ferror concerns, RMS captures
# buzz/offset. Both are in axis units (mm or deg). Lower is better.
SCORE_RMS_WEIGHT = 2.0

ProgressFn = Callable[[str, str], None]


class OneClickError(RuntimeError):
    """Campaign-fatal problem (preflight failure, SDO write failure, ...)."""


class OneClickCancelled(RuntimeError):
    """Operator pressed CANCEL — engine reverts and finalizes."""


# ---------------------------------------------------------------------------
# Stimulus
# ---------------------------------------------------------------------------


@dataclass
class StimulusSpec:
    """One repeatable back-and-forth move used for every measurement.

    Relative strokes from the position the axis is sitting at when the
    campaign starts, so it works regardless of work offsets. The same spec is
    reused for every step of a campaign — comparability matters more than the
    exact numbers.
    """

    axis: str
    stroke: float  # mm or deg, unsigned; direction picked in preflight
    feed: float  # mm/min or deg/min
    cycles: int = 3
    dwell_s: float = 0.25
    settle_s: float = 0.5

    def leg_time_s(self) -> float:
        if self.feed <= 0:
            return 1.0
        return abs(self.stroke) / (self.feed / 60.0)

    def total_time_s(self) -> float:
        per_leg = self.leg_time_s() + self.dwell_s
        return self.cycles * 2.0 * per_leg + self.settle_s

    def describe(self) -> str:
        unit = axis_unit(self.axis)
        return (
            f"{self.cycles}x 0<->{self.stroke:g} {unit} @ F{self.feed:g} "
            f"(~{self.total_time_s():.1f}s per measurement)"
        )


# Defaults sized for this mill (see ethercat_mill.ini limits). Shorter and a
# bit slower than the frozen *_tuning.ngc campaign moves so the accel
# transients still excite the loop but a first unstable pass cannot travel far.
DEFAULT_STIMULI: Dict[str, StimulusSpec] = {
    "X": StimulusSpec("X", stroke=40.0, feed=3000.0, cycles=3),
    "Y": StimulusSpec("Y", stroke=15.0, feed=10000.0, cycles=4),
    "Z": StimulusSpec("Z", stroke=10.0, feed=6000.0, cycles=4),
    "A": StimulusSpec("A", stroke=60.0, feed=3600.0, cycles=3),
}


# ---------------------------------------------------------------------------
# Config / profiles
# ---------------------------------------------------------------------------


@dataclass
class OneClickConfig:
    axis: str
    profile: str = "balanced"
    stimulus: Optional[StimulusSpec] = None
    sample_hz: float = 1000.0
    dry_run: bool = False

    # Ladder shape
    speed_step_ratio: float = 1.25
    speed_gain_max_hz: float = 200.0
    # A6 rule of thumb: speed gain above ~1/4 of the torque filter cutoff
    # fights the filter's phase lag. 0 disables the cap.
    speed_vs_filter_cap: float = 0.25
    pos_step_ratio: float = 1.2
    pos_to_speed_ratio: float = 2.0  # C01.00 rad/s ~ 2x C01.01 Hz
    pos_gain_max_rad_s: float = 400.0
    integral_step_ratio: float = 0.7
    integral_min_ms: float = 2.0
    max_steps_per_phase: int = 8
    max_stall_steps: int = 2
    backoff_ratio: float = 0.75  # verify backoff / rescue softening step
    rescue_max_steps: int = 3
    # Stability margin (v2): when a ladder step rings, the gain is set to
    # margin_ratio x the FIRST ringing gain, not to the last stable step.
    # 0.55 is ~5 dB of gain margin; the old "last stable step" was ~2 dB.
    margin_ratio: float = 0.55
    # Baseline is measured this many times; the run-to-run spread sets the
    # smallest score change that counts as a real improvement.
    baseline_repeats: int = 3
    # Unscored warm-up moves before the baseline repeats. The first move of a
    # campaign can carry a start-up transient (Z 2026-11-27: 405 um / 198 %
    # torque on baseline_1, then 49 um on the next two), which inflated the
    # spread to 416 % and the improvement bar to 15 %. 0 = off.
    baseline_warmup: int = 1
    noise_k: float = 2.0  # improvement must beat noise_k x spread (%)
    max_noise_threshold_pct: float = 15.0
    # Torque guard (% rated, 6077). A clipped torque hides instability.
    # Lowered at preflight to torque_guard_drive_ratio x the drive's 0x6072.
    torque_guard_pct: float = 250.0
    torque_guard_drive_ratio: float = 0.8
    # Sensitivity |S| from pos-cmd vs FERR (frf_analysis). 0 = report only;
    # >0 marks a step unstable when the measured peak Ms exceeds it.
    ms_max: float = 0.0
    frf_nperseg: int = 256
    # Torque feedforward phase (C01 torque_ff_pct). Runs only when the
    # drive's torque FF source is on; never turns the source on itself.
    ff_enabled: bool = True
    ff_step_ratio: float = 1.15
    ff_min_pct: float = 50.0
    ff_max_pct: float = 200.0
    ff_improve_min_pct: float = 3.0
    # Extra verify points, mm (deg for A) from the start position along the
    # tuned axis. Needs the axis homed; Z accepts only positive (upward)
    # offsets. Empty = verify at the start position only.
    verify_offsets: Tuple[float, ...] = ()
    # Standstill noise gate at verify (needs realtime capture).
    rest_capture_s: float = 1.0
    # Measured about the mean (AC rms): a vertical axis holds a steady
    # gravity torque (Z ~12 %) that is not oscillation.
    rest_torque_rms_max_pct: float = 5.0
    rest_ferr_rms_max: float = 0.002  # axis units (2 um)
    # Hardware behaviour
    live_writes: bool = False  # write gains with the drive enabled (test first!)
    allow_python_sampler: bool = False  # legacy ~300 Hz sampler; FFT unreliable
    settle_ferr: float = 0.02  # after re-enable, |FERR| must stay below this...
    settle_hold_s: float = 0.3  # ...for this long...
    settle_timeout_s: float = 5.0  # ...within this time, or the run stops

    # Acceptance / stability gates
    improvement_min_pct: float = 3.0  # keep climbing only if score improves
    integral_improve_min_pct: float = 0.5  # RMS gate for the integral phase
    integral_peak_guard_pct: float = 10.0  # peak may not regress more
    # v2: integral always runs (it matters for load rejection). Set >0 to
    # restore the old "skip when already N% better" shortcut.
    integral_skip_improved_pct: float = 0.0
    keep_best_min_improve_pct: float = 1.0  # salvage best stable step after verify fail
    verify_hf_margin: float = 0.12  # verify HF fail needs baseline_hf + this margin
    hf_fail: float = 0.35
    ring_fail: float = 0.85
    min_prominence_ratio: float = 4.0
    # A spectral peak below this absolute amplitude (axis units) is noise,
    # not a resonance — do not let it block the ladder on a quiet axis.
    min_resonance_amplitude: float = 0.001
    # ...and it must also stand out against the tracking error itself:
    # short-stroke stimuli put motion harmonics 30-60 Hz above the noise
    # floor with huge prominence (found via the sim — see docs/ONE_CLICK_TUNING.md
    # "lessons learned"). A real resonance carries a meaningful fraction of
    # the buffer RMS; forced motion harmonics do not.
    resonance_vs_rms: float = 0.10
    # Ignore FFT peaks below ~gate_min_hz_factor / leg_time (capped): that
    # band is dominated by the stimulus pulse train, not mechanics.
    gate_min_hz_factor: float = 6.0
    gate_min_hz_floor: float = 25.0
    gate_min_hz_cap: float = 120.0
    min_meaningful_rms: float = 0.0005
    # Motion watchdog aborts the move when |FERR| crosses this fraction of
    # the drive 6065 window (or ferr_abort_fallback when 6065 is unreadable).
    ferr_abort_ratio: float = 0.8
    ferr_abort_fallback: float = 0.8  # axis units

    # Notch handling
    allow_notch: bool = True
    notch_width_pct: float = 5.0
    notch_depth_pct: float = 10.0

    # Persistence
    save_presets: bool = True

    @classmethod
    def for_axis(
        cls,
        axis: str,
        profile: str = "balanced",
        stimulus: Optional[StimulusSpec] = None,
        **overrides: Any,
    ) -> "OneClickConfig":
        if axis not in AXES:
            raise ValueError(f"unknown axis {axis!r}")
        if profile not in PROFILES:
            raise ValueError(
                f"unknown profile {profile!r} (have {sorted(PROFILES)})"
            )
        kwargs: Dict[str, Any] = dict(PROFILES[profile])
        kwargs.update(overrides)
        stim = stimulus or DEFAULT_STIMULI.get(axis)
        if stim is None:
            raise ValueError(f"no default stimulus for axis {axis!r}")
        return cls(axis=axis, profile=profile, stimulus=stim, **kwargs)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        return data


# Profile knobs only — everything else stays at the dataclass defaults.
PROFILES: Dict[str, Dict[str, Any]] = {
    "conservative": dict(
        speed_step_ratio=1.15,
        speed_gain_max_hz=120.0,
        pos_gain_max_rad_s=250.0,
        max_steps_per_phase=6,
        improvement_min_pct=4.0,
        integral_min_ms=3.0,
        margin_ratio=0.5,
    ),
    "balanced": dict(integral_min_ms=3.0),
    "aggressive": dict(
        speed_step_ratio=1.4,
        speed_gain_max_hz=400.0,
        pos_gain_max_rad_s=800.0,
        max_steps_per_phase=10,
        improvement_min_pct=2.0,
        integral_min_ms=1.0,
        margin_ratio=0.65,
    ),
}


def estimate_campaign_seconds(cfg: OneClickConfig) -> float:
    """Rough worst-case duration for the confirm dialog / CLI banner."""
    stim = cfg.stimulus or DEFAULT_STIMULI[cfg.axis]
    measures = (
        max(1, cfg.baseline_repeats)  # baseline
        + cfg.rescue_max_steps
        + (cfg.max_steps_per_phase + 1) * 2  # speed + position (+ notch retry)
        + cfg.max_steps_per_phase  # integral
        + (cfg.max_steps_per_phase if cfg.ff_enabled else 0)  # feedforward
        + 2  # verify (+ one backoff re-verify)
        + len(cfg.verify_offsets) + (1 if cfg.verify_offsets else 0)
    )
    write_overhead_s = 2.5  # machine OFF -> SDO write -> ON, per step
    return measures * (stim.total_time_s() + write_overhead_s)


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------


@dataclass
class Measurement:
    label: str
    n_samples: int
    peak: float
    rms: float
    score: float
    unstable: bool
    unstable_why: str
    aborted: bool
    abort_reason: str
    dominant_hz: Optional[float]
    dominant_mag: Optional[float]
    report: Optional[ResonanceReport] = None
    torque_peak_pct: Optional[float] = None
    fs_hz: float = 1000.0
    ms: Optional[float] = None  # sensitivity peak, from frf_analysis
    f_ms_hz: Optional[float] = None

    def summary(self) -> str:
        gate = "UNSTABLE" if self.unstable else "stable"
        dom = (
            f" dom={self.dominant_hz:.1f}Hz" if self.dominant_hz is not None else ""
        )
        tq = (
            f" tq={self.torque_peak_pct:.0f}%"
            if self.torque_peak_pct is not None
            else ""
        )
        return (
            f"{self.label}: peak={self.peak:.5f} rms={self.rms:.5f} "
            f"score={self.score:.5f} {gate}{dom}{tq}"
            + (f" [{self.unstable_why}]" if self.unstable else "")
        )


def _report_to_dict(report: Optional[ResonanceReport]) -> Dict[str, Any]:
    if report is None:
        return {}
    return {
        "n_samples": int(report.n_samples),
        "peak_abs": float(report.peak_abs),
        "rms": float(report.rms),
        "hf_energy_ratio": float(report.hf_energy_ratio),
        "ring_score": float(report.ring_score),
        "gate_stable": bool(report.stable),
        "gate_reason": str(report.reason),
        "peaks": [
            {
                "freq_hz": float(p.freq_hz),
                "magnitude": float(p.magnitude),
                "prominence": float(p.prominence),
            }
            for p in (report.peaks or [])[:5]
        ],
    }


# ---------------------------------------------------------------------------
# Journal — the "learn something when it fails" part
# ---------------------------------------------------------------------------


class TuneJournal:
    """Crash-safe campaign journal.

    Writes three artifact kinds under ``<root>/<stamp>_<axis>/``:

    - ``journal.md``    — human narrative, appended (and flushed) per event so
                          a crash or power loss still leaves the story so far
    - ``journal.json``  — machine-readable event list, rewritten per event
    - ``NN_<label>.csv``— raw FERR samples for each measurement

    Nothing here should ever raise into the engine: journaling failures are
    logged and swallowed so they cannot make a hardware situation worse.
    """

    def __init__(self, root: str, axis: str, config: OneClickConfig) -> None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.dir = os.path.join(root, f"{stamp}_{axis}")
        self.axis = axis
        self._events: List[Dict[str, Any]] = []
        self._csv_index = 0
        self._t0 = time.time()
        try:
            os.makedirs(self.dir, exist_ok=True)
            self._md_path = os.path.join(self.dir, "journal.md")
            self._json_path = os.path.join(self.dir, "journal.json")
            with open(self._md_path, "w", encoding="utf-8") as handle:
                handle.write(
                    f"# One-click tune — axis {axis}\n\n"
                    f"- started: {datetime.now().isoformat(timespec='seconds')}\n"
                    f"- engine: a6_auto_tune v{ENGINE_VERSION}\n"
                    f"- profile: {config.profile}\n"
                    f"- stimulus: {config.stimulus.describe() if config.stimulus else '?'}\n"
                    f"- dry run: {config.dry_run}\n\n"
                )
            self.event(
                "setup",
                "config",
                "campaign configuration",
                config=config.to_dict(),
            )
        except Exception:
            LOG.exception("journal init failed (continuing without journal)")
            self._md_path = None
            self._json_path = None

    def event(self, phase: str, kind: str, message: str, **data: Any) -> None:
        entry = {
            "t": round(time.time() - self._t0, 3),
            "phase": phase,
            "kind": kind,
            "message": message,
        }
        if data:
            entry["data"] = _jsonable(data)
        self._events.append(entry)
        LOG.info("one-click[%s/%s]: %s", phase, kind, message)
        if self._md_path is None:
            return
        try:
            with open(self._md_path, "a", encoding="utf-8") as handle:
                handle.write(f"**[{entry['t']:8.1f}s | {phase} | {kind}]** {message}\n")
                if data:
                    handle.write(
                        "```json\n"
                        + json.dumps(_jsonable(data), indent=2, sort_keys=True)
                        + "\n```\n"
                    )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            LOG.exception("journal.md append failed")
        self._dump_json()

    def record_samples(
        self, label: str, samples: List[float], fs_hz: float
    ) -> Optional[str]:
        if self._md_path is None:
            return None
        self._csv_index += 1
        safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in label)
        path = os.path.join(self.dir, f"{self._csv_index:02d}_{safe}.csv")
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(f"# axis={self.axis} fs_hz={fs_hz:g} label={label}\n")
                handle.write("ferr\n")
                for value in samples:
                    handle.write(f"{value:.6f}\n")
            return path
        except Exception:
            LOG.exception("journal sample CSV failed")
            return None

    def exception(self, phase: str, exc: BaseException) -> None:
        self.event(
            phase,
            "exception",
            f"{type(exc).__name__}: {exc}",
            traceback=traceback.format_exc(),
        )

    def finalize(self, status: str, summary: Dict[str, Any]) -> None:
        self.event("finalize", "result", f"campaign status: {status}", **summary)
        if self._md_path is None:
            return
        try:
            with open(self._md_path, "a", encoding="utf-8") as handle:
                handle.write(
                    f"\n---\n\n**FINAL STATUS: {status.upper()}** — "
                    f"{datetime.now().isoformat(timespec='seconds')}\n"
                )
        except Exception:
            LOG.exception("journal finalize failed")

    def _dump_json(self) -> None:
        if self._json_path is None:
            return
        try:
            tmp = self._json_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(
                    {"axis": self.axis, "engine": ENGINE_VERSION, "events": self._events},
                    handle,
                    indent=1,
                )
            os.replace(tmp, self._json_path)
        except Exception:
            LOG.exception("journal.json dump failed")


def _jsonable(value: Any) -> Any:
    """Best-effort conversion for journal payloads (numpy floats etc.)."""
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (str, bool)) or value is None:
        return value
    if isinstance(value, (int, float)):
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return str(value)


# ---------------------------------------------------------------------------
# Hardware IO (real machine). The engine only talks to this interface, so the
# simulator in a6_auto_tune_sim.py can stand in for tests / bench dry runs.
# ---------------------------------------------------------------------------


class _FerrSampler(threading.Thread):
    """LEGACY (only with allow_python_sampler): polls drive 60F4 from Python.

    Measured 250-750 Hz with jitter on the mill, so the FFT built on it puts
    frequencies in the wrong place. The default path is rt_capture.RtCapture.

    Sets ``tripped`` when |FERR| crosses the abort limit so the caller can
    cmd.abort() the move. Keeps sampling after the trip so the journal still
    captures the whole event.
    """

    def __init__(
        self, axis: str, sample_hz: float, abort_limit: float
    ) -> None:
        super().__init__(daemon=True)
        self.axis = axis
        self.pin = drive_ferr_counts_halpin(axis)
        self.interval = 1.0 / max(sample_hz, 1.0)
        self.abort_limit = abs(abort_limit)
        self.samples: List[float] = []
        self.tripped = False
        self.trip_value: Optional[float] = None
        self._stop = threading.Event()

    def run(self) -> None:  # pragma: no cover - timing loop, exercised on HW
        next_t = time.monotonic()
        while not self._stop.is_set():
            counts = hal_getp_s32(self.pin)
            if counts == counts:
                value = counts_to_unit(self.axis, counts)
                self.samples.append(value)
                if not self.tripped and abs(value) >= self.abort_limit:
                    self.tripped = True
                    self.trip_value = value
            next_t += self.interval
            delay = next_t - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            else:
                next_t = time.monotonic()

    def poll(self) -> None:
        """Watchdog interface; this sampler trips from its own thread."""

    def stop(self) -> List[float]:
        self._stop.set()
        self.join(timeout=2.0)
        return list(self.samples)


class _CaptureWatch:
    """Watchdog over the realtime capture's latest row (tens of ms latency)."""

    def __init__(self, cap: Any, axis: str, abort_limit: float) -> None:
        self.cap = cap
        self.axis = axis
        self.abort_limit = abs(abort_limit)
        self.tripped = False
        self.trip_value: Optional[float] = None

    def poll(self) -> None:
        counts = self.cap.latest_ferr_counts
        if counts is None or self.tripped:
            return
        value = counts_to_unit(self.axis, counts)
        if abs(value) >= self.abort_limit:
            self.tripped = True
            self.trip_value = value


class HardwareTuneIO:
    """Real-machine IO: SDOs via a6_servo_tune, motion via LinuxCNC MDI."""

    name = "hardware"

    def __init__(self, config: Optional["OneClickConfig"] = None) -> None:
        if linuxcnc is None:
            raise OneClickError(
                "linuxcnc Python module not available — "
                "run inside the LinuxCNC environment"
            )
        self._stat = linuxcnc.stat()
        self._cmd = linuxcnc.command()
        self._cfg = config

    def _opt(self, name: str, default: Any) -> Any:
        return getattr(self._cfg, name, default) if self._cfg else default

    # -- realtime capture -------------------------------------------------------

    def capture_available(self) -> bool:
        try:
            import rt_capture

            return rt_capture.sampler_available()
        except Exception:
            return False

    def capture_rest(self, axis: str, seconds: float) -> Optional[Dict[str, Any]]:
        """Standstill capture: FERR (axis units) and torque (%) at rest."""
        if not self.capture_available():
            return None
        import rt_capture

        cap = rt_capture.RtCapture(axis)
        cap.start()
        try:
            time.sleep(max(seconds, 0.2))
        finally:
            result = cap.stop()
        return {
            "ferr": [counts_to_unit(axis, c) for c in result.ferr_counts],
            "torque_pct": list(result.torque_pct),
            "fs_hz": result.fs_hz,
        }

    # -- 6065 window --------------------------------------------------------------

    def relax_ferr_window(self, axis: str) -> Tuple[float, float]:
        prior = relax_following_error_for_tuning(axis, FOLLOWING_ERROR_AUTOTUNE)
        return prior, FOLLOWING_ERROR_AUTOTUNE

    def restore_ferr_window(self, axis: str) -> None:
        restore_following_error_run(axis)

    # -- SDO ----------------------------------------------------------------

    def read_params(self, axis: str):
        return read_axis_params(axis)

    def write_params(
        self, axis: str, params: AxisTuneParams, keys: List[str]
    ) -> Dict[str, Any]:
        live = bool(self._opt("live_writes", False))
        result = apply_axis_params(axis, params, cycle_enable=not live, keys=keys)
        if result.get("cycled_enable"):
            self._wait_settled(axis)
        return {
            "written": result.get("written_keys", []),
            "failed": result.get("failed_keys", []),
            "skipped": result.get("skipped_keys", []),
        }

    def save_preset(
        self, axis: str, name: str, params: AxisTuneParams, notes: str = ""
    ) -> str:
        return save_preset(axis, name, params, notes=notes)

    def _wait_settled(self, axis: str) -> None:
        """After machine OFF->ON, wait until the drive is holding position.

        2026-07-16 Z run: the first move after a write tripped at 1.0 mm FERR
        within ~13 samples. Never move before the axis has settled.
        """
        limit = float(self._opt("settle_ferr", 0.02))
        hold = float(self._opt("settle_hold_s", 0.3))
        timeout = float(self._opt("settle_timeout_s", 5.0))
        pin = drive_ferr_counts_halpin(axis)
        deadline = time.monotonic() + timeout
        quiet_since: Optional[float] = None
        last = float("nan")
        while time.monotonic() < deadline:
            if not machine_is_on():
                quiet_since = None
            else:
                counts = hal_getp_s32(pin)
                if counts == counts:
                    last = counts_to_unit(axis, counts)
                    if abs(last) <= limit:
                        quiet_since = quiet_since or time.monotonic()
                        if time.monotonic() - quiet_since >= hold:
                            return
                    else:
                        quiet_since = None
            time.sleep(0.02)
        raise OneClickError(
            f"axis {axis} did not settle after re-enable (|FERR| {last:.4f}, "
            f"need <= {limit:g} for {hold:g}s) — check Z sag / brake, or use "
            "live writes if scripts/test_live_gain_write.py passed"
        )

    # -- machine state --------------------------------------------------------

    def machine_ready(self) -> Tuple[bool, str]:
        try:
            self._stat.poll()
        except Exception as exc:
            return False, f"linuxcnc status unavailable: {exc}"
        if self._stat.task_state == linuxcnc.STATE_ESTOP:
            return False, "machine is in ESTOP"
        if not machine_is_on():
            return False, "machine is not ON (turn it on first)"
        if self._stat.interp_state != linuxcnc.INTERP_IDLE:
            return False, "a program / MDI command is still running"
        return True, "ok"

    def axis_state(self, axis: str) -> Dict[str, Any]:
        idx = {"X": 0, "Y": 1, "Z": 2, "A": 3}.get(axis, 0)
        joint = AXES[axis]["joint"]
        state: Dict[str, Any] = {
            "homed": None,
            "position": None,
            "min_limit": None,
            "max_limit": None,
            "feed_override": None,
            "opmode": None,
        }
        try:
            self._stat.poll()
            state["homed"] = bool(self._stat.joint[joint]["homed"])
            state["position"] = float(self._stat.actual_position[idx])
            state["min_limit"] = float(self._stat.axis[idx]["min_position_limit"])
            state["max_limit"] = float(self._stat.axis[idx]["max_position_limit"])
            state["feed_override"] = float(self._stat.feedrate)
        except Exception:
            LOG.exception("axis_state read failed")
        # Drive-homing branch (lcec 1.49 cia402) maps 6061; must be CSP (8).
        try:
            op = hal_getp(f"lcec.0.{AXES[axis]['slave']}.opmode-display")
            if op == op:
                state["opmode"] = int(op)
        except Exception:
            pass
        return state

    # -- motion ----------------------------------------------------------------

    def begin_session(self) -> None:
        """Enter MDI once per campaign (re-checked per measurement)."""
        self._ensure_mdi()

    def end_session(self) -> None:
        """Best-effort: leave the operator in MANUAL with G90 restored."""
        try:
            self._mdi("G90")
            self._cmd.wait_complete(2.0)
        except Exception:
            LOG.exception("end_session G90 restore failed")
        try:
            self._cmd.mode(linuxcnc.MODE_MANUAL)
            self._cmd.wait_complete(2.0)
        except Exception:
            LOG.exception("end_session MODE_MANUAL restore failed")

    def run_stimulus(
        self,
        spec: StimulusSpec,
        signed_stroke: float,
        abort_ferr: float,
        sample_hz: float,
        cancel: threading.Event,
    ) -> Tuple[List[float], Dict[str, Any]]:
        """Run the back-and-forth stimulus while capturing drive telemetry.

        Default: realtime capture (rt_capture, one row per servo cycle). The
        legacy Python poller is used only with allow_python_sampler. Uses
        relative (G91) strokes so work offsets do not matter; G90 is restored
        in a finally block. On an abort the axis is returned to its start at
        half feed when the machine is still healthy.

        meta keys: aborted, abort_reason, tripped_ferr, position_drift,
        fs_hz, torque_pct (list or None), machine_fault (bool),
        capture_error (str or None).
        """
        axis = spec.axis
        meta: Dict[str, Any] = {
            "aborted": False,
            "abort_reason": "",
            "tripped_ferr": None,
            "position_drift": None,
            "fs_hz": sample_hz,
            "torque_pct": None,
            "machine_fault": False,
            "capture_error": None,
            "capture": "legacy-python",
        }
        self._ensure_mdi()
        start_pos = self._axis_position(axis)
        leg_timeout = spec.leg_time_s() * 3.0 + 5.0

        cap = None
        sampler: Optional[_FerrSampler] = None
        if self.capture_available():
            import rt_capture

            cap = rt_capture.RtCapture(axis)
            cap.start()
            watch: Any = _CaptureWatch(cap, axis, abort_ferr)
            meta["capture"] = "realtime-sampler"
        elif self._opt("allow_python_sampler", False):
            sampler = _FerrSampler(axis, sample_hz, abort_ferr)
            sampler.start()
            watch = sampler
        else:
            raise OneClickError(
                "realtime capture unavailable (sampler.0 not loaded); refusing "
                "to tune on the legacy Python sampler"
            )

        samples: List[float] = []
        try:
            self._mdi("G21")
            self._wait_leg(2.0)
            self._mdi("G91")
            self._wait_leg(2.0)
            done = False
            for _cycle in range(spec.cycles):
                if done:
                    break
                for sign in (1.0, -1.0):
                    if cancel.is_set():
                        meta.update(aborted=True, abort_reason="cancelled")
                        self._cmd.abort()
                        done = True
                        break
                    self._mdi(
                        f"G1 {axis}{sign * signed_stroke:.4f} F{spec.feed:.1f}"
                    )
                    ok, why = self._wait_leg_watchdog(
                        leg_timeout, watch, cancel
                    )
                    if not ok:
                        meta.update(aborted=True, abort_reason=why)
                        if watch.tripped:
                            meta["tripped_ferr"] = watch.trip_value
                        done = True
                        break
                    if spec.dwell_s > 0:
                        self._sleep_watching(spec.dwell_s, watch)
            if not meta["aborted"] and spec.settle_s > 0:
                self._sleep_watching(spec.settle_s, watch)
        finally:
            try:
                self._mdi("G90")
                self._cmd.wait_complete(3.0)
            except Exception:
                LOG.exception("G90 restore failed after stimulus")
            if cap is not None:
                try:
                    result = cap.stop()
                    samples = [counts_to_unit(axis, c) for c in result.ferr_counts]
                    meta["torque_pct"] = list(result.torque_pct)
                    meta["pos_cmd"] = list(result.pos_cmd)
                    meta["fs_hz"] = result.fs_hz
                except Exception as exc:  # CaptureError or halcmd failure
                    meta["capture_error"] = f"{type(exc).__name__}: {exc}"
                    cap.abort()
            elif sampler is not None:
                samples = sampler.stop()

        # A FERR trip, RCS error or dropped STATE_ON may mean the drive
        # faulted. The engine must stop on that, not treat it as "unstable".
        ready, why_not = self.machine_ready()
        reason = str(meta.get("abort_reason") or "")
        if not ready or "RCS_ERROR" in reason or "dropped out of STATE_ON" in reason:
            meta["machine_fault"] = True
            meta["machine_state"] = why_not

        # Return to the start point if we aborted mid-leg and can still move.
        end_pos = self._axis_position(axis)
        if start_pos is not None and end_pos is not None:
            drift = end_pos - start_pos
            meta["position_drift"] = drift
            if meta["aborted"] and ready and abs(drift) > 0.01:
                try:
                    self._ensure_mdi()
                    self._mdi("G91")
                    self._cmd.wait_complete(2.0)
                    self._mdi(f"G1 {axis}{-drift:.4f} F{spec.feed / 2.0:.1f}")
                    self._cmd.wait_complete(leg_timeout)
                    self._mdi("G90")
                    self._cmd.wait_complete(2.0)
                    meta["returned_to_start"] = True
                except Exception:
                    LOG.exception("return-to-start failed")
                    meta["returned_to_start"] = False
        return samples, meta

    def _sleep_watching(self, seconds: float, watch: Any) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            watch.poll()
            time.sleep(0.01)

    # -- helpers -----------------------------------------------------------

    def max_torque_pct(self, axis: str) -> Optional[float]:
        """Drive torque limit 0x6072 (0.1 % rated per count), or None."""
        try:
            raw = ethercat_upload_u16(AXES[axis]["slave"], 0x6072, 0)
            return raw / 10.0 if raw > 0 else None
        except Exception as exc:
            LOG.warning("0x6072 read failed: %s", exc)
            return None

    def move_axis_to(self, axis: str, target: float, feed: float) -> None:
        """G53 G1 the tuned axis only (caller checked homed + limits)."""
        self._ensure_mdi()
        self._mdi(f"G90 G53 G1 {axis}{target:.4f} F{feed:.1f}")
        self._cmd.wait_complete(120.0)
        self._stat.poll()
        if self._stat.state == linuxcnc.RCS_ERROR:
            raise OneClickError(f"move to {axis}{target:.3f} failed (RCS_ERROR)")

    def _axis_position(self, axis: str) -> Optional[float]:
        idx = {"X": 0, "Y": 1, "Z": 2, "A": 3}.get(axis, 0)
        try:
            self._stat.poll()
            return float(self._stat.actual_position[idx])
        except Exception:
            return None

    def _ensure_mdi(self) -> None:
        self._stat.poll()
        if self._stat.task_mode != linuxcnc.MODE_MDI:
            self._cmd.mode(linuxcnc.MODE_MDI)
            self._cmd.wait_complete(3.0)

    def _mdi(self, code: str) -> None:
        self._cmd.mdi(code)

    def _wait_leg(self, timeout: float) -> None:
        self._cmd.wait_complete(timeout)

    def _wait_leg_watchdog(
        self, timeout: float, sampler: Any, cancel: threading.Event
    ) -> Tuple[bool, str]:
        """Wait for one MDI leg, aborting fast on FERR trip / cancel / fault.

        Checks every 10 ms (was 100 ms: up to ~17 mm of travel at F10000).
        """
        deadline = time.monotonic() + timeout
        while True:
            sampler.poll()
            rc = self._cmd.wait_complete(0.01)
            sampler.poll()
            if rc != -1:
                if sampler.tripped:
                    return (
                        False,
                        f"FERR watchdog tripped at {sampler.trip_value:.4f} "
                        f"(limit {sampler.abort_limit:.4f})",
                    )
                if linuxcnc is not None and rc == getattr(linuxcnc, "RCS_ERROR", 3):
                    return False, "MDI leg reported RCS_ERROR"
                self._stat.poll()
                if self._stat.task_state != linuxcnc.STATE_ON:
                    return False, "machine dropped out of STATE_ON mid-leg"
                return True, ""
            if sampler.tripped:
                self._cmd.abort()
                return (
                    False,
                    f"FERR watchdog tripped at {sampler.trip_value:.4f} "
                    f"(limit {sampler.abort_limit:.4f})",
                )
            if cancel.is_set():
                self._cmd.abort()
                return False, "cancelled"
            self._stat.poll()
            if self._stat.task_state != linuxcnc.STATE_ON:
                self._cmd.abort()
                return False, "machine dropped out of STATE_ON mid-leg"
            if time.monotonic() > deadline:
                self._cmd.abort()
                return False, f"leg timeout after {timeout:.1f}s"


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass
class OneClickResult:
    axis: str
    status: str  # improved | no-change | reverted | failed | cancelled | dry-run
    reason: str
    journal_dir: Optional[str]
    baseline_values: Dict[str, float] = field(default_factory=dict)
    final_values: Dict[str, float] = field(default_factory=dict)
    baseline_score: Optional[float] = None
    final_score: Optional[float] = None
    improvement_pct: Optional[float] = None
    preset_name: Optional[str] = None
    measurements: int = 0

    def summary(self) -> str:
        bits = [f"{self.axis}: {self.status.upper()} — {self.reason}"]
        if self.baseline_score is not None and self.final_score is not None:
            bits.append(
                f"score {self.baseline_score:.5f} -> {self.final_score:.5f}"
                + (
                    f" ({self.improvement_pct:+.1f}%)"
                    if self.improvement_pct is not None
                    else ""
                )
            )
        changed = {
            k: (self.baseline_values.get(k), self.final_values.get(k))
            for k in sorted(set(self.baseline_values) | set(self.final_values))
            if self.baseline_values.get(k) != self.final_values.get(k)
        }
        for key, (old, new) in changed.items():
            bits.append(f"{key}: {_fmt(old)} -> {_fmt(new)}")
        if self.preset_name:
            bits.append(f"preset: {self.preset_name}")
        if self.journal_dir:
            bits.append(f"journal: {self.journal_dir}")
        return "\n".join(bits)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


def default_journal_root() -> str:
    return os.path.join(repo_root(), "logs", "tuning", "one_click")


class OneClickTuner:
    """State machine that drives one axis campaign. One instance per run."""

    def __init__(
        self,
        config: OneClickConfig,
        io: Optional[Any] = None,
        journal_root: Optional[str] = None,
        progress: Optional[ProgressFn] = None,
    ) -> None:
        self.cfg = config
        if self.cfg.stimulus is None:
            self.cfg.stimulus = DEFAULT_STIMULI.get(config.axis)
        if self.cfg.stimulus is None:
            raise ValueError(f"no stimulus for axis {config.axis!r}")
        self.io = io if io is not None else HardwareTuneIO(config)
        self.journal = TuneJournal(
            journal_root or default_journal_root(), config.axis, config
        )
        self._progress_fn = progress
        self._cancel = threading.Event()

        # Campaign state
        self._baseline: Dict[str, float] = {}
        self._ok_keys: List[str] = []
        self._current: Dict[str, float] = {}
        self._touched: set = set()
        self._best_values: Dict[str, float] = {}
        self._best_score: float = math.inf
        self._baseline_score: Optional[float] = None
        self._baseline_hf: Optional[float] = None
        self._abort_ferr: float = config.ferr_abort_fallback
        self._measure_count = 0
        self._notch_attempted = False
        self._notch_applied = False
        self._signed_stroke: float = abs(config.stimulus.stroke)
        self._ferr_relaxed = False
        # v2: effective acceptance threshold (raised to beat measured noise)
        self._improve_pct: float = config.improvement_min_pct
        self._torque_guard: float = config.torque_guard_pct
        self._first_unstable: Dict[str, float] = {}
        self._rest_baseline: Optional[Dict[str, float]] = None

    # -- public API ----------------------------------------------------------

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> OneClickResult:
        axis = self.cfg.axis
        result = OneClickResult(
            axis=axis,
            status="failed",
            reason="did not start",
            journal_dir=self.journal.dir,
        )
        session_open = False
        try:
            self._progress("preflight", "checking machine state…")
            self._preflight()

            self._progress("baseline", "reading drive parameters…")
            self._read_baseline()
            result.baseline_values = {
                k: self._baseline[k] for k in TOUCHABLE_KEYS if k in self._baseline
            }
            self._save_backup_preset()

            if not self.cfg.dry_run:
                prior_ferr, window = self.io.relax_ferr_window(axis)
                self._ferr_relaxed = True
                self._abort_ferr = window * self.cfg.ferr_abort_ratio
                self.journal.event(
                    "baseline",
                    "ferr-window",
                    f"6065 set to {window:g} {axis_unit(axis)} for tuning "
                    f"(was {prior_ferr:g}); production window is 0.5",
                    prior=prior_ferr,
                    tuning=window,
                    abort_ferr=self._abort_ferr,
                )

            self.io.begin_session()
            session_open = True

            base_m = self._measure_baseline()
            result.baseline_score = base_m.score
            self._baseline_score = base_m.score
            if base_m.report is not None:
                self._baseline_hf = float(base_m.report.hf_energy_ratio)
            self._update_best(base_m)
            baseline_unstable = base_m.unstable

            if self.cfg.dry_run:
                result.status = "dry-run"
                result.reason = (
                    "dry run — measured baseline only, wrote nothing"
                )
                result.final_values = dict(result.baseline_values)
                result.final_score = base_m.score
                self._finalize(result)
                return result

            self._ensure_manual_mode()

            ref = base_m
            if baseline_unstable:
                ref = self._phase_rescue(base_m)

            ref = self._phase_speed(ref)
            ref = self._phase_position(ref)
            ref = self._phase_integral(ref)
            ref = self._phase_feedforward(ref)
            final_m, verify_outcome = self._phase_verify(ref)
            if verify_outcome in ("pass", "keep_best") and self.cfg.verify_offsets:
                final_m, verify_outcome = self._phase_verify_positions(
                    final_m, verify_outcome
                )

            result.measurements = self._measure_count
            result.final_values = {
                k: self._current[k] for k in TOUCHABLE_KEYS if k in self._current
            }

            if verify_outcome == "revert_baseline":
                result.final_score = final_m.score if final_m is not None else None
                result.status = "reverted"
                result.reason = (
                    "verify stayed unstable after backoff — baseline restored"
                )
            elif verify_outcome == "keep_best":
                result.final_score = self._best_score
                improvement = None
                if self._baseline_score and self._best_score < math.inf:
                    improvement = (
                        (self._baseline_score - self._best_score)
                        / self._baseline_score
                        * 100.0
                    )
                result.improvement_pct = improvement
                result.status = "improved"
                result.reason = (
                    f"verify/backoff failed but best stable step kept "
                    f"({improvement:.1f}% better than baseline)"
                    if improvement is not None
                    else "verify/backoff failed but best stable step kept"
                )
                if self.cfg.save_presets:
                    result.preset_name = self._save_final_preset()
            else:
                result.final_score = final_m.score if final_m is not None else None
                improvement = None
                if result.baseline_score and result.final_score is not None:
                    improvement = (
                        (result.baseline_score - result.final_score)
                        / result.baseline_score
                        * 100.0
                    )
                result.improvement_pct = improvement
                if baseline_unstable and final_m is not None and not final_m.unstable:
                    result.status = "improved"
                    result.reason = "baseline was unstable; final tune is stable"
                elif improvement is not None and improvement >= 1.0:
                    result.status = "improved"
                    result.reason = f"score improved {improvement:.1f}%"
                elif self._first_unstable and any(
                    abs(result.final_values.get(k, 0.0) - result.baseline_values.get(k, 0.0)) > 1e-6
                    for k in CORE_GAIN_KEYS
                ):
                    # v2: the baseline sat too close to instability; gains
                    # were lowered to the margin even though the air-move
                    # score got worse. Safer, so keep and save it.
                    result.status = "margin-limited"
                    result.reason = (
                        "baseline was within the stability margin; gains lowered "
                        "to " + ", ".join(
                            f"{k}={self._current[k]:g} ({self.cfg.margin_ratio:g} x "
                            f"first ring {v:g})"
                            for k, v in self._first_unstable.items()
                        )
                    )
                else:
                    result.status = "no-change"
                    result.reason = (
                        "no meaningful improvement found beyond the baseline"
                    )
                if self.cfg.save_presets and result.status in (
                    "improved",
                    "margin-limited",
                ):
                    result.preset_name = self._save_final_preset()

            self._finalize(result)
            return result

        except (OneClickCancelled, KeyboardInterrupt):
            self.journal.event("cancel", "cancelled", "operator cancelled — reverting")
            self._revert_to_baseline("cancel")
            result.status = "cancelled"
            result.reason = "cancelled by operator; baseline restored"
            result.final_values = dict(result.baseline_values)
            self._finalize(result)
            return result
        except Exception as exc:  # noqa: BLE001 - report, revert, never re-raise
            self.journal.exception("error", exc)
            self._revert_to_baseline("error")
            result.status = "failed"
            result.reason = f"{type(exc).__name__}: {exc}"
            result.final_values = dict(result.baseline_values)
            self._finalize(result)
            return result
        finally:
            if getattr(self, "_ferr_relaxed", False):
                try:
                    self.io.restore_ferr_window(self.cfg.axis)
                    self.journal.event(
                        "finalize",
                        "ferr-window",
                        "6065 restored to 0.5 production window",
                    )
                except Exception:
                    LOG.exception("restore 6065 production window failed")
                self._ferr_relaxed = False
            if session_open:
                try:
                    self.io.end_session()
                except Exception:
                    LOG.exception("end_session failed")

    # -- phases ---------------------------------------------------------------

    def _preflight(self) -> None:
        axis = self.cfg.axis
        if _np is None:
            raise OneClickError(
                "numpy is required for the stability gate "
                "(sudo apt install python3-numpy)"
            )
        ready, why = self.io.machine_ready()
        if not ready:
            raise OneClickError(f"preflight failed: {why}")

        state = self.io.axis_state(axis)
        self.journal.event("preflight", "machine", "machine ready", **state)

        if not self.io.capture_available():
            if not self.cfg.allow_python_sampler:
                raise OneClickError(
                    "preflight failed: realtime capture (sampler.0) not loaded — "
                    "see the REALTIME CAPTURE block in custom.hal. "
                    "--allow-python-sampler runs the old ~300 Hz poller, whose "
                    "FFT frequencies are wrong"
                )
            self.journal.event(
                "preflight",
                "warning",
                "LEGACY Python sampler: FFT frequencies and notch placement "
                "are unreliable",
            )
        opmode = state.get("opmode")
        if opmode is not None and opmode != 8:
            raise OneClickError(
                f"preflight failed: drive opmode is {opmode}, not 8 (CSP) — "
                "a drive home may have been interrupted"
            )
        self._state0 = state
        reader = getattr(self.io, "max_torque_pct", None)
        drive_lim = reader(self.cfg.axis) if reader else None
        if drive_lim:
            guard = min(
                self.cfg.torque_guard_pct,
                self.cfg.torque_guard_drive_ratio * drive_lim,
            )
            self._torque_guard = guard
            self.journal.event(
                "preflight",
                "info",
                f"drive torque limit 0x6072 = {drive_lim:g}% -> guard {guard:g}%",
            )
        else:
            self.journal.event(
                "preflight",
                "info",
                f"0x6072 not readable — torque guard stays {self._torque_guard:g}%",
            )

        stim = self.cfg.stimulus
        homed = state.get("homed")
        pos = state.get("position")
        lo = state.get("min_limit")
        hi = state.get("max_limit")
        direction = 1.0
        if homed and pos is not None and lo is not None and hi is not None:
            margin = abs(stim.stroke) * 0.05 + 0.1
            if pos + stim.stroke + margin <= hi:
                direction = 1.0
            elif pos - stim.stroke - margin >= lo:
                direction = -1.0
            else:
                raise OneClickError(
                    f"preflight failed: no room for a {stim.stroke:g} "
                    f"{axis_unit(axis)} stroke inside soft limits "
                    f"[{lo:g}, {hi:g}] from {pos:g}"
                )
        elif homed is False:
            self.journal.event(
                "preflight",
                "warning",
                f"axis {axis} not homed — soft-limit envelope check skipped; "
                "operator confirmed clearance",
            )
        self._signed_stroke = direction * abs(stim.stroke)
        self.journal.event(
            "preflight",
            "stimulus",
            f"stimulus direction {'+' if direction > 0 else '-'}"
            f"{abs(stim.stroke):g} {axis_unit(axis)}",
            direction=direction,
            spec=stim.describe(),
        )
        override = state.get("feed_override")
        if override is not None and abs(override - 1.0) > 0.01:
            self.journal.event(
                "preflight",
                "warning",
                f"feed override is {override * 100:.0f}% (not 100%) — "
                "measurements will not be comparable across runs",
            )

    def _read_baseline(self) -> None:
        axis = self.cfg.axis
        params, ok_keys, failed_keys = self.io.read_params(axis)
        self._ok_keys = list(ok_keys)
        if failed_keys:
            self.journal.event(
                "baseline",
                "warning",
                f"{len(failed_keys)} SDO reads failed (they will never be "
                "written)",
                failed=failed_keys,
            )
        missing_core = [k for k in CORE_GAIN_KEYS if k not in params.values]
        if missing_core:
            raise OneClickError(
                "baseline read failed for core gain keys: "
                + ", ".join(missing_core)
                + " — check EtherCAT / passwordless sudo for `ethercat`"
            )
        self._baseline = {k: float(v) for k, v in params.values.items()}
        self._current = dict(self._baseline)

        window = self._baseline.get("following_error")
        if window is not None and window > 0:
            self._abort_ferr = window * self.cfg.ferr_abort_ratio
        else:
            self._abort_ferr = self.cfg.ferr_abort_fallback
            self.journal.event(
                "baseline",
                "warning",
                "drive 6065 window unreadable — using fallback FERR abort "
                f"limit {self._abort_ferr:g} {axis_unit(axis)}",
            )

        notch_missing = [k for k in NOTCH3_KEYS if k not in self._baseline]
        if notch_missing and self.cfg.allow_notch:
            self.cfg.allow_notch = False
            self.journal.event(
                "baseline",
                "warning",
                "3rd notch SDOs unread — automatic notch disabled",
                missing=notch_missing,
            )
        self.journal.event(
            "baseline",
            "params",
            f"baseline snapshot ({len(self._baseline)} keys)",
            values={k: self._baseline[k] for k in sorted(self._baseline)},
            abort_ferr=self._abort_ferr,
        )

    def _save_backup_preset(self) -> None:
        if not self.cfg.save_presets:
            return
        name = f"pre_one_click_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        params = AxisTuneParams.__new__(AxisTuneParams)
        params.values = dict(self._baseline)
        try:
            path = self.io.save_preset(
                self.cfg.axis,
                name,
                params,
                notes="automatic backup before one-click tuning",
            )
            self.journal.event(
                "baseline", "backup", f"baseline preset saved: {name}", path=path
            )
        except Exception as exc:
            # A failed backup is not fatal (journal holds the values), but say so.
            self.journal.event(
                "baseline",
                "warning",
                f"could not save backup preset ({exc}) — journal still has "
                "the baseline values",
            )

    def _ensure_manual_mode(self) -> None:
        """C00.04 must be 0 (manual) or the drive's own auto-tuner fights us."""
        mode = self._current.get(MODE_KEY)
        if mode is None:
            self.journal.event(
                "setup",
                "warning",
                "C00.04 auto-tuning mode unread — assuming manual; the drive "
                "may fight gain writes if its auto-tune is active",
            )
            return
        if int(mode) != 0:
            self.journal.event(
                "setup",
                "write",
                f"C00.04 auto-tuning mode {int(mode)} -> 0 (manual) so the "
                "drive does not overwrite our gains",
            )
            self._write_values("setup", {MODE_KEY: 0.0})

    def _phase_rescue(self, base_m: Measurement) -> Measurement:
        """Baseline already rings: soften speed gain / notch until stable."""
        self._progress("rescue", "baseline unstable — softening first…")
        self.journal.event(
            "rescue",
            "start",
            f"baseline unstable ({base_m.unstable_why}) — rescue before ladder",
        )
        m = base_m
        for attempt in range(1, self.cfg.rescue_max_steps + 1):
            self._check_cancel()
            if not m.unstable:
                break
            if self._try_notch("rescue", m):
                m = self._measure(f"rescue_notch_{attempt}")
                if not m.unstable:
                    self.journal.event(
                        "rescue", "ok", "notch stabilized the baseline"
                    )
                    self._update_best(m)
                    return m
                self._revert_notch("rescue")
            new_speed = max(
                float(PARAM_BY_KEY["speed_gain_hz"]["min"]),
                self._current["speed_gain_hz"] * self.cfg.backoff_ratio,
            )
            self.journal.event(
                "rescue",
                "backoff",
                f"speed gain {self._current['speed_gain_hz']:.1f} -> "
                f"{new_speed:.1f} Hz (attempt {attempt})",
            )
            self._write_values("rescue", {"speed_gain_hz": new_speed})
            m = self._measure(f"rescue_soften_{attempt}")
        if m.unstable:
            raise OneClickError(
                "rescue failed: axis still unstable after "
                f"{self.cfg.rescue_max_steps} soften steps — check mechanics "
                "(coupling, notch on the drive panel) before auto-tuning"
            )
        self.journal.event("rescue", "ok", "baseline stabilized")
        self._update_best(m)
        return m

    def _phase_speed(self, ref: Measurement) -> Measurement:
        cfg = self.cfg
        key = "speed_gain_hz"
        cap = min(cfg.speed_gain_max_hz, float(PARAM_BY_KEY[key]["max"]))
        filt = self._current.get("torque_filter_hz")
        if cfg.speed_vs_filter_cap > 0 and filt:
            filter_cap = filt * cfg.speed_vs_filter_cap
            if filter_cap < cap:
                cap = filter_cap
                self.journal.event(
                    "speed",
                    "cap",
                    f"speed gain capped at {cap:.1f} Hz "
                    f"({cfg.speed_vs_filter_cap:g} x C01.03 torque filter "
                    f"{filt:g} Hz)",
                )
        cur = self._current[key]
        self.journal.event(
            "speed", "start", f"speed ladder from {cur:.1f} Hz, cap {cap:.1f} Hz"
        )
        if cur >= cap:
            self.journal.event(
                "speed", "skip", "already at/above cap — nothing to climb"
            )
            return ref

        stalls = 0
        for step in range(1, cfg.max_steps_per_phase + 1):
            self._check_cancel()
            cur = self._current[key]
            cand = min(cap, max(cur * cfg.speed_step_ratio, cur + 2.0))
            if cand <= cur + 0.05:
                self.journal.event("speed", "done", "reached cap")
                break
            self._progress(
                "speed", f"step {step}: trying {cand:.1f} Hz (was {cur:.1f})"
            )
            self._write_values("speed", {key: cand})
            m = self._measure(f"speed_{cand:.1f}hz")

            if m.unstable:
                if self._try_notch("speed", m):
                    m2 = self._measure(f"speed_{cand:.1f}hz_notched")
                    if not m2.unstable:
                        self.journal.event(
                            "speed",
                            "notch-ok",
                            "notch cleared the ring — continuing ladder",
                        )
                        if self._improved(m2, ref, self._improve_pct):
                            ref = m2
                        self._update_best(m2)
                        continue
                    self._revert_notch("speed")
                target = self._margin_target(key, cand, cur)
                self.journal.event(
                    "speed",
                    "backoff",
                    f"unstable at {cand:.1f} Hz ({m.unstable_why}) — margin "
                    f"backoff to {target:.1f} Hz ({cfg.margin_ratio:g} x first "
                    f"ringing gain)",
                    first_unstable=cand,
                    margin_ratio=cfg.margin_ratio,
                )
                self._write_values("speed", {key: target})
                if target < cur - 1e-6:
                    ref = self._measure(f"speed_margin_{target:.1f}hz")
                    if ref.unstable:
                        raise OneClickError(
                            f"still unstable at the margin gain {target:.1f} Hz "
                            f"({ref.unstable_why}) — check mechanics"
                        )
                    self._update_best(ref)
                break

            if self._improved(m, ref, self._improve_pct):
                self.journal.event(
                    "speed",
                    "accept",
                    f"{cand:.1f} Hz accepted ({m.summary()})",
                )
                ref = m
                self._update_best(m)
                stalls = 0
            else:
                stalls += 1
                self.journal.event(
                    "speed",
                    "stall",
                    f"{cand:.1f} Hz stable but no {self._improve_pct:.1f}% "
                    f"improvement ({m.summary()}) — reverting to {cur:.1f} Hz "
                    f"(stall {stalls}/{cfg.max_stall_steps})",
                )
                self._write_values("speed", {key: cur})
                if stalls >= cfg.max_stall_steps:
                    break
        return ref

    def _phase_position(self, ref: Measurement) -> Measurement:
        cfg = self.cfg
        key = "pos_gain_rad_s"
        speed = self._current["speed_gain_hz"]
        target = speed * cfg.pos_to_speed_ratio
        cap = min(
            cfg.pos_gain_max_rad_s,
            float(PARAM_BY_KEY[key]["max"]),
            target * 1.2,
        )
        cur = self._current[key]
        self.journal.event(
            "position",
            "start",
            f"position ladder from {cur:.1f} rad/s toward ~{target:.1f} "
            f"(cap {cap:.1f})",
        )
        if cur >= cap:
            self.journal.event(
                "position", "skip", "already at/above cap — leaving it alone"
            )
            return ref

        stalls = 0
        for step in range(1, cfg.max_steps_per_phase + 1):
            self._check_cancel()
            cur = self._current[key]
            cand = min(cap, max(cur * cfg.pos_step_ratio, cur + 2.0))
            if cand <= cur + 0.05:
                self.journal.event("position", "done", "reached cap")
                break
            self._progress(
                "position",
                f"step {step}: trying {cand:.1f} rad/s (was {cur:.1f})",
            )
            self._write_values("position", {key: cand})
            m = self._measure(f"pos_{cand:.1f}rads")

            if m.unstable:
                target = self._margin_target(key, cand, cur)
                self.journal.event(
                    "position",
                    "backoff",
                    f"unstable at {cand:.1f} rad/s ({m.unstable_why}) — margin "
                    f"backoff to {target:.1f} ({cfg.margin_ratio:g} x first "
                    f"ringing gain)",
                    first_unstable=cand,
                    margin_ratio=cfg.margin_ratio,
                )
                self._write_values("position", {key: target})
                if target < cur - 1e-6:
                    ref = self._measure(f"pos_margin_{target:.1f}rads")
                    if ref.unstable:
                        raise OneClickError(
                            f"still unstable at the margin gain {target:.1f} "
                            f"rad/s ({ref.unstable_why}) — check mechanics"
                        )
                    self._update_best(ref)
                break
            if self._improved(m, ref, self._improve_pct):
                self.journal.event(
                    "position", "accept", f"{cand:.1f} rad/s accepted ({m.summary()})"
                )
                ref = m
                self._update_best(m)
                stalls = 0
            else:
                stalls += 1
                self.journal.event(
                    "position",
                    "stall",
                    f"{cand:.1f} rad/s stable but no improvement "
                    f"({m.summary()}) — reverting to {cur:.1f} "
                    f"(stall {stalls}/{cfg.max_stall_steps})",
                )
                self._write_values("position", {key: cur})
                if stalls >= cfg.max_stall_steps:
                    break
        return ref

    def _phase_integral(self, ref: Measurement) -> Measurement:
        cfg = self.cfg
        key = "integral_ms"
        cur = self._current[key]
        floor = max(cfg.integral_min_ms, float(PARAM_BY_KEY[key]["min"]))
        if (
            self._baseline_score is not None
            and self._best_score < math.inf
            and cfg.integral_skip_improved_pct > 0
        ):
            imp = (
                (self._baseline_score - self._best_score)
                / self._baseline_score
                * 100.0
            )
            if imp >= cfg.integral_skip_improved_pct:
                self.journal.event(
                    "integral",
                    "skip",
                    f"best already {imp:.1f}% better than baseline "
                    f"(≥{cfg.integral_skip_improved_pct:g}%) — skipping integral tighten",
                )
                return ref
        self.journal.event(
            "integral",
            "start",
            f"integral tighten from {cur:.2f} ms toward {floor:.2f} ms "
            "(lower = stronger)",
        )
        if cur <= floor:
            self.journal.event("integral", "skip", "already at/below floor")
            return ref

        for step in range(1, cfg.max_steps_per_phase + 1):
            self._check_cancel()
            cur = self._current[key]
            cand = max(floor, cur * cfg.integral_step_ratio)
            if cand >= cur - 0.01:
                self.journal.event("integral", "done", "reached floor")
                break
            self._progress(
                "integral", f"step {step}: trying {cand:.2f} ms (was {cur:.2f})"
            )
            self._write_values("integral", {key: cand})
            m = self._measure(f"integral_{cand:.2f}ms")

            rms_gain = (
                (ref.rms - m.rms) / ref.rms * 100.0 if ref.rms > 0 else 0.0
            )
            peak_regress = (
                (m.peak - ref.peak) / ref.peak * 100.0 if ref.peak > 0 else 0.0
            )
            if m.unstable:
                self.journal.event(
                    "integral",
                    "backoff",
                    f"unstable at {cand:.2f} ms ({m.unstable_why}) — "
                    f"returning to {cur:.2f} ms",
                )
                self._write_values("integral", {key: cur})
                break
            if (
                rms_gain >= cfg.integral_improve_min_pct
                and peak_regress <= cfg.integral_peak_guard_pct
            ):
                self.journal.event(
                    "integral",
                    "accept",
                    f"{cand:.2f} ms accepted (rms {rms_gain:+.1f}%, "
                    f"peak {peak_regress:+.1f}%)",
                )
                ref = m
                self._update_best(m)
            else:
                self.journal.event(
                    "integral",
                    "stall",
                    f"{cand:.2f} ms: rms {rms_gain:+.1f}% / peak "
                    f"{peak_regress:+.1f}% — not worth it, reverting to "
                    f"{cur:.2f} ms",
                )
                self._write_values("integral", {key: cur})
                break
        return ref

    def _phase_feedforward(self, ref: Measurement) -> Measurement:
        """Hill-climb torque FF % (up, then down if up did not help)."""
        cfg = self.cfg
        key = "torque_ff_pct"
        if not cfg.ff_enabled:
            return ref
        if not self._writable([key]) or not self._current.get("torque_ff_source"):
            self.journal.event(
                "feedforward",
                "skip",
                "torque FF source is off or torque_ff_pct unreadable — "
                "the tuner does not switch FF on",
            )
            return ref
        lo = max(cfg.ff_min_pct, float(PARAM_BY_KEY[key]["min"]))
        hi = min(cfg.ff_max_pct, float(PARAM_BY_KEY[key]["max"]))
        self.journal.event(
            "feedforward", "start",
            f"torque FF {self._current[key]:g}% (search {lo:g}-{hi:g}%)",
        )
        for ratio in (cfg.ff_step_ratio, 1.0 / cfg.ff_step_ratio):
            moved = False
            for step in range(1, cfg.max_steps_per_phase + 1):
                self._check_cancel()
                cur = self._current[key]
                cand = round(min(hi, max(lo, cur * ratio)), 1)
                if abs(cand - cur) < 0.5:
                    break
                self._progress(
                    "feedforward", f"step {step}: torque FF {cand:g}% (was {cur:g})"
                )
                self._write_values("feedforward", {key: cand})
                m = self._measure(f"ff_{cand:g}pct")
                if m.unstable:
                    self.journal.event(
                        "feedforward", "backoff",
                        f"{cand:g}% unstable ({m.unstable_why}) — back to {cur:g}%",
                    )
                    self._write_values("feedforward", {key: cur})
                    break
                if self._improved(m, ref, max(cfg.ff_improve_min_pct, self._improve_pct)):
                    self.journal.event(
                        "feedforward", "accept",
                        f"{cand:g}% accepted ({m.summary()})",
                    )
                    ref = m
                    self._update_best(m)
                    moved = True
                else:
                    self.journal.event(
                        "feedforward", "stall",
                        f"{cand:g}% no better — back to {cur:g}%",
                    )
                    self._write_values("feedforward", {key: cur})
                    break
            if moved:
                break
        return ref

    def _phase_verify_positions(
        self, final_m: Optional[Measurement], outcome: str
    ) -> Tuple[Optional[Measurement], str]:
        """Re-verify at other points along travel; always return to start."""
        cfg = self.cfg
        state = self.io.axis_state(cfg.axis)
        start = state.get("position")
        lo, hi = state.get("min_limit"), state.get("max_limit")
        if not state.get("homed") or start is None or lo is None or hi is None:
            self.journal.event(
                "verify", "skip", "multi-position verify needs the axis homed"
            )
            return final_m, outcome
        reach = abs(self._signed_stroke) + 1.0
        feed = max(cfg.stimulus.feed / 2.0, 1.0)
        failed: Optional[str] = None
        try:
            for off in cfg.verify_offsets:
                self._check_cancel()
                if cfg.axis == "Z" and off < 0:
                    self.journal.event(
                        "verify", "skip", f"Z offset {off:g} refused (down)"
                    )
                    continue
                target = start + off
                if not (lo + reach <= target <= hi - reach):
                    self.journal.event(
                        "verify", "skip",
                        f"offset {off:+g} -> {target:.2f} outside limits "
                        f"less stroke [{lo + reach:.2f}, {hi - reach:.2f}]",
                    )
                    continue
                self._progress("verify", f"moving to {cfg.axis}{target:.2f}")
                self.io.move_axis_to(cfg.axis, target, feed)
                m = self._measure(f"verify_pos{off:+g}")
                self.journal.event("verify", "position", m.summary(), offset=off)
                if m.unstable:
                    failed = f"unstable at offset {off:+g}: {m.unstable_why}"
                    break
        finally:
            try:
                self.io.move_axis_to(cfg.axis, start, feed)
            except Exception as exc:
                self.journal.event("verify", "warning", f"return to start failed: {exc}")
        if failed is None:
            return final_m, outcome
        self.journal.event(
            "verify", "revert", failed + " — restoring baseline (tune only "
            "held at one spot)"
        )
        self._revert_to_baseline("verify")
        m3 = self._measure("verify_baseline")
        return m3, "revert_baseline"

    def _phase_verify(
        self, ref: Measurement
    ) -> Tuple[Optional[Measurement], str]:
        """Final confirmation measure; one backoff attempt, else salvage best."""
        self._progress("verify", "verifying final tune…")
        m = self._measure("verify")
        if not m.unstable:
            self.journal.event("verify", "ok", m.summary())
            self._update_best(m)
            return m, "pass"

        self.journal.event(
            "verify",
            "warning",
            f"final tune unstable on verify ({m.unstable_why}) — backing off "
            f"speed & position by {self.cfg.backoff_ratio:g}x",
        )
        soft = {
            "speed_gain_hz": max(
                float(PARAM_BY_KEY["speed_gain_hz"]["min"]),
                self._current["speed_gain_hz"] * self.cfg.backoff_ratio,
            ),
            "pos_gain_rad_s": max(
                float(PARAM_BY_KEY["pos_gain_rad_s"]["min"]),
                self._current["pos_gain_rad_s"] * self.cfg.backoff_ratio,
            ),
        }
        self._write_values("verify", soft)
        m2 = self._measure("verify_backoff")
        if not m2.unstable:
            self.journal.event(
                "verify", "ok", f"stable after backoff ({m2.summary()})"
            )
            self._update_best(m2)
            return m2, "pass"

        if self._keep_best_after_verify_failure(verify_m=m, backoff_m=m2):
            salvage_m = self._measure("verify_best")
            self.journal.event("verify", "best-check", salvage_m.summary())
            # Keep-best exists for the harmless-HF false positive (2026-07-12
            # X). Any other failure on the re-check (ring, resonance, torque,
            # standstill noise, abort) means the best step is not safe.
            hard = [
                r.strip()
                for r in (salvage_m.unstable_why or "").split(";")
                if r.strip() and not r.strip().startswith("HF energy")
            ]
            if not (salvage_m.unstable and hard):
                self._update_best(salvage_m)
                return salvage_m, "keep_best"
            self.journal.event(
                "verify",
                "best-rejected",
                "best step failed its re-check: " + "; ".join(hard),
            )

        self.journal.event(
            "verify",
            "revert",
            "still unstable after backoff and no salvageable best step — "
            "restoring baseline",
        )
        self._revert_to_baseline("verify")
        m3 = self._measure("verify_baseline")
        self.journal.event("verify", "baseline-check", m3.summary())
        return m3, "revert_baseline"

    # -- primitives -----------------------------------------------------------

    def _progress(self, phase: str, message: str) -> None:
        if self._progress_fn is not None:
            try:
                self._progress_fn(phase, message)
            except Exception:
                LOG.exception("progress callback failed")

    def _check_cancel(self) -> None:
        if self._cancel.is_set():
            raise OneClickCancelled()

    def _writable(self, keys: List[str]) -> List[str]:
        out = []
        for key in keys:
            defn = PARAM_BY_KEY.get(key)
            if defn is None or defn.get("writable", True) is False:
                continue
            if key not in self._ok_keys:
                continue
            out.append(key)
        return out

    def _write_values(self, phase: str, updates: Dict[str, float]) -> None:
        keys = self._writable(list(updates.keys()))
        dropped = [k for k in updates if k not in keys]
        if dropped:
            self.journal.event(
                phase,
                "warning",
                f"skipping non-writable / unread keys: {', '.join(dropped)}",
            )
        if not keys:
            raise OneClickError(
                f"nothing writable in update {sorted(updates)} — aborting"
            )
        params = AxisTuneParams.__new__(AxisTuneParams)
        params.values = {k: float(updates[k]) for k in keys}
        result = self.io.write_params(self.cfg.axis, params, keys)
        self.journal.event(
            phase,
            "write",
            "SDO write " + ", ".join(f"{k}={updates[k]:g}" for k in keys),
            written=result.get("written"),
            failed=result.get("failed"),
            skipped=result.get("skipped"),
        )
        failed = result.get("failed") or []
        if failed:
            raise OneClickError(
                "SDO write failed: "
                + "; ".join(f"{k}: {err}" for k, err in failed)
            )
        for key in keys:
            self._current[key] = float(updates[key])
            self._touched.add(key)

    def _measure(self, label: str) -> Measurement:
        self._check_cancel()
        self._measure_count += 1
        cfg = self.cfg
        samples, meta = self.io.run_stimulus(
            cfg.stimulus,
            self._signed_stroke,
            self._abort_ferr,
            cfg.sample_hz,
            self._cancel,
        )
        if meta.get("abort_reason") == "cancelled" or self._cancel.is_set():
            raise OneClickCancelled()
        if meta.get("capture_error"):
            self.journal.record_samples(label + "_INVALID", samples, cfg.sample_hz)
            raise OneClickError(
                f"measurement {label!r} invalid: {meta['capture_error']}"
            )
        if meta.get("machine_fault"):
            self.journal.record_samples(label + "_FAULT", samples, cfg.sample_hz)
            self.journal.event(
                "measure", "fault", f"machine fault during {label}", meta=meta
            )
            raise OneClickError(
                f"machine fault during {label!r} "
                f"({meta.get('abort_reason') or meta.get('machine_state')}) — "
                "stopping the campaign; clear the fault before retrying"
            )
        fs = float(meta.get("fs_hz") or cfg.sample_hz)
        torque = meta.get("torque_pct")
        torque_peak = (
            max((abs(t) for t in torque), default=0.0) if torque else None
        )
        meta_journal = {
            k: v for k, v in meta.items() if k not in ("torque_pct", "pos_cmd")
        }
        sens = None
        pos_cmd = meta.get("pos_cmd")
        if pos_cmd and len(pos_cmd) == len(samples):
            try:
                sens = sensitivity(pos_cmd, samples, fs, nperseg=cfg.frf_nperseg)
            except Exception as exc:
                self.journal.event("measure", "warning", f"|S| failed: {exc}")

        report: Optional[ResonanceReport] = None
        gate_min_hz = self._gate_min_hz()
        try:
            report = analyze_ferr_resonance(
                samples,
                axis=cfg.axis,
                fs_hz=fs,
                min_hz=gate_min_hz,
                hf_fail=cfg.hf_fail,
                ring_fail=cfg.ring_fail,
                min_prominence_ratio=cfg.min_prominence_ratio,
            )
        except Exception as exc:
            self.journal.event(
                "measure", "warning", f"FFT analysis failed: {exc}"
            )

        peak = float(report.peak_abs) if report is not None else _peak(samples)
        rms = float(report.rms) if report is not None else _rms(samples)
        score = peak + SCORE_RMS_WEIGHT * rms
        unstable, why = self._classify(report, meta, label=label)
        reasons = [why] if unstable else []
        if torque_peak is not None and torque_peak >= self._torque_guard:
            reasons.append(
                f"torque {torque_peak:.0f}% >= guard {self._torque_guard:g}%"
            )
        if (
            sens is not None
            and sens.ok()
            and cfg.ms_max > 0
            and sens.ms > cfg.ms_max
        ):
            reasons.append(
                f"Ms {sens.ms:.2f} @ {sens.f_ms_hz:.0f} Hz > {cfg.ms_max:g}"
            )
        if label.startswith("verify"):
            rest_why = self._rest_check(label)
            if rest_why:
                reasons.append(rest_why)
        unstable, why = bool(reasons), "; ".join(r for r in reasons if r)
        dominant = report.dominant if report is not None else None

        m = Measurement(
            label=label,
            n_samples=len(samples),
            peak=peak,
            rms=rms,
            score=score,
            unstable=unstable,
            unstable_why=why,
            aborted=bool(meta.get("aborted")),
            abort_reason=str(meta.get("abort_reason") or ""),
            dominant_hz=float(dominant.freq_hz) if dominant else None,
            dominant_mag=float(dominant.magnitude) if dominant else None,
            report=report,
            torque_peak_pct=torque_peak,
            fs_hz=fs,
            ms=sens.ms if sens is not None else None,
            f_ms_hz=sens.f_ms_hz if sens is not None else None,
        )
        csv_path = self.journal.record_samples(label, samples, fs)
        fft_info = _report_to_dict(report)
        fft_info["gate_min_hz"] = gate_min_hz
        fft_info["fs_hz"] = fs
        if sens is not None:
            fft_info["sensitivity"] = sens.summary()
            fft_info["ms"] = sens.ms
        self.journal.event(
            "measure",
            "measurement",
            m.summary(),
            meta=meta_journal,
            csv=csv_path,
            gains={k: self._current.get(k) for k in TOUCHABLE_KEYS},
            fft=fft_info,
        )
        return m

    def _measure_baseline(self) -> Measurement:
        """Measure the baseline N times; spread sets the improvement bar."""
        cfg = self.cfg
        n = max(1, int(cfg.baseline_repeats))
        for i in range(max(0, int(cfg.baseline_warmup))):
            w = self._measure(f"warmup_{i + 1}")
            self.journal.event(
                "baseline", "warmup", f"warm-up move (not scored): {w.summary()}"
            )
        ms = [self._measure("baseline" if n == 1 else f"baseline_{i + 1}")
              for i in range(n)]
        if any(m.unstable for m in ms):
            worst = next(m for m in ms if m.unstable)
            self.journal.event(
                "baseline", "unstable", f"baseline repeat unstable: {worst.summary()}"
            )
            base = worst
        else:
            ordered = sorted(ms, key=lambda m: m.score)
            base = ordered[len(ordered) // 2]  # median
        if n > 1:
            scores = [m.score for m in ms]
            med = base.score if base.score > 0 else max(scores)
            spread_pct = (max(scores) - min(scores)) / med * 100.0 if med > 0 else 0.0
            self._improve_pct = min(
                cfg.max_noise_threshold_pct,
                max(cfg.improvement_min_pct, cfg.noise_k * spread_pct),
            )
            self.journal.event(
                "baseline",
                "noise",
                f"baseline spread {spread_pct:.1f}% over {n} runs -> a step must "
                f"improve the score by >= {self._improve_pct:.1f}%",
                scores=scores,
                spread_pct=spread_pct,
                improve_pct=self._improve_pct,
            )
        if cfg.rest_capture_s > 0 and not cfg.dry_run:
            self._rest_baseline = self._rest_stats("baseline")
        return base

    def _margin_target(self, key: str, unstable_value: float, cur: float) -> float:
        """Gain to settle on after `unstable_value` rang: margin x first ring."""
        self._first_unstable.setdefault(key, unstable_value)
        first = self._first_unstable[key]
        target = min(
            cur,
            max(float(PARAM_BY_KEY[key]["min"]), self.cfg.margin_ratio * first),
        )
        # A "best" step remembered above the margin must never be restored.
        if self._best_values.get(key, -math.inf) > target + 1e-6:
            self.journal.event(
                "margin",
                "best-reset",
                f"best step had {key}={self._best_values[key]:g} above the "
                f"margin {target:g}; it can no longer be kept",
            )
            self._best_values = {}
            self._best_score = math.inf
        return target

    def _rest_stats(self, label: str) -> Optional[Dict[str, float]]:
        capture = getattr(self.io, "capture_rest", None)
        if capture is None:
            return None
        try:
            data = capture(self.cfg.axis, self.cfg.rest_capture_s)
        except Exception as exc:
            self.journal.event("rest", "warning", f"standstill capture failed: {exc}")
            return None
        if not data:
            return None
        ferr = [float(v) for v in data.get("ferr") or []]
        tq = [float(v) for v in data.get("torque_pct") or []]
        stats = {
            "ferr_rms": _rms(ferr),
            "ferr_peak": _peak(ferr),
            # AC rms: steady holding torque (gravity on Z) is not hiss
            "torque_rms_pct": _ac_rms(tq),
            "torque_mean_pct": _mean(tq),
            "torque_peak_pct": _peak(tq),
            "n": float(len(ferr)),
        }
        self.journal.event(
            "rest",
            "standstill",
            f"{label}: rest FERR rms {stats['ferr_rms'] * 1000:.2f} um, "
            f"torque rms {stats['torque_rms_pct']:.2f}% "
            f"(about mean {stats['torque_mean_pct']:.1f}%)",
            **stats,
        )
        return stats

    def _rest_check(self, label: str) -> str:
        """'' if standstill noise is acceptable, else the reason."""
        cfg = self.cfg
        if cfg.rest_capture_s <= 0 or cfg.dry_run:
            return ""
        stats = self._rest_stats(label)
        if stats is None:
            return ""
        why = []
        if stats["torque_rms_pct"] > cfg.rest_torque_rms_max_pct:
            why.append(
                f"standstill torque rms {stats['torque_rms_pct']:.1f}% "
                f"> {cfg.rest_torque_rms_max_pct:g}%"
            )
        if stats["ferr_rms"] > cfg.rest_ferr_rms_max:
            why.append(
                f"standstill FERR rms {stats['ferr_rms'] * 1000:.1f} um "
                f"> {cfg.rest_ferr_rms_max * 1000:g} um"
            )
        return "; ".join(why)

    def _gate_min_hz(self) -> float:
        """Lowest frequency the stability gate treats as a possible resonance.

        The stimulus pulse train forces FERR content up to roughly
        ``gate_min_hz_factor / leg_time`` — flagging those harmonics as
        "resonance" would block the ladder on short/fast strokes.
        """
        cfg = self.cfg
        leg = max(cfg.stimulus.leg_time_s(), 1e-3)
        return min(
            cfg.gate_min_hz_cap,
            max(cfg.gate_min_hz_floor, cfg.gate_min_hz_factor / leg),
        )

    def _classify(
        self,
        report: Optional[ResonanceReport],
        meta: Dict[str, Any],
        label: str = "",
    ) -> Tuple[bool, str]:
        """Engine's own stability gate (report.stable is too twitchy on
        near-silent buffers — tiny spectral peaks must not block the ladder)."""
        if label.startswith("verify"):
            return self._classify_verify(report, meta)
        cfg = self.cfg
        reasons: List[str] = []
        if meta.get("aborted"):
            reasons.append(f"move aborted: {meta.get('abort_reason')}")
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
        elif not meta.get("aborted"):
            reasons.append("no FFT report")
        return (bool(reasons), "; ".join(reasons))

    def _classify_verify(
        self, report: Optional[ResonanceReport], meta: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Verify gate: hard-fail real resonance/ring/abort; HF is relative."""
        cfg = self.cfg
        reasons: List[str] = []
        if meta.get("aborted"):
            reasons.append(f"move aborted: {meta.get('abort_reason')}")
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
                report.ring_score >= cfg.ring_fail
                and report.rms >= cfg.min_meaningful_rms
            ):
                reasons.append(f"ring score {report.ring_score:.2f}")
            score = float(report.peak_abs) + SCORE_RMS_WEIGHT * float(report.rms)
            baseline_hf = self._baseline_hf if self._baseline_hf is not None else 0.0
            hf_limit = max(cfg.hf_fail, baseline_hf + cfg.verify_hf_margin)
            if (
                report.hf_energy_ratio >= hf_limit
                and report.rms >= cfg.min_meaningful_rms
            ):
                beats_baseline = (
                    self._baseline_score is not None
                    and score < self._baseline_score * 0.99
                )
                if not beats_baseline:
                    reasons.append(
                        f"HF energy {report.hf_energy_ratio:.0%} "
                        f"(verify limit {hf_limit:.0%})"
                    )
        elif not meta.get("aborted"):
            reasons.append("no FFT report")
        return (bool(reasons), "; ".join(reasons))

    def _improved(
        self, m: Measurement, ref: Measurement, min_pct: float
    ) -> bool:
        if ref.score <= 0:
            return m.score < ref.score
        return m.score <= ref.score * (1.0 - min_pct / 100.0)

    def _update_best(self, m: Measurement) -> None:
        if m.unstable:
            return
        for key, first in self._first_unstable.items():
            if self._current.get(key, 0.0) > self.cfg.margin_ratio * first + 1e-6:
                return  # above the margin: never a candidate
        if m.score < self._best_score:
            self._best_score = m.score
            self._best_values = {
                k: self._current[k] for k in TOUCHABLE_KEYS if k in self._current
            }

    def _restore_campaign_values(
        self, phase: str, target: Dict[str, float]
    ) -> None:
        keys = self._writable([k for k in TOUCHABLE_KEYS if k in target])
        updates = {
            k: float(target[k])
            for k in keys
            if abs(float(target[k]) - float(self._current.get(k, float("nan"))))
            > 1e-9
        }
        if updates:
            self._write_values(phase, updates)

    def _keep_best_after_verify_failure(
        self, verify_m: Measurement, backoff_m: Measurement
    ) -> bool:
        if not self._best_values or self._baseline_score is None:
            return False
        if self._best_score >= math.inf:
            return False
        improvement = (
            (self._baseline_score - self._best_score)
            / self._baseline_score
            * 100.0
        )
        if improvement < self.cfg.keep_best_min_improve_pct:
            self.journal.event(
                "verify",
                "no-salvage",
                f"verify failed but best only improved {improvement:.1f}% "
                f"(need ≥{self.cfg.keep_best_min_improve_pct:g}%) — reverting",
            )
            return False
        backoff_note = (
            backoff_m.abort_reason
            if backoff_m.aborted
            else backoff_m.unstable_why
        )
        self.journal.event(
            "verify",
            "keep-best",
            f"verify unstable ({verify_m.unstable_why}); "
            f"backoff failed ({backoff_note}) — restoring best stable step "
            f"({improvement:.1f}% better than baseline)",
            best_score=self._best_score,
            baseline_score=self._baseline_score,
            best_values={k: self._best_values[k] for k in sorted(self._best_values)},
            verify_score=verify_m.score,
            backoff_score=backoff_m.score,
        )
        self._restore_campaign_values("verify", self._best_values)
        return True

    def _try_notch(self, phase: str, m: Measurement) -> bool:
        """Write the 3rd manual notch at the dominant FFT peak, if sensible."""
        cfg = self.cfg
        if not cfg.allow_notch or self._notch_attempted:
            return False
        if m.dominant_hz is None or not (40.0 <= m.dominant_hz <= 500.0):
            return False
        current_freq = self._current.get("notch3_freq_hz", NOTCH_DISABLED_HZ)
        if current_freq < NOTCH_DISABLED_HZ - 0.5:
            self.journal.event(
                phase,
                "notch-skip",
                f"3rd notch already in use at {current_freq:g} Hz — "
                "not overwriting it",
            )
            self._notch_attempted = True
            return False
        self._notch_attempted = True
        suggestion = suggest_manual_notch(
            m.dominant_hz,
            notch_index=3,
            width_pct=cfg.notch_width_pct,
            depth_pct=cfg.notch_depth_pct,
        )
        self.journal.event(
            phase,
            "notch",
            f"trying 3rd notch at {m.dominant_hz:.0f} Hz "
            f"(width {cfg.notch_width_pct:g}%, depth {cfg.notch_depth_pct:g}%)",
            suggestion=suggestion,
        )
        self._write_values(phase, suggestion)
        self._notch_applied = True
        return True

    def _revert_notch(self, phase: str) -> None:
        if not self._notch_applied:
            return
        restore = {
            k: self._baseline[k] for k in NOTCH3_KEYS if k in self._baseline
        }
        if restore:
            self.journal.event(
                phase, "notch-revert", "notch did not help — restoring", **restore
            )
            self._write_values(phase, restore)
        self._notch_applied = False

    def _revert_to_baseline(self, phase: str) -> None:
        """Best-effort restore of every touched SDO to its baseline value."""
        if self.cfg.dry_run or not self._touched:
            return
        restore = {
            k: self._baseline[k]
            for k in sorted(self._touched)
            if k in self._baseline
        }
        if not restore:
            return
        self.journal.event(
            phase,
            "revert",
            "restoring baseline values for touched keys",
            values=restore,
        )
        try:
            self._write_values(phase, restore)
            self.journal.event(phase, "revert-ok", "baseline restored")
        except Exception as exc:
            # This is the one place we must scream: drive may hold a mix.
            self.journal.event(
                phase,
                "CRITICAL",
                "REVERT FAILED — drive may hold a mixed tune. Restore these "
                "values by hand (Servo Tuning tab or the pre_one_click "
                "preset): "
                + ", ".join(f"{k}={v:g}" for k, v in restore.items())
                + f" | error: {exc}",
            )

    def _save_final_preset(self) -> Optional[str]:
        name = (
            f"one_click_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        params = AxisTuneParams.__new__(AxisTuneParams)
        values = dict(self._baseline)
        values.update(
            {k: self._current[k] for k in self._touched if k in self._current}
        )
        params.values = values
        try:
            path = self.io.save_preset(
                self.cfg.axis,
                name,
                params,
                notes=f"one-click auto-tune ({self.cfg.profile})",
            )
            self.journal.event(
                "finalize", "preset", f"final tune saved as preset {name}", path=path
            )
            return name
        except Exception as exc:
            self.journal.event(
                "finalize", "warning", f"could not save final preset: {exc}"
            )
            return None

    def _finalize(self, result: OneClickResult) -> None:
        result.measurements = self._measure_count
        self.journal.finalize(
            result.status,
            {
                "reason": result.reason,
                "baseline_score": result.baseline_score,
                "final_score": result.final_score,
                "improvement_pct": result.improvement_pct,
                "baseline_values": result.baseline_values,
                "final_values": result.final_values,
                "measurements": result.measurements,
                "notch_applied": self._notch_applied,
                "preset": result.preset_name,
            },
        )
        self._progress("done", result.summary().splitlines()[0])


def _fmt(value: Any) -> str:
    if value is None:
        return "?"
    try:
        return f"{round(float(value), 4):g}"
    except (TypeError, ValueError):
        return str(value)


def _peak(samples: List[float]) -> float:
    finite = [abs(v) for v in samples if v == v]
    return max(finite) if finite else 0.0


def _mean(samples: List[float]) -> float:
    finite = [v for v in samples if v == v]
    return sum(finite) / len(finite) if finite else 0.0


def _ac_rms(samples: List[float]) -> float:
    """RMS about the mean (the DC holding torque removed)."""
    finite = [v for v in samples if v == v]
    if not finite:
        return 0.0
    m = sum(finite) / len(finite)
    return math.sqrt(sum((v - m) ** 2 for v in finite) / len(finite))


def _rms(samples: List[float]) -> float:
    finite = [v for v in samples if v == v]
    if not finite:
        return 0.0
    return math.sqrt(sum(v * v for v in finite) / len(finite))
