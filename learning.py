"""
learning.py — PULSE Adaptive Learning Engine
Extracts lessons from closed trades and injects them into future signal scoring.
The bot gets smarter after every loss — and remembers what makes winners too.
"""

import json
import os
import logging
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger(__name__)

LEARNING_FILE    = os.getenv("LEARNING_FILE", "trade_lessons.json")
MAX_LESSONS      = 100   # Rolling window — old lessons drop off
RECENT_LESSONS_N = 15    # How many recent lessons to inject into AI prompts


# ══════════════════════════════════════════════════════════════════
# SECTION 1 — PERSISTENCE
# ══════════════════════════════════════════════════════════════════

def _load() -> dict:
    if not os.path.exists(LEARNING_FILE):
        return {"lessons": [], "pattern_summary": "", "last_updated": None}
    try:
        with open(LEARNING_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"lessons": [], "pattern_summary": "", "last_updated": None}


def _save(data: dict) -> None:
    try:
        with open(LEARNING_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except IOError as e:
        log.error(f"[learning] Failed to save lessons: {e}")


# ══════════════════════════════════════════════════════════════════
# SECTION 2 — LESSON EXTRACTION (called by pnl.py on close)
# ══════════════════════════════════════════════════════════════════

def extract_lesson(closed_trade: dict) -> dict:
    """
    Extract a structured lesson from a closed trade.
    Called automatically by pnl.py whenever a signal closes.
    """
    pnl          = closed_trade.get("pnl_pct", 0)
    reason       = closed_trade.get("close_reason", "timeout")
    hold_hours   = closed_trade.get("hold_hours", 0)
    entry_price  = closed_trade.get("entry_price", 0)
    exit_price   = closed_trade.get("exit_price", 0)
    gemini_score = closed_trade.get("gemini_score", 0)
    token        = closed_trade.get("token", "Unknown")
    win          = closed_trade.get("win", False)

    # Classify outcome
    if pnl >= 50:
        outcome = "big_win"
    elif pnl >= 20:
        outcome = "win"
    elif pnl >= 0:
        outcome = "small_win"
    elif pnl >= -15:
        outcome = "small_loss"
    elif pnl >= -30:
        outcome = "loss"
    else:
        outcome = "big_loss"

    # Extract warning patterns for losses
    warning_patterns = []

    if not win:
        if gemini_score < 60:
            warning_patterns.append(f"low_ai_score:{gemini_score}")
        if hold_hours > 6:
            warning_patterns.append("held_too_long")
        if reason == "stop_loss":
            warning_patterns.append("hit_stop_loss")
        if reason == "timeout":
            warning_patterns.append("no_momentum_timeout")
        if entry_price and exit_price:
            drop_pct = ((exit_price - entry_price) / entry_price) * 100
            if drop_pct < -20:
                warning_patterns.append("sharp_reversal_after_entry")

    # Extract success patterns for wins
    success_patterns = []

    if win:
        if gemini_score >= 75:
            success_patterns.append(f"high_ai_score:{gemini_score}")
        if reason == "take_profit":
            success_patterns.append("hit_take_profit_clean")
        if hold_hours <= 4:
            success_patterns.append("fast_mover_quick_exit")
        if pnl >= 50:
            success_patterns.append("strong_momentum_follow_through")

    lesson = {
        "token":            token,
        "timestamp":        datetime.now(timezone.utc).isoformat(),
        "outcome":          outcome,
        "win":              win,
        "pnl_pct":          round(pnl, 2),
        "hold_hours":       round(hold_hours, 1),
        "close_reason":     reason,
        "gemini_score":     gemini_score,
        "warning_patterns": warning_patterns,
        "success_patterns": success_patterns,
    }

    log.info(f"[learning] Lesson extracted: {token} → {outcome} ({pnl:+.1f}%)")
    return lesson


def save_lesson(closed_trade: dict) -> None:
    """
    Extract and persist a lesson from a closed trade.
    Called by pnl.py. Rolling window — oldest lessons drop off.
    """
    lesson = extract_lesson(closed_trade)
    data   = _load()

    data["lessons"].insert(0, lesson)
    data["lessons"] = data["lessons"][:MAX_LESSONS]
    data["last_updated"] = datetime.now(timezone.utc).isoformat()

    _save(data)
    log.info(f"[learning] Lesson saved. Total lessons: {len(data['lessons'])}")


# ══════════════════════════════════════════════════════════════════
# SECTION 3 — PATTERN ANALYSIS (for AI prompt injection)
# ══════════════════════════════════════════════════════════════════

def get_recent_lessons(n: int = RECENT_LESSONS_N) -> list[dict]:
    """Return the N most recent lessons."""
    data = _load()
    return data.get("lessons", [])[:n]


def build_learning_context() -> str:
    """
    Build a concise learning context string to inject into AI scoring prompts.
    Summarises recent wins and losses into actionable patterns.
    Returns empty string if not enough data yet.
    """
    lessons = get_recent_lessons(RECENT_LESSONS_N)

    if len(lessons) < 3:
        return ""   # Not enough history to learn from yet

    wins   = [l for l in lessons if l["win"]]
    losses = [l for l in lessons if not l["win"]]

    # Aggregate warning patterns from losses
    all_warnings: dict[str, int] = {}
    for lesson in losses:
        for pattern in lesson.get("warning_patterns", []):
            all_warnings[pattern] = all_warnings.get(pattern, 0) + 1

    # Aggregate success patterns from wins
    all_successes: dict[str, int] = {}
    for lesson in wins:
        for pattern in lesson.get("success_patterns", []):
            all_successes[pattern] = all_successes.get(pattern, 0) + 1

    # Top patterns
    top_warnings  = sorted(all_warnings.items(),  key=lambda x: x[1], reverse=True)[:5]
    top_successes = sorted(all_successes.items(), key=lambda x: x[1], reverse=True)[:5]

    # Recent loss details (last 5 losses)
    recent_losses = [l for l in losses[:5]]

    # Win rate
    win_rate = round(len(wins) / len(lessons) * 100, 1) if lessons else 0

    # Build context string
    lines = [
        f"LEARNING CONTEXT (from last {len(lessons)} trades | win rate: {win_rate}%):",
        "",
    ]

    if recent_losses:
        lines.append("⚠️ RECENT LOSS PATTERNS — avoid these setups:")
        for lesson in recent_losses:
            patterns = ", ".join(lesson.get("warning_patterns", ["unknown"])) or "unclear"
            lines.append(
                f"  - {lesson['token']}: {lesson['pnl_pct']:+.1f}% ({lesson['close_reason']}) "
                f"| AI score was {lesson['gemini_score']} | patterns: {patterns}"
            )
        lines.append("")

    if top_warnings:
        lines.append("🚫 MOST COMMON FAILURE PATTERNS:")
        for pattern, count in top_warnings:
            lines.append(f"  - {pattern} (seen {count}x in recent losses)")
        lines.append("")

    if top_successes:
        lines.append("✅ WINNING SIGNAL PATTERNS:")
        for pattern, count in top_successes:
            lines.append(f"  - {pattern} (seen {count}x in recent wins)")
        lines.append("")

    lines.append(
        "Use this context to be STRICTER on signals that share loss patterns "
        "and MORE CONFIDENT on signals that match winning patterns. "
        "Penalise heavily any signal with 2+ matching failure patterns."
    )

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════
# SECTION 4 — STATS (for /learn command in bot)
# ══════════════════════════════════════════════════════════════════

def get_learning_stats() -> dict:
    """
    Returns a summary of what the bot has learned — for /learn command.
    """
    lessons = get_recent_lessons(MAX_LESSONS)

    if not lessons:
        return {
            "total_lessons":   0,
            "wins":            0,
            "losses":          0,
            "win_rate":        0.0,
            "top_warnings":    [],
            "top_successes":   [],
            "last_updated":    None,
            "most_costly_loss": None,
            "best_win":        None,
        }

    wins   = [l for l in lessons if l["win"]]
    losses = [l for l in lessons if not l["win"]]

    all_warnings: dict[str, int] = {}
    for lesson in losses:
        for p in lesson.get("warning_patterns", []):
            all_warnings[p] = all_warnings.get(p, 0) + 1

    all_successes: dict[str, int] = {}
    for lesson in wins:
        for p in lesson.get("success_patterns", []):
            all_successes[p] = all_successes.get(p, 0) + 1

    most_costly = min(losses, key=lambda l: l["pnl_pct"]) if losses else None
    best_win    = max(wins,   key=lambda l: l["pnl_pct"]) if wins   else None

    data = _load()

    return {
        "total_lessons":   len(lessons),
        "wins":            len(wins),
        "losses":          len(losses),
        "win_rate":        round(len(wins) / len(lessons) * 100, 1),
        "top_warnings":    sorted(all_warnings.items(),  key=lambda x: x[1], reverse=True)[:5],
        "top_successes":   sorted(all_successes.items(), key=lambda x: x[1], reverse=True)[:5],
        "last_updated":    data.get("last_updated"),
        "most_costly_loss": most_costly,
        "best_win":        best_win,
    }


def format_learning_report() -> str:
    """
    Format the learning stats as a clean Telegram message.
    Used by /learn command in bot.py.
    """
    stats = get_learning_stats()

    if stats["total_lessons"] == 0:
        return (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🧠 BOT LEARNING STATUS\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "No lessons yet — bot needs at least 3 closed trades to start learning.\n\n"
            "Keep running signals and it'll get smarter automatically! 🚀"
        )

    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "🧠 WHAT THE BOT HAS LEARNED",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"📊 Lessons Recorded: {stats['total_lessons']}",
        f"✅ Wins: {stats['wins']}  |  ❌ Losses: {stats['losses']}",
        f"🎯 Learning Win Rate: {stats['win_rate']}%",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "🚫 TOP FAILURE PATTERNS",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    if stats["top_warnings"]:
        for pattern, count in stats["top_warnings"]:
            label = pattern.replace("_", " ").title()
            lines.append(f"  • {label} → seen {count}x in losses")
    else:
        lines.append("  Not enough loss data yet")

    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "✅ TOP WIN PATTERNS",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    if stats["top_successes"]:
        for pattern, count in stats["top_successes"]:
            label = pattern.replace("_", " ").title()
            lines.append(f"  • {label} → seen {count}x in wins")
    else:
        lines.append("  Not enough win data yet")

    if stats["most_costly_loss"]:
        l = stats["most_costly_loss"]
        lines += [
            "",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "💸 MOST COSTLY LOSS",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"  Token: {l['token']}",
            f"  PnL: {l['pnl_pct']:+.1f}%  |  Hold: {l['hold_hours']}h",
            f"  AI Score Was: {l['gemini_score']}",
            f"  Patterns: {', '.join(l['warning_patterns']) or 'none identified'}",
        ]

    if stats["best_win"]:
        w = stats["best_win"]
        lines += [
            "",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "🚀 BEST WIN",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"  Token: {w['token']}",
            f"  PnL: {w['pnl_pct']:+.1f}%  |  Hold: {w['hold_hours']}h",
            f"  AI Score Was: {w['gemini_score']}",
            f"  Patterns: {', '.join(w['success_patterns']) or 'none identified'}",
        ]

    if stats["last_updated"]:
        try:
            dt = datetime.fromisoformat(stats["last_updated"])
            lines += ["", f"🕐 Last updated: {dt.strftime('%d %b %H:%M UTC')}"]
        except Exception:
            pass

    return "\n".join(lines)
