# services/news_service.py
import os
import requests
from typing import List, Dict, Tuple

GNEWS_API = os.getenv("GNEWS_API", "")
NEWS_DATA_API = os.getenv("NEWS_DATA_API", "")
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")


def _from_gnews(query: str) -> List[Dict]:
    if not GNEWS_API: return []
    try:
        r = requests.get("https://gnews.io/api/v4/search",
            params={"q": query, "lang": "en", "max": 8, "apikey": GNEWS_API}, timeout=12)
        if r.status_code != 200: return []
        return [{"title": a.get("title", ""), "url": a.get("url", ""),
                 "source": a.get("source", {}).get("name", "GNews")}
                for a in r.json().get("articles", []) if a.get("title")]
    except Exception:
        return []


def _from_newsdata(query: str) -> List[Dict]:
    if not NEWS_DATA_API: return []
    try:
        r = requests.get("https://newsdata.io/api/1/news",
            params={"q": query, "language": "en", "apikey": NEWS_DATA_API}, timeout=12)
        if r.status_code != 200: return []
        return [{"title": a.get("title", ""), "url": a.get("link", ""),
                 "source": a.get("source_id", "NewsData")}
                for a in r.json().get("results", []) if a.get("title")][:8]
    except Exception:
        return []


def _from_newsapi(query: str) -> List[Dict]:
    if not NEWS_API_KEY: return []
    try:
        r = requests.get("https://newsapi.org/v2/everything",
            params={"q": query, "sortBy": "publishedAt", "pageSize": 8, "apiKey": NEWS_API_KEY}, timeout=12)
        if r.status_code != 200: return []
        return [{"title": a.get("title", ""), "url": a.get("url", ""),
                 "source": a.get("source", {}).get("name", "NewsAPI")}
                for a in r.json().get("articles", [])
                if a.get("title") and "[Removed]" not in a.get("title", "")]
    except Exception:
        return []


def fetch_news(query: str = "latest india news today") -> Tuple[List[Dict], str]:
    q = (query or "").strip() or "latest india news today"
    if any(k in q.lower() for k in ["kakinada", "andhra", "telugu", "vizag"]):
        search_q = q
    elif any(k in q.lower() for k in ["education", "college", "university", "school", "student"]):
        search_q = f"{q} india education students"
    else:
        search_q = q
    for fn, name in [(_from_gnews, "GNEWS"), (_from_newsdata, "NEWSDATA"), (_from_newsapi, "NEWSAPI")]:
        data = fn(search_q)
        if data:
            return data, name
    return [], "NONE"


def summarize_news(articles: List[Dict], lang: str = "en") -> str:
    if not articles:
        return "వార్తలు అందుబాటులో లేవు." if lang == "te" else "No news available right now. Please try again."
    lines = ["📰 తాజా అప్‌డేట్స్:\n"] if lang == "te" else ["📰 Latest News:\n"]
    for i, a in enumerate(articles[:5], 1):
        title = a.get("title", "").strip()
        if title:
            lines.append(f"{i}. {title}")
    return "\n".join(lines)