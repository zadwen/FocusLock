# Changelog

## 2.0.0 — prepared upgrade

- Replaced the conflicting Windows-only implementations with one modular app.
- Added a resizable sidebar layout, task field, custom durations, immediate themes and refreshed insights.
- Replaced recursive timer threads with a monotonic state machine driven by Tk's main loop.
- Fixed pause, break and stop behavior for blockers; protected pause and password changes.
- Fixed focus-time overcounting, stale streaks, stale stats views and preset/progress mismatches.
- Added Linux process blocking and per-user desktop/autostart installation.
- Added validated domains, protected process names, atomic config writes and an OS instance lock.
- Added PBKDF2 password storage while preserving verification of old SHA-256 hashes.
- Preserved unrelated hosts entries and added backups, visible failures and recovery commands.
- Removed the global subprocess monkey patch and escaped notification text correctly.
- Moved automation into `.github/workflows`; added Windows/Linux tests, binaries and checksums.
- Added platform tutorials, release instructions and a candid validation report.

## 1.x

Original Windows versions by zadwen; preserved in Git history.
