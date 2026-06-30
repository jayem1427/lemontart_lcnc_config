"""Generic HAL signal logger for LinuxCNC / Probe Basic.

Loads channel definitions from JSON presets, samples HAL pins on a timer,
writes CSV logs + text summaries, and exposes live buffers for plotting.
"""

from __future__ import annotations

import csv
import json
import math
import os
import re
import subprocess
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional

import linuxcnc


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
class LoggerPreset:
    name: str
    description: str
    rate_hz: float
    trigger: str
    log_subdir: str
    context: List[str]
    channels: List[ChannelConfig]
    plot_groups: List[PlotGroupConfig]
    live_buffer: int = 500

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LoggerPreset":
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
            trigger=data.get("trigger", "program"),
            log_subdir=data.get("log_subdir", data["name"]),
            context=list(data.get("context", ["line", "feed"])),
            channels=channels,
            plot_groups=plot_groups,
            live_buffer=int(data.get("live_buffer", 500)),
        )


def repo_root() -> str:
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
    )


def default_preset_dir() -> str:
    return os.path.join(repo_root(), "config", "logging")


def load_preset(path: str) -> LoggerPreset:
    with open(path, "r", encoding="utf-8") as handle:
        return LoggerPreset.from_dict(json.load(handle))


def list_presets(preset_dir: Optional[str] = None) -> List[str]:
    directory = preset_dir or default_preset_dir()
    if not os.path.isdir(directory):
        return []
    return sorted(
        os.path.join(directory, name)
        for name in os.listdir(directory)
        if name.endswith(".json")
    )


def hal_getp(pin: str) -> float:
    try:
        output = subprocess.check_output(
            ["halcmd", "getp", pin],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return float(output.strip())
    except (subprocess.CalledProcessError, ValueError):
        return float("nan")


def _sanitize_name(value: str) -> str:
    base = os.path.basename(value or "session")
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", base)
    return cleaned.strip("_") or "session"


class HalSignalLogger:
    """Sample configured HAL pins and write CSV logs."""

    def __init__(
        self,
        preset: LoggerPreset,
        log_root: Optional[str] = None,
        ini_path: Optional[str] = None,
        live_buffer: Optional[int] = None,
    ) -> None:
        self.preset = preset
        self.log_root = log_root or os.path.join(repo_root(), "logs")
        self.log_dir = os.path.join(self.log_root, preset.log_subdir)
        self.ini_path = ini_path or os.environ.get(
            "INI_FILE_NAME", os.path.join(repo_root(), "ethercat_mill.ini")
        )
        self.stat = linuxcnc.stat()
        self.rate_hz = preset.rate_hz
        self.trigger = preset.trigger

        buffer_len = live_buffer or preset.live_buffer
        self._buffers: Dict[str, Deque[float]] = {
            channel.id: deque(maxlen=buffer_len) for channel in preset.channels
        }
        self._session_max: Dict[str, float] = {}
        self._session_sum_sq: Dict[str, float] = {}
        self._session_count = 0

        self.state = "idle"
        self._csv_file = None
        self._csv_writer = None
        self._session_path: Optional[str] = None
        self._summary_path: Optional[str] = None
        self._session_name = ""
        self._t0 = 0.0
        self._last_sample = 0.0
        self._last_context: Dict[str, Any] = {}
        self.live_stats: Dict[str, Dict[str, float]] = {}

        os.makedirs(self.log_dir, exist_ok=True)

    def poll(self) -> None:
        if self.state == "idle":
            if self.trigger == "program" and self._program_running():
                program = self._current_program_name()
                self.start_manual(program)
            return

        if self.state != "logging":
            return

        now = time.time()
        if now - self._last_sample < (1.0 / self.rate_hz):
            if self.trigger == "program" and not self._program_running():
                self.stop_manual()
            return

        self._sample(now)
        self._last_sample = now

        if self.trigger == "program" and not self._program_running():
            self.stop_manual()

    def start_manual(self, session_name: str = "manual") -> None:
        if self.state == "logging":
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = _sanitize_name(session_name)
        base = f"{timestamp}_{safe_name}"
        self._session_path = os.path.join(self.log_dir, f"{base}.csv")
        self._summary_path = os.path.join(self.log_dir, f"{base}.summary.txt")
        self._session_name = safe_name
        self._t0 = time.time()
        self._last_sample = 0.0
        self._session_max = {channel.id: 0.0 for channel in self.preset.channels}
        self._session_sum_sq = {channel.id: 0.0 for channel in self.preset.channels}
        self._session_count = 0
        for buffer in self._buffers.values():
            buffer.clear()

        header = ["t"] + list(self.preset.context)
        header.extend(channel.id for channel in self.preset.channels)

        self._csv_file = open(self._session_path, "w", newline="", encoding="utf-8")
        self._csv_writer = csv.writer(self._csv_file)
        self._csv_writer.writerow(header)
        self.state = "logging"

    def stop_manual(self) -> None:
        if self.state != "logging":
            return
        if self._csv_file is not None:
            self._csv_file.close()
            self._csv_file = None
            self._csv_writer = None
        self._write_summary()
        self.state = "idle"

    def get_buffers(self) -> Dict[str, Deque[float]]:
        return self._buffers

    def get_plot_groups(self) -> List[PlotGroupConfig]:
        return self.preset.plot_groups

    def get_channels(self) -> List[ChannelConfig]:
        return self.preset.channels

    def channel_by_id(self) -> Dict[str, ChannelConfig]:
        return {channel.id: channel for channel in self.preset.channels}

    def _program_running(self) -> bool:
        self.stat.poll()
        return (
            self.stat.task_mode == linuxcnc.MODE_AUTO
            and self.stat.exec_state == linuxcnc.EXEC_ON
        )

    def _current_program_name(self) -> str:
        self.stat.poll()
        return _sanitize_name(self.stat.file or "program")

    def _read_context(self) -> Dict[str, Any]:
        self.stat.poll()
        context: Dict[str, Any] = {}
        for key in self.preset.context:
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
        self._last_context = context
        return context

    def _sample(self, now: Optional[float] = None) -> None:
        if self._csv_writer is None:
            return

        sample_time = (now or time.time()) - self._t0
        context = self._read_context()
        row: List[Any] = [f"{sample_time:.3f}"]
        row.extend(context.get(key, "") for key in self.preset.context)

        self.live_stats = {}
        for channel in self.preset.channels:
            raw = hal_getp(channel.pin) * channel.scale
            if math.isnan(raw):
                value = raw
            else:
                value = raw
                abs_val = abs(value)
                self._session_max[channel.id] = max(
                    self._session_max[channel.id], abs_val
                )
                self._session_sum_sq[channel.id] += value * value
                self._buffers[channel.id].append(value)

            row.append("" if math.isnan(value) else f"{value:.6f}")

            buffer = self._buffers[channel.id]
            if buffer:
                rms = math.sqrt(sum(item * item for item in buffer) / len(buffer))
                peak = max(abs(item) for item in buffer)
            else:
                rms = 0.0
                peak = 0.0
            self.live_stats[channel.id] = {
                "last": 0.0 if math.isnan(value) else value,
                "rms": rms,
                "peak": peak,
                "session_max": self._session_max[channel.id],
            }

        self._csv_writer.writerow(row)
        self._session_count += 1

    def _write_summary(self) -> None:
        if self._summary_path is None:
            return

        duration = time.time() - self._t0
        limits = self._read_ferror_limits()
        lines = [
            f"preset: {self.preset.name}",
            f"session: {self._session_name}",
            f"duration_s: {duration:.2f}",
            f"samples: {self._session_count}",
            f"csv: {self._session_path}",
            "",
        ]

        for channel in self.preset.channels:
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
        }
        for channel_id, joint in mapping.items():
            if not any(item.id == channel_id for item in self.preset.channels):
                continue
            section = f"JOINT_{joint}"
            value = ini.find(section, "FERROR")
            if value is not None:
                limits[channel_id] = float(value)
        return limits
