"""Keep installed plugin bytes intact when archive preparation fails."""
from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dbgmcp import install_plugin


class InstallZipTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plugins = self.root / "plugins"
        self.plugins.mkdir()
        self.archive = self.root / "release.zip"

    def make_zip(self, entries: list[tuple[str, bytes]]) -> None:
        with zipfile.ZipFile(self.archive, "w", compression=zipfile.ZIP_STORED) as archive:
            for name, payload in entries:
                archive.writestr(name, payload)

    def corrupt_payload(self, payload: bytes) -> None:
        data = bytearray(self.archive.read_bytes())
        offset = data.index(payload)
        data[offset] ^= 1  # Leave the ZIP member's expected CRC unchanged.
        self.archive.write_bytes(data)

    def test_valid_release_replaces_files_and_ignores_other_directories(self) -> None:
        target = self.plugins / "plugin.dp64"
        target.write_bytes(b"old")
        self.make_zip([
            ("Release/plugin.dp64", b"new plugin"),
            ("Release/lib.dll", b"new dependency"),
            ("Debug/ignored.dll", b"ignored"),
        ])
        installed = install_plugin._install_zip(self.archive, self.plugins)
        self.assertEqual(installed, [target, self.plugins / "lib.dll"])
        self.assertEqual(target.read_bytes(), b"new plugin")
        self.assertEqual((self.plugins / "lib.dll").read_bytes(), b"new dependency")
        self.assertFalse((self.plugins / "ignored.dll").exists())

    def test_corrupt_first_member_does_not_truncate_existing_plugin(self) -> None:
        target = self.plugins / "plugin.dp64"
        target.write_bytes(b"old plugin")
        payload = b"unique corrupt first payload"
        self.make_zip([("Release/plugin.dp64", payload)])
        self.corrupt_payload(payload)
        with self.assertRaises(zipfile.BadZipFile):
            install_plugin._install_zip(self.archive, self.plugins)
        self.assertEqual(target.read_bytes(), b"old plugin")

    def test_corrupt_later_member_preserves_entire_existing_installation(self) -> None:
        (self.plugins / "plugin.dp64").write_bytes(b"old plugin")
        (self.plugins / "lib.dll").write_bytes(b"old dependency")
        payload = b"unique corrupt second payload"
        self.make_zip([
            ("Release/plugin.dp64", b"new plugin"),
            ("Release/lib.dll", payload),
        ])
        self.corrupt_payload(payload)
        with self.assertRaises(zipfile.BadZipFile):
            install_plugin._install_zip(self.archive, self.plugins)
        self.assertEqual((self.plugins / "plugin.dp64").read_bytes(), b"old plugin")
        self.assertEqual((self.plugins / "lib.dll").read_bytes(), b"old dependency")
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["plugins", "release.zip"])

    def test_corrupt_archive_does_not_leave_partially_installed_new_files(self) -> None:
        payload = b"unique corrupt new dependency"
        self.make_zip([("Release/plugin.dp64", b"new"), ("Release/lib.dll", payload)])
        self.corrupt_payload(payload)
        with self.assertRaises(zipfile.BadZipFile):
            install_plugin._install_zip(self.archive, self.plugins)
        self.assertEqual(list(self.plugins.iterdir()), [])

    def test_flattened_name_collision_is_rejected_before_writes(self) -> None:
        target = self.plugins / "lib.dll"
        target.write_bytes(b"old dependency")
        self.make_zip([("Release/a/lib.dll", b"one"), ("Release/b/lib.dll", b"two")])
        with self.assertRaisesRegex(RuntimeError, "Duplicate"):
            install_plugin._install_zip(self.archive, self.plugins)
        self.assertEqual(target.read_bytes(), b"old dependency")

    def test_windows_case_collision_is_rejected_before_writes(self) -> None:
        self.make_zip([("Release/LIB.dll", b"one"), ("Release/lib.DLL", b"two")])
        with self.assertRaisesRegex(RuntimeError, "Duplicate"):
            install_plugin._install_zip(self.archive, self.plugins)
        self.assertEqual(list(self.plugins.iterdir()), [])

    def test_staging_write_failure_preserves_existing_file(self) -> None:
        target = self.plugins / "plugin.dp64"
        target.write_bytes(b"old plugin")
        self.make_zip([("Release/plugin.dp64", b"new")])
        def fail_copy(src, dst):
            dst.write(b"partial")
            raise OSError("simulated staging write failure")
        with mock.patch.object(install_plugin.shutil, "copyfileobj", side_effect=fail_copy):
            with self.assertRaisesRegex(OSError, "simulated"):
                install_plugin._install_zip(self.archive, self.plugins)
        self.assertEqual(target.read_bytes(), b"old plugin")

    def test_archive_without_release_files_is_rejected(self) -> None:
        self.make_zip([("Debug/ignored.dll", b"ignored")])
        with self.assertRaisesRegex(RuntimeError, "No Release"):
            install_plugin._install_zip(self.archive, self.plugins)
        self.assertEqual(list(self.plugins.iterdir()), [])

    def test_distinct_nested_names_keep_existing_flattening_contract(self) -> None:
        self.make_zip([("Release/nested/helper.dll", b"helper")])
        self.assertEqual(
            install_plugin._install_zip(self.archive, self.plugins),
            [self.plugins / "helper.dll"],
        )
        self.assertEqual((self.plugins / "helper.dll").read_bytes(), b"helper")


if __name__ == "__main__":
    unittest.main()
