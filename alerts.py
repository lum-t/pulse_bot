"""
alerts.py — PULSE Message Formatter
Table style for market signals
Emoji rows + best time to post for content pulse
"""


def format_market_signal(signal: dict) -> str:
    """Single market signal — monospace table style."""
    p    = signal["probability"]
    name = signal["name"]
    sym  = signal["symbol"]
    url  = signal.get("dex_url", "")

    bull     = p["bullish"]
    pc1h     = p["price_change_1h"]
    pc24h    = p["price_change_24h"]
    vol1h    = p["volume_1h"]
    liq      = p["liquidity_usd"]
    buys     = p["txns_buys_1h"]
    sells    = p["txns_sells_1h"]

    filled   = round(bull / 10)
    empty    = 10 - filled
    hype_bar = "█" * filled + "░" * empty

    pc1h_str  = f"+{pc1h:.1f}%"  if pc1h  >= 0 else f"{pc1h:.1f}%"
    pc24h_str = f"+{pc24h:.1f}%" if pc24h >= 0 else f"{pc24h:.1f}%"
    pc_emoji  = "🟢" if pc1h >= 0 else "🔴"

    vol_str = f"${vol1h:,.0f}" if vol1h < 1_000_000 else f"${vol1h/1_000_000:.1f}M"
    liq_str = f"${liq:,.0f}"   if liq   < 1_000_000 else f"${liq/1_000_000:.1f}M"

    reason_lines = "\n".join([f"  • {r}" for r in p["reasons"][:3]]) or "  • No strong signals"

    table = (
        f"```\n"
        f"{'Metric':<12} {'Value':>12}\n"
        f"{'─'*26}\n"
        f"{'Hype Score':<12} {bull:>11}%\n"
        f"{'Hype Bar':<12} {hype_bar:>12}\n"
        f"{'1h Change':<12} {pc1h_str:>12}\n"
        f"{'24h Change':<12} {pc24h_str:>12}\n"
        f"{'Buyers':<12} {buys:>12,}\n"
        f"{'Sellers':<12} {sells:>12,}\n"
        f"{'Volume 1h':<12} {vol_str:>12}\n"
        f"{'Liquidity':<12} {liq_str:>12}\n"
        f"{'─'*26}\n"
        f"```"
    )

    msg = (
        f"📈 *MARKET PULSE — SIGNAL*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{pc_emoji} *{escape_md(name)}* `${escape_md(sym)}`\n\n"
        f"{table}\n"
        f"📌 *Why this signal:*\n{escape_md(reason_lines)}\n\n"
    )

    if url:
        msg += f"🔗 [View on DexScreener]({url})\n\n"

    msg += "_⚠️ DYOR — Not financial advice_"
    return msg


def format_signal_summary(signals: list[dict]) -> str:
    """Multi-signal table summary for auto channel posts."""
    if not signals:
        return format_no_signals()

    count = len(signals)
    rows = [
        "```",
        f"{'Token':<8} {'Hype':>5} {'Buy':>6} {'Sell':>6} {'1h':>7}",
        f"{'─'*38}",
    ]

    for s in signals[:8]:
        p      = s["probability"]
        sym    = s["symbol"][:7]
        bull   = p["bullish"]
        buys   = p["txns_buys_1h"]
        sells  = p["txns_sells_1h"]
        pc     = p["price_change_1h"]
        pc_str = f"+{pc:.1f}%" if pc >= 0 else f"{pc:.1f}%"
        arrow  = "▲" if pc >= 0 else "▼"
        rows.append(f"{sym:<8} {bull:>4}% {buys:>6,} {sells:>6,} {arrow}{pc_str:>6}")

    rows.append("```")
    table = "\n".join(rows)

    return (
        f"📈 *MARKET PULSE*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ *{count} signal{'s' if count > 1 else ''} detected on Solana*\n\n"
        f"{table}\n\n"
        f"_Use /signals for full breakdown per token_"
    )


def format_content_alert(idea: dict) -> str:
    """
    Full content idea output:
    Topic → search volume → ideas per platform → best time to post → hashtags
    """
    topic      = idea["topic"]
    status     = idea["status"]
    category   = idea["category"].upper()
    ideas      = idea["ideas"]
    hashtags   = " ".join(idea["hashtags"][:5])
    ts         = idea.get("timestamp", "")
    searches   = idea.get("trend_score", None)
    ai_powered = idea.get("ai_powered", False)
    post_times = idea.get("post_times", {})

    if searches:
        vol_str     = f"{searches:,}" if isinstance(searches, int) else str(searches)
        search_line = f"📊 *{escape_md(vol_str)}* people searching  |  🕐 {escape_md(ts)}\n"
    else:
        search_line = f"🕐 {escape_md(ts)}\n"

    ai_badge = "🤖 _AI\\-Powered Ideas_\n" if ai_powered else ""

    platform_emojis = {
        "YouTube":     "▶️",
        "TikTok":      "🎵",
        "X (Twitter)": "𝕏",
    }

    idea_lines = ""
    for platform, platform_ideas in ideas.items():
        emoji = platform_emojis.get(platform, "📱")
        idea_lines += f"\n{emoji} *{escape_md(platform)}*\n"
        for idx, idea_text in enumerate(platform_ideas, 1):
            idea_lines += f"  {idx}\\. {escape_md(idea_text)}\n"

    post_section = "\n⏰ *BEST TIME TO POST:*\n"
    for platform, info in post_times.items():
        emoji   = platform_emojis.get(platform, "📱")
        time    = escape_md(info["time"])
        day     = escape_md(info["day"])
        urgency = info["urgency"]
        post_section += f"  {emoji} *{escape_md(platform)}* → {time} \\({day}\\) {urgency}\n"

    msg = (
        f"🎨 *CONTENT PULSE*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔍 *{escape_md(topic)}*\n"
        f"📂 `{escape_md(category)}`  |  {status}\n"
        f"{search_line}"
        f"{ai_badge}"
        f"\n🎬 *Animation Ideas:*"
        f"{idea_lines}"
        f"{post_section}\n"
        f"#️⃣ {escape_md(hashtags)}"
    )
    return msg


def format_trend_summary(ideas: list[dict]) -> str:
    """Multi-trend summary for auto channel posts."""
    if not ideas:
        return format_no_trends()

    count = len(ideas)
    lines = [
        "🎨 *CONTENT PULSE*",
        "━━━━━━━━━━━━━━━━━━━━",
        f"🔥 *{count} trend{'s' if count > 1 else ''} detected right now*\n",
    ]

    platform_emojis = {
        "YouTube":     "▶️",
        "TikTok":      "🎵",
        "X (Twitter)": "𝕏",
    }

    for idea in ideas[:4]:
        topic      = escape_md(idea["topic"])
        status     = idea["status"]
        ai_tag     = " 🤖" if idea.get("ai_powered") else ""
        searches   = idea.get("trend_score")
        vol_str    = f" · 📊 {searches:,}" if searches else ""
        post_times = idea.get("post_times", {})

        lines.append(f"🔍 *{topic}* — {status}{ai_tag}{vol_str}")

        ideas_dict = idea.get("ideas", {})
        for platform, platform_ideas in ideas_dict.items():
            if platform_ideas:
                emoji = platform_emojis.get(platform, "📱")
                lines.append(f"  {emoji} {escape_md(platform_ideas[0])}")

        if post_times:
            most_urgent = min(post_times.items(), key=lambda x: x[1].get("hours_until", 99))
            p_name, p_info = most_urgent
            p_emoji = platform_emojis.get(p_name, "📱")
            lines.append(
                f"  ⏰ {p_emoji} Post on *{escape_md(p_name)}* at "
                f"{escape_md(p_info['time'])} — {p_info['urgency']}"
            )

        lines.append("")

    lines.append("_Use /trending for full ideas \\+ all post times_")
    return "\n".join(lines)


def format_new_tokens(tokens: list[dict]) -> str:
    """Format new token launches — table style."""
    if not tokens:
        return "🔍 No new Solana tokens found right now\\. Try again in a few minutes\\."

    rows = [
        "```",
        f"{'#':<3} {'Name':<20} {'Address'}",
        f"{'─'*42}",
    ]
    for i, t in enumerate(tokens[:8], 1):
        name = t.get("name", "Unknown Token")[:18]
        addr = (t.get("address", "") or "")[:8] + "…"
        rows.append(f"{i:<3} {name:<20} {addr}")
    rows.append("```")
    table = "\n".join(rows)

    links = []
    for i, t in enumerate(tokens[:8], 1):
        url  = t.get("url", "")
        name = escape_md(t.get("name", f"Token {i}")[:20])
        if url:
            links.append(f"{i}\\. [{name}]({url})")

    link_block = "\n".join(links)

    return (
        f"🆕 *NEW SOLANA TOKENS — LAST 24H*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{table}\n"
        f"🔗 *Links:*\n{link_block}\n\n"
        f"_⚠️ New tokens are extremely high risk\\. DYOR\\._"
    )


def format_signal_history(history: list[dict]) -> str:
    """Format signal history — table style."""
    if not history:
        return (
            "📋 *SIGNAL HISTORY*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "😴 No signals recorded yet\\."
        )

    rows = [
        "```",
        f"{'#':<3} {'Token':<8} {'Hype':>5} {'1h':>8} {'Time'}",
        f"{'─'*42}",
    ]
    for i, s in enumerate(history[:10], 1):
        sym  = s.get("symbol", "???")[:7]
        bull = s.get("bullish", 50)
        pc   = s.get("price_change_1h", 0)
        pc_s = f"+{pc:.1f}%" if pc >= 0 else f"{pc:.1f}%"
        ts   = s.get("timestamp", "")[:16].replace("T", " ")[5:]
        rows.append(f"{i:<3} {sym:<8} {bull:>4}% {pc_s:>8} {ts}")
    rows.append("```")

    return (
        "📋 *SIGNAL HISTORY — LAST 10*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(rows)
        + "\n\n_⚠️ Historical signals — not financial advice_"
    )


def format_no_signals() -> str:
    return (
        "📈 *MARKET PULSE*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "😴 No significant signals right now\\.\n\n"
        "_Markets are quiet\\. Signals fire when price or volume spikes\\._"
    )


def format_no_trends() -> str:
    return (
        "🎨 *CONTENT PULSE*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "😴 No strong trends detected right now\\.\n\n"
        "_Try /ideas with a specific topic instead\\._"
    )


def format_pnl_card(snapshot: dict) -> str:
    """
    Live PnL card for a single OPEN signal.
    Called by /pnl refresh or mid-update.
    """
    token      = escape_md(snapshot.get("token", "???"))
    pnl        = snapshot.get("pnl_pct", 0.0)
    entry      = snapshot.get("entry_price", 0)
    live       = snapshot.get("live_price", entry)
    hold       = snapshot.get("hold_hours", 0.0)
    score      = snapshot.get("gemini_score", "—")
    address    = snapshot.get("address", "")

    pnl_str    = f"+{pnl:.1f}%" if pnl >= 0 else f"{pnl:.1f}%"
    pnl_emoji  = "🚀" if pnl >= 50 else "🟢" if pnl >= 20 else "🟡" if pnl >= 0 else "🟠" if pnl >= -15 else "🔴"
    entry_str  = f"${entry:.8f}" if entry < 0.01 else f"${entry:.4f}"
    live_str   = f"${live:.8f}"  if live  < 0.01 else f"${live:.4f}"

    bar_filled = max(0, min(10, round((pnl + 30) / 8)))
    bar        = "█" * bar_filled + "░" * (10 - bar_filled)

    dex_link = f"\n🔗 [DexScreener](https://dexscreener.com/solana/{address})" if address else ""

    return (
        f"📊 *PNL CARD — LIVE*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{pnl_emoji} *{token}*  `{pnl_str}`\n\n"
        f"```\n"
        f"{'Entry Price':<14} {entry_str:>12}\n"
        f"{'Live Price':<14} {live_str:>12}\n"
        f"{'PnL':<14} {pnl_str:>12}\n"
        f"{'PnL Bar':<14} {bar:>12}\n"
        f"{'Hold Time':<14} {hold:.1f}h{' ':>9}\n"
        f"{'AI Score':<14} {str(score):>11}/100\n"
        f"{'Status':<14} {'OPEN 🟡':>12}\n"
        f"```"
        f"{dex_link}\n\n"
        f"_⚠️ DYOR — Not financial advice_"
    )


def format_pnl_closed(record: dict) -> str:
    """
    Final PnL card when a signal closes — TP, SL, or timeout.
    Sent automatically to admin chat.
    """
    token      = escape_md(record.get("token", "???"))
    pnl        = record.get("pnl_pct", 0.0)
    entry      = record.get("entry_price", 0)
    exit_p     = record.get("exit_price", entry)
    hold       = record.get("hold_hours", 0.0)
    score      = record.get("gemini_score", "—")
    reason     = record.get("close_reason", "timeout")
    win        = record.get("win", False)
    address    = record.get("address", "")

    pnl_str   = f"+{pnl:.1f}%" if pnl >= 0 else f"{pnl:.1f}%"
    entry_str = f"${entry:.8f}" if entry < 0.01 else f"${entry:.4f}"
    exit_str  = f"${exit_p:.8f}" if exit_p < 0.01 else f"${exit_p:.4f}"

    reason_labels = {
        "take_profit": "✅ TAKE PROFIT HIT",
        "stop_loss":   "❌ STOP LOSS HIT",
        "timeout":     "⏱ AUTO\\-CLOSED \\(8hrs\\)",
        "manual":      "🔒 MANUALLY CLOSED",
    }
    result_label = reason_labels.get(reason, "CLOSED")
    result_emoji = "🏆" if win else "💀"
    dex_link     = f"\n🔗 [DexScreener](https://dexscreener.com/solana/{address})" if address else ""

    return (
        f"📊 *PNL CARD — CLOSED*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{result_emoji} *{token}*  `{pnl_str}`\n"
        f"*{result_label}*\n\n"
        f"```\n"
        f"{'Entry Price':<14} {entry_str:>12}\n"
        f"{'Exit Price':<14} {exit_str:>12}\n"
        f"{'PnL':<14} {pnl_str:>12}\n"
        f"{'Hold Time':<14} {hold:.1f}h{' ':>9}\n"
        f"{'AI Score':<14} {str(score):>11}/100\n"
        f"{'Result':<14} {'WIN ✅' if win else 'LOSS ❌':>12}\n"
        f"```"
        f"{dex_link}\n\n"
        f"_⚠️ DYOR — Not financial advice_"
    )


def format_pnl_mid_update(snapshot: dict) -> str:
    """
    4hr mid-update card sent automatically to admin chat.
    Same as live card but labelled as mid-update.
    """
    base = format_pnl_card(snapshot)
    # Replace the header line only
    return base.replace(
        "📊 *PNL CARD — LIVE*",
        "⏰ *PNL MID\\-UPDATE \\(4hrs\\)*"
    )


def format_pnl_scorecard(scorecard: dict, ai_comment: str = "") -> str:
    """
    Full bot scorecard — shown when admin runs /pnl.
    Shows overall win rate, best/worst trade, open signals count.
    """
    total    = scorecard.get("total", 0)
    wins     = scorecard.get("wins", 0)
    losses   = scorecard.get("losses", 0)
    win_rate = scorecard.get("win_rate", 0.0)
    avg_prof = scorecard.get("avg_profit", 0.0)
    avg_loss = scorecard.get("avg_loss", 0.0)
    best     = scorecard.get("best_trade")
    worst    = scorecard.get("worst_trade")
    open_c   = scorecard.get("open_count", 0)

    if total == 0:
        return (
            "📊 *BOT SCORECARD*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "😴 No closed signals yet\\.\n\n"
            f"📂 Open signals: *{open_c}*\n\n"
            "_Fire some signals and come back\\!_"
        )

    wr_emoji  = "🔥" if win_rate >= 70 else "🟢" if win_rate >= 55 else "🟡" if win_rate >= 45 else "🔴"
    avg_p_str = f"+{avg_prof:.1f}%" if avg_prof >= 0 else f"{avg_prof:.1f}%"
    avg_l_str = f"{avg_loss:.1f}%"

    best_line  = (
        f"🏆 Best:   *{escape_md(best['token'])}*  `+{best['pnl_pct']:.1f}%`\n"
        if best else ""
    )
    worst_line = (
        f"💀 Worst:  *{escape_md(worst['token'])}*  `{worst['pnl_pct']:.1f}%`\n"
        if worst else ""
    )

    ai_line = f"\n🤖 _{escape_md(ai_comment)}_\n" if ai_comment else ""

    return (
        f"📊 *BOT SCORECARD*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{wr_emoji} *Win Rate: {win_rate:.1f}%*  "
        f"\\({wins}W / {losses}L\\)\n\n"
        f"```\n"
        f"{'Total Signals':<16} {total:>8}\n"
        f"{'Wins':<16} {wins:>8}\n"
        f"{'Losses':<16} {losses:>8}\n"
        f"{'Win Rate':<16} {win_rate:>7.1f}%\n"
        f"{'Avg Profit':<16} {avg_p_str:>8}\n"
        f"{'Avg Loss':<16} {avg_l_str:>8}\n"
        f"{'Open Now':<16} {open_c:>8}\n"
        f"```\n"
        f"{best_line}"
        f"{worst_line}"
        f"{ai_line}\n"
        f"_⚠️ Past performance ≠ future results_"
    )


def escape_md(text: str) -> str:
    """Escape special MarkdownV2 characters for Telegram."""
    if not text:
        return ""
    text = str(text)
    special = r"\_*[]()~`>#+-=|{}.!"
    for ch in special:
        text = text.replace(ch, f"\\{ch}")
    return text
