"""
services/tavily_service.py
 
Tavily AI search — primary web search source.
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
 
 
def search_web(query: str, max_results: int = 5) -> List[Dict]:
    """
    Search the web using Tavily API.
    Returns list of {title, url, content, score} dicts.
    Returns empty list on any failure.
    """
    if not _TAVILY_AVAILABLE:
        logger.warning("Tavily package not available")
        return []
    if not TAVILY_API_KEY:
        logger.warning("TAVILY_API_KEY not set — skipping Tavily search")
        return []
 
    try:
        client = _TavilyClient(api_key=TAVILY_API_KEY)
        response = client.search(
            query=query,
            search_depth="basic",
            max_results=max_results,
            include_answer=True,
        )
        results = []
        for r in (response.get("results") or []):
            content = (r.get("content") or "").strip()
            if not content:
                continue
            results.append({
                "title":   (r.get("title") or "").strip(),
                "url":     (r.get("url") or "").strip(),
                "content": content[:800],
                "score":   r.get("score", 0),
            })
        return results
    except Exception as e:
        logger.warning("Tavily search failed: %s", e)
        return []
 
 
def format_search_context(results: List[Dict], query: str = "") -> str:
    """Convert Tavily results into a clean context string for AI summarization."""
    if not results:
        return ""
    lines = []
    for i, r in enumerate(results[:5], 1):
        title   = r.get("title", "").strip()
        content = r.get("content", "").strip()
        if content:
            lines.append(f"[{i}] {title}\n{content}")
    return "\n\n".join(lines)
 
 
def search_and_get_context(query: str, max_results: int = 5) -> Optional[str]:
    """
    Convenience: search Tavily and return formatted context string.
    Returns None if no results or any failure.
    """
    results = search_web(query, max_results=max_results)
    if not results:
        return None
    ctx = format_search_context(results, query=query)
    return ctx if ctx else None
 