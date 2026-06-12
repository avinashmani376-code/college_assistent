"""
services/tavily_service.py

Tavily AI search — primary web search source.
Falls back gracefully when API key is missing or request fails.
"""

import os
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")


def search_web(query: str, max_results: int = 5) -> List[Dict]:
    """
    Search the web using Tavily API.
    Returns list of {title, url, content, score} dicts.
    Returns empty list on failure.
    """
    if not TAVILY_API_KEY:
        logger.warning("TAVILY_API_KEY not set — skipping Tavily search")
        return []

    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=TAVILY_API_KEY)
        response = client.search(
            query=query,
            search_depth="basic",
            max_results=max_results,
            include_answer=True,
        )
        results = []
        for r in (response.get("results") or []):
            results.append({
                "title":   (r.get("title") or "").strip(),
                "url":     (r.get("url") or "").strip(),
                "content": (r.get("content") or "").strip()[:800],
                "score":   r.get("score", 0),
            })
        return results
    except Exception as e:
        logger.warning("Tavily search failed: %s", e)
        return []


def format_search_context(results: List[Dict], query: str = "") -> str:
    """
    Convert Tavily results into a clean context string for AI summarization.
    """
    if not results:
        return ""

    lines = []
    for i, r in enumerate(results[:5], 1):
        title = r.get("title", "").strip()
        content = r.get("content", "").strip()
        if content:
            lines.append(f"[{i}] {title}\n{content}")

    return "\n\n".join(lines)


def search_and_get_context(query: str, max_results: int = 5) -> Optional[str]:
    """
    Convenience function: search Tavily and return formatted context string.
    Returns None if no results found.
    """
    results = search_web(query, max_results=max_results)
    if not results:
        return None
    return format_search_context(results, query=query)
