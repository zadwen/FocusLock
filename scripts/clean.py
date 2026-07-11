"""
FocusLock — Clean Script

Removes all build artifacts, caches, and temporary files.

Usage:
    python scripts/clean.py           # Clean build artifacts
    python scripts/clean.py --all     # Clean everything including __pycache__
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from version import APP_NAME, ROOT

# ── Directories to clean ─────────────────────────────────────────────────────
BUILD_DIRS = [
    ROOT / "build",
    ROOT / "dist",
]

CACHE_DIRS = [
    ROOT / ".mypy_cache",
    ROOT / ".pytest_cache",
]


def clean(Include_pycache: bool = False) -> None:
    """Remove build artifacts and caches."""
    removed = 0

    for d in BUILD_DIRS:
        if d.is_dir():
            shutil.rmtree(d)
            print(f"  Removed {d.relative_to(ROOT)}/")
            removed += 1

    for d in CACHE_DIRS:
        if d.is_dir():
            shutil.rmtree(d)
            print(f"  Removed {d.relative_to(ROOT)}/")
            removed += 1

    if Include_pycache:
        for cache in ROOT.rglob("__pycache__"):
            shutil.rmtree(cache)
            print(f"  Removed {cache.relative_to(ROOT)}/")
            removed += 1

        for pyc in ROOT.rglob("*.pyc"):
            pyc.unlink()
        for pyo in ROOT.rglob("*.pyo"):
            pyo.unlink()
        print("  Cleaned .pyc/.pyo files")
        removed += 1

    if removed == 0:
        print("  Nothing to clean.")
    else:
        print(f"\n  Cleaned {removed} item(s).")


def main() -> None:
    parser = argparse.ArgumentParser(description=f"Clean {APP_NAME} build artifacts")
    parser.add_argument("--all", action="store_true",
                        help="Also remove __pycache__ directories")
    args = parser.parse_args()

    print(f"\n  {APP_NAME} — Clean\n")
    clean(Include_pycache=args.all)


if __name__ == "__main__":
    main()
