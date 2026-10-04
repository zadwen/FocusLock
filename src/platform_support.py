"""Operating-system integration, isolated from the Tk event loop."""
from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path
import queue
import shutil
import signal
import subprocess
import sys
import threading

from core import IS_WINDOWS, validate_app


def run_options():
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if IS_WINDOWS else {}


class InstanceLock:
    """An OS-released file lock prevents competing timers and hosts edits."""
    def __init__(self, directory):
        directory.mkdir(parents=True, exist_ok=True)
        # Windows byte-range locks deny reads through a second handle, even
        # in the same process. Lock byte zero without reading or writing it.
        # msvcrt permits a lock range beyond EOF, including an empty file.
        self.file = (directory / "instance.lock").open("a+b", buffering=0)
        try:
            self.file.seek(0)
            if IS_WINDOWS:
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.file.close()
            raise RuntimeError("FocusLock is already running. Restore its window from the taskbar.") from exc
        except BaseException:
            self.file.close()
            raise

    def close(self):
        self.file.close()


def processes():
    if IS_WINDOWS:
        result = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True,
                                text=True, errors="replace", timeout=8, check=True, **run_options())
        for row in csv.reader(io.StringIO(result.stdout)):
            if len(row) > 1 and row[1].isdigit():
                yield int(row[1]), row[0], None
    else:
        # /proc is standard on Linux; no sudo or process-library dependency required.
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                if entry.stat().st_uid != os.getuid():
                    continue
                # exe gives the full name when the kernel's comm is truncated to 15 bytes.
                try:
                    name = Path(os.readlink(entry / "exe")).name.removesuffix(" (deleted)")
                except OSError:
                    name = (entry / "comm").read_text().strip()
                token = (entry / "stat").read_text().rsplit(")", 1)[1].split()[19]
                yield int(entry.name), name, token
            except (OSError, IndexError):
                continue


class AppBlocker:
    """One worker for the application lifetime; pause never spawns extra workers."""
    def __init__(self):
        self._guard = threading.Lock()
        self._shutdown = threading.Event()
        self._names = set()
        self._enabled = False
        self.errors = queue.Queue()
        self.count = 0
        self._last_error = ""
        self.thread = threading.Thread(target=self._loop, name="FocusLock-blocker", daemon=True)
        self.thread.start()

    def configure(self, names, enabled):
        valid = {validate_app(n).casefold() for n in names}
        with self._guard:
            self._names, self._enabled = valid, enabled

    def _error(self, message):
        if message != self._last_error:
            self.errors.put(message)
            self._last_error = message

    def _loop(self):
        while not self._shutdown.is_set():
            with self._guard:
                enabled = self._enabled
            if enabled:
                try:
                    for pid, name, token in processes():
                        if pid in (os.getpid(), os.getppid()):
                            continue
                        with self._guard:
                            if not self._enabled or name.casefold() not in self._names:
                                continue
                            try:
                                validate_app(name)
                                if IS_WINDOWS:
                                    subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                                                   capture_output=True, timeout=3, check=True, **run_options())
                                else:
                                    # Recheck process identity to avoid killing a reused PID.
                                    current = (Path("/proc") / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()[19]
                                    if current != token:
                                        continue
                                    os.kill(pid, signal.SIGKILL)
                                self.count += 1
                            except (ProcessLookupError, FileNotFoundError):
                                pass
                            except (OSError, subprocess.SubprocessError, ValueError) as exc:
                                self._error(f"Could not close {name}: {exc}")
                except (OSError, subprocess.SubprocessError) as exc:
                    self._error(f"App blocking failed: {exc}")
            self._shutdown.wait(2)

    def close(self):
        self.configure([], False)
        self._shutdown.set()
        self.thread.join(timeout=9)


REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def launch_command():
    if getattr(sys, "frozen", False):
        return [sys.executable]
    executable = Path(sys.executable)
    if IS_WINDOWS and executable.with_name("pythonw.exe").exists():
        executable = executable.with_name("pythonw.exe")
    return [str(executable), str(Path(__file__).with_name("focuslock.py").resolve())]


def autostart_path():
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "autostart/focuslock.desktop"


def startup_enabled():
    if not IS_WINDOWS:
        return autostart_path().exists()
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY) as key:
            winreg.QueryValueEx(key, "FocusLock")
        return True
    except FileNotFoundError:
        return False


def desktop_quote(arg):
    # Freedesktop Exec escaping has both desktop-entry and shell-style layers.
    escaped = arg.replace("\\", "\\\\\\\\").replace('"', '\\\\"').replace("`", "\\\\`").replace("$", "\\\\$").replace("%", "%%")
    return '"' + escaped + '"'


def set_startup(enabled):
    if IS_WINDOWS:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_KEY) as key:
            if enabled:
                winreg.SetValueEx(key, "FocusLock", 0, winreg.REG_SZ, subprocess.list2cmdline(launch_command()))
            else:
                try:
                    winreg.DeleteValue(key, "FocusLock")
                except FileNotFoundError:
                    pass
    else:
        path = autostart_path()
        if enabled:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("[Desktop Entry]\nType=Application\nName=FocusLock\nTerminal=false\nExec=" +
                            " ".join(desktop_quote(s) for s in launch_command()) + "\n", encoding="utf-8")
        else:
            path.unlink(missing_ok=True)


def notify(title, message):
    try:
        if IS_WINDOWS:
            # Single quotes must be doubled for PowerShell string literals.
            title, message = title.replace("'", "''"), message.replace("'", "''")
            script = ("Add-Type -AssemblyName System.Windows.Forms;"
                      "$n=New-Object System.Windows.Forms.NotifyIcon;"
                      "$n.Icon=[System.Drawing.SystemIcons]::Information;$n.Visible=$true;"
                      f"$n.ShowBalloonTip(4000,'{title}','{message}',0);Start-Sleep -Seconds 5;$n.Dispose()")
            subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **run_options())
        elif shutil.which("notify-send"):
            subprocess.Popen(["notify-send", "--app-name=FocusLock", title, message],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass
