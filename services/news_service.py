 services/news_service.py
"""
News service — GNews API ONLY.
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
 
# Read from GNEWS_API_KEY (primary) or legacy GNEWS_API name
_GNEWS_KEY = (
    os.getenv("GNEWS_API_KEY", "")  # primary key name per requirements
    or os.getenv("GNEWS_API",   "")  # legacy name kept in config.py
)
 
print(f"[NEWS] Key status at startup: "
      f"GNews={'SET' if _GNEWS_KEY else 'MISSING'}",
      file=sys.stderr)
 
 
def _from_gnews() -> List[Dict]:
    """
    GNews top headlines for India — free plan compatible.
    Returns list of {title, description, source, url} dicts (max 5).
    On any failure: logs status code + response body, returns empty list.
    """
    if not _GNEWS_KEY:
        print("[NEWS] GNews key missing — cannot fetch news", file=sys.stderr)
        logger.error("GNews API key not set (GNEWS_API_KEY)")
        return []
 
    try:
        print("[NEWS] GNews /top-headlines fetching...", file=sys.stderr)
        r = requests.get(
            "https://gnews.io/api/v4/top-headlines",
            params={
                "token":   _GNEWS_KEY,
                "lang":    "en",
                "country": "in",
                "max":     10,          # fetch 10, return best 5 after filtering
                "topic":   "breaking-news",
            },
            timeout=12,
        )
        print(f"[NEWS] GNews status={r.status_code}", file=sys.stderr)
 
        if r.status_code != 200:
            body = r.text[:500]
            print(f"[NEWS] GNews FAILED — status={r.status_code} body={body}",
                  file=sys.stderr)
            logger.error("GNews error: status=%s body=%s", r.status_code, body)
            return []
 
        raw = r.json().get("articles") or []
        print(f"[NEWS] GNews returned {len(raw)} articles", file=sys.stderr)
 
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
    Fetch news from GNews only.
    Returns (articles, provider_name).
    """
    print(f"[NEWS] fetch_news called: user_message={user_message!r}", file=sys.stderr)
    articles = _from_gnews()
    if articles:
        print(f"[NEWS] SUCCESS: {len(articles)} articles from GNEWS", file=sys.stderr)
        return articles, "GNEWS"
    print("[NEWS] GNews returned no articles", file=sys.stderr)
    return [], "NONE"
 
 
def summarize_news(articles: List[Dict], lang: str = "en") -> str:
    """
    Format articles as:
      📰 Headline
      Short description (1-2 lines)
      Source | Link
    """
    if not articles:
        if lang == "te":
            return "తాజా వార్తలు తీసుకోవడం సాధ్యం కాలేదు. దయచేసి కొద్దిసేపటి తర్వాత మళ్లీ ప్రయత్నించండి."
        return "Unable to fetch the latest news."
 
    header = "📰 తాజా వార్తలు\n" if lang == "te" else "📰 Latest News\n"
    lines  = [header]
 
    for a in articles:
        title       = (a.get("title")       or "").strip()
        description = (a.get("description") or "").strip()
        source      = (a.get("source")      or "").strip()
        url         = (a.get("url")         or "").strip()
 
        if not title:
            continue
 
        # Headline
        lines.append(f"• {title}")
 
        # Description — trim to 2 sentences max
        if description:
            sentences = description.split(". ")
            short_desc = ". ".join(sentences[:2]).strip()
            if short_desc and not short_desc.endswith("."):
                short_desc += "."
            lines.append(f"  {short_desc}")
 
        # Source + link
        meta_parts = []
        if source:
            meta_parts.append(source)
        if url:
            meta_parts.append(url)
        if meta_parts:
            lines.append(f"  🔗 {' — '.join(meta_parts)}")
 
        lines.append("")   # blank line between articles
 
    return "\n".join(lines).rstrip()
 