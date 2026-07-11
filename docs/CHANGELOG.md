# Changelog

## v3.0.0
### Timer Overhaul
- Added long break after N cycles (configurable per preset)
- Added cycle counter display ("Pomodoro N of M")
- Added skip button to jump to next phase
- Added auto-start toggle (pause between phases)
- Fixed first tick losing 1 second (sleep before decrement)
- Fixed pause consuming extra seconds
- Fixed circular timer progress overflow on preset switch
- Fixed phase label not resetting on timer reset
- Fixed button text showing wrong label during break phase
- Timer now syncs display instantly on phase transitions

### Custom Durations
- Added work/break/long-break/cycles spinboxes on session page
- Spinboxes update timer live (no restart needed)
- Clicking a preset fills spinboxes with its values
- Changing spinboxes switches to Custom preset automatically

### Work Time Tracking
- Tracks actual elapsed work time (not just preset duration)
- Works on auto-started phases
- Sub-minute precision (no more floor-division loss)

### New Features
- Sound alerts on phase change (system beep, toggle in Settings)
- Session name cached (no DB query every tick)
- Phase-specific circular timer colors (purple=work, green=break)
- Circular timer dims when paused (visual feedback)

### Build System
- New `build.py` orchestrator with prerequisites check
- `--onedir` mode: folder-based distribution with Install/Uninstall scripts
- Professional output: `dist/FocusLock-3.0.0/` ready to ship
- GitHub Actions: pip cache, distribution artifact, release notes
- Migrated from PyInstaller to Nuitka for faster startup and lower false positives
- Auto-downloads MinGW64 compiler if not present

### Themes
- New vibrant dark theme (#8b5cf6 purple accent)
- New vibrant light theme (#7c3aed purple accent)
- Deeper backgrounds, richer colors

### Presets
- Renamed: "Long Focus" → "Extended Focus", "Short Burst" → "Sprint"
- Added "Custom" preset with editable spinboxes
- Sprint now has 5 cycles (was 4)

### Bug Fixes
- Fixed `QScrollArea` missing import in dialogs
- Fixed `_add_multiple` tuple unpacking in picker dialogs
- Fixed `stat_card` fragile `findChild` hack
- Fixed `AppBlocker` spawning multiple threads
- Fixed theme name case mismatch
- Fixed work time tracking on break resume
- Fixed preset switch resetting cycle count
- Fixed `total_for_phase` ignoring long breaks

## v2.0.0
- SQLAlchemy ORM storage (replaced JSON)
- Password protection (session + parent)
- Website blocking via hosts file
- Dynamic theme switching (no restart)

## v1.1.0
- Added pause/resume during sessions
- Added startup with Windows (registry)
- Added system tray support (minimize instead of close)
- Added break notifications via Windows toast
- Added parent password (overrides session password)
- Added session name input
- Added reset blocklist to defaults button
- Added streak tracking in stats
- CMD window is now hidden when running from source
- Cleaner UI overall

## v1.0.0
- Initial release
- App blocker, Pomodoro timer, website blocker, password lock, stats
