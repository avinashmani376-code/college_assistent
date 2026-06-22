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
 
 
def _from_newsdata(query: str) -> List[Dict]:
    if not _ND_KEY:
        print("[NEWS] NEWS_DATA_API key not set — skipping NewsData.io")
        return []
    try:
        print(f"[NEWS] Calling NewsData.io with query={query!r}")
        r = requests.get(
            "https://newsdata.io/api/1/news",
            params={"q": query, "language": "en", "apikey": _ND_KEY},
            timeout=12,
        )
        print(f"[NEWS] NewsData.io status={r.status_code}")
        if r.status_code != 200:
            logger.warning("NewsData returned %s: %s", r.status_code, r.text[:200])
            return []
        results = r.json().get("results", [])
        print(f"[NEWS] NewsData.io returned {len(results)} articles")
        return [
            {
                "title":  (a.get("title")     or "").strip(),
                "url":    (a.get("link")      or "").strip(),
                "source": (a.get("source_id") or "NewsData").strip(),
            }
            for a in results if a.get("title")
        ][:8]
    except Exception as e:
        logger.warning("NewsData exception: %s", e)
        print(f"[NEWS] NewsData exception: {e}")
        return []
 
 
def _from_gnews(query: str) -> List[Dict]:
    if not GNEWS_API:
        return []
    try:
        print(f"[NEWS] Calling GNews with query={query!r}")
        r = requests.get(
            "https://gnews.io/api/v4/search",
            params={"q": query, "lang": "en", "max": 8, "apikey": GNEWS_API},
            timeout=12,
        )
        print(f"[NEWS] GNews status={r.status_code}")
        if r.status_code != 200:
            return []
        articles = r.json().get("articles", [])
        print(f"[NEWS] GNews returned {len(articles)} articles")
        return [
            {
                "title":  (a.get("title") or "").strip(),
                "url":    (a.get("url")   or "").strip(),
                "source": (a.get("source", {}).get("name") or "GNews").strip(),
            }
            for a in articles if a.get("title")
        ]
    except Exception as e:
        print(f"[NEWS] GNews exception: {e}")
        return []
 
 
def _from_newsapi(query: str) -> List[Dict]:
    if not NEWS_API_KEY:
        return []
    try:
        print(f"[NEWS] Calling NewsAPI.org with query={query!r}")
        r = requests.get(
            "https://newsapi.org/v2/everything",
            params={"q": query, "sortBy": "publishedAt",
                    "pageSize": 8, "apiKey": NEWS_API_KEY},
            timeout=12,
        )
        print(f"[NEWS] NewsAPI status={r.status_code}")
        if r.status_code != 200:
            return []
        articles = r.json().get("articles", [])
        print(f"[NEWS] NewsAPI returned {len(articles)} articles")
        return [
            {
                "title":  (a.get("title") or "").strip(),
                "url":    (a.get("url")   or "").strip(),
                "source": (a.get("source", {}).get("name") or "NewsAPI").strip(),
            }
            for a in articles
            if a.get("title") and "[Removed]" not in (a.get("title") or "")
        ]
    except Exception as e:
        print(f"[NEWS] NewsAPI exception: {e}")
        return []
 
 
def _build_query(user_message: str) -> str:
    """Build the best search query from the user's message."""
    msg = (user_message or "").lower().strip()
    # Strip generic news words to get the real topic
    stop = {"news", "latest", "today", "breaking", "headlines",
            "current", "affairs", "updates", "recent", "top", "stories"}
    words = [w for w in msg.split() if w not in stop]
    topic = " ".join(words).strip()
 
    if not topic or topic in ("", "india"):
        return "india latest news"
    if any(k in topic for k in ["education", "college", "university", "student"]):
        return f"{topic} india"
    return topic or "india latest news"
 
 
def fetch_news(query: str = "india latest news") -> Tuple[List[Dict], str]:
    """
    Try: NewsData.io → GNews → NewsAPI.
    Returns (articles, provider_name).
    """
    search_q = _build_query(query)
    print(f"[NEWS] fetch_news: original={query!r} → search={search_q!r}")
 
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
            return "వార్తలు ఇప్పుడు అందుబాటులో లేవు. కొద్దిసేపటి తర్వాత మళ్లీ ప్రయత్నించండి."
        return "No news available right now. Please try again later."
 
    header = "📰 తాజా వార్తలు:\n" if lang == "te" else "📰 Latest News:\n"
    lines  = [header]
    for i, a in enumerate(articles[:5], 1):
        title = (a.get("title") or "").strip()
        if title:
            lines.append(f"{i}. {title}")
    return "\n".join(lines)
 