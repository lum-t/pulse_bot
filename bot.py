"""
bot.py — PULSE BOT
Main Telegram bot entry point
Handles commands, scheduler, and message routing
"""

import logging
import asyncio
from datetime import datetime, timezone

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
    format_signal_summary, format_trend_summary, escape_md,
    format_pnl_card, format_pnl_closed, format_pnl_mid_update,
    format_pnl_scorecard,
)
from pnl import (
    record_signal, refresh_all_open, check_mid_updates,
    get_scorecard, gemini_scorecard_comment,
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
        "🎨 /trending — current trending content ideas\n"
        "💡 /ideas \\[topic\\] — ideas for any topic\n\n"
        "📈 /signals — live Solana signals\n"
        "🆕 /newtokens — new token launches\n\n"
        "📊 /pnl — live PnL refresh \\+ bot scorecard\n"
        "👛 /wallets — tracked whale wallets\n\n"
        "⚙️ /status — bot health check\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "_PULSE is not financial advice\\._\n"
        "_All trading signals are for information only\\._"
    )
    await safe_reply(update, msg)


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, ctx):
        return
    now = datetime.now(timezone.utc).strftime("%Y\\-%m\\-%d %H:%M UTC")
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

    for signal in signals[:3]:
        try:
            msg = format_market_signal(signal)
            await safe_reply(update, msg)

            addr   = signal.get("token_address") or signal.get("address", "")
            gscore = signal.get("gemini_score", 0)
            if addr:
                await record_signal(
                    token=signal.get("symbol", signal.get("name", "???")),
                    token_address=addr,
                    gemini_score=gscore,
                )
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


async def cmd_pnl(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin only — live PnL refresh + bot scorecard."""
    if not await admin_only(update, ctx):
        return

    await safe_reply(update, "📊 *Refreshing PnL\\.\\.\\.*")

    try:
        snapshots = await refresh_all_open()

        if not snapshots:
            await safe_reply(
                update,
                "📊 *PnL TRACKER*\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "😴 No open signals right now\\.\n\n"
                "_Signals are recorded automatically when /signals is run\\._"
            )
        else:
            for snap in snapshots:
                try:
                    if snap.get("just_closed"):
                        msg = format_pnl_closed(snap)
                    else:
                        msg = format_pnl_card(snap)
                    await safe_reply(update, msg)
                except Exception as e:
                    log.error(f"[bot] Failed to format PnL card: {e}")

        # Always show scorecard at the end
        scorecard  = get_scorecard()
        ai_comment = await gemini_scorecard_comment(scorecard)
        sc_msg     = format_pnl_scorecard(scorecard, ai_comment)
        await safe_reply(update, sc_msg)

    except Exception as e:
        log.error(f"[bot] cmd_pnl crashed: {e}")
        await safe_reply(update, "⚠️ PnL refresh failed\\. Check logs for details\\.")


async def cmd_wallets(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin only — show currently tracked whale wallets."""
    if not await admin_only(update, ctx):
        return

    try:
        from pnl import _load
        data     = _load()
        open_sig = data.get("open", {})

        if not open_sig:
            await safe_reply(
                update,
                "👛 *TRACKED WALLETS*\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "😴 No wallets being tracked yet\\.\n\n"
                "_Run /signals to start tracking new entries\\._"
            )
            return

        lines = [
            "👛 *TRACKED WHALE WALLETS*",
            "━━━━━━━━━━━━━━━━━━━━",
        ]
        for i, (addr, record) in enumerate(open_sig.items(), 1):
            token = escape_md(record.get("token", "???"))
            short = addr[:6] + "\\.\\.\\." + addr[-4:]
            score = record.get("gemini_score", "—")
            lines.append(f"{i}\\. *{token}* — `{short}` — AI: {score}/100")

        lines.append("\n_Wallets auto\\-refresh every 6 hours_")
        await safe_reply(update, "\n".join(lines))

    except Exception as e:
        log.error(f"[bot] cmd_wallets crashed: {e}")
        await safe_reply(update, "⚠️ Could not load wallet data\\.")


async def handle_unknown(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, ctx):
        return
    await safe_reply(update, "❓ Unknown command\\. Type /start to see all commands\\.")


# ─── Scheduled Auto-Alerts ────────────────────────────────────

async def _broadcast(app: Application, msg: str, label: str):
    """Send msg to channel + both admin DMs."""
    targets = []

    if config.TELEGRAM_CHANNEL_ID:
        targets.append(("channel", config.TELEGRAM_CHANNEL_ID))

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


async def auto_pnl_check(app: Application):
    """Runs hourly — sends mid-updates and auto-closes signals that hit TP/SL/timeout."""
    log.info("[scheduler] Running PnL mid-update check...")
    try:
        updates = await check_mid_updates()
    except Exception as e:
        log.error(f"[scheduler] check_mid_updates() crashed: {e}")
        return

    for update_data in updates:
        try:
            if update_data.get("type") == "closed":
                msg = format_pnl_closed(update_data)
            else:
                msg = format_pnl_mid_update(update_data)

            for chat_id in config.ADMIN_CHAT_IDS:
                try:
                    await app.bot.send_message(
                        chat_id=chat_id,
                        text=msg,
                        parse_mode=ParseMode.MARKDOWN_V2
                    )
                except Exception as e:
                    log.error(f"[scheduler] PnL update failed to admin {chat_id}: {e}")
        except Exception as e:
            log.error(f"[scheduler] Failed to format PnL update: {e}")


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
    app.add_handler(CommandHandler("pnl",       cmd_pnl))
    app.add_handler(CommandHandler("wallets",   cmd_wallets))
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
        BotCommand("pnl",       "📊 Live PnL refresh + bot scorecard"),
        BotCommand("wallets",   "👛 Tracked whale wallets"),
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
    scheduler.add_job(
        auto_pnl_check, "interval",
        minutes=60,
        args=[app], id="pnl_check"
    )
    scheduler.start()
    log.info(f"[scheduler] Signal check every {config.SIGNAL_CHECK_INTERVAL} min")
    log.info(f"[scheduler] Trend check every {config.TREND_CHECK_INTERVAL} min")
    log.info(f"[scheduler] PnL mid-update check every 60 min")

    log.info("⚡ PULSE BOT is running...")
    await app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())
