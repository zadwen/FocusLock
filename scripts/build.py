"""
FocusLock — Build Script (Nuitka)

Compiles the application into a standalone Windows executable.

Usage:
    python scripts/build.py                # Development build
    python scripts/build.py --release      # Optimized release build
    python scripts/build.py --debug        # Debug build with debug info

Requires: Nuitka, a C compiler (MSVC Build Tools or MinGW64).
Nuitka auto-downloads MinGW64 if no compiler is found.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

# ── Version (single source of truth) ─────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent))
from version import (
    APP_NAME, VERSION, COMPANY, DESCRIPTION, COPYRIGHT,
    get_version_hex, ROOT,
)

# ── Paths ────────────────────────────────────────────────────────────────────
SRC_DIR = ROOT / "src"
ENTRY_POINT = SRC_DIR / "focuslock_app.py"
ASSETS_DIR = ROOT / "assets"
BUILD_DIR = ROOT / "build"
DIST_DIR = ROOT / "dist"
OUTPUT_DIR = BUILD_DIR / "nuitka_output"

# ── Icon ─────────────────────────────────────────────────────────────────────
ICON = ASSETS_DIR / "icon.ico"


# ═════════════════════════════════════════════════════════════════════════════
# Compiler detection
# ═════════════════════════════════════════════════════════════════════════════
def detect_compiler() -> str:
    """Return 'msvc', 'mingw64', or 'none'."""
    # Check MSVC
    try:
        result = subprocess.run(
            ["cl.exe"], capture_output=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if result.returncode == 0 or b"Microsoft" in result.stderr:
            return "msvc"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Check MinGW64 in PATH
    try:
        result = subprocess.run(
            ["gcc", "--version"], capture_output=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if result.returncode == 0 and b"mingw" in result.stdout.lower():
            return "mingw64"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Check Nuitka cache for auto-downloaded gcc
    nuitka_cache = Path.home() / "AppData" / "Local" / "Nuitka" / "Nuitka" / "Cache" / "downloads" / "gcc"
    if nuitka_cache.exists():
        for gcc in nuitka_cache.rglob("gcc.exe"):
            gcc_dir = gcc.parent
            os.environ["PATH"] = f"{gcc_dir};{os.environ.get('PATH', '')}"
            return "mingw64 (cached)"

    return "none"


# ═════════════════════════════════════════════════════════════════════════════
# Build
# ═════════════════════════════════════════════════════════════════════════════
def build_nuitka(mode: str = "release") -> None:
    """Run Nuitka compilation."""

    compiler = detect_compiler()
    print(f"\n  Compiler:     {compiler}")
    print(f"  Python:       {sys.version.split()[0]}")
    print(f"  Nuitka:       via {sys.executable}")
    print(f"  Entry point:  {ENTRY_POINT.relative_to(ROOT)}")
    print(f"  Output:       {OUTPUT_DIR.relative_to(ROOT)}/")
    print()

    # ── Base arguments ───────────────────────────────────────────────────
    args = [
        sys.executable, "-m", "nuitka",

        # Standalone mode — produces a folder with exe + all dependencies
        "--standalone",

        # Output
        f"--output-dir={BUILD_DIR / 'nuitka_output'}",
        f"--output-filename={APP_NAME}.exe",

        # Windows-specific
        "--windows-console-mode=disable",

        # Plugin: PySide6 handling (Qt plugins, translations, etc.)
        "--enable-plugin=pyside6",

        # Module exclusion (reduce bundle size)
        "--nofollow-import-to=tkinter",
        "--nofollow-import-to=matplotlib",
        "--nofollow-import-to=numpy",
        "--nofollow-import-to=pandas",
        "--nofollow-import-to=pytest",
        "--nofollow-import-to=unittest",
        "--nofollow-import-to=xmlrpc",
        "--nofollow-import-to=pydoc",
        "--nofollow-import-to=doctest",
        "--nofollow-import-to=lib2to3",

        # Include data directories
        f"--include-data-dir={ASSETS_DIR}=assets",

        # Python flags
        "--python-flag=-S",

        # Verbose
        "--verbose",

        # Entry point
        str(ENTRY_POINT),
    ]

    # ── Mode-specific flags ──────────────────────────────────────────────
    if mode == "release":
        args.extend([
            # Compiler optimizations
            "--lto=yes",
            "--assume-yes-for-downloads",

            # Windows version metadata
            f"--file-version={get_version_hex()}",
            f"--product-version={VERSION}",
            f"--company-name={COMPANY}",
            f"--product-name={APP_NAME}",
            f"--file-description={DESCRIPTION}",
            f"--copyright={COPYRIGHT}",
        ])
        # Icon
        if ICON.exists():
            args.append(f"--windows-icon-from-ico={ICON}")

    elif mode == "debug":
        args.extend([
            "--debug",
            "--debugger",
            "--no-progressbar",
        ])

    elif mode == "development":
        args.extend([
            "--assume-yes-for-downloads",
        ])
        if ICON.exists():
            args.append(f"--windows-icon-from-ico={ICON}")

    # ── Run ──────────────────────────────────────────────────────────────
    print(f"  Command ({len(args)} args):")
    print(f"    {' '.join(args[:8])}")
    print(f"    ... ({len(args) - 8} more)")
    print()

    start = time.time()
    result = subprocess.run(args, cwd=str(ROOT))
    elapsed = time.time() - start

    if result.returncode != 0:
        print(f"\n  [FAIL] Nuitka exited with code {result.returncode}")
        sys.exit(result.returncode)

    print(f"\n  Build completed in {elapsed:.1f}s")

    # ── Locate output ────────────────────────────────────────────────────
    exe_name = f"{APP_NAME}.exe"
    # Nuitka creates output in: build/nuitka_output/<entry_name>.dir/
    # or directly in build/nuitka_output/ depending on version
    exe_path = None

    # Check if exe is directly in output dir
    direct = OUTPUT_DIR / exe_name
    if direct.exists():
        exe_path = direct
    else:
        # Check subdirectories (<entry_name>.dir/)
        if OUTPUT_DIR.exists():
            for d in OUTPUT_DIR.iterdir():
                if d.is_dir():
                    candidate = d / exe_name
                    if candidate.exists():
                        exe_path = candidate
                        break

    if exe_path:
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"  {exe_name}  ({size_mb:.1f} MB)")
        print(f"  Location: {exe_path.relative_to(ROOT)}")
    else:
        print(f"  [WARN] {exe_name} not found in expected location")
        print(f"  Checking OUTPUT_DIR: {OUTPUT_DIR}")
        if OUTPUT_DIR.exists():
            for item in OUTPUT_DIR.rglob("*.exe"):
                print(f"    Found: {item.relative_to(ROOT)}")

    return exe_path


# ═════════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════════
def main() -> None:
    parser = argparse.ArgumentParser(description=f"Build {APP_NAME} v{VERSION}")
    parser.add_argument("--release", action="store_true",
                        help="Optimized release build (default)")
    parser.add_argument("--debug", action="store_true",
                        help="Debug build with symbols")
    parser.add_argument("--development", action="store_true",
                        help="Development build (fast, minimal optimization)")
    args = parser.parse_args()

    width = 60
    print("\n" + "=" * width)
    print(f"  {APP_NAME} v{VERSION} — Build System (Nuitka)")
    print("=" * width)

    if not ENTRY_POINT.exists():
        print(f"\n  [FAIL] Entry point not found: {ENTRY_POINT}")
        sys.exit(1)

    mode = "release"
    if args.debug:
        mode = "debug"
    elif args.development:
        mode = "development"

    print(f"\n  Mode: {mode}")

    compiler = detect_compiler()
    if compiler == "none":
        print("\n  [INFO] No C compiler detected.")
        print("  Nuitka will attempt to download MinGW64 automatically.")
        print("  Alternatively, install Visual Studio Build Tools:")
        print("  https://visualstudio.microsoft.com/visual-cpp-build-tools/\n")

    build_nuitka(mode)


if __name__ == "__main__":
    main()
