"""Generic HAL signal logger for LinuxCNC / Probe Basic.

Loads channel definitions from a single JSON config, samples HAL pins on a timer,
writes one CSV log + text summary per session, and exposes live buffers for plotting.
"""

from __future__ import annotations

import csv
import json
import logging
import math
import os
import re
import subprocess
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Deque, Dict, List, Optional

import linuxcnc

LOG = logging.getLogger(__name__)

SessionSavedCallback = Callable[[str, str], None]


@dataclass
class ChannelConfig:
    id: str
    pin: str
    label: str
    units: str = ""
    color: str = "#ffffff"
    group: str = "default"
    scale: float = 1.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChannelConfig":
        return cls(
            id=data["id"],
            pin=data["pin"],
            label=data.get("label", data["id"]),
            units=data.get("units", ""),
            color=data.get("color", "#ffffff"),
            group=data.get("group", "default"),
            scale=float(data.get("scale", 1.0)),
        )


@dataclass
class PlotGroupConfig:
    id: str
    title: str
    y_mode: str = "auto"
    y_min: Optional[float] = None
    y_max: Optional[float] = None
    channels: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlotGroupConfig":
        return cls(
            id=data["id"],
            title=data.get("title", data["id"]),
            y_mode=data.get("y_mode", "auto"),
            y_min=data.get("y_min"),
            y_max=data.get("y_max"),
            channels=list(data.get("channels", [])),
        )


@dataclass
class LoggerConfig:
    name: str
    description: str
    rate_hz: float
    log_subdir: str
    context: List[str]
    channels: List[ChannelConfig]
    plot_groups: List[PlotGroupConfig]
    live_buffer: int = 500

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LoggerConfig":
        channels = [ChannelConfig.from_dict(item) for item in data["channels"]]
        plot_groups = [
            PlotGroupConfig.from_dict(item) for item in data.get("plot_groups", [])
        ]
        if not plot_groups:
            plot_groups = [
                PlotGroupConfig(
                    id="default",
                    title=data.get("name", "signals"),
                    channels=[channel.id for channel in channels],
                )
            ]
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            rate_hz=float(data.get("rate_hz", 50)),
            log_subdir=data.get("log_subdir", data["name"]),
            context=list(data.get("context", ["line", "feed"])),
            channels=channels,
            plot_groups=plot_groups,
            live_buffer=int(data.get("live_buffer", 500)),
        )


# Backward-compatible alias
LoggerPreset = LoggerConfig


def repo_root() -> str:
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
    )


def default_config_dir() -> str:
    return os.path.join(repo_root(), "config", "logging")


def default_preset_dir() -> str:
    return default_config_dir()


def default_config_path() -> str:
    return os.path.join(default_config_dir(), "signals.json")


def load_config(path: Optional[str] = None) -> LoggerConfig:
    config_path = path or default_config_path()
    with open(config_path, "r", encoding="utf-8") as handle:
        return LoggerConfig.from_dict(json.load(handle))


def load_preset(path: str) -> LoggerConfig:
    return load_config(path)


# Drive telemetry is read through a6_servo_tune (same path as Servo Tuning).
# Do not create a separate pb_signal_logger HAL component — get_value on that
# path returned NaN for every tune-*/lcec.* pin while pb_a6_tune worked.


def _joint_ferror_from_pin(pin: str) -> Optional[int]:
    """Return joint index if pin is ``joint.N.f-error``, else None."""
    match = re.match(r"^joint\.(\d+)\.f-error$", pin.strip())
    if not match:
        return None
    return int(match.group(1))


def _joint_pos_from_pin(pin: str) -> Optional[int]:
    """Return joint index if pin is ``joint.N.pos-fb``, else None."""
    match = re.match(r"^joint\.(\d+)\.pos-fb$", pin.strip())
    if not match:
        return None
    return int(match.group(1))


_JOINT_TO_AXIS = {0: "X", 1: "Y", 2: "Z", 3: "A"}


def _axis_from_tune_pin(pin: str) -> Optional[str]:
    match = re.match(
        r"^tune-(?:drive-ferr|torque|velocity)\.(\d+)\.out$", pin.strip()
    )
    if not match:
        return None
    return _JOINT_TO_AXIS.get(int(match.group(1)))


def _tune_hal_getp(pin: str) -> float:
    """Read HAL via the same path Servo Tuning uses (``pb_a6_tune``)."""
    try:
        from a6_servo_tune import hal_getp as tune_hal_getp

        return float(tune_hal_getp(pin))
    except Exception:
        LOG.exception("a6_servo_tune.hal_getp failed for %s", pin)
        return float("nan")


def hal_getp(pin: str, *, allow_subprocess: bool = False) -> float:
    """Compatibility wrapper — prefer Servo Tuning's HAL reader."""
    del allow_subprocess  # kept for call-site compatibility
    return _tune_hal_getp(pin)


def _sanitize_name(value: str) -> str:
    base = os.path.basename(value or "session")
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", base)
    return cleaned.strip("_") or "session"


class HalSignalLogger:
    """Sample configured HAL pins and write one CSV log per session."""

    def __init__(
        self,
        config: LoggerConfig,
        log_root: Optional[str] = None,
        ini_path: Optional[str] = None,
        live_buffer: Optional[int] = None,
        on_session_saved: Optional[SessionSavedCallback] = None,
    ) -> None:
        self.config = config
        self.preset = config  # backward-compatible alias
        self.log_root = log_root or os.path.join(repo_root(), "logs")
        self.log_dir = os.path.join(self.log_root, config.log_subdir)
        self.ini_path = ini_path or os.environ.get(
            "INI_FILE_NAME", os.path.join(repo_root(), "ethercat_mill.ini")
        )
        self.stat = linuxcnc.stat()
        self.rate_hz = config.rate_hz
        self.on_session_saved = on_session_saved

        buffer_len = live_buffer or config.live_buffer
        self._buffers: Dict[str, Deque[float]] = {
            channel.id: deque(maxlen=buffer_len) for channel in config.channels
        }
        # Rolling-window sum of squares for O(1) live RMS (avoids scanning 5k
        # samples × N channels on every sample — that was starving the GUI).
        self._rolling_sum_sq: Dict[str, float] = {
            channel.id: 0.0 for channel in config.channels
        }
        self._rolling_peak: Dict[str, float] = {
            channel.id: 0.0 for channel in config.channels
        }
        self._session_max: Dict[str, float] = {}
        self._session_sum_sq: Dict[str, float] = {}
        self._session_count = 0

        self.state = "idle"
        self._armed = False
        self._auto_stop_on_program_end = False
        self._csv_file = None
        self._csv_writer = None
        self._session_path: Optional[str] = None
        self._summary_path: Optional[str] = None
        self._session_name = ""
        self._t0 = 0.0
        self._last_sample = 0.0
        self._context_cache: Dict[str, Any] = {}
        self._context_cache_t = 0.0
        self._hal_ok = False
        self._write_csv = True
        self.last_session_path: Optional[str] = None
        self.last_summary_path: Optional[str] = None
        self.live_stats: Dict[str, Dict[str, float]] = {}
        self.last_error: str = ""
        self._drive_nan_streak = 0

        os.makedirs(self.log_dir, exist_ok=True)

    def set_rate_hz(self, rate_hz: float) -> None:
        """Sample rate for live buffers / CSV (idle or live session)."""
        self.rate_hz = max(1.0, min(float(rate_hz), 2000.0))

    @property
    def status(self) -> str:
        if self.state == "logging":
            return "logging"
        if self._armed:
            return "armed"
        return "idle"

    def arm_for_next_program(self) -> None:
        if self.state == "logging":
            return
        self._armed = True

    def disarm(self) -> None:
        self._armed = False

    def is_armed(self) -> bool:
        return self._armed

    @property
    def is_live_session(self) -> bool:
        return self.state == "logging" and not self._auto_stop_on_program_end

    def start_live(self) -> None:
        if self.state == "logging":
            return
        self._armed = False
        self._auto_stop_on_program_end = False
        self._begin_session("live")

    def stop(self) -> None:
        self._end_session()

    def poll(self) -> None:
        """Must run on the Qt/UI thread (same thread that created the HAL comp).

        Servo Tuning's FERR plot works because it reads HAL on the UI thread.
        Cross-thread ``hal.get_value`` returns NaN here — that left the plot empty.
        """
        if self.state == "idle":
            if self._armed and self._program_running():
                self._armed = False
                self._auto_stop_on_program_end = True
                try:
                    self._begin_session(self._current_program_name())
                except RuntimeError:
                    LOG.exception("armed session failed to start")
                    self._armed = False
            return

        if self.state != "logging":
            return

        now = time.time()
        interval = 1.0 / max(self.rate_hz, 1.0)
        if self._last_sample <= 0.0:
            self._last_sample = now - interval

        # Cap catch-up so a slow UI frame doesn't dump a huge burst.
        max_catchup = max(1, int(self.rate_hz * 0.05))
        samples = 0
        while now - self._last_sample >= interval and samples < max_catchup:
            self._last_sample += interval
            self._sample(self._last_sample)
            samples += 1

        if samples >= max_catchup and now - self._last_sample >= interval:
            self._last_sample = now

        if self._auto_stop_on_program_end and not self._program_running():
            self._end_session()

    def start_manual(self, session_name: str = "manual") -> None:
        """Backward-compatible alias for start_live or explicit session start."""
        if self.state == "logging":
            return
        self._armed = False
        self._auto_stop_on_program_end = False
        self._begin_session(session_name)

    def stop_manual(self) -> None:
        """Backward-compatible alias for stop."""
        self._end_session()

    def get_buffers(self) -> Dict[str, Deque[float]]:
        return self._buffers

    def snapshot_buffers(self, channel_ids: Optional[List[str]] = None) -> Dict[str, List[float]]:
        ids = channel_ids or [c.id for c in self.config.channels]
        return {cid: list(self._buffers.get(cid, ())) for cid in ids}

    def snapshot_live_stats(self, channel_ids: Optional[List[str]] = None) -> Dict[str, Dict[str, float]]:
        ids = channel_ids or list(self.live_stats.keys())
        return {cid: dict(self.live_stats[cid]) for cid in ids if cid in self.live_stats}

    def get_plot_groups(self) -> List[PlotGroupConfig]:
        return self.config.plot_groups

    def get_channels(self) -> List[ChannelConfig]:
        return self.config.channels

    def channel_by_id(self) -> Dict[str, ChannelConfig]:
        return {channel.id: channel for channel in self.config.channels}

    def _ensure_fast_hal(self) -> bool:
        """Prove drive telemetry is readable via the Servo Tuning HAL path."""
        try:
            self.stat.poll()
        except Exception as exc:
            self.last_error = f"LinuxCNC status unavailable: {exc}"
            self._hal_ok = False
            return False

        # Same readers Servo Tuning uses — raw lcec PDOs, not tune-* floats
        # (those were returning NaN and painting a flat zero plot).
        try:
            from a6_servo_tune import (
                read_drive_ferr,
                read_drive_torque,
                read_drive_velocity,
            )
        except Exception as exc:
            self.last_error = f"a6_servo_tune import failed: {exc}"
            self._hal_ok = False
            return False

        probes = [
            ("X FERR", lambda: read_drive_ferr("X")[1]),
            ("X TORQUE", lambda: read_drive_torque("X")),
            ("X VEL", lambda: read_drive_velocity("X")),
        ]
        ok_name = None
        ok_val = float("nan")
        for name, reader in probes:
            try:
                val = float(reader())
            except Exception:
                val = float("nan")
            if not math.isnan(val):
                ok_name = name
                ok_val = val
                break

        if ok_name is None:
            self.last_error = (
                "No readable drive telemetry (lcec ferr/torque/vel) — "
                "is EtherCAT in OP? Servo Tuning START PLOT uses the "
                "same pins."
            )
            self._hal_ok = False
            return False

        LOG.info("signal logger HAL ok — %s=%.6g", ok_name, ok_val)
        self._hal_ok = True
        self.last_error = ""
        self._drive_nan_streak = 0
        return True

    def _read_pin(self, pin: str) -> float:
        """Read one pin; joint f-error / pos-fb come from linuxcnc.stat."""
        joint_idx = _joint_ferror_from_pin(pin)
        if joint_idx is not None:
            try:
                self.stat.poll()
                return float(self.stat.joint[joint_idx]["ferror_current"])
            except Exception:
                return float("nan")
        joint_idx = _joint_pos_from_pin(pin)
        if joint_idx is not None:
            try:
                self.stat.poll()
                return float(self.stat.joint_actual_position[joint_idx])
            except Exception:
                return float("nan")
        return _tune_hal_getp(pin)

    def _read_channel(self, channel: ChannelConfig) -> float:
        """Drive channels use raw lcec PDOs; joint ferror/pos use stat."""
        joint_idx = _joint_ferror_from_pin(channel.pin)
        if joint_idx is not None:
            try:
                self.stat.poll()
                return float(self.stat.joint[joint_idx]["ferror_current"]) * channel.scale
            except Exception:
                return float("nan")

        joint_idx = _joint_pos_from_pin(channel.pin)
        if joint_idx is not None:
            try:
                self.stat.poll()
                return float(self.stat.joint_actual_position[joint_idx]) * channel.scale
            except Exception:
                return float("nan")

        axis = _axis_from_tune_pin(channel.pin)
        if axis is not None:
            try:
                from a6_servo_tune import (
                    read_drive_ferr,
                    read_drive_torque,
                    read_drive_velocity,
                )

                if "drive-ferr" in channel.pin:
                    _counts, scaled = read_drive_ferr(axis)
                    return float(scaled) * channel.scale
                if "torque" in channel.pin:
                    return float(read_drive_torque(axis)) * channel.scale
                if "velocity" in channel.pin:
                    return float(read_drive_velocity(axis)) * channel.scale
            except Exception:
                LOG.exception("drive read failed for %s", channel.pin)
                return float("nan")

        return self._read_pin(channel.pin) * channel.scale

    def _begin_session(self, session_name: str) -> None:
        if self.state == "logging":
            return

        if not self._ensure_fast_hal():
            LOG.error("%s", self.last_error)
            raise RuntimeError(self.last_error)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = _sanitize_name(session_name)
        base = f"{timestamp}_{safe_name}"
        self._session_path = os.path.join(self.log_dir, f"{base}.csv")
        self._summary_path = os.path.join(self.log_dir, f"{base}.summary.txt")
        self._session_name = safe_name
        self._t0 = time.time()
        self._last_sample = 0.0
        self._session_max = {channel.id: 0.0 for channel in self.config.channels}
        self._session_sum_sq = {channel.id: 0.0 for channel in self.config.channels}
        self._session_count = 0
        for channel in self.config.channels:
            self._buffers[channel.id].clear()
            self._rolling_sum_sq[channel.id] = 0.0
            self._rolling_peak[channel.id] = 0.0
        self.live_stats = {}
        self._context_cache = {}
        self._context_cache_t = 0.0

        header = ["t"] + list(self.config.context)
        header.extend(channel.id for channel in self.config.channels)

        if self._write_csv:
            self._csv_file = open(
                self._session_path,
                "w",
                newline="",
                encoding="utf-8",
                buffering=1024 * 64,
            )
            self._csv_writer = csv.writer(self._csv_file)
            self._csv_writer.writerow(header)
        else:
            self._csv_file = None
            self._csv_writer = None
            self._session_path = None
            self._summary_path = None

        self.state = "logging"

    def _end_session(self) -> None:
        if self.state != "logging":
            return

        csv_path = self._session_path
        summary_path = self._summary_path

        if self._csv_file is not None:
            try:
                self._csv_file.flush()
            except Exception:
                pass
            self._csv_file.close()
            self._csv_file = None
            self._csv_writer = None

        if csv_path:
            self._write_summary()
        self.state = "idle"
        self._auto_stop_on_program_end = False

        if csv_path:
            self.last_session_path = csv_path
            self.last_summary_path = summary_path
            if self.on_session_saved is not None:
                self.on_session_saved(csv_path, summary_path or "")

    def _program_running(self) -> bool:
        self.stat.poll()
        return (
            self.stat.task_mode == linuxcnc.MODE_AUTO
            and self.stat.interp_state != linuxcnc.INTERP_IDLE
        )

    def _current_program_name(self) -> str:
        self.stat.poll()
        return _sanitize_name(self.stat.file or "program")

    def _read_context(self, now: Optional[float] = None) -> Dict[str, Any]:
        """Cache NML status — no need to poll every sample."""
        t = now if now is not None else time.time()
        if self._context_cache and (t - self._context_cache_t) < 0.05:
            return self._context_cache
        self.stat.poll()
        context: Dict[str, Any] = {}
        for key in self.config.context:
            if key == "line":
                context[key] = self.stat.current_line
            elif key == "feed":
                context[key] = round(float(self.stat.current_vel), 4)
            elif key == "motion_type":
                context[key] = int(self.stat.motion_type)
            elif key == "enabled":
                context[key] = int(self.stat.enabled)
            else:
                context[key] = ""
        self._context_cache = context
        self._context_cache_t = t
        return context

    def _push_sample(self, channel_id: str, value: float) -> None:
        """Append to the rolling buffer and update O(1) RMS / peak trackers."""
        buffer = self._buffers[channel_id]
        dropped: Optional[float] = None
        if buffer.maxlen is not None and len(buffer) >= buffer.maxlen:
            dropped = buffer[0]
        buffer.append(value)

        sum_sq = self._rolling_sum_sq[channel_id] + value * value
        peak = self._rolling_peak[channel_id]
        abs_val = abs(value)
        if abs_val > peak:
            peak = abs_val

        if dropped is not None:
            sum_sq -= dropped * dropped
            if sum_sq < 0.0:
                sum_sq = 0.0
            if abs(dropped) >= peak - 1e-15:
                peak = max((abs(v) for v in buffer), default=0.0)

        self._rolling_sum_sq[channel_id] = sum_sq
        self._rolling_peak[channel_id] = peak

    def _sample(self, now: Optional[float] = None) -> None:
        stamp = now or time.time()
        sample_time = stamp - self._t0
        context = self._read_context(stamp)
        row: Optional[List[Any]] = None
        if self._csv_writer is not None:
            row = [f"{sample_time:.3f}"]
            row.extend(context.get(key, "") for key in self.config.context)

        drive_nan = 0
        drive_total = 0
        for channel in self.config.channels:
            raw = self._read_channel(channel)
            is_drive = _axis_from_tune_pin(channel.pin) is not None
            if is_drive:
                drive_total += 1
            if math.isnan(raw):
                got = False
                if is_drive:
                    drive_nan += 1
                # Keep prior sample so the plot does not lie with fake zeros.
                if self._buffers[channel.id]:
                    last = self._buffers[channel.id][-1]
                else:
                    last = 0.0
            else:
                got = True
                last = raw
                abs_val = abs(raw)
                self._session_max[channel.id] = max(
                    self._session_max[channel.id], abs_val
                )
                self._session_sum_sq[channel.id] += raw * raw
                self._push_sample(channel.id, raw)

            if row is not None:
                row.append(f"{last:.6f}" if got else "")

            n = len(self._buffers[channel.id])
            sum_sq = self._rolling_sum_sq[channel.id]
            rms = math.sqrt(sum_sq / n) if n else 0.0
            self.live_stats[channel.id] = {
                "last": last,
                "rms": rms,
                "peak": self._rolling_peak[channel.id],
                "session_max": self._session_max[channel.id],
            }

        if drive_total and drive_nan == drive_total:
            self._drive_nan_streak = getattr(self, "_drive_nan_streak", 0) + 1
            if self._drive_nan_streak == 25:
                self.last_error = (
                    "Drive PDO reads are NaN — plot would stay flat. "
                    "Check EtherCAT OP / Servo Tuning START PLOT."
                )
                LOG.error("%s", self.last_error)
        else:
            self._drive_nan_streak = 0

        if row is not None and self._csv_writer is not None:
            self._csv_writer.writerow(row)
        self._session_count += 1

    def _write_summary(self) -> None:
        if self._summary_path is None:
            return

        duration = time.time() - self._t0
        limits = self._read_ferror_limits()
        lines = [
            f"config: {self.config.name}",
            f"session: {self._session_name}",
            f"duration_s: {duration:.2f}",
            f"samples: {self._session_count}",
            f"csv: {self._session_path}",
            "",
        ]

        for channel in self.config.channels:
            count = max(self._session_count, 1)
            rms = math.sqrt(self._session_sum_sq[channel.id] / count)
            peak = self._session_max[channel.id]
            unit = f" {channel.units}" if channel.units else ""
            lines.append(
                f"{channel.id}: max={peak:.6f}{unit} rms={rms:.6f}{unit} pin={channel.pin}"
            )

            limit = limits.get(channel.id)
            if limit is not None and peak > 0:
                pct = 100.0 * peak / limit
                lines.append(f"  vs_limit: {pct:.1f}% of {limit}")

        with open(self._summary_path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")

    def _read_ferror_limits(self) -> Dict[str, float]:
        limits: Dict[str, float] = {}
        try:
            ini = linuxcnc.ini(self.ini_path)
        except Exception:
            return limits

        mapping = {
            "x_ferr": 0,
            "y_ferr": 1,
            "z_ferr": 2,
            "a_ferr": 3,
            "x_ferr_drive": 0,
            "y_ferr_drive": 1,
            "z_ferr_drive": 2,
            "a_ferr_drive": 3,
        }
        for channel_id, joint in mapping.items():
            if not any(item.id == channel_id for item in self.config.channels):
                continue
            section = f"JOINT_{joint}"
            value = ini.find(section, "FERROR")
            if value is not None:
                limits[channel_id] = float(value)
        return limits
