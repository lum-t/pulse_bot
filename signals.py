"""
signals.py — PULSE Market Intelligence
Solana memecoin signal detection via DexScreener API
Fixed: correct endpoints, lower threshold, better fallback
"""

import requests
from datetime import datetime, timezone
from config import (
    SOLANA_CHAIN,
    VOLUME_SPIKE_MULTIPLIER, PRICE_CHANGE_THRESHOLD,
    MIN_LIQUIDITY_USD, NEW_TOKEN_HOURS
)

DEXSCREENER_API = "https://api.dexscreener.com"


# ─── Fetch trending Solana pairs ─────────────────────────────

def get_trending_solana_pairs() -> list[dict]:
    """
    Fetch top trending Solana pairs directly from DexScreener.
    Uses /token-boosts to get hot token addresses, then fetches
    their actual pair data via /tokens endpoint.
    """
    try:
        # Step 1: Get boosted/trending token addresses
        res = requests.get(
            f"{DEXSCREENER_API}/token-boosts/top/v1",
            timeout=10
        )
        res.raise_for_status()
        boosts = res.json()

        # Filter Solana only and collect addresses
        sol_addresses = [
            item["tokenAddress"]
            for item in boosts
            if item.get("chainId", "").lower() == SOLANA_CHAIN
            and item.get("tokenAddress")
        ][:15]  # top 15

        if not sol_addresses:
            return []

        # Step 2: Batch fetch pair data for those addresses
        # DexScreener allows comma-separated addresses
        batch = ",".join(sol_addresses[:30])
        res2 = requests.get(
            f"{DEXSCREENER_API}/latest/dex/tokens/{batch}",
            timeout=15
        )
        res2.raise_for_status()
        data = res2.json()

        pairs = data.get("pairs") or []
        # Keep only Solana pairs with some liquidity
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
    """
    Fallback: search DexScreener for active Solana memecoins directly.
    Used when boost endpoint fails.
    """
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

        # Deduplicate by pair address
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


# ─── Signal Analysis ─────────────────────────────────────────

def calculate_probability(pair: dict) -> dict:
    """
    Calculate bullish/bearish probability from on-chain data.
    Returns a dict with scores and reasoning.
    """
    score = 50  # neutral start
    reasons = []

    price_change_1h  = float((pair.get("priceChange") or {}).get("h1",  0) or 0)
    price_change_6h  = float((pair.get("priceChange") or {}).get("h6",  0) or 0)
    price_change_24h = float((pair.get("priceChange") or {}).get("h24", 0) or 0)
    volume_1h        = float((pair.get("volume")      or {}).get("h1",  0) or 0)
    volume_24h       = float((pair.get("volume")      or {}).get("h24", 0) or 0)
    liquidity_usd    = float((pair.get("liquidity")   or {}).get("usd", 0) or 0)
    txns_buys_1h     = (pair.get("txns") or {}).get("h1", {}).get("buys",  0) or 0
    txns_sells_1h    = (pair.get("txns") or {}).get("h1", {}).get("sells", 0) or 0

    # Price momentum
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

    # Volume spike vs daily average
    if volume_24h > 0:
        hourly_avg = volume_24h / 24
        if hourly_avg > 0 and volume_1h > hourly_avg * VOLUME_SPIKE_MULTIPLIER:
            score += 15
            reasons.append(f"Volume spike ({round(volume_1h / hourly_avg, 1)}x avg)")

    # Buy/sell pressure
    total_txns = txns_buys_1h + txns_sells_1h
    if total_txns > 0:
        buy_ratio = txns_buys_1h / total_txns
        if buy_ratio > 0.65:
            score += 10
            reasons.append(f"Buy pressure {round(buy_ratio * 100)}%")
        elif buy_ratio < 0.35:
            score -= 10
            reasons.append(f"Sell pressure {round((1 - buy_ratio) * 100)}%")

    # Liquidity check
    if liquidity_usd < MIN_LIQUIDITY_USD:
        score -= 15
        reasons.append("Low liquidity — high risk")
    elif liquidity_usd > 500_000:
        score += 5
        reasons.append("Strong liquidity")

    # Multi-timeframe confirmation
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


def detect_signals() -> list[dict]:
    """
    Main signal detection function.
    Returns list of significant signals ready for alerting.
    Uses primary endpoint with fallback to search.
    """
    signals = []

    # Try primary endpoint first
    pairs = get_trending_solana_pairs()

    # Fallback if primary returned nothing
    if not pairs:
        print("[signals] Primary fetch empty — trying fallback search...")
        pairs = get_trending_solana_pairs_fallback()

    if not pairs:
        print("[signals] No pairs found from any source.")
        return []

    print(f"[signals] Processing {len(pairs)} pairs...")

    for pair in pairs:
        price_change_1h = float((pair.get("priceChange") or {}).get("h1", 0) or 0)
        liquidity_usd   = float((pair.get("liquidity")   or {}).get("usd", 0) or 0)

        # Filter: only surface meaningful moves
        # Using half of config threshold so we don't miss everything
        effective_threshold = PRICE_CHANGE_THRESHOLD / 2
        if abs(price_change_1h) < effective_threshold:
            continue
        if liquidity_usd < MIN_LIQUIDITY_USD:
            continue

        prob       = calculate_probability(pair)
        base_token = pair.get("baseToken") or {}

        signals.append({
            "name":      base_token.get("name",    "Unknown"),
            "symbol":    base_token.get("symbol",  "???"),
            "address":   base_token.get("address", ""),
            "price_usd": pair.get("priceUsd", "N/A"),
            "dex_url":   pair.get("url", ""),
            "probability": prob,
        })

    print(f"[signals] {len(signals)} signals passed filters.")
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
