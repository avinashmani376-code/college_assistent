# services/news_service.py
"""
News service — NewsData.io (free) → GNews → NewsAPI.
Direct fetch, NO AI, NO Tavily.
 
Root causes fixed:
1. Key name mismatch: .env has NEWSDATA_API, code was reading NEWS_DATA_API
   → now reads BOTH names
2. Free NewsData.io key (pub_...) cannot use ?q= search on /api/1/news
   → uses /api/1/latest-news endpoint (free plan compatible)
3. Added full debug logging to every step
"""
import os
import sys
import logging
import requests
from typing import List, Dict, Tuple
 
logger = logging.getLogger(__name__)
 
# ── Key loading — read every possible env var name ─────────────────────────
# .env file uses:    NEWSDATA_API
# render.yaml uses:  NEWS_DATA_API
# code also checks:  NEWSDATA_API_KEY  (just in case)
_ND_KEY = (
    os.getenv("NEWSDATA_API",     "")  # matches .env file exactly
    or os.getenv("NEWS_DATA_API", "")  # matches render.yaml
    or os.getenv("NEWSDATA_API_KEY", "")
)
GNEWS_API    = os.getenv("GNEWS_API",    "")
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
 
print(f"[NEWS] Key status at startup: "
      f"NewsData={'SET' if _ND_KEY else 'MISSING'} "
      f"GNews={'SET' if GNEWS_API else 'MISSING'} "
      f"NewsAPI={'SET' if NEWS_API_KEY else 'MISSING'}",
      file=sys.stderr)
 
 
def _from_newsdata_free(category: str = "top") -> List[Dict]:
    """
    NewsData.io FREE plan — uses /api/1/latest-news (no ?q= param needed).
    Free keys (pub_...) CANNOT use the /api/1/news search endpoint.
    """
    if not _ND_KEY:
        print("[NEWS] NewsData key missing — skipping", file=sys.stderr)
        return []
    try:
        print(f"[NEWS] NewsData.io /latest-news category={category!r}", file=sys.stderr)
        r = requests.get(
            "https://newsdata.io/api/1/latest-news",
            params={
                "apikey":   _ND_KEY,
                "language": "en",
                "country":  "in",      # India news by default
            },
            timeout=12,
        )
        print(f"[NEWS] NewsData status={r.status_code}", file=sys.stderr)
        if r.status_code != 200:
            err = r.text[:300]
            print(f"[NEWS] NewsData error body: {err}", file=sys.stderr)
            logger.warning("NewsData returned %s: %s", r.status_code, err)
            return []
        results = r.json().get("results") or []
        print(f"[NEWS] NewsData returned {len(results)} articles", file=sys.stderr)
        return [
            {
                "title":  (a.get("title")     or "").strip(),
                "url":    (a.get("link")      or "").strip(),
                "source": (a.get("source_id") or "NewsData").strip(),
            }
            for a in results
            if (a.get("title") or "").strip()
        ][:8]
    except Exception as e:
        print(f"[NEWS] NewsData exception: {e}", file=sys.stderr)
        logger.warning("NewsData exception: %s", e)
        return []
 
 
def _from_gnews(topic: str = "india") -> List[Dict]:
    """GNews fallback — works with free key."""
    if not GNEWS_API:
        print("[NEWS] GNews key missing — skipping", file=sys.stderr)
        return []
    try:
        print(f"[NEWS] GNews topic={topic!r}", file=sys.stderr)
        r = requests.get(
            "https://gnews.io/api/v4/top-headlines",
            params={
                "token":    GNEWS_API,
                "lang":     "en",
                "country":  "in",
                "max":      8,
                "topic":    "breaking-news",
            },
            timeout=12,
        )
        print(f"[NEWS] GNews status={r.status_code}", file=sys.stderr)
        if r.status_code != 200:
            print(f"[NEWS] GNews error: {r.text[:200]}", file=sys.stderr)
            return []
        articles = r.json().get("articles") or []
        print(f"[NEWS] GNews returned {len(articles)} articles", file=sys.stderr)
        return [
            {
                "title":  (a.get("title") or "").strip(),
                "url":    (a.get("url")   or "").strip(),
                "source": (a.get("source", {}).get("name") or "GNews").strip(),
            }
            for a in articles
            if (a.get("title") or "").strip()
        ]
    except Exception as e:
        print(f"[NEWS] GNews exception: {e}", file=sys.stderr)
        return []
 
 
def _from_newsapi(query: str = "india") -> List[Dict]:
    """NewsAPI.org fallback."""
    if not NEWS_API_KEY:
        print("[NEWS] NewsAPI key missing — skipping", file=sys.stderr)
        return []
    try:
        print(f"[NEWS] NewsAPI.org query={query!r}", file=sys.stderr)
        r = requests.get(
            "https://newsapi.org/v2/top-headlines",
            params={
                "country":  "in",
                "pageSize": 8,
                "apiKey":   NEWS_API_KEY,
            },
            timeout=12,
        )
        print(f"[NEWS] NewsAPI status={r.status_code}", file=sys.stderr)
        if r.status_code != 200:
            print(f"[NEWS] NewsAPI error: {r.text[:200]}", file=sys.stderr)
            return []
        articles = r.json().get("articles") or []
        print(f"[NEWS] NewsAPI returned {len(articles)} articles", file=sys.stderr)
        return [
            {
                "title":  (a.get("title") or "").strip(),
                "url":    (a.get("url")   or "").strip(),
                "source": (a.get("source", {}).get("name") or "NewsAPI").strip(),
            }
            for a in articles
            if (a.get("title") or "").strip()
               and "[Removed]" not in (a.get("title") or "")
        ]
    except Exception as e:
        print(f"[NEWS] NewsAPI exception: {e}", file=sys.stderr)
        return []
 
 
def fetch_news(user_message: str = "") -> Tuple[List[Dict], str]:
    """
    Try providers in order. Returns (articles, provider_name).
    Always fetches top/latest headlines — no query search (free plan).
    """
    print(f"[NEWS] fetch_news called: user_message={user_message!r}", file=sys.stderr)
 
    for fn, name, arg in [
        (_from_newsdata_free, "NEWSDATA", "top"),
        (_from_gnews,         "GNEWS",    "india"),
        (_from_newsapi,       "NEWSAPI",  "india"),
    ]:
        try:
            articles = fn(arg)
            if articles:
                print(f"[NEWS] SUCCESS via {name}: {len(articles)} articles", file=sys.stderr)
                return articles, name
        except Exception as e:
            print(f"[NEWS] Provider {name} crashed: {e}", file=sys.stderr)
 
    print("[NEWS] ALL providers failed", file=sys.stderr)
    return [], "NONE"
 
 
def summarize_news(articles: List[Dict], lang: str = "en") -> str:
    if not articles:
        if lang == "te":
            return "వార్తలు ఇప్పుడు అందుబాటులో లేవు. కొద్దిసేపటి తర్వాత మళ్లీ ప్రయత్నించండి."
        return "No news available right now. Please try again later."
 
    header = "📰 తాజా వార్తలు:\n" if lang == "te" else "📰 Latest News:\n"
    lines  = [header]
    for i, a in enumerate(articles[:5], 1):
        title = (a.get("title") or "").strip()
        if title:
            lines.append(f"{i}. {title}")
    return "\n".join(lines)
 