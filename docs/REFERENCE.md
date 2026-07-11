# FocusLock v3.0.0 — Complete Reference

## What Is It

A PySide6 desktop Pomodoro timer + focus app for Windows. Blocks distracting apps/websites during work sessions, tracks stats, supports custom durations, long breaks, sound alerts, password protection, and dark/light themes.

---

## Project Structure

```
FocusLock/
├── src/
│   ├── focuslock_app.py              # Main entry point (all UI + logic)
│   └── focuslock/                    # Core package
│       ├── __init__.py               # APP_NAME, VERSION exports
│       ├── constants.py              # App name, version, themes, presets, defaults
│       ├── config.py                 # SQLAlchemy ORM (SQLite DB at %APPDATA%/FocusLock/)
│       ├── core/
│       │   ├── timer.py              # Thread-safe PomodoroTimer
│       │   └── security.py           # Password hashing (salted)
│       ├── blocking/
│       │   ├── app_blocker.py        # Kills/blocks processes via psutil
│       │   └── website_blocker.py    # Modifies Windows hosts file
│       ├── platform/
│       │   ├── startup.py            # Windows registry Run key
│       │   ├── notifications.py      # Qt tray + PowerShell toast
│       │   └── subprocess_patch.py   # Hides console windows on subprocess calls
│       └── ui/
│           ├── widgets.py            # Theme, CircularTimer, BarChart, ToggleButton, etc.
│           └── dialogs.py            # AppPickerDialog, SitePickerDialog
├── scripts/
│   ├── version.py                    # Single source of truth for version
│   ├── build.py                      # Nuitka build orchestrator
│   ├── clean.py                      # Build artifact cleanup
│   └── release.py                    # Release packaging
├── installer/
│   └── focuslock.iss                 # Inno Setup installer script
├── .github/workflows/build.yml        # GitHub Actions CI/CD
├── requirements.txt                  # Python dependencies
├── requirements-build.txt            # Build-time dependencies
├── docs/
│   ├── BUILD.md                      # Build system technical reference
│   ├── REFERENCE.md                  # This file
│   └── CHANGELOG.md                  # Version history
├── LICENSE
└── README.md
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.10+ |
| UI Framework | PySide6 (Qt6) |
| Database | SQLite via SQLAlchemy 2.0 ORM |
| Process mgmt | psutil |
| Build | Nuitka 4.x |
| Platform | Windows 10/11 |

---

## Features

### Timer
- 5 presets: Classic (25/5), Extended Focus (50/10), Sprint (15/3), Deep Work (90/20), Custom
- Custom work/break/long-break/cycles via spinboxes
- Long break after N cycles (configurable)
- Skip button to jump to next phase
- Auto-start toggle (pause between phases)
- Cycle counter: "Pomodoro N of M"
- Circular progress ring with phase colors (purple=work, green=break)

### Blocking
- App blocker: kills processes by name during work
- Website blocker: modifies hosts file to block domains
- Per-item enable/disable toggles
- Add custom apps/sites via picker dialogs

### Settings
- Start with Windows (registry)
- Minimize to tray
- Notify on break (Windows toast)
- Sound alerts on phase change
- Block websites during focus toggle
- Auto-start next phase toggle
- Session name

### Security
- Session password (locks pause/stop)
- Parent password (locks settings/reset/clear passwords)

### Stats
- Total sessions, focus time, current streak
- 7-day bar chart

### Themes
- Dark: deep purple accent (#8b5cf6)
- Light: purple accent (#7c3aed)

---

## Database

**Location:** `%APPDATA%/FocusLock/focuslock.db` (SQLite, WAL mode)

**Tables (SQLAlchemy ORM):**
- `settings` — key-value store for all preferences
- `apps` — blocked applications (exe, name, enabled)
- `sites` — blocked websites (domain, name, enabled)
- `daily_stats` — date, session_count, total_minutes

**Auto-migration:** On first run, imports from legacy `config.json` + `stats.json` if they exist.

**Default seeding:** When tables are empty, seeds 8 default apps + 10 default sites.

---

## How to Run from Source

```bash
# From project root
python ./src/focuslock_app.py
```

No special setup needed if dependencies are installed. The app creates the DB automatically on first run.

---

## Build System

### Prerequisites
- Python 3.10+ with pip
- Packages: `pip install -r requirements.txt`
- Build packages: `pip install nuitka ordered-set zstandard`

### Build Commands

```bash
# Development build (fast, minimal optimization)
python scripts/build.py --development

# Release build (LTO, metadata, icon)
python scripts/build.py --release

# Debug build (symbols, debug info)
python scripts/build.py --debug

# Clean all build artifacts
python scripts/clean.py
python scripts/clean.py --all    # Also clean __pycache__

# Package for release
python scripts/release.py
python scripts/release.py --zip  # Also create zip archive
python scripts/release.py --verify  # Check build exists
```

### What Build Does

1. **Detects compiler** — MSVC Build Tools, MinGW64 (auto-downloads), or none
2. **Compiles Python to C** via Nuitka with `--standalone` mode
3. **Bundles** all dependencies into `_internal/` folder
4. **Optimizes** with LTO in release mode
5. **Creates distribution folder** `dist/FocusLock-3.0.0/`:
   - `FocusLock.exe` — standalone executable
   - `_internal/` — runtime dependencies (PySide6, SQLAlchemy, psutil, etc.)
   - `Install.bat` — creates Desktop shortcut
   - `Uninstall.bat` — removes shortcut
   - `README.txt` — usage instructions for end user

### Output Structure

```
dist/
└── FocusLock-3.0.0/               # Distribution package (for shipping)
    ├── FocusLock.exe               # <-- User sees this first
    ├── _internal/                  # Runtime dependencies
    │   ├── PySide6/                # Qt libraries + plugins
    │   ├── sqlalchemy/             # ORM
    │   ├── psutil/                 # Process management
    │   ├── assets/                 # Bundled app assets
    │   └── ... (other runtime deps)
    ├── Install.bat
    ├── Uninstall.bat
    ├── README.txt
    ├── LICENSE
    └── CHANGELOG.md
```

### GitHub Actions

**File:** `.github/workflows/build.yml`

**Triggers:**
- Push tag `v*` (e.g., `v3.0.0`)
- Manual dispatch

**What it does:**
1. Sets up Python 3.12 with pip cache
2. Installs all dependencies + Nuitka
3. Reads version from `scripts/version.py`
4. Builds with Nuitka (release mode)
5. Packages with `scripts/release.py`
6. Uploads distribution folder + zip as artifacts
7. Creates a GitHub Release (on tag push only)

---

## Key Code Details

### Timer Flow
```
User clicks Start
  → _toggle_timer() → timer.start() → spawns _loop thread
  → _loop: sleep 1s, decrement, emit on_tick every second
  → _rem reaches 0 → _switch() → emits on_phase(phase, cycles)
  → _on_phase_ui() → updates labels, starts/stops blockers, auto-starts next phase
```

### Phase Transition
```
Work ends (rem=0)
  → _switch: cycles++, phase="break", rem=break_sec (or long_break_sec every N cycles)
  → on_phase("break", cycles) → UI updates: "BREAK TIME", cycle label, sound, notification
  → _on_tick_ui immediately syncs display
  → blockers stop
  → if auto_start: timer continues, else paused
```

### Custom Duration Change
```
User changes work spinbox (e.g., 25→30)
  → _on_spin_changed() → preset="Custom" → _apply_custom()
  → _recreate_timer({work:30, break:5, ...})
  → if not running: remaining=30*60 (full new duration)
  → if running: remaining=min(old_remaining, new_total)
  → new PomodoroTimer created, cycle count preserved
  → _on_tick_ui syncs display immediately
```

### Work Time Tracking
```
_timer.start() → _track_work_time(start=True) → records time.time()
_timer.pause() → _track_work_time(pause=True) → elapsed = now - start → accumulated
_record_session() → storage.record_session(actual_minutes)
```

### Theme Toggle
```
_toggle_theme()
  → saves running state (was_running, remaining, phase, cycles)
  → pauses timer, stops blockers
  → swaps theme, rebuilds entire UI
  → recreates timer, restores all state
  → restarts if was running
```

---

## Settings Storage

All settings stored in SQLite `settings` table via `Storage` class:

| Key | Default | Description |
|-----|---------|-------------|
| `theme` | `"dark"` | UI theme |
| `preset` | `"Classic"` | Active preset name |
| `session_name` | `""` | Display name for session |
| `minimize_to_tray` | `True` | Close button minimizes |
| `notify_break` | `True` | Toast on phase change |
| `sound_alerts` | `True` | Beep on phase change |
| `block_websites` | `True` | Block sites during work |
| `auto_start` | `True` | Auto-start next phase |
| `password_hash` | `""` | Session password hash |
| `parent_password_hash` | `""` | Parent password hash |

---

## To Do After a Break

1. **Run from source:** `python ./src/focuslock_app.py`
2. **Build for distribution:** `python scripts/build.py --release`
3. **Ship:** Zip `dist/FocusLock-3.0.0/` and share
4. **Release:** Push tag `git tag v3.0.0 && git push --tags` → GitHub Actions builds + publishes
5. **Add icon:** Place `assets/icon.ico` and rebuild
