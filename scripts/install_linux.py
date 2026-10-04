"""Install the source app for this user; no sudo or system modifications."""
from pathlib import Path
import os
import shutil
import stat
import sys

if sys.platform != "linux":
    raise SystemExit("This installer is for Linux. On Windows, download FocusLock.exe.")
if os.getuid() == 0:
    raise SystemExit("Run this installer as your regular user, without sudo.")
try:
    import tkinter
except ImportError:
    raise SystemExit("Install tkinter first: sudo apt install python3-tk (Ubuntu/Zorin/Debian).")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from platform_support import desktop_quote

install = Path.home() / ".local/share/focuslock"
bin_dir = Path.home() / ".local/bin"
applications = Path.home() / ".local/share/applications"
for directory in (install, bin_dir, applications):
    directory.mkdir(parents=True, exist_ok=True)
for source in (ROOT / "src").glob("*.py"):
    shutil.copy2(source, install / source.name)
shutil.copy2(ROOT / "assets/focuslock.svg", install / "focuslock.svg")
# A small Python launcher preserves paths containing spaces or quotes.
launcher = bin_dir / "focuslock"
launcher.write_text("#!/usr/bin/env python3\nimport os\nos.execv(" + repr(sys.executable) + ", " +
                    repr([sys.executable, str(install / "focuslock.py")]) + " + __import__('sys').argv[1:])\n")
launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
entry = ("[Desktop Entry]\nType=Application\nName=FocusLock\nComment=Make room for deep work\n"
         "Exec=" + desktop_quote(sys.executable) + " " + desktop_quote(str(install / "focuslock.py")) +
         "\nIcon=" + str(install / "focuslock.svg") + "\nTerminal=false\nCategories=Utility;Education;\nStartupWMClass=FocusLock\n")
(applications / "focuslock.desktop").write_text(entry, encoding="utf-8")
print("Installed. Open FocusLock from your applications menu, or run:")
print(launcher)
