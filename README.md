<div align="center">

<img src="https://img.shields.io/badge/FocusLock-1.0.0-6c63ff?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZmlsbD0id2hpdGUiIGQ9Ik0xMiAxTDMgNXYNmMwIDUuNTUgMy44NCAxMC43NCAxMCA0LjkzIDYuMTYtNS43OSAxMC05LjM4IDEwLTEwLjkzVjVMMTIgMXoiLz48L3N2Zz4=" alt="FocusLock">

# 🔒 FocusLock

### **small script to focus on study.**

A lightweight Windows app that **locks distractions** and keeps you in the zone during study sessions.

[![Stars](https://img.shields.io/github/stars/zadwen/FocusLock?style=flat-square&color=6c63ff)](https://github.com/zadwen/FocusLock/stargazers)
[![Windows](https://img.shields.io/badge/Windows-10%2F11-0078d4?style=flat-square&logo=windows)](https://github.com/zadwen/FocusLock/releases)
[![Python](https://img.shields.io/badge/Python-3.10+-3776ab?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-43e97b?style=flat-square)](LICENSE)
[![Made by zadwen](https://img.shields.io/badge/made%20by-zadwen-ff6584?style=flat-square)](https://github.com/zadwen)

<br>

> *"The enemy of studying isn't laziness — it's Steam, Discord, and YouTube."*

<br>

</div>

---

## ✨ Features

| Feature | Description |
|---|---|
| 🎮 **App Blocker** | Force-kills Steam, Discord, Epic Games, and any custom `.exe` during sessions |
| ⏱ **Pomodoro Timer** | Built-in timer with 4 presets (Classic, Long Focus, Short Burst, Deep Work) |
| 🌐 **Website Blocker** | Blocks distracting sites via the hosts file (YouTube, Reddit, Twitter...) |
| 🔐 **Password Lock** | Set a password so you *can't* cheat and stop the session early |
| 📊 **Study Stats** | Tracks total sessions, focus minutes, and your longest streak |
| 🌙 **Dark / Light Mode** | Easy on the eyes, day or night |
| 📦 **Portable .exe** | No install needed — just run and focus |

---

## 🚀 Quick Start

### Option 1 — Download the .exe (easiest)

1. Go to **[Releases](https://github.com/zadwen/FocusLock/releases)**
2. Download `FocusLock.exe`
3. Run it — no installation needed

> ⚠️ **Run as Administrator** if you want website blocking (modifies your hosts file)

---

### Option 2 — Run from source

```bash
# Clone the repo
git clone https://github.com/zadwen/FocusLock.git
cd FocusLock

# No external dependencies needed! Just run:
python src/focuslock.py
```

**Requirements:** Python 3.10+ on Windows

---

## 🖥️ How to Use

1. **Add apps to block** → Go to the *Blocklist* tab, add any `.exe` you want killed
2. **Pick a Pomodoro preset** → Classic 25/5, or customize your own rhythm
3. **Set a password** *(optional)* → Go to *Settings* to make stopping the session harder
4. **Hit START** → FocusLock will close blocked apps every 2 seconds

### 💡 Tips
- Steam opens background processes — `steam.exe` and `steamwebhelper.exe` are both blocked by default
- Enable website blocking for maximum focus (requires Admin)
- Use the Deep Work preset (90/20) for hard subjects like math or programming

---

## 📋 Default Blocklist

```
steam.exe              steamwebhelper.exe
discord.exe            EpicGamesLauncher.exe
Battle.net.exe         LeagueClient.exe
TwitchUI.exe           Spotify.exe
```

You can add or remove anything from the *Blocklist* tab.

---

## 🌐 Default Website Blocklist

```
youtube.com    reddit.com    twitter.com
twitch.tv      instagram.com tiktok.com
facebook.com
```

can be customized in website app

---

## 🔨 Build Your Own .exe

```bash
pip install pyinstaller
build.bat
```

Your executable will appear in `dist/FocusLock.exe`.

---





## 📜 License

MIT License — free to use, modify, and share.

---

<div align="center">

Made by [zadwen](https://github.com/zadwen)**


</div>
