#!/usr/bin/env python3
"""Bump the NeXroll version everywhere it lives, in one shot.

Usage:
    python NeXroll/scripts/bump_version.py 2.0.0-beta.2

Updates:
    NeXroll/version.py              __version__ = '...'   (file has a UTF-8 BOM)
    NeXroll/backend/version.py      __version__ = '...'
    Releases/installer.nsi          !define APP_VERSION "..."
    NeXroll/frontend/package.json   "version": "..."

The version history shows these drifting apart when bumped by hand (the
frontend package.json sat at 1.12.0 through several releases). Run this
instead of editing the files individually.
"""
import json
import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.\-]+)?$")


def _sub_or_die(pattern: str, repl: str, text: str, path: pathlib.Path) -> str:
    new_text, n = re.subn(pattern, repl, text, count=1, flags=re.MULTILINE)
    if n != 1:
        sys.exit(f"ERROR: pattern {pattern!r} not found in {path} — file format changed?")
    return new_text


def bump_python_version(path: pathlib.Path, version: str) -> None:
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    text = _sub_or_die(r"^__version__\s*=\s*['\"][^'\"]+['\"]",
                       f"__version__ = '{version}'", text, path)
    path.write_bytes((("﻿" if bom else "") + text).encode("utf-8"))


def bump_nsi(path: pathlib.Path, version: str) -> None:
    text = path.read_text(encoding="utf-8-sig")
    text = _sub_or_die(r'^!define APP_VERSION "[^"]+"',
                       f'!define APP_VERSION "{version}"', text, path)
    path.write_text(text, encoding="utf-8")


def bump_package_json(path: pathlib.Path, version: str) -> None:
    # Regex (not json.dump) so formatting/key order stay untouched.
    text = path.read_text(encoding="utf-8")
    text = _sub_or_die(r'^(\s*)"version":\s*"[^"]+"',
                       rf'\g<1>"version": "{version}"', text, path)
    path.write_text(text, encoding="utf-8")
    json.loads(path.read_text(encoding="utf-8"))  # sanity: still valid JSON


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    version = sys.argv[1].lstrip("v")
    if not VERSION_RE.match(version):
        sys.exit(f"ERROR: {version!r} doesn't look like a semver version (e.g. 2.0.0-beta.2)")

    targets = [
        (REPO_ROOT / "NeXroll" / "version.py", bump_python_version),
        (REPO_ROOT / "NeXroll" / "backend" / "version.py", bump_python_version),
        (REPO_ROOT / "Releases" / "installer.nsi", bump_nsi),
        (REPO_ROOT / "NeXroll" / "frontend" / "package.json", bump_package_json),
    ]
    for path, fn in targets:
        if not path.exists():
            sys.exit(f"ERROR: {path} not found — run from the repo checkout")
        fn(path, version)
        print(f"  bumped {path.relative_to(REPO_ROOT)}")
    print(f"All files now at {version}.")
    print("Reminder: Releases/installer.nsi is gitignored — stage it with: git add -f Releases/installer.nsi")


if __name__ == "__main__":
    main()
