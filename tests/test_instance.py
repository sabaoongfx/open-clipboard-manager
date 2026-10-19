import os
import shutil
import tempfile
import threading
import unittest

import base  # noqa: F401  (sets up sys.path)
import instance


class SingleInstance(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="ocm-instance-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.received = []
        self.got = threading.Event()
        self.server = instance.Server(self.dir, self.on_command)
        self.server.start()
        self.addCleanup(self.server.stop)

    def on_command(self, command):
        self.received.append(command)
        self.got.set()

    def test_a_second_launch_reaches_the_running_instance(self):
        self.assertTrue(instance.send(self.dir, "show"))
        self.assertTrue(self.got.wait(2))
        self.assertEqual(self.received, ["show"])

    def test_settings_can_be_requested_too(self):
        self.assertTrue(instance.send(self.dir, "settings"))
        self.assertTrue(self.got.wait(2))
        self.assertEqual(self.received, ["settings"])

    def test_unknown_commands_are_refused(self):
        self.assertFalse(instance.send(self.dir, "format-disk"))
        self.assertEqual(self.received, [])

    def test_only_the_loopback_interface_is_used(self):
        self.assertEqual(self.server.sock.getsockname()[0], "127.0.0.1")

    def test_no_instance_means_nobody_answers(self):
        self.assertFalse(instance.send(tempfile.mkdtemp(), "show"))

    def test_a_stale_port_file_is_not_mistaken_for_a_running_instance(self):
        self.server.stop()
        with open(os.path.join(self.dir, "instance.port"), "w") as f:
            f.write("1")  # nothing listens on port 1
        self.assertFalse(instance.send(self.dir, "show"))

    def test_garbage_in_the_port_file_is_ignored(self):
        with open(os.path.join(self.dir, "instance.port"), "w") as f:
            f.write("not a number")
        self.assertFalse(instance.send(self.dir, "show"))

    def test_stopping_removes_the_port_file_and_the_instance_goes_away(self):
        self.server.stop()
        self.assertFalse(os.path.exists(os.path.join(self.dir, "instance.port")))
        self.assertFalse(instance.send(self.dir, "show"))

    def test_several_launches_in_a_row_are_all_answered(self):
        for _ in range(5):
            self.assertTrue(instance.send(self.dir, "show"))


if __name__ == "__main__":
    unittest.main()
