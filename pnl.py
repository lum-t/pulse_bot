import json
import os
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
import aiohttp
import google.generativeai as genai

# ── Config ────────────────────────────────────────────────────────────────────
PNL_FILE = os.getenv("PNL_FILE_PATH", "pnl_data.json")
TAKE_PROFIT = float(os.getenv("TAKE_PROFIT_PERCENT", 50)) / 100   # 0.50
STOP_LOSS   = float(os.getenv("STOP_LOSS_PERCENT",   30)) / 100   # 0.30
AUTO_CLOSE_HOURS  = int(os.getenv("AUTO_CLOSE_HOURS", 8))
MID_UPDATE_HOURS  = int(os.getenv("MID_UPDATE_HOURS", 4))
DEXSCREENER_BASE  = "https://api.dexscreener.com/latest/dex"

genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))
gemini = genai.GenerativeModel("gemini-2.0-flash")

logger = logging.getLogger(__name__)


# ── Persistence ───────────────────────────────────────────────────────────────

def _load() -> dict:
    """Load PnL data from disk."""
    if not os.path.exists(PNL_FILE):
        return {"open": {}, "closed": []}
    try:
        with open(PNL_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"open": {}, "closed": []}


def _save(data: dict) -> None:
    """Persist PnL data to disk."""
    try:
        with open(PNL_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except IOError as e:
        logger.error(f"Failed to save PnL data: {e}")


# ── DexScreener price fetch ───────────────────────────────────────────────────

async def get_live_price(token_address: str) -> Optional[float]:
    """Fetch current price from DexScreener."""
    url = f"{DEXSCREENER_BASE}/tokens/{token_address}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                pairs = data.get("pairs") or []
                if not pairs:
                    return None
                # Pick the pair with highest liquidity
                pairs_sorted = sorted(
                    pairs,
                    key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0),
                    reverse=True
                )
                price_str = pairs_sorted[0].get("priceUsd")
                return float(price_str) if price_str else None
    except Exception as e:
        logger.error(f"Price fetch error for {token_address}: {e}")
        return None


# ── Signal entry ──────────────────────────────────────────────────────────────

async def record_signal(
    token: str,
    token_address: str,
    gemini_score: int,
    chain: str = "solana"
) -> Optional[dict]:
    """
    Called when a new signal fires.
    Fetches entry price and saves the open position.
    Returns the saved record or None on failure.
    """
    entry_price = await get_live_price(token_address)
    if entry_price is None:
        logger.warning(f"Could not get entry price for {token} ({token_address})")
        return None

    now = datetime.now(timezone.utc).isoformat()
    record = {
        "token":         token,
        "address":       token_address,
        "chain":         chain,
        "entry_price":   entry_price,
        "gemini_score":  gemini_score,
        "entry_time":    now,
        "mid_alerted":   False,   # True after 4hr mid-update sent
        "status":        "open",
    }

    data = _load()
    data["open"][token_address] = record
    _save(data)
    logger.info(f"Signal recorded: {token} @ ${entry_price}")
    return record


# ── PnL calculation ───────────────────────────────────────────────────────────

def _calc_pnl(entry: float, current: float) -> float:
    """Return PnL as a decimal, e.g. 0.84 = +84%."""
    if entry == 0:
        return 0.0
    return (current - entry) / entry


def _pnl_emoji(pnl: float) -> str:
    if pnl >= 0.5:
        return "🚀"
    if pnl >= 0.2:
        return "🟢"
    if pnl >= 0:
        return "🟡"
    if pnl >= -0.15:
        return "🟠"
    return "🔴"


def _result_label(pnl: float, reason: str) -> str:
    if reason == "take_profit":
        return "✅ TAKE PROFIT HIT"
    if reason == "stop_loss":
        return "❌ STOP LOSS HIT"
    if reason == "timeout":
        return "⏱ AUTO-CLOSED (8hrs)"
    return "CLOSED"


# ── Close a signal ────────────────────────────────────────────────────────────

async def close_signal(token_address: str, reason: str = "timeout") -> Optional[dict]:
    """
    Close an open signal. Fetch live price, calculate PnL, move to closed list.
    reason: 'take_profit' | 'stop_loss' | 'timeout' | 'manual'
    Returns the closed record.
    """
    data = _load()
    record = data["open"].get(token_address)
    if not record:
        return None

    exit_price = await get_live_price(token_address)
    if exit_price is None:
        exit_price = record["entry_price"]   # fallback — no change

    pnl        = _calc_pnl(record["entry_price"], exit_price)
    entry_dt   = datetime.fromisoformat(record["entry_time"])
    now        = datetime.now(timezone.utc)
    hold_hours = round((now - entry_dt).total_seconds() / 3600, 1)

    closed_record = {
        **record,
        "exit_price":  exit_price,
        "exit_time":   now.isoformat(),
        "pnl_pct":     round(pnl * 100, 2),
        "hold_hours":  hold_hours,
        "close_reason": reason,
        "win":         pnl > 0,
        "status":      "closed",
    }

    del data["open"][token_address]
    data["closed"].append(closed_record)
    _save(data)
    logger.info(f"Signal closed: {record['token']} | PnL: {pnl*100:.1f}% | Reason: {reason}")
    return closed_record


# ── Live refresh (called by /pnl command) ─────────────────────────────────────

async def refresh_all_open() -> list[dict]:
    """
    Fetch live prices for all open signals.
    Auto-closes any that hit TP / SL / 8hr timeout.
    Returns list of snapshot dicts for display.
    """
    data   = _load()
    now    = datetime.now(timezone.utc)
    snapshots = []

    for address, record in list(data["open"].items()):
        live_price = await get_live_price(address)
        if live_price is None:
            live_price = record["entry_price"]

        pnl        = _calc_pnl(record["entry_price"], live_price)
        entry_dt   = datetime.fromisoformat(record["entry_time"])
        hold_hours = (now - entry_dt).total_seconds() / 3600

        # Determine if we should auto-close
        close_reason = None
        if pnl >= TAKE_PROFIT:
            close_reason = "take_profit"
        elif pnl <= -STOP_LOSS:
            close_reason = "stop_loss"
        elif hold_hours >= AUTO_CLOSE_HOURS:
            close_reason = "timeout"

        if close_reason:
            closed = await close_signal(address, reason=close_reason)
            if closed:
                snapshots.append({**closed, "just_closed": True})
        else:
            snapshots.append({
                **record,
                "live_price":  live_price,
                "pnl_pct":     round(pnl * 100, 2),
                "hold_hours":  round(hold_hours, 1),
                "just_closed": False,
            })

    return snapshots


# ── Mid-update check (called by scheduler every hour) ─────────────────────────

async def check_mid_updates() -> list[dict]:
    """
    Called hourly by the scheduler.
    Returns signals that just crossed the 4hr mid-update mark (not yet alerted).
    Also closes any that hit TP/SL/timeout.
    """
    data    = _load()
    now     = datetime.now(timezone.utc)
    updates = []

    for address, record in list(data["open"].items()):
        live_price = await get_live_price(address)
        if live_price is None:
            live_price = record["entry_price"]

        pnl        = _calc_pnl(record["entry_price"], live_price)
        entry_dt   = datetime.fromisoformat(record["entry_time"])
        hold_hours = (now - entry_dt).total_seconds() / 3600

        close_reason = None
        if pnl >= TAKE_PROFIT:
            close_reason = "take_profit"
        elif pnl <= -STOP_LOSS:
            close_reason = "stop_loss"
        elif hold_hours >= AUTO_CLOSE_HOURS:
            close_reason = "timeout"

        if close_reason:
            closed = await close_signal(address, reason=close_reason)
            if closed:
                updates.append({**closed, "type": "closed"})
        elif hold_hours >= MID_UPDATE_HOURS and not record.get("mid_alerted"):
            # Mark mid-alert sent
            data["open"][address]["mid_alerted"] = True
            _save(data)
            updates.append({
                **record,
                "live_price":  live_price,
                "pnl_pct":     round(pnl * 100, 2),
                "hold_hours":  round(hold_hours, 1),
                "type":        "mid_update",
            })

    return updates


# ── Scorecard (bot win rate stats) ────────────────────────────────────────────

def get_scorecard() -> dict:
    """
    Returns overall bot performance stats from all closed signals.
    """
    data   = _load()
    closed = data.get("closed", [])

    if not closed:
        return {
            "total":      0,
            "wins":       0,
            "losses":     0,
            "win_rate":   0.0,
            "avg_profit": 0.0,
            "avg_loss":   0.0,
            "best_trade": None,
            "worst_trade": None,
            "open_count": len(data.get("open", {})),
        }

    wins   = [t for t in closed if t.get("win")]
    losses = [t for t in closed if not t.get("win")]

    avg_profit = (sum(t["pnl_pct"] for t in wins)   / len(wins))   if wins   else 0.0
    avg_loss   = (sum(t["pnl_pct"] for t in losses) / len(losses)) if losses else 0.0

    best  = max(closed, key=lambda t: t["pnl_pct"])
    worst = min(closed, key=lambda t: t["pnl_pct"])

    return {
        "total":       len(closed),
        "wins":        len(wins),
        "losses":      len(losses),
        "win_rate":    round(len(wins) / len(closed) * 100, 1),
        "avg_profit":  round(avg_profit, 2),
        "avg_loss":    round(avg_loss, 2),
        "best_trade":  best,
        "worst_trade": worst,
        "open_count":  len(data.get("open", {})),
    }


# ── Gemini commentary on scorecard ───────────────────────────────────────────

async def gemini_scorecard_comment(scorecard: dict) -> str:
    """Ask Gemini to give a 1-line commentary on bot performance."""
    try:
        prompt = (
            f"Bot trading stats: {scorecard['wins']}W / {scorecard['losses']}L, "
            f"win rate {scorecard['win_rate']}%, avg profit {scorecard['avg_profit']}%, "
            f"avg loss {scorecard['avg_loss']}%. "
            "Give ONE sharp sentence verdict on whether this bot is performing well. "
            "Be direct, no fluff."
        )
        response = gemini.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini scorecard comment error: {e}")
        return "AI commentary unavailable."
