"""
services/tavily_service.py

Tavily AI search — used ONLY for current/recent information.
NOT used for stable knowledge (definitions, well-known people, concepts).
Falls back gracefully when API key is missing or package not installed.
"""

import os
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# Safe import — deployment won't crash even if package is missing
try:
    from tavily import TavilyClient as _TavilyClient
    _TAVILY_AVAILABLE = True
except ImportError:
    _TAVILY_AVAILABLE = False
    logger.warning("tavily-python package not installed. Tavily search disabled.")


def search_web(query: str, max_results: int = 3) -> List[Dict]:
    """
    Search the web using Tavily API.
    Returns list of {title, url, content, score} dicts.
    Returns empty list on any failure.

    max_results default is 3 (reduced from 5) to keep responses fast and focused.
    """
    if not _TAVILY_AVAILABLE:
        logger.warning("[TAVILY] Package not available")
        return []
    if not TAVILY_API_KEY:
        logger.warning("[TAVILY] TAVILY_API_KEY not set — skipping Tavily search")
        return []

    try:
        print(f"[TAVILY] Searching: {query!r} max_results={max_results}")
        client = _TavilyClient(api_key=TAVILY_API_KEY)
        response = client.search(
            query=query,
            search_depth="basic",
            max_results=max_results,
            include_answer=False,  # skip Tavily's own AI answer; we use Groq
        )
        results = []
        for r in (response.get("results") or []):
            content = (r.get("content") or "").strip()
            if not content:
                continue
            results.append({
                "title":   (r.get("title") or "").strip(),
                "url":     (r.get("url") or "").strip(),
                "content": content[:500],   # cap at 500 chars per result
                "score":   r.get("score", 0),
            })
        print(f"[TAVILY] Got {len(results)} results")
        return results
    except Exception as e:
        logger.warning("[TAVILY] Search failed: %s", e)
        print(f"[TAVILY] Exception: {e}")
        return []


def format_search_context(results: List[Dict], query: str = "") -> str:
    """Convert Tavily results into a clean context string for AI summarization."""
    if not results:
        return ""
    lines = []
    for i, r in enumerate(results[:3], 1):
        title   = r.get("title", "").strip()
        content = r.get("content", "").strip()
        if content:
            lines.append(f"[{i}] {title}\n{content}")
    return "\n\n".join(lines)


def search_and_get_context(query: str, max_results: int = 3) -> Optional[str]:
    """
    Convenience: search Tavily and return formatted context string.
    Returns None if no results or any failure.
    """
    results = search_web(query, max_results=max_results)
    if not results:
        return None
    ctx = format_search_context(results, query=query)
    return ctx if ctx else None
