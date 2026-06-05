<div align="center">

# 🔒 FocusLock

### Stop procrastinating. Start studying.

A Windows app that kills distracting apps and locks you into study sessions.

[![Stars](https://img.shields.io/github/stars/zadwen/FocusLock?style=flat-square&color=6c63ff)](https://github.com/zadwen/FocusLock/stargazers)
[![Windows](https://img.shields.io/badge/Windows-10%2F11-0078d4?style=flat-square&logo=windows)](https://github.com/zadwen/FocusLock/releases)
[![Python](https://img.shields.io/badge/Python-3.10+-3776ab?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-43e97b?style=flat-square)](LICENSE)

</div>

---

Built this because I kept opening Steam every 10 minutes when I was supposed to be studying. Figured if I made it annoying enough to stop the session, I'd actually stay focused.

## Features

| | |
|---|---|
| 🎮 **App Blocker** | Force-kills Steam, Discord, Epic Games, and anything else you add — every 2 seconds |
| ⏱ **Pomodoro Timer** | Built-in timer with 4 presets. Switches automatically between focus and break |
| ⏸ **Pause & Resume** | Pause the session (and blocking) if you need a real break |
| 🌐 **Website Blocker** | Blocks sites via hosts file. Needs admin to work |
| 🔐 **Password Lock** | Set a password so you can't just click "stop" when things get hard |
| 👨‍👧 **Parent Password** | Second password that overrides the session one — useful if someone else is setting it for you |
| 🚀 **Runs on Startup** | Opens with Windows so you don't forget to use it |
| 🔔 **Break Notifications** | Windows notification when it's time to switch phases |
| 🗕 **System Tray** | Minimizes to tray instead of closing |
| 📊 **Study Stats** | Tracks sessions, total focus time, and your streak |
| 🌙 **Dark / Light mode** | |

---

## Getting Started

### Download (easiest)

Grab `FocusLock.exe` from the [Releases](https://github.com/zadwen/FocusLock/releases) page and run it. No install needed.

> Right-click → Run as Administrator if you want the website blocker to work.

### Run from source

```bash
git clone https://github.com/zadwen/FocusLock.git
cd FocusLock
python src/focuslock.py
```

Needs Python 3.10+ on Windows. No pip installs required for the core app.

**Optional — for system tray icon:**
```bash
pip install pystray Pillow
```

---

## How it works

1. Add the apps you want blocked in the **Blocklist** tab
2. Pick a Pomodoro preset (or use Classic 25/5)
3. Hit **Start Session** — blocked apps will be killed every 2 seconds
4. Set a password in Settings if you don't trust yourself to stop early

The website blocker edits your `hosts` file to redirect blocked domains to localhost. It cleans up automatically when the session ends.

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

## Build a .exe yourself

```bash
pip install pyinstaller
build.bat
```

Output goes to `dist/FocusLock.exe`.

---

## Project layout

```
FocusLock/
├── src/
│   └── focuslock.py        # everything's in here
├── assets/
├── .github/workflows/
│   └── build.yml           # auto-builds exe on release tags
├── build.bat
├── requirements.txt
└── README.md
```

## License

MIT — do whatever you want with it.

---

<div align="center">
Made by <a href="https://github.com/zadwen">zadwen</a> because exam season is brutal


</div>
