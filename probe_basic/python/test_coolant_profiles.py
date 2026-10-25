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

from coolant_profiles import load_profiles, recipe_for_tool  # noqa: E402

SHIPPED = os.path.join(HERE, "..", "coolant_tools.ini")


class CoolantProfileTests(unittest.TestCase):
    def test_shipped_ini_parses(self):
        default, tools = load_profiles(SHIPPED)
        self.assertEqual(default.freq, 20000)
        self.assertEqual(default.duty, 30)
        self.assertIn(3, tools)
        self.assertEqual(tools[3].duty, 35)
        self.assertEqual(tools[99].freq, 0)
        self.assertEqual(tools[99].duty, 0)

    def test_inherit_unspecified_keys(self):
        default, tools = load_profiles(SHIPPED)
        self.assertEqual(tools[9].freq, default.freq)
        self.assertEqual(tools[9].pressure, default.pressure)
        self.assertEqual(tools[9].duty, 25)

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


if __name__ == "__main__":
    unittest.main()
