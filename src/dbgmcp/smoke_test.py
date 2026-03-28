"""Basic local smoke test for x64dbg automation."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from x64dbg_automate import X64DbgClient

from dbgmcp.cli import ensure_x64dbg_path_env
from dbgmcp.runtime import cleanup_session_best_effort, safe_start_session

DEFAULT_TARGET = Path(r"C:\Windows\System32\notepad.exe")

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        type=Path,
        default=None,
        help="Optional target executable to load. Defaults to notepad.exe unless --no-target is set.",
    )
    parser.add_argument(
        "--no-target",
        action="store_true",
        help="Only verify debugger startup and plugin connectivity.",
    )
    return parser.parse_args(argv)


def _resolve_target(explicit_target: Path | None, no_target: bool) -> Path | None:
    if no_target:
        return None
    if explicit_target is not None:
        return explicit_target
    configured = os.environ.get("DBGMCP_SMOKE_TARGET", "").strip()
    if configured:
        return Path(configured)
    return DEFAULT_TARGET


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    ensure_x64dbg_path_env()
    configured = os.environ.get("X64DBG_PATH", "").strip()
    debugger_path = Path(configured) if configured else None
    if debugger_path is None or not debugger_path.is_file():
        print("Smoke test failed: no debugger executable found.", file=sys.stderr)
        return 1

    target = _resolve_target(args.target, args.no_target)
    if target is not None and not target.is_file():
        print(f"Smoke test failed: target executable not found: {target}", file=sys.stderr)
        return 1

    client = X64DbgClient(str(debugger_path))
    session_pid = 0
    try:
        if target is None:
            session_pid = safe_start_session(client)
        else:
            session_pid = safe_start_session(client, str(target), load_timeout=15)
        print(f"Debugger PID: {session_pid}")
        sessions = X64DbgClient.list_sessions()
        matching = [session for session in sessions if session.pid == session_pid]
        if not matching:
            raise RuntimeError("Debugger session was not discoverable after launch.")
        session = matching[0]
        print(f"REQ port: {session.sess_req_rep_port}")
        print(f"SUB port: {session.sess_pub_sub_port}")
        if target is not None:
            cip, ok = client.eval_sync("cip")
            if not ok:
                raise RuntimeError("Failed to resolve cip register.")
            instruction = client.disassemble_at(cip)
            debuggee_pid = client.debugee_pid()
            print(f"Debuggee PID: {debuggee_pid}")
            print(f"CIP: 0x{cip:X}")
            print(f"Instruction: {instruction.instruction if instruction else 'unknown'}")
        return 0
    except Exception as exc:
        print(f"Smoke test failed: {exc}", file=sys.stderr)
        return 1
    finally:
        try:
            session_pid = session_pid or int(getattr(client, "session_pid", 0) or 0)
            if session_pid:
                cleanup_errors = cleanup_session_best_effort(client)
                for error in cleanup_errors:
                    print(f"Cleanup warning: {error}", file=sys.stderr)
        except Exception as exc:
            print(f"Cleanup warning: {exc}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
