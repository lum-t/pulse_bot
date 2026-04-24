"""
ratelimit.py — PULSE Rate Limiter
Prevents admins from hammering commands and overloading APIs
Simple in-memory cooldown per user per command
"""

import time
from config import RATE_LIMIT_SECONDS

# Structure: { "user_id:command": last_used_timestamp }
_cooldowns: dict[str, float] = {}


def is_rate_limited(user_id: str, command: str) -> tuple[bool, int]:
    """
    Check if a user is rate limited for a command.
    Returns (is_limited, seconds_remaining)
    """
    key     = f"{user_id}:{command}"
    now     = time.time()
    last    = _cooldowns.get(key, 0)
    elapsed = now - last

    if elapsed < RATE_LIMIT_SECONDS:
        remaining = int(RATE_LIMIT_SECONDS - elapsed)
        return True, remaining

    return False, 0


def record_use(user_id: str, command: str):
    """Record that a user just used a command."""
    key = f"{user_id}:{command}"
    _cooldowns[key] = time.time()


def check_and_record(user_id: str, command: str) -> tuple[bool, int]:
    """
    Combined check + record in one call.
    Returns (is_limited, seconds_remaining).
    If not limited, records the use automatically.
    """
    limited, remaining = is_rate_limited(user_id, command)
    if not limited:
        record_use(user_id, command)
    return limited, remaining
