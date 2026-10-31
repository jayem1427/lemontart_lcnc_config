"""Parse probe_basic/coolant_tools.ini into per-tool PWM recipes.

No LinuxCNC imports — unit-testable on any Python 3.
"""

from __future__ import annotations

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
