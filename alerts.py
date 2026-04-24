"""
alerts.py — PULSE Message Formatter
Formats signals and content ideas into clean Telegram messages
Two completely separate alert types — never mixed
"""


def format_market_signal(signal: dict) -> str:
    """
    Format a single market signal into a Telegram message.
    📈 MARKET PULSE — trading signals only, no content ideas
    """
    p    = signal["probability"]
    name = signal["name"]
    sym  = signal["symbol"]
    url  = signal.get("dex_url", "")

    bull = p["bullish"]
    bear = p["bearish"]
    bar  = "🟩" * (bull // 20) + "🟥" * (bear // 20)

    pc1h     = p["price_change_1h"]
    pc_emoji = "🟢" if pc1h >= 0 else "🔴"
    pc_str   = f"+{pc1h:.1f}%" if pc1h >= 0 else f"{pc1h:.1f}%"

    vol     = p["volume_1h"]
    vol_str = f"${vol:,.0f}" if vol < 1_000_000 else f"${vol/1_000_000:.1f}M"

    liq     = p["liquidity_usd"]
    liq_str = f"${liq:,.0f}" if liq < 1_000_000 else f"${liq/1_000_000:.1f}M"

    reason_lines = "\n".join([f"  • {r}" for r in p["reasons"][:3]]) if p["reasons"] else "  • No strong signals"

    msg = (
        f"📈 *MARKET PULSE — SIGNAL DETECTED*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🪙 *{name}* `${sym}`\n\n"
        f"{pc_emoji} Price Change \\(1h\\): *{pc_str}*\n"
        f"💧 Liquidity: *{liq_str}*\n"
        f"📊 Volume \\(1h\\): *{vol_str}*\n"
        f"🔄 Buys / Sells: *{p['txns_buys_1h']} / {p['txns_sells_1h']}*\n\n"
        f"🧠 *Probability Score*\n"
        f"Bullish: *{bull}%*  |  Bearish: *{bear}%*\n"
        f"{bar}\n\n"
        f"📌 *Why this signal:*\n{reason_lines}\n\n"
    )

    if url:
        msg += f"🔗 [View on DexScreener]({url})\n\n"

    msg += "⚠️ _DYOR — Not financial advice_"
    return msg


def format_content_alert(idea: dict) -> str:
    """
    Format a content idea into a Telegram message.
    🎨 CONTENT PULSE — animation ideas only, no trading signals
    """
    topic      = idea["topic"]
    status     = idea["status"]
    category   = idea["category"].upper()
    ideas      = idea["ideas"]
    hashtags   = " ".join(idea["hashtags"][:5])
    ts         = idea.get("timestamp", "")
    ai_powered = idea.get("ai_powered", False)

    ai_badge = "🤖 _AI\\-Generated Ideas_\n" if ai_powered else ""

    platform_sections = ""
    for platform, platform_ideas in ideas.items():
        emoji = {"YouTube": "▶️", "TikTok": "🎵", "X (Twitter)": "𝕏"}.get(platform, "📱")
        platform_sections += f"\n{emoji} *{platform}*\n"
        for i, idea_text in enumerate(platform_ideas, 1):
            platform_sections += f"  {i}\\. {escape_md(idea_text)}\n"

    msg = (
        f"🎨 *CONTENT PULSE — IDEA ALERT*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔍 Topic: *{escape_md(topic)}*\n"
        f"📂 Category: `{category}`\n"
        f"📡 Status: {status}\n"
        f"🕐 {ts}\n"
        f"{ai_badge}"
        f"\n🎬 *Animation Ideas:*"
        f"{platform_sections}\n"
        f"#️⃣ *Hashtags:*\n{escape_md(hashtags)}"
    )
    return msg


def format_new_tokens(tokens: list[dict]) -> str:
    """Format new token launches for /newtokens command."""
    if not tokens:
        return "🔍 No new Solana tokens found right now\\. Try again in a few minutes\\."

    lines = ["📈 *NEW SOLANA TOKENS — LAST 24H*\n━━━━━━━━━━━━━━━━━━━━"]
    for i, t in enumerate(tokens[:8], 1):
        name = escape_md(t.get("name", "Unknown Token"))
        url  = t.get("url", "")
        addr = t.get("address", "")[:8] + "..." if t.get("address") else "N/A"

        line  = f"\n*{i}.* {name}\n"
        line += f"   `{addr}`\n"
        if url:
            line += f"   [View on DexScreener]({url})\n"
        lines.append(line)

    lines.append("\n⚠️ _New tokens are extremely high risk\\. DYOR\\._")
    return "\n".join(lines)


def format_signal_summary(signals: list[dict]) -> str:
    """Lightweight summary for auto signal checks posted to channel."""
    count = len(signals)
    lines = [
        "📈 *MARKET PULSE*",
        "━━━━━━━━━━━━━━━━━━━━",
        f"⚡ *{count} signal{'s' if count > 1 else ''} detected on Solana*\n",
    ]

    for signal in signals[:5]:
        sym    = escape_md(signal["symbol"])
        pc     = signal["probability"]["price_change_1h"]
        arrow  = "🟢" if pc >= 0 else "🔴"
        pc_str = f"\\+{pc:.1f}%" if pc >= 0 else f"{pc:.1f}%"
        lines.append(f"• `${sym}` — {pc_str} {arrow}")

    lines.append("")
    lines.append("_Use /signals for the full breakdown_")
    return "\n".join(lines)


def format_trend_summary(ideas: list[dict]) -> str:
    """Lightweight summary for auto trend checks posted to channel."""
    count = len(ideas)
    lines = [
        "🎨 *CONTENT PULSE*",
        "━━━━━━━━━━━━━━━━━━━━",
        f"🔥 *{count} trend{'s' if count > 1 else ''} detected right now*\n",
    ]

    for idea in ideas[:5]:
        topic  = escape_md(idea["topic"])
        status = idea["status"]
        ai_tag = " 🤖" if idea.get("ai_powered") else ""
        lines.append(f"• {topic} — {status}{ai_tag}")

    lines.append("")
    lines.append("_Use /trending to see the full animation ideas_")
    return "\n".join(lines)


def format_signal_history(history: list[dict]) -> str:
    """Format signal history for /history command."""
    if not history:
        return (
            "📋 *SIGNAL HISTORY*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "😴 No signals recorded yet\\."
        )

    lines = [
        "📋 *SIGNAL HISTORY — LAST 10*",
        "━━━━━━━━━━━━━━━━━━━━",
    ]

    for i, s in enumerate(history, 1):
        sym      = escape_md(s.get("symbol", "???"))
        name     = escape_md(s.get("name", "Unknown"))
        bull     = s.get("bullish", 50)
        pc       = s.get("price_change_1h", 0)
        arrow    = "🟢" if pc >= 0 else "🔴"
        pc_str   = escape_md(f"+{pc:.1f}%" if pc >= 0 else f"{pc:.1f}%")
        ts_raw   = s.get("timestamp", "")[:16].replace("T", " ")
        ts       = escape_md(ts_raw)

        lines.append(
            f"\n*{i}\\.* `${sym}` — {name}\n"
            f"   {arrow} {pc_str}  •  Bullish: *{bull}%*\n"
            f"   🕐 _{ts} UTC_"
        )

    lines.append("\n⚠️ _Historical signals — not financial advice_")
    return "\n".join(lines)


def format_no_signals() -> str:
    return (
        "📈 *MARKET PULSE*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "😴 No significant signals right now\\.\n\n"
        "_Markets are quiet\\. Signals appear when price or volume spikes\\._"
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
    special = r"\_*[]()~`>#+-=|{}.!"
    for ch in special:
        text = text.replace(ch, f"\\{ch}")
    return text
