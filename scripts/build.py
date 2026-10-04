"""Build on the target OS: python scripts/build.py."""
from pathlib import Path
import subprocess
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
if sys.platform not in ("win32", "linux"):
    raise SystemExit("Build on Windows or Linux.")
if sys.platform == "linux" and platform.machine().lower() not in ("x86_64", "amd64"):
    raise SystemExit("The packaged Linux binary targets x86-64. On ARM, run from source.")
subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=ROOT, check=True)
command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile",
           "--name", "FocusLock" if sys.platform == "win32" else "FocusLock-linux-x86_64",
           "--paths", str(ROOT / "src")]
if sys.platform == "win32":
    command.append("--windowed")
command.append(str(ROOT / "src/focuslock.py"))
subprocess.run(command, cwd=ROOT, check=True)
print("Build complete. See the dist folder.")
