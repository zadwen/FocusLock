"""FocusLock's portable, UI-independent session and storage logic."""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import secrets
import sys
import tempfile
import time
from urllib.parse import urlsplit

VERSION = "2.0.0"
IS_WINDOWS = sys.platform == "win32"
DEFAULT_APPS = (["steam.exe", "steamwebhelper.exe", "discord.exe", "EpicGamesLauncher.exe",
                 "Battle.net.exe", "Spotify.exe"] if IS_WINDOWS else
                ["steam", "steamwebhelper", "Discord", "discord", "spotify"])
DEFAULT_SITES = ["youtube.com", "reddit.com", "twitch.tv", "instagram.com", "tiktok.com"]
PRESETS = {"Classic": (25, 5), "Long focus": (50, 10), "Quick sprint": (15, 3), "Deep work": (90, 20)}
PROTECTED = {"focuslock", "focuslock.exe", "python", "python3", "pythonw.exe", "python.exe",
             "system", "systemd", "init", "explorer.exe", "winlogon.exe", "csrss.exe",
             "services.exe", "lsass.exe", "svchost.exe", "dwm.exe", "gnome-shell",
             "plasmashell", "xorg", "xwayland", "bash", "sh", "sudo", "pkexec"}
START_MARK = "# FocusLock-START"
END_MARK = "# FocusLock-END"


def data_dir():
    if IS_WINDOWS:
        return Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming")) / "FocusLock"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "FocusLock"


def defaults():
    return {"blocklist": DEFAULT_APPS[:], "website_blocklist": DEFAULT_SITES[:],
            "password_hash": "", "parent_password_hash": "", "block_websites": False,
            "pomodoro_work": 25, "pomodoro_break": 5, "theme": "dark",
            "notify_break": True, "session_name": "", "minimize_on_close": False}


def atomic_json(path, value):
    """Never leave partially-written configuration after a crash."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read_json(path):
    path = Path(path)
    if not path.exists():
        return {}, None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("Expected a JSON object")
        return value, None
    except (OSError, ValueError) as exc:
        # Keep the original for diagnosis; do not silently overwrite corruption.
        backup = path.with_name(path.name + ".invalid-" + str(time.time_ns()))
        try:
            backup.write_bytes(path.read_bytes())
        except OSError:
            pass
        return {}, f"Could not read {path.name}: {exc}. Defaults loaded; a backup was attempted."


def valid_minutes(value, fallback):
    return value if type(value) is int and 1 <= value <= 240 else fallback


def validate_app(value):
    value = value.strip()
    if (not value or len(value) > 128 or any(c in value for c in '/\\\n\r\t*?"')
            or any(ord(c) < 32 for c in value)):
        raise ValueError("Use an exact process name, not a path or wildcard.")
    if value.casefold() in PROTECTED or re.fullmatch(r"python(?:w|\d+(?:\.\d+)*)?(?:\.exe)?", value, re.I):
        raise ValueError("That process is protected to keep your desktop and FocusLock running.")
    return value


def normalize_domain(value):
    value = value.strip()
    if not value or any(c.isspace() for c in value):
        raise ValueError("Enter one domain or website URL, with no whitespace.")
    try:
        parsed = urlsplit(value if "://" in value else "https://" + value)
        if parsed.scheme not in ("http", "https") or parsed.username or parsed.password or parsed.port:
            raise ValueError("Use an HTTP(S) domain without credentials or a port.")
        host = (parsed.hostname or "").rstrip(".").encode("idna").decode("ascii").lower()
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Enter a valid website domain, such as reddit.com.") from exc
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("Enter a domain name, not an IP address.")
    if host == "localhost" or "." not in host or len(host) > 253:
        raise ValueError("Enter a full domain, such as reddit.com.")
    if not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", p) for p in host.split(".")):
        raise ValueError("Invalid domain name.")
    return host


def load_config(path):
    raw, warning = read_json(path)
    cfg = defaults()
    for key in ("password_hash", "parent_password_hash", "session_name"):
        if isinstance(raw.get(key), str):
            cfg[key] = raw[key]
    for key in ("block_websites", "notify_break", "minimize_on_close"):
        if type(raw.get(key)) is bool:
            cfg[key] = raw[key]
    if raw.get("theme") in ("dark", "light"):
        cfg["theme"] = raw["theme"]
    for key in ("pomodoro_work", "pomodoro_break"):
        cfg[key] = valid_minutes(raw.get(key), cfg[key])
    for key, validator in (("blocklist", validate_app), ("website_blocklist", normalize_domain)):
        if isinstance(raw.get(key), list):
            cfg[key] = []
            for value in raw[key]:
                try:
                    item = validator(value) if isinstance(value, str) else None
                    if item and item.casefold() not in [s.casefold() for s in cfg[key]]:
                        cfg[key].append(item)
                except ValueError:
                    pass
    return cfg, warning


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600_000).hex()
    return f"pbkdf2_sha256$600000${salt}${digest}"


def verify_password(password, stored):
    if not stored:
        return False
    if re.fullmatch(r"[a-fA-F0-9]{64}", stored):
        return hmac.compare_digest(hashlib.sha256(password.encode()).hexdigest(), stored.lower())
    try:
        kind, iterations, salt, digest = stored.split("$")
        count = int(iterations)
        if kind != "pbkdf2_sha256" or not 100_000 <= count <= 2_000_000:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), count).hex()
        return hmac.compare_digest(actual, digest)
    except (ValueError, TypeError):
        return False


def strip_hosts(content):
    """Remove only complete, exact marker sections; preserve every unrelated byte."""
    lines = content.splitlines(keepends=True)
    output, section = [], None
    for line in lines:
        marker = line.strip()
        if marker == START_MARK:
            if section is not None:
                raise ValueError("Nested FocusLock hosts markers. Repair the file manually before continuing.")
            section = []
        elif marker == END_MARK:
            if section is None:
                raise ValueError("Unmatched FocusLock hosts marker. No changes made.")
            section = None
        elif section is None:
            output.append(line)
        else:
            # Do not erase unrelated records accidentally placed in our section.
            entry = line.split("#", 1)[0].split()
            if entry and (len(entry) != 2 or entry[0] not in ("127.0.0.1", "0.0.0.0", "::1")):
                raise ValueError("Unexpected entry in FocusLock hosts section. No changes made.")
    if section is not None:
        raise ValueError("Unclosed FocusLock hosts marker. No changes made.")
    return "".join(output)


class HostsManager:
    def __init__(self, path=None):
        self.path = Path(path) if path else (Path(os.environ.get("SystemRoot", r"C:\Windows")) /
                    "System32/drivers/etc/hosts" if IS_WINDOWS else Path("/etc/hosts"))
        self.active = False

    def has_block(self):
        return START_MARK in self.path.read_text(encoding="utf-8").splitlines()

    def update(self, domains=()):
        domains = [normalize_domain(d) for d in domains]
        with self.path.open("r", encoding="utf-8", newline="") as f:
            original = f.read()
        clean = strip_hosts(original)
        result = clean
        if domains:
            names = sorted({n for d in domains for n in ([d] if d.startswith("www.") else [d, "www." + d])})
            result += ("" if clean.endswith("\n") or not clean else "\n") + START_MARK + "\n"
            result += "".join(f"127.0.0.1 {d}\n::1 {d}\n" for d in names) + END_MARK + "\n"
        if result != original:
            # First backup is kept, never overwritten by already-blocked contents.
            backup = self.path.with_name(self.path.name + ".focuslock-backup")
            if not backup.exists():
                with backup.open("x", encoding="utf-8", newline="") as f:
                    f.write(original)
            # r+ preserves hosts ownership, ACLs, and symlinks. Check for external edits.
            with self.path.open("r+", encoding="utf-8", newline="") as f:
                if f.read() != original:
                    raise OSError("Hosts file changed outside FocusLock. Retry the operation.")
                f.seek(0)
                f.write(result)
                f.truncate()
                f.flush()
                os.fsync(f.fileno())
        self.active = bool(domains)


class Session:
    """Single-thread timer. Call advance from Tk's event loop; time is monotonic."""
    def __init__(self, work_minutes, break_minutes, clock=time.monotonic):
        self.work_seconds = work_minutes * 60
        self.break_seconds = break_minutes * 60
        if min(self.work_seconds, self.break_seconds) <= 0:
            raise ValueError("Durations must be positive")
        self.clock = clock
        self.phase = "work"
        self.remaining = float(self.work_seconds)
        self.focus_seconds = 0.0
        self.cycles = 0
        self.running = False
        self.paused = False
        self._last = None

    def start(self):
        if self.running:
            return
        self.running, self.paused = True, False
        self._last = self.clock()

    def advance(self):
        if not self.running or self.paused:
            return False
        now = self.clock()
        delta, self._last = max(0.0, now - self._last), now
        changed = False
        while delta > 0:
            used = min(delta, self.remaining)
            if self.phase == "work":
                self.focus_seconds += used
            self.remaining -= used
            delta -= used
            if self.remaining <= 1e-9:
                if self.phase == "work":
                    self.cycles += 1
                    self.phase = "break"
                    self.remaining = float(self.break_seconds)
                else:
                    self.phase = "work"
                    self.remaining = float(self.work_seconds)
                changed = True
        return changed

    def pause(self):
        self.advance()
        self.paused = True

    def resume(self):
        if self.running and self.paused:
            self._last = self.clock()
            self.paused = False

    def stop(self):
        self.advance()
        self.running = False

    @property
    def display(self):
        minutes, seconds = divmod(math.ceil(self.remaining), 60)
        return f"{minutes:02d}:{seconds:02d}"


def load_stats(path):
    raw, warning = read_json(path)
    stats = {"total_sessions": 0, "total_seconds": 0, "sessions_by_date": {}}
    for key in ("total_sessions", "total_seconds"):
        value = raw.get(key)
        if type(value) in (int, float) and math.isfinite(value) and value >= 0:
            stats[key] = value
    if "total_seconds" not in raw:
        legacy = raw.get("total_minutes", 0)
        if type(legacy) in (int, float) and math.isfinite(legacy) and legacy >= 0:
            stats["total_seconds"] = legacy * 60
    if isinstance(raw.get("sessions_by_date"), dict):
        for date, count in raw["sessions_by_date"].items():
            try:
                dt.date.fromisoformat(date)
                if type(count) is int and count > 0:
                    stats["sessions_by_date"][date] = count
            except (ValueError, TypeError):
                pass
    return stats, warning


def record_session(stats, seconds, today=None):
    if seconds < 1:
        return
    date = (today or dt.date.today()).isoformat()
    stats["total_sessions"] += 1
    stats["total_seconds"] += seconds
    stats["sessions_by_date"][date] = stats["sessions_by_date"].get(date, 0) + 1


def streaks(stats, today=None):
    today = today or dt.date.today()
    dates = sorted(dt.date.fromisoformat(d) for d in stats["sessions_by_date"])
    best, length, previous = 0, 0, None
    for date in dates:
        length = length + 1 if previous and date - previous == dt.timedelta(days=1) else 1
        best, previous = max(best, length), date
    current = length if previous in (today, today - dt.timedelta(days=1)) else 0
    return current, best
