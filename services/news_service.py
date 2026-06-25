# services/news_service.py
"""
News service — GNews API ONLY.
No fallback providers.
Direct fetch, NO AI, NO Tavily.
 
On failure: logs status code + response body, returns failure message.
"""
import os
import sys
import re
import logging
import requests
from typing import List, Dict, Tuple
 
logger = logging.getLogger(__name__)
 
# Read from GNEWS_API_KEY (primary) or legacy GNEWS_API name
_GNEWS_KEY = (
    os.getenv("GNEWS_API_KEY", "")
    or os.getenv("GNEWS_API", "")
)
 
print(
    f"[NEWS] Key status at startup: GNews={'SET' if _GNEWS_KEY else 'MISSING'}",
    file=sys.stderr,
)
 
# ── Noise words to strip when extracting a search topic ───────────────────
_NOISE_WORDS = {
    "latest", "today", "today's", "todays", "news", "about", "on",
    "tell", "me", "show", "give", "current", "recent", "new",
    "breaking", "headlines", "headline", "update", "updates",
    "what", "is", "are", "the", "a", "an", "in", "of", "for",
    "whats", "what's",
}

# ── Phrases that mean "general news" (no specific topic) ──────────────────
_GENERIC_PHRASES = {
    "latest news", "today's news", "todays news", "breaking news",
    "top news", "top headlines", "news today", "current news",
    "recent news", "news",
}

# ── Topic keyword map for GNews `topic` param (top-headlines only) ─────────
_TOPIC_MAP = {
    "technology": "technology",
    "tech":       "technology",
    "education":  "education",
    "sports":     "sports",
    "sport":      "sports",
    "business":   "business",
    "finance":    "business",
    "breaking":   "breaking-news",
    "india":      "nation",
    "national":   "nation",
}
 
# ── "Why it matters" templates keyed on topic/keyword ─────────────────────
_WHY_MATTERS = {
    "technology":    "It affects how we use technology in our daily lives.",
    "tech":          "It affects how we use technology in our daily lives.",
    "education":     "It directly impacts students and schools across India.",
    "sports":        "It is important for Indian sports and its fans.",
    "sport":         "It is important for Indian sports and its fans.",
    "business":      "It affects jobs, prices, and the Indian economy.",
    "finance":       "It affects jobs, prices, and the Indian economy.",
    "health":        "It affects the health and well-being of people.",
    "science":       "It helps us understand the world and improve our lives.",
    "space":         "It shows India's growing strength in science and space.",
    "satellite":     "It helps improve communication and weather services.",
    "politics":      "It shapes how India is governed and run.",
    "election":      "It decides who will lead and make decisions for India.",
    "environment":   "It affects the air, water, and nature around us.",
    "climate":       "It affects weather, farming, and life on Earth.",
    "economy":       "It impacts the cost of living and job opportunities.",
    "cricket":       "It matters to millions of cricket fans across India.",
    "default":       "It is an important development that affects many people.",
}
 

def _extract_search_query(user_message: str) -> str:
    """
    Strip noise words from the user message to get a clean search topic.
    Returns an empty string if no meaningful topic remains (generic request).

    Examples:
        "Latest news about petrol"  → "petrol"
        "Today's AI news"           → "AI"
        "Show me business news"     → "business"
        "Latest news"               → ""
        "Breaking news"             → ""
    """
    normalized = user_message.strip().lower()

    # Check if the whole message matches a generic phrase — return empty
    if normalized in _GENERIC_PHRASES:
        return ""

    # Remove punctuation (apostrophes already handled via normalization)
    cleaned = re.sub(r"[^\w\s]", " ", normalized)

    # Split into words and filter out noise words
    words = [w for w in cleaned.split() if w not in _NOISE_WORDS]

    query = " ".join(words).strip()
    return query


def _detect_topic(user_message: str) -> str:
    """Map user message to a GNews topic param (used for top-headlines fallback)."""
    msg = user_message.lower()
    for kw, topic in _TOPIC_MAP.items():
        if kw in msg:
            return topic
    return "breaking-news"
 
 
def _why_matters(title: str, description: str, topic: str) -> str:
    """Return a short 'why it matters' sentence based on content keywords."""
    text = (title + " " + description).lower()
    for kw, reason in _WHY_MATTERS.items():
        if kw == "default":
            continue
        if kw in text:
            return reason
    # Fall back to topic-level reason
    for kw, mapped_topic in _TOPIC_MAP.items():
        if mapped_topic == topic and kw in _WHY_MATTERS:
            return _WHY_MATTERS[kw]
    return _WHY_MATTERS["default"]
 
 
def _simplify(text: str, max_sentences: int = 2, max_words: int = 40) -> str:
    """
    Return a clean, short version of `text`.
    - Strips HTML/URLs/source suffixes (e.g. '- Reuters')
    - Keeps at most `max_sentences` sentences
    - Truncates to `max_words` words
    """
    if not text:
        return ""
    # Strip HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Strip trailing source attribution like ' - Reuters' or ' | NDTV'
    text = re.sub(r"\s*[-|]\s*\w[\w\s]{0,30}$", "", text).strip()
    # Strip URLs
    text = re.sub(r"https?://\S+", "", text).strip()
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
 
    # Split into sentences and keep the first max_sentences
    sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    short = " ".join(sentences[:max_sentences])
 
    # Word cap
    words = short.split()
    if len(words) > max_words:
        short = " ".join(words[:max_words]).rstrip(",.;:") + "."
 
    if short and not short[-1] in ".!?":
        short += "."
    return short
 

def _from_gnews_search(query: str) -> List[Dict]:
    """
    GNews /search endpoint — used when a specific topic is detected.
    Returns list of {title, description, source, url, topic} dicts (max 5).
    On failure: logs status + body, returns empty list.
    """
    if not _GNEWS_KEY:
        print("[NEWS] GNews key missing — cannot fetch news", file=sys.stderr)
        logger.error("GNews API key not set (GNEWS_API_KEY or GNEWS_API)")
        return []

    try:
        print(f"[NEWS] GNews /search q={query!r} fetching...", file=sys.stderr)
        r = requests.get(
            "https://gnews.io/api/v4/search",
            params={
                "token": _GNEWS_KEY,
                "lang":  "en",
                "max":   10,
                "q":     query,
            },
            timeout=5,
        )
        print(f"[NEWS] GNews /search status={r.status_code}", file=sys.stderr)

        if r.status_code != 200:
            body = r.text[:500]
            print(
                f"[NEWS] GNews /search FAILED — status={r.status_code} body={body}",
                file=sys.stderr,
            )
            logger.error("GNews /search error: status=%s body=%s", r.status_code, body)
            return []

        raw = r.json().get("articles") or []
        print(f"[NEWS] GNews /search returned {len(raw)} raw articles", file=sys.stderr)

        articles = []
        for a in raw:
            title = (a.get("title") or "").strip()
            if not title:
                continue
            articles.append({
                "title":       title,
                "description": (a.get("description") or "").strip(),
                "source":      (a.get("source", {}).get("name") or "GNews").strip(),
                "url":         (a.get("url") or "").strip(),
                "topic":       query,
            })
            if len(articles) == 5:
                break

        print(f"[NEWS] GNews /search parsed {len(articles)} valid articles", file=sys.stderr)
        return articles

    except Exception as e:
        print(f"[NEWS] GNews /search exception: {e}", file=sys.stderr)
        logger.error("GNews /search exception: %s", e)
        return []


def _from_gnews(topic: str = "breaking-news") -> List[Dict]:
    """
    GNews top headlines — free plan compatible.
    Returns list of {title, description, source, url} dicts (max 5).
    On failure: logs status + body, returns empty list.
    """
    if not _GNEWS_KEY:
        print("[NEWS] GNews key missing — cannot fetch news", file=sys.stderr)
        logger.error("GNews API key not set (GNEWS_API_KEY or GNEWS_API)")
        return []
 
    try:
        print(f"[NEWS] GNews /top-headlines topic={topic!r} fetching...", file=sys.stderr)
        r = requests.get(
            "https://gnews.io/api/v4/top-headlines",
            params={
                "token":   _GNEWS_KEY,
                "lang":    "en",
                "country": "in",
                "max":     10,
                "topic":   topic,
            },
            timeout=5,
        )
        print(f"[NEWS] GNews status={r.status_code}", file=sys.stderr)
 
        if r.status_code != 200:
            body = r.text[:500]
            print(
                f"[NEWS] GNews FAILED — status={r.status_code} body={body}",
                file=sys.stderr,
            )
            logger.error("GNews error: status=%s body=%s", r.status_code, body)
            return []
 
        raw = r.json().get("articles") or []
        print(f"[NEWS] GNews returned {len(raw)} raw articles", file=sys.stderr)
 
        articles = []
        for a in raw:
            title = (a.get("title") or "").strip()
            if not title:
                continue
            articles.append({
                "title":       title,
                "description": (a.get("description") or "").strip(),
                "source":      (a.get("source", {}).get("name") or "GNews").strip(),
                "url":         (a.get("url") or "").strip(),
                "topic":       topic,
            })
            if len(articles) == 5:
                break
 
        print(f"[NEWS] Parsed {len(articles)} valid articles", file=sys.stderr)
        return articles
 
    except Exception as e:
        print(f"[NEWS] GNews exception: {e}", file=sys.stderr)
        logger.error("GNews exception: %s", e)
        return []
 
 
def fetch_news(user_message: str = "") -> Tuple[List[Dict], str]:
    """
    Fetch up to 5 news articles from GNews.

    Decision logic:
      - If a specific topic is detected in user_message → use /search endpoint
      - Otherwise (generic "latest news", "breaking news", etc.) → use /top-headlines

    Returns (articles, provider_name).
    If search returns no articles, returns ([], "NO_RESULTS:<topic>") so the
    caller can show a targeted "no results" message.
    """
    print(f"[NEWS] fetch_news called: user_message={user_message!r}", file=sys.stderr)

    search_query = _extract_search_query(user_message)

    if search_query:
        # Specific topic detected — use search endpoint
        print(f"[NEWS] Topic detected: {search_query!r} → using /search", file=sys.stderr)
        articles = _from_gnews_search(search_query)
        if articles:
            print(f"[NEWS] SUCCESS: {len(articles)} articles from GNEWS /search", file=sys.stderr)
            return articles, "GNEWS"
        print(f"[NEWS] GNews /search returned no articles for {search_query!r}", file=sys.stderr)
        return [], f"NO_RESULTS:{search_query}"
    else:
        # Generic request — use top-headlines
        topic = _detect_topic(user_message)
        print(f"[NEWS] No specific topic — using /top-headlines topic={topic!r}", file=sys.stderr)
        articles = _from_gnews(topic=topic)
        if articles:
            print(f"[NEWS] SUCCESS: {len(articles)} articles from GNEWS /top-headlines", file=sys.stderr)
            return articles, "GNEWS"
        print("[NEWS] GNews /top-headlines returned no articles", file=sys.stderr)
        return [], "NONE"
 
 
def summarize_news(articles: List[Dict], lang: str = "en") -> str:
    """
    Format each article as:
      📰 <Headline>
      📌 What happened: <2-3 simple sentences, ≤50 words>
      🌍 Why it matters: <1 sentence>
      🔗 Source: <name>
    """
    if not articles:
        if lang == "te":
            return (
                "తాజా వార్తలు తీసుకోవడం సాధ్యం కాలేదు. "
                "దయచేసి కొద్దిసేపటి తర్వాత మళ్లీ ప్రయత్నించండి."
            )
        return "Unable to fetch the latest news."
 
    blocks = []
    for a in articles:
        title  = (a.get("title")       or "").strip()
        desc   = (a.get("description") or "").strip()
        source = (a.get("source")      or "GNews").strip()
        topic  = (a.get("topic")       or "breaking-news")
 
        if not title:
            continue
 
        what_happened = _simplify(desc, max_sentences=3, max_words=50)
        if not what_happened:
            what_happened = _simplify(title, max_sentences=1, max_words=25)
 
        why = _why_matters(title, desc, topic)
 
        block = (
            f"📰 {title}\n"
            f"📌 What happened:\n{what_happened}\n"
            f"🌍 Why it matters:\n{why}\n"
            f"🔗 Source: {source}"
        )
        blocks.append(block)
 
    if not blocks:
        return "Unable to fetch the latest news."
 
    header = "📰 తాజా వార్తలు\n\n" if lang == "te" else "📰 Latest News\n\n"
    return header + "\n\n─────────────\n\n".join(blocks)


def format_news_response(articles: List[Dict], provider: str, lang: str = "en") -> str:
    """
    Wrapper that handles the NO_RESULTS sentinel from fetch_news.
    Use this instead of calling summarize_news directly when you have
    the (articles, provider) tuple from fetch_news.

    Returns "No recent news found for '<topic>'." when search has no results.
    """
    if not articles and provider.startswith("NO_RESULTS:"):
        topic = provider.split("NO_RESULTS:", 1)[1]
        return f"No recent news found for '{topic}'."
    return summarize_news(articles, lang=lang)