"""Patch subprocess to suppress console windows on Windows."""

import ctypes
import subprocess as _subprocess

_ORIG_POPEN = _subprocess.Popen
_NO_WINDOW = 0x08000000


class _PatchedPopen(_ORIG_POPEN):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("creationflags", 0)
        kwargs["creationflags"] |= _NO_WINDOW
        kwargs.setdefault("stdout", _subprocess.DEVNULL)
        kwargs.setdefault("stderr", _subprocess.DEVNULL)
        super().__init__(*args, **kwargs)


def apply():
    _subprocess.Popen = _PatchedPopen
    try:
        ctypes.windll.user32.ShowWindow(
            ctypes.windll.kernel32.GetConsoleWindow(), 0
        )
    except Exception:
        pass


apply()
