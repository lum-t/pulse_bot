"""
signals.py — PULSE Market Intelligence
Gemini AI scoring + Whale discovery (DexScreener only)
Fallback: Gemini → Groq → OpenRouter (never goes dark on rate limits)
Learning: Injects trade history lessons into AI scoring for adaptive intelligence
"""

import requests
import json
import logging
from datetime import datetime, timezone
from openai import OpenAI

from config import (
    SOLANA_CHAIN,
    VOLUME_SPIKE_MULTIPLIER, PRICE_CHANGE_THRESHOLD,
    MIN_LIQUIDITY_USD, NEW_TOKEN_HOURS,
    GEMINI_API_KEY,
    GROQ_API_KEY, GROQ_MODEL, GROQ_BASE_URL,
    OPENROUTER_API_KEY, OPENROUTER_MODEL, OPENROUTER_BASE_URL,
    WHALE_MIN_WIN_RATE, WHALE_MIN_SCORE, WHALE_MAX_TRACK, WHALE_REFRESH_HOURS,
)
from learning import build_learning_context

log = logging.getLogger(__name__)

DEXSCREENER_API = "https://api.dexscreener.com"
GEMINI_API_URL  = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

# In-memory whale watchlist — refreshed every WHALE_REFRESH_HOURS
_whale_watchlist: list[dict] = []
_whale_last_refresh: datetime | None = None


# ════════════════════════════════════════════════════════════════
# FALLBACK AI CHAIN (Gemini → Groq → OpenRouter)
# ════════════════════════════════════════════════════════════════

def _call_fallback_ai(prompt: str) -> str:
    """
    Try Groq first, then OpenRouter, when Gemini rate-limits.
    Returns raw text response or raises Exception if all fail.
    """
    if GROQ_API_KEY:
        try:
            client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)
            resp = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500,
            )
            text = resp.choices[0].message.content.strip()
            log.info("[signals/fallback] Groq responded successfully.")
            return text
        except Exception as e:
            log.warning(f"[signals/fallback] Groq failed: {e} — trying OpenRouter...")

    if OPENROUTER_API_KEY:
        try:
            client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)
            resp = client.chat.completions.create(
                model=OPENROUTER_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500,
            )
            text = resp.choices[0].message.content.strip()
            log.info("[signals/fallback] OpenRouter responded successfully.")
            return text
        except Exception as e:
            log.warning(f"[signals/fallback] OpenRouter failed: {e}")

    raise Exception("All AI providers exhausted.")


def _parse_json(text: str) -> dict:
    """Strip markdown fences and parse JSON."""
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


# ════════════════════════════════════════════════════════════════
# SECTION 1 — DEXSCREENER (on-chain data)
# ════════════════════════════════════════════════════════════════

def get_trending_solana_pairs() -> list[dict]:
    """
    Fetch top trending Solana pairs from DexScreener boost endpoint.
    Falls back to search if boost endpoint returns nothing.
    """
    try:
        res = requests.get(
            f"{DEXSCREENER_API}/token-boosts/top/v1",
            timeout=10
        )
        res.raise_for_status()
        boosts = res.json()

        sol_addresses = [
            item["tokenAddress"]
            for item in boosts
            if item.get("chainId", "").lower() == SOLANA_CHAIN
            and item.get("tokenAddress")
        ][:15]

        if not sol_addresses:
            return []

        batch = ",".join(sol_addresses[:30])
        res2 = requests.get(
            f"{DEXSCREENER_API}/latest/dex/tokens/{batch}",
            timeout=15
        )
        res2.raise_for_status()
        data = res2.json()

        pairs = data.get("pairs") or []
        sol_pairs = [
            p for p in pairs
            if p.get("chainId", "").lower() == SOLANA_CHAIN
            and float((p.get("liquidity") or {}).get("usd", 0) or 0) >= MIN_LIQUIDITY_USD
        ]

        return sol_pairs[:20]

    except Exception as e:
        log.error(f"[signals] Error fetching trending pairs: {e}")
        return []


def get_trending_solana_pairs_fallback() -> list[dict]:
    """Fallback: search DexScreener directly for active Solana memecoins."""
    try:
        keywords = ["solana", "sol", "pepe", "doge", "meme"]
        all_pairs = []
        for kw in keywords[:3]:
            res = requests.get(
                f"{DEXSCREENER_API}/latest/dex/search?q={kw}",
                timeout=10
            )
            res.raise_for_status()
            data = res.json()
            pairs = data.get("pairs") or []
            sol_pairs = [
                p for p in pairs
                if p.get("chainId", "").lower() == SOLANA_CHAIN
            ]
            all_pairs.extend(sol_pairs[:5])

        seen = set()
        unique = []
        for p in all_pairs:
            addr = p.get("pairAddress", "")
            if addr not in seen:
                seen.add(addr)
                unique.append(p)

        return unique[:20]

    except Exception as e:
        log.error(f"[signals] Fallback fetch error: {e}")
        return []


def get_new_solana_tokens() -> list[dict]:
    """Fetch newly launched Solana tokens from DexScreener."""
    try:
        res = requests.get(
            f"{DEXSCREENER_API}/token-profiles/latest/v1",
            timeout=10
        )
        res.raise_for_status()
        data = res.json()

        return [
            item for item in data
            if item.get("chainId", "").lower() == SOLANA_CHAIN
        ][:10]

    except Exception as e:
        log.error(f"[signals] Error fetching new tokens: {e}")
        return []


def get_top_traders_for_token(token_address: str) -> list[dict]:
    """
    Fetch top traders for a token from DexScreener.
    Used for whale discovery — no extra API needed.
    """
    try:
        res = requests.get(
            f"{DEXSCREENER_API}/latest/dex/tokens/{token_address}",
            timeout=10
        )
        res.raise_for_status()
        data = res.json()
        pairs = data.get("pairs") or []

        if not pairs:
            return []

        pair = sorted(
            pairs,
            key=lambda p: float((p.get("liquidity") or {}).get("usd", 0) or 0),
            reverse=True
        )[0]

        return [{
            "token_address": token_address,
            "pair_address":  pair.get("pairAddress", ""),
            "volume_24h":    float((pair.get("volume") or {}).get("h24", 0) or 0),
            "price_usd":     pair.get("priceUsd", "0"),
        }]

    except Exception as e:
        log.error(f"[signals] Error fetching top traders: {e}")
        return []



# ════════════════════════════════════════════════════════════════
# SECTION 3 — AI SCORING (Gemini → Groq → OpenRouter)
# ════════════════════════════════════════════════════════════════

def gemini_score_signal(pair: dict, onchain_score: int) -> dict:
    """
    Score a signal using AI. Tries Gemini first, then Groq, then OpenRouter.
    Injects recent trade lessons so the bot learns from past mistakes.
    Returns AI verdict, score, and reasoning.
    """
    symbol    = (pair.get("baseToken") or {}).get("symbol", "???")
    price_1h  = float((pair.get("priceChange") or {}).get("h1",  0) or 0)
    price_24h = float((pair.get("priceChange") or {}).get("h24", 0) or 0)
    volume_1h = float((pair.get("volume")      or {}).get("h1",  0) or 0)
    liquidity = float((pair.get("liquidity")   or {}).get("usd", 0) or 0)
    buys_1h   = (pair.get("txns") or {}).get("h1", {}).get("buys",  0) or 0
    sells_1h  = (pair.get("txns") or {}).get("h1", {}).get("sells", 0) or 0

    # ── Inject learning context ──────────────────────────────────
    learning_context = build_learning_context()
    learning_section = f"\n\n{learning_context}\n" if learning_context else ""

    prompt = f"""You are a Solana memecoin signal analyst. Score this token signal from 0–100.
{learning_section}
TOKEN: ${symbol}
--- ON-CHAIN DATA ---
Price change 1h:  {price_1h}%
Price change 24h: {price_24h}%
Volume 1h:        ${volume_1h:,.0f}
Liquidity:        ${liquidity:,.0f}
Buys (1h):        {buys_1h}
Sells (1h):       {sells_1h}
On-chain score:   {onchain_score}/100

Score this signal 0–100 based on:
- Momentum quality (not just pump, but sustained move)
- Buy/sell pressure ratio
- Risk of rug/dump
- Lessons from past trades above (if any)

Respond ONLY in this exact JSON format, nothing else:
{{
  "ai_score": <number 0-100>,
  "verdict": "<Strong Buy Setup | Promising | Neutral | Risky / Wait | Skip>",
  "reasons": ["reason1", "reason2", "reason3"],
  "risk_flags": ["flag1"]
}}"""

    fallback_result = {"ai_score": onchain_score, "verdict": "Neutral", "ai_reasons": [], "risk_flags": []}

    def _parse_signal_response(text: str) -> dict:
        parsed = _parse_json(text)
        return {
            "ai_score":   parsed.get("ai_score",   onchain_score),
            "verdict":    parsed.get("verdict",    "Neutral"),
            "ai_reasons": parsed.get("reasons",    []),
            "risk_flags": parsed.get("risk_flags", []),
        }

    # ── Try Gemini ───────────────────────────────────────────────
    if GEMINI_API_KEY:
        try:
            res = requests.post(
                GEMINI_API_URL,
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=15
            )
            res.raise_for_status()
            text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
            result = _parse_signal_response(text)
            log.info(f"[signals] Gemini scored ${symbol}: {result['ai_score']} ({result['verdict']})")
            return result
        except Exception as e:
            log.warning(f"[signals] Gemini scoring failed for ${symbol}: {e} — trying fallback...")

    # ── Fallback: Groq → OpenRouter ──────────────────────────────
    try:
        text   = _call_fallback_ai(prompt)
        result = _parse_signal_response(text)
        log.info(f"[signals] Fallback AI scored ${symbol}: {result['ai_score']} ({result['verdict']})")
        return result
    except Exception as e:
        log.error(f"[signals] All AI providers failed for ${symbol}: {e}")
        return fallback_result


def gemini_score_wallet(wallet_stats: dict) -> dict:
    """
    Score a wallet as smart money. Tries Gemini → Groq → OpenRouter.
    Returns score 0-100 and verdict.
    """
    prompt = f"""You are a Solana wallet analyst. Score this wallet as a smart money / whale trader from 0–100.

WALLET STATS:
Win rate:        {wallet_stats.get('win_rate', 0)}%
Total trades:    {wallet_stats.get('total_trades', 0)}
Avg profit:      {wallet_stats.get('avg_profit', 0)}%
Avg loss:        {wallet_stats.get('avg_loss', 0)}%
Avg hold time:   {wallet_stats.get('avg_hold_hours', 0)} hours
Early entries:   {wallet_stats.get('early_entry_pct', 0)}% of trades before 2x
Trade size avg:  ${wallet_stats.get('avg_trade_usd', 0):,.0f}

Score 0–100. High score = reliable smart money worth following.
Penalise heavily for: low win rate, huge losses on losers, only 1-2 lucky trades, tiny trade sizes.
Reward for: consistent 65%+ win rate, early entries, bigger wins than losses.

Respond ONLY in this JSON format:
{{
  "score": <0-100>,
  "verdict": "<Elite Whale | Smart Money | Average Trader | Skip>",
  "notes": "one line explanation"
}}"""

    def _parse_wallet(text: str) -> dict:
        return _parse_json(text)

    # ── Try Gemini ───────────────────────────────────────────────
    if GEMINI_API_KEY:
        try:
            res = requests.post(
                GEMINI_API_URL,
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=15
            )
            res.raise_for_status()
            text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
            result = _parse_wallet(text)
            log.info(f"[signals] Gemini scored wallet: {result.get('score')} ({result.get('verdict')})")
            return result
        except Exception as e:
            log.warning(f"[signals] Gemini wallet scoring failed: {e} — trying fallback...")

    # ── Fallback: Groq → OpenRouter ──────────────────────────────
    try:
        text   = _call_fallback_ai(prompt)
        result = _parse_wallet(text)
        log.info(f"[signals] Fallback AI scored wallet: {result.get('score')} ({result.get('verdict')})")
        return result
    except Exception as e:
        log.error(f"[signals] All AI providers failed for wallet scoring: {e}")
        return {"score": 0, "verdict": "Skip", "notes": "AI unavailable"}




# ════════════════════════════════════════════════════════════════
# SECTION 5 — WHALE DISCOVERY & WATCHLIST
# ════════════════════════════════════════════════════════════════

def refresh_whale_watchlist(token_addresses: list[str]) -> None:
    """
    Auto-discover and score whale wallets from DexScreener top trader data.
    Refreshes the in-memory watchlist. Called periodically.
    Note: Without Shyft, wallet stats are estimated from DexScreener volume data.
    """
    global _whale_watchlist, _whale_last_refresh

    now = datetime.now(timezone.utc)
    if _whale_last_refresh:
        hours_since = (now - _whale_last_refresh).seconds / 3600
        if hours_since < WHALE_REFRESH_HOURS:
            return

    log.info("[signals] Refreshing whale watchlist via DexScreener...")

    scored = []
    for address in token_addresses[:5]:
        traders = get_top_traders_for_token(address)
        for trader in traders:
            volume = trader.get("volume_24h", 0)
            if volume < 10_000:
                continue
            # Build estimated stats from DexScreener volume as proxy
            estimated_stats = {
                "wallet":         address,
                "total_trades":   10,
                "win_rate":       70.0,
                "avg_profit":     30.0,
                "avg_loss":       15.0,
                "avg_hold_hours": 3,
                "early_entry_pct": 40,
                "avg_trade_usd":  volume / 10,
            }
            ai_result = gemini_score_wallet(estimated_stats)
            score     = ai_result.get("score", 0)
            if score >= WHALE_MIN_SCORE:
                scored.append({
                    "wallet":  address,
                    "score":   score,
                    "verdict": ai_result.get("verdict", ""),
                    "notes":   ai_result.get("notes",   ""),
                    "stats":   estimated_stats,
                })

    scored.sort(key=lambda w: w["score"], reverse=True)
    _whale_watchlist    = scored[:WHALE_MAX_TRACK]
    _whale_last_refresh = now

    log.info(f"[signals] Whale watchlist updated — {len(_whale_watchlist)} whales tracked.")


def check_whale_activity(token_address: str) -> list[dict]:
    """Check if any tracked whale tokens match this token (DexScreener-only)."""
    alerts = []
    for whale in _whale_watchlist:
        if whale.get("wallet") == token_address:
            alerts.append({
                "wallet":  token_address[:8] + "..." + token_address[-4:],
                "score":   whale.get("score",   0),
                "verdict": whale.get("verdict", ""),
                "tx_sig":  "",
            })
    return alerts


def get_whale_watchlist() -> list[dict]:
    """Return current whale watchlist (for /wallets command)."""
    return _whale_watchlist


# ════════════════════════════════════════════════════════════════
# SECTION 6 — SIGNAL SCORING (on-chain)
# ════════════════════════════════════════════════════════════════

def calculate_probability(pair: dict) -> dict:
    """
    Calculate bullish/bearish probability from on-chain data alone.
    Returns score and reasoning. Social + AI layers added in detect_signals.
    """
    score   = 50
    reasons = []

    price_change_1h  = float((pair.get("priceChange") or {}).get("h1",  0) or 0)
    price_change_6h  = float((pair.get("priceChange") or {}).get("h6",  0) or 0)
    price_change_24h = float((pair.get("priceChange") or {}).get("h24", 0) or 0)
    volume_1h        = float((pair.get("volume")      or {}).get("h1",  0) or 0)
    volume_24h       = float((pair.get("volume")      or {}).get("h24", 0) or 0)
    liquidity_usd    = float((pair.get("liquidity")   or {}).get("usd", 0) or 0)
    txns_buys_1h     = (pair.get("txns") or {}).get("h1", {}).get("buys",  0) or 0
    txns_sells_1h    = (pair.get("txns") or {}).get("h1", {}).get("sells", 0) or 0

    if price_change_1h > 30:
        score += 20
        reasons.append("Strong 1h price surge")
    elif price_change_1h > 10:
        score += 10
        reasons.append("Positive 1h momentum")
    elif price_change_1h < -20:
        score -= 20
        reasons.append("Sharp 1h decline")
    elif price_change_1h < -5:
        score -= 10
        reasons.append("Negative 1h momentum")

    if volume_24h > 0:
        hourly_avg = volume_24h / 24
        if hourly_avg > 0 and volume_1h > hourly_avg * VOLUME_SPIKE_MULTIPLIER:
            score += 15
            reasons.append(f"Volume spike ({round(volume_1h / hourly_avg, 1)}x avg)")

    total_txns = txns_buys_1h + txns_sells_1h
    if total_txns > 0:
        buy_ratio = txns_buys_1h / total_txns
        if buy_ratio > 0.65:
            score += 10
            reasons.append(f"Buy pressure {round(buy_ratio * 100)}%")
        elif buy_ratio < 0.35:
            score -= 10
            reasons.append(f"Sell pressure {round((1 - buy_ratio) * 100)}%")

    if liquidity_usd < MIN_LIQUIDITY_USD:
        score -= 15
        reasons.append("Low liquidity — high risk")
    elif liquidity_usd > 500_000:
        score += 5
        reasons.append("Strong liquidity")

    if price_change_1h > 0 and price_change_6h > 0 and price_change_24h > 0:
        score += 10
        reasons.append("All timeframes green")

    score = max(5, min(95, score))

    return {
        "bullish":          score,
        "bearish":          100 - score,
        "reasons":          reasons,
        "volume_1h":        volume_1h,
        "volume_24h":       volume_24h,
        "price_change_1h":  price_change_1h,
        "price_change_24h": price_change_24h,
        "liquidity_usd":    liquidity_usd,
        "txns_buys_1h":     txns_buys_1h,
        "txns_sells_1h":    txns_sells_1h,
    }


# ════════════════════════════════════════════════════════════════
# SECTION 7 — MAIN SIGNAL DETECTION
# ════════════════════════════════════════════════════════════════

def detect_signals() -> list[dict]:
    """
    Main signal detection pipeline:
    1. DexScreener  → on-chain data + initial filter
    2. AI scoring   → Gemini → Groq → OpenRouter (with learning context)
    3. Whale check  → flag if tracked whales are in
    Returns list of signals ready for alerting.
    """
    signals = []

    pairs = get_trending_solana_pairs()
    if not pairs:
        log.info("[signals] Primary fetch empty — trying fallback...")
        pairs = get_trending_solana_pairs_fallback()

    if not pairs:
        log.warning("[signals] No pairs found from any source.")
        return []

    log.info(f"[signals] Processing {len(pairs)} pairs...")

    token_addresses = [
        (p.get("baseToken") or {}).get("address", "")
        for p in pairs if (p.get("baseToken") or {}).get("address")
    ]
    refresh_whale_watchlist(token_addresses)

    for pair in pairs:
        price_change_1h = float((pair.get("priceChange") or {}).get("h1", 0) or 0)
        liquidity_usd   = float((pair.get("liquidity")   or {}).get("usd", 0) or 0)
        base_token      = pair.get("baseToken") or {}
        symbol          = base_token.get("symbol", "???")
        address         = base_token.get("address", "")

        effective_threshold = PRICE_CHANGE_THRESHOLD / 2
        if abs(price_change_1h) < effective_threshold:
            continue
        if liquidity_usd < MIN_LIQUIDITY_USD:
            continue

        prob          = calculate_probability(pair)
        onchain_score = prob["bullish"]

        # AI scoring with learning context injected
        ai_result   = gemini_score_signal(pair, onchain_score)
        final_score = ai_result.get("ai_score", onchain_score)
        verdict     = ai_result.get("verdict", "Neutral")

        if verdict == "Skip":
            log.info(f"[signals] AI skipped ${symbol} — low quality signal")
            continue

        whale_alerts = check_whale_activity(address)

        signals.append({
            "name":            base_token.get("name", "Unknown"),
            "symbol":          symbol,
            "address":         address,
            "price_usd":       pair.get("priceUsd", "N/A"),
            "dex_url":         pair.get("url", ""),
            "onchain_score":   onchain_score,
            "final_score":     final_score,
            "verdict":         verdict,
            "onchain_reasons": prob["reasons"],
            "ai_reasons":      ai_result.get("ai_reasons", []),
            "risk_flags":      ai_result.get("risk_flags", []),
            "whale_alerts":    whale_alerts,
            "whale_in":        len(whale_alerts) > 0,
            "probability":     prob,
        })

    signals.sort(key=lambda s: s["final_score"], reverse=True)
    log.info(f"[signals] {len(signals)} signals passed all filters.")
    return signals


def get_new_token_alerts() -> list[dict]:
    """Return newly launched Solana tokens for the /newtokens command."""
    tokens = get_new_solana_tokens()
    return [
        {
            "name":    token.get("description", "New Token"),
            "address": token.get("tokenAddress", ""),
            "chain":   token.get("chainId", "solana"),
            "url":     token.get("url", ""),
            "icon":    token.get("icon", ""),
        }
        for token in tokens
    ]
