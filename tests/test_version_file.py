import os
import sys
import unittest

import base  # noqa: F401  (sets up sys.path)

sys.path.insert(0, os.path.join(base.APP_DIR, "tools"))
import make_version_file as mvf  # noqa: E402
from platform_base import APP_NAME, APP_VERSION  # noqa: E402


class VersionTuple(unittest.TestCase):
    def test_a_three_part_version_gets_a_fourth_number(self):
        self.assertEqual(mvf.version_tuple("0.3.0"), (0, 3, 0, 0))

    def test_shorter_and_four_part_versions(self):
        self.assertEqual(mvf.version_tuple("2"), (2, 0, 0, 0))
        self.assertEqual(mvf.version_tuple("1.2.3.4"), (1, 2, 3, 4))

    def test_unusable_versions_are_rejected(self):
        for version in ("", "1.2.x", "1.2.3.4.5", "70000.0.0", "-1.0.0", "0.3.0-beta"):
            with self.subTest(version=version), self.assertRaises(ValueError):
                mvf.version_tuple(version)

    def test_the_app_version_itself_is_usable(self):
        mvf.version_tuple(APP_VERSION)


class VersionFileText(unittest.TestCase):
    def setUp(self):
        self.text = mvf.build("Open-Clipboard-Manager-x64.exe")

    def test_the_file_carries_the_product_name_and_version(self):
        dotted = ".".join(str(n) for n in mvf.version_tuple(APP_VERSION))
        self.assertIn(f"StringStruct('ProductName', {APP_NAME!r})", self.text)
        self.assertIn(f"StringStruct('ProductVersion', '{dotted}')", self.text)
        self.assertIn(f"StringStruct('FileVersion', '{dotted}')", self.text)

    def test_company_description_and_original_file_name_are_set(self):
        self.assertIn("StringStruct('CompanyName', 'sabaoongfx')", self.text)
        self.assertIn(f"StringStruct('FileDescription', {APP_NAME!r})", self.text)
        self.assertIn("StringStruct('OriginalFilename', 'Open-Clipboard-Manager-x64.exe')", self.text)

    def test_the_original_file_name_differs_per_build(self):
        self.assertIn("'Open-Clipboard-Manager.exe'", mvf.build("Open-Clipboard-Manager.exe"))

    def test_fixed_version_numbers_match_the_strings(self):
        self.assertIn("filevers=(0, 3, 0, 0)", mvf.build("x.exe", version="0.3.0"))
        self.assertIn("prodvers=(1, 2, 3, 0)", mvf.build("x.exe", version="1.2.3"))

    def test_the_text_is_valid_for_pyinstaller(self):
        """PyInstaller evaluates this text with its own VSVersionInfo classes; stand in simple recorders."""
        seen = {}

        def recorder(name):
            def make(*args, **kwargs):
                seen.setdefault(name, []).append((args, kwargs))
                return (name, args, kwargs)
            return make

        names = ("VSVersionInfo", "FixedFileInfo", "StringFileInfo", "StringTable", "StringStruct",
                 "VarFileInfo", "VarStruct")
        eval(compile(self.text.split("\n", 1)[1], "version.txt", "eval"), {n: recorder(n) for n in names})
        strings = {args[0]: args[1] for args, _ in seen["StringStruct"]}
        self.assertEqual(strings["ProductName"], APP_NAME)
        self.assertEqual(len(seen["VSVersionInfo"]), 1)
        self.assertEqual(seen["StringTable"][0][0][0], "040904B0")

    def test_every_string_is_quoted_safely(self):
        text = mvf.build("it's.exe", name="Tom's Clipboard")
        compile(text.split("\n", 1)[1], "version.txt", "eval")  # still one valid expression


if __name__ == "__main__":
    unittest.main()
