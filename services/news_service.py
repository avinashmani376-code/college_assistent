
# services/news_service.py
"""
News service — NewsData.io ONLY.
No fallback providers.
Direct fetch, NO AI, NO Tavily.
 
On failure: logs status code + response body, returns failure message.
"""
import os
import sys
import logging
import requests
from typing import List, Dict, Tuple
 
logger = logging.getLogger(__name__)
 
# Read every possible env var name for NewsData key
_ND_KEY = (
    os.getenv("NEWSDATA_API",     "")   # matches .env file
    or os.getenv("NEWS_DATA_API", "")   # matches render.yaml
    or os.getenv("NEWSDATA_API_KEY", "")
)
 
print(f"[NEWS] Key status at startup: "
      f"NewsData={'SET' if _ND_KEY else 'MISSING'}",
      file=sys.stderr)
 
 
def _from_newsdata() -> List[Dict]:
    """
    NewsData.io FREE plan — /api/1/latest-news (no ?q= needed).
    Returns list of {title, url, source} dicts.
    On any failure: logs status + body, returns empty list.
    """
    if not _ND_KEY:
        print("[NEWS] NewsData key missing — cannot fetch news", file=sys.stderr)
        logger.error("NewsData API key not set")
        return []
 
    try:
        print("[NEWS] NewsData.io /latest-news fetching...", file=sys.stderr)
        r = requests.get(
            "https://newsdata.io/api/1/latest-news",
            params={
                "apikey":   _ND_KEY,
                "language": "en",
                "country":  "in",
            },
            timeout=12,
        )
        print(f"[NEWS] NewsData status={r.status_code}", file=sys.stderr)
 
        if r.status_code != 200:
            body = r.text[:500]
            print(f"[NEWS] NewsData FAILED — status={r.status_code} body={body}",
                  file=sys.stderr)
            logger.error("NewsData error: status=%s body=%s", r.status_code, body)
            return []
 
        results = r.json().get("results") or []
        print(f"[NEWS] NewsData returned {len(results)} articles", file=sys.stderr)
 
        articles = [
            {
                "title":  (a.get("title")     or "").strip(),
                "url":    (a.get("link")      or "").strip(),
                "source": (a.get("source_id") or "NewsData").strip(),
            }
            for a in results
            if (a.get("title") or "").strip()
        ][:8]
 
        print(f"[NEWS] Parsed {len(articles)} valid articles", file=sys.stderr)
        return articles
 
    except Exception as e:
        print(f"[NEWS] NewsData exception: {e}", file=sys.stderr)
        logger.error("NewsData exception: %s", e)
        return []
 
 
def fetch_news(user_message: str = "") -> Tuple[List[Dict], str]:
    """
    Fetch news from NewsData.io only.
    Returns (articles, provider_name).
    """
    print(f"[NEWS] fetch_news called: user_message={user_message!r}", file=sys.stderr)
    articles = _from_newsdata()
    if articles:
        print(f"[NEWS] SUCCESS: {len(articles)} articles from NEWSDATA", file=sys.stderr)
        return articles, "NEWSDATA"
    print("[NEWS] NewsData returned no articles", file=sys.stderr)
    return [], "NONE"
 
 
def summarize_news(articles: List[Dict], lang: str = "en") -> str:
    if not articles:
        if lang == "te":
            return "తాజా వార్తలు తీసుకోవడం సాధ్యం కాలేదు. దయచేసి కొద్దిసేపటి తర్వాత మళ్లీ ప్రయత్నించండి."
        return "Unable to fetch the latest news. Please try again later."
 
    header = "📰 తాజా వార్తలు:\n" if lang == "te" else "📰 Latest News:\n"
    lines  = [header]
    for i, a in enumerate(articles[:5], 1):
        title = (a.get("title") or "").strip()
        if title:
            lines.append(f"{i}. {title}")
    return "\n".join(lines)
 