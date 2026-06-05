"""
FocusLock - Study Focus App Blocker for Windows
Author: zadwen
GitHub: https://github.com/zadwen/FocusLock
"""

import sys
import os
import json
import time
import threading
import subprocess
import hashlib
import datetime
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from pathlib import Path

# ─────────────────────────────────────────────
# Constants & Paths
# ─────────────────────────────────────────────
APP_NAME = "FocusLock"
VERSION  = "1.0.0"
AUTHOR   = "zadwen"

DATA_DIR  = Path(os.getenv("APPDATA", ".")) / "FocusLock"
DATA_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = DATA_DIR / "config.json"
STATS_FILE  = DATA_DIR / "stats.json"

DEFAULT_BLOCKLIST = [
    "steam.exe",
    "steamwebhelper.exe",
    "discord.exe",
    "EpicGamesLauncher.exe",
    "Battle.net.exe",
    "LeagueClient.exe",
    "TwitchUI.exe",
    "Netflix.exe",
    "Spotify.exe",
    "chrome.exe",   # optional - user can remove
]

DEFAULT_WEBSITE_BLOCKLIST = [
    "youtube.com",
    "twitter.com",
    "reddit.com",
    "twitch.tv",
    "instagram.com",
    "tiktok.com",
    "facebook.com",
]

POMODORO_PRESETS = {
    "Classic (25/5)":   (25, 5),
    "Long Focus (50/10)": (50, 10),
    "Short Burst (15/3)": (15, 3),
    "Deep Work (90/20)":  (90, 20),
}

# ─────────────────────────────────────────────
# Config & Stats
# ─────────────────────────────────────────────
def load_config() -> dict:
    defaults = {
        "blocklist": DEFAULT_BLOCKLIST,
        "website_blocklist": DEFAULT_WEBSITE_BLOCKLIST,
        "password_hash": "",
        "block_websites": False,
        "pomodoro_work": 25,
        "pomodoro_break": 5,
        "theme": "dark",
    }
    if CONFIG_FILE.exists():
        try:
            saved = json.loads(CONFIG_FILE.read_text())
            defaults.update(saved)
        except Exception:
            pass
    return defaults


def save_config(cfg: dict):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


def load_stats() -> dict:
    defaults = {
        "total_sessions": 0,
        "total_focus_minutes": 0,
        "sessions_by_date": {},
        "longest_streak_days": 0,
    }
    if STATS_FILE.exists():
        try:
            saved = json.loads(STATS_FILE.read_text())
            defaults.update(saved)
        except Exception:
            pass
    return defaults


def save_stats(stats: dict):
    STATS_FILE.write_text(json.dumps(stats, indent=2))


def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()



# App Blocking Engine

class AppBlocker:
    def __init__(self, blocklist: list[str]):
        self.blocklist = [b.lower() for b in blocklist]
        self._running = False
        self._thread: threading.Thread | None = None

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
            result = subprocess.run(
                ["tasklist", "/fo", "csv", "/nh"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.splitlines():
                parts = line.strip().strip('"').split('","')
                if not parts:
                    continue
                proc_name = parts[0].lower()
                if proc_name in self.blocklist:
                    pid = parts[1] if len(parts) > 1 else None
                    if pid:
                        subprocess.run(
                            ["taskkill", "/F", "/PID", pid],
                            capture_output=True
                        )
        except Exception:
            pass  # Fail silently — don't crash the blocker



# Website Blocking Engine (hosts file)

HOSTS_PATH = Path(r"C:\Windows\System32\drivers\etc\hosts")
BLOCK_MARKER_START = "# FocusLock-START"
BLOCK_MARKER_END   = "# FocusLock-END"

def block_websites(domains: list[str]):
    """Append domains to hosts file (requires admin)."""
    try:
        content = HOSTS_PATH.read_text(encoding="utf-8")
        # Remove previous FocusLock block if any
        content = _strip_focuslock_block(content)
        block = f"\n{BLOCK_MARKER_START}\n"
        for d in domains:
            block += f"127.0.0.1 {d}\n"
            block += f"127.0.0.1 www.{d}\n"
        block += f"{BLOCK_MARKER_END}\n"
        HOSTS_PATH.write_text(content + block, encoding="utf-8")
    except PermissionError:
        return False
    return True


def unblock_websites():
    """Remove FocusLock entries from hosts file."""
    try:
        content = HOSTS_PATH.read_text(encoding="utf-8")
        content = _strip_focuslock_block(content)
        HOSTS_PATH.write_text(content, encoding="utf-8")
    except PermissionError:
        return False
    return True


def _strip_focuslock_block(content: str) -> str:
    lines = content.splitlines()
    out, inside = [], False
    for line in lines:
        if BLOCK_MARKER_START in line:
            inside = True
            continue
        if BLOCK_MARKER_END in line:
            inside = False
            continue
        if not inside:
            out.append(line)
    return "\n".join(out)



# Pomodoro Timer

class PomodoroTimer:
    def __init__(self, work_min: int, break_min: int,
                 on_tick=None, on_phase_change=None):
        self.work_sec  = work_min * 60
        self.break_sec = break_min * 60
        self.on_tick   = on_tick
        self.on_phase_change = on_phase_change
        self._remaining = self.work_sec
        self._phase     = "work"   # "work" | "break"
        self._running   = False
        self._thread: threading.Thread | None = None
        self.cycles_done = 0

    @property
    def phase(self): return self._phase

    @property
    def remaining(self): return self._remaining

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
        self.cycles_done = 0
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
            self._switch_phase()

    def _switch_phase(self):
        if self._phase == "work":
            self.cycles_done += 1
            self._phase = "break"
            self._remaining = self.break_sec
        else:
            self._phase = "work"
            self._remaining = self.work_sec

        if self.on_phase_change:
            self.on_phase_change(self._phase, self.cycles_done)

        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()



# FocusLock App

DARK = {
    "bg":       "#0f0f13",
    "surface":  "#1a1a24",
    "card":     "#22223a",
    "accent":   "#6c63ff",
    "accent2":  "#ff6584",
    "success":  "#43e97b",
    "text":     "#e8e8f0",
    "subtext":  "#8888aa",
    "border":   "#2e2e4a",
}

LIGHT = {
    "bg":       "#f4f4fb",
    "surface":  "#ffffff",
    "card":     "#eaeaf6",
    "accent":   "#6c63ff",
    "accent2":  "#ff6584",
    "success":  "#2cb67d",
    "text":     "#1a1a2e",
    "subtext":  "#555577",
    "border":   "#d0d0e8",
}


class FocusLockApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg   = load_config()
        self.stats = load_stats()
        self.C     = DARK if self.cfg.get("theme") == "dark" else LIGHT

        self._blocker: AppBlocker | None = None
        self._timer:   PomodoroTimer | None = None
        self._session_start: datetime.datetime | None = None
        self._locked = False

        self.title(f"FocusLock v{VERSION}  ·  by {AUTHOR}")
        self.geometry("800x620")
        self.resizable(False, False)
        self.configure(bg=self.C["bg"])

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # UI Construction
    def _build_ui(self):
        C = self.C

        # Header
        hdr = tk.Frame(self, bg=C["surface"], height=64)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(hdr, text="🔒 FocusLock", font=("Segoe UI", 18, "bold"),
                 bg=C["surface"], fg=C["accent"]).pack(side="left", padx=20, pady=16)
        tk.Label(hdr, text=f"v{VERSION} · by {AUTHOR}",
                 font=("Segoe UI", 9), bg=C["surface"], fg=C["subtext"]).pack(side="left")

        self._theme_btn = tk.Button(
            hdr, text="☀" if self.cfg["theme"] == "dark" else "🌙",
            command=self._toggle_theme, relief="flat",
            bg=C["surface"], fg=C["subtext"], font=("Segoe UI", 14),
            cursor="hand2"
        )
        self._theme_btn.pack(side="right", padx=16)

        # Tabs
        self._tab_frame = tk.Frame(self, bg=C["bg"])
        self._tab_frame.pack(fill="x", padx=0)

        self._pages: dict[str, tk.Frame] = {}
        self._tab_btns: dict[str, tk.Button] = {}
        self._active_tab = tk.StringVar(value="Session")

        tabs = ["Session", "Blocklist", "Websites", "Stats", "Settings"]
        tab_bar = tk.Frame(self, bg=C["surface"])
        tab_bar.pack(fill="x")

        for tab in tabs:
            btn = tk.Button(
                tab_bar, text=tab, relief="flat",
                bg=C["surface"], fg=C["subtext"],
                font=("Segoe UI", 10), padx=16, pady=10,
                command=lambda t=tab: self._switch_tab(t),
                cursor="hand2"
            )
            btn.pack(side="left")
            self._tab_btns[tab] = btn

        # Content area
        self._content = tk.Frame(self, bg=C["bg"])
        self._content.pack(fill="both", expand=True, padx=20, pady=16)

        self._build_session_page()
        self._build_blocklist_page()
        self._build_websites_page()
        self._build_stats_page()
        self._build_settings_page()

        self._switch_tab("Session")

    def _switch_tab(self, name: str):
        C = self.C
        for n, p in self._pages.items():
            p.pack_forget()
        for n, b in self._tab_btns.items():
            b.configure(
                fg=C["accent"] if n == name else C["subtext"],
                font=("Segoe UI", 10, "bold" if n == name else "normal"),
            )
        self._pages[name].pack(fill="both", expand=True)
        self._active_tab.set(name)

    # ── Session Page 
    def _build_session_page(self):
        C = self.C
        f = tk.Frame(self._content, bg=C["bg"])
        self._pages["Session"] = f

        # Timer card
        card = tk.Frame(f, bg=C["card"], relief="flat")
        card.pack(fill="x", pady=(0, 12))

        self._phase_label = tk.Label(
            card, text="FOCUS TIME", font=("Segoe UI", 11, "bold"),
            bg=C["card"], fg=C["accent"]
        )
        self._phase_label.pack(pady=(18, 4))

        self._timer_label = tk.Label(
            card, text="25:00", font=("Courier New", 52, "bold"),
            bg=C["card"], fg=C["text"]
        )
        self._timer_label.pack()

        self._cycle_label = tk.Label(
            card, text="Cycle 0 complete", font=("Segoe UI", 9),
            bg=C["card"], fg=C["subtext"]
        )
        self._cycle_label.pack(pady=(0, 12))

        # Progress bar
        self._progress = ttk.Progressbar(card, length=400, mode="determinate")
        self._progress.pack(pady=(0, 16))

        # Controls
        ctrl = tk.Frame(card, bg=C["card"])
        ctrl.pack(pady=(0, 18))

        self._lock_btn = tk.Button(
            ctrl, text="🔒  START FOCUS SESSION",
            command=self._toggle_session,
            bg=C["accent"], fg="white",
            font=("Segoe UI", 12, "bold"),
            relief="flat", padx=24, pady=10, cursor="hand2"
        )
        self._lock_btn.pack(side="left", padx=6)

        self._reset_btn = tk.Button(
            ctrl, text="↺  Reset",
            command=self._reset_timer,
            bg=C["card"], fg=C["subtext"],
            font=("Segoe UI", 10),
            relief="flat", padx=12, pady=10, cursor="hand2"
        )
        self._reset_btn.pack(side="left", padx=6)

        # Preset selector
        preset_row = tk.Frame(f, bg=C["bg"])
        preset_row.pack(fill="x", pady=4)
        tk.Label(preset_row, text="Pomodoro Preset:",
                 bg=C["bg"], fg=C["subtext"], font=("Segoe UI", 9)).pack(side="left")

        self._preset_var = tk.StringVar(value="Classic (25/5)")
        for label in POMODORO_PRESETS:
            rb = tk.Radiobutton(
                preset_row, text=label, variable=self._preset_var,
                value=label, command=self._apply_preset,
                bg=C["bg"], fg=C["text"], selectcolor=C["card"],
                activebackground=C["bg"], font=("Segoe UI", 9),
                cursor="hand2"
            )
            rb.pack(side="left", padx=8)

        # Status bar
        self._status = tk.Label(
            f, text="Ready to focus. Start a session to lock distractions.",
            bg=C["bg"], fg=C["subtext"], font=("Segoe UI", 9)
        )
        self._status.pack(pady=8)

    # ── Blocklist Page 
    def _build_blocklist_page(self):
        C = self.C
        f = tk.Frame(self._content, bg=C["bg"])
        self._pages["Blocklist"] = f

        tk.Label(f, text="App Blocklist", font=("Segoe UI", 14, "bold"),
                 bg=C["bg"], fg=C["text"]).pack(anchor="w", pady=(0, 4))
        tk.Label(f, text="These apps will be force-closed during focus sessions.",
                 bg=C["bg"], fg=C["subtext"], font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 10))

        list_frame = tk.Frame(f, bg=C["card"])
        list_frame.pack(fill="both", expand=True)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")

        self._app_listbox = tk.Listbox(
            list_frame, yscrollcommand=scrollbar.set,
            bg=C["card"], fg=C["text"], selectbackground=C["accent"],
            font=("Consolas", 10), relief="flat", bd=0,
            highlightthickness=0
        )
        self._app_listbox.pack(fill="both", expand=True, padx=8, pady=8)
        scrollbar.config(command=self._app_listbox.yview)

        for app in self.cfg["blocklist"]:
            self._app_listbox.insert(tk.END, app)

        btn_row = tk.Frame(f, bg=C["bg"])
        btn_row.pack(fill="x", pady=8)

        tk.Button(btn_row, text="+ Add App", command=self._add_app,
                  bg=C["accent"], fg="white", relief="flat",
                  font=("Segoe UI", 9, "bold"), padx=12, pady=6,
                  cursor="hand2").pack(side="left", padx=(0, 6))

        tk.Button(btn_row, text="✕ Remove Selected", command=self._remove_app,
                  bg=C["card"], fg=C["accent2"], relief="flat",
                  font=("Segoe UI", 9), padx=12, pady=6,
                  cursor="hand2").pack(side="left")

    # ── Websites Page 
    def _build_websites_page(self):
        C = self.C
        f = tk.Frame(self._content, bg=C["bg"])
        self._pages["Websites"] = f

        tk.Label(f, text="Website Blocker", font=("Segoe UI", 14, "bold"),
                 bg=C["bg"], fg=C["text"]).pack(anchor="w", pady=(0, 4))
        tk.Label(f, text="⚠ Requires running FocusLock as Administrator to modify hosts file.",
                 bg=C["bg"], fg=C["accent2"], font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 10))

        self._web_enabled = tk.BooleanVar(value=self.cfg.get("block_websites", False))
        tk.Checkbutton(
            f, text="Enable website blocking during sessions",
            variable=self._web_enabled, command=self._save_cfg,
            bg=C["bg"], fg=C["text"], selectcolor=C["card"],
            activebackground=C["bg"], font=("Segoe UI", 10),
            cursor="hand2"
        ).pack(anchor="w", pady=(0, 8))

        list_frame = tk.Frame(f, bg=C["card"])
        list_frame.pack(fill="both", expand=True)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")

        self._web_listbox = tk.Listbox(
            list_frame, yscrollcommand=scrollbar.set,
            bg=C["card"], fg=C["text"], selectbackground=C["accent"],
            font=("Consolas", 10), relief="flat", bd=0,
            highlightthickness=0
        )
        self._web_listbox.pack(fill="both", expand=True, padx=8, pady=8)
        scrollbar.config(command=self._web_listbox.yview)

        for site in self.cfg["website_blocklist"]:
            self._web_listbox.insert(tk.END, site)

        btn_row = tk.Frame(f, bg=C["bg"])
        btn_row.pack(fill="x", pady=8)

        tk.Button(btn_row, text="+ Add Site", command=self._add_site,
                  bg=C["accent"], fg="white", relief="flat",
                  font=("Segoe UI", 9, "bold"), padx=12, pady=6,
                  cursor="hand2").pack(side="left", padx=(0, 6))
        tk.Button(btn_row, text="✕ Remove Selected", command=self._remove_site,
                  bg=C["card"], fg=C["accent2"], relief="flat",
                  font=("Segoe UI", 9), padx=12, pady=6,
                  cursor="hand2").pack(side="left")

    # ── Stats Page 
    def _build_stats_page(self):
        C = self.C
        f = tk.Frame(self._content, bg=C["bg"])
        self._pages["Stats"] = f

        tk.Label(f, text="Your Study Stats", font=("Segoe UI", 14, "bold"),
                 bg=C["bg"], fg=C["text"]).pack(anchor="w", pady=(0, 16))

        stats = self.stats
        items = [
            ("📅", "Total Sessions",     str(stats["total_sessions"])),
            ("⏱",  "Total Focus Time",   f"{stats['total_focus_minutes']} min"),
            ("🔥",  "Longest Streak",     f"{stats['longest_streak_days']} days"),
        ]

        for icon, label, val in items:
            row = tk.Frame(f, bg=C["card"])
            row.pack(fill="x", pady=4)
            tk.Label(row, text=icon, font=("Segoe UI", 18), bg=C["card"]).pack(side="left", padx=12, pady=12)
            tk.Label(row, text=label, font=("Segoe UI", 11), bg=C["card"], fg=C["subtext"]).pack(side="left")
            tk.Label(row, text=val, font=("Segoe UI", 13, "bold"),
                     bg=C["card"], fg=C["accent"]).pack(side="right", padx=16)

        tk.Button(f, text="Reset Stats", command=self._reset_stats,
                  bg=C["card"], fg=C["accent2"], relief="flat",
                  font=("Segoe UI", 9), pady=6, cursor="hand2").pack(anchor="e", pady=16)

    # ── Settings Page 
    def _build_settings_page(self):
        C = self.C
        f = tk.Frame(self._content, bg=C["bg"])
        self._pages["Settings"] = f

        tk.Label(f, text="Settings", font=("Segoe UI", 14, "bold"),
                 bg=C["bg"], fg=C["text"]).pack(anchor="w", pady=(0, 16))

        # Password
        pw_frame = tk.Frame(f, bg=C["card"])
        pw_frame.pack(fill="x", pady=4)
        tk.Label(pw_frame, text="🔑  Session Lock Password",
                 bg=C["card"], fg=C["text"], font=("Segoe UI", 10)).pack(side="left", padx=12, pady=10)
        tk.Button(pw_frame, text="Set Password", command=self._set_password,
                  bg=C["accent"], fg="white", relief="flat",
                  font=("Segoe UI", 9), padx=10, pady=4,
                  cursor="hand2").pack(side="right", padx=12, pady=10)

        if self.cfg.get("password_hash"):
            tk.Label(pw_frame, text="✓ Set", bg=C["card"], fg=C["success"],
                     font=("Segoe UI", 9)).pack(side="right")

        # Autostart (informational)
        info = tk.Frame(f, bg=C["card"])
        info.pack(fill="x", pady=4)
        tk.Label(info, text="ℹ  Run as Administrator for website blocking & full app kill",
                 bg=C["card"], fg=C["subtext"], font=("Segoe UI", 9)).pack(padx=12, pady=10, anchor="w")

        # About
        about = tk.Frame(f, bg=C["card"])
        about.pack(fill="x", pady=4)
        tk.Label(about, text=f"FocusLock {VERSION}  ·  Made with ♥ by {AUTHOR}  ·  github.com/zadwen",
                 bg=C["card"], fg=C["subtext"], font=("Segoe UI", 9)).pack(padx=12, pady=12)

    # ── Session Logic 
    def _toggle_session(self):
        if not self._locked:
            self._start_session()
        else:
            self._stop_session()

    def _start_session(self):
        C = self.C
        work, brk = POMODORO_PRESETS.get(
            self._preset_var.get(), (self.cfg["pomodoro_work"], self.cfg["pomodoro_break"])
        )
        self._timer = PomodoroTimer(
            work, brk,
            on_tick=self._on_tick,
            on_phase_change=self._on_phase_change
        )
        self._progress["maximum"] = work * 60

        self._blocker = AppBlocker(self.cfg["blocklist"])
        self._blocker.start()

        if self.cfg.get("block_websites") and self._web_enabled.get():
            ok = block_websites(self.cfg["website_blocklist"])
            if not ok:
                messagebox.showwarning(
                    "Admin Required",
                    "Website blocking requires Administrator privileges.\n"
                    "Restart FocusLock as Admin to enable it."
                )

        self._timer.start()
        self._locked = True
        self._session_start = datetime.datetime.now()

        self._lock_btn.configure(text="⏸  PAUSE SESSION", bg=C["accent2"])
        self._status.configure(text="🔒 Session active — distractions are blocked!")

    def _stop_session(self):
        if self.cfg.get("password_hash"):
            pw = simpledialog.askstring("Unlock", "Enter password to stop session:", show="*")
            if not pw or hash_password(pw) != self.cfg["password_hash"]:
                messagebox.showerror("Locked", "Wrong password! Stay focused 💪")
                return

        C = self.C
        if self._timer:
            self._timer.pause()
        if self._blocker:
            self._blocker.stop()

        unblock_websites()

        self._locked = False
        self._lock_btn.configure(text="🔒  START FOCUS SESSION", bg=C["accent"])
        self._status.configure(text="Session ended. Great work!")

        self._record_session()

    def _reset_timer(self):
        if self._locked:
            messagebox.showinfo("Active", "Stop the session first.")
            return
        if self._timer:
            self._timer.reset()
        self._timer_label.configure(text=f"{self.cfg['pomodoro_work']:02d}:00")
        self._phase_label.configure(text="FOCUS TIME")
        self._progress["value"] = 0

    def _apply_preset(self):
        name = self._preset_var.get()
        work, brk = POMODORO_PRESETS[name]
        self.cfg["pomodoro_work"]  = work
        self.cfg["pomodoro_break"] = brk
        save_config(self.cfg)
        self._timer_label.configure(text=f"{work:02d}:00")

    # ── Timer Callbacks (thread-safe) ────────
    def _on_tick(self, remaining: int, phase: str):
        self.after(0, self._update_timer_ui, remaining, phase)

    def _update_timer_ui(self, remaining: int, phase: str):
        mins, secs = divmod(remaining, 60)
        self._timer_label.configure(text=f"{mins:02d}:{secs:02d}")
        total = (self.cfg["pomodoro_work"] if phase == "work"
                 else self.cfg["pomodoro_break"]) * 60
        self._progress["maximum"] = total
        self._progress["value"] = total - remaining

    def _on_phase_change(self, new_phase: str, cycles: int):
        self.after(0, self._update_phase_ui, new_phase, cycles)

    def _update_phase_ui(self, phase: str, cycles: int):
        C = self.C
        if phase == "work":
            self._phase_label.configure(text="FOCUS TIME", fg=C["accent"])
            self.bell()
        else:
            self._phase_label.configure(text="☕ BREAK TIME", fg=C["success"])
            self.bell()
        self._cycle_label.configure(text=f"Cycle {cycles} complete")

    # ── App/Site list management 
    def _add_app(self):
        val = simpledialog.askstring("Add App", "Enter .exe name (e.g. discord.exe):")
        if val and val.strip():
            name = val.strip().lower()
            if name not in self.cfg["blocklist"]:
                self.cfg["blocklist"].append(name)
                self._app_listbox.insert(tk.END, name)
                save_config(self.cfg)

    def _remove_app(self):
        sel = self._app_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        val = self._app_listbox.get(idx)
        self._app_listbox.delete(idx)
        if val in self.cfg["blocklist"]:
            self.cfg["blocklist"].remove(val)
        save_config(self.cfg)

    def _add_site(self):
        val = simpledialog.askstring("Add Website", "Enter domain (e.g. reddit.com):")
        if val and val.strip():
            name = val.strip().lower()
            if name not in self.cfg["website_blocklist"]:
                self.cfg["website_blocklist"].append(name)
                self._web_listbox.insert(tk.END, name)
                save_config(self.cfg)

    def _remove_site(self):
        sel = self._web_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        val = self._web_listbox.get(idx)
        self._web_listbox.delete(idx)
        if val in self.cfg["website_blocklist"]:
            self.cfg["website_blocklist"].remove(val)
        save_config(self.cfg)

    # ── Password 
    def _set_password(self):
        pw = simpledialog.askstring("Set Password", "New password (leave blank to disable):", show="*")
        if pw is None:
            return
        self.cfg["password_hash"] = hash_password(pw) if pw else ""
        save_config(self.cfg)
        messagebox.showinfo("Saved", "Password updated!" if pw else "Password removed.")

    # ── Stats recording 
    def _record_session(self):
        if not self._session_start:
            return
        elapsed = (datetime.datetime.now() - self._session_start).seconds // 60
        today = datetime.date.today().isoformat()

        self.stats["total_sessions"] += 1
        self.stats["total_focus_minutes"] += elapsed
        self.stats["sessions_by_date"][today] = (
            self.stats["sessions_by_date"].get(today, 0) + 1
        )
        save_stats(self.stats)
        self._session_start = None

    def _reset_stats(self):
        if messagebox.askyesno("Reset Stats", "Reset all study statistics?"):
            self.stats = {
                "total_sessions": 0,
                "total_focus_minutes": 0,
                "sessions_by_date": {},
                "longest_streak_days": 0,
            }
            save_stats(self.stats)
            messagebox.showinfo("Done", "Stats reset.")

    # ── Theme 
    def _toggle_theme(self):
        self.cfg["theme"] = "light" if self.cfg["theme"] == "dark" else "dark"
        save_config(self.cfg)
        messagebox.showinfo("Theme", "Restart FocusLock to apply the new theme.")

    def _save_cfg(self):
        self.cfg["block_websites"] = self._web_enabled.get()
        save_config(self.cfg)

    # ── Close 
    def _on_close(self):
        if self._locked:
            messagebox.showwarning("Locked", "Stop the focus session before closing!")
            return
        if self._blocker:
            self._blocker.stop()
        unblock_websites()
        self.destroy()



# Entry point

def main():
    app = FocusLockApp()
    app.mainloop()


if __name__ == "__main__":
    main()
