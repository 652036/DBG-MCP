from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dbgmcp import runtime


class SafeStartSessionTests(unittest.TestCase):
    def test_safe_start_session_without_target_uses_upstream_behavior(self) -> None:
        client = mock.Mock()

        with mock.patch.object(runtime, "_ORIGINAL_START_SESSION", return_value=4321) as original:
            session_pid = runtime.safe_start_session(client)

        self.assertEqual(session_pid, 4321)
        original.assert_called_once_with(client, "", "", "")
        client.load_executable.assert_not_called()

    def test_safe_start_session_with_target_uses_two_phase_launch(self) -> None:
        client = mock.Mock()
        client.load_executable.return_value = True

        with mock.patch.object(runtime, "_ORIGINAL_START_SESSION", return_value=9876) as original:
            session_pid = runtime.safe_start_session(
                client,
                target_exe=r"C:\Windows\System32\notepad.exe",
                load_timeout=15,
            )

        self.assertEqual(session_pid, 9876)
        original.assert_called_once_with(client, "", "", "")
        client.wait_cmd_ready.assert_called_once_with(10)
        client.load_executable.assert_called_once_with(
            r"C:\Windows\System32\notepad.exe",
            "",
            "",
            wait_timeout=15,
        )

    def test_safe_start_session_cleans_up_on_load_failure(self) -> None:
        client = mock.Mock()
        client.load_executable.return_value = False

        with (
            mock.patch.object(runtime, "_ORIGINAL_START_SESSION", return_value=1111),
            mock.patch.object(runtime, "cleanup_session_best_effort", return_value=[]) as cleanup,
        ):
            with self.assertRaisesRegex(RuntimeError, "Failed to load executable"):
                runtime.safe_start_session(client, target_exe=r"C:\broken.exe")

        cleanup.assert_called_once_with(client)


if __name__ == "__main__":
    unittest.main()
