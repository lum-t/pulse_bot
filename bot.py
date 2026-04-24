"""
bot.py — PULSE BOT
Main Telegram bot entry point
Handles commands, scheduler, and message routing
"""

import logging
import asyncio
from datetime import datetime

from telegram import Update, BotCommand
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler, filters
)
from telegram.constants import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
from signals import detect_signals, get_new_token_alerts
from trends  import get_trending_content_ideas, get_ideas_for_topic
from alerts  import (
    format_market_signal, format_content_alert,
    format_new_tokens, format_no_signals, format_no_trends,
    format_signal_summary, format_trend_summary, escape_md
)

# ─── Logging ─────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    level=logging.INFO
)
log = logging.getLogger("pulse_bot")


# ─── Admin-only guard ──────────────────────────────────────
from config import ADMIN_IDS

async def admin_only(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """Return True if user is admin, else silently ignore."""
    user_id = str(update.effective_user.id)
    if user_id not in ADMIN_IDS:
        return False  # completely ignore — no reply, no reaction
    return True


# ─── Command Handlers ────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, ctx):
        return
    msg = (
        "⚡ *Welcome to PULSE BOT*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Your hybrid intelligence system\\.\n"
        "Two worlds\\. One bot\\. Zero noise\\.\n\n"
        "🎨 *Content Engine*\n"
        "Animation ideas for YouTube, TikTok \\& X\n"
        "Based on what's trending right now\n\n"
        "📈 *Market Engine*\n"
        "Solana memecoin signals\n"
        "Probability scores, volume spikes, new tokens\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "*Commands:*\n\n"
        "🎨 /trending — current trending ideas\n"
        "💡 /ideas \\[topic\\] — ideas for any topic\n\n"
        "📈 /signals — live Solana signals\n"
        "🆕 /newtokens — new token launches\n\n"
        "⚙️ /status — bot health check\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "_PULSE is not financial advice\\._\n"
        "_All trading signals are for information only\\._"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, ctx):
        return
    now = datetime.utcnow().strftime("%Y\\-%m\\-%d %H:%M UTC")
    msg = (
        "⚙️ *PULSE BOT — STATUS*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🟢 Bot: Online\n"
        f"🕐 Time: {now}\n"
        f"⏱ Signal check: every {config.SIGNAL_CHECK_INTERVAL} min\n"
        f"⏱ Trend check: every {config.TREND_CHECK_INTERVAL} min\n"
        f"⛓ Chain: Solana only\n"
        f"📡 Data: DexScreener \\+ Google Trends\n"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)


async def cmd_signals(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, ctx):
        return
    await update.message.reply_text(
        "📈 *Scanning Solana for signals\\.\\.\\.*",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    signals = detect_signals()
    if not signals:
        await update.message.reply_text(
            format_no_signals(), parse_mode=ParseMode.MARKDOWN_V2
        )
        return
    for signal in signals[:3]:  # max 3 at a time
        msg = format_market_signal(signal)
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)


async def cmd_trending(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, ctx):
        return
    await update.message.reply_text(
        "🎨 *Scanning trends\\.\\.\\.*",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    ideas = get_trending_content_ideas()
    if not ideas:
        await update.message.reply_text(
            format_no_trends(), parse_mode=ParseMode.MARKDOWN_V2
        )
        return
    for idea in ideas[:2]:  # max 2 at a time
        msg = format_content_alert(idea)
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)


async def cmd_ideas(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, ctx):
        return
    # Get topic from command args: /ideas memecoin
    topic = " ".join(ctx.args).strip() if ctx.args else ""

    if not topic:
        await update.message.reply_text(
            "💡 *Usage:* `/ideas your topic here`\n\n"
            "Examples:\n"
            "`/ideas memecoin season`\n"
            "`/ideas morning routine`\n"
            "`/ideas AI taking jobs`",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return

    await update.message.reply_text(
        f"💡 *Generating ideas for: {escape_md(topic)}\\.\\.\\.*",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    idea = get_ideas_for_topic(topic)
    msg  = format_content_alert(idea)
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)


async def cmd_newtokens(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, ctx):
        return
    await update.message.reply_text(
        "🆕 *Fetching new Solana token launches\\.\\.\\.*",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    tokens = get_new_token_alerts()
    msg    = format_new_tokens(tokens)
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)


async def handle_unknown(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, ctx):
        return
    await update.message.reply_text(
        "❓ Unknown command\\. Type /start to see all commands\\.",
        parse_mode=ParseMode.MARKDOWN_V2
    )


# ─── Scheduled Auto-Alerts ───────────────────────────────────

async def auto_signal_check(app: Application):
    """Runs on schedule — sends a summary notification of detected signals."""
    log.info("[scheduler] Running auto signal check...")
    signals = detect_signals()
    if not signals:
        log.info("[scheduler] No signals found.")
        return
    try:
        msg = format_signal_summary(signals)
        await app.bot.send_message(
            chat_id=config.TELEGRAM_CHANNEL_ID,
            text=msg,
            parse_mode=ParseMode.MARKDOWN_V2
        )
        log.info(f"[scheduler] Signal summary sent to channel — {len(signals)} signals.")
    except Exception as e:
        log.error(f"[scheduler] Failed to send signal summary: {e}")


async def auto_trend_check(app: Application):
    """Runs on schedule — sends a summary notification of detected trends."""
    log.info("[scheduler] Running auto trend check...")
    ideas = get_trending_content_ideas()
    if not ideas:
        log.info("[scheduler] No trends found.")
        return
    try:
        msg = format_trend_summary(ideas)
        await app.bot.send_message(
            chat_id=config.TELEGRAM_CHANNEL_ID,
            text=msg,
            parse_mode=ParseMode.MARKDOWN_V2
        )
        log.info(f"[scheduler] Trend summary sent to channel — {len(ideas)} trends.")
    except Exception as e:
        log.error(f"[scheduler] Failed to send trend summary: {e}")


# ─── Bot Setup ───────────────────────────────────────────────

def build_app() -> Application:
    app = Application.builder().token(config.TELEGRAM_TOKEN).build()

    # Register commands
    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("status",    cmd_status))
    app.add_handler(CommandHandler("signals",   cmd_signals))
    app.add_handler(CommandHandler("trending",  cmd_trending))
    app.add_handler(CommandHandler("ideas",     cmd_ideas))
    app.add_handler(CommandHandler("newtokens", cmd_newtokens))
    app.add_handler(MessageHandler(filters.COMMAND, handle_unknown))

    return app


async def main():
    if not config.TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN is not set in your .env file")
    if not config.TELEGRAM_CHANNEL_ID:
        raise ValueError("TELEGRAM_CHANNEL_ID is not set in your .env file")

    app = build_app()

    # Set bot command menu in Telegram
    await app.bot.set_my_commands([
        BotCommand("start",     "Welcome + overview"),
        BotCommand("trending",  "🎨 Current trending content ideas"),
        BotCommand("ideas",     "💡 Ideas for a specific topic"),
        BotCommand("signals",   "📈 Live Solana memecoin signals"),
        BotCommand("newtokens", "🆕 New token launches"),
        BotCommand("status",    "⚙️ Bot health check"),
    ])

    # Setup scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        auto_signal_check,
        "interval",
        minutes=config.SIGNAL_CHECK_INTERVAL,
        args=[app],
        id="signal_check"
    )
    scheduler.add_job(
        auto_trend_check,
        "interval",
        minutes=config.TREND_CHECK_INTERVAL,
        args=[app],
        id="trend_check"
    )
    scheduler.start()
    log.info(f"[scheduler] Signal check every {config.SIGNAL_CHECK_INTERVAL} min")
    log.info(f"[scheduler] Trend check every {config.TREND_CHECK_INTERVAL} min")

    log.info("⚡ PULSE BOT is running...")
    await app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    asyncio.run(main())