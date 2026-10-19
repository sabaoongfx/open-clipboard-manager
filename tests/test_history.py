import json
import os
import unittest
from unittest import mock

from PIL import Image

from base import IsolatedDataTestCase, w


def picture(colour="red", size=(8, 6)):
    return Image.new("RGB", size, colour)


class AddingAndOrdering(IsolatedDataTestCase):
    def test_newest_entry_is_first(self):
        h = w.History(self.config())
        h.add_text("a")
        h.add_text("b")
        self.assertEqual([i["text"] for i in h.items], ["b", "a"])

    def test_copying_the_same_text_again_moves_it_to_the_top_without_duplicating(self):
        h = w.History(self.config())
        for text in ("a", "b", "a"):
            h.add_text(text)
        self.assertEqual([i["text"] for i in h.items], ["a", "b"])

    def test_blank_text_is_ignored(self):
        h = w.History(self.config())
        for text in ("", "   ", "\n\t"):
            h.add_text(text)
        self.assertEqual(h.items, [])

    def test_bump_moves_an_entry_to_the_top_and_refreshes_its_time(self):
        h = w.History(self.config())
        with mock.patch.object(w.time, "time", return_value=1000):
            h.add_text("a")
        h.add_text("b")
        with mock.patch.object(w.time, "time", return_value=2000):
            h.bump(h.items[1])
        self.assertEqual([i["text"] for i in h.items], ["a", "b"])
        self.assertEqual(h.items[0]["time"], 2000)


class Limits(IsolatedDataTestCase):
    def test_history_never_exceeds_max_items(self):
        h = w.History(self.config(max_items=3))
        for n in range(6):
            h.add_text(str(n))
        self.assertEqual([i["text"] for i in h.items], ["5", "4", "3"])

    def test_trimming_deletes_the_image_files_of_dropped_entries(self):
        h = w.History(self.config(max_items=1))
        h.add_image(picture("red"))
        h.add_image(picture("blue"))
        self.assertEqual(len(h.items), 1)
        self.assertEqual(self.image_files(), [h.items[0]["file"]])

    def test_apply_limits_trims_and_persists_after_the_limit_is_lowered(self):
        cfg = self.config(max_items=10)
        h = w.History(cfg)
        for n in range(5):
            h.add_text(str(n))
        cfg["max_items"] = 2
        h.apply_limits()
        self.assertEqual(len(h.items), 2)
        self.assertEqual(len(w.load_json(w.HISTORY_FILE, [])), 2)


class Identity(IsolatedDataTestCase):
    def test_text_equal_to_an_image_file_name_does_not_collide_with_the_image(self):
        h = w.History(self.config())
        h.add_image(picture())
        filename = h.items[0]["file"]
        h.add_text(filename)
        self.assertEqual(sorted(i["type"] for i in h.items), ["image", "text"])
        h.remove({"type": "text", "text": filename})
        self.assertEqual([i["type"] for i in h.items], ["image"])
        self.assertEqual(self.image_files(), [filename])

    def test_the_same_picture_is_stored_once(self):
        h = w.History(self.config())
        h.add_image(picture("red"))
        h.add_image(picture("red"))
        self.assertEqual(len(h.items), 1)
        self.assertEqual(len(self.image_files()), 1)

    def test_different_pictures_are_stored_separately(self):
        h = w.History(self.config())
        h.add_image(picture("red"))
        h.add_image(picture("blue"))
        self.assertEqual(len(self.image_files()), 2)

    def test_images_are_not_recorded_when_disabled(self):
        h = w.History(self.config(save_images=False))
        h.add_image(picture())
        self.assertEqual(h.items, [])
        self.assertEqual(self.image_files(), [])


class RemovingAndClearing(IsolatedDataTestCase):
    def test_removing_an_image_deletes_its_file(self):
        h = w.History(self.config())
        h.add_image(picture())
        h.remove(h.items[0])
        self.assertEqual(h.items, [])
        self.assertEqual(self.image_files(), [])

    def test_clear_removes_every_entry_and_image_file(self):
        h = w.History(self.config())
        h.add_text("a")
        h.add_image(picture())
        h.clear()
        self.assertEqual(h.items, [])
        self.assertEqual(self.image_files(), [])
        self.assertEqual(w.load_json(w.HISTORY_FILE, None), [])


class Persistence(IsolatedDataTestCase):
    def test_history_survives_a_restart(self):
        h = w.History(self.config())
        h.add_text("a")
        h.add_image(picture())
        again = w.History(self.config())
        self.assertEqual([i["type"] for i in again.items], ["image", "text"])
        self.assertEqual(again.items[1]["text"], "a")

    def test_nothing_is_written_when_saving_history_is_off(self):
        h = w.History(self.config(save_history=False))
        h.add_text("a")
        self.assertFalse(os.path.exists(w.HISTORY_FILE))

    def test_history_written_before_image_support_still_loads(self):
        os.makedirs(self.dir, exist_ok=True)
        with open(w.HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(["old one", "old two"], f)
        h = w.History(self.config())
        self.assertEqual([i["text"] for i in h.items], ["old one", "old two"])

    def test_garbage_entries_in_the_file_are_skipped(self):
        with open(w.HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump([42, None, {"type": "text"}, {"type": "mystery"}, {"type": "text", "text": "ok"}], f)
        h = w.History(self.config())
        self.assertEqual([i["text"] for i in h.items], ["ok"])

    def test_an_entry_whose_image_file_is_missing_is_dropped_on_load(self):
        with open(w.HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump([{"type": "image", "file": "gone.png", "w": 1, "h": 1}], f)
        self.assertEqual(w.History(self.config()).items, [])

    def test_a_corrupt_history_file_gives_an_empty_history(self):
        with open(w.HISTORY_FILE, "w", encoding="utf-8") as f:
            f.write("{not json")
        self.assertEqual(w.History(self.config()).items, [])


class OrphanImageSweep(IsolatedDataTestCase):
    def test_unreferenced_files_are_deleted_at_startup(self):
        os.makedirs(w.IMAGE_DIR)
        stale = os.path.join(w.IMAGE_DIR, "stale.png")
        open(stale, "wb").close()
        w.History(self.config())
        self.assertFalse(os.path.exists(stale))

    def test_files_left_over_from_a_run_without_saved_history_are_deleted(self):
        h = w.History(self.config(save_history=False))
        h.add_image(picture())
        self.assertEqual(len(self.image_files()), 1)
        w.History(self.config(save_history=False))
        self.assertEqual(self.image_files(), [])

    def test_files_that_entries_refer_to_are_kept(self):
        h = w.History(self.config())
        h.add_image(picture())
        before = self.image_files()
        w.History(self.config())
        self.assertEqual(self.image_files(), before)

    def test_a_missing_image_folder_is_fine(self):
        self.assertEqual(w.History(self.config()).items, [])


if __name__ == "__main__":
    unittest.main()
