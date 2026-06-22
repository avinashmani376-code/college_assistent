# services/news_service.py
"""
News service.
Primary: NewsData.io  Fallback: GNews → NewsAPI
Direct fetch — NO AI, NO Tavily.
"""
import os
import logging
import requests
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)

NEWS_DATA_API = os.getenv("NEWS_DATA_API", "")
GNEWS_API     = os.getenv("GNEWS_API", "")
NEWS_API_KEY  = os.getenv("NEWS_API_KEY", "")

# NewsData.io API key has two possible env names
_ND_KEY = NEWS_DATA_API or os.getenv("NEWSDATA_API_KEY", "")

_TIMEOUT = 12


def _from_newsdata(query: str) -> List[Dict]:
    if not _ND_KEY:
        print("[NEWS] NEWS_DATA_API key not set — skipping NewsData.io")
        return []
    try:
        url = "https://newsdata.io/api/1/news"
        params = {"q": query, "language": "en", "apikey": _ND_KEY}
        print(f"[NEWS] NewsData.io → GET {url} params={params}")
        r = requests.get(url, params=params, timeout=_TIMEOUT)
        print(f"[NEWS] NewsData.io status={r.status_code}")
        if r.status_code == 401:
            logger.warning("[NEWS] NewsData.io: Invalid API key (401)")
            return []
        if r.status_code == 429:
            logger.warning("[NEWS] NewsData.io: Rate limit exceeded (429)")
            return []
        if r.status_code != 200:
            logger.warning("[NEWS] NewsData.io returned %s: %s", r.status_code, r.text[:300])
            return []
        body = r.json()
        if body.get("status") != "success":
            logger.warning("[NEWS] NewsData.io response status=%s", body.get("status"))
            print(f"[NEWS] NewsData.io body: {str(body)[:300]}")
            return []
        results = body.get("results", [])
        print(f"[NEWS] NewsData.io returned {len(results)} articles")
        return [
            {
                "title":  (a.get("title")     or "").strip(),
                "url":    (a.get("link")      or "").strip(),
                "source": (a.get("source_id") or "NewsData").strip(),
            }
            for a in results if (a.get("title") or "").strip()
        ][:8]
    except requests.exceptions.Timeout:
        logger.warning("[NEWS] NewsData.io timed out")
        print("[NEWS] NewsData.io timeout")
        return []
    except Exception as e:
        logger.warning("[NEWS] NewsData.io exception: %s", e)
        print(f"[NEWS] NewsData.io exception: {e}")
        return []


def _from_gnews(query: str) -> List[Dict]:
    if not GNEWS_API:
        print("[NEWS] GNEWS_API key not set — skipping GNews")
        return []
    try:
        url = "https://gnews.io/api/v4/search"
        params = {"q": query, "lang": "en", "max": 8, "apikey": GNEWS_API}
        print(f"[NEWS] GNews → GET {url} params={params}")
        r = requests.get(url, params=params, timeout=_TIMEOUT)
        print(f"[NEWS] GNews status={r.status_code}")
        if r.status_code == 403:
            logger.warning("[NEWS] GNews: Invalid API key or plan limit (403)")
            return []
        if r.status_code != 200:
            logger.warning("[NEWS] GNews returned %s: %s", r.status_code, r.text[:200])
            return []
        articles = r.json().get("articles", [])
        print(f"[NEWS] GNews returned {len(articles)} articles")
        return [
            {
                "title":  (a.get("title") or "").strip(),
                "url":    (a.get("url")   or "").strip(),
                "source": (a.get("source", {}).get("name") or "GNews").strip(),
            }
            for a in articles if (a.get("title") or "").strip()
        ]
    except requests.exceptions.Timeout:
        logger.warning("[NEWS] GNews timed out")
        return []
    except Exception as e:
        print(f"[NEWS] GNews exception: {e}")
        return []


def _from_newsapi(query: str) -> List[Dict]:
    if not NEWS_API_KEY:
        print("[NEWS] NEWS_API_KEY not set — skipping NewsAPI.org")
        return []
    try:
        url = "https://newsapi.org/v2/everything"
        params = {"q": query, "sortBy": "publishedAt", "pageSize": 8, "apiKey": NEWS_API_KEY}
        print(f"[NEWS] NewsAPI.org → GET {url} q={query!r}")
        r = requests.get(url, params=params, timeout=_TIMEOUT)
        print(f"[NEWS] NewsAPI.org status={r.status_code}")
        if r.status_code == 401:
            logger.warning("[NEWS] NewsAPI.org: Invalid API key (401)")
            return []
        if r.status_code != 200:
            logger.warning("[NEWS] NewsAPI.org returned %s: %s", r.status_code, r.text[:200])
            return []
        articles = r.json().get("articles", [])
        print(f"[NEWS] NewsAPI.org returned {len(articles)} articles")
        return [
            {
                "title":  (a.get("title") or "").strip(),
                "url":    (a.get("url")   or "").strip(),
                "source": (a.get("source", {}).get("name") or "NewsAPI").strip(),
            }
            for a in articles
            if (a.get("title") or "").strip() and "[Removed]" not in (a.get("title") or "")
        ]
    except requests.exceptions.Timeout:
        logger.warning("[NEWS] NewsAPI.org timed out")
        return []
    except Exception as e:
        print(f"[NEWS] NewsAPI.org exception: {e}")
        return []


def _build_query(user_message: str) -> str:
    """Build the best search query from the user's message."""
    msg = (user_message or "").lower().strip()
    # Strip generic noise words to get the real topic
    stop = {"news", "latest", "today", "breaking", "headlines",
            "current", "affairs", "updates", "recent", "top", "stories",
            "show", "give", "me", "the", "some", "get"}
    words = [w for w in msg.split() if w not in stop]
    topic = " ".join(words).strip()

    if not topic or topic in ("", "india"):
        return "india latest news today"
    if any(k in topic for k in ["education", "college", "university", "student"]):
        return f"{topic} india"
    return topic


def fetch_news(query: str = "india latest news") -> Tuple[List[Dict], str]:
    """
    Try: NewsData.io → GNews → NewsAPI.
    Returns (articles, provider_name).
    """
    search_q = _build_query(query)
    print(f"[NEWS] fetch_news: original={query!r} → search={search_q!r}")
    print(f"[NEWS] Keys available: ND={'yes' if _ND_KEY else 'NO'} "
          f"GNEWS={'yes' if GNEWS_API else 'NO'} "
          f"NEWSAPI={'yes' if NEWS_API_KEY else 'NO'}")

    for fn, name in [
        (_from_newsdata, "NEWSDATA"),
        (_from_gnews,    "GNEWS"),
        (_from_newsapi,  "NEWSAPI"),
    ]:
        articles = fn(search_q)
        if articles:
            print(f"[NEWS] SUCCESS via {name}: {len(articles)} articles")
            return articles, name

    print("[NEWS] All providers failed — no articles returned")
    return [], "NONE"


def summarize_news(articles: List[Dict], lang: str = "en") -> str:
    if not articles:
        if lang == "te":
            return (
                "📰 వార్తలు ఇప్పుడు అందుబాటులో లేవు.\n"
                "కొద్దిసేపటి తర్వాత మళ్లీ ప్రయత్నించండి."
            )
        return (
            "📰 No news articles available right now.\n"
            "Please check your news API key or try again later."
        )

    header = "📰 తాజా వార్తలు:\n" if lang == "te" else "📰 Latest News:\n"
    lines  = [header]
    for i, a in enumerate(articles[:5], 1):
        title = (a.get("title") or "").strip()
        if title:
            lines.append(f"{i}. {title}")
    return "\n".join(lines)
