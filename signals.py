"""
signals.py — PULSE Market Intelligence
Solana memecoin signal detection via DexScreener API
Completely separate from content engine
"""

import requests
import time
from datetime import datetime, timezone
from config import (
    DEXSCREENER_BASE_URL, SOLANA_CHAIN,
    VOLUME_SPIKE_MULTIPLIER, PRICE_CHANGE_THRESHOLD,
    MIN_LIQUIDITY_USD, NEW_TOKEN_HOURS
)


# ─── Fetch trending Solana pairs ─────────────────────────────

def get_trending_solana_pairs() -> list[dict]:
    """Fetch top trending Solana pairs from DexScreener."""
    try:
        url = f"{DEXSCREENER_BASE_URL}/tokens/{SOLANA_CHAIN}"
        # Use search for trending memecoins
        url = f"https://api.dexscreener.com/token-boosts/top/v1"
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()

        # Filter to Solana only
        solana_pairs = [
            item for item in data
            if item.get("chainId", "").lower() == SOLANA_CHAIN
        ]
        return solana_pairs[:20]  # top 20

    except Exception as e:
        print(f"[signals] Error fetching trending pairs: {e}")
        return []


def get_new_solana_tokens() -> list[dict]:
    """Fetch newly launched Solana tokens from DexScreener."""
    try:
        url = f"https://api.dexscreener.com/token-profiles/latest/v1"
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()

        solana_tokens = [
            item for item in data
            if item.get("chainId", "").lower() == SOLANA_CHAIN
        ]
        return solana_tokens[:10]

    except Exception as e:
        print(f"[signals] Error fetching new tokens: {e}")
        return []


def get_pair_details(token_address: str) -> dict | None:
    """Get detailed data for a specific token address."""
    try:
        url = f"{DEXSCREENER_BASE_URL}/tokens/{token_address}"
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()
        pairs = data.get("pairs", [])

        # Return the Solana pair with highest liquidity
        solana_pairs = [p for p in pairs if p.get("chainId") == SOLANA_CHAIN]
        if not solana_pairs:
            return None
        return max(solana_pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))

    except Exception as e:
        print(f"[signals] Error fetching pair details: {e}")
        return None


# ─── Signal Analysis ─────────────────────────────────────────

def calculate_probability(pair: dict) -> dict:
    """
    Calculate bullish/bearish probability from on-chain data.
    Returns a dict with scores and reasoning.
    """
    score = 50  # start neutral
    reasons = []

    price_change_1h  = float(pair.get("priceChange", {}).get("h1",  0) or 0)
    price_change_6h  = float(pair.get("priceChange", {}).get("h6",  0) or 0)
    price_change_24h = float(pair.get("priceChange", {}).get("h24", 0) or 0)
    volume_1h        = float(pair.get("volume",      {}).get("h1",  0) or 0)
    volume_24h       = float(pair.get("volume",      {}).get("h24", 0) or 0)
    liquidity_usd    = float(pair.get("liquidity",   {}).get("usd", 0) or 0)
    txns_buys_1h     = pair.get("txns", {}).get("h1", {}).get("buys",  0) or 0
    txns_sells_1h    = pair.get("txns", {}).get("h1", {}).get("sells", 0) or 0

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

    # Volume analysis
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

    # Clamp between 5 and 95
    score = max(5, min(95, score))

    return {
        "bullish":  score,
        "bearish":  100 - score,
        "reasons":  reasons,
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
    """
    signals = []
    trending = get_trending_solana_pairs()

    for item in trending:
        token_address = item.get("tokenAddress")
        if not token_address:
            continue

        pair = get_pair_details(token_address)
        if not pair:
            continue

        price_change_1h = float(pair.get("priceChange", {}).get("h1", 0) or 0)
        liquidity_usd   = float(pair.get("liquidity",   {}).get("usd", 0) or 0)

        # Only surface meaningful signals
        if abs(price_change_1h) < PRICE_CHANGE_THRESHOLD:
            continue
        if liquidity_usd < MIN_LIQUIDITY_USD:
            continue

        prob     = calculate_probability(pair)
        base_token = pair.get("baseToken", {})

        signals.append({
            "name":     base_token.get("name",   "Unknown"),
            "symbol":   base_token.get("symbol", "???"),
            "address":  base_token.get("address", ""),
            "price_usd": pair.get("priceUsd", "N/A"),
            "dex_url":  pair.get("url", ""),
            "probability": prob,
        })

    return signals


def get_new_token_alerts() -> list[dict]:
    """Return newly launched Solana tokens for the /newtokens command."""
    tokens = get_new_solana_tokens()
    results = []

    for token in tokens:
        results.append({
            "name":        token.get("description", "New Token"),
            "address":     token.get("tokenAddress", ""),
            "chain":       token.get("chainId", "solana"),
            "url":         token.get("url", ""),
            "icon":        token.get("icon", ""),
        })

    return results
