"""
services/search_service.py

Web search: Tavily (primary) → Wikipedia → DuckDuckGo → AI fallback.
"""

import re
import requests
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

REQ_TIMEOUT = 10

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

QUESTION_PREFIXES = [
    "who is ", "who was ", "what is ", "what are ", "what was ",
    "tell me about ", "explain ", "define ", "meaning of ",
    "what do you know about ", "how does ", "how did ",
    "when did ", "where is ", "why is ", "why was ",
    "give me info on ", "information about ", "details about ",
]


def _headers():
    import random
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }


def _extract_entity(query: str) -> str:
    q = query.strip().lower()
    for prefix in QUESTION_PREFIXES:
        if q.startswith(prefix):
            q = query.strip()[len(prefix):].strip()
            break
    else:
        q = query.strip()
    return q.strip("?.! ")


def _clean_html(text: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = (text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                .replace("&quot;", '"').replace("&#039;", "'").replace("&nbsp;", " "))
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _trim_to_sentences(text: str, max_sentences: int = 6) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 8]
    return " ".join(sentences[:max_sentences])


def _tavily_search(query: str) -> List[Dict]:
    try:
        from services.tavily_service import search_web
        results = search_web(query, max_results=5)
        return results
    except Exception:
        return []


def _wikipedia_summary(query: str) -> Dict:
    entity = _extract_entity(query)
    if not entity:
        entity = query
    for attempt in [entity, entity.split()[0] if entity.split() else entity]:
        try:
            title = re.sub(r"[^a-zA-Z0-9 ]", "", attempt).strip().replace(" ", "_")
            if not title or len(title) < 2:
                continue
            r = requests.get(
                f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}",
                timeout=REQ_TIMEOUT,
                headers={"User-Agent": "IdealCollegeAI/1.0"}
            )
            if r.status_code != 200:
                continue
            d = r.json() or {}
            if d.get("type") == "disambiguation":
                continue
            extract = (d.get("extract") or "").strip()
            if extract and len(extract) > 40:
                return {
                    "title": d.get("title", attempt),
                    "snippet": extract,
                    "link": d.get("content_urls", {}).get("desktop", {}).get("page", "")
                }
        except Exception:
            continue
    return {}


def _ddg_instant_answer(query: str) -> Dict:
    try:
        r = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
            timeout=REQ_TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        if r.status_code != 200:
            return {}
        d = r.json() or {}
        abstract = (d.get("AbstractText") or "").strip()
        heading = (d.get("Heading") or "").strip()
        link = (d.get("AbstractURL") or "").strip()
        if abstract:
            return {"title": heading or query, "snippet": abstract, "link": link}
        for t in (d.get("RelatedTopics") or []):
            if isinstance(t, dict) and t.get("Text"):
                return {"title": heading or query, "snippet": t["Text"].strip(), "link": t.get("FirstURL", "")}
    except Exception:
        pass
    return {}


def search_and_format(query: str, lang: str = "en") -> str:
    # 1. Tavily
    tavily_results = _tavily_search(query)
    if tavily_results:
        snippets = [r.get("content", "").strip() for r in tavily_results[:5]
                    if r.get("content") and len(r["content"]) > 30]
        merged = " ".join(snippets)
        body = _trim_to_sentences(merged, 6)
        if body and len(body) > 60:
            first_title = tavily_results[0].get("title", query).strip()
            return f"🔎 {first_title}\n\n{body}"

    # 2. Wikipedia
    wiki = _wikipedia_summary(query)
    if wiki.get("snippet"):
        return f"📘 {wiki.get('title', '')}\n\n{_trim_to_sentences(wiki['snippet'], 6)}"

    # 3. DuckDuckGo
    ia = _ddg_instant_answer(query)
    if ia.get("snippet"):
        return f"🔎 {ia.get('title', '')}\n\n{_trim_to_sentences(ia['snippet'], 6)}"

    # 4. Return empty — router will try AI fallback
    return ""