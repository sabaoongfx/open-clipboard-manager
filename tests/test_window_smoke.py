"""Builds the real window for every page and theme. Needs a display; skipped where Tk cannot start."""
import tkinter as tk
import unittest
from unittest import mock

from PIL import Image

from base import IsolatedDataTestCase, w
import ui


class WindowSmoke(IsolatedDataTestCase):
    def setUp(self):
        super().setUp()
        try:
            self.root = tk.Tk()
        except tk.TclError as e:
            self.skipTest(f"no display: {e}")
        self.root.withdraw()
        self.addCleanup(self.root.destroy)

        self.platform = mock.Mock()
        self.platform.ui_font = "Segoe UI"
        self.platform.name = "windows"
        self.platform.hotkey_examples = "e.g. ctrl+alt+h"
        self.platform.autostart_enabled.return_value = False
        self.platform.is_dark_mode.return_value = False

        self.app = mock.Mock()
        self.app.config = self.config()
        self.app.paused = False
        self.app.history = w.History(self.app.config)
        self.app.history.add_text("hello world")
        self.app.history.add_text("see bug #42")
        self.app.history.add_image(Image.new("RGB", (30, 20), "orange"))
        self.app.image_file.side_effect = w.image_path
        self.app.actions = w.Actions()
        self.window = ui.MainWindow(self.root, self.app, self.platform, w.make_icon())

    def test_every_page_builds_in_both_themes(self):
        for dark in (False, True):
            self.platform.is_dark_mode.return_value = dark
            for page in ("history", "images", "actions", "settings"):
                with self.subTest(dark=dark, page=page):
                    self.window.show(page)
                    self.root.update()
                    self.assertEqual(self.window.page, page)
                    self.assertEqual(self.window.title.cget("text"), ui.MainWindow.TITLES[page])

    def test_the_window_and_top_bar_carry_the_app_name(self):
        self.window.show()
        self.assertEqual(self.window.win.title(), w.APP_NAME)

    def test_the_history_lists_every_entry_newest_first(self):
        self.window.show("history")
        self.assertEqual([i["type"] for i in self.window.visible], ["image", "text", "text"])
        self.assertEqual(len(self.window.tree.get_children()), 3)

    def test_the_images_page_lists_only_images(self):
        self.window.show("images")
        self.assertEqual([i["type"] for i in self.window.visible], ["image"])

    def test_searching_filters_the_list(self):
        self.window.show("history")
        self.window.search_var.set("bug")
        self.assertEqual([i.get("text") for i in self.window.visible], ["see bug #42"])
        self.window.search_var.set("nothing matches this")
        self.assertEqual(self.window.visible, [])
        self.assertIsNone(self.window.selected_item())

    def test_searching_for_image_finds_images(self):
        self.window.show("history")
        self.window.search_var.set("image")
        self.assertEqual([i["type"] for i in self.window.visible], ["image"])

    def test_choosing_an_entry_hands_it_to_the_app(self):
        self.window.show("history")
        self.window.tree.selection_set("1")
        self.window._use_selected()
        self.app.use_item.assert_called_once_with(self.window.visible[1])

    def test_remove_is_only_enabled_with_a_selection(self):
        self.window.show("history")
        self.assertTrue(self.window.remove_btn.enabled)
        self.window.search_var.set("zzz")
        self.assertFalse(self.window.remove_btn.enabled)

    def test_the_pause_button_follows_the_app_state(self):
        self.window.show("history")
        self.assertEqual(self.window.pause_btn.text, "Pause")
        self.app.paused = True
        self.window.update_pause()
        self.assertEqual(self.window.pause_btn.text, "Resume")

    def test_hiding_withdraws_the_window_and_showing_brings_it_back(self):
        self.window.show()
        self.window.hide()
        self.assertEqual(self.window.win.state(), "withdrawn")
        self.window.show()
        self.assertNotEqual(self.window.win.state(), "withdrawn")

    def test_a_theme_change_rebuilds_the_window_without_leaving_errors_behind(self):
        errors = []
        self.root.report_callback_exception = lambda *args: errors.append(args)
        self.window.show()
        self.platform.is_dark_mode.return_value = True
        self.window.show()
        for _ in range(8):  # let the delayed "drop topmost" callback of the first window run
            self.root.update()
            self.root.after(40)
        self.assertEqual(errors, [])

    def test_saving_settings_reports_the_result_in_the_status_label(self):
        self.window.show("settings")
        self.app.save_settings.return_value = (True, None)
        self.window._save_settings()
        self.assertEqual(self.window.status.cget("text"), "Settings saved")
        self.app.save_settings.return_value = (False, "Invalid hotkey: nope")
        self.window._save_settings()
        self.assertEqual(self.window.status.cget("text"), "Invalid hotkey: nope")
        self.assertEqual(self.window.status.cget("fg"), self.window.t["danger"])

    def test_the_actions_page_lists_the_loaded_actions(self):
        self.window.show("actions")
        self.assertEqual(len(self.window.actions_tree.get_children()), len(self.app.actions.actions))


if __name__ == "__main__":
    unittest.main()
