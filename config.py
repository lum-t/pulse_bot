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
ADMIN_CHAT_IDS = list(filter(None, [
    os.getenv("ADMIN_1_CHAT_ID"),
    os.getenv("ADMIN_2_CHAT_ID"),
]))

# ─── Scheduler intervals ─────────────────────────────────────
SIGNAL_CHECK_INTERVAL = int(os.getenv("SIGNAL_CHECK_INTERVAL", 15))  # minutes
TREND_CHECK_INTERVAL  = int(os.getenv("TREND_CHECK_INTERVAL",  30))  # minutes

# ─── AI (Google Gemini) ──────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# ─── LunarCrush ──────────────────────────────────────────────
LUNARCRUSH_API_KEY  = os.getenv("LUNARCRUSH_API_KEY", "")
LUNARCRUSH_BASE_URL = "https://lunarcrush.com/api4/public"

# Minimum social score before a token is considered for signals
LUNARCRUSH_MIN_GALAXY_SCORE  = 40   # 0–100, higher = more social buzz
LUNARCRUSH_MIN_SOCIAL_VOLUME = 500  # minimum posts/mentions across platforms

# ─── Shyft (Wallet Tracking) ─────────────────────────────────
SHYFT_API_KEY  = os.getenv("SHYFT_API_KEY", "")
SHYFT_BASE_URL = "https://api.shyft.to/sol/v1"

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

# ─── Whale Discovery ─────────────────────────────────────────
# Pulled from DexScreener top traders, scored by Gemini, tracked by Shyft
WHALE_MIN_WIN_RATE      = 0.65   # 65% minimum win rate to qualify
WHALE_MIN_SCORE         = 70     # Gemini score out of 100
WHALE_MAX_TRACK         = 20     # Maximum wallets tracked at once
WHALE_REFRESH_HOURS     = 6      # Re-score and refresh whale list every 6 hours

# ─── PnL Tracking ────────────────────────────────────────────
PNL_TAKE_PROFIT_PCT  = 50.0   # Auto-close signal at +50%
PNL_STOP_LOSS_PCT    = 30.0   # Auto-close signal at -30%
PNL_AUTO_CLOSE_HOURS = 8      # Auto-close any open signal after 8 hours
PNL_LIVE_UPDATE_HRS  = 4      # Send mid-signal update after 4 hours
PNL_FILE             = "pnl_history.json"

# ─── Signal History ──────────────────────────────────────────
HISTORY_FILE     = "signal_history.json"
MAX_HISTORY_SIZE = 50

# ─── Trend Keywords ──────────────────────────────────────────
# NOTE: Crypto keywords are for signal engine only — NOT fed into content ideas
CRYPTO_KEYWORDS = [
    "solana crypto",
    "memecoin 2026",
    "pump fun token",
    "BONK coin",
    "WIF token",
    "POPCAT crypto",
    "crypto meme coin",
    "solana meme token",
]

# Content engine keywords — zero crypto, pure lifestyle/animation/general only
LIFESTYLE_KEYWORDS = [
    "day in my life",
    "morning routine vlog",
    "silent vlog",
    "aesthetic vlog",
    "grwm 2026",
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
