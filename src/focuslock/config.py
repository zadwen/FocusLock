"""SQLAlchemy ORM-based persistent storage for FocusLock.

Uses SQLAlchemy 2.0 declarative models on top of SQLite with WAL mode.
Automatically migrates data from legacy JSON files on first run.
"""

import json
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    Boolean, Column, Integer, String, Text, func, select, create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, Mapped, mapped_column

from .constants import DEFAULT_APPS, DEFAULT_SITES

DATA_DIR = Path(os.getenv("APPDATA", ".")) / "FocusLock"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_FILE = DATA_DIR / "focuslock.db"
LEGACY_CONFIG = DATA_DIR / "config.json"
LEGACY_STATS = DATA_DIR / "stats.json"

_DEFAULTS = {
    "theme": "dark",
    "preset": "Classic (25/5)",
    "session_name": "",
    "minimize_to_tray": True,
    "notify_break": True,
    "password_hash": "",
    "parent_password_hash": "",
    "block_websites": False,
    "pomodoro_work": 25,
    "pomodoro_break": 5,
}


# ── ORM models ──────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class App(Base):
    __tablename__ = "apps"

    exe: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Site(Base):
    __tablename__ = "sites"

    domain: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class DailyStat(Base):
    __tablename__ = "daily_stats"

    date: Mapped[str] = mapped_column(String, primary_key=True)
    sessions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


# ── Storage facade ──────────────────────────────────────────────────────
class Storage:
    """High-level storage API backed by SQLAlchemy + SQLite.

    Provides typed methods for every entity.  All writes are committed
    immediately (SQLite autocommit via ``Session``).
    """

    def __init__(self):
        self._engine = create_engine(
            f"sqlite:///{DB_FILE}",
            echo=False,
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(self._engine)
        self._session_factory = Session(bind=self._engine)
        self._migrate()

    # ── helpers ───────────────────────────────────────────────────────────
    @property
    def _db(self) -> Session:
        return self._session_factory

    def _commit(self):
        self._db.commit()

    # ── one-time migration from legacy JSON ───────────────────────────────
    def _migrate(self):
        if self.get("theme") is not None:
            return  # already migrated

        try:
            if LEGACY_CONFIG.exists():
                old = json.loads(LEGACY_CONFIG.read_text(encoding="utf-8"))
                for key in _DEFAULTS:
                    if key in old:
                        self.set(key, old[key])
                for exe in old.get("blocklist", []):
                    meta = old.get("blocklist_meta", {}).get(exe, {})
                    self.add_app(exe, meta.get("name", exe), meta.get("enabled", True))
                for domain in old.get("website_blocklist", []):
                    meta = old.get("website_blocklist_meta", {}).get(domain, {})
                    self.add_site(domain, meta.get("name", domain), meta.get("enabled", True))
        except Exception:
            pass

        try:
            if LEGACY_STATS.exists():
                old = json.loads(LEGACY_STATS.read_text(encoding="utf-8"))
                for d, data in old.get("sessions_by_date", {}).items():
                    if isinstance(data, dict):
                        self._record_raw(d, data.get("sessions", 0), data.get("minutes", 0))
        except Exception:
            pass

        self._seed_defaults()

    def _seed_defaults(self):
        """Pre-populate empty blocklists with sensible defaults."""
        if not self._db.execute(select(App)).scalars().first():
            for exe in DEFAULT_APPS:
                self._db.add(App(exe=exe, name=exe.replace(".exe", ""), enabled=True))
            self._commit()
        if not self._db.execute(select(Site)).scalars().first():
            for domain in DEFAULT_SITES:
                self._db.add(Site(domain=domain, name=domain, enabled=True))
            self._commit()

    # ── settings ──────────────────────────────────────────────────────────
    def get(self, key: str, default=None):
        row = self._db.get(Setting, key)
        if row is None:
            return _DEFAULTS.get(key, default)
        try:
            return json.loads(row.value)
        except (json.JSONDecodeError, TypeError):
            return row.value

    def set(self, key: str, value):
        existing = self._db.get(Setting, key)
        serialized = json.dumps(value)
        if existing:
            existing.value = serialized
        else:
            self._db.add(Setting(key=key, value=serialized))
        self._commit()

    # ── apps ──────────────────────────────────────────────────────────────
    def get_apps(self) -> list[dict]:
        rows = self._db.execute(select(App).order_by(App.name)).scalars().all()
        return [{"exe": r.exe, "name": r.name, "enabled": r.enabled} for r in rows]

    def get_enabled_apps(self) -> list[str]:
        rows = self._db.execute(
            select(App.exe).where(App.enabled.is_(True))
        ).scalars().all()
        return list(rows)

    def add_app(self, exe: str, name: str | None = None, enabled: bool = True):
        existing = self._db.get(App, exe)
        if existing:
            existing.name = name or exe
            existing.enabled = enabled
        else:
            self._db.add(App(exe=exe, name=name or exe, enabled=enabled))
        self._commit()

    def remove_app(self, exe: str):
        obj = self._db.get(App, exe)
        if obj:
            self._db.delete(obj)
            self._commit()

    def toggle_app(self, exe: str, enabled: bool):
        obj = self._db.get(App, exe)
        if obj:
            obj.enabled = enabled
            self._commit()

    # ── sites ─────────────────────────────────────────────────────────────
    def get_sites(self) -> list[dict]:
        rows = self._db.execute(select(Site).order_by(Site.name)).scalars().all()
        return [{"domain": r.domain, "name": r.name, "enabled": r.enabled} for r in rows]

    def get_enabled_sites(self) -> list[str]:
        rows = self._db.execute(
            select(Site.domain).where(Site.enabled.is_(True))
        ).scalars().all()
        return list(rows)

    def add_site(self, domain: str, name: str | None = None, enabled: bool = True):
        existing = self._db.get(Site, domain)
        if existing:
            existing.name = name or domain
            existing.enabled = enabled
        else:
            self._db.add(Site(domain=domain, name=name or domain, enabled=enabled))
        self._commit()

    def remove_site(self, domain: str):
        obj = self._db.get(Site, domain)
        if obj:
            self._db.delete(obj)
            self._commit()

    def toggle_site(self, domain: str, enabled: bool):
        obj = self._db.get(Site, domain)
        if obj:
            obj.enabled = enabled
            self._commit()

    # ── stats ─────────────────────────────────────────────────────────────
    def record_session(self, work_minutes: int = 25):
        today = date.today().isoformat()
        existing = self._db.get(DailyStat, today)
        if existing:
            existing.sessions += 1
            existing.minutes += work_minutes
        else:
            self._db.add(DailyStat(date=today, sessions=1, minutes=work_minutes))
        self._commit()

    def _record_raw(self, date_str: str, sessions: int, minutes: int):
        existing = self._db.get(DailyStat, date_str)
        if existing:
            existing.sessions += sessions
            existing.minutes += minutes
        else:
            self._db.add(DailyStat(date=date_str, sessions=sessions, minutes=minutes))
        self._commit()

    def get_total_stats(self) -> tuple[int, int]:
        row = self._db.execute(
            select(
                func.coalesce(func.sum(DailyStat.sessions), 0),
                func.coalesce(func.sum(DailyStat.minutes), 0),
            )
        ).one()
        return int(row[0]), int(row[1])

    def get_daily_stats(self, days: int = 7) -> dict[str, dict]:
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        rows = self._db.execute(
            select(DailyStat).where(DailyStat.date >= cutoff)
        ).scalars().all()
        return {r.date: {"sessions": r.sessions, "minutes": r.minutes} for r in rows}

    def get_streak(self) -> tuple[int, int]:
        rows = self._db.execute(
            select(DailyStat.date).order_by(DailyStat.date.desc())
        ).scalars().all()
        if not rows:
            return 0, 0

        all_dates = sorted(set(date.fromisoformat(d) for d in rows))
        today = date.today()
        date_set = set(all_dates)

        # Current streak
        current = 0
        check = today
        if today not in date_set and (today - timedelta(days=1)) not in date_set:
            current = 0
        else:
            if today not in date_set:
                check = today - timedelta(days=1)
            while check in date_set:
                current += 1
                check -= timedelta(days=1)

        # Longest streak
        longest = 0
        streak = 1
        for i in range(1, len(all_dates)):
            if all_dates[i] - all_dates[i - 1] == timedelta(days=1):
                streak += 1
            else:
                longest = max(longest, streak)
                streak = 1
        longest = max(longest, streak, current)

        return current, longest

    def close(self):
        self._db.close()
