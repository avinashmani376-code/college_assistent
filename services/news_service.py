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

Cache:
  → Every successful response cached for 5 minutes (keyed by topic)
  → On HTTP 429 rate-limit: serve cache if available, else show busy message

Error messages:
  Network failure / timeout  → "Unable to fetch the latest news."
  Invalid API key            → "News service: Invalid API key."
  Rate limit (no cache)      → "News service is temporarily busy..."
  Topic not found            → "No recent news found for '<Topic>'."
"""
import os
import re
import sys
import json
import time
import logging
import requests
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# ── API key ───────────────────────────────────────────────────────────────
_GNEWS_KEY = (
    os.getenv("GNEWS_API_KEY", "")
    or os.getenv("GNEWS_API",     "")
)

print(
    f"[NEWS] GNews key: {'SET (len=' + str(len(_GNEWS_KEY)) + ')' if _GNEWS_KEY else 'MISSING'}",
    file=sys.stderr,
)

# ── In-memory cache: key → (articles, expiry_timestamp) ──────────────────
_CACHE: Dict[str, Tuple[List[Dict], float]] = {}
_CACHE_TTL = 300  # seconds (5 minutes)

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
    "technology":    "technology",
    "tech":          "technology",
    "education":     "education",
    "sports":        "sports",
    "sport":         "sports",
    "business":      "business",
    "finance":       "business",
    "world":         "world",
    "india":         "nation",
    "national":      "nation",
    "health":        "health",
    "science":       "science",
    "entertainment": "entertainment",
}

# ── "Why it matters" — dynamic sentences keyed by content keyword ─────────
_WHY_MATTERS = {
    # People
    "elon musk":       "Elon Musk's decisions impact technology and global markets.",
    "modi":            "This may affect government policies in India.",
    "trump":           "This could affect US policies and global relations.",
    # Energy
    "petrol price":    "It may affect petrol and diesel prices at the pump.",
    "fuel price":      "It may affect transportation costs for millions of people.",
    "petrol":          "It may affect petrol and diesel prices.",
    "fuel":            "It may affect fuel costs and daily transportation.",
    "crude oil":       "It could influence global fuel and energy prices.",
    # Tech / AI
    "artificial intelligence": "AI is rapidly changing how people work and learn.",
    "chatgpt":         "AI tools like ChatGPT are changing how students and professionals work.",
    "openai":          "OpenAI's products are shaping the future of artificial intelligence.",
    "ai":              "It could influence future technology and daily life.",
    "technology":      "It affects how we use technology in our daily lives.",
    "tech":            "It affects how we use technology in our daily lives.",
    # Companies / products
    "tesla":           "Tesla influences the global electric vehicle industry.",
    "apple":           "Apple's products and decisions affect millions of users worldwide.",
    "google":          "Google's changes can affect how billions of people access information.",
    "microsoft":       "Microsoft's moves can affect businesses and software users worldwide.",
    "startup":         "It may affect innovation and job creation in the tech industry.",
    # Crypto / finance
    "bitcoin":         "Cryptocurrency movements affect global financial markets.",
    "crypto":          "Cryptocurrency changes affect investors and financial markets.",
    "stock market":    "It may affect investors and the value of companies.",
    "sensex":          "It directly affects Indian investors and the stock market.",
    "nifty":           "It directly affects Indian investors and the stock market.",
    "rupee":           "It may affect the cost of imported goods and foreign exchange.",
    "gold":            "Gold price changes affect savings and investments in India.",
    "inflation":       "It affects the cost of everyday items for ordinary people.",
    "rbi":             "RBI decisions affect loan rates, savings, and the Indian economy.",
    # Sports
    "ipl":             "IPL is India's biggest cricket event followed by millions.",
    "cricket":         "It matters to millions of cricket fans across India.",
    "football":        "It is important for football fans around the world.",
    "sports":          "It is important for sports fans.",
    "sport":           "It is important for sports fans.",
    "olympic":         "Olympic results bring pride and recognition to nations.",
    # Geography
    "andhra pradesh":  "It may affect people living in Andhra Pradesh.",
    "telangana":       "It may affect people living in Telangana.",
    "india":           "It directly affects the lives of people across India.",
    "pakistan":        "It may affect India-Pakistan relations and regional stability.",
    "china":           "China's actions can affect global trade and regional security.",
    # Science / space
    "isro":            "It shows India's growing strength in space technology.",
    "space":           "It helps us understand the universe and advance science.",
    "satellite":       "It helps improve communication and weather forecasting.",
    "moon":            "Lunar exploration advances science and inspires future generations.",
    # Economy / jobs
    "economy":         "It impacts the cost of living and job opportunities.",
    "gdp":             "GDP growth affects jobs, wages, and living standards.",
    "jobs":            "It directly affects employment and livelihoods.",
    "budget":          "The budget shapes government spending and taxes for all citizens.",
    # Health
    "vaccine":         "Vaccines protect communities from serious diseases.",
    "health":          "It affects the health and well-being of people.",
    "hospital":        "It affects healthcare access for millions of patients.",
    # Education
    "neet":            "It affects thousands of medical students across India.",
    "jee":             "It affects thousands of engineering students across India.",
    "exam":            "It may affect students preparing for important examinations.",
    "education":       "It directly impacts students and schools across India.",
    # Politics / governance
    "election":        "It decides who will lead and make decisions for India.",
    "parliament":      "It shapes laws and decisions that affect every Indian citizen.",
    "politics":        "It may affect government decisions and policies.",
    # Environment
    "climate":         "It affects weather, farming, and life on Earth.",
    "environment":     "It affects the air, water, and nature around us.",
    "pollution":       "Pollution affects the health of millions of people.",
    "default":         "It is an important development that affects many people.",
}

# ── Error message strings ─────────────────────────────────────────────────
_ERR_NO_KEY       = "News service: API key not configured."
_ERR_INVALID_KEY  = "News service: Invalid API key. Please check GNEWS_API_KEY."
_ERR_RATE_LIMIT   = (
    "News service is temporarily busy because the daily API limit has been reached. "
    "Please try again later."
)
_ERR_API_FAILURE  = "Unable to fetch the latest news."
_ERR_PARSE        = "Unable to fetch the latest news."

# ── Topic synonym map for relevance filtering ─────────────────────────────
_TOPIC_SYNONYMS: Dict[str, List[str]] = {
    "elon musk":      ["elon", "musk", "elon musk"],
    "modi":           ["modi", "narendra modi", "pm modi", "prime minister modi"],
    "petrol":         ["petrol", "fuel", "gasoline", "crude oil", "crude",
                       "diesel", "pump price", "oil price", "fuel price", "lpg"],
    "petrol price":   ["petrol", "fuel", "diesel", "crude", "oil price",
                       "pump price", "fuel price"],
    "ai":             ["artificial intelligence", " ai ", "machine learning",
                       "llm", "openai", "chatgpt", "gemini", "deep learning",
                       "neural network", "generative ai", "large language",
                       "gpt", "claude", "mistral", "copilot"],
    "technology":     ["technology", "tech", "software", "hardware", "startup",
                       "silicon valley", "google", "apple", "microsoft",
                       "amazon", "meta", "chip", "semiconductor", "app"],
    "tesla":          ["tesla", "electric vehicle", " ev ", "elon musk",
                       "model s", "model 3", "model y", "cybertruck"],
    "bitcoin":        ["bitcoin", "btc", "cryptocurrency", "crypto", "blockchain",
                       "ethereum", "digital currency", "altcoin", "defi", "web3"],
    "stock market":   ["stock", "shares", "sensex", "nifty", "bse", "nse",
                       "market cap", "ipo", "equity", "bull run", "bear market",
                       "dalal street"],
    "gold price":     ["gold", "silver", "bullion", "mcx gold", "gold rate",
                       "precious metal"],
    "rupee":          ["rupee", "inr", "currency", "forex", "exchange rate",
                       "dollar rupee", "usd inr"],
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
    "space":          ["space", "nasa", "isro", "rocket", "satellite", "moon",
                       "mars", "orbit", "spacecraft", "astronaut", "launch",
                       "gaganyaan", "chandrayaan", "aditya"],
    "isro":           ["isro", "indian space", "gaganyaan", "chandrayaan",
                       "aditya", "launch vehicle", "sriharikota", "rocket"],
    "economy":        ["economy", "gdp", "inflation", "recession", "rbi",
                       "interest rate", "sensex", "nifty", "budget", "fiscal",
                       "economic growth", "unemployment"],
    "inflation":      ["inflation", "price rise", "cpi", "wpi", "rbi",
                       "interest rate", "repo rate", "cost of living"],
    "jobs":           ["jobs", "employment", "unemployment", "hiring",
                       "layoff", "salary", "career", "workforce"],
    "health":         ["health", "medical", "hospital", "disease", "vaccine",
                       "covid", "cancer", "treatment", "doctor", "medicine",
                       "patient", "clinical", "pharma", "drug"],
    "education":      ["education", "school", "college", "university", "student",
                       "exam", "syllabus", "teacher", "cbse", "neet", "jee",
                       "board exam", "result", "admission"],
    "politics":       ["politics", "election", "vote", "parliament", "minister",
                       "government", "political party", "campaign", "poll",
                       "lok sabha", "bjp", "congress", "aap"],
    "climate":        ["climate", "global warming", "carbon", "emission",
                       "renewable", "solar energy", "wind energy",
                       "environment", "pollution", "greenhouse", "net zero"],
    "business":       ["business", "company", "startup", "profit", "revenue",
                       "merger", "acquisition", "ipo", "stock market", "shares",
                       "ceo", "founder", "valuation"],
    "finance":        ["finance", "bank", "loan", "interest", "rbi",
                       "income tax", "gst", "budget", "investment", "mutual fund"],
}


# ── Cache helpers ──────────────────────────────────────────────────────────

def _cache_key(topic: str) -> str:
    return topic.strip().lower()


def _cache_get(topic: str) -> Optional[List[Dict]]:
    key = _cache_key(topic)
    entry = _CACHE.get(key)
    if entry is None:
        return None
    articles, expiry = entry
    if time.time() > expiry:
        del _CACHE[key]
        print(f"[NEWS CACHE] Expired: {key!r}", file=sys.stderr)
        return None
    print(f"[NEWS CACHE] HIT: {key!r} ({len(articles)} articles)", file=sys.stderr)
    return articles


def _cache_set(topic: str, articles: List[Dict]) -> None:
    key = _cache_key(topic)
    _CACHE[key] = (articles, time.time() + _CACHE_TTL)
    print(f"[NEWS CACHE] SET: {key!r} ({len(articles)} articles, TTL={_CACHE_TTL}s)", file=sys.stderr)


# ── Relevance filtering ────────────────────────────────────────────────────

def _get_filter_terms(topic: str) -> List[str]:
    if topic in _TOPIC_SYNONYMS:
        return _TOPIC_SYNONYMS[topic]
    for key, terms in _TOPIC_SYNONYMS.items():
        if topic in key or key in topic:
            return terms
    return [w for w in topic.split() if len(w) >= 3] or [topic]


def _is_relevant(article: Dict, topic: str) -> bool:
    text = (
        " " +
        (article.get("title")       or "").lower() + " " +
        (article.get("description") or "").lower() + " "
    )
    return any(term in text for term in _get_filter_terms(topic))


def _filter_articles(articles: List[Dict], topic: str) -> List[Dict]:
    if not topic:
        return articles[:5]
    kept, dropped = [], 0
    for a in articles:
        if _is_relevant(a, topic):
            kept.append(a)
            print(f"[NEWS FILTER] KEEP: {a.get('title','')[:70]!r}", file=sys.stderr)
            if len(kept) == 5:
                break
        else:
            dropped += 1
            print(f"[NEWS FILTER] DROP: {a.get('title','')[:70]!r}", file=sys.stderr)
    print(f"[NEWS FILTER] topic={topic!r} kept={len(kept)} dropped={dropped}", file=sys.stderr)
    return kept


# ── Text helpers ───────────────────────────────────────────────────────────

def _extract_search_query(user_message: str) -> str:
    normalized = user_message.strip().lower()
    if normalized in _GENERIC_PHRASES:
        return ""
    normalized = re.sub(r"'s\b", " ", normalized)
    cleaned = re.sub(r"[^\w\s]", " ", normalized)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    words = [w for w in cleaned.split() if w not in _NOISE_WORDS and len(w) > 1]
    return " ".join(words).strip()


def _why_matters(title: str, description: str, topic: str) -> str:
    text = (title + " " + description + " " + topic).lower()
    for kw in sorted(_WHY_MATTERS.keys(), key=len, reverse=True):
        if kw == "default":
            continue
        if kw in text:
            return _WHY_MATTERS[kw]
    return _WHY_MATTERS["default"]


def _clean_text(text: str, max_sentences: int = 3, max_words: int = 50) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s*[-|]\s*[A-Z][\w\s]{0,30}$", "", text).strip()
    text = re.sub(r"https?://\S+", "", text).strip()
    text = re.sub(r"\b(read more|click here|\.\.\.)\b.*", "", text, flags=re.I).strip()
    text = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s.strip() for s in sentences if s.strip() and len(s.split()) > 3]
    short = " ".join(sentences[:max_sentences])
    words = short.split()
    if len(words) > max_words:
        short = " ".join(words[:max_words]).rstrip(",.;:") + "."
    if short and short[-1] not in ".!?":
        short += "."
    return short


def _rewrite_summary(title: str, desc: str, max_sentences: int = 3, max_words: int = 50) -> str:
    if not desc:
        return _clean_text(title, max_sentences=1, max_words=20)
    cleaned = _clean_text(desc, max_sentences=max_sentences, max_words=max_words)
    if not cleaned:
        cleaned = _clean_text(title, max_sentences=1, max_words=20)
    return cleaned


def _make_sentinel(message: str) -> List[Dict]:
    return [{_SENTINEL: True, "_message": message}]


# ── GNews API caller ───────────────────────────────────────────────────────

def _call_gnews(
    endpoint: str,
    params: dict,
    label: str,
) -> Tuple[Optional[List[Dict]], Optional[str]]:
    """
    Generic GNews caller for both /search and /top-headlines.
    Returns (articles, error_string).
    On HTTP 429: returns (None, "RATE_LIMIT") so caller can check cache.
    """
    sep = "=" * 60
    print(f"\n{sep}", file=sys.stderr)
    print(f"[NEWS DEBUG] {label}", file=sys.stderr)
    safe = {k: v for k, v in params.items() if k != "token"}
    print(f"[NEWS DEBUG] Params      : {safe}", file=sys.stderr)

    if not _GNEWS_KEY:
        print(f"[NEWS DEBUG] API Key     : MISSING", file=sys.stderr)
        print(f"{sep}\n", file=sys.stderr)
        logger.error("[NEWS] GNews key not set")
        return None, _ERR_NO_KEY

    print(f"[NEWS DEBUG] API Key     : SET (len={len(_GNEWS_KEY)})", file=sys.stderr)

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
                print(f"[NEWS DEBUG] → Rate limit (429)", file=sys.stderr)
                print(f"{sep}\n", file=sys.stderr)
                return None, "RATE_LIMIT"
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
    if not _GNEWS_KEY:
        return None, _ERR_NO_KEY
    params = {"token": _GNEWS_KEY, "lang": "en", "max": 10, "q": query}
    articles, err = _call_gnews("search", params, f"GNews /search q={query!r}")
    if err is not None:
        return None, err
    if articles:
        return articles, None
    # Word-by-word fallback
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
    return [], None


def _headlines_gnews(topic: str = "breaking-news") -> Tuple[Optional[List[Dict]], Optional[str]]:
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
    Fetch up to 5 news articles from GNews, with caching.

    Cache: serve from cache if fresh (5 min TTL).
    Rate limit (429): serve stale cache if any exists; else show busy message.
    router.py requires no changes.
    """
    print(f"[NEWS] fetch_news: {user_message!r}", file=sys.stderr)

    search_query = _extract_search_query(user_message)
    cache_key    = search_query if search_query else "general"

    print(f"[NEWS] search_query={search_query!r}  cache_key={cache_key!r}", file=sys.stderr)

    # ── Check cache first ─────────────────────────────────────────────────
    cached = _cache_get(cache_key)
    if cached is not None:
        print(f"[NEWS] Serving {len(cached)} articles from cache", file=sys.stderr)
        return cached, "GNEWS"

    # ── Specific topic → /search ──────────────────────────────────────────
    if search_query:
        articles, err = _search_gnews(search_query)

        if err == "RATE_LIMIT":
            stale = _CACHE.get(_cache_key(cache_key))
            if stale:
                stale_articles, _ = stale
                print(f"[NEWS] 429 → serving stale cache ({len(stale_articles)} articles)", file=sys.stderr)
                return stale_articles, "GNEWS"
            return _make_sentinel(_ERR_RATE_LIMIT), "ERROR:RATE_LIMIT"

        if err is not None:
            return _make_sentinel(err), f"ERROR:{err}"

        if articles:
            filtered = _filter_articles(articles, search_query)
            if filtered:
                _cache_set(cache_key, filtered)
                return filtered, "GNEWS"

        display = search_query.title()
        msg = (
            f'No recent news found about "{display}" at the moment.\n'
            f"Please try another topic or check again later."
        )
        return _make_sentinel(msg), f"NO_RESULTS:{search_query}"

    # ── Generic headlines → /top-headlines ───────────────────────────────
    topic = _TOPIC_MAP.get(
        next((k for k in _TOPIC_MAP if k in user_message.lower()), ""),
        "breaking-news",
    )
    articles, err = _headlines_gnews(topic)

    if err == "RATE_LIMIT":
        stale = _CACHE.get(_cache_key("general"))
        if stale:
            stale_articles, _ = stale
            return stale_articles, "GNEWS"
        return _make_sentinel(_ERR_RATE_LIMIT), "ERROR:RATE_LIMIT"

    if err is not None:
        return _make_sentinel(err), f"ERROR:{err}"

    if articles:
        _cache_set(cache_key, articles[:5])
        return articles[:5], "GNEWS"

    return _make_sentinel("No recent news found."), "NO_RESULTS:general"


def summarize_news(articles: List[Dict], lang: str = "en") -> str:
    """
    Format articles as:
      📰 Headline
      📌 What happened (2-3 simple sentences, easy English)
      🌍 Why it matters (specific 1 sentence, never generic)
      🔗 Source

    Handles sentinel dicts from fetch_news transparently.
    router.py requires no changes.
    """
    # ── Sentinel: pre-built message ────────────────────────────────────────
    if articles and articles[0].get(_SENTINEL):
        msg = articles[0].get("_message", _ERR_API_FAILURE)
        if lang == "te":
            return "తాజా వార్తలు తీసుకోవడం సాధ్యం కాలేదు. దయచేసి కొద్దిసేపటి తర్వాత మళ్లీ ప్రయత్నించండి."
        return msg

    if not articles:
        if lang == "te":
            return "తాజా వార్తలు తీసుకోవడం సాధ్యం కాలేదు. దయచేసి కొద్దిసేపటి తర్వాత మళ్లీ ప్రయత్నించండి."
        return _ERR_API_FAILURE

    blocks = []
    for a in articles[:5]:
        title  = (a.get("title")       or "").strip()
        desc   = (a.get("description") or "").strip()
        source = (a.get("source")      or "GNews").strip()
        topic  = (a.get("topic")       or "")

        if not title:
            continue

        what = _rewrite_summary(title, desc, max_sentences=3, max_words=50)
        why  = _why_matters(title, desc, topic)

        blocks.append(
            f"📰 {title}\n"
            f"📌 What happened:\n{what}\n"
            f"🌍 Why it matters:\n{why}\n"
            f"🔗 Source: {source}"
        )

    if not blocks:
        return _ERR_API_FAILURE

    header = "📰 తాజా వార్తలు\n\n" if lang == "te" else "📰 Latest News\n\n"
    return header + "\n\n─────────────\n\n".join(blocks)


def format_news_response(articles: List[Dict], provider: str, lang: str = "en") -> str:
    """Legacy wrapper — kept for backward compatibility."""
    return summarize_news(articles, lang=lang)