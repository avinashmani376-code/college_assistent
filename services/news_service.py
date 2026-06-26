# services/news_service.py
"""
News service — GNews API ONLY.
No fallback providers. No AI. No Tavily.
 
Case 1: Generic request ("Latest news", "Breaking news")
  → GNews /top-headlines  (India, breaking-news)
  → Returns up to 5 mixed top headlines
 
Case 2: Specific topic ("Latest news about Elon Musk", "Cricket news")
  → GNews /search with the extracted topic as query
  → Returns ONLY articles relevant to that topic
  → Word-by-word fallback if exact phrase returns zero results
  → "No recent news found for '<Topic>'." if still nothing
 
Empty article list from router.py reaches summarize_news():
  → sentinel article carries the exact user-facing message
  → summarize_news detects sentinel and returns it directly
  → router.py requires NO changes
 
Error messages:
  Network failure / timeout  → "Unable to fetch the latest news."
  Invalid API key            → "News service: Invalid API key."
  Rate limit                 → "News service: API rate limit reached."
  Topic not found            → "No recent news found for '<Topic>'."
"""
import os
import re
import sys
import json
import logging
import requests
from typing import List, Dict, Optional, Tuple
 
logger = logging.getLogger(__name__)
 
# ── API key — accepts both naming conventions ─────────────────────────────
_GNEWS_KEY = (
    os.getenv("GNEWS_API_KEY", "")
    or os.getenv("GNEWS_API",     "")
)
 
print(
    f"[NEWS] GNews key: {'SET (len=' + str(len(_GNEWS_KEY)) + ')' if _GNEWS_KEY else 'MISSING'}",
    file=sys.stderr,
)
 
# ── Sentinel key — signals a pre-built message to summarize_news ──────────
_SENTINEL = "_sentinel"
 
# ── Noise words stripped when extracting a search topic ───────────────────
_NOISE_WORDS = {
    "latest", "today", "today's", "todays", "news", "about", "on",
    "tell", "me", "show", "give", "current", "recent", "new",
    "breaking", "headlines", "headline", "update", "updates",
    "what", "is", "are", "the", "a", "an", "in", "of", "for",
    "whats",
}
 
# ── Phrases that mean "give me general headlines" ─────────────────────────
_GENERIC_PHRASES = {
    "latest news", "today's news", "todays news", "today news",
    "breaking news", "top news", "top headlines", "news today",
    "current news", "recent news", "news", "latest news today",
    "headlines", "latest updates",
}
 
# ── Maps topic keywords → GNews /top-headlines topic param ────────────────
_TOPIC_MAP = {
    "technology":  "technology",
    "tech":        "technology",
    "education":   "education",
    "sports":      "sports",
    "sport":       "sports",
    "business":    "business",
    "finance":     "business",
    "world":       "world",
    "india":       "nation",
    "national":    "nation",
    "health":      "health",
    "science":     "science",
    "entertainment": "entertainment",
}
 
# ── "Why it matters" one-liners ───────────────────────────────────────────
_WHY_MATTERS = {
    "technology":    "It affects how we use technology in our daily lives.",
    "tech":          "It affects how we use technology in our daily lives.",
    "ai":            "AI is rapidly changing how people work and learn.",
    "education":     "It directly impacts students and schools across India.",
    "sports":        "It is important for Indian sports fans.",
    "sport":         "It is important for Indian sports fans.",
    "cricket":       "It matters to millions of cricket fans across India.",
    "ipl":           "IPL is India's biggest cricket event followed by millions.",
    "business":      "It affects jobs, prices, and the Indian economy.",
    "finance":       "It affects jobs, prices, and the Indian economy.",
    "health":        "It affects the health and well-being of people.",
    "science":       "It helps us understand the world and improve our lives.",
    "space":         "It shows India's growing strength in science and space.",
    "politics":      "It shapes how India is governed.",
    "election":      "It decides who will lead and make decisions for India.",
    "environment":   "It affects the air, water, and nature around us.",
    "climate":       "It affects weather, farming, and life on Earth.",
    "economy":       "It impacts the cost of living and job opportunities.",
    "petrol":        "Fuel prices affect transportation costs and daily life.",
    "bitcoin":       "Cryptocurrency affects global financial markets.",
    "tesla":         "Tesla influences the global electric vehicle industry.",
    "elon musk":     "Elon Musk's decisions impact technology and global markets.",
    "default":       "It is an important development that affects many people.",
}
 
# ── Error message strings ─────────────────────────────────────────────────
_ERR_NO_KEY       = "News service: API key not configured."
_ERR_INVALID_KEY  = "News service: Invalid API key. Please check GNEWS_API_KEY."
_ERR_RATE_LIMIT   = "News service: API rate limit reached. Please try again later."
_ERR_API_FAILURE  = "Unable to fetch the latest news."
_ERR_PARSE        = "Unable to fetch the latest news."
 
 
# ── Topic synonym map for relevance filtering ─────────────────────────────
# For each topic key, articles MUST contain at least one of these terms
# (checked against title + description, lowercased).
# Topics not listed here fall back to the topic words themselves.
_TOPIC_SYNONYMS: Dict[str, List[str]] = {
    # People
    "elon musk":      ["elon", "musk", "elon musk"],
    "modi":           ["modi", "narendra modi", "pm modi", "prime minister modi"],
    # Energy / fuel
    "petrol":         ["petrol", "fuel", "gasoline", "crude oil", "crude",
                       "diesel", "pump price", "oil price", "fuel price", "lpg"],
    "petrol price":   ["petrol", "fuel", "diesel", "crude", "oil price",
                       "pump price", "fuel price"],
    # Technology / AI
    "ai":             ["artificial intelligence", " ai ", "machine learning",
                       "llm", "openai", "chatgpt", "gemini", "deep learning",
                       "neural network", "generative ai", "large language",
                       "gpt", "claude", "mistral", "copilot"],
    "technology":     ["technology", "tech", "software", "hardware", "startup",
                       "silicon valley", "google", "apple", "microsoft",
                       "amazon", "meta", "chip", "semiconductor", "app"],
    # Companies / products
    "tesla":          ["tesla", "electric vehicle", " ev ", "elon musk",
                       "model s", "model 3", "model y", "cybertruck", "autopilot"],
    # Crypto / finance
    "bitcoin":        ["bitcoin", "btc", "cryptocurrency", "crypto", "blockchain",
                       "ethereum", "digital currency", "altcoin", "defi", "web3"],
    "stock market":   ["stock", "shares", "sensex", "nifty", "bse", "nse",
                       "market cap", "ipo", "equity", "bull run", "bear market",
                       "stock market", "dalal street"],
    "gold price":     ["gold", "silver", "bullion", "mcx gold", "gold rate",
                       "precious metal"],
    "rupee":          ["rupee", "inr", "currency", "forex", "exchange rate",
                       "dollar rupee", "usd inr"],
    # Sports
    "cricket":        ["cricket", "ipl", "bcci", "test match", "odi", "wicket",
                       "batsman", "bowler", "t20", "world cup", "rohit sharma",
                       "virat kohli", "dhoni", "innings", "run chase"],
    "ipl":            ["ipl", "indian premier league", "cricket", "t20", "bcci",
                       "auction", "team india", "wicket", "six", "century"],
    "football":       ["football", "fifa", "premier league", "champions league",
                       "bundesliga", "la liga", "ronaldo", "messi", "world cup",
                       "goalscorer", "transfer"],
    "sports":         ["sport", "sports", "cricket", "football", "ipl",
                       "olympic", "athlete", "championship", "tournament",
                       "player", "match result", "medal", "gold medal"],
    # Countries / regions
    "india":          ["india", "indian", "modi", "delhi", "mumbai", "rupee",
                       "bjp", "congress", "supreme court", "parliament",
                       "lok sabha", "rajya sabha", "new delhi"],
    "andhra pradesh": ["andhra", "andhra pradesh", " ap ", "vizag",
                       "vijayawada", "amaravati", "chandrababu", "telugu desam",
                       "ycp", "jagan", "kakinada", "guntur"],
    "pakistan":       ["pakistan", "pakistani", "islamabad", "karachi", "lahore",
                       "imran khan", "pti"],
    "china":          ["china", "chinese", "beijing", "shanghai", "xi jinping",
                       "ccp", "taiwan", "hong kong"],
    "ukraine":        ["ukraine", "ukrainian", "kyiv", "zelensky", "russia",
                       "war", "nato", "ceasefire"],
    # Science / space
    "space":          ["space", "nasa", "isro", "rocket", "satellite", "moon",
                       "mars", "orbit", "spacecraft", "astronaut", "launch",
                       "gaganyaan", "chandrayaan", "aditya"],
    "isro":           ["isro", "indian space", "gaganyaan", "chandrayaan",
                       "aditya", "launch vehicle", "sriharikota", "rocket"],
    # Economy
    "economy":        ["economy", "gdp", "inflation", "recession", "rbi",
                       "interest rate", "sensex", "nifty", "budget", "fiscal",
                       "economic growth", "unemployment"],
    "inflation":      ["inflation", "price rise", "cpi", "wpi", "rbi",
                       "interest rate", "repo rate", "cost of living"],
    "jobs":           ["jobs", "employment", "unemployment", "hiring",
                       "layoff", "salary", "career", "workforce"],
    # Health
    "health":         ["health", "medical", "hospital", "disease", "vaccine",
                       "covid", "cancer", "treatment", "doctor", "medicine",
                       "patient", "clinical", "pharma", "drug"],
    # Education
    "education":      ["education", "school", "college", "university", "student",
                       "exam", "syllabus", "teacher", "cbse", "neet", "jee",
                       "board exam", "result", "admission"],
    # Politics
    "politics":       ["politics", "election", "vote", "parliament", "minister",
                       "government", "political party", "campaign", "poll",
                       "lok sabha", "bjp", "congress", "aap"],
    # Environment
    "climate":        ["climate", "global warming", "carbon", "emission",
                       "renewable", "solar energy", "wind energy",
                       "environment", "pollution", "greenhouse", "net zero"],
    # Business
    "business":       ["business", "company", "startup", "profit", "revenue",
                       "merger", "acquisition", "ipo", "stock market", "shares",
                       "ceo", "founder", "valuation"],
    # Finance
    "finance":        ["finance", "bank", "loan", "interest", "rbi",
                       "income tax", "gst", "budget", "investment", "mutual fund"],
}
 
 
 
def _get_filter_terms(topic: str) -> List[str]:
    """
    Return the list of terms that qualify an article as relevant for topic.
    1. Exact match in _TOPIC_SYNONYMS.
    2. Partial match (topic is substring of a key or vice versa).
    3. Fallback: the individual words of the topic (length >= 3).
    """
    if topic in _TOPIC_SYNONYMS:
        return _TOPIC_SYNONYMS[topic]
    for key, terms in _TOPIC_SYNONYMS.items():
        if topic in key or key in topic:
            return terms
    # Unknown topic — use its own words
    return [w for w in topic.split() if len(w) >= 3] or [topic]
 
 
def _is_relevant(article: Dict, topic: str) -> bool:
    """
    Return True when title+description contains at least one filter term.
    Matching is case-insensitive substring search.
    """
    text = (
        " " +
        (article.get("title")       or "").lower() + " " +
        (article.get("description") or "").lower() + " "
    )
    return any(term in text for term in _get_filter_terms(topic))
 
 
def _filter_articles(articles: List[Dict], topic: str) -> List[Dict]:
    """
    Keep only articles relevant to topic. Returns up to 5.
    Logs each keep/drop decision for debugging.
    """
    if not topic:
        return articles[:5]   # no topic = generic headlines, no filtering needed
 
    kept   = []
    dropped = 0
    for a in articles:
        if _is_relevant(a, topic):
            kept.append(a)
            print(
                f"[NEWS FILTER] KEEP: {a.get('title', '')[:70]!r}",
                file=sys.stderr,
            )
            if len(kept) == 5:
                break
        else:
            dropped += 1
            print(
                f"[NEWS FILTER] DROP: {a.get('title', '')[:70]!r}",
                file=sys.stderr,
            )
 
    print(
        f"[NEWS FILTER] topic={topic!r} kept={len(kept)} dropped={dropped}",
        file=sys.stderr,
    )
    return kept
 
 
# ── Helpers ───────────────────────────────────────────────────────────────
 
def _extract_search_query(user_message: str) -> str:
    """
    Strip noise words and return the clean search topic.
    Returns "" for fully generic requests like "Latest news".
 
    Examples:
      "Latest news about Elon Musk"   → "elon musk"
      "Today's AI news"               → "ai"
      "Cricket news"                  → "cricket"
      "Latest news"                   → ""
      "Breaking news"                 → ""
    """
    normalized = user_message.strip().lower()
 
    # Exact generic phrase → no topic
    if normalized in _GENERIC_PHRASES:
        return ""
 
    # Remove possessives before stripping punctuation ("today's" → "today")
    normalized = re.sub(r"'s\b", " ", normalized)
 
    # Remove all punctuation
    cleaned = re.sub(r"[^\w\s]", " ", normalized)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
 
    # Remove noise words AND single-char leftovers (e.g. stray "s")
    words = [w for w in cleaned.split() if w not in _NOISE_WORDS and len(w) > 1]
    return " ".join(words).strip()
 
 
def _why_matters(title: str, description: str, topic: str) -> str:
    """Pick the most relevant 'why it matters' sentence."""
    text = (title + " " + description + " " + topic).lower()
    # Check specific keywords first (longest match wins)
    for kw in sorted(_WHY_MATTERS.keys(), key=len, reverse=True):
        if kw == "default":
            continue
        if kw in text:
            return _WHY_MATTERS[kw]
    return _WHY_MATTERS["default"]
 
 
def _simplify(text: str, max_sentences: int = 3, max_words: int = 50) -> str:
    """Return a clean, short version of text (strips HTML, URLs, source tags)."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s*[-|]\s*\w[\w\s]{0,30}$", "", text).strip()
    text = re.sub(r"https?://\S+", "", text).strip()
    text = re.sub(r"\s+", " ", text).strip()
 
    sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    short = " ".join(sentences[:max_sentences])
 
    words = short.split()
    if len(words) > max_words:
        short = " ".join(words[:max_words]).rstrip(",.;:") + "."
 
    if short and short[-1] not in ".!?":
        short += "."
    return short
 
 
def _make_sentinel(message: str) -> List[Dict]:
    """Return a sentinel list that summarize_news will convert to message."""
    return [{_SENTINEL: True, "_message": message}]
 
 
# ── GNews API calls ───────────────────────────────────────────────────────
 
def _call_gnews(
    endpoint: str,
    params: dict,
    label: str,
) -> Tuple[Optional[List[Dict]], Optional[str]]:
    """
    Generic GNews caller used by both /search and /top-headlines.
    Returns (articles, error_string).
      articles=list, error=None   → success
      articles=[],   error=None   → zero results (API worked)
      articles=None, error=str    → API/network failure
    """
    sep = "=" * 60
    print(f"\n{sep}", file=sys.stderr)
    print(f"[NEWS DEBUG] {label}", file=sys.stderr)
    safe = {k: v for k, v in params.items() if k != "token"}
    print(f"[NEWS DEBUG] Params: {safe}", file=sys.stderr)
 
    try:
        r = requests.get(
            f"https://gnews.io/api/v4/{endpoint}",
            params=params,
            timeout=8,
        )
        print(f"[NEWS DEBUG] HTTP Status : {r.status_code}", file=sys.stderr)
        print(f"[NEWS DEBUG] Body        : {r.text[:800]}", file=sys.stderr)
 
        if r.status_code != 200:
            logger.error("[NEWS] %s HTTP %s — %s", label, r.status_code, r.text[:400])
            if r.status_code in (401, 403):
                print(f"[NEWS DEBUG] → Invalid/unauthorized key", file=sys.stderr)
                print(f"{sep}\n", file=sys.stderr)
                return None, _ERR_INVALID_KEY
            if r.status_code == 429:
                print(f"[NEWS DEBUG] → Rate limit", file=sys.stderr)
                print(f"{sep}\n", file=sys.stderr)
                return None, _ERR_RATE_LIMIT
            print(f"[NEWS DEBUG] → HTTP error {r.status_code}", file=sys.stderr)
            print(f"{sep}\n", file=sys.stderr)
            return None, f"{_ERR_API_FAILURE} (HTTP {r.status_code})"
 
        try:
            data = r.json()
        except Exception as pe:
            print(f"[NEWS DEBUG] → JSON parse error: {pe}", file=sys.stderr)
            print(f"{sep}\n", file=sys.stderr)
            logger.error("[NEWS] JSON parse error: %s", pe)
            return None, _ERR_PARSE
 
        print(f"[NEWS DEBUG] JSON keys   : {list(data.keys())}", file=sys.stderr)
 
        if "errors" in data:
            errs = "; ".join(str(e) for e in data["errors"])
            print(f"[NEWS DEBUG] → API errors: {errs}", file=sys.stderr)
            print(f"{sep}\n", file=sys.stderr)
            logger.error("[NEWS] API errors: %s", errs)
            return None, f"{_ERR_API_FAILURE} ({errs})"
 
        raw = data.get("articles") or []
        print(f"[NEWS DEBUG] Articles    : {len(raw)}", file=sys.stderr)
        print(f"{sep}\n", file=sys.stderr)
 
        # Collect ALL raw articles (up to 10 from API).
        # Do NOT cap at 5 here — _filter_articles caps after relevance filtering,
        # so relevant articles aren't missed because irrelevant ones filled the cap.
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
                "topic":       params.get("q", params.get("topic", "")),
            })
 
        print(f"[NEWS DEBUG] Valid       : {len(articles)}", file=sys.stderr)
        return articles, None
 
    except requests.exceptions.Timeout:
        print(f"[NEWS DEBUG] → Timeout", file=sys.stderr)
        print(f"{sep}\n", file=sys.stderr)
        logger.error("[NEWS] %s timeout", label)
        return None, _ERR_API_FAILURE
 
    except requests.exceptions.ConnectionError as ce:
        print(f"[NEWS DEBUG] → Connection error: {ce}", file=sys.stderr)
        print(f"{sep}\n", file=sys.stderr)
        logger.error("[NEWS] %s connection error: %s", label, ce)
        return None, _ERR_API_FAILURE
 
    except Exception as e:
        print(f"[NEWS DEBUG] → Exception: {e}", file=sys.stderr)
        print(f"{sep}\n", file=sys.stderr)
        logger.error("[NEWS] %s exception: %s", label, e)
        return None, _ERR_API_FAILURE
 
 
def _search_gnews(query: str) -> Tuple[Optional[List[Dict]], Optional[str]]:
    """
    GNews /search for a specific topic.
    Tries full query first, then falls back word-by-word (longest first).
    """
    if not _GNEWS_KEY:
        return None, _ERR_NO_KEY
 
    params = {"token": _GNEWS_KEY, "lang": "en", "max": 10, "q": query}
    articles, err = _call_gnews("search", params, f"GNews /search q={query!r}")
 
    if err is not None:
        return None, err
    if articles:
        return articles, None
 
    # Word-by-word fallback (only if multi-word query and it returned zero)
    words = sorted({w for w in query.split() if len(w) >= 3}, key=len, reverse=True)
    for word in words:
        if word == query:
            continue
        print(f"[NEWS] Fallback: trying single word={word!r}", file=sys.stderr)
        fb_params = {"token": _GNEWS_KEY, "lang": "en", "max": 10, "q": word}
        fb_articles, fb_err = _call_gnews("search", fb_params, f"GNews /search fallback q={word!r}")
        if fb_err is not None:
            return None, fb_err
        if fb_articles:
            print(f"[NEWS] Fallback succeeded: {word!r}", file=sys.stderr)
            return fb_articles, None
 
    return [], None  # API worked, genuinely no results
 
 
def _headlines_gnews(topic: str = "breaking-news") -> Tuple[Optional[List[Dict]], Optional[str]]:
    """GNews /top-headlines for generic requests."""
    if not _GNEWS_KEY:
        return None, _ERR_NO_KEY
 
    params = {
        "token":   _GNEWS_KEY,
        "lang":    "en",
        "country": "in",
        "max":     10,
        "topic":   topic,
    }
    return _call_gnews("top-headlines", params, f"GNews /top-headlines topic={topic!r}")
 
 
# ── Public API ────────────────────────────────────────────────────────────
 
def fetch_news(user_message: str = "") -> Tuple[List[Dict], str]:
    """
    Fetch up to 5 news articles from GNews.
 
    Returns (articles, provider_tag):
      articles populated  → ("GNEWS")
      topic not found     → ([], "NO_RESULTS:<topic>")
      general no results  → ([], "NO_RESULTS:general")
      API failure         → ([], "ERROR:<message>")
 
    router.py usage:
      articles, provider = fetch_news(user_message)
      reply = summarize_news(articles, lang=lang)
 
    summarize_news detects the sentinel embedded in articles
    and returns the correct message without needing provider_tag.
    """
    print(f"[NEWS] fetch_news: {user_message!r}", file=sys.stderr)
 
    search_query = _extract_search_query(user_message)
    print(f"[NEWS] search_query extracted: {search_query!r}", file=sys.stderr)
 
    # ── Specific topic ────────────────────────────────────────────────────
    if search_query:
        print(f"[NEWS] Specific topic → /search", file=sys.stderr)
        articles, err = _search_gnews(search_query)
 
        if err is not None:
            print(f"[NEWS] /search error: {err}", file=sys.stderr)
            return _make_sentinel(err), f"ERROR:{err}"
 
        if articles:
            # Apply relevance filter — keep only articles about the topic
            filtered = _filter_articles(articles, search_query)
            if filtered:
                print(f"[NEWS] After filter: {len(filtered)} relevant articles", file=sys.stderr)
                return filtered, "GNEWS"
            print(f"[NEWS] All {len(articles)} articles filtered out for {search_query!r}", file=sys.stderr)
 
        # API worked but zero results (or all filtered out)
        display_topic = search_query.title()
        msg = (
            f'No recent news found about "{display_topic}" at the moment.\n'
            f"Please try another topic or check again later."
        )
        print(f"[NEWS] No relevant articles for {search_query!r}", file=sys.stderr)
        return _make_sentinel(msg), f"NO_RESULTS:{search_query}"
 
    # ── Generic headlines ─────────────────────────────────────────────────
    topic = _TOPIC_MAP.get(
        next((k for k in _TOPIC_MAP if k in user_message.lower()), ""),
        "breaking-news",
    )
    print(f"[NEWS] Generic → /top-headlines topic={topic!r}", file=sys.stderr)
    articles, err = _headlines_gnews(topic)
 
    if err is not None:
        print(f"[NEWS] /top-headlines error: {err}", file=sys.stderr)
        return _make_sentinel(err), f"ERROR:{err}"
 
    if articles:
        print(f"[NEWS] /top-headlines success: {len(articles)} articles", file=sys.stderr)
        return articles, "GNEWS"
 
    msg = "No recent news found."
    print(f"[NEWS] /top-headlines zero results", file=sys.stderr)
    return _make_sentinel(msg), "NO_RESULTS:general"
 
 
def summarize_news(articles: List[Dict], lang: str = "en") -> str:
    """
    Format articles as:
      📰 Headline
      📌 What happened (2-3 sentences)
      🌍 Why it matters (1 sentence)
      🔗 Source
 
    Handles sentinel dicts returned by fetch_news when list is empty or error.
    router.py calls this with whatever fetch_news returned — no changes needed there.
    """
    # ── Sentinel: pre-built message (no results / error) ──────────────────
    if articles and articles[0].get(_SENTINEL):
        msg = articles[0].get("_message", "Unable to fetch the latest news.")
        if lang == "te":
            return "తాజా వార్తలు తీసుకోవడం సాధ్యం కాలేదు. దయచేసి కొద్దిసేపటి తర్వాత మళ్లీ ప్రయత్నించండి."
        return msg
 
    # ── No articles at all ────────────────────────────────────────────────
    if not articles:
        if lang == "te":
            return "తాజా వార్తలు తీసుకోవడం సాధ్యం కాలేదు. దయచేసి కొద్దిసేపటి తర్వాత మళ్లీ ప్రయత్నించండి."
        return "Unable to fetch the latest news."
 
    # ── Format real articles ──────────────────────────────────────────────
    blocks = []
    for a in articles[:5]:
        title  = (a.get("title")       or "").strip()
        desc   = (a.get("description") or "").strip()
        source = (a.get("source")      or "GNews").strip()
        topic  = (a.get("topic")       or "")
 
        if not title:
            continue
 
        what = _simplify(desc, max_sentences=3, max_words=50)
        if not what:
            what = _simplify(title, max_sentences=1, max_words=25)
 
        why = _why_matters(title, desc, topic)
 
        blocks.append(
            f"📰 {title}\n"
            f"📌 What happened:\n{what}\n"
            f"🌍 Why it matters:\n{why}\n"
            f"🔗 Source: {source}"
        )
 
    if not blocks:
        return "Unable to fetch the latest news."
 
    header = "📰 తాజా వార్తలు\n\n" if lang == "te" else "📰 Latest News\n\n"
    return header + "\n\n─────────────\n\n".join(blocks)
 
 
def format_news_response(articles: List[Dict], provider: str, lang: str = "en") -> str:
    """
    Legacy wrapper — kept for backward compatibility.
    router.py only calls summarize_news, so this is not used in the main flow.
    """
    return summarize_news(articles, lang=lang)