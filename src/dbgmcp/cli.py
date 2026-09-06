from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import tempfile
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]

KNOWN_DEBUGGER_PATHS = (
    PROJECT_ROOT / "x64dbg.exe",
    PROJECT_ROOT / "x96dbg.exe",
    PROJECT_ROOT / "x32dbg.exe",
    PROJECT_ROOT / "release" / "x64" / "x64dbg.exe",
    PROJECT_ROOT / "release" / "x32" / "x32dbg.exe",
    Path.home() / "AppData" / "Local" / "x64dbg" / "release" / "x64" / "x64dbg.exe",
    Path.home() / "AppData" / "Local" / "x64dbg" / "release" / "x32" / "x32dbg.exe",
    Path("C:/x64dbg/release/x64/x64dbg.exe"),
    Path("C:/x64dbg/release/x32/x32dbg.exe"),
    Path("C:/x64dbg/x64dbg.exe"),
    Path("C:/x64dbg/x96dbg.exe"),
    Path("C:/Program Files/x64dbg/x64dbg.exe"),
    Path("C:/Program Files (x86)/x64dbg/x32dbg.exe"),
)

PLUGIN_GLOBS = (
    "xauto*.dp64",
    "xauto*.dp32",
    "x64dbg*automate*.dp64",
    "x64dbg*automate*.dp32",
)

PLUGIN_RUNTIME_FILES = {
    "64": ("x64dbg-automate.dp64", "libzmq-mt-4_3_5.dll"),
    "32": ("x64dbg-automate.dp32", "libzmq-mt-4_3_5.dll"),
}


@dataclass(frozen=True)
class DoctorReport:
    python_version: str
    package_version: str | None
    debugger_path: Path | None
    debugger_source: str
    plugin_dir: Path | None
    plugin_files: tuple[Path, ...]
    required_plugin_files: tuple[str, ...]
    missing_plugin_files: tuple[str, ...]
    active_sessions: str


def _iter_debugger_candidates() -> Iterable[tuple[Path, str]]:
    env_path = os.environ.get("X64DBG_PATH", "").strip()
    if env_path:
        yield Path(env_path), "env:X64DBG_PATH"

    for candidate in KNOWN_DEBUGGER_PATHS:
        yield candidate, "known-local-path"


def detect_debugger_path() -> tuple[Path | None, str]:
    seen: set[str] = set()
    for candidate, source in _iter_debugger_candidates():
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        try:
            exists = candidate.is_file()
        except OSError:
            continue
        if exists:
            return candidate.resolve(), source
    return None, "not-found"


def _root_from_candidate(path: Path) -> tuple[str, Path] | None:
    try:
        is_file = path.is_file()
        is_dir = False if is_file else path.is_dir()
    except OSError:
        return None
    if is_file:
        root = path.parent
    elif is_dir:
        root = path
    else:
        return None
    try:
        root = root.resolve()
    except OSError:
        return None
    return (debugger_arch(path) or "64"), root


def discover_debugger_roots() -> list[tuple[str, Path]]:
    roots: list[tuple[str, Path]] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        found = _root_from_candidate(path)
        if found is None:
            return
        arch, root = found
        key = str(root).lower()
        if key in seen:
            return
        seen.add(key)
        roots.append((arch, root))

    env_path = os.environ.get("X64DBG_PATH", "").strip()
    if env_path:
        add(Path(env_path))

    for candidate in KNOWN_DEBUGGER_PATHS:
        add(candidate)

    return roots


def plugin_dir_for_debugger(debugger_path: Path | None) -> Path | None:
    if debugger_path is None:
        return None
    return debugger_path.parent / "plugins"


def find_plugin_files(plugin_dir: Path | None) -> tuple[Path, ...]:
    if plugin_dir is None or not plugin_dir.exists():
        return ()

    results: list[Path] = []
    for pattern in PLUGIN_GLOBS:
        results.extend(sorted(plugin_dir.glob(pattern)))
    unique = {path.resolve(): None for path in results}
    return tuple(unique.keys())


def debugger_arch(debugger_path: Path | None) -> str | None:
    if debugger_path is None:
        return None

    probe = str(debugger_path).lower()
    if "x32dbg" in probe or "dbg32" in probe:
        return "32"
    return "64"


def required_plugin_files(debugger_path: Path | None) -> tuple[str, ...]:
    arch = debugger_arch(debugger_path)
    if arch is None:
        return ()
    return PLUGIN_RUNTIME_FILES[arch]


def missing_plugin_files(plugin_dir: Path | None, debugger_path: Path | None) -> tuple[str, ...]:
    if plugin_dir is None:
        return required_plugin_files(debugger_path)

    missing: list[str] = []
    for filename in required_plugin_files(debugger_path):
        if not (plugin_dir / filename).is_file():
            missing.append(filename)
    return tuple(missing)


def discover_active_sessions() -> str:
    try:
        from x64dbg_automate import X64DbgClient
    except Exception as exc:
        return f"unavailable ({exc})"

    try:
        sessions = X64DbgClient.list_sessions()
    except Exception as exc:
        return f"error ({exc})"

    if not sessions:
        return "0"
    return str(len(sessions))


def collect_doctor_report() -> DoctorReport:
    try:
        package_version = metadata.version("x64dbg_automate")
    except metadata.PackageNotFoundError:
        package_version = None

    debugger_path, debugger_source = detect_debugger_path()
    plugin_dir = plugin_dir_for_debugger(debugger_path)
    plugin_files = find_plugin_files(plugin_dir)
    required_files = required_plugin_files(debugger_path)
    missing_files = missing_plugin_files(plugin_dir, debugger_path)

    return DoctorReport(
        python_version=platform.python_version(),
        package_version=package_version,
        debugger_path=debugger_path,
        debugger_source=debugger_source,
        plugin_dir=plugin_dir,
        plugin_files=plugin_files,
        required_plugin_files=required_files,
        missing_plugin_files=missing_files,
        active_sessions=discover_active_sessions(),
    )


def build_mcp_config(debugger_path: Path | None) -> dict[str, object]:
    env: dict[str, str] = {}
    if debugger_path is not None:
        env["X64DBG_PATH"] = str(debugger_path)

    return {
        "mcpServers": {
            "dbgmcp": {
                "command": sys.executable,
                "args": ["-m", "dbgmcp", "mcp"],
                "env": env,
            }
        }
    }


def ensure_x64dbg_path_env(explicit_path: str = "") -> None:
    if explicit_path:
        os.environ["X64DBG_PATH"] = explicit_path
        return

    if os.environ.get("X64DBG_PATH", "").strip():
        return

    detected, _ = detect_debugger_path()
    if detected is not None:
        os.environ["X64DBG_PATH"] = str(detected)


def run_mcp(explicit_path: str = "") -> int:
    ensure_x64dbg_path_env(explicit_path)

    try:
        from dbgmcp.runtime import patch_x64dbg_client_start_session
        from x64dbg_automate.mcp_server import main as upstream_main
    except Exception as exc:
        print(f"Failed to import x64dbg_automate MCP server: {exc}", file=sys.stderr)
        return 1

    patch_x64dbg_client_start_session()
    upstream_main()
    return 0


def command_doctor(_: argparse.Namespace) -> int:
    report = collect_doctor_report()
    lines = [
        f"python_version={report.python_version}",
        f"x64dbg_automate_version={report.package_version or 'missing'}",
        f"debugger_path={report.debugger_path or 'not found'}",
        f"debugger_source={report.debugger_source}",
        f"plugin_dir={report.plugin_dir or 'unknown'}",
        f"plugin_files_found={len(report.plugin_files)}",
        f"plugin_required_files={','.join(report.required_plugin_files) or 'unknown'}",
        f"plugin_missing_files={','.join(report.missing_plugin_files) or 'none'}",
        f"active_sessions={report.active_sessions}",
    ]

    if report.plugin_files:
        for plugin_file in report.plugin_files:
            lines.append(f"plugin={plugin_file}")
    if report.missing_plugin_files:
        lines.append(
            "next_step=Install or repair the x64dbg-automate plugin runtime files before using start_session."
        )

    print("\n".join(lines))
    return 0


def command_print_mcp_config(_: argparse.Namespace) -> int:
    debugger_path, _ = detect_debugger_path()
    config = build_mcp_config(debugger_path)
    print(json.dumps(config, indent=2, ensure_ascii=False))
    return 0


def command_print_env(_: argparse.Namespace) -> int:
    debugger_path, source = detect_debugger_path()
    payload = {
        "X64DBG_PATH": str(debugger_path) if debugger_path else "",
        "source": source,
        "temp_dir": tempfile.gettempdir(),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def command_mcp(args: argparse.Namespace) -> int:
    return run_mcp(args.x64dbg_path)


def command_install_plugin(args: argparse.Namespace) -> int:
    from dbgmcp.install_plugin import main as install_plugin_main

    argv: list[str] = []
    if args.dbg64_root is not None:
        argv.extend(["--dbg64-root", str(args.dbg64_root)])
    if args.dbg32_root is not None:
        argv.extend(["--dbg32-root", str(args.dbg32_root)])
    if args.skip_32:
        argv.append("--skip-32")
    if args.skip_64:
        argv.append("--skip-64")
    return install_plugin_main(argv)


def command_smoke_test(args: argparse.Namespace) -> int:
    from dbgmcp.smoke_test import main as smoke_test_main

    argv: list[str] = []
    if args.target is not None:
        argv.extend(["--target", str(args.target)])
    if args.no_target:
        argv.append("--no-target")
    return smoke_test_main(argv)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dbgmcp",
        description="Local wrapper around the official x64dbg Automate MCP server.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Check Python dependency, debugger detection, plugin files, and active sessions.",
    )
    doctor_parser.set_defaults(func=command_doctor)

    env_parser = subparsers.add_parser(
        "print-env",
        help="Print the detected X64DBG_PATH and temp directory used by x64dbg-automate.",
    )
    env_parser.set_defaults(func=command_print_env)

    config_parser = subparsers.add_parser(
        "print-mcp-config",
        help="Print an MCP config snippet using this local wrapper.",
    )
    config_parser.set_defaults(func=command_print_mcp_config)

    mcp_parser = subparsers.add_parser(
        "mcp",
        help="Run the upstream x64dbg Automate MCP server with optional local path auto-detection.",
    )
    mcp_parser.add_argument(
        "--x64dbg-path",
        default="",
        help="Explicit debugger executable path. If omitted, dbgmcp uses X64DBG_PATH or a standard x64dbg location.",
    )
    mcp_parser.set_defaults(func=command_mcp)

    install_parser = subparsers.add_parser(
        "install-plugin",
        help="Download and install the compatible x64dbg-automate plugin into local debugger roots.",
    )
    install_parser.add_argument("--dbg64-root", type=Path, default=None)
    install_parser.add_argument("--dbg32-root", type=Path, default=None)
    install_parser.add_argument("--skip-32", action="store_true")
    install_parser.add_argument("--skip-64", action="store_true")
    install_parser.set_defaults(func=command_install_plugin)

    smoke_parser = subparsers.add_parser(
        "smoke-test",
        help="Launch the debugger, verify x64dbg-automate connectivity, and optionally load a target executable.",
    )
    smoke_parser.add_argument(
        "--target",
        type=Path,
        default=None,
        help="Executable to load for a fuller end-to-end debug session check.",
    )
    smoke_parser.add_argument(
        "--no-target",
        action="store_true",
        help="Only verify debugger launch and session discovery.",
    )
    smoke_parser.set_defaults(func=command_smoke_test)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
