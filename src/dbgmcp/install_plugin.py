"""Install x64dbg-automate plugin assets into local debugger directories."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from x64dbg_automate import COMPAT_VERSION


GITHUB_RELEASES_API = "https://api.github.com/repos/dariushoule/x64dbg-automate/releases"
DEFAULT_DBG64 = Path(r"C:\Users\Administrator\Desktop\vtce\KittyDebugTool\DBG\DBG64")
DEFAULT_DBG32 = Path(r"C:\Users\Administrator\Desktop\vtce\KittyDebugTool\DBG\DBG32")


def _fetch_json(url: str) -> list[dict] | dict:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "dbgmcp-installer",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def _pick_release() -> dict:
    releases = _fetch_json(GITHUB_RELEASES_API)
    for release in releases:
        tag_name = str(release.get("tag_name", ""))
        if COMPAT_VERSION in tag_name and not release.get("draft") and not release.get("prerelease"):
            return release
    raise RuntimeError(
        f"Could not find a published x64dbg-automate release matching compat version {COMPAT_VERSION!r}."
    )


def _pick_asset(release: dict, arch: str) -> dict:
    needle = f"release{arch}"
    for asset in release.get("assets", []):
        name = str(asset.get("name", "")).lower()
        if needle in name and name.endswith(".zip"):
            return asset
    raise RuntimeError(f"Could not find a {arch}-bit asset in release {release.get('tag_name')}.")


def _download_asset(asset: dict, destination: Path) -> None:
    url = asset["browser_download_url"]
    request = urllib.request.Request(url, headers={"User-Agent": "dbgmcp-installer"})
    with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as handle:
        shutil.copyfileobj(response, handle)


def _install_zip(zip_path: Path, plugin_dir: Path) -> list[Path]:
    plugin_dir.mkdir(parents=True, exist_ok=True)
    installed: list[Path] = []
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            member_path = Path(member.filename)
            if member_path.parts[:1] != ("Release",):
                continue
            output_path = plugin_dir / member_path.name
            with archive.open(member) as src, output_path.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            installed.append(output_path)
    if not installed:
        raise RuntimeError(f"No Release/* files found in {zip_path.name}.")
    return installed


def _default_debugger_roots() -> list[tuple[str, Path]]:
    roots: list[tuple[str, Path]] = []
    if DEFAULT_DBG64.is_dir():
        roots.append(("64", DEFAULT_DBG64))
    if DEFAULT_DBG32.is_dir():
        roots.append(("32", DEFAULT_DBG32))
    return roots


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dbg64-root", type=Path, default=DEFAULT_DBG64)
    parser.add_argument("--dbg32-root", type=Path, default=DEFAULT_DBG32)
    parser.add_argument("--skip-32", action="store_true", help="Only install the 64-bit plugin.")
    parser.add_argument("--skip-64", action="store_true", help="Only install the 32-bit plugin.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    targets: list[tuple[str, Path]] = []
    if not args.skip_64 and args.dbg64_root.is_dir():
        targets.append(("64", args.dbg64_root))
    if not args.skip_32 and args.dbg32_root.is_dir():
        targets.append(("32", args.dbg32_root))
    if not targets:
        discovered = ", ".join(f"{arch}:{path}" for arch, path in _default_debugger_roots())
        raise SystemExit(
            "No debugger roots found. "
            f"Checked default locations: {discovered or 'none found'}. "
            "Pass --dbg64-root/--dbg32-root explicitly if needed."
        )

    release = _pick_release()
    tag = release["tag_name"]
    print(f"Using x64dbg-automate plugin release {tag}.")

    with tempfile.TemporaryDirectory(prefix="dbgmcp-plugin-") as temp_dir:
        temp_path = Path(temp_dir)
        for arch, root in targets:
            asset = _pick_asset(release, arch)
            archive_path = temp_path / asset["name"]
            _download_asset(asset, archive_path)
            plugin_dir = root / "plugins"
            installed = _install_zip(archive_path, plugin_dir)
            print(f"[{arch}-bit] Installed {len(installed)} files into {plugin_dir}")
            for path in installed:
                print(f"  - {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
