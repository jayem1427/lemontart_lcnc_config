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

from coolant_profiles import load_profiles, recipe_for_tool, save_tool_recipe  # noqa: E402

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
        self.assertEqual(tools[9].freq, default.freq)
        self.assertEqual(tools[9].pressure, default.pressure)
        self.assertEqual(tools[9].duty, 1)

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


if __name__ == "__main__":
    unittest.main()
