"""
config.py — PULSE BOT Configuration
All settings, thresholds, and environment variables
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── Telegram ────────────────────────────────────────────────
TELEGRAM_TOKEN      = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID    = os.getenv("TELEGRAM_CHAT_ID")        # private chat for commands
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")    # channel for public alerts

# Admin IDs — only these 2 users can command the bot
ADMIN_IDS = set(filter(None, [
    os.getenv("ADMIN_1_ID"),
    os.getenv("ADMIN_2_ID"),
]))

# ─── Scheduler intervals ─────────────────────────────────────
SIGNAL_CHECK_INTERVAL = int(os.getenv("SIGNAL_CHECK_INTERVAL", 15))  # minutes
TREND_CHECK_INTERVAL  = int(os.getenv("TREND_CHECK_INTERVAL",  30))  # minutes

# ─── AI (Google Gemini) ──────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# ─── Timezone ────────────────────────────────────────────────
DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "Africa/Lagos")

# ─── Rate Limiting ───────────────────────────────────────────
# Seconds an admin must wait between the same command
RATE_LIMIT_SECONDS = 30

# ─── DexScreener ─────────────────────────────────────────────
DEXSCREENER_BASE_URL = "https://api.dexscreener.com/latest/dex"
SOLANA_CHAIN         = "solana"

# Signal detection thresholds
VOLUME_SPIKE_MULTIPLIER = 3.0
PRICE_CHANGE_THRESHOLD  = 20.0
MIN_LIQUIDITY_USD       = 10_000
NEW_TOKEN_HOURS         = 24

# ─── Signal History ──────────────────────────────────────────
HISTORY_FILE     = "signal_history.json"
MAX_HISTORY_SIZE = 50   # keep last 50 signals

# ─── Trend Keywords ──────────────────────────────────────────
CRYPTO_KEYWORDS = [
    "solana", "memecoin", "SOL", "pump fun",
    "BONK", "WIF", "POPCAT", "crypto meme"
]

LIFESTYLE_KEYWORDS = [
    "day in my life", "morning routine", "vlog",
    "aesthetic", "grwm", "silent vlog"
]

ANIMATION_KEYWORDS = [
    "animation meme", "animated video", "2d animation",
    "motion graphics", "animator life", "cartoon meme"
]

GENERAL_TRENDING = [
    "trending", "viral", "tiktok trend"
]

# ─── Content Templates ───────────────────────────────────────
PLATFORMS = ["YouTube", "TikTok", "X (Twitter)"]

# ─── Website-ready API flag ──────────────────────────────────
ENABLE_API = False
API_PORT   = 8000
