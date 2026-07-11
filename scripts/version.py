"""
FocusLock — Version Management

Single source of truth for the application version.
All other files (constants.py, build scripts, CI, installer)
read from this module.

Usage:
    python scripts/version.py              # prints current version
    python scripts/version.py --bump patch # 3.0.0 -> 3.0.1
    python scripts/version.py --bump minor # 3.0.0 -> 3.1.0
    python scripts/version.py --bump major # 3.0.0 -> 4.0.0
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# ── Canonical version ────────────────────────────────────────────────────────
VERSION = "3.0.0"
APP_NAME = "FocusLock"
COMPANY = "zadwen"
DESCRIPTION = "Focus and productivity app — Pomodoro timer with app and website blocking"
COPYRIGHT = "Copyright (c) 2026 zadwen"
LICENSE_ID = "MIT"

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
CONSTANTS_FILE = ROOT / "src" / "focuslock" / "constants.py"


def get_version_tuple() -> tuple[int, int, int]:
    parts = VERSION.split(".")
    return (int(parts[0]), int(parts[1]), int(parts[2]))


def get_version_hex() -> str:
    """Return version as dot-separated for Nuitka --file-version: 3.0.0.0"""
    major, minor, patch = get_version_tuple()
    return f"{major}.{minor}.{patch}.0"


def bump(part: str) -> str:
    major, minor, patch = get_version_tuple()
    if part == "major":
        return f"{major + 1}.0.0"
    elif part == "minor":
        return f"{major}.{minor + 1}.0"
    elif part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"Unknown bump target: {part}")


def update_version(new_version: str) -> None:
    """Write new version to this file and to src/focuslock/constants.py."""
    # 1. Update this file
    text = ROOT.joinpath("scripts", "version.py").read_text(encoding="utf-8")
    text = re.sub(
        r'^VERSION\s*=\s*"[^"]*"$',
        f'VERSION = "{new_version}"',
        text,
        flags=re.MULTILINE,
    )
    ROOT.joinpath("scripts", "version.py").write_text(text, encoding="utf-8")

    # 2. Update constants.py
    ct = CONSTANTS_FILE.read_text(encoding="utf-8")
    ct = re.sub(
        r'^VERSION\s*=\s*"[^"]*"$',
        f'VERSION = "{new_version}"',
        ct,
        flags=re.MULTILINE,
    )
    CONSTANTS_FILE.write_text(ct, encoding="utf-8")

    print(f"Version updated: {VERSION} -> {new_version}")
    print(f"  scripts/version.py")
    print(f"  {CONSTANTS_FILE.relative_to(ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Version management")
    parser.add_argument("--bump", choices=["major", "minor", "patch"],
                        help="Bump version part")
    args = parser.parse_args()

    if args.bump:
        new = bump(args.bump)
        update_version(new)
    else:
        print(VERSION)


if __name__ == "__main__":
    main()
