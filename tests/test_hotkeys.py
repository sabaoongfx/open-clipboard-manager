import ctypes
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

    def test_win_v_is_the_default_hotkey(self):
        m = self.m
        self.assertEqual(m.Platform.default_hotkey, "win+v")
        self.assertEqual(m._parse_hotkey("win+v"), (m.MOD_WIN | m.MOD_NOREPEAT, ord("V")))

    def make_hooked(self, spec="win+v"):
        """A Platform set up as if the hook for `spec` were installed, with the keyboard faked."""
        m = self.m
        platform = m.Platform()
        platform._hook_target = (m._parse_hotkey(spec)[0] & ~m.MOD_NOREPEAT, m._parse_hotkey(spec)[1])
        platform._swallowed = False
        platform.triggered = []
        platform._on_trigger = lambda: platform.triggered.append(1)
        return platform

    def feed(self, platform, vk, down, held=(), injected_mark=0):
        """Run the hook callback for one key event; returns what it answered and the injected keys."""
        m = self.m
        info = m.KBDLLHOOKSTRUCT(vk, 0, 0, 0, injected_mark)
        injected = []
        with mock.patch.object(m.user32, "GetAsyncKeyState",
                               side_effect=lambda k: 0x8000 if k in held else 0), \
                mock.patch.object(m.user32, "keybd_event", side_effect=lambda *a: injected.append(a)), \
                mock.patch.object(m.user32, "CallNextHookEx", return_value=0) as next_hook:
            result = platform._on_key(m.HC_ACTION, m.WM_KEYDOWN if down else 0x0101, ctypes.addressof(info))
        return result, injected, next_hook.called

    def test_win_v_is_swallowed_and_triggers_the_app(self):
        m = self.m
        platform = self.make_hooked()
        result, injected, passed_on = self.feed(platform, 0x56, True, held=(m.VK_LWIN,))
        self.assertEqual(result, 1)
        self.assertFalse(passed_on)
        self.assertEqual(platform.triggered, [1])
        # a harmless key tap is injected so releasing Win does not open the Start menu
        self.assertEqual([a[0] for a in injected], [m.VK_UNASSIGNED, m.VK_UNASSIGNED])
        self.assertTrue(all(a[3] == m.INJECT_MARK for a in injected))

    def test_the_key_release_is_swallowed_too_and_only_once(self):
        m = self.m
        platform = self.make_hooked()
        self.feed(platform, 0x56, True, held=(m.VK_LWIN,))
        self.assertEqual(self.feed(platform, 0x56, False, held=(m.VK_LWIN,))[0], 1)
        self.assertFalse(platform._swallowed)
        self.assertFalse(self.feed(platform, 0x56, False)[0] == 1, "a later release is not ours")

    def test_holding_the_key_does_not_trigger_again(self):
        m = self.m
        platform = self.make_hooked()
        for _ in range(4):
            self.assertEqual(self.feed(platform, 0x56, True, held=(m.VK_LWIN,))[0], 1)
        self.assertEqual(platform.triggered, [1])

    def test_either_windows_key_works(self):
        m = self.m
        platform = self.make_hooked()
        self.feed(platform, 0x56, True, held=(m.VK_RWIN,))
        self.assertEqual(platform.triggered, [1])

    def test_plain_v_and_other_modifier_combinations_pass_through(self):
        m = self.m
        for held in ((), (m.VK_CONTROL,), (m.VK_LWIN, m.VK_SHIFT), (m.VK_LWIN, m.VK_CONTROL)):
            platform = self.make_hooked()
            with self.subTest(held=held):
                result, injected, passed_on = self.feed(platform, 0x56, True, held=held)
                self.assertTrue(passed_on)
                self.assertNotEqual(result, 1)
                self.assertEqual(platform.triggered, [])
                self.assertEqual(injected, [])

    def test_other_keys_pass_through(self):
        m = self.m
        platform = self.make_hooked()
        result, _, passed_on = self.feed(platform, 0x41, True, held=(m.VK_LWIN,))
        self.assertTrue(passed_on)
        self.assertEqual(platform.triggered, [])

    def test_keys_we_injected_ourselves_are_ignored(self):
        m = self.m
        platform = self.make_hooked()
        _, _, passed_on = self.feed(platform, 0x56, True, held=(m.VK_LWIN,), injected_mark=m.INJECT_MARK)
        self.assertTrue(passed_on)
        self.assertEqual(platform.triggered, [])

    def test_a_combination_with_extra_modifiers_needs_exactly_those_modifiers(self):
        m = self.m
        platform = self.make_hooked("win+shift+v")
        self.feed(platform, 0x56, True, held=(m.VK_LWIN,))
        self.assertEqual(platform.triggered, [])
        self.feed(platform, 0x56, True, held=(m.VK_LWIN, m.VK_SHIFT))
        self.assertEqual(platform.triggered, [1])

    def test_without_an_installed_hook_everything_passes_through(self):
        m = self.m
        platform = self.make_hooked()
        platform._hook_target = None
        self.assertTrue(self.feed(platform, 0x56, True, held=(m.VK_LWIN,))[2])

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

    def test_the_default_keeps_cmd_v_free_for_pasting(self):
        platform = self.m.Platform()
        platform.validate_hotkey(platform.default_hotkey)
        self.assertEqual(platform.default_hotkey, "ctrl+cmd+v")

    def test_plain_cmd_v_is_refused_because_it_is_the_system_paste_shortcut(self):
        for spec in ("cmd+v", "command+v", "win+v"):
            with self.subTest(spec=spec), self.assertRaisesRegex(ValueError, "Paste"):
                self.m.Platform().validate_hotkey(spec)
        self.m.Platform().validate_hotkey("cmd+shift+v")

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
