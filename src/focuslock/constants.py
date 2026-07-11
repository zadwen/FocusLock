"""Application-wide constants and defaults."""

APP_NAME = "FocusLock"
VERSION = "3.0.0"

DEFAULT_APPS = [
    "steam.exe",
    "steamwebhelper.exe",
    "discord.exe",
    "EpicGamesLauncher.exe",
    "Battle.net.exe",
    "LeagueClient.exe",
    "TwitchUI.exe",
    "Spotify.exe",
]

DEFAULT_SITES = [
    "youtube.com",
    "twitter.com",
    "x.com",
    "reddit.com",
    "twitch.tv",
    "instagram.com",
    "tiktok.com",
    "facebook.com",
    "netflix.com",
    "discord.com",
]

PRESETS = {
    "Classic": {"work": 25, "break": 5, "long_break": 15, "cycles": 4},
    "Extended Focus": {"work": 50, "break": 10, "long_break": 20, "cycles": 3},
    "Sprint": {"work": 15, "break": 3, "long_break": 10, "cycles": 5},
    "Deep Work": {"work": 90, "break": 20, "long_break": 30, "cycles": 2},
    "Custom": {"work": 25, "break": 5, "long_break": 15, "cycles": 4},
}

SUGGESTED_APPS = {
    "Games": [
        ("Steam", "steam.exe"),
        ("Steam Helper", "steamwebhelper.exe"),
        ("Epic Games", "EpicGamesLauncher.exe"),
        ("Battle.net", "Battle.net.exe"),
        ("League Client", "LeagueClient.exe"),
        ("Valorant", "VALORANT-Win64-Shipping.exe"),
        ("Minecraft", "Minecraft.exe"),
        ("Roblox", "RobloxPlayerBeta.exe"),
        ("Xbox App", "XboxApp.exe"),
        ("GOG Galaxy", "GalaxyClient.exe"),
    ],
    "Social & Chat": [
        ("Discord", "discord.exe"),
        ("Slack", "slack.exe"),
        ("Microsoft Teams", "ms-teams.exe"),
        ("Telegram", "Telegram.exe"),
        ("WhatsApp", "WhatsApp.exe"),
        ("Signal", "Signal.exe"),
        ("Skype", "Skype.exe"),
    ],
    "Media & Music": [
        ("Spotify", "Spotify.exe"),
        ("Twitch", "TwitchUI.exe"),
        ("VLC", "vlc.exe"),
        ("iTunes", "iTunes.exe"),
        ("Deezer", "Deezer.exe"),
    ],
    "Browsers": [
        ("Chrome", "chrome.exe"),
        ("Firefox", "firefox.exe"),
        ("Edge", "msedge.exe"),
        ("Opera", "opera.exe"),
        ("Brave", "brave.exe"),
    ],
    "Other": [
        ("Zoom", "Zoom.exe"),
        ("OBS Studio", "obs64.exe"),
        ("Photoshop", "Photoshop.exe"),
        ("Blender", "Blender.exe"),
    ],
}

SUGGESTED_SITES = {
    "Social Media": [
        "twitter.com", "x.com", "instagram.com", "facebook.com",
        "tiktok.com", "reddit.com", "snapchat.com", "linkedin.com",
        "pinterest.com", "tumblr.com",
    ],
    "Video & Streaming": [
        "youtube.com", "twitch.tv", "netflix.com", "hulu.com",
        "disneyplus.com", "primevideo.com", "crunchyroll.com",
        "vimeo.com", "dailymotion.com",
    ],
    "News & Forums": [
        "news.ycombinator.com", "medium.com", "9gag.com",
        "buzzfeed.com", "cnn.com", "bbc.com", "theverge.com",
    ],
    "Shopping": [
        "amazon.com", "ebay.com", "aliexpress.com", "etsy.com",
        "walmart.com",
    ],
    "Messaging": [
        "discord.com", "slack.com", "messenger.com", "whatsapp.com",
    ],
}

THEMES = {
    "dark": {
        "bg": "#0a0a12",
        "surface": "#111120",
        "sidebar": "#0c0c16",
        "card": "#16162a",
        "card_hover": "#1e1e3a",
        "accent": "#8b5cf6",
        "accent_hover": "#a78bfa",
        "accent2": "#f472b6",
        "success": "#34d399",
        "warn": "#fbbf24",
        "text": "#f0f0fa",
        "subtext": "#7c7c9e",
        "muted": "#4a4a6a",
        "border": "#1e1e3a",
        "input": "#12121f",
        "danger": "#f472b6",
        "timer_work": "#8b5cf6",
        "timer_break": "#34d399",
        "timer_bg": "#16162a",
    },
    "light": {
        "bg": "#f4f4fb",
        "surface": "#ffffff",
        "sidebar": "#ececf8",
        "card": "#ffffff",
        "card_hover": "#f0f0fa",
        "accent": "#7c3aed",
        "accent_hover": "#6d28d9",
        "accent2": "#ec4899",
        "success": "#10b981",
        "warn": "#f59e0b",
        "text": "#111120",
        "subtext": "#5a5a78",
        "muted": "#9898b0",
        "border": "#d4d4ec",
        "input": "#f8f8ff",
        "danger": "#ec4899",
        "timer_work": "#7c3aed",
        "timer_break": "#10b981",
        "timer_bg": "#ececf8",
    },
}
