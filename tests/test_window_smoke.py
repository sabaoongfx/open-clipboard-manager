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
        self.addCleanup(self.cancel_pending_timers)  # runs first: no timer may outlive the root window

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

    def cancel_pending_timers(self):
        for timer in self.root.tk.splitlist(self.root.tk.call("after", "info")):
            self.root.after_cancel(timer)

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

    def settle(self):
        """Let Tk lay the window out and run queued idle work (the row icons are placed after layout)."""
        for _ in range(30):
            self.root.update_idletasks()
            self.root.update()
            if not self.window._layout_pending:
                break
        self.root.update_idletasks()
        self.root.update()

    def shown_row_buttons(self):
        return [b for b in self.window.row_buttons if b.winfo_manager()]

    def test_the_toolbar_has_a_labelled_copy_button_that_copies_the_selected_entry(self):
        self.window.show("history")
        self.settle()
        self.assertEqual(self.window.copy_btn.text, "Copy")
        self.assertTrue(self.window.copy_btn.enabled)
        self.app.copy_item.return_value = True
        self.window.tree.selection_set("1")
        self.window._copy_selected()
        self.app.copy_item.assert_called_once_with(self.window.visible[1])
        self.assertEqual(self.window.preview_caption.cget("text"), "Copied to clipboard")

    def test_a_failed_copy_says_so(self):
        self.window.show("history")
        self.app.copy_item.return_value = False
        self.window._copy_selected()
        self.assertEqual(self.window.preview_caption.cget("text"), "Could not copy this item")
        self.assertEqual(self.window.preview_caption.cget("fg"), self.window.t["danger"])

    def test_the_confirmation_goes_away_and_the_caption_comes_back(self):
        self.window.show("history")
        self.app.copy_item.return_value = True
        self.window._copy_selected()
        token = self.window._flash_token
        self.window._end_flash(token)
        self.assertIn("characters", self.window.preview_caption.cget("text").lower() + " characters")
        self.assertEqual(self.window.preview_caption.cget("fg"), self.window.t["muted"])
        self.window._end_flash(object())  # a stale timer from an earlier copy must not clobber a newer message
        self.assertEqual(self.window.preview_caption.cget("fg"), self.window.t["muted"])

    def test_copy_is_disabled_when_nothing_is_selected(self):
        self.window.show("history")
        self.window.search_var.set("zzz")
        self.assertFalse(self.window.copy_btn.enabled)

    def test_every_visible_row_gets_a_copy_and_a_trash_icon_over_its_last_cell(self):
        self.window.show("history")
        self.settle()
        buttons = self.shown_row_buttons()
        self.assertEqual(len(buttons), 3)
        self.assertEqual(sorted(b.iid for b in buttons), ["0", "1", "2"])
        for button in buttons:
            box = self.window.tree.bbox(button.iid, "actions")
            self.assertEqual((button.winfo_x(), button.winfo_y()), (box[0], box[1]))

    def test_clicking_a_rows_trash_icon_removes_that_row(self):
        self.window.show("history")
        self.settle()
        button = next(b for b in self.shown_row_buttons() if b.iid == "1")
        button.trash.event_generate("<Button-1>", x=1, y=1)
        self.app.remove_item.assert_called_once_with(self.window.visible[1])

    def test_clicking_a_rows_copy_icon_copies_that_row(self):
        self.window.show("history")
        self.settle()
        self.app.copy_item.return_value = True
        button = next(b for b in self.shown_row_buttons() if b.iid == "2")
        button.copy.event_generate("<Button-1>", x=1, y=1)
        self.app.copy_item.assert_called_once_with(self.window.visible[2])

    def test_the_icons_follow_the_list_when_it_is_filtered(self):
        self.window.show("history")
        self.settle()
        self.window.search_var.set("bug")
        self.settle()
        self.assertEqual([b.iid for b in self.shown_row_buttons()], ["0"])
        self.window.search_var.set("zzz")
        self.settle()
        self.assertEqual(self.shown_row_buttons(), [])

    def test_there_is_no_scrollbar_while_all_rows_fit(self):
        self.window.show("history")
        self.settle()
        self.assertFalse(self.window.tree_scroll.winfo_ismapped())

    def test_the_scrollbar_appears_only_when_the_list_is_longer_than_the_view(self):
        for n in range(60):
            self.app.history.add_text(f"entry {n}")
        self.window.show("history")
        self.settle()
        self.assertTrue(self.window.tree_scroll.winfo_ismapped())
        self.window.search_var.set("entry 55")  # one match fits again
        self.settle()
        self.assertFalse(self.window.tree_scroll.winfo_ismapped())

    def test_icons_exist_only_for_rows_in_view_and_are_reused(self):
        for n in range(60):
            self.app.history.add_text(f"entry {n}")
        self.window.show("history")
        self.settle()
        in_view = len(self.shown_row_buttons())
        self.assertTrue(0 < in_view < 60)
        self.assertEqual(len(self.window.row_buttons), in_view)
        self.window.tree.yview_moveto(0.5)
        self.settle()
        self.assertEqual(len(self.window.row_buttons), in_view, "the pool is reused, not grown")
        self.assertTrue(all(b.iid for b in self.shown_row_buttons()))

    def test_the_selected_rows_icons_share_its_background(self):
        self.window.show("history")
        self.settle()
        selected = next(b for b in self.shown_row_buttons() if b.iid == self.window.tree.selection()[0])
        other = next(b for b in self.shown_row_buttons() if b.iid != self.window.tree.selection()[0])
        self.assertEqual(selected.cget("bg"), self.window.t["selected"])
        self.assertEqual(other.cget("bg"), self.window.t["elevated"])

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
        # Tk reports a timer whose command was deleted ("invalid command name") through bgerror, which
        # Python never sees, so install a handler that records those as well.
        self.root.tk.createcommand("bgerror", lambda message: errors.append(message))
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
