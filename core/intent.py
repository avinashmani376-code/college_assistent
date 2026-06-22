# core/intent.py
import re
from typing import Dict
 
# ── College intent keywords ────────────────────────────────────────────────
# These match the question IS about the college.
# "director", "ranjith", "vasu" are added here so director questions
# route to college intent AND pass the is_about_college gate.
COLLEGE_KEYWORDS = [
    # identity
    "ideal college", "ideal", "college", "campus", "kakinada college",
    "vidyuth nagar", "arts and sciences", "naac", "andhra university",
    "adikavi nannaya", "affiliation", "accreditation",
    # people — all names and roles explicitly listed
    "principal", "vice principal", "hod", "head of department",
    "faculty", "staff", "teacher", "professor",
    "director", "academic director", "administrative director",
    "satyanarayana", "ranjith", "vasu", "kama raju",
    "exam incharge", "suresh kumar",
    # academics
    "course", "courses", "bca", "bsc", "bba", "mca", "msc",
    "b.sc", "m.sc", "agriculture", "fisheries", "aqua",
    "food technology", "fsn", "computer science",
    "duration", "subjects", "syllabus",
    "ug", "pg", "undergraduate", "postgraduate", "stream",
    # fees
    "fee", "fees", "fee structure", "tuition", "ఫీజు", "annual fee",
    # admissions
    "admission", "admissions", "apply", "eligibility", "documents",
    "application", "join", "enroll", "intake",
    # hostel
    "hostel", "accommodation", "hostel fee", "boys hostel", "girls hostel",
    "mess", "హాస్టల్",
    # facilities
    "library", "lab", "labs", "laboratory", "wifi", "wi-fi",
    "playground", "cafeteria", "cctv", "parking", "auditorium",
    "ro water", "canteen",
    # transport
    "bus", "transport", "bus facility", "vehicle",
    # placements
    "placement", "placements", "placed", "selected", "company", "companies",
    "drives", "recruit", "package", "campus drive",
    "tech mahindra", "sutherland", "tcs", "infosys",
    # rules / exams
    "timing", "timings", "hours", "attendance", "exam", "examination",
    "uniform", "rules", "ragging", "schedule",
    # scholarships / sports
    "scholarship", "scholarships", "financial aid",
    "sports", "nss", "ncc", "cultural", "cricket", "volleyball",
    # history
    "established", "founded", "history", "founders",
    # Telugu script
    "కళాశాల", "కాలేజీ", "ఐడియల్", "కోర్సు", "కోర్సులు",
    "ఫీజు", "అడ్మిషన్", "హాస్టల్", "ప్రిన్సిపల్",
    "లైబ్రరీ", "ప్లేస్‌మెంట్", "సౌకర్యాలు", "సమయం",
    "సిబ్బంది", "ఫ్యాకల్టీ", "డైరెక్టర్",
]
 
# Romanized Telugu college phrases — weighted 2x in scoring
ROMAN_TELUGU_COLLEGE = [
    "college gurunchi", "fee enti", "fee ela", "fee cheppandi",
    "hostel enti", "hostel fee", "principal evaru", "hod evaru",
    "courses emi", "courses enti", "admission ela", "admission kosam",
    "placements enti", "placements ela", "library gurunchi",
    "timing enti", "time enti", "scholarship undi", "facilities emi",
    "rules emi", "attendance enti",
    "director evaru", "ranjith evaru", "vasu evaru",
    "academic director evaru", "administrative director evaru",
]
 
# ── Weather keywords ───────────────────────────────────────────────────────
WEATHER_KEYWORDS = [
    "weather", "temperature", "climate", "rain", "rainfall", "forecast",
    "humidity", "wind speed", "sunny", "cloudy", "storm",
    "how is weather", "today weather", "current weather", "mausam",
    "వాతావరణం", "ఉష్ణోగ్రత", "వర్షం", "వాతావరణ నివేదిక", "నేటి వాతావరణం",
]
 
# ── News keywords ──────────────────────────────────────────────────────────
NEWS_KEYWORDS = [
    "news", "latest news", "today news", "breaking news", "headlines",
    "latest updates", "current events", "recent news", "top stories",
    "india news", "telugu news",
    "వార్తలు", "తాజా వార్తలు", "నేటి వార్తలు", "బ్రేకింగ్",
]
 
# ── General knowledge / search keywords ───────────────────────────────────
SEARCH_KEYWORDS = [
    "what is", "who is", "who was", "what are", "what was",
    "explain", "define", "meaning of", "tell me about",
    "how does", "how did", "why is", "why was", "when did",
    "where is", "information about", "search", "find",
    "ఏమిటి", "ఎవరు", "గురించి చెప్పు", "వివరణ",
]
 
# ── Detail-request keywords (trigger DETAILED mode) ───────────────────────
DETAIL_KEYWORDS = [
    "explain more", "tell me more", "elaborate", "more details",
    "in detail", "detailed", "full explanation", "describe",
    "why", "how does", "how did",
]
 
# ── Media keywords ─────────────────────────────────────────────────────────
IMAGE_KEYWORDS = [
    "image", "images", "photo", "photos", "campus photos", "gallery",
    "picture", "pictures", "college images",
    "ఫోటోలు", "చిత్రాలు", "క్యాంపస్ ఫోటోలు",
]
 
VIDEO_KEYWORDS = [
    "video", "college video", "virtual tour",
    "వీడియో", "పూర్తి వివరాలు",
]
 
NON_CITY_WORDS = {
    "weather", "report", "reports", "today", "now", "forecast",
    "current", "latest", "here", "there", "please", "temperature",
    "climate", "check", "show", "get", "give", "what", "how",
    "the", "a", "an", "is", "are", "was", "will", "me", "my",
    "your", "our", "their", "tell", "know", "want", "of", "in",
    "at", "for", "about", "and", "or", "humid", "humidity",
    "wind", "sunny", "cloudy", "rain", "cold", "hot",
}
 
 
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
    """Returns True when user explicitly asks for more detail."""
    t = text.lower()
    return any(k in t for k in DETAIL_KEYWORDS)
 
 
def _is_valid_city(word: str) -> bool:
    return bool(word) and len(word) > 1 and word.lower() not in NON_CITY_WORDS
 
 
def extract_city_from_weather(msg: str) -> str:
    msg_clean = msg.strip()
 
    # Pattern 1: "weather in Kakinada" / "weather of Delhi"
    prep = re.search(
        r'\b(?:in|at|of|for)\s+([A-Za-z][A-Za-z ]{1,30}?)'
        r'(?:\s*(?:\?|$|today|now|please|weather|forecast|report)|\s*$)',
        msg_clean, re.IGNORECASE,
    )
    if prep:
        candidate = prep.group(1).strip().strip("?.!, ")
        city_words = [w for w in candidate.split() if _is_valid_city(w)]
        if city_words:
            return " ".join(city_words)
 
    # Pattern 2: "Kakinada weather"
    before = re.search(r'^([A-Za-z][A-Za-z ]{1,25}?)\s+weather', msg_clean, re.IGNORECASE)
    if before:
        candidate = before.group(1).strip()
        city_words = [w for w in candidate.split() if _is_valid_city(w)]
        if city_words:
            return " ".join(city_words)
 
    # Pattern 3: explicit construction patterns
    for pat in [
        r"weather\s+(?:of|in|at|for)\s+([A-Za-z][A-Za-z ]{1,25})",
        r"temperature\s+(?:in|at|of)\s+([A-Za-z][A-Za-z ]{1,25})",
        r"climate\s+(?:of|in|at)\s+([A-Za-z][A-Za-z ]{1,25})",
    ]:
        m = re.search(pat, msg_clean, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip().strip("?.!, ")
            city_words = [w for w in candidate.split() if _is_valid_city(w)]
            if city_words:
                return " ".join(city_words)
 
    # Pattern 4: first valid non-weather word
    words = msg_clean.split()
    wx_idx = {i for i, w in enumerate(words)
               if w.lower() in ("weather", "temperature", "climate", "forecast")}
    for i, w in enumerate(words):
        cleaned = w.strip("?.!,")
        if _is_valid_city(cleaned) and i not in wx_idx and (i - 1) not in wx_idx:
            return cleaned
 
    return "Kakinada"
 
 
def classify_intent(message: str) -> Dict:
    msg = (message or "").lower().strip()
 
    # Media always wins
    if any(k in msg for k in IMAGE_KEYWORDS):
        return {"intent": "images"}
    if any(k in msg for k in VIDEO_KEYWORDS):
        return {"intent": "video"}
 
    # Score all intents
    weather_score = sum(1 for k in WEATHER_KEYWORDS if k in msg)
    news_score    = sum(1 for k in NEWS_KEYWORDS    if k in msg)
    search_score  = sum(1 for k in SEARCH_KEYWORDS  if k in msg)
    college_score = sum(1 for k in COLLEGE_KEYWORDS if k in msg)
    college_score += sum(2 for k in ROMAN_TELUGU_COLLEGE if k in msg)
 
    # Weather wins unless college clearly dominates
    if weather_score >= 1 and college_score <= weather_score:
        return {"intent": "weather", "city": extract_city_from_weather(message)}
 
    # News wins only when no college intent
    if news_score >= 1 and college_score == 0:
        return {"intent": "news"}
 
    # College
    if college_score >= 1:
        return {"intent": "college"}
 
    # General knowledge
    if search_score >= 1:
        return {"intent": "search"}
 
    # News fallback
    if news_score >= 1:
        return {"intent": "news"}
 
    return {"intent": "general"}