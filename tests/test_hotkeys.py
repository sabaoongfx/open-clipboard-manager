import sys
import unittest
from unittest import mock

import base  # noqa: F401  (sets up sys.path)


class WindowsHotkeys(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sys.platform != "win32":
            raise unittest.SkipTest("Windows only")
        import platform_windows
        cls.m = platform_windows

    def test_modifiers_and_letter(self):
        m = self.m
        self.assertEqual(m._parse_hotkey("ctrl+alt+h"), (m.MOD_CONTROL | m.MOD_ALT | m.MOD_NOREPEAT, ord("H")))

    def test_case_and_spaces_are_ignored(self):
        m = self.m
        self.assertEqual(m._parse_hotkey(" Ctrl + SHIFT + v "), (m.MOD_CONTROL | m.MOD_SHIFT | m.MOD_NOREPEAT, ord("V")))

    def test_digits_and_function_keys(self):
        m = self.m
        self.assertEqual(m._parse_hotkey("alt+5")[1], ord("5"))
        self.assertEqual(m._parse_hotkey("alt+f1")[1], 0x70)
        self.assertEqual(m._parse_hotkey("alt+f24")[1], 0x70 + 23)

    def test_win_key_is_a_modifier(self):
        m = self.m
        self.assertTrue(m._parse_hotkey("win+v")[0] & m.MOD_WIN)

    def test_invalid_hotkeys_are_rejected(self):
        for spec in ("", "h", "ctrl+alt", "ctrl+", "ctrl+alt+nope", "alt+f25", "alt+f0", "ctrl+hh"):
            with self.subTest(spec=spec), self.assertRaises(ValueError):
                self.m._parse_hotkey(spec)

    def test_a_later_key_replaces_an_earlier_one(self):
        self.assertEqual(self.m._parse_hotkey("ctrl+a+b")[1], ord("B"))

    def test_sanitize_strips_quotes_and_line_breaks(self):
        self.assertEqual(self.m.Platform().sanitize_arg('a"b\r\nc'), "abc")


class MacHotkeys(unittest.TestCase):
    """platform_macos needs PyObjC, which only exists on a Mac, so it is imported against stand-in modules."""

    @classmethod
    def setUpClass(cls):
        fakes = {"AppKit": mock.MagicMock(), "Foundation": mock.MagicMock()}
        with mock.patch.dict(sys.modules, fakes):
            sys.modules.pop("platform_macos", None)
            import platform_macos
        cls.m = platform_macos

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop("platform_macos", None)

    def test_modifiers_and_letter(self):
        m = self.m
        self.assertEqual(m._parse_hotkey("cmd+shift+v"), (m.MOD_CMD | m.MOD_SHIFT, m.KEY_CODES["v"]))

    def test_modifier_aliases(self):
        m = self.m
        self.assertEqual(m._parse_hotkey("option+h"), m._parse_hotkey("alt+h"))
        self.assertEqual(m._parse_hotkey("control+h"), m._parse_hotkey("ctrl+h"))
        self.assertEqual(m._parse_hotkey("win+h"), m._parse_hotkey("command+h"))

    def test_function_keys(self):
        m = self.m
        self.assertEqual(m._parse_hotkey("ctrl+f5")[1], 96)
        self.assertEqual(m._parse_hotkey("ctrl+f12")[1], 111)

    def test_invalid_hotkeys_are_rejected(self):
        for spec in ("", "v", "cmd+shift", "cmd+nope", "cmd+f13", "cmd+vv"):
            with self.subTest(spec=spec), self.assertRaises(ValueError):
                self.m._parse_hotkey(spec)

    def test_sanitize_strips_everything_the_shell_would_interpret_inside_double_quotes(self):
        self.assertEqual(self.m.Platform().sanitize_arg('a"b$(rm)`c`\\d\ne'), "ab(rm)cde")

    def test_key_code_table_has_no_duplicates(self):
        codes = list(self.m.KEY_CODES.values())
        self.assertEqual(len(codes), len(set(codes)))


if __name__ == "__main__":
    unittest.main()
