<div align="center">

# FocusLock

### Stop procrastinating. Start studying.

A Windows desktop app that blocks distracting apps and websites during Pomodoro focus sessions.

[![Stars](https://img.shields.io/github/stars/zadwen/FocusLock?style=flat-square&color=8b5cf6)](https://github.com/zadwen/FocusLock/stargazers)
[![Windows](https://img.shields.io/badge/Windows-10%2F11-0078d4?style=flat-square&logo=windows)](https://github.com/zadwen/FocusLock/releases)
[![Python](https://img.shields.io/badge/Python-3.10+-3776ab?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-43e97b?style=flat-square)](LICENSE)

</div>

---

## Features

| | |
|---|---|
| Pomodoro Timer | Circular countdown with work/break/long-break phases, 5 presets + custom durations |
| Cycle Counter | Tracks "Pomodoro N of M" with configurable cycles before long break |
| App Blocker | Force-kills distracting apps every 2 seconds during work phases |
| Website Blocker | Blocks sites via hosts file modification (requires admin) |
| Custom Durations | Set work/break/long-break/cycles via spinboxes on the session page |
| Sound Alerts | Beep on phase change (toggle in Settings) |
| Skip Button | Jump to the next phase without waiting |
| Password Lock | Session password prevents pausing/stopping |
| Parent Password | Second password that overrides session lock |
| Auto-Start | Toggle whether phases auto-continue or pause between them |
| Start with Windows | Registry startup entry |
| System Tray | Minimizes to tray instead of closing |
| Session Stats | Total sessions, focus time, streak, 7-day chart |
| Dark / Light Theme | Toggle instantly without restarting |

---

## Download

Grab `FocusLock.exe` from the [Releases](https://github.com/zadwen/FocusLock/releases) page and run it. No Python needed.

> Right-click > Run as Administrator if you want the website blocker to work.

---

## Run from source

```bash
git clone https://github.com/zadwen/FocusLock.git
cd FocusLock
pip install -r requirements.txt
python ./src/focuslock_app.py
```

Requires Python 3.10+ on Windows.

---

## Build a .exe

### Prerequisites

| Requirement | Why | How to get it |
|-------------|-----|---------------|
| **Python 3.10+** | Runtime | [python.org](https://python.org) — check "Add to PATH" |
| **Windows 10/11** | Platform | Required for hosts file + registry features |
| **C compiler** | Nuitka compiles Python to machine code | Auto-downloaded (see below) |

The C compiler is handled automatically. Nuitka downloads [MinGW64](https://winlibs.com) (~250 MB) on first build and caches it. No manual install needed.

> If you prefer MSVC (Visual Studio Build Tools), install it from [here](https://visualstudio.microsoft.com/visual-cpp-build-tools/) and Nuitka will use it instead.

### Quick build (3 commands)

```bash
git clone https://github.com/zadwen/FocusLock.git
cd FocusLock
pip install -r requirements.txt
pip install nuitka ordered-set zstandard
python scripts/build.py --release
python scripts/release.py --zip
```

This produces:

```
dist/
├── FocusLock-3.0.0/          # Standalone folder (run FocusLock.exe from here)
└── FocusLock-3.0.0.zip       # Zip for sharing (44 MB)
```

### Step-by-step build

**1. Clone and install dependencies**

```bash
git clone https://github.com/zadwen/FocusLock.git
cd FocusLock
pip install -r requirements.txt        # PySide6, SQLAlchemy, psutil
pip install nuitka ordered-set zstandard  # Build tools
```

**2. Build the executable**

```bash
python scripts/build.py --release
```

On first run, Nuitka will download MinGW64 (~250 MB). This is a one-time download, cached for future builds.

Build takes **4-5 minutes** on a modern machine. Output goes to `build/nuitka_output/focuslock_app.dist/`.

**3. Package for distribution**

```bash
python scripts/release.py --zip
```

This creates `dist/FocusLock-3.0.0/` with everything needed to run the app, plus a zip for sharing.

**4. Test the build**

```bash
dist/FocusLock-3.0.0/FocusLock.exe
```

### Build modes

```bash
python scripts/build.py --release       # Optimized, LTO, version metadata (default)
python scripts/build.py --development   # Faster build, minimal optimization
python scripts/build.py --debug         # Debug symbols, no optimization
```

### Other scripts

```bash
python scripts/clean.py                 # Remove build artifacts
python scripts/clean.py --all           # Also remove __pycache__
python scripts/release.py --verify      # Check if build output exists
python scripts/version.py               # Print current version (3.0.0)
python scripts/version.py --bump patch  # 3.0.0 -> 3.0.1
```

### Create a Windows installer (optional)

Requires [Inno Setup 6.x](https://jrsoftware.org/isinfo.php):

```bash
python scripts/build.py --release
python scripts/release.py
iscc installer/focuslock.iss
```

Output: `dist/FocusLock-3.0.0-Setup.exe`

### Troubleshooting

| Problem | Fix |
|---------|-----|
| `No C compiler detected` | Nuitka will auto-download MinGW64. Wait for the download (~250 MB). |
| Build hangs at download | Your connection may be slow. The download is cached — rerun `build.py` to resume. |
| `gcc.exe` not found after download | Delete `build/` and rerun. Nuitka will re-extract. |
| `PySide6` errors | Run `pip install --upgrade PySide6` and rebuild. |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` |
| Website blocker doesn't work | Run the app as Administrator (hosts file requires admin). |
| Antivirus blocks the exe | Add an exclusion for `dist/FocusLock-3.0.0/`. Nuitka builds occasionally trigger false positives. |

### What the build produces

```
dist/FocusLock-3.0.0/
├── FocusLock.exe          # The app (52 MB)
├── python312.dll          # Python runtime
├── qt6core.dll            # Qt framework
├── qt6gui.dll
├── qt6widgets.dll
├── PySide6/               # Qt plugins + translations
├── shiboken6/             # PySide6 bindings
├── sqlalchemy/            # ORM
├── psutil/                # Process management
├── *.dll, *.pyd           # C extensions
├── Install.bat            # Creates Desktop shortcut
├── Uninstall.bat          # Removes shortcut
├── README.txt             # End-user instructions
├── LICENSE
└── CHANGELOG.md
```

No Python installation needed on the target machine. Just zip and share.

---

## Default Blocklist

```
steam.exe            steamwebhelper.exe
discord.exe          EpicGamesLauncher.exe
Battle.net.exe       LeagueClient.exe
TwitchUI.exe         Spotify.exe
```

Fully editable from the UI.

---

## Project Layout

```
FocusLock/
├── src/
│   ├── focuslock_app.py              # Main entry point
│   └── focuslock/                    # Core package
│       ├── constants.py              # Name, version, themes, presets
│       ├── config.py                 # SQLAlchemy ORM (SQLite)
│       ├── core/
│       │   ├── timer.py              # Thread-safe PomodoroTimer
│       │   └── security.py           # Password hashing
│       ├── blocking/
│       │   ├── app_blocker.py        # Process blocking
│       │   └── website_blocker.py    # Hosts file blocking
│       ├── platform/
│       │   ├── startup.py            # Windows registry
│       │   ├── notifications.py      # Toast notifications
│       │   └── subprocess_patch.py   # Hidden console windows
│       └── ui/
│           ├── widgets.py            # Theme, CircularTimer, charts
│           └── dialogs.py            # App/site picker dialogs
├── scripts/
│   ├── version.py                    # Single source of truth for version
│   ├── build.py                      # Nuitka build orchestrator
│   ├── clean.py                      # Build artifact cleanup
│   └── release.py                    # Release packaging
├── installer/
│   └── focuslock.iss                 # Inno Setup installer script
├── .github/workflows/build.yml        # GitHub Actions CI/CD
├── requirements.txt                  # Python dependencies
├── docs/
│   ├── BUILD.md                      # Technical build docs
│   ├── REFERENCE.md                  # Technical reference
│   └── CHANGELOG.md                  # Version history
└── LICENSE                           # MIT
```

---

## License

MIT

---

<div align="center">
Made by <a href="https://github.com/zadwen">zadwen</a>
</div>
