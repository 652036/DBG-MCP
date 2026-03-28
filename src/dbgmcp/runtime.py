from __future__ import annotations

from typing import Callable

from x64dbg_automate import X64DbgClient

_ORIGINAL_START_SESSION: Callable[[X64DbgClient, str, str, str], int] = X64DbgClient.start_session


def cleanup_session_best_effort(client: X64DbgClient) -> list[str]:
    """Try hard to tear down a debugger session without raising."""
    errors: list[str] = []
    session_pid = getattr(client, "session_pid", 0) or 0

    if session_pid:
        try:
            client.terminate_session()
            return errors
        except Exception as exc:
            errors.append(f"terminate_session failed: {exc}")

    try:
        client.detach_session()
        return errors
    except Exception as exc:
        errors.append(f"detach_session failed: {exc}")

    debugger_path = getattr(client, "x64dbg_path", None)
    if session_pid and debugger_path:
        try:
            rescue = X64DbgClient(str(debugger_path))
            rescue.attach_session(session_pid)
            rescue.terminate_session()
            return errors
        except Exception as exc:
            errors.append(f"rescue terminate failed: {exc}")

    return errors


def safe_start_session(
    client: X64DbgClient,
    target_exe: str = "",
    cmdline: str = "",
    current_dir: str = "",
    warmup_timeout: int = 10,
    load_timeout: int = 10,
) -> int:
    """Work around local debugger builds that hang on start_session(target_exe=...)."""
    target = target_exe.strip()
    if not target and (cmdline or current_dir):
        raise ValueError("cmdline and current_dir cannot be provided without target_exe")

    if not target:
        return _ORIGINAL_START_SESSION(client, "", "", "")

    session_pid = _ORIGINAL_START_SESSION(client, "", "", "")
    try:
        try:
            client.wait_cmd_ready(warmup_timeout)
        except Exception:
            pass

        loaded = client.load_executable(
            target,
            cmdline,
            current_dir,
            wait_timeout=load_timeout,
        )
        if not loaded:
            raise RuntimeError("Failed to load executable")
        return session_pid
    except Exception:
        cleanup_session_best_effort(client)
        raise


def patch_x64dbg_client_start_session() -> None:
    """Monkey-patch the upstream client so MCP start_session inherits the safer flow."""
    current = X64DbgClient.start_session
    if getattr(current, "__dbgmcp_patched__", False):
        return

    def _patched_start_session(
        self: X64DbgClient,
        target_exe: str = "",
        cmdline: str = "",
        current_dir: str = "",
    ) -> int:
        return safe_start_session(
            self,
            target_exe=target_exe,
            cmdline=cmdline,
            current_dir=current_dir,
        )

    _patched_start_session.__dbgmcp_patched__ = True  # type: ignore[attr-defined]
    X64DbgClient.start_session = _patched_start_session
