"""
history.py — PULSE Signal History
Stores and retrieves the last N market signals and content ideas
"""

import json
from datetime import datetime, timezone
from config import HISTORY_FILE, MAX_HISTORY_SIZE


def _load() -> dict:
    try:
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"signals": [], "trends": []}


def _save(data: dict):
    with open(HISTORY_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ─── Signals ──────────────────────────────────────────────────

def save_signal(signal: dict):
    """Save a detected signal to history."""
    data = _load()
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "name":      signal.get("name", "Unknown"),
        "symbol":    signal.get("symbol", "???"),
        "price_usd": signal.get("price_usd", "N/A"),
        "dex_url":   signal.get("dex_url", ""),
        "bullish":   signal["probability"]["bullish"],
        "bearish":   signal["probability"]["bearish"],
        "price_change_1h": signal["probability"]["price_change_1h"],
        "reasons":   signal["probability"]["reasons"],
    }
    data["signals"].insert(0, entry)
    data["signals"] = data["signals"][:MAX_HISTORY_SIZE]
    _save(data)


def save_trend(idea: dict):
    """Save a detected trend/content idea to history."""
    data = _load()
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "topic":     idea.get("topic", "Unknown"),
        "category":  idea.get("category", "general"),
        "status":    idea.get("status", ""),
    }
    data["trends"].insert(0, entry)
    data["trends"] = data["trends"][:MAX_HISTORY_SIZE]
    _save(data)


def get_signal_history(limit: int = 10) -> list[dict]:
    """Return last N signals."""
    data = _load()
    return data.get("signals", [])[:limit]


def get_trend_history(limit: int = 10) -> list[dict]:
    """Return last N trends."""
    data = _load()
    return data.get("trends", [])[:limit]


def clear_history():
    """Wipe all history — admin use only."""
    _save({"signals": [], "trends": []})
