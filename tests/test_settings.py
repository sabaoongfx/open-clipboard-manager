import unittest
from unittest import mock

from base import IsolatedDataTestCase, w


class SaveSettings(IsolatedDataTestCase):
    """App.save_settings validates, applies and persists the Settings page without needing a window."""

    def setUp(self):
        super().setUp()
        self.platform = mock.patch.object(w, "PLATFORM").start()
        self.addCleanup(mock.patch.stopall)
        self.platform.validate_hotkey.side_effect = lambda spec: (_ for _ in ()).throw(ValueError("bad")) \
            if spec == "nope" else None
        self.app = w.App.__new__(w.App)  # skip __init__, which would create a Tk window and a tray icon
        self.app.config = self.config(max_items=100)
        self.app.history = w.History(self.app.config)
        self.values = {"hotkey": "ctrl+alt+k", "max_items": "50", "preview_chars": "120", "paste_on_select": False,
                       "save_history": True, "save_images": False, "autostart": True}

    def test_valid_values_are_applied_and_written_to_the_config_file(self):
        self.assertEqual(self.app.save_settings(self.values), (True, None))
        self.assertEqual(self.app.config["max_items"], 50)
        self.assertEqual(self.app.config["preview_chars"], 120)
        self.assertFalse(self.app.config["paste_on_select"])
        self.assertEqual(w.load_json(w.CONFIG_FILE, {})["hotkey"], "ctrl+alt+k")

    def test_the_hotkey_is_normalised_and_only_changed_when_it_differs(self):
        self.app.save_settings({**self.values, "hotkey": "  Ctrl+Alt+K "})
        self.assertEqual(self.app.config["hotkey"], "ctrl+alt+k")
        self.platform.change_hotkey.assert_called_once_with("ctrl+alt+k")
        self.platform.change_hotkey.reset_mock()
        self.app.save_settings(self.values)
        self.platform.change_hotkey.assert_not_called()

    def test_startup_setting_is_passed_to_the_platform(self):
        self.app.save_settings(self.values)
        self.platform.set_autostart.assert_called_once_with(True)

    def test_an_invalid_hotkey_changes_nothing(self):
        saved, message = self.app.save_settings({**self.values, "hotkey": "nope"})
        self.assertFalse(saved)
        self.assertIn("Invalid hotkey", message)
        self.assertEqual(self.app.config["max_items"], 100)
        self.platform.change_hotkey.assert_not_called()

    def test_out_of_range_or_non_numeric_sizes_change_nothing(self):
        for key, bad in (("max_items", "0"), ("max_items", "1001"), ("max_items", "x"),
                         ("preview_chars", "19"), ("preview_chars", "301"), ("preview_chars", "")):
            with self.subTest(key=key, value=bad):
                saved, message = self.app.save_settings({**self.values, key: bad})
                self.assertFalse(saved)
                self.assertIn("History size", message)
        self.assertEqual(self.app.config["max_items"], 100)

    def test_the_boundary_values_are_accepted(self):
        for key, low, high in (("max_items", "1", "1000"), ("preview_chars", "20", "300")):
            for value in (low, high):
                with self.subTest(key=key, value=value):
                    self.assertTrue(self.app.save_settings({**self.values, key: value})[0])

    def test_lowering_the_history_size_trims_existing_history(self):
        for n in range(10):
            self.app.history.add_text(str(n))
        self.app.save_settings({**self.values, "max_items": "3"})
        self.assertEqual(len(self.app.history.items), 3)

    def test_a_failing_startup_change_still_saves_everything_else_and_warns(self):
        self.platform.set_autostart.side_effect = OSError("denied")
        saved, message = self.app.save_settings(self.values)
        self.assertTrue(saved)
        self.assertIn("denied", message)
        self.assertEqual(self.app.config["max_items"], 50)


if __name__ == "__main__":
    unittest.main()
