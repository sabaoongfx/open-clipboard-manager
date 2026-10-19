import sys
import unittest
from unittest import mock

import base  # noqa: F401  (sets up sys.path)
from platform_base import PlatformBase

REQUIRED_ATTRIBUTES = ("name", "default_hotkey", "hotkey_examples", "default_actions_file", "data_dir", "ui_font")


def import_mac_backend():
    """platform_macos needs PyObjC (Mac only), so it is imported against stand-in modules."""
    with mock.patch.dict(sys.modules, {"AppKit": mock.MagicMock(), "Foundation": mock.MagicMock()}):
        sys.modules.pop("platform_macos", None)
        import platform_macos
    return platform_macos


class BackendContract(unittest.TestCase):
    def backends(self):
        if sys.platform == "win32":
            import platform_windows
            yield "windows", platform_windows.Platform
        import platform_linux
        yield "linux", platform_linux.Platform  # only shells out to helper programs, so it imports anywhere
        yield "macos", import_mac_backend().Platform

    def tearDown(self):
        sys.modules.pop("platform_macos", None)

    def test_every_backend_implements_the_whole_interface(self):
        for name, backend in self.backends():
            with self.subTest(backend=name):
                self.assertTrue(issubclass(backend, PlatformBase))
                self.assertEqual(backend.__abstractmethods__, frozenset())
                backend()  # abstract classes with missing methods raise TypeError here

    def test_every_backend_sets_the_descriptive_attributes(self):
        for name, backend in self.backends():
            platform = backend()  # some attributes (Linux's hotkey help) depend on the session
            for attribute in REQUIRED_ATTRIBUTES:
                with self.subTest(backend=name, attribute=attribute):
                    self.assertTrue(getattr(platform, attribute))

    def test_every_backend_ships_a_default_hotkey_it_can_parse(self):
        for name, backend in self.backends():
            with self.subTest(backend=name):
                backend().validate_hotkey(backend.default_hotkey)

    def test_windows_and_linux_default_to_win_v_and_macos_to_ctrl_cmd_v(self):
        defaults = {name: backend.default_hotkey for name, backend in self.backends()}
        self.assertEqual(defaults.get("windows", "win+v"), "win+v")
        self.assertEqual(defaults["linux"], "super+v")
        self.assertEqual(defaults["macos"], "ctrl+cmd+v")

    def test_a_backend_missing_a_method_cannot_be_created(self):
        class Incomplete(PlatformBase):
            def is_dark_mode(self):
                return False

        with self.assertRaises(TypeError):
            Incomplete()

    def test_the_entry_script_that_start_at_login_launches_exists(self):
        import os
        from platform_base import ENTRY_SCRIPT
        self.assertTrue(os.path.isfile(ENTRY_SCRIPT))


if __name__ == "__main__":
    unittest.main()
