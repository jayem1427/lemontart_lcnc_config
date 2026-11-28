"""LinuxCNC python remap: M202 applies the current tool's PWM coolant recipe.

The recipe is the tool's preset from coolant_tools.ini (tool-agnostic named
presets; see coolant_profiles.py), or [DEFAULT] if the tool has no entry.
"""

from __future__ import annotations

import os

from interpreter import INTERP_ERROR, INTERP_OK

from coolant_profiles import load_library, recipe_for_tool

try:
    from emccanon import MESSAGE
except ImportError:  # unit tests / no LinuxCNC
    def MESSAGE(msg):
        pass


def _config_dir():
    ini = os.environ.get("INI_FILE_NAME") or ""
    if ini:
        return os.path.dirname(os.path.abspath(ini))
    return os.getcwd()


def _profile_path():
    base = _config_dir()
    try:
        import linuxcnc

        ini = linuxcnc.ini(os.environ.get("INI_FILE_NAME"))
        rel = ini.find("COOLANT", "PROFILE_FILE") or "probe_basic/coolant_tools.ini"
    except Exception:
        rel = "probe_basic/coolant_tools.ini"
    if os.path.isabs(rel):
        return rel
    return os.path.join(base, rel)


def _current_tool(self):
    try:
        return int(float(self.params[5400]))
    except Exception:
        return 0


def apply_tool_coolant(self, **words):
    """Load coolant_tools.ini for #5400 and poke M68 E4/E5/E6. Does not M8."""
    path = _profile_path()
    try:
        lib = load_library(path)
    except Exception as exc:
        self.set_errormsg("M202: cannot read %s (%s)" % (path, exc))
        return INTERP_ERROR

    tool = _current_tool(self)
    recipe = recipe_for_tool(lib.default, {t: e.recipe for t, e in lib.tools.items()}, tool)
    entry = lib.tools.get(tool)
    if entry is not None and entry.missing_preset:
        # A failure worth showing: the tool points at a preset that was deleted
        # or misspelled, so it is running on [DEFAULT] instead.
        MESSAGE("M202: T%d preset '%s' not found in %s - using [DEFAULT] %g Hz / %g %%"
                % (tool, entry.preset, os.path.basename(path), recipe.freq, recipe.duty))
    try:
        self.execute("M68 E4 Q%.4f" % recipe.freq)
        self.execute("M68 E5 Q%.4f" % recipe.duty)
        self.execute("M68 E6 Q%.4f" % recipe.pressure)
    except Exception as exc:
        self.set_errormsg("M202: M68 failed (%s)" % exc)
        return INTERP_ERROR

    # Silent on success (Jon 2026-11-24: no popup on every tool load).
    # REVERT: uncomment to show the recipe again.
    # MESSAGE(
    #     "coolant T%d: %.0f Hz, %.1f %% duty, %.1f psi"
    #     % (tool, recipe.freq, recipe.duty, recipe.pressure)
    # )
    return INTERP_OK
