import sys
import os
import json
import time
import threading
import subprocess
import hashlib
import datetime
import winreg
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from pathlib import Path
try:
    from PIL import Image, ImageDraw
    import pystray
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False

# --------------------------------------------------
# Config paths
# --------------------------------------------------
APP_NAME = "FocusLock"
VERSION = "1.1.0"

DATA_DIR = Path(os.getenv("APPDATA", ".")) / "FocusLock"
DATA_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = DATA_DIR / "config.json"
STATS_FILE = DATA_DIR / "stats.json"

# default apps to block - user can edit these in the UI
DEFAULT_APPS = [
    "steam.exe",
    "steamwebhelper.exe",
    "discord.exe",
    "EpicGamesLauncher.exe",
    "Battle.net.exe",
    "LeagueClient.exe",
    "TwitchUI.exe",
    "Spotify.exe",
]

DEFAULT_SITES = [
    "youtube.com",
    "twitter.com",
    "reddit.com",
    "twitch.tv",
    "instagram.com",
    "tiktok.com",
    "facebook.com",
]

POMODORO_PRESETS = {
    "Classic (25/5)": (25, 5),
    "Long Focus (50/10)": (50, 10),
    "Short Burst (15/3)": (15, 3),
    "Deep Work (90/20)": (90, 20),
}

# TODO: add more presets in next version maybe

# --------------------------------------------------
# Config helpers
# --------------------------------------------------
def load_config():
    defaults = {
        "blocklist": DEFAULT_APPS,
        "website_blocklist": DEFAULT_SITES,
        "password_hash": "",
        "block_websites": False,
        "pomodoro_work": 25,
        "pomodoro_break": 5,
        "theme": "dark",
        "run_on_startup": False,
        "parent_password_hash": "",
        "session_name": "",
        "notify_break": True,
    }
    if CONFIG_FILE.exists():
        try:
            saved = json.loads(CONFIG_FILE.read_text())
            defaults.update(saved)
        except Exception:
            pass
    return defaults


def save_config(cfg):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


def load_stats():
    defaults = {
        "total_sessions": 0,
        "total_minutes": 0,
        "sessions_by_date": {},
        "current_streak": 0,
        "longest_streak": 0,
        "last_session_date": "",
    }
    if STATS_FILE.exists():
        try:
            saved = json.loads(STATS_FILE.read_text())
            defaults.update(saved)
        except Exception:
            pass
    return defaults


def save_stats(stats):
    STATS_FILE.write_text(json.dumps(stats, indent=2))


def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()


# --------------------------------------------------
# Startup registry
# --------------------------------------------------
STARTUP_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

def set_startup(enabled):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_KEY, 0, winreg.KEY_SET_VALUE)
        if enabled:
            exe_path = sys.executable if getattr(sys, "frozen", False) else f'pythonw "{os.path.abspath(__file__)}"'
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"Startup registry error: {e}")
        return False


def is_startup_enabled():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_KEY, 0, winreg.KEY_READ)
        winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False
    except Exception:
        return False


# --------------------------------------------------
# App blocker
# --------------------------------------------------
class AppBlocker:
    def __init__(self, blocklist):
        self.blocklist = [b.lower() for b in blocklist]
        self._running = False
        self._thread = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            self._kill_blocked()
            time.sleep(2)

    def _kill_blocked(self):
        try:
            out = subprocess.run(
                ["tasklist", "/fo", "csv", "/nh"],
                capture_output=True, text=True, timeout=5
            ).stdout
            for line in out.splitlines():
                parts = line.strip().strip('"').split('","')
                if not parts:
                    continue
                name = parts[0].lower()
                if name in self.blocklist:
                    pid = parts[1] if len(parts) > 1 else None
                    if pid:
                        subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
        except Exception:
            pass


# --------------------------------------------------
# Website blocker (hosts file)
# --------------------------------------------------
HOSTS = Path(r"C:\Windows\System32\drivers\etc\hosts")
MARKER_START = "# FocusLock-START"
MARKER_END = "# FocusLock-END"


def block_websites(domains):
    try:
        content = HOSTS.read_text(encoding="utf-8")
        content = _strip_fl_block(content)
        block = f"\n{MARKER_START}\n"
        for d in domains:
            block += f"127.0.0.1 {d}\n127.0.0.1 www.{d}\n"
        block += f"{MARKER_END}\n"
        HOSTS.write_text(content + block, encoding="utf-8")
        return True
    except PermissionError:
        return False


def unblock_websites():
    try:
        content = HOSTS.read_text(encoding="utf-8")
        HOSTS.write_text(_strip_fl_block(content), encoding="utf-8")
        return True
    except Exception:
        return False


def _strip_fl_block(content):
    lines, inside = [], False
    for line in content.splitlines():
        if MARKER_START in line:
            inside = True
            continue
        if MARKER_END in line:
            inside = False
            continue
        if not inside:
            lines.append(line)
    return "\n".join(lines)


# --------------------------------------------------
# Pomodoro timer
# --------------------------------------------------
class PomodoroTimer:
    def __init__(self, work_min, break_min, on_tick=None, on_phase_change=None):
        self.work_sec = work_min * 60
        self.break_sec = break_min * 60
        self.on_tick = on_tick
        self.on_phase_change = on_phase_change
        self._remaining = self.work_sec
        self._phase = "work"
        self._running = False
        self._thread = None
        self.cycles = 0

    @property
    def phase(self):
        return self._phase

    @property
    def remaining(self):
        return self._remaining

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def pause(self):
        self._running = False

    def reset(self):
        self._running = False
        self._phase = "work"
        self._remaining = self.work_sec
        self.cycles = 0
        if self.on_tick:
            self.on_tick(self._remaining, self._phase)

    def _loop(self):
        while self._running and self._remaining > 0:
            time.sleep(1)
            if not self._running:
                break
            self._remaining -= 1
            if self.on_tick:
                self.on_tick(self._remaining, self._phase)
        if self._running and self._remaining <= 0:
            self._switch()

    def _switch(self):
        if self._phase == "work":
            self.cycles += 1
            self._phase = "break"
            self._remaining = self.break_sec
        else:
            self._phase = "work"
            self._remaining = self.work_sec
        if self.on_phase_change:
            self.on_phase_change(self._phase, self.cycles)
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()


# --------------------------------------------------
# System tray icon (optional)
# --------------------------------------------------
def make_tray_icon():
    # simple purple lock icon drawn with PIL
    img = Image.new("RGB", (64, 64), color="#0f0f13")
    d = ImageDraw.Draw(img)
    d.ellipse([16, 4, 48, 36], outline="#6c63ff", width=5)
    d.rectangle([10, 28, 54, 58], fill="#6c63ff")
    d.ellipse([26, 36, 38, 48], fill="white")
    return img


# --------------------------------------------------
# Notification helper
# --------------------------------------------------
def notify(title, message):
    # uses windows toasts via powershell - no extra lib needed
    # a bit hacky but works fine
    script = f"""
    Add-Type -AssemblyName System.Windows.Forms
    $notify = New-Object System.Windows.Forms.NotifyIcon
    $notify.Icon = [System.Drawing.SystemIcons]::Information
    $notify.Visible = $true
    $notify.ShowBalloonTip(4000, '{title}', '{message}', [System.Windows.Forms.ToolTipIcon]::None)
    Start-Sleep -s 5
    $notify.Dispose()
    """
    try:
        subprocess.Popen(
            ["powershell", "-WindowStyle", "Hidden", "-Command", script],
            creationflags=subprocess.CREATE_NO_WINDOW
        )
    except Exception:
        pass  # not critical if this fails


# --------------------------------------------------
# Colors
# --------------------------------------------------
DARK = {
    "bg": "#0f0f13",
    "surface": "#1a1a24",
    "card": "#22223a",
    "accent": "#6c63ff",
    "accent2": "#ff6584",
    "success": "#43e97b",
    "warn": "#f9c74f",
    "text": "#e8e8f0",
    "subtext": "#8888aa",
    "border": "#2e2e4a",
}

LIGHT = {
    "bg": "#f4f4fb",
    "surface": "#ffffff",
    "card": "#eaeaf6",
    "accent": "#6c63ff",
    "accent2": "#ff6584",
    "success": "#2cb67d",
    "warn": "#e09f00",
    "text": "#1a1a2e",
    "subtext": "#555577",
    "border": "#d0d0e8",
}


# --------------------------------------------------
# Main App
# --------------------------------------------------
class FocusLock(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.stats = load_stats()
        self.C = DARK if self.cfg.get("theme") == "dark" else LIGHT

        self._blocker = None
        self._timer = None
        self._session_start = None
        self._locked = False
        self._tray = None
        self._paused = False

        self.title(f"FocusLock v{VERSION}")
        self.geometry("820x640")
        self.resizable(False, False)
        self.configure(bg=self.C["bg"])

        # hide CMD window if running as script (not frozen exe)
        if not getattr(sys, "frozen", False):
            try:
                import ctypes
                ctypes.windll.user32.ShowWindow(
                    ctypes.windll.kernel32.GetConsoleWindow(), 0
                )
            except Exception:
                pass

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # -----------------------------------------------
    # UI
    # -----------------------------------------------
    def _build_ui(self):
        C = self.C

        # header
        hdr = tk.Frame(self, bg=C["surface"], height=60)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(hdr, text="🔒 FocusLock", font=("Segoe UI", 17, "bold"),
                 bg=C["surface"], fg=C["accent"]).pack(side="left", padx=20, pady=14)
        tk.Label(hdr, text=f"v{VERSION}",
                 font=("Segoe UI", 9), bg=C["surface"], fg=C["subtext"]).pack(side="left", pady=14)

        self._theme_btn = tk.Button(
            hdr, text="☀" if self.cfg["theme"] == "dark" else "🌙",
            command=self._toggle_theme, relief="flat",
            bg=C["surface"], fg=C["subtext"], font=("Segoe UI", 14),
            cursor="hand2", bd=0
        )
        self._theme_btn.pack(side="right", padx=16)

        # tab bar
        tab_bar = tk.Frame(self, bg=C["surface"])
        tab_bar.pack(fill="x")

        self._pages = {}
        self._tab_btns = {}
        self._active_tab = "Session"

        for tab in ["Session", "Blocklist", "Websites", "Stats", "Settings"]:
            btn = tk.Button(
                tab_bar, text=tab, relief="flat",
                bg=C["surface"], fg=C["subtext"],
                font=("Segoe UI", 10), padx=16, pady=10,
                command=lambda t=tab: self._switch_tab(t),
                cursor="hand2", bd=0
            )
            btn.pack(side="left")
            self._tab_btns[tab] = btn

        # content
        self._content = tk.Frame(self, bg=C["bg"])
        self._content.pack(fill="both", expand=True, padx=20, pady=16)

        self._build_session_tab()
        self._build_blocklist_tab()
        self._build_websites_tab()
        self._build_stats_tab()
        self._build_settings_tab()

        self._switch_tab("Session")

    def _switch_tab(self, name):
        C = self.C
        for n, p in self._pages.items():
            p.pack_forget()
        for n, b in self._tab_btns.items():
            b.configure(
                fg=C["accent"] if n == name else C["subtext"],
                font=("Segoe UI", 10, "bold" if n == name else "normal"),
            )
        self._pages[name].pack(fill="both", expand=True)
        self._active_tab = name

    # -----------------------------------------------
    # Session tab
    # -----------------------------------------------
    def _build_session_tab(self):
        C = self.C
        f = tk.Frame(self._content, bg=C["bg"])
        self._pages["Session"] = f

        # session name input
        name_row = tk.Frame(f, bg=C["bg"])
        name_row.pack(fill="x", pady=(0, 8))
        tk.Label(name_row, text="Session name (optional):",
                 bg=C["bg"], fg=C["subtext"], font=("Segoe UI", 9)).pack(side="left")
        self._session_name_var = tk.StringVar(value=self.cfg.get("session_name", ""))
        tk.Entry(name_row, textvariable=self._session_name_var,
                 bg=C["card"], fg=C["text"], insertbackground=C["text"],
                 relief="flat", font=("Segoe UI", 10), width=28
                 ).pack(side="left", padx=8)

        # timer card
        card = tk.Frame(f, bg=C["card"])
        card.pack(fill="x", pady=(0, 10))

        self._phase_lbl = tk.Label(card, text="FOCUS TIME",
                                    font=("Segoe UI", 11, "bold"),
                                    bg=C["card"], fg=C["accent"])
        self._phase_lbl.pack(pady=(16, 2))

        self._timer_lbl = tk.Label(card, text="25:00",
                                    font=("Courier New", 54, "bold"),
                                    bg=C["card"], fg=C["text"])
        self._timer_lbl.pack()

        self._cycle_lbl = tk.Label(card, text="No cycles yet",
                                    font=("Segoe UI", 9),
                                    bg=C["card"], fg=C["subtext"])
        self._cycle_lbl.pack(pady=(0, 8))

        self._progress = ttk.Progressbar(card, length=420, mode="determinate")
        self._progress.pack(pady=(0, 14))

        # buttons row
        btn_row = tk.Frame(card, bg=C["card"])
        btn_row.pack(pady=(0, 16))

        self._start_btn = tk.Button(
            btn_row, text="🔒  START SESSION",
            command=self._toggle_session,
            bg=C["accent"], fg="white",
            font=("Segoe UI", 12, "bold"),
            relief="flat", padx=22, pady=9, cursor="hand2", bd=0
        )
        self._start_btn.pack(side="left", padx=4)

        self._pause_btn = tk.Button(
            btn_row, text="⏸ Pause",
            command=self._pause_resume,
            bg=C["card"], fg=C["subtext"],
            font=("Segoe UI", 10),
            relief="flat", padx=12, pady=9, cursor="hand2", bd=0,
            state="disabled"
        )
        self._pause_btn.pack(side="left", padx=4)

        self._reset_btn = tk.Button(
            btn_row, text="↺ Reset",
            command=self._reset_timer,
            bg=C["card"], fg=C["subtext"],
            font=("Segoe UI", 10),
            relief="flat", padx=12, pady=9, cursor="hand2", bd=0
        )
        self._reset_btn.pack(side="left", padx=4)

        # presets
        preset_row = tk.Frame(f, bg=C["bg"])
        preset_row.pack(fill="x", pady=2)
        tk.Label(preset_row, text="Preset:",
                 bg=C["bg"], fg=C["subtext"], font=("Segoe UI", 9)).pack(side="left")

        self._preset_var = tk.StringVar(value="Classic (25/5)")
        for label in POMODORO_PRESETS:
            tk.Radiobutton(
                preset_row, text=label, variable=self._preset_var,
                value=label, command=self._apply_preset,
                bg=C["bg"], fg=C["text"], selectcolor=C["card"],
                activebackground=C["bg"], font=("Segoe UI", 9),
                cursor="hand2"
            ).pack(side="left", padx=6)

        self._status_lbl = tk.Label(
            f, text="Ready. Pick a preset and start your session.",
            bg=C["bg"], fg=C["subtext"], font=("Segoe UI", 9)
        )
        self._status_lbl.pack(pady=6)

    # -----------------------------------------------
    # Blocklist tab
    # -----------------------------------------------
    def _build_blocklist_tab(self):
        C = self.C
        f = tk.Frame(self._content, bg=C["bg"])
        self._pages["Blocklist"] = f

        tk.Label(f, text="App Blocklist", font=("Segoe UI", 13, "bold"),
                 bg=C["bg"], fg=C["text"]).pack(anchor="w", pady=(0, 2))
        tk.Label(f, text="These processes get force-killed every 2 seconds during a session.",
                 bg=C["bg"], fg=C["subtext"], font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 8))

        lf = tk.Frame(f, bg=C["card"])
        lf.pack(fill="both", expand=True)

        sb = tk.Scrollbar(lf)
        sb.pack(side="right", fill="y")

        self._app_lb = tk.Listbox(
            lf, yscrollcommand=sb.set,
            bg=C["card"], fg=C["text"], selectbackground=C["accent"],
            font=("Consolas", 10), relief="flat", bd=0, highlightthickness=0
        )
        self._app_lb.pack(fill="both", expand=True, padx=8, pady=8)
        sb.config(command=self._app_lb.yview)

        for app in self.cfg["blocklist"]:
            self._app_lb.insert(tk.END, app)

        br = tk.Frame(f, bg=C["bg"])
        br.pack(fill="x", pady=6)

        tk.Button(br, text="+ Add App", command=self._add_app,
                  bg=C["accent"], fg="white", relief="flat",
                  font=("Segoe UI", 9, "bold"), padx=12, pady=5,
                  cursor="hand2", bd=0).pack(side="left", padx=(0, 6))
        tk.Button(br, text="✕ Remove", command=self._remove_app,
                  bg=C["card"], fg=C["accent2"], relief="flat",
                  font=("Segoe UI", 9), padx=12, pady=5,
                  cursor="hand2", bd=0).pack(side="left")
        tk.Button(br, text="↺ Reset Defaults", command=self._reset_app_defaults,
                  bg=C["card"], fg=C["subtext"], relief="flat",
                  font=("Segoe UI", 9), padx=12, pady=5,
                  cursor="hand2", bd=0).pack(side="right")

    # -----------------------------------------------
    # Websites tab
    # -----------------------------------------------
    def _build_websites_tab(self):
        C = self.C
        f = tk.Frame(self._content, bg=C["bg"])
        self._pages["Websites"] = f

        tk.Label(f, text="Website Blocker", font=("Segoe UI", 13, "bold"),
                 bg=C["bg"], fg=C["text"]).pack(anchor="w", pady=(0, 2))
        tk.Label(f, text="⚠  Requires Administrator — right-click FocusLock → Run as Administrator.",
                 bg=C["bg"], fg=C["warn"], font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 8))

        self._web_var = tk.BooleanVar(value=self.cfg.get("block_websites", False))
        web_row = tk.Frame(f, bg=C["bg"])
        web_row.pack(anchor="w", pady=(0, 6))
        tk.Label(web_row, text="Block websites during sessions",
                 bg=C["bg"], fg=C["text"], font=("Segoe UI", 10)).pack(side="left")
        def _web_refresh():
            on = self._web_var.get()
            _web_btn.configure(
                text="  ON  " if on else "  OFF  ",
                bg=C["accent"] if on else C["border"],
                fg="white" if on else C["subtext"],
            )
        def _web_click():
            self._web_var.set(not self._web_var.get())
            _web_refresh()
            self._save_cfg()
        _web_btn = tk.Button(web_row, text="", command=_web_click,
                             relief="flat", font=("Segoe UI", 8, "bold"),
                             padx=6, pady=3, cursor="hand2", bd=0)
        _web_btn.pack(side="left", padx=10)
        _web_refresh()

        lf = tk.Frame(f, bg=C["card"])
        lf.pack(fill="both", expand=True)

        sb = tk.Scrollbar(lf)
        sb.pack(side="right", fill="y")

        self._web_lb = tk.Listbox(
            lf, yscrollcommand=sb.set,
            bg=C["card"], fg=C["text"], selectbackground=C["accent"],
            font=("Consolas", 10), relief="flat", bd=0, highlightthickness=0
        )
        self._web_lb.pack(fill="both", expand=True, padx=8, pady=8)
        sb.config(command=self._web_lb.yview)

        for site in self.cfg["website_blocklist"]:
            self._web_lb.insert(tk.END, site)

        br = tk.Frame(f, bg=C["bg"])
        br.pack(fill="x", pady=6)

        tk.Button(br, text="+ Add Site", command=self._add_site,
                  bg=C["accent"], fg="white", relief="flat",
                  font=("Segoe UI", 9, "bold"), padx=12, pady=5,
                  cursor="hand2", bd=0).pack(side="left", padx=(0, 6))
        tk.Button(br, text="✕ Remove", command=self._remove_site,
                  bg=C["card"], fg=C["accent2"], relief="flat",
                  font=("Segoe UI", 9), padx=12, pady=5,
                  cursor="hand2", bd=0).pack(side="left")

    # -----------------------------------------------
    # Stats tab
    # -----------------------------------------------
    def _build_stats_tab(self):
        C = self.C
        f = tk.Frame(self._content, bg=C["bg"])
        self._pages["Stats"] = f

        tk.Label(f, text="Study Stats", font=("Segoe UI", 13, "bold"),
                 bg=C["bg"], fg=C["text"]).pack(anchor="w", pady=(0, 12))

        s = self.stats
        hours = s["total_minutes"] // 60
        mins = s["total_minutes"] % 60

        rows = [
            ("📅", "Total Sessions", str(s["total_sessions"])),
            ("⏱", "Total Focus Time", f"{hours}h {mins}m"),
            ("🔥", "Current Streak", f"{s['current_streak']} days"),
            ("🏆", "Longest Streak", f"{s['longest_streak']} days"),
        ]

        for icon, label, val in rows:
            row = tk.Frame(f, bg=C["card"])
            row.pack(fill="x", pady=3)
            tk.Label(row, text=icon, font=("Segoe UI", 16),
                     bg=C["card"]).pack(side="left", padx=12, pady=10)
            tk.Label(row, text=label, font=("Segoe UI", 10),
                     bg=C["card"], fg=C["subtext"]).pack(side="left")
            tk.Label(row, text=val, font=("Segoe UI", 12, "bold"),
                     bg=C["card"], fg=C["accent"]).pack(side="right", padx=16)

        # last session date
        if s.get("last_session_date"):
            tk.Label(f, text=f"Last session: {s['last_session_date']}",
                     bg=C["bg"], fg=C["subtext"],
                     font=("Segoe UI", 9)).pack(anchor="w", pady=8)

        tk.Button(f, text="Reset all stats", command=self._reset_stats,
                  bg=C["card"], fg=C["accent2"], relief="flat",
                  font=("Segoe UI", 9), pady=5, cursor="hand2", bd=0
                  ).pack(anchor="e", pady=10)

    # -----------------------------------------------
    # Settings tab
    # -----------------------------------------------
    def _build_settings_tab(self):
        C = self.C
        f = tk.Frame(self._content, bg=C["bg"])
        self._pages["Settings"] = f

        tk.Label(f, text="Settings", font=("Segoe UI", 13, "bold"),
                 bg=C["bg"], fg=C["text"]).pack(anchor="w", pady=(0, 12))

        # helper to make a proper toggle button (checkbuttons are buggy on windows)
        def make_toggle(parent, var, callback):
            def refresh():
                on = var.get()
                btn.configure(
                    text="  ON  " if on else "  OFF  ",
                    bg=C["accent"] if on else C["border"],
                    fg="white" if on else C["subtext"],
                )
            def click():
                var.set(not var.get())
                refresh()
                callback()
            btn = tk.Button(parent, text="", command=click,
                            relief="flat", font=("Segoe UI", 8, "bold"),
                            padx=6, pady=4, cursor="hand2", bd=0)
            refresh()
            return btn

        # startup toggle
        startup_row = tk.Frame(f, bg=C["card"])
        startup_row.pack(fill="x", pady=3)
        tk.Label(startup_row, text="🚀  Launch with Windows",
                 bg=C["card"], fg=C["text"], font=("Segoe UI", 10)
                 ).pack(side="left", padx=12, pady=10)
        self._startup_var = tk.BooleanVar(value=is_startup_enabled())
        make_toggle(startup_row, self._startup_var, self._toggle_startup).pack(side="right", padx=12, pady=8)

        # break notifications
        notif_row = tk.Frame(f, bg=C["card"])
        notif_row.pack(fill="x", pady=3)
        tk.Label(notif_row, text="🔔  Break notifications",
                 bg=C["card"], fg=C["text"], font=("Segoe UI", 10)
                 ).pack(side="left", padx=12, pady=10)
        self._notif_var = tk.BooleanVar(value=self.cfg.get("notify_break", True))
        make_toggle(notif_row, self._notif_var, self._save_cfg).pack(side="right", padx=12, pady=8)

        # minimize to tray
        tray_row = tk.Frame(f, bg=C["card"])
        tray_row.pack(fill="x", pady=3)
        tk.Label(tray_row, text="🗕  Minimize to system tray",
                 bg=C["card"], fg=C["text"], font=("Segoe UI", 10)
                 ).pack(side="left", padx=12, pady=10)
        self._tray_var = tk.BooleanVar(value=self.cfg.get("minimize_to_tray", True))
        make_toggle(tray_row, self._tray_var, self._save_cfg).pack(side="right", padx=12, pady=8)

        # passwords
        pw_row = tk.Frame(f, bg=C["card"])
        pw_row.pack(fill="x", pady=3)
        tk.Label(pw_row, text="🔑  Session stop password",
                 bg=C["card"], fg=C["text"], font=("Segoe UI", 10)
                 ).pack(side="left", padx=12, pady=10)
        has_pw = "✓ Set" if self.cfg.get("password_hash") else "Not set"
        tk.Label(pw_row, text=has_pw,
                 bg=C["card"], fg=C["success"] if self.cfg.get("password_hash") else C["subtext"],
                 font=("Segoe UI", 9)).pack(side="right", padx=6)
        tk.Button(pw_row, text="Change", command=lambda: self._set_password("password_hash"),
                  bg=C["accent"], fg="white", relief="flat",
                  font=("Segoe UI", 9), padx=8, pady=3,
                  cursor="hand2", bd=0).pack(side="right", padx=6, pady=8)

        # parent password (extra lock, different from session pw)
        ppw_row = tk.Frame(f, bg=C["card"])
        ppw_row.pack(fill="x", pady=3)
        tk.Label(ppw_row, text="👨‍👧  Parent password (overrides session pw)",
                 bg=C["card"], fg=C["text"], font=("Segoe UI", 10)
                 ).pack(side="left", padx=12, pady=10)
        has_ppw = "✓ Set" if self.cfg.get("parent_password_hash") else "Not set"
        tk.Label(ppw_row, text=has_ppw,
                 bg=C["card"], fg=C["success"] if self.cfg.get("parent_password_hash") else C["subtext"],
                 font=("Segoe UI", 9)).pack(side="right", padx=6)
        tk.Button(ppw_row, text="Change", command=lambda: self._set_password("parent_password_hash"),
                  bg=C["accent"], fg="white", relief="flat",
                  font=("Segoe UI", 9), padx=8, pady=3,
                  cursor="hand2", bd=0).pack(side="right", padx=6, pady=8)

        # about
        about = tk.Frame(f, bg=C["card"])
        about.pack(fill="x", pady=3)
        tk.Label(about, text="FocusLock  ·  made by zadwen  ·  github.com/zadwen/FocusLock",
                 bg=C["card"], fg=C["subtext"], font=("Segoe UI", 9)
                 ).pack(padx=12, pady=10)

        # future ideas note (feels human lol)
        ideas = tk.Frame(f, bg=C["bg"])
        ideas.pack(fill="x", pady=(8, 0))
        tk.Label(ideas,
                 text="Coming soon: daily goals, export stats, multiple profiles, Discord status",
                 bg=C["bg"], fg=C["subtext"], font=("Segoe UI", 8, "italic")
                 ).pack(anchor="w")

    # -----------------------------------------------
    # Session logic
    # -----------------------------------------------
    def _toggle_session(self):
        if not self._locked:
            self._start_session()
        else:
            self._end_session()

    def _start_session(self):
        C = self.C
        work, brk = POMODORO_PRESETS.get(
            self._preset_var.get(),
            (self.cfg["pomodoro_work"], self.cfg["pomodoro_break"])
        )

        self._timer = PomodoroTimer(
            work, brk,
            on_tick=self._tick,
            on_phase_change=self._phase_change
        )
        self._progress["maximum"] = work * 60

        self._blocker = AppBlocker(self.cfg["blocklist"])
        self._blocker.start()

        if self._web_var.get():
            ok = block_websites(self.cfg["website_blocklist"])
            if not ok:
                messagebox.showwarning(
                    "Admin needed",
                    "Website blocking needs Administrator.\n"
                    "Right-click FocusLock → Run as Administrator."
                )

        self._timer.start()
        self._locked = True
        self._paused = False
        self._session_start = datetime.datetime.now()

        # save session name
        self.cfg["session_name"] = self._session_name_var.get()
        save_config(self.cfg)

        self._start_btn.configure(text="🔓  STOP SESSION", bg=C["accent2"])
        self._pause_btn.configure(state="normal")
        self._status_lbl.configure(text="🔒 Locked in. Apps are being monitored.")

    def _end_session(self):
        # check password
        if self.cfg.get("password_hash") or self.cfg.get("parent_password_hash"):
            pw = simpledialog.askstring("Unlock", "Enter password to stop:", show="*")
            if not pw:
                return
            phash = hash_pw(pw)
            valid = (
                phash == self.cfg.get("password_hash") or
                phash == self.cfg.get("parent_password_hash")
            )
            if not valid:
                messagebox.showerror("Wrong password", "Stay focused! You can do it 💪")
                return

        C = self.C
        if self._timer:
            self._timer.pause()
        if self._blocker:
            self._blocker.stop()
        unblock_websites()

        self._locked = False
        self._paused = False
        self._start_btn.configure(text="🔒  START SESSION", bg=C["accent"])
        self._pause_btn.configure(state="disabled", text="⏸ Pause")
        self._status_lbl.configure(text="Session ended. Good work!")

        self._record_session()

    def _pause_resume(self):
        if not self._locked or not self._timer:
            return
        C = self.C
        if not self._paused:
            self._timer.pause()
            if self._blocker:
                self._blocker.stop()
            self._paused = True
            self._pause_btn.configure(text="▶ Resume")
            self._status_lbl.configure(text="⏸ Paused — blocking suspended.")
        else:
            self._timer.start()
            self._blocker = AppBlocker(self.cfg["blocklist"])
            self._blocker.start()
            self._paused = False
            self._pause_btn.configure(text="⏸ Pause")
            self._status_lbl.configure(text="🔒 Back to focus mode.")

    def _reset_timer(self):
        if self._locked:
            messagebox.showinfo("Active", "Stop the session first.")
            return
        if self._timer:
            self._timer.reset()
        work, _ = POMODORO_PRESETS.get(self._preset_var.get(), (25, 5))
        self._timer_lbl.configure(text=f"{work:02d}:00")
        self._phase_lbl.configure(text="FOCUS TIME")
        self._progress["value"] = 0
        self._cycle_lbl.configure(text="No cycles yet")

    def _apply_preset(self):
        if self._locked:
            return
        name = self._preset_var.get()
        work, brk = POMODORO_PRESETS[name]
        self.cfg["pomodoro_work"] = work
        self.cfg["pomodoro_break"] = brk
        save_config(self.cfg)
        self._timer_lbl.configure(text=f"{work:02d}:00")
        self._progress["value"] = 0

    # -----------------------------------------------
    # Timer callbacks (must use .after for thread safety)
    # -----------------------------------------------
    def _tick(self, remaining, phase):
        self.after(0, self._update_timer, remaining, phase)

    def _update_timer(self, remaining, phase):
        m, s = divmod(remaining, 60)
        self._timer_lbl.configure(text=f"{m:02d}:{s:02d}")
        total = (self.cfg["pomodoro_work"] if phase == "work"
                 else self.cfg["pomodoro_break"]) * 60
        self._progress["maximum"] = total
        self._progress["value"] = total - remaining

    def _phase_change(self, new_phase, cycles):
        self.after(0, self._update_phase, new_phase, cycles)

    def _update_phase(self, phase, cycles):
        C = self.C
        if phase == "work":
            self._phase_lbl.configure(text="FOCUS TIME", fg=C["accent"])
            if self.cfg.get("notify_break"):
                notify("FocusLock", "Break's over — back to work! 💪")
        else:
            self._phase_lbl.configure(text="☕ BREAK TIME", fg=C["success"])
            if self.cfg.get("notify_break"):
                notify("FocusLock", f"Nice work! Take a break. ({cycles} cycles done)")
        self._cycle_lbl.configure(text=f"{cycles} cycle{'s' if cycles != 1 else ''} done")
        self.bell()

    # -----------------------------------------------
    # App list management
    # -----------------------------------------------
    def _add_app(self):
        val = simpledialog.askstring("Add app", "Enter the .exe name (e.g. discord.exe):")
        if val and val.strip():
            name = val.strip().lower()
            if name not in self.cfg["blocklist"]:
                self.cfg["blocklist"].append(name)
                self._app_lb.insert(tk.END, name)
                save_config(self.cfg)

    def _remove_app(self):
        sel = self._app_lb.curselection()
        if not sel:
            return
        val = self._app_lb.get(sel[0])
        self._app_lb.delete(sel[0])
        if val in self.cfg["blocklist"]:
            self.cfg["blocklist"].remove(val)
        save_config(self.cfg)

    def _reset_app_defaults(self):
        if messagebox.askyesno("Reset", "Reset blocklist to defaults?"):
            self.cfg["blocklist"] = DEFAULT_APPS[:]
            self._app_lb.delete(0, tk.END)
            for app in self.cfg["blocklist"]:
                self._app_lb.insert(tk.END, app)
            save_config(self.cfg)

    def _add_site(self):
        val = simpledialog.askstring("Add site", "Enter domain (e.g. reddit.com):")
        if val and val.strip():
            name = val.strip().lower()
            if name not in self.cfg["website_blocklist"]:
                self.cfg["website_blocklist"].append(name)
                self._web_lb.insert(tk.END, name)
                save_config(self.cfg)

    def _remove_site(self):
        sel = self._web_lb.curselection()
        if not sel:
            return
        val = self._web_lb.get(sel[0])
        self._web_lb.delete(sel[0])
        if val in self.cfg["website_blocklist"]:
            self.cfg["website_blocklist"].remove(val)
        save_config(self.cfg)

    # -----------------------------------------------
    # Password
    # -----------------------------------------------
    def _set_password(self, key):
        pw = simpledialog.askstring("Password", "New password (blank = disable):", show="*")
        if pw is None:
            return
        self.cfg[key] = hash_pw(pw) if pw else ""
        save_config(self.cfg)
        messagebox.showinfo("Saved", "Password updated!" if pw else "Password removed.")
        # refresh the settings tab
        self._pages["Settings"].pack_forget()
        self._pages["Settings"].destroy()
        del self._pages["Settings"]
        self._build_settings_tab()
        if self._active_tab == "Settings":
            self._pages["Settings"].pack(fill="both", expand=True)

    # -----------------------------------------------
    # Stats
    # -----------------------------------------------
    def _record_session(self):
        if not self._session_start:
            return
        mins = max(1, (datetime.datetime.now() - self._session_start).seconds // 60)
        today = datetime.date.today().isoformat()

        self.stats["total_sessions"] += 1
        self.stats["total_minutes"] += mins
        self.stats["sessions_by_date"][today] = self.stats["sessions_by_date"].get(today, 0) + 1

        # streak logic
        last = self.stats.get("last_session_date", "")
        if last:
            try:
                last_date = datetime.date.fromisoformat(last)
                diff = (datetime.date.today() - last_date).days
                if diff == 1:
                    self.stats["current_streak"] += 1
                elif diff > 1:
                    self.stats["current_streak"] = 1
                # diff == 0 means same day, no change
            except Exception:
                self.stats["current_streak"] = 1
        else:
            self.stats["current_streak"] = 1

        self.stats["longest_streak"] = max(
            self.stats["longest_streak"], self.stats["current_streak"]
        )
        self.stats["last_session_date"] = today

        save_stats(self.stats)
        self._session_start = None

    def _reset_stats(self):
        if messagebox.askyesno("Reset", "Clear all your study stats?"):
            self.stats = {
                "total_sessions": 0, "total_minutes": 0,
                "sessions_by_date": {}, "current_streak": 0,
                "longest_streak": 0, "last_session_date": ""
            }
            save_stats(self.stats)

    # -----------------------------------------------
    # Settings helpers
    # -----------------------------------------------
    def _toggle_startup(self):
        ok = set_startup(self._startup_var.get())
        if not ok:
            messagebox.showwarning("Error", "Couldn't update startup setting.")
            self._startup_var.set(not self._startup_var.get())
        self._save_cfg()

    def _toggle_theme(self):
        self.cfg["theme"] = "light" if self.cfg["theme"] == "dark" else "dark"
        save_config(self.cfg)
        messagebox.showinfo("Theme changed", "Restart FocusLock to apply the theme.")

    def _save_cfg(self):
        self.cfg["block_websites"] = self._web_var.get()
        self.cfg["notify_break"] = self._notif_var.get()
        self.cfg["minimize_to_tray"] = self._tray_var.get()
        save_config(self.cfg)

    # -----------------------------------------------
    # Close / tray
    # -----------------------------------------------
    def _on_close(self):
        if self._locked:
            messagebox.showwarning("Locked", "Stop the session before closing!")
            return

        if self.cfg.get("minimize_to_tray") and HAS_TRAY:
            self._minimize_to_tray()
            return

        if self._blocker:
            self._blocker.stop()
        unblock_websites()
        self.destroy()

    def _minimize_to_tray(self):
        self.withdraw()
        if HAS_TRAY and self._tray is None:
            img = make_tray_icon()
            menu = pystray.Menu(
                pystray.MenuItem("Open FocusLock", self._restore),
                pystray.MenuItem("Quit", self._quit_from_tray)
            )
            self._tray = pystray.Icon("FocusLock", img, "FocusLock", menu)
            threading.Thread(target=self._tray.run, daemon=True).start()

    def _restore(self, icon=None, item=None):
        self.after(0, self.deiconify)

    def _quit_from_tray(self, icon=None, item=None):
        if self._locked:
            return
        if self._tray:
            self._tray.stop()
        if self._blocker:
            self._blocker.stop()
        unblock_websites()
        self.after(0, self.destroy)


# --------------------------------------------------
# Run
# --------------------------------------------------
if __name__ == "__main__":
    app = FocusLock()
    app.mainloop()
