"""FocusLock — a calm, local-first focus timer for Windows and Linux."""
from __future__ import annotations

import argparse
import datetime as dt
import os
from pathlib import Path
import queue
import sys
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from core import (VERSION, IS_WINDOWS, DEFAULT_APPS, PRESETS, HostsManager, Session,
                  atomic_json, data_dir, hash_password, load_config, load_stats,
                  normalize_domain, record_session, streaks, validate_app, verify_password)
from platform_support import AppBlocker, InstanceLock, notify, set_startup, startup_enabled

PALETTES = {
    "dark": {"bg": "#0d1519", "surface": "#142027", "card": "#1b2c34", "text": "#edf5f2",
             "muted": "#a0b7ba", "accent": "#b9f277", "ink": "#142018", "line": "#30434a", "danger": "#ffaaa0"},
    "light": {"bg": "#f2f5ef", "surface": "#ffffff", "card": "#e5ecdf", "text": "#182c25",
              "muted": "#50665c", "accent": "#315f24", "ink": "#ffffff", "line": "#ccd8c6", "danger": "#a7302b"},
}


class FocusLock(tk.Tk):
    def __init__(self, directory=None):
        super().__init__()
        self.directory = Path(directory) if directory else data_dir()
        self.cfg, config_warning = load_config(self.directory / "config.json")
        self.stats, stats_warning = load_stats(self.directory / "stats.json")
        self.session = None
        self.hosts = HostsManager()
        self.blocker = AppBlocker()
        self.current_page = "Focus"
        self.status_text = "Your next good hour starts here."
        self.site_error = False
        self._closing = False
        self.title("FocusLock")
        self.geometry("1040x760")
        self.minsize(940, 710)
        self.protocol("WM_DELETE_WINDOW", self.close_window)
        self._build()
        self.after(200, self._pulse)
        warnings = [w for w in (config_warning, stats_warning) if w]
        if warnings:
            self.after(400, lambda: messagebox.showwarning("Recovered settings", "\n\n".join(warnings), parent=self))
        self.after(600, self._recover_hosts)

    @property
    def active(self):
        return bool(self.session and self.session.running)

    def persist(self, stats=False):
        try:
            atomic_json(self.directory / ("stats.json" if stats else "config.json"), self.stats if stats else self.cfg)
            return True
        except OSError as exc:
            messagebox.showerror("Could not save", f"{exc}\nYour changes are still in memory.", parent=self)
            return False

    def text(self, parent, text, size=11, color="text", bold=False, bg=None, **kwargs):
        return tk.Label(parent, text=text, font=(self.font, size, "bold" if bold else "normal"),
                        bg=bg or parent.cget("bg"), fg=self.C[color], **kwargs)

    def button(self, parent, text, command, primary=False, danger=False, **kwargs):
        return tk.Button(parent, text=text, command=command, font=(self.font, 10, "bold"),
                         bg=self.C["accent"] if primary else self.C["card"],
                         fg=self.C["ink"] if primary else self.C["danger" if danger else "text"],
                         activebackground=self.C["accent"], activeforeground=self.C["ink"],
                         relief="flat", bd=0, padx=16, pady=10, cursor="hand2",
                         highlightthickness=1, highlightbackground=self.C["line"], **kwargs)

    def entry(self, parent, var, width=24):
        return tk.Entry(parent, textvariable=var, width=width, relief="flat", bd=0,
                        font=(self.font, 12), bg=self.C["card"], fg=self.C["text"],
                        insertbackground=self.C["text"], highlightthickness=1,
                        highlightbackground=self.C["line"], highlightcolor=self.C["accent"])

    def _build(self):
        for child in self.winfo_children():
            child.destroy()
        self.C = PALETTES[self.cfg["theme"]]
        self.font = "Segoe UI" if IS_WINDOWS else "DejaVu Sans"
        C = self.C
        self.configure(bg=C["bg"])
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Focus.Horizontal.TProgressbar", background=C["accent"], troughcolor=C["line"],
                        borderwidth=0, lightcolor=C["accent"], darkcolor=C["accent"])
        side = tk.Frame(self, bg=C["surface"], width=195)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        self.text(side, "FOCUSLOCK", 17, "accent", True).pack(anchor="w", padx=20, pady=(32, 3))
        self.text(side, "Make room for deep work.", 9, "muted").pack(anchor="w", padx=20, pady=(0, 38))
        self.nav = {}
        for name in ("Focus", "Blocked apps", "Websites", "Insights", "Settings"):
            b = self.button(side, name, lambda n=name: self.show_page(n), anchor="w")
            b.pack(fill="x", padx=12, pady=4)
            self.nav[name] = b
        self.button(side, "Quit FocusLock", self.quit_app).pack(side="bottom", fill="x", padx=12, pady=14)
        self.text(side, f"LOCAL FIRST  /  v{VERSION}\nby zadwen", 9, "muted", justify="left").pack(side="bottom", anchor="w", padx=20, pady=10)
        outer = tk.Frame(self, bg=C["bg"])
        outer.pack(side="left", fill="both", expand=True, padx=30, pady=25)
        head = tk.Frame(outer, bg=C["bg"])
        head.pack(fill="x", pady=(0, 20))
        self.page_title = self.text(head, "", 25, bold=True)
        self.page_title.pack(side="left")
        self.state_badge = self.text(head, "READY", 9, "accent", True, padx=12, pady=7, bg=C["card"])
        self.state_badge.pack(side="right")
        self.container = tk.Frame(outer, bg=C["bg"])
        self.container.pack(fill="both", expand=True)
        self.pages = {}
        for name in self.nav:
            self.pages[name] = tk.Frame(self.container, bg=C["bg"])
        self._focus_page()
        self._list_page("Blocked apps", "blocklist")
        self._list_page("Websites", "website_blocklist")
        self._insights_page()
        self._settings_page()
        self.status_label = self.text(outer, self.status_text, 9, "muted", anchor="w", justify="left", wraplength=680)
        self.status_label.pack(fill="x", pady=(12, 0))
        self.show_page(self.current_page)
        self._render_timer()

    def show_page(self, name):
        for page in self.pages.values():
            page.pack_forget()
        self.pages[name].pack(fill="both", expand=True)
        self.current_page = name
        self.page_title.configure(text={"Focus": "Less noise. More focus.", "Insights": "Your effort adds up."}.get(name, name))
        for n, button in self.nav.items():
            button.configure(bg=self.C["card"] if n == name else self.C["surface"],
                             fg=self.C["accent"] if n == name else self.C["muted"])
        if name == "Insights":
            self._refresh_stats()

    def _focus_page(self):
        p, C = self.pages["Focus"], self.C
        self.text(p, "One task. One timer. A little space to do your best work.", 11, "muted").pack(anchor="w", pady=(0, 18))
        self.name_var = tk.StringVar(value=self.cfg["session_name"])
        self.text(p, "WHAT ARE YOU WORKING ON?", 9, "muted", True).pack(anchor="w", pady=(0, 6))
        self.name_entry = self.entry(p, self.name_var)
        self.name_entry.pack(fill="x", ipady=9, pady=(0, 16))
        card = tk.Frame(p, bg=C["surface"], highlightthickness=1, highlightbackground=C["line"])
        card.pack(fill="x")
        self.phase_label = self.text(card, "FOCUS TIME", 10, "accent", True)
        self.phase_label.pack(pady=(18, 0))
        self.timer_label = self.text(card, "25:00", 66, bold=True)
        self.timer_label.pack()
        self.cycle_label = self.text(card, "No rush. Just begin.", 10, "muted")
        self.cycle_label.pack(pady=(0, 13))
        self.progress = ttk.Progressbar(card, style="Focus.Horizontal.TProgressbar", maximum=100)
        self.progress.pack(fill="x", padx=30, pady=(0, 16))
        actions = tk.Frame(card, bg=C["surface"])
        actions.pack(pady=(0, 20))
        self.start_button = self.button(actions, "Start focus", self.toggle_session, primary=True, width=16)
        self.start_button.pack(side="left", padx=5)
        self.pause_button = self.button(actions, "Pause", self.pause_resume, width=9)
        self.pause_button.pack(side="left", padx=5)
        plan = tk.Frame(p, bg=C["bg"])
        plan.pack(fill="x", pady=(18, 8))
        self.text(plan, "YOUR RHYTHM", 9, "muted", True).pack(anchor="w", pady=(0, 8))
        presets = tk.Frame(plan, bg=C["bg"])
        presets.pack(fill="x")
        self.preset_buttons = []
        for i, (name, times) in enumerate(PRESETS.items()):
            presets.columnconfigure(i, weight=1)
            b = self.button(presets, f"{name}\n{times[0]} / {times[1]} min", lambda t=times: self.choose_preset(t))
            b.grid(row=0, column=i, sticky="ew", padx=(0, 5))
            self.preset_buttons.append(b)
        custom = tk.Frame(plan, bg=C["bg"])
        custom.pack(fill="x", pady=(12, 0))
        self.work_var = tk.StringVar(value=str(self.cfg["pomodoro_work"]))
        self.break_var = tk.StringVar(value=str(self.cfg["pomodoro_break"]))
        for label, variable in (("Focus", self.work_var), ("Break", self.break_var)):
            self.text(custom, label, 10, "muted").pack(side="left", padx=(0, 8))
            self.entry(custom, variable, 4).pack(side="left", ipady=5, padx=(0, 8))
        self.text(custom, "minutes · 1–240 each", 9, "muted").pack(side="left")
        self.apply_button = self.button(custom, "Apply", self.apply_custom)
        self.apply_button.pack(side="right")
        self.block_summary = self.text(p, "", 10, "muted")
        self.block_summary.pack(anchor="w", pady=(13, 0))

    def _list_page(self, name, key):
        p, C = self.pages[name], self.C
        if key == "blocklist":
            note = ("Exact process names. Apps close during focus and are allowed on breaks.\n"
                    "Save your work first: closing an app can discard unsaved changes.")
        else:
            note = ("Blocks listed domains and their www versions through the hosts file.\n"
                    "Other subdomains, VPNs and cached connections may bypass this.")
        self.text(p, note, 10, "muted", justify="left", wraplength=660).pack(anchor="w", pady=(0, 14))
        if key == "website_blocklist":
            self.web_var = tk.BooleanVar(value=self.cfg["block_websites"])
            self._check(p, "Enable website blocking during focus", self.web_var, self.toggle_web).pack(anchor="w", pady=(0, 8))
            privilege = ("Run as Administrator to edit hosts. App blocking works without it." if IS_WINDOWS else
                         "Needs write access to /etc/hosts. See README for the Linux limitation.")
            self.text(p, privilege, 9, "muted", wraplength=660).pack(anchor="w", pady=(0, 14))
        box_frame = tk.Frame(p, bg=C["surface"])
        box_frame.pack(fill="both", expand=True)
        scroll = tk.Scrollbar(box_frame)
        scroll.pack(side="right", fill="y")
        box = tk.Listbox(box_frame, bg=C["surface"], fg=C["text"], selectbackground=C["accent"],
                         selectforeground=C["ink"], font=(self.font, 12), relief="flat", bd=0,
                         highlightthickness=0, yscrollcommand=scroll.set, activestyle="none",
                         selectmode="extended", exportselection=False)
        box.pack(fill="both", expand=True, padx=12, pady=12)
        scroll.configure(command=box.yview)
        for item in self.cfg[key]:
            box.insert("end", item)
        row = tk.Frame(p, bg=C["bg"])
        row.pack(fill="x", pady=(14, 0))
        self.button(row, "+ Add app" if key == "blocklist" else "+ Add website",
                    lambda: self.add_item(key, box), primary=True).pack(side="left", padx=(0, 8))
        self.button(row, "Remove selected", lambda: self.remove_items(key, box), danger=True).pack(side="left")
        self.text(p, "Lists are locked while a session is running. Stop the session to edit.", 9, "muted").pack(anchor="w", pady=12)

    def _insights_page(self):
        p = self.pages["Insights"]
        self.text(p, "Only active focus time counts. Breaks and pauses are excluded.", 11, "muted").pack(anchor="w", pady=(0, 22))
        self.stat_labels = {}
        grid = tk.Frame(p, bg=self.C["bg"])
        grid.pack(fill="x")
        for i, key in enumerate(("Focus time", "Sessions", "Current streak", "Best streak")):
            grid.columnconfigure(i % 2, weight=1)
            card = tk.Frame(grid, bg=self.C["surface"])
            card.grid(row=i // 2, column=i % 2, sticky="nsew", padx=(0, 10), pady=(0, 10))
            self.text(card, key.upper(), 9, "muted", True).pack(anchor="w", padx=20, pady=(20, 10))
            self.stat_labels[key] = self.text(card, "0", 28, "accent", True)
            self.stat_labels[key].pack(anchor="w", padx=20, pady=(0, 22))
        self.text(p, "THIS WEEK · completed sessions", 9, "muted", True).pack(anchor="w", pady=(18, 8))
        self.week_label = self.text(p, "", 11, justify="left")
        self.week_label.pack(anchor="w")
        self.button(p, "Reset saved insights", self.reset_stats, danger=True).pack(anchor="w", pady=24)

    def _check(self, parent, text, variable, command):
        return tk.Checkbutton(parent, text=text, variable=variable, command=command,
                              bg=parent.cget("bg"), fg=self.C["text"], activebackground=parent.cget("bg"),
                              activeforeground=self.C["text"], selectcolor=self.C["card"],
                              font=(self.font, 11), cursor="hand2", padx=0)

    def _settings_page(self):
        p = self.pages["Settings"]
        self.text(p, "Build a routine that works for you.", 11, "muted").pack(anchor="w", pady=(0, 18))
        for key, label in (("notify_break", "Notify me when focus or break ends"),
                           ("minimize_on_close", "Minimize to the taskbar when I close the window")):
            variable = tk.BooleanVar(value=self.cfg[key])
            self._check(p, label, variable, lambda k=key, v=variable: self.change_setting(k, v.get())).pack(anchor="w", pady=7)
        try:
            enabled = startup_enabled()
        except OSError:
            enabled = False
        self.startup_var = tk.BooleanVar(value=enabled)
        self._check(p, "Open FocusLock when I sign in", self.startup_var, self.change_startup).pack(anchor="w", pady=7)
        self.button(p, "Switch to " + ("light" if self.cfg["theme"] == "dark" else "dark") + " theme", self.toggle_theme).pack(anchor="w", pady=18)
        self.text(p, "SESSION GUARD", 9, "muted", True).pack(anchor="w", pady=(8, 6))
        self.text(p, "Passwords guard pause, stop and password changes.\nFocusLock is a self-control tool, not parental-control security.",
                  10, "muted", justify="left").pack(anchor="w", pady=(0, 14))
        for key, label in (("password_hash", "Session password"), ("parent_password_hash", "Recovery password")):
            row = tk.Frame(p, bg=self.C["surface"])
            row.pack(fill="x", pady=5)
            self.text(row, label + ("  ·  Set" if self.cfg[key] else "  ·  Not set"), 11).pack(side="left", padx=15)
            self.button(row, "Change", lambda k=key: self.change_password(k)).pack(side="right", padx=6, pady=6)
        self.text(p, "Stored on this computer only:\n" + str(self.directory), 9, "muted", justify="left", wraplength=640).pack(anchor="w", pady=18)

    def set_status(self, text, error=False):
        self.status_text = text
        self.status_label.configure(text=text, fg=self.C["danger" if error else "muted"])

    def idle_edit(self):
        if self.active:
            messagebox.showinfo("Session running", "Stop your session before changing its plan or blocklists.", parent=self)
            return False
        return True

    def choose_preset(self, values):
        if not self.idle_edit():
            return
        self.work_var.set(str(values[0]))
        self.break_var.set(str(values[1]))
        self.apply_custom()

    def apply_custom(self):
        if not self.idle_edit():
            return False
        try:
            work, rest = int(self.work_var.get()), int(self.break_var.get())
            if not 1 <= work <= 240 or not 1 <= rest <= 240:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid duration", "Enter whole minutes between 1 and 240 for both timers.", parent=self)
            return False
        self.cfg.update(pomodoro_work=work, pomodoro_break=rest)
        if not self.persist():
            return False
        self._render_timer()
        return True

    def authorize(self, prompt="Enter your session or recovery password:", recovery_only=False):
        keys = ("parent_password_hash",) if recovery_only else ("password_hash", "parent_password_hash")
        stored = [self.cfg[k] for k in keys if self.cfg[k]]
        if not stored:
            return True
        pw = simpledialog.askstring("Session guard", prompt, show="*", parent=self)
        if pw is None:
            return False
        if any(verify_password(pw, value) for value in stored):
            return True
        messagebox.showerror("Incorrect password", "The password did not match.", parent=self)
        return False

    def toggle_session(self):
        if self.active:
            self.stop_session()
            return
        if not self.apply_custom():
            return
        if self.cfg["blocklist"] and not messagebox.askokcancel("Ready to focus?",
                "Listed apps will be closed during focus. Save any work in those apps before starting.", parent=self):
            return
        self.cfg["session_name"] = self.name_var.get().strip()
        if not self.persist():
            return
        self.site_error = False
        self.session = Session(self.cfg["pomodoro_work"], self.cfg["pomodoro_break"])
        self.session.start()
        self._sync_blocking()
        self.set_status("Session started. Give this task your attention." + (" Website blocking is unavailable." if self.site_error else ""), self.site_error)
        self._render_timer()

    def _sync_blocking(self):
        focusing = self.active and not self.session.paused and self.session.phase == "work"
        self.blocker.configure(self.cfg["blocklist"], focusing)
        should_block = focusing and self.cfg["block_websites"] and not self.site_error
        try:
            if should_block and not self.hosts.active:
                self.hosts.update(self.cfg["website_blocklist"])
            elif not should_block and self.hosts.active:
                self.hosts.update()
        except (OSError, ValueError) as exc:
            self.site_error = True
            self.set_status("Website blocker needs attention. " + str(exc), True)
            messagebox.showwarning("Website blocker", f"{exc}\n\nApp blocking still works. To recover leftover rules, use the README recovery instructions.", parent=self)

    def pause_resume(self):
        if not self.active:
            return
        if self.session.paused:
            self.session.resume()
            self.set_status("Welcome back. Continue at your own pace.")
        else:
            if not self.authorize():
                return
            self.session.pause()
            self.set_status("Paused. Apps and websites are allowed until you resume.")
        self._sync_blocking()
        self._render_timer()

    def stop_session(self):
        if not self.active or not self.authorize():
            return False
        self.session.stop()
        self._sync_blocking()
        record_session(self.stats, self.session.focus_seconds)
        self.persist(stats=True)
        seconds = int(self.session.focus_seconds)
        self.set_status(f"Session saved · {seconds // 60}m {seconds % 60}s of focus." + (" Website rules remain; recovery is needed." if self.hosts.active else " Well done."), self.hosts.active)
        self._render_timer()
        return True

    def _pulse(self):
        if self._closing:
            return
        if self.active:
            changed = self.session.advance()
            if changed:
                self._sync_blocking()
                message = "Take a breath. It's break time." if self.session.phase == "break" else "Break's over. Ready to focus?"
                self.set_status(message, self.site_error)
                if self.cfg["notify_break"]:
                    notify("FocusLock", message)
                    self.bell()
        try:
            while True:
                self.set_status(self.blocker.errors.get_nowait(), True)
        except queue.Empty:
            pass
        self._render_timer()
        self.after(200, self._pulse)

    def _render_timer(self):
        active = self.active
        phase = self.session.phase if active else "work"
        paused = active and self.session.paused
        duration = self.cfg["pomodoro_work"] * 60
        self.timer_label.configure(text=self.session.display if active else f"{self.cfg['pomodoro_work']:02d}:00")
        self.phase_label.configure(text="ON PAUSE" if paused else "FOCUS TIME" if phase == "work" else "TAKE A BREAK")
        if active:
            duration = self.session.work_seconds if phase == "work" else self.session.break_seconds
            self.progress["value"] = 100 * (1 - self.session.remaining / duration)
            self.cycle_label.configure(text=f"{self.session.cycles} completed cycles · {int(self.session.focus_seconds) // 60} min focused")
        else:
            self.progress["value"] = 0
            self.cycle_label.configure(text="No rush. Just begin.")
        self.state_badge.configure(text="PAUSED" if paused else "FOCUSING" if active and phase == "work" else "ON BREAK" if active else "READY")
        self.start_button.configure(text="End session" if active else "Start focus")
        self.pause_button.configure(state="normal" if active else "disabled", text="Resume" if paused else "Pause")
        for button in self.preset_buttons + [self.apply_button]:
            button.configure(state="disabled" if active else "normal")
        self.name_entry.configure(state="disabled" if active else "normal")
        self.block_summary.configure(text=f"{len(self.cfg['blocklist'])} apps on your list  ·  Website blocking {'unavailable' if self.site_error else 'on' if self.cfg['block_websites'] else 'off'}")
        if self.current_page == "Insights":
            self._refresh_stats()

    def add_item(self, key, box):
        if not self.idle_edit():
            return
        prompt = ("Exact process name (e.g. discord.exe):" if IS_WINDOWS else "Exact process name (e.g. Discord or steam):") if key == "blocklist" else "Domain or URL (e.g. reddit.com):"
        raw = simpledialog.askstring("Add app" if key == "blocklist" else "Add website", prompt, parent=self)
        if raw is None:
            return
        try:
            value = validate_app(raw) if key == "blocklist" else normalize_domain(raw)
        except ValueError as exc:
            messagebox.showerror("Invalid entry", str(exc), parent=self)
            return
        if value.casefold() in [v.casefold() for v in self.cfg[key]]:
            self.set_status("That item is already on your list.")
            return
        self.cfg[key].append(value)
        box.insert("end", value)
        self.persist()
        self._render_timer()

    def remove_items(self, key, box):
        if not self.idle_edit():
            return
        for index in reversed(box.curselection()):
            self.cfg[key].pop(index)
            box.delete(index)
        self.persist()
        self._render_timer()

    def toggle_web(self):
        if not self.idle_edit():
            self.web_var.set(self.cfg["block_websites"])
            return
        self.cfg["block_websites"] = self.web_var.get()
        self.persist()
        self._render_timer()

    def change_password(self, key):
        if not self.idle_edit():
            return
        if not self.authorize(recovery_only=key == "parent_password_hash" and bool(self.cfg[key])):
            return
        password = simpledialog.askstring("Change password", "New password (leave empty to remove):", show="*", parent=self)
        if password is None:
            return
        if password:
            confirm = simpledialog.askstring("Confirm password", "Enter the new password again:", show="*", parent=self)
            if password != confirm:
                messagebox.showerror("Passwords differ", "Nothing was changed. Try again.", parent=self)
                return
        self.cfg[key] = hash_password(password) if password else ""
        self.persist()
        self._build()

    def change_setting(self, key, value):
        self.cfg[key] = value
        self.persist()

    def change_startup(self):
        try:
            set_startup(self.startup_var.get())
        except OSError as exc:
            self.startup_var.set(not self.startup_var.get())
            messagebox.showerror("Could not update startup", str(exc), parent=self)

    def toggle_theme(self):
        self.cfg["session_name"] = self.name_var.get()
        self.cfg["theme"] = "light" if self.cfg["theme"] == "dark" else "dark"
        self.persist()
        self._build()

    def _refresh_stats(self):
        seconds = int(self.stats["total_seconds"])
        current, best = streaks(self.stats)
        values = {"Focus time": f"{seconds // 3600}h {seconds % 3600 // 60}m",
                  "Sessions": str(int(self.stats["total_sessions"])), "Current streak": f"{current} days", "Best streak": f"{best} days"}
        for key, value in values.items():
            self.stat_labels[key].configure(text=value)
        today = dt.date.today()
        self.week_label.configure(text="   ·   ".join(f"{(today - dt.timedelta(days=i)).strftime('%a')} {self.stats['sessions_by_date'].get((today - dt.timedelta(days=i)).isoformat(), 0)}" for i in range(6, -1, -1)))

    def reset_stats(self):
        if self.idle_edit() and messagebox.askyesno("Reset insights", "Permanently clear your saved focus statistics?", parent=self):
            self.stats = {"total_sessions": 0, "total_seconds": 0, "sessions_by_date": {}}
            self.persist(stats=True)
            self._refresh_stats()

    def _recover_hosts(self):
        try:
            if self.hosts.has_block():
                self.hosts.active = True
                if messagebox.askyesno("Recover website access", "Found website rules from a previous session. Remove them now?", parent=self):
                    self.hosts.update()
                else:
                    self.set_status("Previous website rules remain. Use README recovery instructions to remove them.", True)
        except (OSError, ValueError) as exc:
            self.set_status("Could not inspect or recover website rules: " + str(exc), True)

    def close_window(self):
        if self.cfg["minimize_on_close"]:
            self.iconify()
        else:
            self.quit_app()

    def quit_app(self):
        if self.active and not self.stop_session():
            return
        if self.hosts.active:
            try:
                self.hosts.update()
            except (OSError, ValueError) as exc:
                messagebox.showerror("Website rules remain", f"{exc}\nRecover hosts using the README before quitting.", parent=self)
                return
        if not self.persist(stats=True):
            return
        self._closing = True
        self.blocker.close()
        self.destroy()


def main():
    parser = argparse.ArgumentParser(description="FocusLock for Windows and Linux")
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--recover-hosts", action="store_true", help="Remove only FocusLock website rules; requires hosts write permission")
    args = parser.parse_args()
    if args.recover_hosts:
        try:
            HostsManager().update()
            print("FocusLock website rules removed.")
            return 0
        except (OSError, ValueError) as exc:
            print(f"Recovery failed: {exc}", file=sys.stderr)
            return 1
    if sys.platform not in ("win32", "linux"):
        print("FocusLock currently supports Windows and Linux.", file=sys.stderr)
        return 1
    try:
        lock = InstanceLock(data_dir())
    except (OSError, RuntimeError) as exc:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("FocusLock", str(exc), parent=root)
        root.destroy()
        return 1
    try:
        app = FocusLock()
        app.mainloop()
    finally:
        lock.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
