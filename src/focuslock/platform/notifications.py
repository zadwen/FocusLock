"""Windows balloon / toast notifications.

Uses Qt's ``QSystemTrayIcon.showMessage`` when a tray icon is available,
falling back to a PowerShell-based ``NotifyIcon`` otherwise.
"""

import subprocess


def notify(title, message, tray_icon=None):
    """Show a Windows notification.

    If *tray_icon* (a ``QSystemTrayIcon``) is provided and visible, the
    notification is sent through it.  Otherwise a lightweight PowerShell
    script is spawned.
    """
    if tray_icon is not None and tray_icon.isVisible():
        tray_icon.showMessage(title, message)
        return

    safe_title = title.replace("'", "''")
    safe_msg = message.replace("'", "''")
    script = (
        "Add-Type -AssemblyName System.Windows.Forms;"
        "$n=New-Object System.Windows.Forms.NotifyIcon;"
        "$n.Icon=[System.Drawing.SystemIcons]::Information;"
        "$n.Visible=$true;"
        f"$n.ShowBalloonTip(4000,'{safe_title}','{safe_msg}',"
        "[System.Windows.Forms.ToolTipIcon]::None);"
        "Start-Sleep -s 5;$n.Dispose()"
    )
    try:
        subprocess.Popen(
            ["powershell", "-WindowStyle", "Hidden", "-Command", script]
        )
    except Exception:
        pass
