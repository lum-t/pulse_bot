"""
signals.py — PULSE Market Intelligence
Upgraded: LunarCrush sentiment + Gemini AI scoring + Whale discovery + Shyft tracking
"""

import requests
import json
from datetime import datetime, timezone
from config import (
    SOLANA_CHAIN,
    VOLUME_SPIKE_MULTIPLIER, PRICE_CHANGE_THRESHOLD,
    MIN_LIQUIDITY_USD, NEW_TOKEN_HOURS,
    LUNARCRUSH_API_KEY, LUNARCRUSH_BASE_URL,
    LUNARCRUSH_MIN_GALAXY_SCORE, LUNARCRUSH_MIN_SOCIAL_VOLUME,
    SHYFT_API_KEY, SHYFT_BASE_URL,
    GEMINI_API_KEY,
    WHALE_MIN_WIN_RATE, WHALE_MIN_SCORE, WHALE_MAX_TRACK, WHALE_REFRESH_HOURS,
)

DEXSCREENER_API = "https://api.dexscreener.com"
GEMINI_API_URL  = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

# In-memory whale watchlist — refreshed every WHALE_REFRESH_HOURS
_whale_watchlist: list[dict] = []
_whale_last_refresh: datetime | None = None


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
        print(f"[signals] Error fetching trending pairs: {e}")
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
        print(f"[signals] Fallback fetch error: {e}")
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
        print(f"[signals] Error fetching new tokens: {e}")
        return []


def get_top_traders_for_token(token_address: str) -> list[dict]:
    """
    Fetch top traders for a token from DexScreener.
    Used for whale discovery — no extra API needed.
    Returns list of trader wallet addresses with basic stats.
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

        # Pull the most liquid pair's data
        pair = sorted(
            pairs,
            key=lambda p: float((p.get("liquidity") or {}).get("usd", 0) or 0),
            reverse=True
        )[0]

        # DexScreener doesn't expose wallet-level data directly
        # We extract what we can from txn metadata to seed Shyft lookups
        return [{
            "token_address": token_address,
            "pair_address":  pair.get("pairAddress", ""),
            "volume_24h":    float((pair.get("volume") or {}).get("h24", 0) or 0),
            "price_usd":     pair.get("priceUsd", "0"),
        }]

    except Exception as e:
        print(f"[signals] Error fetching top traders: {e}")
        return []


# ════════════════════════════════════════════════════════════════
# SECTION 2 — LUNARCRUSH (social sentiment)
# ════════════════════════════════════════════════════════════════

def get_lunarcrush_sentiment(symbol: str) -> dict:
    """
    Fetch social sentiment for a token from LunarCrush.
    Returns galaxy score, social volume, and sentiment data.
    """
    if not LUNARCRUSH_API_KEY:
        return {}

    try:
        res = requests.get(
            f"{LUNARCRUSH_BASE_URL}/coins/{symbol.lower()}/v1",
            headers={"Authorization": f"Bearer {LUNARCRUSH_API_KEY}"},
            timeout=10
        )

        if res.status_code == 404:
            return {}  # Token not found on LunarCrush — not a disqualifier

        res.raise_for_status()
        data = res.json().get("data", {})

        return {
            "galaxy_score":   data.get("galaxy_score", 0),
            "social_volume":  data.get("social_volume", 0),
            "sentiment":      data.get("sentiment", 0),       # 0–100, >50 = bullish
            "social_score":   data.get("social_score", 0),
            "alt_rank":       data.get("alt_rank", 9999),     # lower = better
        }

    except Exception as e:
        print(f"[signals] LunarCrush error for {symbol}: {e}")
        return {}


def social_sentiment_score(sentiment_data: dict) -> tuple[int, list[str]]:
    """
    Convert LunarCrush data into a social score contribution and reasons.
    Returns (score_delta, reasons).
    """
    if not sentiment_data:
        return 0, ["No social data — on-chain only"]

    delta   = 0
    reasons = []

    galaxy = sentiment_data.get("galaxy_score", 0)
    volume = sentiment_data.get("social_volume", 0)
    sent   = sentiment_data.get("sentiment", 50)
    rank   = sentiment_data.get("alt_rank", 9999)

    if galaxy >= LUNARCRUSH_MIN_GALAXY_SCORE:
        delta += 15
        reasons.append(f"Galaxy score {galaxy}/100 🔥")
    elif galaxy > 0:
        delta += 5
        reasons.append(f"Galaxy score {galaxy}/100")

    if volume >= LUNARCRUSH_MIN_SOCIAL_VOLUME:
        delta += 10
        reasons.append(f"Social volume {volume:,} posts")

    if sent > 65:
        delta += 10
        reasons.append(f"Bullish sentiment {sent}%")
    elif sent < 35:
        delta -= 10
        reasons.append(f"Bearish sentiment {sent}%")

    if rank < 100:
        delta += 5
        reasons.append(f"AltRank #{rank} — top social mover")

    return delta, reasons


# ════════════════════════════════════════════════════════════════
# SECTION 3 — GEMINI AI (signal scoring)
# ════════════════════════════════════════════════════════════════

def gemini_score_signal(pair: dict, onchain_score: int, sentiment_data: dict) -> dict:
    """
    Send signal data to Gemini for AI analysis and scoring.
    Returns AI verdict, score, and reasoning.
    """
    if not GEMINI_API_KEY:
        return {"ai_score": onchain_score, "verdict": "No AI key", "ai_reasons": []}

    symbol    = (pair.get("baseToken") or {}).get("symbol", "???")
    price_1h  = float((pair.get("priceChange") or {}).get("h1",  0) or 0)
    price_24h = float((pair.get("priceChange") or {}).get("h24", 0) or 0)
    volume_1h = float((pair.get("volume")      or {}).get("h1",  0) or 0)
    liquidity = float((pair.get("liquidity")   or {}).get("usd", 0) or 0)
    buys_1h   = (pair.get("txns") or {}).get("h1", {}).get("buys",  0) or 0
    sells_1h  = (pair.get("txns") or {}).get("h1", {}).get("sells", 0) or 0

    galaxy  = sentiment_data.get("galaxy_score",  0)
    soc_vol = sentiment_data.get("social_volume", 0)
    sent    = sentiment_data.get("sentiment",     50)

    prompt = f"""You are a Solana memecoin signal analyst. Score this token signal from 0–100.

TOKEN: ${symbol}
--- ON-CHAIN DATA ---
Price change 1h:  {price_1h}%
Price change 24h: {price_24h}%
Volume 1h:        ${volume_1h:,.0f}
Liquidity:        ${liquidity:,.0f}
Buys (1h):        {buys_1h}
Sells (1h):       {sells_1h}
On-chain score:   {onchain_score}/100

--- SOCIAL DATA (LunarCrush) ---
Galaxy score:     {galaxy}/100
Social volume:    {soc_vol} posts
Sentiment:        {sent}/100

Score this signal 0–100 based on:
- Momentum quality (not just pump, but sustained move)
- Buy/sell pressure ratio
- Social vs on-chain alignment (both high = stronger)
- Risk of rug/dump

Respond ONLY in this exact JSON format, nothing else:
{{
  "ai_score": <number 0-100>,
  "verdict": "<Strong Buy Setup | Promising | Neutral | Risky / Wait | Skip>",
  "reasons": ["reason1", "reason2", "reason3"],
  "risk_flags": ["flag1"] 
}}"""

    try:
        res = requests.post(
            GEMINI_API_URL,
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=15
        )
        res.raise_for_status()
        raw = res.json()

        text = raw["candidates"][0]["content"]["parts"][0]["text"]
        # Strip markdown code fences if present
        text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(text)

        return {
            "ai_score":   parsed.get("ai_score",   onchain_score),
            "verdict":    parsed.get("verdict",    "Neutral"),
            "ai_reasons": parsed.get("reasons",    []),
            "risk_flags": parsed.get("risk_flags", []),
        }

    except Exception as e:
        print(f"[signals] Gemini scoring error for {symbol}: {e}")
        return {"ai_score": onchain_score, "verdict": "Neutral", "ai_reasons": [], "risk_flags": []}


def gemini_score_wallet(wallet_stats: dict) -> dict:
    """
    Ask Gemini to score a wallet as a potential smart money whale.
    Returns score 0-100 and verdict.
    """
    if not GEMINI_API_KEY:
        return {"score": 0, "verdict": "No AI key"}

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

    try:
        res = requests.post(
            GEMINI_API_URL,
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=15
        )
        res.raise_for_status()
        raw  = res.json()
        text = raw["candidates"][0]["content"]["parts"][0]["text"]
        text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(text)

    except Exception as e:
        print(f"[signals] Gemini wallet scoring error: {e}")
        return {"score": 0, "verdict": "Skip", "notes": str(e)}


# ════════════════════════════════════════════════════════════════
# SECTION 4 — SHYFT (wallet tracking)
# ════════════════════════════════════════════════════════════════

def get_wallet_transactions(wallet_address: str, limit: int = 20) -> list[dict]:
    """Fetch recent transactions for a wallet via Shyft."""
    if not SHYFT_API_KEY:
        return []

    try:
        res = requests.get(
            f"{SHYFT_BASE_URL}/transaction/history",
            headers={"x-api-key": SHYFT_API_KEY},
            params={
                "network":  "mainnet-beta",
                "account":  wallet_address,
                "tx_num":   limit,
                "enable_raw": False,
            },
            timeout=15
        )
        res.raise_for_status()
        data = res.json()
        return data.get("result", [])

    except Exception as e:
        print(f"[signals] Shyft tx fetch error for {wallet_address}: {e}")
        return []


def analyse_wallet_performance(wallet_address: str) -> dict:
    """
    Analyse a wallet's trading history via Shyft.
    Returns basic performance stats for Gemini to score.
    """
    txns = get_wallet_transactions(wallet_address, limit=50)

    if not txns:
        return {}

    # Simple heuristic analysis of swap transactions
    swap_txns = [t for t in txns if t.get("type") in ("SWAP", "TOKEN_SWAP")]

    total   = len(swap_txns)
    wins    = 0
    losses  = 0
    profits = []
    losses_ = []

    for tx in swap_txns:
        # Shyft returns token transfers — approximate PnL from fee + transfer data
        actions = tx.get("actions", [])
        for action in actions:
            info = action.get("info", {})
            amount_usd = float(info.get("amount_usd", 0) or 0)
            if amount_usd > 0:
                wins += 1
                profits.append(amount_usd)
            elif amount_usd < 0:
                losses += 1
                losses_.append(abs(amount_usd))

    win_rate    = (wins / total * 100) if total > 0 else 0
    avg_profit  = (sum(profits) / len(profits))  if profits  else 0
    avg_loss    = (sum(losses_) / len(losses_))  if losses_  else 0

    return {
        "wallet":          wallet_address,
        "total_trades":    total,
        "win_rate":        round(win_rate, 1),
        "avg_profit":      round(avg_profit, 2),
        "avg_loss":        round(avg_loss, 2),
        "avg_hold_hours":  0,   # Extended analysis — placeholder
        "early_entry_pct": 0,   # Extended analysis — placeholder
        "avg_trade_usd":   round((sum(profits) + sum(losses_)) / total, 2) if total > 0 else 0,
    }


def check_whale_activity(token_address: str) -> list[dict]:
    """
    Check if any tracked whales have recently bought this token via Shyft.
    Returns list of whale alerts.
    """
    if not _whale_watchlist or not SHYFT_API_KEY:
        return []

    alerts = []
    for whale in _whale_watchlist:
        wallet = whale.get("wallet", "")
        if not wallet:
            continue

        txns = get_wallet_transactions(wallet, limit=10)
        for tx in txns:
            actions = tx.get("actions", [])
            for action in actions:
                info = action.get("info", {})
                token_out = info.get("token_out_address", "")
                if token_out == token_address:
                    alerts.append({
                        "wallet":  wallet[:8] + "..." + wallet[-4:],
                        "score":   whale.get("score", 0),
                        "verdict": whale.get("verdict", ""),
                        "tx_sig":  tx.get("signatures", [""])[0],
                    })

    return alerts


# ════════════════════════════════════════════════════════════════
# SECTION 5 — WHALE DISCOVERY & WATCHLIST
# ════════════════════════════════════════════════════════════════

def refresh_whale_watchlist(token_addresses: list[str]) -> None:
    """
    Auto-discover and score whale wallets from top token traders.
    Refreshes the in-memory watchlist. Called periodically.
    """
    global _whale_watchlist, _whale_last_refresh

    now = datetime.now(timezone.utc)
    if _whale_last_refresh:
        hours_since = (now - _whale_last_refresh).seconds / 3600
        if hours_since < WHALE_REFRESH_HOURS:
            return  # Not time to refresh yet

    print("[signals] Refreshing whale watchlist...")

    candidate_wallets = set()

    # Step 1 — Pull top trader wallets from Shyft for each token
    for address in token_addresses[:5]:  # Limit API calls
        txns = get_wallet_transactions(address, limit=20)
        for tx in txns:
            signer = tx.get("fee_payer", "")
            if signer:
                candidate_wallets.add(signer)

    if not candidate_wallets:
        print("[signals] No candidate wallets found.")
        return

    # Step 2 — Analyse and score each candidate wallet
    scored = []
    for wallet in list(candidate_wallets)[:15]:  # Cap API calls
        stats = analyse_wallet_performance(wallet)
        if not stats:
            continue

        # Pre-filter by win rate before spending Gemini tokens
        if stats.get("win_rate", 0) < (WHALE_MIN_WIN_RATE * 100):
            continue

        ai_result = gemini_score_wallet(stats)
        score     = ai_result.get("score", 0)

        if score >= WHALE_MIN_SCORE:
            scored.append({
                "wallet":  wallet,
                "score":   score,
                "verdict": ai_result.get("verdict", ""),
                "notes":   ai_result.get("notes", ""),
                "stats":   stats,
            })

    # Step 3 — Keep top N wallets by score
    scored.sort(key=lambda w: w["score"], reverse=True)
    _whale_watchlist   = scored[:WHALE_MAX_TRACK]
    _whale_last_refresh = now

    print(f"[signals] Whale watchlist updated — {len(_whale_watchlist)} whales tracked.")


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
    2. LunarCrush   → social sentiment cross-check
    3. Gemini AI    → final score + verdict
    4. Whale check  → flag if tracked whales are in
    Returns list of signals ready for alerting.
    """
    signals = []

    # Step 1 — Get pairs
    pairs = get_trending_solana_pairs()
    if not pairs:
        print("[signals] Primary fetch empty — trying fallback...")
        pairs = get_trending_solana_pairs_fallback()

    if not pairs:
        print("[signals] No pairs found from any source.")
        return []

    print(f"[signals] Processing {len(pairs)} pairs...")

    # Refresh whale watchlist using current token addresses
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

        # Basic filter — same logic as before
        effective_threshold = PRICE_CHANGE_THRESHOLD / 2
        if abs(price_change_1h) < effective_threshold:
            continue
        if liquidity_usd < MIN_LIQUIDITY_USD:
            continue

        # Step 2 — On-chain score
        prob         = calculate_probability(pair)
        onchain_score = prob["bullish"]

        # Step 3 — LunarCrush social sentiment
        sentiment_data  = get_lunarcrush_sentiment(symbol)
        social_delta, social_reasons = social_sentiment_score(sentiment_data)

        combined_score = min(95, onchain_score + social_delta)

        # Step 4 — Gemini AI final scoring
        ai_result = gemini_score_signal(pair, combined_score, sentiment_data)
        final_score = ai_result.get("ai_score", combined_score)
        verdict     = ai_result.get("verdict", "Neutral")

        # Skip signals Gemini rated as Skip
        if verdict == "Skip":
            print(f"[signals] Gemini skipped ${symbol} — low quality signal")
            continue

        # Step 5 — Whale activity check
        whale_alerts = check_whale_activity(address)

        signals.append({
            "name":         base_token.get("name", "Unknown"),
            "symbol":       symbol,
            "address":      address,
            "price_usd":    pair.get("priceUsd", "N/A"),
            "dex_url":      pair.get("url", ""),
            # Scores
            "onchain_score":  onchain_score,
            "social_delta":   social_delta,
            "final_score":    final_score,
            "verdict":        verdict,
            # Reasons (combined for alert formatting)
            "onchain_reasons": prob["reasons"],
            "social_reasons":  social_reasons,
            "ai_reasons":      ai_result.get("ai_reasons", []),
            "risk_flags":      ai_result.get("risk_flags", []),
            # Sentiment data
            "sentiment":       sentiment_data,
            # Whale alerts
            "whale_alerts":    whale_alerts,
            "whale_in":        len(whale_alerts) > 0,
            # Raw probability (kept for backward compat with alerts.py)
            "probability":     prob,
        })

    # Sort by final AI score — best signals first
    signals.sort(key=lambda s: s["final_score"], reverse=True)

    print(f"[signals] {len(signals)} signals passed all filters.")
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
