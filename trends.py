"""
trends.py — PULSE Content Engine
Fetches trending topics via Google Trends (pytrends) + generates
platform-specific content ideas via Gemini AI.

Keyword discovery is fully AI-driven: Gemini generates fresh, relevant
search keywords every run instead of relying on static config lists.
Static lists (ANIMATION_KEYWORDS, LIFESTYLE_KEYWORDS, GENERAL_TRENDING)
are only used as a fallback if Gemini is unavailable.
"""

import json
import logging
import time
import random
from datetime import datetime, timezone

import requests
from pytrends.request import TrendReq

import google.generativeai as genai

from config import (
    GEMINI_API_KEY,
    LIFESTYLE_KEYWORDS,
    ANIMATION_KEYWORDS,
    GENERAL_TRENDING,
    PLATFORMS,
    DEFAULT_TIMEZONE,
)

log = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)
gemini = genai.GenerativeModel("gemini-1.5-flash")

# ─── Google Trends ────────────────────────────────────────────

def _build_pytrends() -> TrendReq:
    return TrendReq(
        hl="en-US",
        tz=0,
        timeout=(10, 25),
        retries=3,
        backoff_factor=1.5,
    )


def _fetch_trend_score(keyword: str, pytrends: TrendReq, retries: int = 3) -> int:
    """
    Return a 0–100 Google Trends interest score for a keyword.
    Retries with exponential backoff on 429. Falls back to 0 on failure.
    """
    for attempt in range(retries):
        try:
            # Polite delay between requests to avoid rate limiting
            time.sleep(random.uniform(2.5, 5.0))
            pytrends.build_payload([keyword], timeframe="now 1-d", geo="")
            data = pytrends.interest_over_time()
            if data.empty:
                return 0
            return int(data[keyword].iloc[-1])
        except Exception as e:
            err_str = str(e)
            if "429" in err_str:
                wait = (2 ** attempt) * 10 + random.uniform(0, 5)
                log.warning(
                    f"[trends] 429 rate limit on '{keyword}' "
                    f"(attempt {attempt+1}/{retries}). Waiting {wait:.1f}s..."
                )
                time.sleep(wait)
            else:
                log.warning(f"[trends] Trend score error for '{keyword}': {e}")
                return 0
    log.error(f"[trends] All retries exhausted for '{keyword}' — skipping.")
    return 0


def _get_realtime_trending(retries: int = 3) -> list[str]:
    """
    Pull Google Trends realtime trending searches (US).
    Returns a list of topic strings. Retries with backoff on 429.
    """
    for attempt in range(retries):
        try:
            time.sleep(random.uniform(1.0, 3.0))
            pt = _build_pytrends()
            df = pt.trending_searches(pn="united_states")
            return df[0].tolist()[:10]
        except Exception as e:
            err_str = str(e)
            if "429" in err_str:
                wait = (2 ** attempt) * 10 + random.uniform(0, 5)
                log.warning(
                    f"[trends] 429 on realtime fetch "
                    f"(attempt {attempt+1}/{retries}). Waiting {wait:.1f}s..."
                )
                time.sleep(wait)
            else:
                log.warning(f"[trends] Realtime trending fetch failed: {e}")
                return []
    log.error("[trends] Realtime trending fetch failed after all retries.")
    return []


# ─── Gemini keyword generation ────────────────────────────────

def _gemini_generate_keywords() -> dict[str, list[str]]:
    """
    Ask Gemini to generate fresh, relevant keyword buckets for
    animation and lifestyle content — replacing static config lists.

    Returns a dict like:
        {
            "animation": ["keyword1", ...],
            "lifestyle": ["keyword1", ...],
            "general":   ["keyword1", ...],
        }

    Falls back to static config lists if Gemini is unavailable.
    """
    if not GEMINI_API_KEY:
        log.warning("[trends] No Gemini API key — using static keyword fallback.")
        return _static_keyword_fallback()

    prompt = """You are a trend researcher for a content creator who makes animation and lifestyle content.

Your job is to suggest Google Trends search keywords that are likely to have HIGH search interest RIGHT NOW.

Think about:
- Viral formats and challenges sweeping social media
- Pop culture moments (movies, shows, music, celebrities)
- Creator and YouTube meta trends
- Aesthetic movements and visual styles
- Animation techniques and styles gaining popularity
- Everyday lifestyle topics people are actively searching

Rules:
- Keywords must be short (1–4 words), natural search phrases
- No crypto, finance, or political keywords
- Prioritise topics relevant to Gen Z and millennial audiences
- Make them specific enough to return real Google Trends data

Respond ONLY in this exact JSON format, no markdown, no extra text:
{
  "animation": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"],
  "lifestyle": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"],
  "general":   ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"]
}"""

    try:
        response = gemini.generate_content(prompt)
        text = response.text.strip()
        text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(text)

        required = {"animation", "lifestyle", "general"}
        if not required.issubset(parsed.keys()):
            raise ValueError(f"Missing keyword buckets in Gemini response: {parsed.keys()}")

        log.info(f"[trends] Gemini generated keywords: {parsed}")
        return parsed

    except Exception as e:
        log.error(f"[trends] Gemini keyword generation failed: {e} — using static fallback.")
        return _static_keyword_fallback()


def _static_keyword_fallback() -> dict[str, list[str]]:
    """Returns the original static config lists as a safe fallback."""
    return {
        "animation": ANIMATION_KEYWORDS,
        "lifestyle": LIFESTYLE_KEYWORDS,
        "general":   GENERAL_TRENDING,
    }


# ─── Gemini idea generation ───────────────────────────────────

def _gemini_generate_ideas(topic: str, category: str, trend_score: int) -> dict:
    """
    Ask Gemini to generate platform-specific content ideas for a topic.
    Returns structured ideas dict ready for format_content_alert().
    """
    if not GEMINI_API_KEY:
        return _fallback_idea(topic, category, trend_score)

    prompt = f"""You are a viral content strategist for a creator who makes animation and lifestyle content.

TRENDING TOPIC: "{topic}"
CATEGORY: {category}
GOOGLE TREND SCORE: {trend_score}/100

Generate creative, specific content ideas for this creator. Focus on animation, lifestyle vlogging, and general entertainment angles. Do NOT generate crypto or financial content.

Respond ONLY in this exact JSON format, no markdown, no extra text:
{{
  "ideas": {{
    "YouTube": ["idea 1", "idea 2"],
    "TikTok": ["idea 1", "idea 2"],
    "X (Twitter)": ["idea 1", "idea 2"]
  }},
  "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"],
  "post_times": {{
    "YouTube": {{"time": "6:00 PM", "day": "Saturday", "urgency": "🔥 Peak weekend views", "hours_until": 8}},
    "TikTok": {{"time": "7:00 PM", "day": "Today", "urgency": "⚡ Post now", "hours_until": 2}},
    "X (Twitter)": {{"time": "12:00 PM", "day": "Tomorrow", "urgency": "📅 Schedule it", "hours_until": 18}}
  }}
}}"""

    try:
        response = gemini.generate_content(prompt)
        text = response.text.strip()
        text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(text)

        return {
            "topic":        topic,
            "category":     category,
            "status":       _trend_status(trend_score),
            "trend_score":  trend_score,
            "timestamp":    datetime.now(timezone.utc).strftime("%d %b %H:%M UTC"),
            "ideas":        parsed.get("ideas", _default_ideas(topic)),
            "hashtags":     parsed.get("hashtags", [f"#{topic.replace(' ', '')}"]),
            "post_times":   parsed.get("post_times", _default_post_times()),
            "ai_powered":   True,
        }

    except Exception as e:
        log.error(f"[trends] Gemini idea generation failed for '{topic}': {e}")
        return _fallback_idea(topic, category, trend_score)


def _trend_status(score: int) -> str:
    if score >= 75:
        return "🔥 Viral"
    if score >= 50:
        return "📈 Trending"
    if score >= 25:
        return "🌱 Rising"
    return "💡 Niche"


def _default_ideas(topic: str) -> dict:
    return {
        "YouTube":     [f"My honest take on {topic}", f"I tried {topic} for a week"],
        "TikTok":      [f"{topic} POV animation", f"Reacting to {topic}"],
        "X (Twitter)": [f"Thread: everything about {topic}", f"Hot take on {topic}"],
    }


def _default_post_times() -> dict:
    return {
        "YouTube":     {"time": "6:00 PM", "day": "Saturday",  "urgency": "🔥 Best reach",   "hours_until": 8},
        "TikTok":      {"time": "7:00 PM", "day": "Today",     "urgency": "⚡ Post tonight",  "hours_until": 3},
        "X (Twitter)": {"time": "12:00 PM","day": "Tomorrow",  "urgency": "📅 Schedule it",   "hours_until": 18},
    }


def _fallback_idea(topic: str, category: str, trend_score: int) -> dict:
    """Used when Gemini is unavailable — returns basic templated ideas."""
    return {
        "topic":       topic,
        "category":    category,
        "status":      _trend_status(trend_score),
        "trend_score": trend_score,
        "timestamp":   datetime.now(timezone.utc).strftime("%d %b %H:%M UTC"),
        "ideas":       _default_ideas(topic),
        "hashtags":    [f"#{w.replace(' ', '')}" for w in topic.split()[:3]] + ["#ContentCreator", "#Animation"],
        "post_times":  _default_post_times(),
        "ai_powered":  False,
    }


# ─── Public API ───────────────────────────────────────────────

def get_trending_content_ideas(max_results: int = 4) -> list[dict]:
    """
    Main trend detection pipeline:
    1. Pull Google realtime trending topics
    2. Ask Gemini to generate fresh keyword buckets (animation / lifestyle / general)
    3. Score all keywords against Google Trends (with polite delays + 429 backoff)
    4. Generate Gemini-powered ideas for the top hits
    Returns a list of idea dicts ready for format_content_alert().
    """
    pt    = _build_pytrends()
    ideas = []
    seen  = set()

    # Step 1 — Google realtime trending
    realtime = _get_realtime_trending()

    # Step 2 — AI-generated keyword buckets
    ai_keywords = _gemini_generate_keywords()

    # Build keyword pool: realtime first, then AI-generated buckets
    keyword_pool: list[tuple[str, str]] = []

    for topic in realtime:
        keyword_pool.append((topic, "general"))

    for category, keywords in ai_keywords.items():
        for kw in keywords:
            keyword_pool.append((kw, category))

    # Step 3 — Score and collect (capped to limit API calls)
    scored: list[tuple[int, str, str]] = []
    cap = 15  # Reduced from 20 to be gentler on Google's rate limits

    for keyword, category in keyword_pool[:cap]:
        if keyword.lower() in seen:
            continue
        seen.add(keyword.lower())

        score = _fetch_trend_score(keyword, pt)
        if score >= 50:
            scored.append((score, keyword, category))

    # Sort by score descending
    scored.sort(reverse=True)

    # Step 4 — Generate ideas for top N
    for score, keyword, category in scored[:max_results]:
        idea = _gemini_generate_ideas(keyword, category, score)
        ideas.append(idea)

    # If Google Trends returned nothing usable, generate ideas from AI keywords directly
    if not ideas:
        log.warning("[trends] No scored results — generating ideas from AI keywords directly.")
        for category, keywords in ai_keywords.items():
            if len(ideas) >= max_results:
                break
            for kw in keywords[:1]:
                idea = _gemini_generate_ideas(kw, category, trend_score=0)
                ideas.append(idea)
                if len(ideas) >= max_results:
                    break

    return ideas


def get_ideas_for_topic(topic: str) -> dict:
    """
    Generate content ideas for a specific topic (used by /ideas command).
    Fetches a live trend score then runs Gemini generation.
    """
    pt    = _build_pytrends()
    score = _fetch_trend_score(topic, pt)

    topic_lower = topic.lower()
    if any(kw in topic_lower for kw in ["animat", "motion", "2d", "3d", "cartoon"]):
        category = "animation"
    elif any(kw in topic_lower for kw in ["vlog", "routine", "grwm", "aesthetic", "life"]):
        category = "lifestyle"
    else:
        category = "general"

    return _gemini_generate_ideas(topic, category, score)
