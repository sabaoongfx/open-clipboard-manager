import queue
import unittest
from unittest import mock

from PIL import Image

from base import IsolatedDataTestCase, w


class AppWithoutWindow(IsolatedDataTestCase):
    """App logic that needs no Tk window: the object is built without __init__ and given stand-ins."""

    def setUp(self):
        super().setUp()
        self.platform = mock.patch.object(w, "PLATFORM").start()
        self.addCleanup(mock.patch.stopall)
        self.app = w.App.__new__(w.App)
        self.app.root = mock.Mock()
        self.app.window = mock.Mock()
        self.app.events = queue.Queue()
        self.app.history = w.History(self.config())
        self.app.paused = False
        self.app.last_seq = None


class PollClipboard(AppWithoutWindow):
    def test_the_next_poll_is_scheduled_even_when_reading_the_clipboard_fails(self):
        self.platform.clipboard_token.side_effect = RuntimeError("clipboard busy")
        with self.assertRaises(RuntimeError):
            self.app.poll_clipboard()
        self.app.root.after.assert_called_once_with(self.app.POLL_MS, self.app.poll_clipboard)

    def test_new_text_is_recorded_and_the_window_refreshed(self):
        self.platform.clipboard_token.return_value = 7
        self.platform.get_text.return_value = "hello"
        self.app.poll_clipboard()
        self.assertEqual([i["text"] for i in self.app.history.items], ["hello"])
        self.app.window.refresh.assert_called_once()
        self.assertEqual(self.app.last_seq, 7)

    def test_an_unchanged_clipboard_is_not_read_again(self):
        self.app.last_seq = 7
        self.platform.clipboard_token.return_value = 7
        self.app.poll_clipboard()
        self.platform.get_text.assert_not_called()

    def test_nothing_is_recorded_while_paused_but_the_change_is_remembered(self):
        self.app.paused = True
        self.platform.clipboard_token.return_value = 9
        self.platform.get_text.return_value = "secret"
        self.app.poll_clipboard()
        self.assertEqual(self.app.history.items, [])
        self.assertEqual(self.app.last_seq, 9)


class ImageCapture(AppWithoutWindow):
    def test_an_image_is_stored_on_a_worker_thread_and_handed_back_as_an_event(self):
        self.platform.get_text.return_value = None
        self.platform.get_image.return_value = Image.new("RGB", (6, 4), "green")
        self.app.capture_clipboard()
        event, item = self.app.events.get(timeout=5)
        self.assertIs(event, w.Event.IMAGE)
        self.assertEqual((item["type"], item["w"], item["h"]), ("image", 6, 4))
        self.assertEqual(self.image_files(), [item["file"]])
        self.assertEqual(self.app.history.items, [], "the history is only changed on the main thread")

    def test_pumping_the_event_adds_the_image_and_refreshes_the_window(self):
        item = self.app.history.store_image(Image.new("RGB", (3, 3), "red"))
        self.app.post(w.Event.IMAGE, item)
        self.app.pump()
        self.assertEqual(self.app.history.items, [item])
        self.app.window.refresh.assert_called_once()
        self.app.root.after.assert_called_once_with(100, self.app.pump)

    def test_no_event_is_posted_when_images_are_turned_off(self):
        self.app.history.config["save_images"] = False
        self.platform.get_text.return_value = None
        self.platform.get_image.return_value = Image.new("RGB", (2, 2))
        self.app.capture_clipboard()
        with self.assertRaises(queue.Empty):
            self.app.events.get(timeout=1)

    def test_a_clipboard_with_neither_text_nor_image_is_ignored(self):
        self.platform.get_text.return_value = None
        self.platform.get_image.return_value = None
        self.app.capture_clipboard()
        self.assertTrue(self.app.events.empty())
        self.assertEqual(self.app.history.items, [])


class Events(AppWithoutWindow):
    def test_events_are_delivered_in_order_with_their_payload(self):
        self.app.post(w.Event.ERROR, "boom")
        self.app.post(w.Event.TOGGLE)
        self.assertEqual(self.app.events.get_nowait(), (w.Event.ERROR, "boom"))
        self.assertEqual(self.app.events.get_nowait(), (w.Event.TOGGLE, None))

    def test_the_error_event_shows_a_warning(self):
        self.app.post(w.Event.ERROR, "hotkey taken")
        with mock.patch.object(w.messagebox, "showwarning") as warn:
            self.app.pump()
        warn.assert_called_once_with(w.APP_NAME, "hotkey taken")

    def test_the_hotkey_remembers_where_to_paste_unless_our_window_has_focus(self):
        self.platform.remember_foreground.return_value = "notepad"
        self.app.window.has_focus.return_value = False
        self.app.post(w.Event.HOTKEY)
        self.app.pump()
        self.assertEqual(self.app.prev_window, "notepad")
        self.app.window.show.assert_called_once_with()

        self.app.prev_window = "kept"
        self.app.window.has_focus.return_value = True
        self.app.post(w.Event.HOTKEY)
        self.app.pump()
        self.assertEqual(self.app.prev_window, "kept")

    def test_opening_from_the_tray_forgets_the_paste_target(self):
        self.app.prev_window = "notepad"
        self.app.post(w.Event.SHOW)
        self.app.pump()
        self.assertIsNone(self.app.prev_window)


class HotkeyMigration(AppWithoutWindow):
    def setUp(self):
        super().setUp()
        self.platform.default_hotkey = "win+v"

    def migrate(self, **config):
        self.app.config = self.config(**config)
        self.app._migrate_config()
        return self.app.config

    def test_the_old_default_is_replaced_by_the_new_one_once(self):
        config = self.migrate(hotkey="ctrl+alt+h")
        self.assertEqual(config["hotkey"], "win+v")
        self.assertTrue(config["hotkey_migrated"])
        self.assertEqual(w.load_json(w.CONFIG_FILE, {})["hotkey"], "win+v")

    def test_a_hotkey_chosen_later_is_left_alone_even_if_it_is_the_old_default(self):
        config = self.migrate(hotkey="ctrl+alt+h", hotkey_migrated=True)
        self.assertEqual(config["hotkey"], "ctrl+alt+h")

    def test_a_custom_hotkey_is_never_touched(self):
        config = self.migrate(hotkey="ctrl+shift+k")
        self.assertEqual(config["hotkey"], "ctrl+shift+k")
        self.assertNotIn("hotkey_migrated", config)

    def test_a_fresh_install_already_has_the_new_default_and_needs_no_migration(self):
        config = self.migrate(hotkey="win+v")
        self.assertEqual(config["hotkey"], "win+v")
        self.assertNotIn("hotkey_migrated", config)


class StartingTheApp(IsolatedDataTestCase):
    def test_a_second_launch_only_asks_the_running_copy_to_open_and_exits(self):
        with mock.patch.object(w.instance, "send", return_value=True) as send, \
                mock.patch.object(w, "App") as app:
            w.main([])
        send.assert_called_once_with(w.DATA_DIR, "show")
        app.assert_not_called()

    def test_the_settings_flag_asks_for_the_settings_page(self):
        with mock.patch.object(w.instance, "send", return_value=True) as send:
            w.main(["--settings"])
        send.assert_called_once_with(w.DATA_DIR, "settings")

    def test_with_nothing_running_a_new_app_starts_and_creates_its_config(self):
        with mock.patch.object(w.instance, "send", return_value=False), mock.patch.object(w, "App") as app:
            w.main([])
        app.return_value.run.assert_called_once_with(show=False)
        self.assertTrue(w.load_json(w.CONFIG_FILE, None))

    def test_the_show_flag_opens_the_window_of_a_new_app(self):
        with mock.patch.object(w.instance, "send", return_value=False), mock.patch.object(w, "App") as app:
            w.main(["--show"])
        app.return_value.run.assert_called_once_with(show=True)


class StoreImage(IsolatedDataTestCase):
    def test_store_image_does_not_touch_the_history_until_add_item(self):
        h = w.History(self.config())
        item = h.store_image(Image.new("RGB", (4, 4), "red"))
        self.assertEqual(h.items, [])
        self.assertEqual(self.image_files(), [item["file"]])
        h.add_item(item)
        self.assertEqual(h.items, [item])

    def test_store_image_returns_none_when_images_are_off(self):
        h = w.History(self.config(save_images=False))
        self.assertIsNone(h.store_image(Image.new("RGB", (4, 4))))
        self.assertEqual(self.image_files(), [])


if __name__ == "__main__":
    unittest.main()
