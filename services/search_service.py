# services/search_service.py
"""
Concise, accurate web search.
Sources (in priority order):
  1. Google search (HTML scrape with realistic browser headers)
  2. Wikipedia REST summary
  3. DuckDuckGo Instant Answer
  4. DuckDuckGo HTML (last-resort fallback)
"""

import re
import random
import requests
from typing import List, Dict
from urllib.parse import quote_plus, urlparse, parse_qs, unquote

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]
REQ_TIMEOUT = 10


def _headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": "https://www.google.com/",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
    }


def _clean_html(text: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = (text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                 .replace("&quot;", '"').replace("&#039;", "'").replace("&nbsp;", " "))
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    text = re.sub(r"&#\d+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _trim_to_lines(text: str, max_sentences: int = 6) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 8]
    return " ".join(sentences[:max_sentences])


def _decode_google_url(url: str) -> str:
    if not url: return ""
    if url.startswith("/url?"):
        try:
            q = parse_qs(urlparse(url).query)
            if "q" in q: return unquote(q["q"][0])
        except Exception:
            pass
    return url


def search_google(query: str) -> List[Dict[str, str]]:
    if not query: return []
    url = f"https://www.google.com/search?q={quote_plus(query)}&hl=en&gl=in&num=10&pws=0"
    try:
        r = requests.get(url, headers=_headers(), timeout=REQ_TIMEOUT)
        if r.status_code != 200: return []
        html = r.text
        results: List[Dict[str, str]] = []
        blocks = re.findall(
            r'<a[^>]+href="(/url\?q=[^"]+|https?://[^"]+)"[^>]*>.*?<h3[^>]*>(.*?)</h3>(.*?)(?=<a[^>]+href="(?:/url\?q=|https?://)|$)',
            html, flags=re.DOTALL | re.IGNORECASE,
        )
        for raw_link, title_html, tail in blocks[:12]:
            title = _clean_html(title_html)
            if not title or len(title) < 4: continue
            link = _decode_google_url(raw_link)
            if "google.com" in link or "webcache.googleusercontent" in link: continue
            snippet = ""
            sm = re.search(r'<(?:span|div)[^>]*>([^<]{40,400})</(?:span|div)>', tail, flags=re.IGNORECASE)
            if sm: snippet = _clean_html(sm.group(1))
            results.append({"title": title, "snippet": snippet, "link": link})
        if not results:
            for m in re.finditer(r'<h3[^>]*>(.*?)</h3>', html, re.DOTALL):
                t = _clean_html(m.group(1))
                if t and len(t) > 4:
                    results.append({"title": t, "snippet": "", "link": ""})
        if results:
            ab = re.search(r'<div[^>]+class="[^"]*(?:hgKElc|kno-rdesc|wDYxhc)[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
            if ab:
                ans = _clean_html(ab.group(1))
                if ans and len(ans) > 60:
                    results.insert(0, {"title": "Answer", "snippet": ans, "link": ""})
        return results
    except Exception:
        return []


def _wikipedia_summary(query: str) -> Dict[str, str]:
    try:
        title = re.sub(r"[^a-zA-Z0-9 ]", "", query).strip().replace(" ", "_")
        if not title: return {}
        r = requests.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}",
                         timeout=REQ_TIMEOUT, headers={"User-Agent": "IdealCollegeAI/1.0"})
        if r.status_code != 200: return {}
        d = r.json() or {}
        extract = (d.get("extract") or "").strip()
        if extract and len(extract) > 30:
            return {"title": d.get("title", query), "snippet": extract,
                    "link": d.get("content_urls", {}).get("desktop", {}).get("page", "")}
    except Exception:
        pass
    return {}


def _ddg_instant_answer(query: str) -> Dict[str, str]:
    try:
        r = requests.get("https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
            timeout=REQ_TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200: return {}
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


def search_duckduckgo(query: str) -> List[Dict[str, str]]:
    if not query: return []
    try:
        resp = requests.post("https://html.duckduckgo.com/html/",
            headers=_headers(), data={"q": query, "kl": "in-en"}, timeout=REQ_TIMEOUT)
        if resp.status_code != 200: return []
        html = resp.text
        results: List[Dict[str, str]] = []
        title_matches = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL)
        snippet_matches = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL)
        for i, t in enumerate(title_matches[:5]):
            title = _clean_html(t)
            snippet = _clean_html(snippet_matches[i]) if i < len(snippet_matches) else ""
            if title and len(title) > 3:
                results.append({"title": title, "snippet": snippet, "link": ""})
        return results
    except Exception:
        return []


def search_and_format(query: str, lang: str = "en") -> str:
    google_results = search_google(query)
    if google_results and google_results[0].get("title") == "Answer":
        body = _trim_to_lines(google_results[0]["snippet"], 6)
        if body: return f"🔎 {query.strip().title()}\n\n{body}"
    if google_results:
        snippets = [r.get("snippet", "").strip() for r in google_results[:5]
                    if r.get("snippet") and len(r["snippet"]) > 30]
        merged = " ".join(snippets)
        body = _trim_to_lines(merged, 6)
        if body and len(body) > 60:
            return f"🔎 {google_results[0].get('title', query).strip()}\n\n{body}"
        bullets = [f"• {r['title'].strip()}" for r in google_results[:4] if r.get("title")]
        if bullets: return "\n".join(bullets[:5])

    wiki = _wikipedia_summary(query)
    if wiki.get("snippet"):
        return f"📘 {wiki.get('title','')}\n\n{_trim_to_lines(wiki['snippet'], 6)}"

    ia = _ddg_instant_answer(query)
    if ia.get("snippet"):
        return f"🔎 {ia.get('title','')}\n\n{_trim_to_lines(ia['snippet'], 6)}"

    ddg = search_duckduckgo(query)
    if ddg:
        lines = []
        for r in ddg[:4]:
            title = (r.get("title") or "").strip()
            snippet = _trim_to_lines((r.get("snippet") or "").strip(), 1)
            if title and snippet: lines.append(f"• {title} — {snippet}")
            elif title: lines.append(f"• {title}")
        if lines: return "\n".join(lines[:5])

    return ("సంబంధిత సమాచారం దొరకలేదు. దయచేసి మరోసారి అడగండి."
            if lang == "te"
            else "Sorry, I couldn't find a clean answer for that. Please rephrase your question.")