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


def escape_md(text: str) -> str:
    """Escape special MarkdownV2 characters for Telegram."""
    if not text:
        return ""
    text = str(text)
    special = r"\_*[]()~`>#+-=|{}.!"
    for ch in special:
        text = text.replace(ch, f"\\{ch}")
    return text
