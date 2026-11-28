"""Parse probe_basic/coolant_tools.ini: tool-agnostic presets + tool assignments.

No LinuxCNC imports, so it's unit-testable on any Python 3.

File layout (comments are kept when the tab edits it):

    [DEFAULT]               fallback for tools with no entry, and for keys a
    FREQ = 10               preset or tool leaves out
    DUTY = 1
    PRESSURE = 0

    [PRESET Heavy]          a named recipe; any preset can go on any tool
    FREQ = 10
    DUTY = 2

    [T12]                   tool 12 uses the Heavy preset
    PRESET = Heavy

    [T7]                    a tool may still carry its own numbers (older
    DUTY = 3                files did only this). Keys written in a tool
                            section override its preset, key by key.

Resolution for a tool: [DEFAULT] <- [PRESET <name>] <- the tool's own keys.
A tool that names a preset that doesn't exist falls back to [DEFAULT] plus
its own keys and is flagged ``missing_preset`` (M202 warns once). T0 (empty
spindle) is always dry.
"""

from __future__ import annotations

import re
from configparser import ConfigParser
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

RECIPE_KEYS = ("FREQ", "DUTY", "PRESSURE")
PRESET_PREFIX = "PRESET "


@dataclass(frozen=True)
class CoolantRecipe:
    freq: float
    duty: float
    pressure: float


@dataclass
class ToolEntry:
    tool: int
    preset: Optional[str]          # preset name as written, or None
    overrides: Dict[str, float]    # keys written in the tool section itself
    recipe: CoolantRecipe          # fully resolved
    missing_preset: bool = False   # names a preset that isn't in the file


@dataclass
class CoolantLibrary:
    default: CoolantRecipe
    presets: Dict[str, CoolantRecipe] = field(default_factory=dict)  # file order
    tools: Dict[int, ToolEntry] = field(default_factory=dict)

    def preset_named(self, name) -> Optional[str]:
        """Exact stored spelling of a preset name, matched case-insensitively."""
        want = (name or "").strip().lower()
        for stored in self.presets:
            if stored.lower() == want:
                return stored
        return None

    def tools_using(self, name) -> List[int]:
        want = (name or "").strip().lower()
        return sorted(t for t, e in self.tools.items()
                      if e.preset is not None and e.preset.lower() == want)


def _num(raw, fallback):
    try:
        return float(raw)
    except (TypeError, ValueError):
        return float(fallback)


def _parse_tool_section(name):
    text = name.strip()
    if text[:1] in "Tt":
        text = text[1:]
    if not text.isdigit():
        return None
    return int(text)


def _parse_preset_section(name):
    text = name.strip()
    if text[:len(PRESET_PREFIX)].upper() != PRESET_PREFIX:
        return None
    text = text[len(PRESET_PREFIX):].strip()
    return text or None


def _recipe(base, values):
    return CoolantRecipe(
        freq=_num(values.get("FREQ"), base.freq) if "FREQ" in values else base.freq,
        duty=_num(values.get("DUTY"), base.duty) if "DUTY" in values else base.duty,
        pressure=(_num(values.get("PRESSURE"), base.pressure)
                  if "PRESSURE" in values else base.pressure),
    )


def load_library(path) -> CoolantLibrary:
    """Read the whole file: [DEFAULT], every [PRESET <name>], every [T<n>]."""
    # default_section is renamed so [DEFAULT] does NOT leak its keys into every
    # section: we need to know which keys a tool/preset really wrote.
    parser = ConfigParser(interpolation=None, default_section="\x00none")
    parser.optionxform = str.upper
    read = parser.read(path)
    if not read:
        raise FileNotFoundError("coolant profile file not found: %s" % path)

    dflt = {}
    for name in parser.sections():
        if name.strip().upper() == "DEFAULT":
            dflt = dict(parser[name])
    zero = CoolantRecipe(0.0, 0.0, 0.0)
    default = _recipe(zero, dflt)

    lib = CoolantLibrary(default=default)
    for name in parser.sections():
        pname = _parse_preset_section(name)
        if pname is not None:
            lib.presets[pname] = _recipe(default, dict(parser[name]))

    for name in parser.sections():
        tool = _parse_tool_section(name)
        if tool is None:
            continue
        sec = dict(parser[name])
        preset = (sec.get("PRESET") or "").strip() or None
        overrides = {k: _num(v, 0) for k, v in sec.items() if k in RECIPE_KEYS}
        base, missing = default, False
        if preset is not None:
            stored = lib.preset_named(preset)
            if stored is None:
                missing = True
            else:
                base = lib.presets[stored]
        lib.tools[tool] = ToolEntry(
            tool=tool, preset=preset, overrides=overrides,
            recipe=_recipe(base, sec), missing_preset=missing,
        )
    return lib


def load_profiles(path):
    """Return (default_recipe, {tool_number: resolved recipe}). Kept for M202."""
    lib = load_library(path)
    return lib.default, {t: e.recipe for t, e in lib.tools.items()}


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


# ---------------------------------------------------------------- writing
# Line-based so the user's comments and ordering survive every edit.

_SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*$")
_KEY_RE = re.compile(r"^\s*([A-Za-z_]+)\s*[=:]")


def _fmt(value):
    return "%g" % float(value)


def _read_lines(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read().splitlines()


def _write_lines(path, lines):
    while lines and not lines[-1].strip():
        lines.pop()
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def _find_section(lines, match_fn) -> Tuple[Optional[int], int]:
    """(header index, end index exclusive) of the first section match_fn accepts."""
    start, end = None, len(lines)
    for idx, line in enumerate(lines):
        m = _SECTION_RE.match(line)
        if not m:
            continue
        if start is not None:
            end = idx
            break
        if match_fn(m.group(1)):
            start = idx
    return start, end


def _edit_section(lines, match_fn, header, set_values=None, remove_keys=()):
    """Set/remove keys in a section (created at the end if missing)."""
    pending = {k.upper(): v for k, v in (set_values or {}).items()}
    remove = {k.upper() for k in remove_keys}
    start, end = _find_section(lines, match_fn)
    if start is None:
        while lines and not lines[-1].strip():
            lines.pop()
        lines.append("")
        lines.append("[%s]" % header)
        lines.extend("%s = %s" % (k, v) for k, v in pending.items())
        return lines
    out = lines[:start + 1]
    for line in lines[start + 1:end]:
        m = _KEY_RE.match(line)
        key = m.group(1).upper() if m else None
        if key in remove and key not in pending:
            continue
        if key in pending:
            out.append("%s = %s" % (key, pending.pop(key)))
            continue
        out.append(line)
    # keys not already present go right after the header
    for offset, (k, v) in enumerate(pending.items(), start=1):
        out.insert(start + offset, "%s = %s" % (k, v))
    return out + lines[end:]


def _drop_section(lines, match_fn):
    start, end = _find_section(lines, match_fn)
    if start is None:
        return lines, False
    # The section's range already ends with its trailing blank line, so
    # cutting [start, end) leaves exactly one blank between its neighbours.
    out = lines[:start] + lines[end:]
    if 0 < start < len(out) and not out[start - 1].strip() and not out[start].strip():
        del out[start]
    return out, True


def _tool_match(tool):
    return lambda name: _parse_tool_section(name) == tool


def _preset_match(pname):
    want = pname.strip().lower()
    return lambda name: (_parse_preset_section(name) or "").lower() == want


def _check_tool(tool_number):
    tool = int(tool_number)
    if tool <= 0:
        raise ValueError("tool number must be > 0 (T0 is always dry)")
    return tool


def check_preset_name(name):
    text = (name or "").strip()
    if not text:
        raise ValueError("preset name is empty")
    if any(c in text for c in "[]\n\r=:#;"):
        raise ValueError("preset name can't contain [ ] = : # ; or line breaks")
    return text


def save_tool_recipe(path, tool_number, values):
    """Set keys (e.g. {"FREQ": 10, "DUTY": 1.5}) in [T<n>], keeping comments.

    Older per-tool numbers. Existing keys are rewritten in place; missing keys
    go right after the section header; a missing section is appended.
    """
    tool = _check_tool(tool_number)
    lines = _edit_section(_read_lines(path), _tool_match(tool), "T%d" % tool,
                          {k: _fmt(v) for k, v in values.items()})
    _write_lines(path, lines)


def save_preset(path, name, values):
    """Create or update [PRESET <name>] (case-insensitive match), keeping comments.

    Returns the tools that use it, so the caller can say what changed.
    """
    name = check_preset_name(name)
    lines = _read_lines(path)
    start, _end = _find_section(lines, _preset_match(name))
    header = PRESET_PREFIX + name
    if start is not None:
        header = _SECTION_RE.match(lines[start]).group(1).strip()
    lines = _edit_section(lines, _preset_match(name), header,
                          {k: _fmt(v) for k, v in values.items()})
    _write_lines(path, lines)
    return load_library(path).tools_using(name)


def delete_preset(path, name):
    """Remove [PRESET <name>] and the PRESET line from every tool using it.

    Those tools fall back to [DEFAULT] (plus any numbers of their own).
    Returns the tools that were using it.
    """
    name = check_preset_name(name)
    users = load_library(path).tools_using(name)
    lines, found = _drop_section(_read_lines(path), _preset_match(name))
    if not found:
        raise KeyError("no preset named %r" % name)
    for tool in users:
        lines = _edit_section(lines, _tool_match(tool), "T%d" % tool,
                              remove_keys=("PRESET",))
    _write_lines(path, lines)
    return users


def assign_preset(path, tool_number, name):
    """Point [T<n>] at a preset. Its own FREQ/DUTY/PRESSURE are removed so the
    preset governs completely (edit the preset, every tool using it follows)."""
    tool = _check_tool(tool_number)
    name = check_preset_name(name)
    lib = load_library(path)
    stored = lib.preset_named(name)
    if stored is None:
        raise KeyError("no preset named %r" % name)
    lines = _edit_section(_read_lines(path), _tool_match(tool), "T%d" % tool,
                          {"PRESET": stored}, remove_keys=RECIPE_KEYS)
    _write_lines(path, lines)


def clear_tool(path, tool_number):
    """Remove [T<n>] entirely: the tool goes back to [DEFAULT]. True if it existed."""
    tool = _check_tool(tool_number)
    lines, found = _drop_section(_read_lines(path), _tool_match(tool))
    if found:
        _write_lines(path, lines)
    return found


def import_presets(path, presets):
    """Add presets (list of {"name", "freq", "duty"}) not already in the file.

    Used once to bring in the tab's old probe_basic/mql_presets.json. Returns
    the names added.
    """
    lib = load_library(path)
    added = []
    for entry in presets:
        name = check_preset_name(entry.get("name"))
        if lib.preset_named(name) is not None or name.lower() in (a.lower() for a in added):
            continue
        save_preset(path, name, {"FREQ": entry["freq"], "DUTY": entry["duty"]})
        added.append(name)
    return added
