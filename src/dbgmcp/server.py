"""Local MCP entry point with sensible defaults for this workstation."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from x64dbg_automate.mcp_server import main as x64dbg_mcp_main

from dbgmcp.cli import (
    detect_debugger_path,
    ensure_x64dbg_path_env,
    missing_plugin_files,
    plugin_dir_for_debugger,
)
from dbgmcp.runtime import patch_x64dbg_client_start_session

patch_x64dbg_client_start_session()


def _resolve_default_debugger() -> Path | None:
    debugger_path, _ = detect_debugger_path()
    return debugger_path


def _ensure_x64dbg_path() -> Path | None:
    ensure_x64dbg_path_env()
    configured = os.environ.get("X64DBG_PATH", "").strip()
    if configured:
        return Path(configured)
    return _resolve_default_debugger()


def _warn_missing_plugin(debugger_path: Path | None) -> None:
    if debugger_path is None:
        print(
            "dbgmcp: X64DBG_PATH is not set and no default debugger executable was found.",
            file=sys.stderr,
        )
        return

    plugin_dir = plugin_dir_for_debugger(debugger_path)
    missing = missing_plugin_files(plugin_dir, debugger_path)
    if missing:
        print(
            "dbgmcp: missing x64dbg-automate plugin files in "
            f"{plugin_dir}: {', '.join(missing)}. "
            "Run `python -m dbgmcp install-plugin` before starting a session.",
            file=sys.stderr,
        )


def main() -> None:
    debugger_path = _ensure_x64dbg_path()
    _warn_missing_plugin(debugger_path)
    x64dbg_mcp_main()


if __name__ == "__main__":
    main()
