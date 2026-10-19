"""Shared test setup: import the app and point its data files at a temporary folder."""
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP_DIR)

import winclipman as w  # noqa: E402  (needs the path set up above)


class IsolatedDataTestCase(unittest.TestCase):
    """Runs each test with empty history/config/actions/image locations so real user data is never touched."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="winclipman-test-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        for name, filename in (("IMAGE_DIR", "images"), ("HISTORY_FILE", "history.json"),
                               ("CONFIG_FILE", "config.json"), ("USER_ACTIONS_FILE", "actions.json")):
            patcher = mock.patch.object(w, name, os.path.join(self.dir, filename))
            patcher.start()
            self.addCleanup(patcher.stop)

    def config(self, **overrides):
        return {**w.DEFAULT_CONFIG, **overrides}

    def image_files(self):
        return sorted(os.listdir(w.IMAGE_DIR)) if os.path.isdir(w.IMAGE_DIR) else []
