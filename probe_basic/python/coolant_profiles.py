"""Parse probe_basic/coolant_tools.ini into per-tool PWM recipes.

No LinuxCNC imports — unit-testable on any Python 3.
"""

from __future__ import annotations

import re
from configparser import ConfigParser
from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class CoolantRecipe:
    freq: float
    duty: float
    pressure: float


def _f(section, key, fallback):
    raw = section.get(key, fallback)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return float(fallback)


def _parse_tool_section(name):
    text = name.strip()
    if text.lower() == "default":
        return None
    if text[:1] in "Tt":
        text = text[1:]
    if not text.isdigit():
        return None
    return int(text)


def load_profiles(path):
    """Return (default_recipe, {tool_number: recipe}).

    Per-tool sections inherit unspecified keys from [DEFAULT].
    """
    parser = ConfigParser(interpolation=None)
    parser.optionxform = str  # keep FREQ/DUTY/PRESSURE
    read = parser.read(path)
    if not read:
        raise FileNotFoundError("coolant profile file not found: %s" % path)

    # ConfigParser's DEFAULT is not a named section (has_section is False).
    default = CoolantRecipe(
        freq=_f(parser.defaults(), "FREQ", 0),
        duty=_f(parser.defaults(), "DUTY", 0),
        pressure=_f(parser.defaults(), "PRESSURE", 0),
    )

    tools = {}  # type: Dict[int, CoolantRecipe]
    for name in parser.sections():
        tool = _parse_tool_section(name)
        if tool is None:
            continue
        sec = parser[name]
        tools[tool] = CoolantRecipe(
            freq=_f(sec, "FREQ", default.freq),
            duty=_f(sec, "DUTY", default.duty),
            pressure=_f(sec, "PRESSURE", default.pressure),
        )
    return default, tools


def recipe_for_tool(default, tools, tool_number):
    """Empty spindle (T<=0) is always dry. Unknown tools use [DEFAULT]."""
    try:
        tool = int(tool_number)
    except (TypeError, ValueError):
        tool = 0
    if tool <= 0:
        return CoolantRecipe(0.0, 0.0, 0.0)
    found = tools.get(tool)
    if found is None:
        return default
    return found


_SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*$")
_KEY_RE = re.compile(r"^\s*([A-Za-z_]+)\s*[=:]")


def _fmt(value):
    return "%g" % float(value)


def save_tool_recipe(path, tool_number, values):
    """Set keys (e.g. {"FREQ": 10, "DUTY": 1.5}) in [T<n>], keeping comments.

    Existing keys are rewritten in place; missing keys go right after the
    section header. A missing section is appended at the end of the file.
    """
    tool = int(tool_number)
    if tool <= 0:
        raise ValueError("tool number must be > 0 (T0 is always dry)")
    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.read().splitlines()

    start = None
    end = len(lines)
    for idx, line in enumerate(lines):
        match = _SECTION_RE.match(line)
        if not match:
            continue
        if start is not None:
            end = idx
            break
        if _parse_tool_section(match.group(1)) == tool:
            start = idx

    pending = {key.upper(): val for key, val in values.items()}
    if start is None:
        while lines and not lines[-1].strip():
            lines.pop()
        lines.append("")
        lines.append("[T%d]" % tool)
        lines.extend("%s = %s" % (key, _fmt(val)) for key, val in pending.items())
    else:
        for idx in range(start + 1, end):
            match = _KEY_RE.match(lines[idx])
            if match and match.group(1).upper() in pending:
                key = match.group(1).upper()
                lines[idx] = "%s = %s" % (key, _fmt(pending.pop(key)))
        for offset, (key, val) in enumerate(pending.items(), start=1):
            lines.insert(start + offset, "%s = %s" % (key, _fmt(val)))

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
