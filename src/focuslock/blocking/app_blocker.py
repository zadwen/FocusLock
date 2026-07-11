"""Force-kill blocked processes during focus sessions."""

import subprocess
import threading
import time


class AppBlocker:
    """Monitors running processes and kills any that are in the enabled set.

    Only one monitoring thread runs at a time – calling ``start()`` while
    already running is a safe no-op.
    """

    def __init__(self):
        self._enabled = set()
        self._running = False
        self._lock = threading.Lock()

    def set_enabled_apps(self, apps):
        """Replace the set of exe names that should be killed."""
        with self._lock:
            self._enabled = {a.lower() for a in apps}

    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            self._kill()
            time.sleep(2)

    def _kill(self):
        with self._lock:
            targets = set(self._enabled)
        if not targets:
            return
        try:
            result = subprocess.run(
                ["tasklist", "/fo", "csv", "/nh"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in result.stdout.splitlines():
                parts = line.strip().strip('"').split('","')
                if len(parts) < 2:
                    continue
                if parts[0].lower() in targets:
                    subprocess.run(
                        ["taskkill", "/F", "/PID", parts[1]],
                        capture_output=True,
                    )
        except Exception:
            pass
