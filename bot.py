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


# ─── Admin-only guard ────────────────────────────────────────
from config import ADMIN_IDS

async def admin_only(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """Return True if user is admin, else silently ignore."""
    user_id = str(update.effective_user.id)
    if user_id not in ADMIN_IDS:
        return False
    return True


# ─── Safe reply helper ───────────────────────────────────────
async def safe_reply(update: Update, text: str):
    """Send MarkdownV2 message with fallback to plain text on parse error."""
    try:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2)
    except Exception as e:
        log.warning(f"[bot] Markdown send failed ({e}), retrying as plain text")
        # Strip common markdown chars and retry
        plain = text.replace("*", "").replace("_", "").replace("\\", "").replace("`", "")
        try:
            await update.message.reply_text(plain)
        except Exception as e2:
            log.error(f"[bot] Plain text send also failed: {e2}")


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
    await safe_reply(update, msg)


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
    await safe_reply(update, msg)


async def cmd_signals(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, ctx):
        return

    await safe_reply(update, "📈 *Scanning Solana for signals\\.\\.\\.*")

    try:
        signals = detect_signals()
    except Exception as e:
        log.error(f"[bot] detect_signals() crashed: {e}")
        await safe_reply(update, "⚠️ Signal scan failed\\. Check logs for details\\.")
        return

    if not signals:
        await safe_reply(update, format_no_signals())
        return

    # Send up to 3 signals directly to the user
    for signal in signals[:3]:
        try:
            msg = format_market_signal(signal)
            await safe_reply(update, msg)
        except Exception as e:
            log.error(f"[bot] Failed to send signal: {e}")


async def cmd_trending(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, ctx):
        return

    await safe_reply(update, "🎨 *Scanning trends\\.\\.\\.*")

    try:
        ideas = get_trending_content_ideas()
    except Exception as e:
        log.error(f"[bot] get_trending_content_ideas() crashed: {e}")
        await safe_reply(update, "⚠️ Trend scan failed\\. Try /ideas with a specific topic\\.")
        return

    if not ideas:
        await safe_reply(update, format_no_trends())
        return

    # Send up to 2 ideas directly to the user
    for idea in ideas[:2]:
        try:
            msg = format_content_alert(idea)
            await safe_reply(update, msg)
        except Exception as e:
            log.error(f"[bot] Failed to send trend: {e}")


async def cmd_ideas(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, ctx):
        return

    topic = " ".join(ctx.args).strip() if ctx.args else ""

    if not topic:
        await safe_reply(
            update,
            "💡 *Usage:* `/ideas your topic here`\n\n"
            "Examples:\n"
            "`/ideas memecoin season`\n"
            "`/ideas morning routine`\n"
            "`/ideas AI taking jobs`"
        )
        return

    await safe_reply(update, f"💡 *Generating ideas for: {escape_md(topic)}\\.\\.\\.*")

    try:
        idea = get_ideas_for_topic(topic)
        msg  = format_content_alert(idea)
        await safe_reply(update, msg)
    except Exception as e:
        log.error(f"[bot] get_ideas_for_topic() crashed: {e}")
        await safe_reply(update, "⚠️ Idea generation failed\\. Try again in a moment\\.")


async def cmd_newtokens(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, ctx):
        return

    await safe_reply(update, "🆕 *Fetching new Solana token launches\\.\\.\\.*")

    try:
        tokens = get_new_token_alerts()
        msg    = format_new_tokens(tokens)
        await safe_reply(update, msg)
    except Exception as e:
        log.error(f"[bot] get_new_token_alerts() crashed: {e}")
        await safe_reply(update, "⚠️ Token fetch failed\\. DexScreener may be rate limiting\\.")


async def handle_unknown(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, ctx):
        return
    await safe_reply(update, "❓ Unknown command\\. Type /start to see all commands\\.")


# ─── Scheduled Auto-Alerts (channel + both admin DMs) ────────

async def _broadcast(app: Application, msg: str, label: str):
    """
    Send msg to:
      1. Public channel (TELEGRAM_CHANNEL_ID)
      2. Both admin private chats (ADMIN_1_CHAT_ID + ADMIN_2_CHAT_ID)
    Failures on individual targets are logged but don't stop others.
    """
    targets = []

    # Channel
    if config.TELEGRAM_CHANNEL_ID:
        targets.append(("channel", config.TELEGRAM_CHANNEL_ID))

    # Admin DMs
    for chat_id in config.ADMIN_CHAT_IDS:
        targets.append(("admin DM", chat_id))

    for target_type, chat_id in targets:
        try:
            await app.bot.send_message(
                chat_id=chat_id,
                text=msg,
                parse_mode=ParseMode.MARKDOWN_V2
            )
            log.info(f"[scheduler] {label} sent to {target_type} ({chat_id})")
        except Exception as e:
            log.error(f"[scheduler] Failed to send {label} to {target_type} ({chat_id}): {e}")


async def auto_signal_check(app: Application):
    """Runs on schedule — sends signal summary to channel + both admin DMs."""
    log.info("[scheduler] Running auto signal check...")
    try:
        signals = detect_signals()
    except Exception as e:
        log.error(f"[scheduler] detect_signals() crashed: {e}")
        return

    if not signals:
        log.info("[scheduler] No signals found.")
        return

    msg = format_signal_summary(signals)
    await _broadcast(app, msg, f"signal summary ({len(signals)} signals)")


async def auto_trend_check(app: Application):
    """Runs on schedule — sends trend summary to channel + both admin DMs."""
    log.info("[scheduler] Running auto trend check...")
    try:
        ideas = get_trending_content_ideas()
    except Exception as e:
        log.error(f"[scheduler] get_trending_content_ideas() crashed: {e}")
        return

    if not ideas:
        log.info("[scheduler] No trends found.")
        return

    msg = format_trend_summary(ideas)
    await _broadcast(app, msg, f"trend summary ({len(ideas)} trends)")


# ─── Bot Setup ───────────────────────────────────────────────

def build_app() -> Application:
    app = Application.builder().token(config.TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("status",    cmd_status))
    app.add_handler(CommandHandler("signals",   cmd_signals))
    app.add_handler(CommandHandler("trending",  cmd_trending))
    app.add_handler(CommandHandler("ideas",     cmd_ideas))
    app.add_handler(CommandHandler("newtokens", cmd_newtokens))
    app.add_handler(MessageHandler(filters.COMMAND, handle_unknown))

    return app


async def main():
    import os
    print("=== ENV DEBUG ===", flush=True)
    print(f"TELEGRAM_TOKEN set: {'YES' if os.getenv('TELEGRAM_TOKEN') else 'NO'}", flush=True)
    print(f"TELEGRAM_CHANNEL_ID: '{os.getenv('TELEGRAM_CHANNEL_ID', 'NOT SET')}'", flush=True)
    print(f"ADMIN_IDS: {ADMIN_IDS}", flush=True)
    print("=================", flush=True)

    if not config.TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN is not set in your .env file")
    if not config.TELEGRAM_CHANNEL_ID:
        raise ValueError("TELEGRAM_CHANNEL_ID is not set in your .env file")
    if not ADMIN_IDS:
        raise ValueError("No ADMIN_IDS set — bot will ignore all commands. Set ADMIN_1_ID in .env")

    app = build_app()

    await app.bot.set_my_commands([
        BotCommand("start",     "Welcome + overview"),
        BotCommand("trending",  "🎨 Current trending content ideas"),
        BotCommand("ideas",     "💡 Ideas for a specific topic"),
        BotCommand("signals",   "📈 Live Solana memecoin signals"),
        BotCommand("newtokens", "🆕 New token launches"),
        BotCommand("status",    "⚙️ Bot health check"),
    ])

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        auto_signal_check, "interval",
        minutes=config.SIGNAL_CHECK_INTERVAL,
        args=[app], id="signal_check"
    )
    scheduler.add_job(
        auto_trend_check, "interval",
        minutes=config.TREND_CHECK_INTERVAL,
        args=[app], id="trend_check"
    )
    scheduler.start()
    log.info(f"[scheduler] Signal check every {config.SIGNAL_CHECK_INTERVAL} min")
    log.info(f"[scheduler] Trend check every {config.TREND_CHECK_INTERVAL} min")

    log.info("⚡ PULSE BOT is running...")
    await app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())
