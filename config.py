"""
config.py — PULSE BOT Configuration
All settings, thresholds, and environment variables
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── Telegram ────────────────────────────────────────────────
TELEGRAM_TOKEN      = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID    = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")

# Admin IDs — only these 2 users can command the bot
ADMIN_IDS = set(filter(None, [
    os.getenv("ADMIN_1_ID"),
    os.getenv("ADMIN_2_ID"),
]))

# Admin Chat IDs — private DM chat IDs for each admin
# Bot will send alerts directly to both admins + the channel
ADMIN_CHAT_IDS = list(filter(None, [
    os.getenv("ADMIN_1_CHAT_ID"),
    os.getenv("ADMIN_2_CHAT_ID"),
]))

# ─── Scheduler intervals ─────────────────────────────────────
SIGNAL_CHECK_INTERVAL = int(os.getenv("SIGNAL_CHECK_INTERVAL", 15))  # minutes
TREND_CHECK_INTERVAL  = int(os.getenv("TREND_CHECK_INTERVAL",  30))  # minutes

# ─── AI (Google Gemini) ──────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# ─── Timezone ────────────────────────────────────────────────
DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "Africa/Lagos")

# ─── Rate Limiting ───────────────────────────────────────────
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
MAX_HISTORY_SIZE = 50

# ─── Trend Keywords ──────────────────────────────────────────
# CRYPTO: specific coin names + crypto-native phrases only
# Avoids single words like "solana" that can match celebrities/athletes
CRYPTO_KEYWORDS = [
    "solana crypto",
    "memecoin 2025",
    "pump fun token",
    "BONK coin",
    "WIF token",
    "POPCAT crypto",
    "crypto meme coin",
    "solana meme token",
]

LIFESTYLE_KEYWORDS = [
    "day in my life",
    "morning routine vlog",
    "silent vlog",
    "aesthetic vlog",
    "grwm 2025",
    "content creator life",
]

ANIMATION_KEYWORDS = [
    "animation meme",
    "animated short film",
    "2d animation trend",
    "motion graphics viral",
    "animator life",
    "AI animation video",
]

GENERAL_TRENDING = [
    "trending video idea",
    "viral tiktok trend",
    "youtube shorts idea",
]

# ─── Content Templates ───────────────────────────────────────
PLATFORMS = ["YouTube", "TikTok", "X (Twitter)"]

# ─── Website-ready API flag ──────────────────────────────────
ENABLE_API = False
API_PORT   = 8000
