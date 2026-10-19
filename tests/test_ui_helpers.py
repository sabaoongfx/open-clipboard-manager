import unittest
from unittest import mock

import base  # noqa: F401  (sets up sys.path)
import ui


class When(unittest.TestCase):
    NOW = 1_700_000_000

    def ago(self, seconds):
        with mock.patch.object(ui.time, "time", return_value=self.NOW):
            return ui.when(self.NOW - seconds)

    def test_missing_timestamp_is_blank(self):
        self.assertEqual(ui.when(None), "")
        self.assertEqual(ui.when(0), "")

    def test_relative_wording(self):
        self.assertEqual(self.ago(5), "Just now")
        self.assertEqual(self.ago(59), "Just now")
        self.assertEqual(self.ago(60), "1 min ago")
        self.assertEqual(self.ago(59 * 60), "59 min ago")
        self.assertEqual(self.ago(3600), "1 h ago")
        self.assertEqual(self.ago(23 * 3600), "23 h ago")

    def test_older_than_a_day_shows_a_date(self):
        self.assertRegex(self.ago(3 * 86400), r"^[A-Z][a-z]{2} \d{2}$")

    def test_a_timestamp_in_the_future_does_not_go_negative(self):
        self.assertEqual(self.ago(-500), "Just now")


class Icons(unittest.TestCase):
    def test_every_navigation_icon_has_a_drawer(self):
        for _, _, name in ui.MainWindow.NAV:
            self.assertIn(name, ui.ICON_DRAWERS)

    def test_every_icon_draws_something_in_the_requested_colour(self):
        for name in ui.ICON_DRAWERS:
            with self.subTest(icon=name):
                img = ui.render_icon(name, "#ff0000")
                self.assertEqual(img.size, (ui.ICON_SIZE, ui.ICON_SIZE))
                self.assertIsNotNone(img.getbbox(), "the icon is blank")
                pixels = [p for p in img.getdata() if p[3] > 0]
                self.assertTrue(all(p[:3] == (255, 0, 0) for p in pixels))

    def test_icons_stay_inside_their_canvas(self):
        for name in ui.ICON_DRAWERS:
            with self.subTest(icon=name):
                left, top, right, bottom = ui.render_icon(name, "#000000").getbbox()
                self.assertGreaterEqual(left, 0)
                self.assertGreaterEqual(top, 0)
                self.assertLessEqual(right, ui.ICON_SIZE)
                self.assertLessEqual(bottom, ui.ICON_SIZE)


class Themes(unittest.TestCase):
    def test_light_and_dark_define_the_same_colours(self):
        self.assertEqual(set(ui.LIGHT), set(ui.DARK))

    def test_every_colour_is_a_hex_value(self):
        for theme in (ui.LIGHT, ui.DARK):
            for name, value in theme.items():
                with self.subTest(colour=name):
                    self.assertRegex(value, r"^#[0-9a-f]{6}$")


if __name__ == "__main__":
    unittest.main()
