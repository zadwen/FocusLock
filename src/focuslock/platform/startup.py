"""Windows startup registry integration."""

import os
import sys
import winreg

from ..constants import APP_NAME

REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def set_startup(enable, script_path=None):
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_SET_VALUE
        )
        if enable:
            if getattr(sys, "frozen", False):
                path = sys.executable
            else:
                # Point to the actual entry-point script, not this module
                app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                entry = os.path.join(app_dir, "focuslock_app.py")
                path = f'pythonw "{entry}"'
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, path)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


def startup_is_on():
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_READ
        )
        winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        return True
    except Exception:
        return False
