import json
import os
import re
import unittest
from unittest import mock

from base import APP_DIR, IsolatedDataTestCase, w


class Matching(IsolatedDataTestCase):
    def write_actions(self, actions):
        with open(w.USER_ACTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(actions, f)

    def test_a_matching_entry_returns_every_command_of_the_action(self):
        self.write_actions([{"name": "Bug", "regex": r"bug\s*#?(\d+)",
                             "commands": [{"name": "One", "exec": "a"}, {"name": "Two", "exec": "b"}]}])
        found = w.Actions().match("see bug #42")
        self.assertEqual([(a, c, e) for a, c, e, _ in found], [("Bug", "One", "a"), ("Bug", "Two", "b")])
        self.assertEqual(found[0][3].group(1), "42")

    def test_no_match_gives_no_commands(self):
        self.write_actions([{"name": "Bug", "regex": r"bug (\d+)", "commands": [{"name": "x", "exec": "y"}]}])
        self.assertEqual(w.Actions().match("nothing here"), [])

    def test_several_actions_can_match_the_same_text(self):
        self.write_actions([
            {"name": "A", "regex": "foo", "commands": [{"name": "a", "exec": "a"}]},
            {"name": "B", "regex": "oo", "commands": [{"name": "b", "exec": "b"}]},
        ])
        self.assertEqual([a for a, *_ in w.Actions().match("foo")], ["A", "B"])

    def test_broken_actions_are_skipped_and_the_rest_still_work(self):
        self.write_actions([
            {"name": "bad regex", "regex": "(", "commands": []},
            {"name": "missing keys"},
            {"name": "good", "regex": "x", "commands": [{"name": "c", "exec": "e"}]},
        ])
        self.assertEqual([a for a, *_ in w.Actions().match("x")], ["good"])

    def test_matching_works_across_lines(self):
        self.write_actions([{"name": "A", "regex": r"start.*end", "commands": [{"name": "c", "exec": "e"}]}])
        self.assertEqual(len(w.Actions().match("start\nmiddle\nend")), 1)

    def test_a_missing_or_corrupt_actions_file_means_no_actions(self):
        with open(w.USER_ACTIONS_FILE, "w", encoding="utf-8") as f:
            f.write("not json")
        self.assertEqual(w.Actions().match("anything"), [])

    def test_the_bundled_defaults_are_used_when_the_user_has_no_file(self):
        self.assertFalse(os.path.exists(w.USER_ACTIONS_FILE))
        self.assertTrue(w.Actions().actions)


class Running(IsolatedDataTestCase):
    def run_template(self, template, text, pattern):
        match = re.search(pattern, text, re.S)
        with mock.patch.object(w.subprocess, "Popen") as popen:
            w.Actions.run(template, match)
        (command,), kwargs = popen.call_args
        self.assertTrue(kwargs["shell"])
        return command

    def test_capture_groups_are_substituted(self):
        self.assertEqual(self.run_template("open https://x/\\1", "bug #42", r"bug\s*#?(\d+)"),
                         "open https://x/42")

    def test_the_whole_match_is_substituted_for_backslash_zero(self):
        self.assertEqual(self.run_template('open "\\0"', "go to http://a.b/c now", r"http://\S+"),
                         'open "http://a.b/c"')

    def test_a_group_that_does_not_exist_becomes_empty(self):
        self.assertEqual(self.run_template("echo [\\2]", "abc", r"(b)"), "echo []")

    def test_quotes_in_clipboard_text_cannot_close_the_quoted_argument(self):
        command = self.run_template('open "\\0"', 'a" & calc & "b', r".+")
        self.assertEqual(command.count('"'), 2)

    def test_line_breaks_in_clipboard_text_are_removed(self):
        command = self.run_template('open "\\0"', "line1\nline2\r\nline3", r".+")
        self.assertNotIn("\n", command)
        self.assertNotIn("\r", command)


class BundledActionFiles(unittest.TestCase):
    """The default action files for every platform must be valid, even when run on another OS."""

    def test_every_default_file_is_well_formed(self):
        for name in ("actions_windows.json", "actions_macos.json"):
            with self.subTest(file=name):
                with open(os.path.join(APP_DIR, name), encoding="utf-8") as f:
                    actions = json.load(f)
                self.assertTrue(actions)
                for action in actions:
                    re.compile(action["regex"])
                    self.assertTrue(action["name"])
                    self.assertTrue(action["commands"])
                    for command in action["commands"]:
                        self.assertTrue(command["name"])
                        self.assertTrue(command["exec"])


if __name__ == "__main__":
    unittest.main()
