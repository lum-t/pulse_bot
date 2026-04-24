# ⚡ PULSE BOT

Your hybrid intelligence system. Two worlds. One bot. Zero noise.

- 🎨 **Content Engine** — Animation video ideas for YouTube, TikTok & X based on what's trending right now
- 📈 **Market Engine** — Solana memecoin signals with probability scores, volume spikes & new token alerts

Both engines are completely separate — they never mix.

---

## 📁 Project Structure

```
pulse_bot/
├── bot.py              ← Main Telegram bot (commands + scheduler)
├── signals.py          ← Solana memecoin signal detection
├── trends.py           ← Content trend detection + idea generator
├── alerts.py           ← Message formatter for Telegram
├── config.py           ← All settings and thresholds
├── .env                ← Your private credentials (never share this)
├── env.example         ← Template for .env
├── requirements.txt    ← Python dependencies
└── README.md           ← This file
```

---

## 🚀 Setup — Step by Step

### Step 1 — Get your Telegram credentials

**Bot Token:**
1. Open Telegram → search `@BotFather`
2. Type `/newbot` → follow the steps
3. Copy the token it gives you

**Chat ID (where the bot sends alerts):**
1. Open Telegram → search `@userinfobot`
2. Send it any message
3. It replies with your Chat ID — copy it

---

### Step 2 — Create your `.env` file

In the `pulse_bot/` folder, copy the example file:

```bash
cp env.example .env
```

Then open `.env` and fill in your values:

```
TELEGRAM_TOKEN=your_actual_bot_token_here
TELEGRAM_CHAT_ID=your_actual_chat_id_here
SIGNAL_CHECK_INTERVAL=15
TREND_CHECK_INTERVAL=30
```

> ⚠️ Never share your `.env` file. Never upload it to GitHub.

---

### Step 3 — Install dependencies

Make sure you have Python 3.10+ installed, then run:

```bash
pip install -r requirements.txt
```

---

### Step 4 — Run the bot

```bash
python bot.py
```

You should see:
```
⚡ PULSE BOT is running...
[scheduler] Signal check every 15 min
[scheduler] Trend check every 30 min
```

Open Telegram, find your bot, and type `/start`.

---

## 💬 Bot Commands

| Command | What it does |
|---|---|
| `/start` | Welcome message + full overview |
| `/trending` | Current trending content ideas (animation-ready) |
| `/ideas [topic]` | Generate animation ideas for any topic you type |
| `/signals` | Live Solana memecoin signals right now |
| `/newtokens` | New Solana token launches in the last 24h |
| `/status` | Bot health check + uptime info |

**Examples:**
```
/ideas memecoin season
/ideas morning routine
/ideas AI taking jobs
```

---

## 🎨 Content Engine — How It Works

The content engine watches:
- **Google Trends** — crypto, lifestyle & animation keywords
- **DexScreener** — trending Solana token names (used as content seeds only)

For each trend it generates animation-specific ideas across:
- **YouTube** — longer video concepts + hooks + titles
- **TikTok** — short punchy concepts + hooks
- **X (Twitter)** — post copy + meme angles

Categories it covers:
- 🪙 Crypto/meme content
- 🌅 Lifestyle (day-in-my-life, routines, aesthetic)
- 😂 Meme animations
- 🎯 General trending topics

Auto-sends content ideas every **30 minutes** (configurable in `.env`).

---

## 📈 Market Engine — How It Works

The market engine uses **DexScreener API** (free, no key needed) to:
1. Fetch top trending Solana tokens
2. Pull detailed pair data (price, volume, liquidity, transactions)
3. Calculate a probability score using:
   - Price momentum (1h, 6h, 24h)
   - Volume spikes vs. 24h average
   - Buy/sell pressure ratio
   - Liquidity health check
   - Multi-timeframe confirmation

A signal is only sent when:
- Price change > **20%** in 1 hour
- Liquidity > **$10,000** USD

Auto-sends market signals every **15 minutes** (configurable in `.env`).

> ⚠️ All signals are for information only. Not financial advice. Always DYOR.

---

## ⚙️ Configuration

Edit `config.py` or your `.env` file to tune the bot:

| Setting | Default | What it controls |
|---|---|---|
| `SIGNAL_CHECK_INTERVAL` | 15 min | How often to scan for memecoin signals |
| `TREND_CHECK_INTERVAL` | 30 min | How often to scan for content trends |
| `PRICE_CHANGE_THRESHOLD` | 20% | Minimum 1h price change to trigger signal |
| `MIN_LIQUIDITY_USD` | $10,000 | Ignore tokens below this liquidity |
| `VOLUME_SPIKE_MULTIPLIER` | 3x | Volume must be 3x hourly average to flag |

You can also edit `CRYPTO_KEYWORDS`, `LIFESTYLE_KEYWORDS`, and `ANIMATION_KEYWORDS` in `config.py` to tune what trends the content engine watches.

---

## 🔮 Website Integration

The bot is built ready to pair with a website. The logic is fully separated:

- `signals.py` — can be imported and called by a web backend directly
- `trends.py` — same, returns clean Python dicts
- `config.py` — has an `ENABLE_API` flag (set to `True` to expose a local REST API on port 8000)

When you're ready to build the website, the data layer is already there.

---

## 🛠 Troubleshooting

**Bot doesn't start:**
- Check your `.env` file exists and has valid values
- Make sure `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID` are both filled in

**No signals showing:**
- Markets might genuinely be quiet — try `/signals` manually
- Lower `PRICE_CHANGE_THRESHOLD` in `config.py` if you want more sensitive alerts

**No trends showing:**
- Google Trends can rate-limit. The bot has fallback topics built in
- Try `/ideas your topic` to generate ideas manually instead

**`pytrends` errors:**
- Google Trends occasionally blocks automated requests
- The bot will fall back to preset topics automatically — this is normal

---

## 📦 Dependencies

| Package | Purpose |
|---|---|
| `python-telegram-bot` | Telegram bot framework |
| `requests` | DexScreener API calls |
| `pytrends` | Google Trends data |
| `python-dotenv` | Load `.env` file safely |
| `apscheduler` | Scheduled auto-alerts |
| `aiohttp` | Async HTTP support |

---

## ⚠️ Disclaimer

PULSE BOT is a personal intelligence tool. Market signals are probability estimates based on on-chain data — not financial advice. Always do your own research before making any trading decisions.
