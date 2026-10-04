# Validation report — FocusLock v2 prepared upgrade

## Completed locally

- **27 automated tests passed** on Linux with Python 3.12 and a virtual X11 display, including six GUI behavior tests. Also checked against both the runtime Tk and distribution Tk 8.6.
- Checked dark and light screenshots of the actual application and the Settings page; screenshots in this package are not mockups.
- Checked all pages at the 940 × 710 minimum size for vertical layout overflow.
- Verified timer pause/resume, repeated starts, delayed callbacks, work/break transitions, and excluding pauses/breaks from focus totals.
- Verified GUI integration releases blockers on pause and break, restores them on resume, and preserves sessions across theme changes.
- Verified password checks, salted hashes, old hash verification, malformed config handling, atomic-save failure behavior, old stats migration, and expiring streaks.
- Tested hosts changes against temporary files, including IPv4/IPv6 rules, exact unrelated-byte preservation, repeated application, malformed-marker refusal, and cleanup.
- Verified single-instance locking and that repeated blocker reconfiguration retains one worker.
- Built a Linux x86-64 executable. Its bundled Python starts and `--version` returns `2.0.0`. Launched the bundled GUI with development library paths removed and visually checked its screenshot.

## Not yet verified on native target machines

- Windows executable build/run, SmartScreen behavior, tasklist/taskkill behavior, registry startup, and Windows notification delivery.
- GNOME/KDE sign-in autostart, real process termination, and every named Linux distribution.
- Administrator-level changes to a real system hosts file or browser-level DNS behavior. Tests deliberately use temporary hosts files.
- GitHub-hosted workflow execution and publication of release assets. GitHub was not connected; no repository push or release was performed.

The workflow runs tests and produces separate native Windows/Linux builds. Its GUI tests are required on CI rather than silently skipped. Before releasing, run the workflow, download its artifacts, and perform the native checks above.

## Known limits

- Linux website blocking requires preconfigured hosts-file write access; no privileged service is installed. Normal Linux use supports the timer and app blocker. Permission failures are visible.
- Hosts edits are system-wide, not browser- or user-specific. Multiple users/tools editing hosts can conflict. Use a dedicated network policy tool when you need stronger isolation.
- Not tamper-resistant parental control. Killing the app or modifying its files can bypass it.
- Active-session stats are saved on normal stop/quit, not continuously. A crash can lose the active session, and sleep handling follows the platform monotonic clock.
- Process blocking is exact-name based. Apps can respawn between scans or use different executable names; protected processes may reject termination.
- Existing v1 statistics preserve old overcounting; historical data cannot be corrected reliably.
- The locally supplied Linux executable is built on glibc 2.39. The release workflow uses Ubuntu 22.04 to target glibc 2.35+. Use source on incompatible systems.

Passing tests is evidence for the listed behaviors, not a claim that the app has no bugs.
