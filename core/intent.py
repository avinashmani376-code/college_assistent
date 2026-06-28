"""
Natural Language Intent Classifier
===================================
Understands free-form user input without requiring exact patterns.
Supports:
  - Flexible intent detection (search / news / weather / college / images / video)
  - Context-aware classification (classify_intent_with_context)
  - Pronoun and follow-up resolution
  - Language detection (English / Telugu)
  - Static vs real-time knowledge routing
"""
 
import re
from typing import Dict, List, Optional
 
# ═══════════════════════════════════════════════════════════════
# COLLEGE KEYWORDS
# ═══════════════════════════════════════════════════════════════
 
COLLEGE_KEYWORDS = [
    "ideal college", "ideal", "college", "campus", "kakinada college",
    "vidyuth nagar", "arts and sciences", "naac", "andhra university",
    "adikavi nannaya", "affiliation", "accreditation",
    "principal", "vice principal", "hod", "head of department",
    "faculty", "staff", "teacher", "professor",
    "director", "academic director", "administrative director",
    "satyanarayana", "ranjith", "vasu", "kama raju",
    "exam incharge", "suresh kumar",
    "course", "courses", "bca", "bsc", "bba", "mca", "msc",
    "b.sc", "m.sc", "agriculture", "fisheries", "aqua",
    "food technology", "fsn", "computer science",
    "duration", "subjects", "syllabus",
    "ug", "pg", "undergraduate", "postgraduate",
    "fee", "fees", "fee structure", "tuition", "ఫీజు", "annual fee",
    "admission", "admissions", "apply", "eligibility", "documents",
    "application", "join", "enroll",
    "hostel", "accommodation", "hostel fee", "boys hostel", "girls hostel",
    "mess", "హాస్టల్",
    "library", "lab", "labs", "laboratory", "wifi", "wi-fi",
    "playground", "cafeteria", "cctv", "parking", "auditorium",
    "ro water", "canteen",
    "bus", "transport", "bus facility", "vehicle",
    "placement", "placements", "placed", "selected", "company", "companies",
    "drives", "recruit", "package", "campus drive",
    "timing", "timings", "hours", "attendance", "exam", "examination",
    "uniform", "rules", "ragging",
    "scholarship", "scholarships", "financial aid",
    "sports", "nss", "ncc", "cultural", "volleyball",
    "established", "founded",
    "కళాశాల", "కాలేజీ", "ఐడియల్", "కోర్సు", "కోర్సులు",
    "ఫీజు", "అడ్మిషన్", "హాస్టల్", "ప్రిన్సిపల్",
    "లైబ్రరీ", "ప్లేస్‌మెంట్", "సౌకర్యాలు", "సమయం",
    "సిబ్బంది", "ఫ్యాకల్టీ", "డైరెక్టర్",
]
 
ROMAN_TELUGU_COLLEGE = [
    "college gurunchi", "fee enti", "fee ela",
    "hostel enti", "hostel fee", "principal evaru", "hod evaru",
    "courses emi", "courses enti", "admission ela", "admission kosam",
    "placements enti", "placements ela", "library gurunchi",
    "timing enti", "scholarship undi", "facilities emi",
    "rules emi", "attendance enti",
    "director evaru", "ranjith evaru", "vasu evaru",
    "academic director evaru", "administrative director evaru",
]
 
# ═══════════════════════════════════════════════════════════════
# WEATHER KEYWORDS
# ═══════════════════════════════════════════════════════════════
 
WEATHER_KEYWORDS = [
    "weather", "temperature", "climate", "rain", "rainfall", "forecast",
    "humidity", "wind speed", "sunny", "cloudy", "storm",
    "today weather", "current weather", "mausam",
    "వాతావరణం", "ఉష్ణోగ్రత", "వర్షం", "నేటి వాతావరణం",
]
 
# Follow-up words that mean "same weather topic"
WEATHER_FOLLOWUP_WORDS = {
    "tomorrow", "weekend", "next week", "rain", "sunny", "cloudy",
    "temperature", "humidity", "forecast", "tonight", "evening",
    "morning", "afternoon", "రేపు", "వర్షం",
}
 
# ═══════════════════════════════════════════════════════════════
# NEWS KEYWORDS
# ═══════════════════════════════════════════════════════════════
 
NEWS_KEYWORDS = [
    "news", "latest news", "today news", "breaking news", "headlines",
    "latest updates", "current events", "recent news", "top stories",
    "india news", "telugu news", "current affairs", "affairs",
    "వార్తలు", "తాజా వార్తలు", "నేటి వార్తలు", "బ్రేకింగ్",
]
 
# News intent patterns — flexible regex matching
_NEWS_PATTERNS = [
    r"(?:latest|recent|current|today'?s?|breaking|top|new)\s+news(?:\s+(?:about|on|of|regarding)\s+(.+))?",
    r"\bnews\s+(?:about|on|of|regarding)\s+(.+)",
    r"(.+?)\s+(?:latest\s+)?news\b",
    r"what'?s?\s+(?:new|happening)(?:\s+(?:in|about|on|with)\s+(.+))?",
    r"\bany\s+(?:updates?|news)\s+(?:about|on|in)\s+(.+)",
    r"^\s*news\s*$",
    r"\bheadlines\b",
    r"\b(?:current\s+affairs|current\s+events)\b",
    r"(?:tell\s+me\s+)?(.+?)\s+news(?:\s+today)?\s*$",
    r"(?:recent|latest)\s+(?:updates?|developments?)\s+(?:in|about|on)\s+(.+)",
]
 
# News follow-up words
NEWS_FOLLOWUP_WORDS = {
    "today", "updates", "any updates", "big companies", "latest",
    "recent", "what happened", "anything new", "new developments",
}
 
# ═══════════════════════════════════════════════════════════════
# SEARCH KEYWORDS
# ═══════════════════════════════════════════════════════════════
 
SEARCH_KEYWORDS = [
    "what is", "who is", "who was", "what are", "what was",
    "explain", "define", "meaning of", "tell me about", "tell me more about",
    "how does", "how did", "why is", "why was", "when did",
    "where is", "information about", "search", "find",
    "tell me", "about", "i want to know", "give information",
    "give me information", "can you explain", "can you tell",
    "who are", "biography", "bio", "details", "history of",
    "facts about", "info about", "info on", "summary of",
    "overview of", "everything about", "something about",
    "could you tell", "what do you know about", "any information",
    "please explain", "give me details", "tell me something about",
    "ఏమిటి", "ఎవరు", "గురించి చెప్పు", "వివరణ",
]
 
# ═══════════════════════════════════════════════════════════════
# DETAIL / ELABORATION KEYWORDS
# ═══════════════════════════════════════════════════════════════
 
DETAIL_KEYWORDS = [
    "explain more", "tell me more", "elaborate", "more details",
    "in detail", "detailed explanation", "full explanation",
    "describe in detail", "explain everything", "details",
]
 
# ═══════════════════════════════════════════════════════════════
# SELF-REFERENCE (who made this bot)
# ═══════════════════════════════════════════════════════════════
 
SELF_REFERENCE_KEYWORDS = [
    "who developed you", "who created you", "who made you",
    "who invented you", "who designed you", "who built you",
    "who is your developer", "who is your creator", "who is your maker",
    "who is behind this ai", "who owns this ai", "who owns you",
    "who created this chatbot", "who developed this chatbot",
    "who made this chatbot", "who built this chatbot",
    "who created this assistant", "who developed this assistant",
    "who made this assistant", "who built this assistant",
    "who created this system", "who developed this system",
    "who made this system", "who built this system",
    "who created ideal ai", "who developed ideal ai",
    "who made ideal ai", "who built ideal ai",
    "who created this bot", "who developed this bot",
    "who made this bot", "who built this bot",
    "your developer", "your creator", "your maker",
    "who are you made by", "who are you created by",
    "who are you developed by", "who are you built by",
    "నిన్ను ఎవరు తయారు చేశారు", "నిన్ను ఎవరు డెవలప్ చేశారు",
    "ఈ ai ని ఎవరు తయారు చేశారు", "ఈ చాట్\u200dబాట్\u200dను ఎవరు తయారు చేశారు",
    "ఈ సిస్టమ్\u200dను ఎవరు డెవలప్ చేశారు", "నిన్ను ఎవరు",
    "ఈ ai ఎవరు", "ఈ చాట్\u200dబాట్ ఎవరు", "ఈ సిస్టమ్ ఎవరు",
]
 
_SELF_REF_VERBS = [
    "developed", "created", "made", "invented", "designed", "built",
    "programmed", "coded", "launched", "trained", "deployed",
]
_SELF_REF_TARGETS = [
    "you", "your", "this ai", "this bot", "this chatbot",
    "this assistant", "this system", "ideal ai", "this app",
    "this application", "this tool",
]
 
# ═══════════════════════════════════════════════════════════════
# IMAGE / VIDEO KEYWORDS
# ═══════════════════════════════════════════════════════════════
 
IMAGE_KEYWORDS = [
    "image", "images", "photo", "photos", "campus photos", "gallery",
    "picture", "pictures", "college images",
    "ఫోటోలు", "చిత్రాలు",
]
 
VIDEO_KEYWORDS = [
    "video", "college video", "virtual tour",
    "వీడియో", "పూర్తి వివరాలు",
]
 
# ═══════════════════════════════════════════════════════════════
# FILLER / STOP WORDS  (stripped to find real subject)
# ═══════════════════════════════════════════════════════════════
 
_FILLER_WORDS = {
    "who", "what", "is", "are", "was", "were", "tell", "me", "about",
    "please", "can", "you", "explain", "give", "information", "details",
    "today", "latest", "recent", "current", "a", "an", "the", "i",
    "want", "to", "know", "some", "show", "find", "search", "get",
    "describe", "define", "meaning", "of", "in", "on", "at", "for",
    "and", "or", "do", "does", "did", "how", "why", "when", "where",
    "which", "from", "with", "by", "its", "info", "could", "would",
    "should", "any", "something", "everything", "anything", "nothing",
    "please", "kindly", "just", "only", "also", "too", "as", "well",
}
 
# Pronouns that signal a follow-up referencing previous topic
_PRONOUNS = {
    "he", "she", "it", "they", "his", "her", "hers", "its",
    "their", "theirs", "him", "them", "this", "that", "these",
    "those", "same",
}
 
# Bare follow-up starters — meaningless without previous context
_FOLLOWUP_STARTERS = [
    "what about", "and what", "tell me more", "what else",
    "any more", "more about", "what is his", "what is her",
    "what is their", "who else", "when did he", "when did she",
    "when was he", "when was she", "how old is he", "how old is she",
    "how old", "when was", "where was", "where is he", "where is she",
    "how did he", "how did she", "why did he", "why did she",
    "what did he", "what did she", "latest", "recent", "new",
    "latest movie", "latest song", "latest news", "latest film",
    "newest", "budget", "collection", "box office", "directed by",
    "who directed", "who produced", "release date", "cast",
    "awards", "net worth", "age", "born", "death", "married",
    "children", "family", "height", "nationality",
]
 
# ═══════════════════════════════════════════════════════════════
# CITY EXTRACTION (weather)
# ═══════════════════════════════════════════════════════════════
 
NON_CITY_WORDS = {
    "weather", "report", "reports", "today", "now", "forecast",
    "current", "latest", "here", "there", "please", "temperature",
    "climate", "check", "show", "get", "give", "what", "how",
    "the", "a", "an", "is", "are", "was", "will", "me", "my",
    "your", "our", "their", "tell", "know", "want", "of", "in",
    "at", "for", "about", "and", "or", "humid", "humidity",
    "wind", "sunny", "cloudy", "rain", "cold", "hot",
}
 
# ═══════════════════════════════════════════════════════════════
# REAL-TIME vs STATIC KNOWLEDGE
# ═══════════════════════════════════════════════════════════════
 
_REALTIME_TRIGGERS = [
    "today", "current", "latest", "recent", "now",
    "2024", "2025", "2026",
    "who is cm", "who is pm", "who is president", "who is ceo",
    "who is ap cm", "who is telangana cm", "who is governor",
    "who is minister", "stock", "price", "rate", "score",
    "match result", "election result", "won", "winner",
    "bitcoin", "crypto", "ipl", "cricket score",
]
 
_STATIC_TRIGGERS = [
    "what is", "what are", "define", "meaning of",
    "explain what", "what does", "explain", "describe",
]
 
_KNOWN_STATIC_TOPICS = [
    "ai", "artificial intelligence", "machine learning", "deep learning",
    "neural network", "blockchain", "cloud computing", "internet of things",
    "python", "java", "javascript", "html", "css", "sql", "database",
    "algorithm", "data structure", "operating system", "computer",
    "programming", "software", "hardware", "internet", "network",
    "cybersecurity", "encryption", "virus", "malware", "api", "oop",
    "big data", "data science", "computer vision", "nlp",
    "solar system", "photosynthesis", "gravity", "atom", "dna",
    "evolution", "relativity", "quantum", "black hole", "galaxy",
    "electricity", "magnetism", "thermodynamics", "cell", "genetics",
    "democracy", "communism", "capitalism", "economics", "constitution",
    "parliament", "judiciary", "globalization", "inflation", "gdp",
]
 
_FAMOUS_PEOPLE_STATIC = [
    "mahatma gandhi", "jawaharlal nehru", "subhas chandra bose",
    "albert einstein", "isaac newton", "nikola tesla", "thomas edison",
    "shakespeare", "napoleon", "abraham lincoln", "winston churchill",
    "apj abdul kalam", "rabindranath tagore", "swami vivekananda",
    "aryabhatta", "chanakya", "dr ambedkar", "br ambedkar",
    "srinivasa ramanujan", "cv raman",
    "elon musk", "bill gates", "steve jobs",
    "mark zuckerberg", "jeff bezos", "warren buffett",
    "sachin tendulkar", "virat kohli", "ms dhoni", "rohit sharma",
    "amitabh bachchan", "shah rukh khan",
]
 
# ═══════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════
 
def _is_self_reference(msg: str) -> bool:
    if any(k in msg for k in SELF_REFERENCE_KEYWORDS):
        return True
    if "who" in msg:
        for verb in _SELF_REF_VERBS:
            if verb in msg:
                for target in _SELF_REF_TARGETS:
                    if target in msg:
                        return True
    for phrase in ("your developer", "your creator", "your maker",
                   "who made you", "who built you", "who created you",
                   "who invented you", "who designed you", "who developed you"):
        if phrase in msg:
            return True
    return False
 
 
def _content_words(msg: str) -> List[str]:
    """Strip filler words and return meaningful tokens."""
    tokens = re.findall(r"[a-zA-Z'\-]+", msg.lower())
    return [w for w in tokens if w not in _FILLER_WORDS]
 
 
def _is_news_query(msg: str) -> bool:
    if any(k in msg for k in NEWS_KEYWORDS):
        return True
    for pat in _NEWS_PATTERNS:
        if re.search(pat, msg, re.IGNORECASE):
            return True
    return False
 
 
def _extract_news_topic(msg: str) -> str:
    """Extract the topic from a news query (e.g. 'Elon Musk' from 'Latest news about Elon Musk')."""
    for pat in _NEWS_PATTERNS:
        m = re.search(pat, msg, re.IGNORECASE)
        if m:
            groups = [g for g in (m.groups() if m.lastindex else []) if g]
            if groups:
                topic = groups[0].strip().strip("?.!,")
                words = [w for w in topic.split() if w.lower() not in _FILLER_WORDS]
                if words:
                    return " ".join(words)
    return ""
 
 
def _is_search_query(msg: str) -> bool:
    """
    Returns True for any natural info-seeking query:
    bare names, bio/details suffixes, filler-wrapped questions.
    """
    if any(k in msg for k in SEARCH_KEYWORDS):
        if _content_words(msg):
            return True
 
    cw = _content_words(msg)
    if cw:
        weather_tok = {w for k in WEATHER_KEYWORDS for w in k.split()}
        news_tok    = {w for k in NEWS_KEYWORDS    for w in k.split()}
        college_tok = {w for k in COLLEGE_KEYWORDS for w in k.split()}
        image_tok   = {w for k in IMAGE_KEYWORDS   for w in k.split()}
        video_tok   = {w for k in VIDEO_KEYWORDS   for w in k.split()}
        occupied = weather_tok | news_tok | college_tok | image_tok | video_tok
        if [w for w in cw if w not in occupied]:
            return True
    return False
 
 
def _is_valid_city(word: str) -> bool:
    return bool(word) and len(word) > 1 and word.lower() not in NON_CITY_WORDS
 
 
# ═══════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════
 
def detect_language(text: str) -> str:
    if not text:
        return "en"
    telugu_chars = sum(1 for ch in text if "\u0C00" <= ch <= "\u0C7F")
    total = max(len(text.replace(" ", "")), 1)
    if telugu_chars / total > 0.08:
        return "te"
    roman_te = {
        "nenu", "meeru", "kavali", "cheppu", "undi", "ledu", "anni",
        "emi", "ela", "enduku", "enti", "evaru", "gurunchi", "kosam",
        "cheyyi", "cheyandi", "cheppandi", "okka", "ledhu",
    }
    words = set(re.findall(r"[a-zA-Z]+", text.lower()))
    if words & roman_te:
        return "te"
    return "en"
 
 
def is_detail_request(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in DETAIL_KEYWORDS)
 
 
def extract_city_from_weather(msg: str) -> str:
    c = msg.strip()
    m = re.search(
        r'\b(?:in|at|of|for)\s+([A-Za-z][A-Za-z ]{1,30}?)'
        r'(?:\s*(?:\?|$|today|now|please|weather|forecast)|\s*$)',
        c, re.IGNORECASE,
    )
    if m:
        cw = [w for w in m.group(1).strip().strip("?.!, ").split() if _is_valid_city(w)]
        if cw:
            return " ".join(cw)
    m2 = re.search(r'^([A-Za-z][A-Za-z ]{1,25}?)\s+weather', c, re.IGNORECASE)
    if m2:
        cw = [w for w in m2.group(1).strip().split() if _is_valid_city(w)]
        if cw:
            return " ".join(cw)
    for pat in [
        r"weather\s+(?:of|in|at|for)\s+([A-Za-z][A-Za-z ]{1,25})",
        r"temperature\s+(?:in|at|of)\s+([A-Za-z][A-Za-z ]{1,25})",
    ]:
        m3 = re.search(pat, c, re.IGNORECASE)
        if m3:
            cw = [w for w in m3.group(1).strip().strip("?.!, ").split() if _is_valid_city(w)]
            if cw:
                return " ".join(cw)
    words = c.split()
    wx = {i for i, w in enumerate(words)
          if w.lower() in ("weather", "temperature", "climate", "forecast")}
    for i, w in enumerate(words):
        clean = w.strip("?.!,")
        if _is_valid_city(clean) and i not in wx and (i - 1) not in wx:
            return clean
    return "Kakinada"
 
 
def is_static_knowledge(question: str) -> bool:
    """
    True  → Groq can answer from training data (no Tavily needed).
    False → Needs fresh web data (use Tavily).
    """
    q = question.lower().strip()
 
    # Real-time signals → always Tavily
    if any(r in q for r in _REALTIME_TRIGGERS):
        return False
 
    # Known static topic + static question word → Groq direct
    if any(t in q for t in _STATIC_TRIGGERS) and any(e in q for e in _KNOWN_STATIC_TOPICS):
        return True
 
    # Well-known people → Groq direct
    if ("who is" in q or "who was" in q) and any(p in q for p in _FAMOUS_PEOPLE_STATIC):
        return True
 
    # Any who/about/explain/bio query with content word → Groq has training data
    _who_patterns = [
        "who is", "who was", "who are", "who were",
        "tell me about", "about", "explain", "biography", "bio",
        "details", "history of", "information about", "info about",
    ]
    if any(p in q for p in _who_patterns) and _content_words(q):
        return True
 
    # Default → Tavily (safer for unknown queries)
    return False
 
 
def classify_intent(message: str) -> Dict:
    """
    Classify intent from a single message (no history).
    For context-aware classification use classify_intent_with_context().
    """
    msg = (message or "").lower().strip()
 
    if _is_self_reference(msg):
        return {"intent": "college"}
 
    if any(k in msg for k in IMAGE_KEYWORDS):
        return {"intent": "images"}
    if any(k in msg for k in VIDEO_KEYWORDS):
        return {"intent": "video"}
 
    weather_score = sum(1 for k in WEATHER_KEYWORDS if k in msg)
    college_score = sum(1 for k in COLLEGE_KEYWORDS if k in msg)
    college_score += sum(2 for k in ROMAN_TELUGU_COLLEGE if k in msg)
 
    if weather_score >= 1 and college_score <= weather_score:
        return {"intent": "weather", "city": extract_city_from_weather(message)}
 
    # News before college (prevents sports keywords stealing news queries)
    if _is_news_query(msg):
        return {"intent": "news", "topic": _extract_news_topic(msg)}
 
    if college_score >= 1:
        return {"intent": "college"}
 
    if _is_search_query(msg):
        return {"intent": "search"}
 
    return {"intent": "general"}
 
 
def _is_self_contained(msg: str, weather_score: int, college_score: int,
                        has_news: bool, has_search: bool, cw: list) -> bool:
    """
    Returns True when the current message is self-contained — it has a
    clear intent and subject on its own, so previous context must be
    completely ignored.
 
    A message is self-contained when ANY of these is true:
      - It has a weather signal (city + weather keyword)
      - It has a news signal with a topic
      - It has a college signal
      - It has 3+ meaningful content words (clear subject present)
      - It contains a named entity signal (capitalised word that is NOT
        a sentence-start-only capital, i.e. appears mid-sentence OR the
        message is multi-word and starts with a capital proper noun)
    """
    # Strong explicit intent signals always win
    if weather_score >= 1:
        return True
    if college_score >= 2:          # strong college match
        return True
    if has_news and any(                # news with its own topic
        re.search(pat, msg, re.IGNORECASE) and
        any(g for g in (re.search(pat, msg, re.IGNORECASE).groups() or []) if g)
        for pat in _NEWS_PATTERNS
    ):
        return True
 
    # 3+ content words → message carries its own subject
    if len(cw) >= 3:
        return True
 
    # 2 content words where at least one looks like a proper noun
    # (original text has a capital mid-sentence or is a known named entity)
    if len(cw) >= 2:
        return True          # 2 content words is enough to be self-contained
 
    return False
 
 
def classify_intent_with_context(message: str, context: Dict) -> Dict:
    """
    Context-aware intent classification.
 
    PRIORITY ORDER:
      1. Current message  ← always analysed first, highest priority
      2. Previous context ← used ONLY when current message is ambiguous/incomplete
 
    context = {
        "intent":   last resolved intent (str),
        "topic":    last resolved topic/subject (str),
        "city":     last weather city (str),
    }
 
    Returns the same dict shape as classify_intent().
    Updates context in-place when a new clear intent is detected.
    """
    msg = (message or "").lower().strip()
    raw = message.strip()
 
    # ── Always-first checks (self-ref / media) — never need context ────
    if _is_self_reference(msg):
        context["intent"] = "college"
        context["topic"]  = ""
        context["city"]   = ""
        return {"intent": "college"}
 
    if any(k in msg for k in IMAGE_KEYWORDS):
        context["intent"] = "images"
        return {"intent": "images"}
 
    if any(k in msg for k in VIDEO_KEYWORDS):
        context["intent"] = "video"
        return {"intent": "video"}
 
    # ── Score current message ───────────────────────────────────────────
    weather_score = sum(1 for k in WEATHER_KEYWORDS if k in msg)
    college_score = sum(1 for k in COLLEGE_KEYWORDS if k in msg)
    college_score += sum(2 for k in ROMAN_TELUGU_COLLEGE if k in msg)
    has_news  = _is_news_query(msg)
    has_search = _is_search_query(msg)
    cw = _content_words(msg)
 
    # ── Step 1: Is the current message self-contained? ──────────────────
    # If YES → route normally, update context, IGNORE previous context.
    # If NO  → it's a bare follow-up → use previous context.
    self_contained = _is_self_contained(msg, weather_score, college_score,
                                        has_news, has_search, cw)
 
    if self_contained:
        # ── Normal routing (current message wins completely) ────────────
        if weather_score >= 1 and college_score <= weather_score:
            city = extract_city_from_weather(message)
            context["intent"] = "weather"
            context["city"]   = city
            context["topic"]  = ""
            return {"intent": "weather", "city": city}
 
        if has_news:
            topic = _extract_news_topic(msg)
            context["intent"] = "news"
            context["topic"]  = topic
            context["city"]   = ""
            return {"intent": "news", "topic": topic}
 
        if college_score >= 1:
            context["intent"] = "college"
            context["topic"]  = ""
            context["city"]   = ""
            return {"intent": "college"}
 
        if has_search:
            topic = " ".join(cw[:4]) if cw else raw
            context["intent"] = "search"
            context["topic"]  = topic
            context["city"]   = ""
            return {"intent": "search", "topic": topic}
 
        topic = " ".join(cw[:4]) if cw else ""
        context["intent"] = "general"
        context["topic"]  = topic
        context["city"]   = ""
        return {"intent": "general"}
 
    # ── Step 2: Message is ambiguous — use previous context ─────────────
    prior_intent = context.get("intent", "")
    prior_topic  = context.get("topic", "")
    prior_city   = context.get("city", "")
 
    is_pronoun_msg = bool(set(msg.split()) & _PRONOUNS)
 
    # Weather follow-up ("Tomorrow?", "Weekend?", "Rain?")
    if prior_intent == "weather" and prior_city:
        if set(msg.split()) & WEATHER_FOLLOWUP_WORDS or len(cw) <= 2:
            return {"intent": "weather", "city": prior_city, "_followup": True}
 
    # News follow-up ("Today?", "Any updates?", "Big companies?")
    if prior_intent == "news":
        if set(msg.split()) & NEWS_FOLLOWUP_WORDS or len(cw) <= 2:
            followup_q = f"{prior_topic} {raw}".strip() if prior_topic else raw
            return {"intent": "news", "topic": prior_topic, "_followup": True,
                    "_resolved_message": followup_q}
 
    # Search/general follow-up with pronoun or bare word
    if prior_intent in ("search", "general") and prior_topic:
        if is_pronoun_msg or len(cw) <= 2:
            return {"intent": "search", "topic": prior_topic,
                    "_followup": True,
                    "_resolved_message": f"{prior_topic} {raw}".strip()}
 
    # ── Step 3: Fallback — no clear context either, classify normally ───
    if has_news:
        topic = _extract_news_topic(msg)
        context["intent"] = "news"
        context["topic"]  = topic
        context["city"]   = ""
        return {"intent": "news", "topic": topic}
 
    if has_search:
        topic = " ".join(cw[:4]) if cw else raw
        context["intent"] = "search"
        context["topic"]  = topic
        context["city"]   = ""
        return {"intent": "search", "topic": topic}
 
    context["intent"] = "general"
    context["topic"]  = " ".join(cw[:4]) if cw else ""
    return {"intent": "general"}