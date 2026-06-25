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
import json
import logging
import requests
from typing import List, Dict, Optional, Tuple

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
    "technology":  "It affects how we use technology in our daily lives.",
    "tech":        "It affects how we use technology in our daily lives.",
    "education":   "It directly impacts students and schools across India.",
    "sports":      "It is important for Indian sports and its fans.",
    "sport":       "It is important for Indian sports and its fans.",
    "business":    "It affects jobs, prices, and the Indian economy.",
    "finance":     "It affects jobs, prices, and the Indian economy.",
    "health":      "It affects the health and well-being of people.",
    "science":     "It helps us understand the world and improve our lives.",
    "space":       "It shows India's growing strength in science and space.",
    "satellite":   "It helps improve communication and weather services.",
    "politics":    "It shapes how India is governed and run.",
    "election":    "It decides who will lead and make decisions for India.",
    "environment": "It affects the air, water, and nature around us.",
    "climate":     "It affects weather, farming, and life on Earth.",
    "economy":     "It impacts the cost of living and job opportunities.",
    "cricket":     "It matters to millions of cricket fans across India.",
    "default":     "It is an important development that affects many people.",
}

# ── Error message templates ────────────────────────────────────────────────
_ERR_INVALID_KEY  = "News service: Invalid API key. Please check GNEWS_API_KEY."
_ERR_RATE_LIMIT   = "News service: API rate limit reached. Please try again later."
_ERR_API_FAILURE  = "News service: API request failed. Please try again shortly."
_ERR_PARSE        = "News service: Unexpected response from news API. Please try again."
_ERR_NO_KEY       = "News service: API key not configured."


def _extract_search_query(user_message: str) -> str:
    """
    Normalize user message and strip noise words to get a clean search topic.
    Returns lowercase, punctuation-free topic string.
    Returns empty string for fully generic requests.

    Examples:
        "Latest news about petrol"     -> "petrol"
        "Today's AI news"              -> "ai"
        "Show me business news"        -> "business"
        "latest news about elone musk" -> "elone musk"
        "Latest news"                  -> ""
        "Breaking news"                -> ""
    """
    normalized = user_message.strip().lower()

    if normalized in _GENERIC_PHRASES:
        return ""

    cleaned = re.sub(r"[^\w\s]", " ", normalized)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    words = [w for w in cleaned.split() if w not in _NOISE_WORDS]
    return " ".join(words).strip()


def _detect_topic(user_message: str) -> str:
    """Map user message to a GNews topic param (used for top-headlines only)."""
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
    for kw, mapped_topic in _TOPIC_MAP.items():
        if mapped_topic == topic and kw in _WHY_MATTERS:
            return _WHY_MATTERS[kw]
    return _WHY_MATTERS["default"]


def _simplify(text: str, max_sentences: int = 2, max_words: int = 40) -> str:
    """
    Return a clean, short version of text.
    - Strips HTML/URLs/source suffixes (e.g. '- Reuters')
    - Keeps at most max_sentences sentences
    - Truncates to max_words words
    """
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s*[-|]\s*\w[\w\s]{0,30}$", "", text).strip()
    text = re.sub(r"https?://\S+", "", text).strip()
    text = re.sub(r"\s+", " ", text).strip()

    sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    short = " ".join(sentences[:max_sentences])

    words = short.split()
    if len(words) > max_words:
        short = " ".join(words[:max_words]).rstrip(",.;:") + "."

    if short and short[-1] not in ".!?":
        short += "."
    return short


def _call_gnews_search(query: str) -> Tuple[Optional[List[Dict]], Optional[str]]:
    """
    Call GNews /search endpoint for a specific query string.

    Returns:
      (articles, error_message)

      Success with articles  -> (list_of_dicts, None)
      Success but empty      -> ([], None)
      API / network failure  -> (None, human_readable_error_string)

    Full debug info is printed to stderr before every return.
    """
    sep = "=" * 60

    print(f"\n{sep}", file=sys.stderr)
    print(f"[NEWS DEBUG] GNews /search called", file=sys.stderr)
    print(f"[NEWS DEBUG] Requested Topic : {query!r}", file=sys.stderr)

    if not _GNEWS_KEY:
        print(f"[NEWS DEBUG] API Key         : MISSING", file=sys.stderr)
        print(f"{sep}\n", file=sys.stderr)
        logger.error("GNews API key not set (GNEWS_API_KEY or GNEWS_API)")
        return None, _ERR_NO_KEY

    print(f"[NEWS DEBUG] API Key         : SET (length={len(_GNEWS_KEY)})", file=sys.stderr)

    url = "https://gnews.io/api/v4/search"
    params = {
        "token": _GNEWS_KEY,
        "lang":  "en",
        "max":   10,
        "q":     query,
    }
    safe_params = {k: v for k, v in params.items() if k != "token"}
    print(f"[NEWS DEBUG] Request URL     : {url}?{safe_params}", file=sys.stderr)

    try:
        r = requests.get(url, params=params, timeout=8)

        print(f"[NEWS DEBUG] HTTP Status     : {r.status_code}", file=sys.stderr)
        print(f"[NEWS DEBUG] Response Body   :\n{r.text[:1000]}", file=sys.stderr)

        # ── Non-200 responses ─────────────────────────────────────────────
        if r.status_code != 200:
            logger.error(
                "GNews /search HTTP %s — body: %s", r.status_code, r.text[:1000]
            )

            if r.status_code in (401, 403):
                print(f"[NEWS DEBUG] -> Invalid or unauthorized API key", file=sys.stderr)
                print(f"{sep}\n", file=sys.stderr)
                return None, _ERR_INVALID_KEY

            if r.status_code == 429:
                print(f"[NEWS DEBUG] -> Rate limit exceeded", file=sys.stderr)
                print(f"{sep}\n", file=sys.stderr)
                return None, _ERR_RATE_LIMIT

            print(f"[NEWS DEBUG] -> Unhandled HTTP error {r.status_code}", file=sys.stderr)
            print(f"{sep}\n", file=sys.stderr)
            return None, f"{_ERR_API_FAILURE} (HTTP {r.status_code})"

        # ── Parse JSON ────────────────────────────────────────────────────
        try:
            data = r.json()
        except Exception as parse_exc:
            print(f"[NEWS DEBUG] -> JSON parse error: {parse_exc}", file=sys.stderr)
            print(f"{sep}\n", file=sys.stderr)
            logger.error("GNews /search JSON parse error: %s", parse_exc)
            return None, _ERR_PARSE

        print(f"[NEWS DEBUG] Parsed JSON     : {json.dumps(data)[:1000]}", file=sys.stderr)

        # ── Check for API-level errors ────────────────────────────────────
        if "errors" in data:
            print(f"[NEWS DEBUG] -> API errors: {data['errors']}", file=sys.stderr)
            print(f"{sep}\n", file=sys.stderr)
            logger.error("GNews /search API errors: %s", data["errors"])
            errors_str = "; ".join(str(e) for e in data["errors"])
            return None, f"{_ERR_API_FAILURE} ({errors_str})"

        # ── Extract articles ──────────────────────────────────────────────
        raw = data.get("articles") or []
        print(f"[NEWS DEBUG] Articles Found  : {len(raw)}", file=sys.stderr)

        if not raw:
            print(f"[NEWS DEBUG] -> No articles returned for topic: {query!r}", file=sys.stderr)
            print(f"{sep}\n", file=sys.stderr)
            return [], None  # API worked fine, just zero results

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

        print(f"[NEWS DEBUG] Valid Articles  : {len(articles)}", file=sys.stderr)
        print(f"{sep}\n", file=sys.stderr)
        return articles, None

    except requests.exceptions.Timeout:
        print(f"[NEWS DEBUG] -> Request timed out after 8s", file=sys.stderr)
        print(f"{sep}\n", file=sys.stderr)
        logger.error("GNews /search timeout for query=%s", query)
        return None, f"{_ERR_API_FAILURE} (connection timed out)"

    except requests.exceptions.ConnectionError as ce:
        print(f"[NEWS DEBUG] -> Connection error: {ce}", file=sys.stderr)
        print(f"{sep}\n", file=sys.stderr)
        logger.error("GNews /search connection error: %s", ce)
        return None, f"{_ERR_API_FAILURE} (connection error)"

    except Exception as e:
        print(f"[NEWS DEBUG] -> Unexpected exception: {e}", file=sys.stderr)
        print(f"{sep}\n", file=sys.stderr)
        logger.error("GNews /search exception: %s", e)
        return None, _ERR_API_FAILURE


def _from_gnews_search(query: str) -> Tuple[Optional[List[Dict]], Optional[str]]:
    """
    Search GNews for a topic, with ONE automatic word-by-word fallback.

    Strategy:
      1. Search with the full cleaned query (e.g. "elone musk").
      2. If API succeeded but returned zero articles, try each individual
         word (>=3 chars, longest first) as a standalone search.
      3. If the API itself fails, stop and return the error.

    Returns:
      (articles, error_message)
        Success with articles -> (list, None)
        Zero results          -> ([], None)
        API failure           -> (None, error_string)
    """
    articles, err = _call_gnews_search(query)

    if err is not None:
        return None, err  # hard API failure

    if articles:
        return articles, None  # full query succeeded

    # Word-by-word fallback
    words = [w for w in query.split() if len(w) >= 3]
    words_sorted = sorted(set(words), key=len, reverse=True)

    for word in words_sorted:
        if word == query:
            continue
        print(f"[NEWS] Fallback: trying word={word!r}", file=sys.stderr)
        fallback_articles, fallback_err = _call_gnews_search(word)
        if fallback_err is not None:
            return None, fallback_err
        if fallback_articles:
            print(f"[NEWS] Fallback succeeded with word={word!r}", file=sys.stderr)
            return fallback_articles, None

    return [], None


def _from_gnews(topic: str = "breaking-news") -> Tuple[Optional[List[Dict]], Optional[str]]:
    """
    GNews /top-headlines — used for generic requests with no specific topic.

    Returns:
      (articles, error_message)
        Success with articles -> (list, None)
        Zero results          -> ([], None)
        API failure           -> (None, error_string)
    """
    sep = "=" * 60

    print(f"\n{sep}", file=sys.stderr)
    print(f"[NEWS DEBUG] GNews /top-headlines called", file=sys.stderr)
    print(f"[NEWS DEBUG] Requested Topic : {topic!r}", file=sys.stderr)

    if not _GNEWS_KEY:
        print(f"[NEWS DEBUG] API Key         : MISSING", file=sys.stderr)
        print(f"{sep}\n", file=sys.stderr)
        logger.error("GNews API key not set (GNEWS_API_KEY or GNEWS_API)")
        return None, _ERR_NO_KEY

    print(f"[NEWS DEBUG] API Key         : SET (length={len(_GNEWS_KEY)})", file=sys.stderr)

    url = "https://gnews.io/api/v4/top-headlines"
    params = {
        "token":   _GNEWS_KEY,
        "lang":    "en",
        "country": "in",
        "max":     10,
        "topic":   topic,
    }
    safe_params = {k: v for k, v in params.items() if k != "token"}
    print(f"[NEWS DEBUG] Request URL     : {url}?{safe_params}", file=sys.stderr)

    try:
        r = requests.get(url, params=params, timeout=8)

        print(f"[NEWS DEBUG] HTTP Status     : {r.status_code}", file=sys.stderr)
        print(f"[NEWS DEBUG] Response Body   :\n{r.text[:1000]}", file=sys.stderr)

        if r.status_code != 200:
            logger.error(
                "GNews /top-headlines HTTP %s — body: %s", r.status_code, r.text[:1000]
            )
            if r.status_code in (401, 403):
                print(f"[NEWS DEBUG] -> Invalid or unauthorized API key", file=sys.stderr)
                print(f"{sep}\n", file=sys.stderr)
                return None, _ERR_INVALID_KEY
            if r.status_code == 429:
                print(f"[NEWS DEBUG] -> Rate limit exceeded", file=sys.stderr)
                print(f"{sep}\n", file=sys.stderr)
                return None, _ERR_RATE_LIMIT
            print(f"[NEWS DEBUG] -> Unhandled HTTP error {r.status_code}", file=sys.stderr)
            print(f"{sep}\n", file=sys.stderr)
            return None, f"{_ERR_API_FAILURE} (HTTP {r.status_code})"

        try:
            data = r.json()
        except Exception as parse_exc:
            print(f"[NEWS DEBUG] -> JSON parse error: {parse_exc}", file=sys.stderr)
            print(f"{sep}\n", file=sys.stderr)
            logger.error("GNews /top-headlines JSON parse error: %s", parse_exc)
            return None, _ERR_PARSE

        print(f"[NEWS DEBUG] Parsed JSON     : {json.dumps(data)[:1000]}", file=sys.stderr)

        if "errors" in data:
            print(f"[NEWS DEBUG] -> API errors: {data['errors']}", file=sys.stderr)
            print(f"{sep}\n", file=sys.stderr)
            logger.error("GNews /top-headlines API errors: %s", data["errors"])
            errors_str = "; ".join(str(e) for e in data["errors"])
            return None, f"{_ERR_API_FAILURE} ({errors_str})"

        raw = data.get("articles") or []
        print(f"[NEWS DEBUG] Articles Found  : {len(raw)}", file=sys.stderr)

        if not raw:
            print(f"[NEWS DEBUG] -> No articles returned for topic: {topic!r}", file=sys.stderr)
            print(f"{sep}\n", file=sys.stderr)
            return [], None

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

        print(f"[NEWS DEBUG] Valid Articles  : {len(articles)}", file=sys.stderr)
        print(f"{sep}\n", file=sys.stderr)
        return articles, None

    except requests.exceptions.Timeout:
        print(f"[NEWS DEBUG] -> Request timed out after 8s", file=sys.stderr)
        print(f"{sep}\n", file=sys.stderr)
        logger.error("GNews /top-headlines timeout for topic=%s", topic)
        return None, f"{_ERR_API_FAILURE} (connection timed out)"

    except requests.exceptions.ConnectionError as ce:
        print(f"[NEWS DEBUG] -> Connection error: {ce}", file=sys.stderr)
        print(f"{sep}\n", file=sys.stderr)
        logger.error("GNews /top-headlines connection error: %s", ce)
        return None, f"{_ERR_API_FAILURE} (connection error)"

    except Exception as e:
        print(f"[NEWS DEBUG] -> Unexpected exception: {e}", file=sys.stderr)
        print(f"{sep}\n", file=sys.stderr)
        logger.error("GNews /top-headlines exception: %s", e)
        return None, _ERR_API_FAILURE


def fetch_news(user_message: str = "") -> Tuple[List[Dict], str]:
    """
    Fetch up to 5 news articles from GNews.

    Decision logic:
      - Specific topic detected -> /search (with word-by-word fallback)
      - Generic request          -> /top-headlines

    Returns (articles, provider_tag) where provider_tag is one of:
      "GNEWS"              -- success, articles populated
      "NO_RESULTS:<topic>" -- API worked, no articles found for topic
      "ERROR:<message>"    -- API / network / key failure with reason
    """
    print(f"[NEWS] fetch_news called: user_message={user_message!r}", file=sys.stderr)

    search_query = _extract_search_query(user_message)

    if search_query:
        print(f"[NEWS] Topic detected: {search_query!r} -> using /search", file=sys.stderr)
        articles, err = _from_gnews_search(search_query)

        if err is not None:
            print(f"[NEWS] /search API error: {err}", file=sys.stderr)
            return [], f"ERROR:{err}"

        if articles:
            print(f"[NEWS] SUCCESS: {len(articles)} articles", file=sys.stderr)
            return articles, "GNEWS"

        print(f"[NEWS] No articles for {search_query!r} after fallback", file=sys.stderr)
        return [], f"NO_RESULTS:{search_query}"

    else:
        topic = _detect_topic(user_message)
        print(f"[NEWS] No specific topic — using /top-headlines topic={topic!r}", file=sys.stderr)
        articles, err = _from_gnews(topic=topic)

        if err is not None:
            print(f"[NEWS] /top-headlines API error: {err}", file=sys.stderr)
            return [], f"ERROR:{err}"

        if articles:
            print(f"[NEWS] SUCCESS: {len(articles)} articles", file=sys.stderr)
            return articles, "GNEWS"

        print("[NEWS] /top-headlines returned no articles", file=sys.stderr)
        return [], "NO_RESULTS:general"


def summarize_news(articles: List[Dict], lang: str = "en") -> str:
    """
    Format each article as:
      📰 <Headline>
      📌 What happened: <2-3 simple sentences, <=50 words>
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
    Wrapper around summarize_news that handles provider_tag sentinels.

    provider_tag              -> message shown
    ──────────────────────────────────────────────────────────────────
    "GNEWS"                   -> formatted article blocks
    "NO_RESULTS:<topic>"      -> "No recent news found for '<Topic>'."
    "NO_RESULTS:general"      -> "No recent news found."
    "ERROR:<message>"         -> specific error (key / rate limit / timeout)
    """
    if not articles:
        if provider.startswith("NO_RESULTS:"):
            topic = provider.split("NO_RESULTS:", 1)[1]
            if topic == "general":
                if lang == "te":
                    return (
                        "తాజా వార్తలు తీసుకోవడం సాధ్యం కాలేదు. "
                        "దయచేసి కొద్దిసేపటి తర్వాత మళ్లీ ప్రయత్నించండి."
                    )
                return "No recent news found."
            display = topic.title()
            return f"No recent news found for '{display}'."

        if provider.startswith("ERROR:"):
            error_msg = provider.split("ERROR:", 1)[1]
            if lang == "te":
                return (
                    "వార్తలు తీసుకోవడంలో సమస్య వచ్చింది. "
                    "దయచేసి కొద్దిసేపటి తర్వాత మళ్లీ ప్రయత్నించండి."
                )
            return error_msg

        if lang == "te":
            return (
                "తాజా వార్తలు తీసుకోవడం సాధ్యం కాలేదు. "
                "దయచేసి కొద్దిసేపటి తర్వాత మళ్లీ ప్రయత్నించండి."
            )
        return "Unable to fetch the latest news."

    return summarize_news(articles, lang=lang)