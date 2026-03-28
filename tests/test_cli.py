from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dbgmcp import cli


class DetectDebuggerPathTests(unittest.TestCase):
    def test_detect_debugger_path_prefers_env_var(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_exe = Path(temp_dir) / "x64dbg.exe"
            fake_exe.write_bytes(b"MZ")

            with mock.patch.dict(os.environ, {"X64DBG_PATH": str(fake_exe)}, clear=False):
                detected, source = cli.detect_debugger_path()

            self.assertEqual(detected, fake_exe.resolve())
            self.assertEqual(source, "env:X64DBG_PATH")

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


if __name__ == "__main__":
    unittest.main()
