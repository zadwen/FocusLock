"""Pomodoro timer with work/break/long-break phases and thread-safe state."""

import threading
import time


class PomodoroTimer:
    """Threaded countdown timer that alternates between work, short break,
    and long break phases.

    - ``long_break_sec``: duration of the long break (applied every
      ``cycles_per_set`` work phases).
    - ``cycles_per_set``: how many work cycles before a long break.

    Thread-safety: all mutable state is protected by ``_lock``.  The
    ``on_tick`` / ``on_phase`` callbacks are always invoked from a
    *background* thread – use Qt signals to bounce to the main thread.
    """

    def __init__(self, work_min, break_min, on_tick=None, on_phase=None,
                 long_break_min=0, cycles_per_set=4):
        self.work_sec = work_min * 60
        self.break_sec = break_min * 60
        self.long_break_sec = long_break_min * 60 if long_break_min > 0 else self.work_sec
        self.cycles_per_set = max(1, cycles_per_set)
        self.on_tick = on_tick
        self.on_phase = on_phase

        self._rem = self.work_sec
        self._phase = "work"
        self._running = False
        self._lock = threading.Lock()
        self.cycles = 0

    # ── public read-only properties ───────────────────────────────────────
    @property
    def phase(self):
        with self._lock:
            return self._phase

    @property
    def remaining(self):
        with self._lock:
            return self._rem

    @property
    def is_running(self):
        with self._lock:
            return self._running

    @property
    def phase_total(self):
        """Return the total seconds for the current phase, including long breaks."""
        with self._lock:
            if self._phase == "work":
                return self.work_sec
            # Determine if this is a long break
            if self.cycles > 0 and self.cycles % self.cycles_per_set == 0:
                return self.long_break_sec
            return self.break_sec

    # ── controls ──────────────────────────────────────────────────────────
    def start(self):
        if self.is_running:
            return
        with self._lock:
            self._running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def pause(self):
        with self._lock:
            self._running = False

    def skip(self):
        """Skip to the next phase immediately."""
        with self._lock:
            if not self._running:
                return
            # Force rem to 0 so the loop exits and triggers _switch
            self._rem = 0

    def reset(self):
        with self._lock:
            self._running = False
            self._phase = "work"
            self._rem = self.work_sec
            self.cycles = 0
        if self.on_tick:
            self.on_tick(self.work_sec, "work")

    def set_remaining(self, seconds):
        """Overwrite remaining time, clamped to current phase total."""
        with self._lock:
            cap = self.work_sec if self._phase == "work" else self.break_sec
            self._rem = max(0, min(seconds, cap))

    def set_phase(self, phase):
        with self._lock:
            self._phase = phase

    # ── internal ──────────────────────────────────────────────────────────
    def _loop(self):
        first = True
        while True:
            with self._lock:
                if not self._running:
                    break
                if self._rem <= 0:
                    break
                rem = self._rem
                phase = self._phase
            if self.on_tick:
                self.on_tick(rem, phase)
            # Sleep first on all ticks except the initial display tick
            if first:
                first = False
            else:
                time.sleep(1)
            # After sleeping, decrement
            with self._lock:
                if not self._running:
                    break
                if self._rem <= 0:
                    break
                self._rem -= 1
        if self.is_running:
            self._switch()

    def _switch(self):
        with self._lock:
            if self._phase == "work":
                self.cycles += 1
                self._phase = "break"
                # Use long break every N cycles
                if self.cycles % self.cycles_per_set == 0:
                    self._rem = self.long_break_sec
                else:
                    self._rem = self.break_sec
            else:
                self._phase = "work"
                self._rem = self.work_sec
            phase = self._phase
            cycles = self.cycles
        if self.on_phase:
            self.on_phase(phase, cycles)
        # Automatically continue the next phase
        if self.is_running:
            threading.Thread(target=self._loop, daemon=True).start()
