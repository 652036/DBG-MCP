from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dbgmcp import cli
from dbgmcp import install_plugin


REPO_ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_MACHINE_PATHS = ("KittyDebugTool", r"Desktop\vtce", "Desktop/vtce", "醉梦DBG")


def _without_x64dbg_path() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("X64DBG_PATH", None)
    return env


class DetectDebuggerPathTests(unittest.TestCase):
    def test_detect_debugger_path_prefers_env_var(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_exe = Path(temp_dir) / "x64dbg.exe"
            fake_exe.write_bytes(b"MZ")

            with mock.patch.dict(os.environ, {"X64DBG_PATH": str(fake_exe)}, clear=False):
                detected, source = cli.detect_debugger_path()

            self.assertEqual(detected, fake_exe.resolve())
            self.assertEqual(source, "env:X64DBG_PATH")

    def test_detect_debugger_path_falls_back_to_standard_location(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_exe = Path(temp_dir) / "release" / "x64" / "x64dbg.exe"
            fake_exe.parent.mkdir(parents=True)
            fake_exe.write_bytes(b"MZ")

            with mock.patch.dict(os.environ, _without_x64dbg_path(), clear=True):
                with mock.patch.object(cli, "KNOWN_DEBUGGER_PATHS", (fake_exe,)):
                    detected, source = cli.detect_debugger_path()

            self.assertEqual(detected, fake_exe.resolve())
            self.assertEqual(source, "known-local-path")

    def test_detect_debugger_path_returns_not_found_without_env_or_standard_install(self) -> None:
        missing = Path(tempfile.gettempdir()) / "dbgmcp-missing-x64dbg.exe"
        with mock.patch.dict(os.environ, _without_x64dbg_path(), clear=True):
            with mock.patch.object(cli, "KNOWN_DEBUGGER_PATHS", (missing,)):
                detected, source = cli.detect_debugger_path()

        self.assertIsNone(detected)
        self.assertEqual(source, "not-found")

    def test_known_debugger_paths_are_standard_x64dbg_locations(self) -> None:
        rendered = [str(path).replace("\\", "/").lower() for path in cli.KNOWN_DEBUGGER_PATHS]
        joined = "\n".join(rendered)
        self.assertTrue(any(item.endswith("c:/x64dbg/release/x64/x64dbg.exe") for item in rendered))
        self.assertTrue(any(item.endswith("c:/x64dbg/release/x32/x32dbg.exe") for item in rendered))
        self.assertTrue(any("appdata/local/x64dbg/release/x64/x64dbg.exe" in item for item in rendered))
        self.assertTrue(any(item.endswith("program files/x64dbg/x64dbg.exe") for item in rendered))
        self.assertNotIn("kittydebugtool", joined)
        self.assertNotIn("desktop/vtce", joined)
        self.assertNotIn("醉梦dbg.exe", joined)

    def test_iter_debugger_candidates_starts_with_env_then_known_paths(self) -> None:
        env_exe = Path(r"C:\custom\x64dbg.exe")
        known_exe = Path(r"C:\x64dbg\release\x64\x64dbg.exe")
        with mock.patch.dict(os.environ, {"X64DBG_PATH": str(env_exe)}, clear=False):
            with mock.patch.object(cli, "KNOWN_DEBUGGER_PATHS", (known_exe,)):
                candidates = list(cli._iter_debugger_candidates())

        self.assertEqual(
            candidates,
            [
                (env_exe, "env:X64DBG_PATH"),
                (known_exe, "known-local-path"),
            ],
        )

    def test_discover_debugger_roots_uses_x64dbg_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_exe = Path(temp_dir) / "x64dbg.exe"
            fake_exe.write_bytes(b"MZ")
            env = _without_x64dbg_path()
            env["X64DBG_PATH"] = str(fake_exe)

            with mock.patch.dict(os.environ, env, clear=True):
                with mock.patch.object(cli, "KNOWN_DEBUGGER_PATHS", ()):
                    roots = cli.discover_debugger_roots()

        self.assertEqual(roots, [("64", fake_exe.parent.resolve())])

    def test_discover_debugger_roots_classifies_x32dbg_from_env(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_exe = Path(temp_dir) / "x32dbg.exe"
            fake_exe.write_bytes(b"MZ")
            env = _without_x64dbg_path()
            env["X64DBG_PATH"] = str(fake_exe)

            with mock.patch.dict(os.environ, env, clear=True):
                with mock.patch.object(cli, "KNOWN_DEBUGGER_PATHS", ()):
                    roots = cli.discover_debugger_roots()

        self.assertEqual(roots, [("32", fake_exe.parent.resolve())])

    def test_discover_debugger_roots_accepts_x64dbg_path_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            env = _without_x64dbg_path()
            env["X64DBG_PATH"] = str(root)

            with mock.patch.dict(os.environ, env, clear=True):
                with mock.patch.object(cli, "KNOWN_DEBUGGER_PATHS", ()):
                    roots = cli.discover_debugger_roots()

        self.assertEqual(roots, [("64", root.resolve())])

    def test_build_mcp_config_includes_detected_path(self) -> None:
        debugger_path = Path(r"C:\tools\x64dbg\x64dbg.exe")
        config = cli.build_mcp_config(debugger_path)

        server = config["mcpServers"]["dbgmcp"]
        self.assertEqual(server["args"], ["-m", "dbgmcp", "mcp"])
        self.assertEqual(server["env"]["X64DBG_PATH"], str(debugger_path))

    def test_find_plugin_files_returns_empty_tuple_for_missing_dir(self) -> None:
        missing_dir = Path(tempfile.gettempdir()) / "dbgmcp-missing-plugin-dir"
        if missing_dir.exists():
            self.fail("Temporary test path unexpectedly exists")

        self.assertEqual(cli.find_plugin_files(missing_dir), ())

    def test_missing_plugin_files_reports_runtime_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_dir = Path(temp_dir)
            (plugin_dir / "x64dbg-automate.dp64").write_bytes(b"plugin")

            debugger_path = Path(r"C:\tools\x64dbg\x64dbg.exe")
            missing = cli.missing_plugin_files(plugin_dir, debugger_path)

        self.assertEqual(missing, ("libzmq-mt-4_3_5.dll",))

    def test_missing_plugin_files_reports_runtime_dependency_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_dir = Path(temp_dir)
            (plugin_dir / "x64dbg-automate.dp64").write_bytes(b"plugin")

            missing = cli.missing_plugin_files(
                plugin_dir,
                Path(r"C:\tools\x64dbg\release\x64\x64dbg.exe"),
            )

        self.assertEqual(missing, ("libzmq-mt-4_3_5.dll",))

    def test_main_smoke_test_subcommand_delegates_to_module(self) -> None:
        with mock.patch("dbgmcp.smoke_test.main", return_value=0) as mocked_main:
            result = cli.main(["smoke-test", "--no-target"])

        self.assertEqual(result, 0)
        mocked_main.assert_called_once_with(["--no-target"])

    def test_main_install_plugin_subcommand_delegates_to_module(self) -> None:
        with mock.patch("dbgmcp.install_plugin.main", return_value=0) as mocked_main:
            result = cli.main(["install-plugin", "--skip-32"])

        self.assertEqual(result, 0)
        mocked_main.assert_called_once_with(["--skip-32"])


class InstallPluginDiscoveryTests(unittest.TestCase):
    def test_parse_args_has_no_hardcoded_debugger_root_defaults(self) -> None:
        args = install_plugin._parse_args([])
        self.assertIsNone(args.dbg64_root)
        self.assertIsNone(args.dbg32_root)

    def test_resolve_install_targets_uses_x64dbg_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_exe = Path(temp_dir) / "x64dbg.exe"
            fake_exe.write_bytes(b"MZ")
            env = _without_x64dbg_path()
            env["X64DBG_PATH"] = str(fake_exe)

            with mock.patch.dict(os.environ, env, clear=True):
                with mock.patch.object(cli, "KNOWN_DEBUGGER_PATHS", ()):
                    targets = install_plugin.resolve_install_targets(skip_32=True)

        self.assertEqual(targets, [("64", fake_exe.parent.resolve())])

    def test_resolve_install_targets_uses_explicit_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            dbg64 = Path(temp_dir) / "x64"
            dbg32 = Path(temp_dir) / "x32"
            dbg64.mkdir()
            dbg32.mkdir()

            with mock.patch.object(cli, "KNOWN_DEBUGGER_PATHS", ()):
                with mock.patch.dict(os.environ, _without_x64dbg_path(), clear=True):
                    targets = install_plugin.resolve_install_targets(
                        dbg64_root=dbg64,
                        dbg32_root=dbg32,
                    )

        self.assertEqual(targets, [("64", dbg64), ("32", dbg32)])

    def test_resolve_install_targets_uses_standard_location(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_exe = Path(temp_dir) / "release" / "x64" / "x64dbg.exe"
            fake_exe.parent.mkdir(parents=True)
            fake_exe.write_bytes(b"MZ")

            with mock.patch.dict(os.environ, _without_x64dbg_path(), clear=True):
                with mock.patch.object(cli, "KNOWN_DEBUGGER_PATHS", (fake_exe,)):
                    targets = install_plugin.resolve_install_targets(skip_32=True)

        self.assertEqual(targets, [("64", fake_exe.parent.resolve())])

    def test_resolve_install_targets_requires_x64dbg_path_or_standard_location(self) -> None:
        missing = Path(tempfile.gettempdir()) / "dbgmcp-missing-debugger-root"
        with mock.patch.dict(os.environ, _without_x64dbg_path(), clear=True):
            with mock.patch.object(cli, "KNOWN_DEBUGGER_PATHS", (missing,)):
                with self.assertRaises(SystemExit) as ctx:
                    install_plugin.resolve_install_targets()

        self.assertIn("X64DBG_PATH", str(ctx.exception))
        self.assertIn("--dbg64-root", str(ctx.exception))


class PublicDefaultPathTests(unittest.TestCase):
    def test_source_and_docs_do_not_ship_machine_specific_debugger_paths(self) -> None:
        files = [
            REPO_ROOT / "src" / "dbgmcp" / "cli.py",
            REPO_ROOT / "src" / "dbgmcp" / "install_plugin.py",
            REPO_ROOT / "README.md",
            REPO_ROOT / "README.zh-CN.md",
        ]
        for path in files:
            text = path.read_text(encoding="utf-8")
            for needle in FORBIDDEN_MACHINE_PATHS:
                self.assertNotIn(needle, text, msg=f"{path} still contains {needle!r}")


if __name__ == "__main__":
    unittest.main()
