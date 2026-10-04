"""UI regression tests. Use Xvfb on headless Linux; never touch system hosts/processes."""
import os
from pathlib import Path
import sys
import tempfile
import tkinter as tk
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from core import HostsManager, hash_password
from focuslock import FocusLock


class UITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            root = tk.Tk()
            root.destroy()
        except tk.TclError as exc:
            if os.environ.get("FOCUSLOCK_REQUIRE_UI_TESTS") == "1":
                raise
            raise unittest.SkipTest(f"A graphical display is required: {exc}")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        path = Path(self.temp.name) / "hosts"
        path.write_text("127.0.0.1 localhost\n")
        self.hosts = HostsManager(path)
        self.patches = [patch("focuslock.AppBlocker"), patch("focuslock.HostsManager", return_value=self.hosts),
                        patch("focuslock.startup_enabled", return_value=False),
                        patch("focuslock.notify"), patch("focuslock.messagebox"), patch("focuslock.simpledialog")]
        self.mocks = [p.start() for p in self.patches]
        self.addCleanup(lambda: [p.stop() for p in reversed(self.patches)])
        self.app = FocusLock(self.temp.name)
        self.app.blocker.errors = __import__("queue").Queue()
        self.app.cfg["blocklist"] = []
        self.app.update()
        self.addCleanup(self.cleanup_app)

    def cleanup_app(self):
        try:
            self.app._closing = True
            for callback in self.app.tk.splitlist(self.app.tk.call("after", "info")):
                self.app.after_cancel(callback)
            self.app.destroy()
        except tk.TclError:
            pass

    def test_session_pause_resume_stop_and_hosts(self):
        self.app.cfg["block_websites"] = True
        self.app.toggle_session()
        self.assertTrue(self.hosts.active)
        self.app.pause_resume()
        self.assertTrue(self.app.session.paused)
        self.assertFalse(self.hosts.active)
        self.app.pause_resume()
        self.assertTrue(self.hosts.active)
        self.app.session.focus_seconds = 12.5
        self.app.stop_session()
        self.assertFalse(self.hosts.active)
        self.assertEqual(self.app.stats["total_sessions"], 1)
        self.assertLess(self.app.stats["total_seconds"], 13)

    def test_break_releases_apps_and_sites(self):
        self.app.cfg["block_websites"] = True
        self.app.toggle_session()
        self.app.session.phase = "break"
        self.app._sync_blocking()
        self.assertFalse(self.hosts.active)
        self.app.blocker.configure.assert_called_with([], False)
        self.app.pause_resume()
        self.app.pause_resume()
        self.app.blocker.configure.assert_called_with([], False)

    def test_password_guards_pause_and_password_changes(self):
        self.app.cfg["password_hash"] = hash_password("secret")
        self.app.toggle_session()
        self.mocks[-1].askstring.return_value = "wrong"
        self.app.pause_resume()
        self.assertFalse(self.app.session.paused)
        self.app.change_password("password_hash")
        self.assertTrue(self.app.cfg["password_hash"])
        self.mocks[-1].askstring.return_value = "secret"
        self.app.pause_resume()
        self.assertTrue(self.app.session.paused)

    def test_theme_change_preserves_active_session(self):
        self.app.toggle_session()
        session = self.app.session
        self.app.toggle_theme()
        self.app.update()
        self.assertIs(self.app.session, session)
        self.assertEqual(self.app.cfg["theme"], "light")
        self.assertEqual(self.app.start_button.cget("text"), "End session")

    def test_invalid_custom_duration_does_not_start(self):
        self.app.work_var.set("0")
        self.app.toggle_session()
        self.assertFalse(self.app.active)
        self.mocks[-2].showerror.assert_called()

    def test_layout_minimum_size_has_visible_controls(self):
        self.app.geometry("940x710")
        self.app.update()
        for name in self.app.pages:
            self.app.show_page(name)
            self.app.update()
            page = self.app.pages[name]
            for child in page.winfo_children():
                if child.winfo_ismapped():
                    self.assertLessEqual(child.winfo_y() + child.winfo_height(), page.winfo_height() + 2,
                                         f"{name}: {child} overflows page vertically")
