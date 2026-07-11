"""
FocusLock — Release Packaging

Takes the Nuitka build output and packages it into a clean distribution folder
ready for shipping. Optionally creates a zip archive.

Usage:
    python scripts/release.py              # Package latest build
    python scripts/release.py --zip        # Package + create zip
    python scripts/release.py --verify     # Verify build output exists
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from version import APP_NAME, VERSION, ROOT

# ── Paths ────────────────────────────────────────────────────────────────────
BUILD_DIR = ROOT / "build" / "nuitka_output"
DIST_DIR = ROOT / "dist"
RELEASE_NAME = f"{APP_NAME}-{VERSION}"


def find_build_output() -> Path | None:
    """Locate the Nuitka output directory containing FocusLock.exe."""
    exe_name = f"{APP_NAME}.exe"
    if not BUILD_DIR.exists():
        return None
    for d in BUILD_DIR.iterdir():
        if d.is_dir() and (d / exe_name).exists():
            return d
    return None


def create_release(build_dir: Path) -> Path:
    """Copy build output to a clean release folder."""
    release_dir = DIST_DIR / RELEASE_NAME
    if release_dir.exists():
        shutil.rmtree(release_dir)

    # Copy the entire Nuitka output
    shutil.copytree(build_dir, release_dir)

    # Add supplementary files
    files_to_add = {
        "README.txt": _readme_content(),
        "LICENSE": (ROOT / "LICENSE").read_text(encoding="utf-8") if (ROOT / "LICENSE").exists() else "",
        "CHANGELOG.md": (ROOT / "CHANGELOG.md").read_text(encoding="utf-8") if (ROOT / "CHANGELOG.md").exists() else "",
        "Install.bat": _install_bat(),
        "Uninstall.bat": _uninstall_bat(),
    }

    for name, content in files_to_add.items():
        (release_dir / name).write_text(content, encoding="utf-8")

    return release_dir


def create_zip(release_dir: Path) -> Path:
    """Create a zip archive of the release folder."""
    zip_path = DIST_DIR / f"{RELEASE_NAME}.zip"
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in release_dir.rglob("*"):
            arcname = file.relative_to(DIST_DIR)
            zf.write(file, arcname)

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"  Created {zip_path.name} ({size_mb:.1f} MB)")
    return zip_path


def verify() -> bool:
    """Verify the build output exists and is valid."""
    build_dir = find_build_output()
    if not build_dir:
        print(f"\n  [FAIL] No build output found at {BUILD_DIR.relative_to(ROOT)}/")
        print(f"  Run 'python scripts/build.py' first.")
        return False

    exe = build_dir / f"{APP_NAME}.exe"
    size_mb = exe.stat().st_size / (1024 * 1024)
    print(f"\n  Build output found:")
    print(f"    {exe.relative_to(ROOT)} ({size_mb:.1f} MB)")

    # Count files in output
    file_count = sum(1 for _ in build_dir.rglob("*") if _.is_file())
    total_size = sum(f.stat().st_size for f in build_dir.rglob("*") if f.is_file())
    print(f"    {file_count} files, {total_size / (1024*1024):.1f} MB total")

    return True


# ── Content generators ───────────────────────────────────────────────────────
def _readme_content() -> str:
    return f"""{APP_NAME} v{VERSION}
{'=' * 40}

Quick Start:
  1. Run {APP_NAME}.exe
  2. Or double-click Install.bat for a Desktop shortcut

Features:
  - Pomodoro timer with work/break/long-break cycles
  - App and website blocking during focus sessions
  - Customizable durations and presets
  - Sound and notification alerts
  - Dark and Light themes
  - Session statistics and streak tracking
  - Password protection

System Requirements:
  - Windows 10 or later
  - No Python installation required

Uninstall:
  1. Run Uninstall.bat to remove the Desktop shortcut
  2. Delete this entire folder

Version: {VERSION}
"""


def _install_bat() -> str:
    return f"""@echo off
echo ==========================================
echo  {APP_NAME} v{VERSION} - Installer
echo ==========================================
echo.
echo Creating Desktop shortcut...

set SCRIPT_DIR=%~dp0
set SHORTCUT_PATH=%USERPROFILE%\\Desktop\\{APP_NAME}.lnk
set TARGET=%SCRIPT_DIR%{APP_NAME}.exe

powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT_PATH%'); $s.TargetPath = '%TARGET%'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.Save()"

echo.
echo Desktop shortcut created!
echo You can now run {APP_NAME} from your Desktop.
echo.
pause
"""


def _uninstall_bat() -> str:
    return f"""@echo off
echo Uninstalling {APP_NAME}...

del "%USERPROFILE%\\Desktop\\{APP_NAME}.lnk" 2>nul

echo Desktop shortcut removed.
echo You can now delete this folder: %~dp0
echo.
pause
"""


# ── Main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description=f"Package {APP_NAME} for release")
    parser.add_argument("--zip", action="store_true",
                        help="Also create a zip archive")
    parser.add_argument("--verify", action="store_true",
                        help="Verify build output exists")
    args = parser.parse_args()

    print(f"\n  {APP_NAME} v{VERSION} — Release Packaging\n")

    if args.verify:
        ok = verify()
        sys.exit(0 if ok else 1)

    build_dir = find_build_output()
    if not build_dir:
        print(f"  [FAIL] No build output found.")
        print(f"  Run: python scripts/build.py")
        sys.exit(1)

    print(f"  Found build: {build_dir.relative_to(ROOT)}")

    release_dir = create_release(build_dir)
    file_count = sum(1 for _ in release_dir.rglob("*") if _.is_file())
    total_size = sum(f.stat().st_size for f in release_dir.rglob("*") if f.is_file())
    print(f"  Release folder: {release_dir.relative_to(ROOT)}/")
    print(f"  {file_count} files, {total_size / (1024*1024):.1f} MB")

    if args.zip:
        create_zip(release_dir)

    print()


if __name__ == "__main__":
    main()
