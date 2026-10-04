import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from core import (Session, HostsManager, START_MARK, END_MARK, atomic_json, load_config,
                  load_stats, normalize_domain, strip_hosts, validate_app, hash_password,
                  verify_password, record_session, streaks)
from platform_support import InstanceLock, AppBlocker


class Clock:
    def __init__(self): self.now = 0
    def __call__(self): return self.now
    def add(self, seconds): self.now += seconds


class TimerTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.timer = Session(1, 1, self.clock)
        self.timer.start()

    def test_pause_does_not_count_and_resume_is_idempotent(self):
        self.clock.add(10)
        self.timer.pause()
        self.clock.add(400)
        self.timer.resume()
        self.timer.resume()
        self.clock.add(5)
        self.timer.advance()
        self.assertEqual(self.timer.focus_seconds, 15)
        self.assertEqual(self.timer.display, "00:45")

    def test_break_does_not_count_as_focus(self):
        self.clock.add(90)
        self.timer.advance()
        self.assertEqual(self.timer.phase, "break")
        self.assertEqual(self.timer.focus_seconds, 60)
        self.assertEqual(self.timer.cycles, 1)

    def test_delayed_callback_catches_multiple_phases(self):
        self.clock.add(250)
        self.assertTrue(self.timer.advance())
        self.assertEqual(self.timer.focus_seconds, 130)
        self.assertEqual(self.timer.remaining, 50)
        self.assertEqual(self.timer.cycles, 2)

    def test_stop_while_paused_does_not_count_pause(self):
        self.clock.add(12.5)
        self.timer.pause()
        self.clock.add(100)
        self.timer.stop()
        self.assertEqual(self.timer.focus_seconds, 12.5)
        self.assertFalse(self.timer.running)

    def test_start_twice_does_not_reset_clock(self):
        self.clock.add(15)
        self.timer.start()
        self.timer.advance()
        self.assertEqual(self.timer.focus_seconds, 15)


class ValidationTests(unittest.TestCase):
    def test_urls_and_idn(self):
        self.assertEqual(normalize_domain("HTTPS://Reddit.com/r/test"), "reddit.com")
        self.assertEqual(normalize_domain("bücher.de"), "xn--bcher-kva.de")

    def test_invalid_domains(self):
        for value in ("localhost", "127.0.0.1", "reddit.com\n0.0.0.0 bank.com", "*.com", "https://a.com:44", "https://user@a.com", "-a.com", "a..com"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_domain(value)

    def test_protected_apps_and_paths(self):
        for value in ("python3.12", "explorer.exe", "systemd", "*.exe", "/bin/steam", "x\ny"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_app(value)
        self.assertEqual(validate_app(" Discord "), "Discord")

    def test_password_salts_and_legacy_migration(self):
        first, second = hash_password("test123"), hash_password("test123")
        self.assertNotEqual(first, second)
        self.assertTrue(verify_password("test123", first))
        self.assertFalse(verify_password("wrong", first))
        self.assertTrue(verify_password("old", hashlib.sha256(b"old").hexdigest()))
        self.assertFalse(verify_password("x", "pbkdf2_sha256$9999999999$x$x"))


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "config.json"

    def test_invalid_json_is_preserved(self):
        self.path.write_text("{broken")
        cfg, warning = load_config(self.path)
        self.assertTrue(warning)
        self.assertEqual(cfg["pomodoro_work"], 25)
        self.assertTrue(list(self.path.parent.glob("*.invalid-*")))

    def test_bad_types_and_unsafe_entries(self):
        atomic_json(self.path, {"pomodoro_work": True, "pomodoro_break": -1,
                    "blocklist": [5, "python3", "steam", "STEAM"], "block_websites": "yes"})
        cfg, _ = load_config(self.path)
        self.assertEqual(cfg["pomodoro_work"], 25)
        self.assertEqual(cfg["pomodoro_break"], 5)
        self.assertEqual(cfg["blocklist"], ["steam"])
        self.assertFalse(cfg["block_websites"])

    def test_atomic_failure_preserves_original(self):
        atomic_json(self.path, {"old": True})
        with patch("core.os.replace", side_effect=OSError("disk failed")):
            with self.assertRaises(OSError): atomic_json(self.path, {"new": True})
        self.assertEqual(json.loads(self.path.read_text()), {"old": True})
        self.assertEqual(len(list(self.path.parent.iterdir())), 1)

    def test_legacy_stats_and_expired_streak(self):
        atomic_json(self.path, {"total_minutes": 10, "total_sessions": 2,
                               "sessions_by_date": {"2026-10-01": 1, "2026-10-02": 1, "bad": 2}})
        stats, _ = load_stats(self.path)
        self.assertEqual(stats["total_seconds"], 600)
        self.assertEqual(streaks(stats, dt.date(2026, 10, 4)), (0, 2))
        record_session(stats, 20, dt.date(2026, 10, 4))
        self.assertEqual(stats["total_seconds"], 620)
        self.assertEqual(streaks(stats, dt.date(2026, 10, 4)), (1, 2))

    def test_no_fake_minute_for_short_session(self):
        stats, _ = load_stats(self.path)
        record_session(stats, 3)
        self.assertEqual(stats["total_seconds"], 3)
        self.assertEqual(stats["total_sessions"], 1)


class HostsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "hosts"
        self.original = "# custom config\r\n127.0.0.1 localhost\r\n10.0.0.2 private.test\r\n"
        self.path.write_bytes(self.original.encode())
        self.manager = HostsManager(self.path)

    def test_apply_idempotent_and_restore_exact_bytes(self):
        self.manager.update(["reddit.com"])
        first = self.path.read_bytes()
        self.manager.update(["reddit.com"])
        self.assertEqual(first, self.path.read_bytes())
        self.assertIn(b"::1 reddit.com", first)
        self.manager.update()
        self.assertEqual(self.original.encode(), self.path.read_bytes())
        self.assertEqual(self.original.encode(), self.path.with_name("hosts.focuslock-backup").read_bytes())

    def test_no_rewrite_if_no_block(self):
        with patch("pathlib.Path.open", wraps=self.path.open) as opener:
            self.manager.update()
        self.assertEqual(opener.call_count, 1)

    def test_malformed_markers_never_truncate_hosts(self):
        for value in (START_MARK + "\nkeep", END_MARK, START_MARK + "\n" + START_MARK,
                      START_MARK + "\n10.0.0.2 private\n" + END_MARK):
            with self.subTest(value=value), self.assertRaises(ValueError): strip_hosts(value)

    def test_invalid_input_does_not_modify_hosts(self):
        with self.assertRaises(ValueError): self.manager.update(["reddit.com\nevil"])
        self.assertEqual(self.path.read_bytes(), self.original.encode())

    def test_marker_in_comment_is_not_treated_as_block(self):
        text = "# docs mention " + START_MARK + " here\n127.0.0.1 localhost\n"
        self.assertEqual(strip_hosts(text), text)


class PlatformTests(unittest.TestCase):
    def test_single_instance_released_on_close(self):
        with tempfile.TemporaryDirectory() as d:
            one = InstanceLock(Path(d))
            try:
                with self.assertRaises(RuntimeError): InstanceLock(Path(d))
            finally: one.close()
            two = InstanceLock(Path(d))
            two.close()

    def test_windows_lock_acquisition_never_reads_locked_bytes(self):
        handle = MagicMock()
        handle.read.side_effect = PermissionError("Windows denies reads of another handle's locked bytes")
        handle.write.side_effect = PermissionError("Windows denies writes of another handle's locked bytes")
        backend = SimpleNamespace(LK_NBLCK=2, locking=MagicMock())
        with tempfile.TemporaryDirectory() as d, patch("platform_support.IS_WINDOWS", True), \
                patch.dict(sys.modules, {"msvcrt": backend}), patch("pathlib.Path.open", return_value=handle):
            lock = InstanceLock(Path(d))
            lock.close()
        backend.locking.assert_called_once_with(handle.fileno.return_value, 2, 1)
        handle.read.assert_not_called()
        handle.write.assert_not_called()
        handle.close.assert_called_once()

    def test_windows_lock_contention_closes_failed_handle(self):
        handle = MagicMock()
        handle.read.side_effect = PermissionError("locked byte")
        backend = SimpleNamespace(LK_NBLCK=2, locking=MagicMock(side_effect=PermissionError("already locked")))
        with tempfile.TemporaryDirectory() as d, patch("platform_support.IS_WINDOWS", True), \
                patch.dict(sys.modules, {"msvcrt": backend}), patch("pathlib.Path.open", return_value=handle):
            with self.assertRaises(RuntimeError):
                InstanceLock(Path(d))
        handle.close.assert_called_once()
        handle.read.assert_not_called()

    def test_reconfigure_does_not_spawn_workers(self):
        worker = AppBlocker()
        thread = worker.thread
        try:
            for _ in range(20):
                worker.configure([], True)
                worker.configure([], False)
            self.assertIs(thread, worker.thread)
        finally: worker.close()
        self.assertFalse(thread.is_alive())


if __name__ == "__main__":
    unittest.main()
