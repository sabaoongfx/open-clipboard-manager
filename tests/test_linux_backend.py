"""The Linux backend shells out to xclip / wl-clipboard / xdotool, so these tests replace those calls."""
import io
import os
import tempfile
import unittest
from unittest import mock

from PIL import Image

import base  # noqa: F401  (sets up sys.path)
import platform_linux as pl


def make_platform(wayland=False, backend="xclip"):
    with mock.patch.object(pl, "is_wayland", return_value=wayland), \
            mock.patch.object(pl.Platform, "_detect_backend", return_value=backend):
        return pl.Platform()


def png_bytes(colour="red"):
    buf = io.BytesIO()
    Image.new("RGB", (4, 3), colour).save(buf, "PNG")
    return buf.getvalue()


class FakeClipboard:
    """Stands in for the helper programs: holds targets and per-target data, answers _run() calls."""

    def __init__(self, **data):
        self.data = data  # e.g. {"UTF8_STRING": b"hi"}

    def run(self, args, data=None, timeout=3):
        if "TARGETS" in args or "--list-types" in args:
            return "\n".join(self.data).encode() if self.data else None
        mime = args[args.index("-t") + 1] if "-t" in args else args[args.index("--type") + 1]
        return self.data.get(mime)


class Reading(unittest.TestCase):
    def platform_with(self, **data):
        platform = make_platform()
        platform._run = FakeClipboard(**data).run
        return platform

    def test_text_is_read_and_decoded(self):
        platform = self.platform_with(UTF8_STRING="héllo".encode())
        platform.clipboard_token()
        self.assertEqual(platform.get_text(), "héllo")

    def test_the_token_changes_when_the_text_changes_and_not_otherwise(self):
        platform = self.platform_with(UTF8_STRING=b"one")
        first = platform.clipboard_token()
        self.assertEqual(platform.clipboard_token(), first)
        platform._run = FakeClipboard(UTF8_STRING=b"two").run
        self.assertNotEqual(platform.clipboard_token(), first)

    def test_an_image_is_read_when_there_is_no_text(self):
        platform = self.platform_with(**{"image/png": png_bytes()})
        platform.clipboard_token()
        self.assertIsNone(platform.get_text())
        self.assertEqual(platform.get_image().size, (4, 3))

    def test_copying_a_different_image_changes_the_token_even_though_the_formats_match(self):
        platform = self.platform_with(**{"image/png": png_bytes("red")})
        first = platform.clipboard_token()
        platform._run = FakeClipboard(**{"image/png": png_bytes("blue")}).run
        self.assertNotEqual(platform.clipboard_token(), first)

    def test_text_wins_over_an_image(self):
        platform = self.platform_with(UTF8_STRING=b"cell", **{"image/png": png_bytes()})
        platform.clipboard_token()
        self.assertEqual(platform.get_text(), "cell")
        self.assertIsNone(platform.get_image())

    def test_an_empty_or_unreadable_clipboard_gives_nothing(self):
        platform = make_platform()
        platform._run = lambda *a, **k: None
        platform.clipboard_token()
        self.assertIsNone(platform.get_text())
        self.assertIsNone(platform.get_image())

    def test_corrupt_image_data_is_ignored(self):
        platform = self.platform_with(**{"image/png": b"not a png"})
        platform.clipboard_token()
        self.assertIsNone(platform.get_image())

    def test_the_wayland_tools_are_used_on_wayland(self):
        platform = make_platform(wayland=True, backend="wl")
        calls = []
        platform._run = lambda args, **k: calls.append(args) or b"text/plain"
        platform._targets()
        self.assertEqual(calls[0][0], "wl-paste")


class Writing(unittest.TestCase):
    def test_text_is_sent_to_xclip_as_utf8(self):
        platform = make_platform()
        with mock.patch.object(pl.Platform, "_spawn_owner", return_value=True) as spawn:
            self.assertTrue(platform.set_text("héllo"))
        args, data = spawn.call_args[0]
        self.assertEqual(args[0], "xclip")
        self.assertIn("UTF8_STRING", args)
        self.assertEqual(data, "héllo".encode())

    def test_text_is_sent_to_wl_copy_on_wayland(self):
        platform = make_platform(wayland=True, backend="wl")
        with mock.patch.object(pl.Platform, "_spawn_owner", return_value=True) as spawn:
            platform.set_text("x")
        self.assertEqual(spawn.call_args[0][0][0], "wl-copy")

    def test_an_image_is_sent_as_png(self):
        platform = make_platform()
        with mock.patch.object(pl.Platform, "_spawn_owner", return_value=True) as spawn:
            platform.set_image(Image.new("RGB", (2, 2)))
        args, data = spawn.call_args[0]
        self.assertIn("image/png", args)
        self.assertTrue(data.startswith(b"\x89PNG"))

    def test_without_a_clipboard_tool_writing_fails_cleanly(self):
        platform = make_platform(backend=None)
        self.assertFalse(platform.set_text("x"))
        self.assertFalse(platform.set_image(Image.new("RGB", (1, 1))))

    def test_writing_invalidates_the_cached_read(self):
        platform = make_platform()
        platform._snapshot = ("stale", None, 1)
        with mock.patch.object(pl.Platform, "_spawn_owner", return_value=True):
            platform.set_text("new")
        self.assertIsNone(platform._snapshot)


class Pasting(unittest.TestCase):
    def test_x11_pastes_with_xdotool(self):
        platform = make_platform()
        with mock.patch.object(pl.shutil, "which", return_value="/usr/bin/xdotool"), \
                mock.patch.object(pl.Platform, "_run") as run:
            platform.send_paste()
        run.assert_called_once_with(["xdotool", "key", "--clearmodifiers", "ctrl+v"])

    def test_wayland_prefers_wtype_then_ydotool_then_does_nothing(self):
        platform = make_platform(wayland=True, backend="wl")
        with mock.patch.object(pl.shutil, "which", side_effect=lambda n: n if n == "wtype" else None), \
                mock.patch.object(pl.Platform, "_run") as run:
            platform.send_paste()
        self.assertEqual(run.call_args[0][0][0], "wtype")
        with mock.patch.object(pl.shutil, "which", side_effect=lambda n: n if n == "ydotool" else None), \
                mock.patch.object(pl.Platform, "_run") as run:
            platform.send_paste()
        self.assertEqual(run.call_args[0][0][0], "ydotool")
        with mock.patch.object(pl.shutil, "which", return_value=None), \
                mock.patch.object(pl.Platform, "_run") as run:
            platform.send_paste()
        run.assert_not_called()

    def test_the_previous_window_is_remembered_with_xdotool_on_x11_only(self):
        with mock.patch.object(pl.shutil, "which", return_value="/usr/bin/xdotool"), \
                mock.patch.object(pl.Platform, "_run", return_value=b"1234\n"):
            self.assertEqual(make_platform().remember_foreground(), "1234")
            self.assertIsNone(make_platform(wayland=True, backend="wl").remember_foreground())

    def test_focusing_a_window_activates_it(self):
        platform = make_platform()
        with mock.patch.object(pl.Platform, "_run") as run:
            platform.focus("1234")
            platform.focus(None)
        run.assert_called_once_with(["xdotool", "windowactivate", "--sync", "1234"])


class Hotkeys(unittest.TestCase):
    def test_super_v_is_the_default_and_parses(self):
        platform = make_platform()
        self.assertEqual(platform.default_hotkey, "super+v")
        self.assertEqual(pl._parse_hotkey("super+v"), (pl.SUPER_MASK, "v"))
        self.assertEqual(pl._parse_hotkey("win+v"), pl._parse_hotkey("super+v"))

    def test_modifiers_keys_and_function_keys(self):
        self.assertEqual(pl._parse_hotkey("Ctrl + Alt + H"), (pl.CONTROL_MASK | pl.ALT_MASK, "h"))
        self.assertEqual(pl._parse_hotkey("shift+f5"), (pl.SHIFT_MASK, "F5"))
        self.assertEqual(pl._parse_hotkey("ctrl+7"), (pl.CONTROL_MASK, "7"))

    def test_invalid_hotkeys_are_rejected(self):
        for spec in ("", "v", "ctrl+alt", "ctrl+nope", "ctrl+f13", "ctrl+vv"):
            with self.subTest(spec=spec), self.assertRaises(ValueError):
                make_platform().validate_hotkey(spec)

    def test_wayland_has_no_global_hotkey_and_says_what_to_do_instead(self):
        platform = make_platform(wayland=True, backend="wl")
        self.assertIn("--show", platform.hotkey_examples)
        with mock.patch.object(pl, "_X11Hotkey") as x11:
            platform.start_hotkey("super+v", lambda: None, lambda m: None)
        x11.assert_not_called()

    def test_a_bad_hotkey_is_rejected_before_anything_is_grabbed(self):
        with mock.patch.object(pl, "_X11Hotkey") as x11, self.assertRaises(ValueError):
            make_platform().start_hotkey("nope", lambda: None, lambda m: None)
        x11.assert_not_called()

    def test_x11_grabs_the_key_through_the_helper(self):
        with mock.patch.object(pl, "_X11Hotkey") as x11:
            platform = make_platform()
            platform.start_hotkey("super+v", lambda: None, lambda m: None)
        x11.assert_called_once()
        x11.return_value.start.assert_called_once()

    def test_changing_the_hotkey_falls_back_to_the_old_one_if_the_new_one_is_taken(self):
        made = []

        def fake(spec, on_trigger, on_error):
            helper = mock.Mock(spec=["start", "stop", "spec"])
            helper.spec = spec
            helper.start.return_value = spec != "ctrl+alt+x"  # that one is "already used"
            made.append(helper)
            return helper

        platform = make_platform()
        with mock.patch.object(pl, "_X11Hotkey", side_effect=fake):
            platform.start_hotkey("super+v", lambda: None, lambda m: None)
            platform.change_hotkey("ctrl+alt+x")
        self.assertEqual([h.spec for h in made], ["super+v", "ctrl+alt+x", "super+v"])
        made[0].stop.assert_called_once()
        self.assertEqual(platform._hotkey.spec, "super+v")


class Environment(unittest.TestCase):
    def test_wayland_detection(self):
        self.assertTrue(pl.is_wayland({"XDG_SESSION_TYPE": "wayland"}))
        self.assertTrue(pl.is_wayland({"WAYLAND_DISPLAY": "wayland-0"}))
        self.assertFalse(pl.is_wayland({"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0"}))
        self.assertFalse(pl.is_wayland({"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0"}))
        self.assertFalse(pl.is_wayland({}))

    def test_backend_detection_prefers_wl_clipboard_on_wayland_and_xclip_otherwise(self):
        with mock.patch.object(pl, "is_wayland", return_value=True), \
                mock.patch.object(pl.shutil, "which", return_value="/usr/bin/x"):
            self.assertEqual(pl.Platform()._backend, "wl")
        with mock.patch.object(pl, "is_wayland", return_value=False), \
                mock.patch.object(pl.shutil, "which", return_value="/usr/bin/x"):
            self.assertEqual(pl.Platform()._backend, "xclip")
        with mock.patch.object(pl, "is_wayland", return_value=False), \
                mock.patch.object(pl.shutil, "which", return_value=None):
            self.assertIsNone(pl.Platform()._backend)

    def test_dark_mode_follows_the_gnome_setting(self):
        platform = make_platform()
        with mock.patch.object(pl.Platform, "_run", return_value=b"'prefer-dark'\n"):
            self.assertTrue(platform.is_dark_mode())
        with mock.patch.object(pl.Platform, "_run", return_value=b"'default'\n"):
            self.assertFalse(platform.is_dark_mode())
        with mock.patch.object(pl.Platform, "_run", return_value=None):
            self.assertFalse(platform.is_dark_mode())

    def test_sanitize_strips_what_the_shell_would_interpret(self):
        self.assertEqual(make_platform().sanitize_arg('a"b$(rm)`c`\\d\ne'), "ab(rm)cde")

    def test_autostart_writes_and_removes_a_desktop_entry(self):
        path = os.path.join(tempfile.mkdtemp(), "autostart", "ocm.desktop")
        with mock.patch.object(pl, "AUTOSTART_FILE", path):
            platform = make_platform()
            self.assertFalse(platform.autostart_enabled())
            platform.set_autostart(True)
            self.assertTrue(platform.autostart_enabled())
            with open(path, encoding="utf-8") as f:
                text = f.read()
            self.assertIn("Exec=", text)
            self.assertIn("winclipman.py", text)
            platform.set_autostart(False)
            self.assertFalse(platform.autostart_enabled())
            platform.set_autostart(False)  # removing twice is fine

    def test_helper_programs_that_are_missing_do_not_crash(self):
        self.assertIsNone(pl.Platform._run(["definitely-not-a-real-program-xyz"]))


if __name__ == "__main__":
    unittest.main()
