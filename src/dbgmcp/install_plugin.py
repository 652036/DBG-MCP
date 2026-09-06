"""Install x64dbg-automate plugin assets into local debugger directories."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from dbgmcp.cli import discover_debugger_roots


GITHUB_RELEASES_API = "https://api.github.com/repos/dariushoule/x64dbg-automate/releases"


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


def _compat_version() -> str:
    from x64dbg_automate import COMPAT_VERSION

    return COMPAT_VERSION


def _pick_release() -> dict:
    compat_version = _compat_version()
    releases = _fetch_json(GITHUB_RELEASES_API)
    for release in releases:
        tag_name = str(release.get("tag_name", ""))
        if compat_version in tag_name and not release.get("draft") and not release.get("prerelease"):
            return release
    raise RuntimeError(
        f"Could not find a published x64dbg-automate release matching compat version {compat_version!r}."
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


def resolve_install_targets(
    dbg64_root: Path | None = None,
    dbg32_root: Path | None = None,
    skip_32: bool = False,
    skip_64: bool = False,
) -> list[tuple[str, Path]]:
    targets: list[tuple[str, Path]] = []
    have_64 = False
    have_32 = False

    if not skip_64 and dbg64_root is not None:
        if not dbg64_root.is_dir():
            raise SystemExit(f"64-bit debugger root not found: {dbg64_root}")
        targets.append(("64", dbg64_root))
        have_64 = True
    if not skip_32 and dbg32_root is not None:
        if not dbg32_root.is_dir():
            raise SystemExit(f"32-bit debugger root not found: {dbg32_root}")
        targets.append(("32", dbg32_root))
        have_32 = True

    if (not skip_64 and not have_64) or (not skip_32 and not have_32):
        for arch, root in discover_debugger_roots():
            if arch == "64" and not skip_64 and not have_64:
                targets.append((arch, root))
                have_64 = True
            elif arch == "32" and not skip_32 and not have_32:
                targets.append((arch, root))
                have_32 = True
            if (skip_64 or have_64) and (skip_32 or have_32):
                break

    if not targets:
        raise SystemExit(
            "No debugger roots found. "
            "Set X64DBG_PATH to your debugger executable or pass --dbg64-root/--dbg32-root."
        )
    return targets


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dbg64-root", type=Path, default=None)
    parser.add_argument("--dbg32-root", type=Path, default=None)
    parser.add_argument("--skip-32", action="store_true", help="Only install the 64-bit plugin.")
    parser.add_argument("--skip-64", action="store_true", help="Only install the 32-bit plugin.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    targets = resolve_install_targets(
        dbg64_root=args.dbg64_root,
        dbg32_root=args.dbg32_root,
        skip_32=args.skip_32,
        skip_64=args.skip_64,
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
