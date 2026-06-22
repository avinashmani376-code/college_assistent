"""
News service — fetches from NewsData.io (primary), GNews, NewsAPI (fallbacks).
Direct fetch and format — NO AI, NO Tavily involvement.
"""
import os
import logging
import requests
from typing import List, Dict, Tuple
 
logger = logging.getLogger(__name__)
 
NEWS_DATA_API = os.getenv("NEWS_DATA_API", "")
GNEWS_API     = os.getenv("GNEWS_API", "")
NEWS_API_KEY  = os.getenv("NEWS_API_KEY", "")
 
 
def _from_newsdata(query: str) -> List[Dict]:
    """NewsData.io — primary source (NEWS_DATA_API key)."""
    if not NEWS_DATA_API:
        return []
    try:
        r = requests.get(
            "https://newsdata.io/api/1/news",
            params={"q": query, "language": "en", "apikey": NEWS_DATA_API},
            timeout=12,
        )
        if r.status_code != 200:
            logger.warning("NewsData returned %s", r.status_code)
            return []
        return [
            {
                "title":  (a.get("title")     or "").strip(),
                "url":    (a.get("link")      or "").strip(),
                "source": (a.get("source_id") or "NewsData").strip(),
            }
            for a in r.json().get("results", [])
            if a.get("title")
        ][:8]
    except Exception as e:
        logger.warning("NewsData exception: %s", e)
        return []
 
 
def _from_gnews(query: str) -> List[Dict]:
    """GNews — first fallback."""
    if not GNEWS_API:
        return []
    try:
        r = requests.get(
            "https://gnews.io/api/v4/search",
            params={"q": query, "lang": "en", "max": 8, "apikey": GNEWS_API},
            timeout=12,
        )
        if r.status_code != 200:
            return []
        return [
            {
                "title":  (a.get("title") or "").strip(),
                "url":    (a.get("url")   or "").strip(),
                "source": (a.get("source", {}).get("name") or "GNews").strip(),
            }
            for a in r.json().get("articles", [])
            if a.get("title")
        ]
    except Exception as e:
        logger.warning("GNews exception: %s", e)
        return []
 
 
def _from_newsapi(query: str) -> List[Dict]:
    """NewsAPI.org — second fallback."""
    if not NEWS_API_KEY:
        return []
    try:
        r = requests.get(
            "https://newsapi.org/v2/everything",
            params={"q": query, "sortBy": "publishedAt", "pageSize": 8, "apiKey": NEWS_API_KEY},
            timeout=12,
        )
        if r.status_code != 200:
            return []
        return [
            {
                "title":  (a.get("title") or "").strip(),
                "url":    (a.get("url")   or "").strip(),
                "source": (a.get("source", {}).get("name") or "NewsAPI").strip(),
            }
            for a in r.json().get("articles", [])
            if a.get("title") and "[Removed]" not in (a.get("title") or "")
        ]
    except Exception as e:
        logger.warning("NewsAPI exception: %s", e)
        return []
 
 
def fetch_news(query: str = "latest india news today") -> Tuple[List[Dict], str]:
    """
    Try providers in order: NewsData → GNews → NewsAPI.
    Returns (articles, provider_name).
    """
    q = (query or "").strip() or "latest india news today"
    # Narrow query for local/education topics
    if any(k in q.lower() for k in ["kakinada", "andhra", "telugu", "vizag"]):
        search_q = q
    elif any(k in q.lower() for k in ["education", "college", "university", "student"]):
        search_q = f"{q} india"
    else:
        search_q = q
 
    for fn, name in [
        (_from_newsdata, "NEWSDATA"),
        (_from_gnews,    "GNEWS"),
        (_from_newsapi,  "NEWSAPI"),
    ]:
        articles = fn(search_q)
        if articles:
            return articles, name
 
    return [], "NONE"
 
 
def summarize_news(articles: List[Dict], lang: str = "en") -> str:
    """Format articles as a numbered list — no AI needed."""
    if not articles:
        if lang == "te":
            return "వార్తలు ఇప్పుడు అందుబాటులో లేవు. కొద్దిసేపటి తర్వాత మళ్లీ ప్రయత్నించండి."
        return "No news available right now. Please try again later."
 
    header = "📰 తాజా అప్‌డేట్స్:\n" if lang == "te" else "📰 Latest News:\n"
    lines  = [header]
    for i, a in enumerate(articles[:5], 1):
        title = a.get("title", "").strip()
        if title:
            lines.append(f"{i}. {title}")
    return "\n".join(lines)