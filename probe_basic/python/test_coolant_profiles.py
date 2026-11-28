#!/usr/bin/env python3
"""Tests for coolant_tools.ini lookup (no LinuxCNC required).

    python3 probe_basic/python/test_coolant_profiles.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

HERE = os.path.abspath(os.path.dirname(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from coolant_profiles import (  # noqa: E402
    assign_preset,
    clear_tool,
    delete_preset,
    import_presets,
    load_library,
    load_profiles,
    recipe_for_tool,
    save_preset,
    save_tool_recipe,
)

SHIPPED = os.path.join(HERE, "..", "coolant_tools.ini")


class CoolantProfileTests(unittest.TestCase):
    def test_shipped_ini_parses(self):
        default, tools = load_profiles(SHIPPED)
        self.assertEqual(default.freq, 10)
        self.assertEqual(default.duty, 1)
        self.assertIn(3, tools)
        self.assertEqual(tools[3].duty, 2)
        self.assertEqual(tools[99].freq, 0)
        self.assertEqual(tools[99].duty, 0)

    def test_inherit_unspecified_keys(self):
        default, tools = load_profiles(SHIPPED)
        self.assertEqual(tools[3].freq, default.freq)          # Heavy leaves PRESSURE out
        self.assertEqual(tools[3].pressure, default.pressure)
        self.assertEqual(recipe_for_tool(default, tools, 9), default)  # no entry

    def test_unknown_tool_uses_default(self):
        default, tools = load_profiles(SHIPPED)
        rec = recipe_for_tool(default, tools, 1234)
        self.assertEqual(rec, default)

    def test_empty_spindle_is_dry(self):
        default, tools = load_profiles(SHIPPED)
        rec = recipe_for_tool(default, tools, 0)
        self.assertEqual(rec.freq, 0)
        self.assertEqual(rec.duty, 0)
        self.assertEqual(rec.pressure, 0)

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_profiles("/no/such/coolant_tools.ini")

    def test_partial_override_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".ini", delete=False) as fh:
            fh.write("[DEFAULT]\nFREQ=1000\nDUTY=10\nPRESSURE=5\n\n[T7]\nDUTY=40\n")
            path = fh.name
        try:
            default, tools = load_profiles(path)
            rec = recipe_for_tool(default, tools, 7)
            self.assertEqual(rec.freq, 1000)
            self.assertEqual(rec.duty, 40)
            self.assertEqual(rec.pressure, 5)
        finally:
            os.unlink(path)

    def _tmp_ini(self, text):
        fh = tempfile.NamedTemporaryFile("w", suffix=".ini", delete=False)
        fh.write(text)
        fh.close()
        self.addCleanup(os.unlink, fh.name)
        return fh.name

    def test_save_updates_existing_section_keeps_comments(self):
        path = self._tmp_ini(
            "# header note\n[DEFAULT]\nFREQ = 10\nDUTY = 1\n\n"
            "[T3]\n# flood-ish\nDUTY = 2\n\n[T9]\nDUTY = 1\n"
        )
        save_tool_recipe(path, 3, {"FREQ": 20, "DUTY": 2.5})
        with open(path) as fh:
            text = fh.read()
        self.assertIn("# header note", text)
        self.assertIn("# flood-ish", text)
        default, tools = load_profiles(path)
        self.assertEqual(tools[3].freq, 20)
        self.assertEqual(tools[3].duty, 2.5)
        self.assertEqual(tools[9].duty, 1)
        self.assertEqual(tools[9].freq, 10)

    def test_save_appends_new_section(self):
        path = self._tmp_ini("[DEFAULT]\nFREQ = 10\nDUTY = 1\n\n[T3]\nDUTY = 2\n")
        save_tool_recipe(path, 42, {"FREQ": 15, "DUTY": 0.5})
        default, tools = load_profiles(path)
        self.assertEqual(tools[42].freq, 15)
        self.assertEqual(tools[42].duty, 0.5)
        self.assertEqual(tools[3].duty, 2)

    def test_save_rejects_empty_spindle(self):
        path = self._tmp_ini("[DEFAULT]\nFREQ = 10\n")
        with self.assertRaises(ValueError):
            save_tool_recipe(path, 0, {"FREQ": 1})


class PresetTests(unittest.TestCase):
    """Tool-agnostic presets: [PRESET <name>] + [T<n>] PRESET = <name>."""

    BASE = (
        "# keep me\n[DEFAULT]\nFREQ = 10\nDUTY = 1\nPRESSURE = 0\n\n"
        "[PRESET Heavy]\nFREQ = 10\nDUTY = 2\n\n"
        "[PRESET Light pulse]\nFREQ = 1\nDUTY = 0.3\n\n"
        "[T3]\n# roughing\nPRESET = Heavy\n\n[T12]\nPRESET = Heavy\n\n"
        "[T7]\nDUTY = 3\n"
    )

    def _tmp(self, text=None):
        fh = tempfile.NamedTemporaryFile("w", suffix=".ini", delete=False)
        fh.write(self.BASE if text is None else text)
        fh.close()
        self.addCleanup(os.unlink, fh.name)
        return fh.name

    def test_shipped_presets(self):
        lib = load_library(SHIPPED)
        self.assertIn("Heavy", lib.presets)
        self.assertEqual(lib.tools[3].preset, "Heavy")
        self.assertEqual(lib.tools[1].recipe.freq, 1)
        self.assertEqual(lib.tools[1].recipe.duty, 0.3)
        self.assertEqual(lib.tools[99].recipe, recipe_for_tool(lib.default, {}, 0))
        self.assertFalse(any(e.missing_preset for e in lib.tools.values()))

    def test_tool_resolves_through_preset(self):
        default, tools = load_profiles(self._tmp())
        self.assertEqual(tools[3].duty, 2)
        self.assertEqual(tools[3].pressure, 0)     # preset left it out -> DEFAULT
        self.assertEqual(tools[7].duty, 3)         # old-style numbers still work
        self.assertEqual(tools[7].freq, 10)

    def test_tool_override_beats_preset(self):
        path = self._tmp(self.BASE + "\n[T20]\nPRESET = Heavy\nDUTY = 5\n")
        lib = load_library(path)
        self.assertEqual(lib.tools[20].recipe.freq, 10)
        self.assertEqual(lib.tools[20].recipe.duty, 5)
        self.assertEqual(lib.tools[20].overrides, {"DUTY": 5.0})

    def test_any_preset_on_any_tool(self):
        path = self._tmp()
        for tool in (3, 7, 55):
            assign_preset(path, tool, "light PULSE")   # case-insensitive
        lib = load_library(path)
        for tool in (3, 7, 55):
            self.assertEqual(lib.tools[tool].preset, "Light pulse")
            self.assertEqual(lib.tools[tool].recipe.duty, 0.3)
            self.assertEqual(lib.tools[tool].overrides, {})  # own numbers removed
        with open(path) as fh:
            self.assertIn("# roughing", fh.read())

    def test_editing_a_preset_moves_every_tool_using_it(self):
        path = self._tmp()
        users = save_preset(path, "heavy", {"FREQ": 20, "DUTY": 4})
        self.assertEqual(users, [3, 12])
        lib = load_library(path)
        self.assertEqual(list(lib.presets).count("Heavy"), 1)  # updated, not duplicated
        for tool in (3, 12):
            self.assertEqual(lib.tools[tool].recipe.freq, 20)
            self.assertEqual(lib.tools[tool].recipe.duty, 4)

    def test_new_preset_appended(self):
        path = self._tmp()
        self.assertEqual(save_preset(path, "Finish", {"FREQ": 5, "DUTY": 0.5}), [])
        lib = load_library(path)
        self.assertEqual(list(lib.presets)[-1], "Finish")
        self.assertEqual(lib.presets["Finish"].pressure, 0)

    def test_delete_preset_unassigns_tools(self):
        path = self._tmp()
        self.assertEqual(delete_preset(path, "Heavy"), [3, 12])
        lib = load_library(path)
        self.assertNotIn("Heavy", lib.presets)
        self.assertIsNone(lib.tools[3].preset)
        self.assertEqual(lib.tools[3].recipe, lib.default)
        with self.assertRaises(KeyError):
            delete_preset(path, "Heavy")

    def test_missing_preset_flagged_and_falls_back(self):
        path = self._tmp(self.BASE + "\n[T40]\nPRESET = Nope\n")
        lib = load_library(path)
        self.assertTrue(lib.tools[40].missing_preset)
        self.assertEqual(lib.tools[40].recipe, lib.default)

    def test_assign_unknown_preset_rejected(self):
        with self.assertRaises(KeyError):
            assign_preset(self._tmp(), 3, "Nope")

    def test_bad_names_and_tool_zero(self):
        path = self._tmp()
        for bad in ("", "  ", "a]b", "x=y", "c#d"):
            with self.assertRaises(ValueError):
                save_preset(path, bad, {"FREQ": 1, "DUTY": 1})
        with self.assertRaises(ValueError):
            assign_preset(path, 0, "Heavy")

    def test_removing_sections_keeps_one_blank_line_between(self):
        path = self._tmp()
        delete_preset(path, "Heavy")
        clear_tool(path, 3)
        with open(path) as fh:
            lines = fh.read().splitlines()
        for idx, line in enumerate(lines):
            if line.startswith("[") and idx > 0:
                above = lines[idx - 1]
                self.assertTrue(above == "" or above.startswith("#"),
                                "section %s glued to %r" % (line, above))
        self.assertNotIn("", [a for a, b in zip(lines, lines[1:]) if a == "" and b == ""])

    def test_clear_tool_returns_to_default(self):
        path = self._tmp()
        self.assertTrue(clear_tool(path, 12))
        self.assertFalse(clear_tool(path, 12))
        lib = load_library(path)
        self.assertNotIn(12, lib.tools)
        self.assertEqual(lib.tools[3].preset, "Heavy")

    def test_default_section_does_not_leak_into_sections(self):
        path = self._tmp("[DEFAULT]\nFREQ = 10\nDUTY = 1\nPRESET = Heavy\n\n"
                         "[PRESET Heavy]\nDUTY = 2\n\n[T5]\nDUTY = 4\n")
        lib = load_library(path)
        self.assertIsNone(lib.tools[5].preset)
        self.assertEqual(lib.tools[5].recipe.duty, 4)

    def test_import_old_tab_presets(self):
        path = self._tmp()
        added = import_presets(path, [
            {"name": "Default", "freq": 10, "duty": 1},
            {"name": "heavy", "freq": 99, "duty": 99},   # already there: skipped
        ])
        self.assertEqual(added, ["Default"])
        self.assertEqual(load_library(path).presets["Heavy"].duty, 2)


if __name__ == "__main__":
    unittest.main()
