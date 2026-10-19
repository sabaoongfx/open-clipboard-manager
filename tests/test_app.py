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
