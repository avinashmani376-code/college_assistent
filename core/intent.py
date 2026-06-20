
# core/intent.py
import re
from typing import Dict
 
# ── College keywords (English + Telugu script) ────────────────────────────
COLLEGE_KEYWORDS = [
    # identity
    "ideal college", "ideal", "college", "campus", "kakinada college",
    "vidyuth nagar", "arts and sciences", "naac", "andhra university",
    "adikavi nannaya", "affiliation", "accreditation",
    # people
    "principal", "vice principal", "computer science hod", "computer science head of department ",
    "faculty", "staff", "teacher", "professor", "director",
    "satyanarayana", "ranjith", "vasu", "kama raju","academic director", "administrative director",
    " agriculture head of the department", "agriculture hod","fisheries hod","bba hod","agriculture head of the department"
    "bba head of the department","food technology head of the department","food technology hod",
    # academics
    "course", "courses", "bca", "bsc", "bba", "mca", "msc",
    "b.sc", "m.sc", "agriculture", "fisheries", "aqua",
    "food technology", "fsn", "computer science", "ai course",
    "artificial intelligence course", "duration", "subjects",
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
    "drives", "recruit", "package", "job", "campus drive", "tech mahindra",
    "sutherland", "tcs", "infosys",
    # rules / exams
    "timing", "timings", "hours", "attendance", "exam", "examination",
    "uniform", "rules", "ragging", "schedule",
    # scholarships
    "scholarship", "scholarships", "financial aid",
    # sports / activities
    "sports", "nss", "ncc", "cultural", "cricket", "volleyball",
    # history
    "established", "founded", "history", "founders",
    # Telugu script
    "కళాశాల", "కాలేజీ", "ఐడియల్", "కోర్సు", "కోర్సులు",
    "ఫీజు", "అడ్మిషన్", "హాస్టల్", "ప్రిన్సిపల్",
    "లైబ్రరీ", "ప్లేస్‌మెంట్", "సౌకర్యాలు", "సమయం",
    "సిబ్బంది", "ఫ్యాకల్టీ",
]
 
# ── Romanized Telugu college phrases ─────────────────────────────────────
ROMAN_TELUGU_COLLEGE = [
    "college gurunchi", "college guri", "fee enti", "fee ela", "fee cheppandi",
    "hostel enti", "hostel fee", "principal evaru", "hod evaru",
    "courses emi", "courses enti", "admission ela", "admission kosam",
    "placements enti", "placements ela", "library gurunchi", "bus facility",
    "timing enti", "time enti", "scholarship undi", "facilities emi",
    "rules emi", "attendance enti",
]
 
# ── Weather keywords ──────────────────────────────────────────────────────
WEATHER_KEYWORDS = [
    "weather", "weather report", "weather of", "weather in", "weather at",
    "temperature", "climate", "rain", "rainfall", "forecast", "humidity",
    "wind speed", "sunny", "cloudy", "storm", "hot weather", "cold weather",
    "how is weather", "today weather", "current weather", "mausam","weather report of",
    "వాతావరణం", "ఉష్ణోగ్రత", "వర్షం", "వాతావరణ నివేదిక",
    "నేటి వాతావరణం",
]
 
# ── News keywords ─────────────────────────────────────────────────────────
NEWS_KEYWORDS = [
    "news", "latest news", "today news", "breaking news", "headlines",
    "latest updates", "current events", "recent news", "what happened",
    "top stories", "india news", "telugu news",
    "వార్తలు", "తాజా వార్తలు", "నేటి వార్తలు", "బ్రేకింగ్",
]
 
# ── Search / general-knowledge keywords ──────────────────────────────────
SEARCH_KEYWORDS = [
    "what is", "who is", "who was", "what are", "what was",
    "explain", "define", "meaning of", "tell me about",
    "how does", "how did", "why is", "why was", "when did",
    "where is", "information about", "details about",
    "search", "find", "internet", "google", "look up",
    "ఏమిటి", "ఎవరు", "గురించి చెప్పు", "వివరణ",
]
 
# ── Media keywords ────────────────────────────────────────────────────────
IMAGE_KEYWORDS = [
    "image", "images", "photo", "photos", "campus photos", "gallery",
    "picture", "pictures", "show me", "college images","campus images",
    "ఫోటోలు", "చిత్రాలు", "క్యాంపస్ ఫోటోలు",
]
 
VIDEO_KEYWORDS = [
    "video", "full details", "full explanation", "explain college",
    "college video", "tour", "virtual tour","campus video",
    "వీడియో", "పూర్తి వివరాలు",
]
 
# ── Words that are NOT city names ─────────────────────────────────────────
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
    # Romanized Telugu indicators
    roman_te = {
        "nenu", "meeru", "kavali", "cheppu", "undi", "ledu", "anni",
        "emi", "ela", "enduku", "enti", "evaru", "gurunchi", "kosam",
        "cheyyi", "cheyandi", "cheppandi", "okka", "anni", "ledhu",
    }
    words = set(re.findall(r"[a-zA-Z]+", text.lower()))
    if words & roman_te:
        return "te"
    return "en"
 
 
def _is_valid_city(word: str) -> bool:
    return bool(word) and len(word) > 1 and word.lower() not in NON_CITY_WORDS
 
 
def extract_city_from_weather(msg: str) -> str:
    msg_clean = msg.strip()
 
    # "in/at/of/for <city>"
    prep_match = re.search(
        r'\b(?:in|at|of|for)\s+([a-zA-Z][a-zA-Z ]{1,30}?)'
        r'(?:\s*(?:\?|$|today|now|please|weather|forecast|report)|\s*$)',
        msg_clean, re.IGNORECASE,
    )
    if prep_match:
        candidate = prep_match.group(1).strip().strip("?.!, ")
        city_words = [w for w in candidate.split() if _is_valid_city(w)]
        if city_words:
            return " ".join(city_words)
 
    # "<city> weather"
    city_before = re.search(
        r'^([a-zA-Z][a-zA-Z ]{1,25}?)\s+weather',
        msg_clean, re.IGNORECASE,
    )
    if city_before:
        candidate = city_before.group(1).strip()
        city_words = [w for w in candidate.split() if _is_valid_city(w)]
        if city_words:
            return " ".join(city_words)
 
    for pat in [
        r"weather\s+(?:of|in|at|for)\s+([a-zA-Z][a-zA-Z ]{1,25})",
        r"temperature\s+(?:in|at|of)\s+([a-zA-Z][a-zA-Z ]{1,25})",
        r"climate\s+(?:of|in|at)\s+([a-zA-Z][a-zA-Z ]{1,25})",
    ]:
        m = re.search(pat, msg_clean, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip().strip("?.!, ")
            city_words = [w for w in candidate.split() if _is_valid_city(w)]
            if city_words:
                return " ".join(city_words)
 
    words = msg_clean.split()
    weather_idx = {
        i for i, w in enumerate(words)
        if w.lower() in ("weather", "temperature", "climate", "forecast")
    }
    for i, w in enumerate(words):
        cleaned = w.strip("?.!,")
        if _is_valid_city(cleaned) and i not in weather_idx and (i - 1) not in weather_idx:
            return cleaned
 
    return "Kakinada"
 
 
def classify_intent(message: str) -> Dict:
    msg = (message or "").lower().strip()
 
    # ── Hard-coded media checks (always first) ───────────────────────────
    if any(k in msg for k in IMAGE_KEYWORDS):
        return {"intent": "images"}
    if any(k in msg for k in VIDEO_KEYWORDS):
        return {"intent": "video"}
 
    # ── Score every intent ───────────────────────────────────────────────
    weather_score = sum(1 for k in WEATHER_KEYWORDS if k in msg)
    news_score    = sum(1 for k in NEWS_KEYWORDS    if k in msg)
    search_score  = sum(1 for k in SEARCH_KEYWORDS  if k in msg)
 
    # College: keyword match OR romanized Telugu college phrase
    college_score = sum(1 for k in COLLEGE_KEYWORDS        if k in msg)
    college_score += sum(2 for k in ROMAN_TELUGU_COLLEGE   if k in msg)  # weight higher
 
    # ── Weather: needs at least one clear weather term ───────────────────
    if weather_score >= 1:
        # But don't steal "weather course" type college queries
        if college_score > weather_score:
            pass  # fall through to college check below
        else:
            return {"intent": "weather", "city": extract_city_from_weather(message)}
 
    # ── News ─────────────────────────────────────────────────────────────
    if news_score >= 1 and college_score == 0:
        return {"intent": "news"}
 
    # ── College: wins if score > 0 ───────────────────────────────────────
    if college_score >= 1:
        return {"intent": "college"}
 
    # ── General knowledge question ("what is X", "explain X") ────────────
    if search_score >= 1:
        return {"intent": "search"}
 
    # ── News fallback (e.g. "latest" alone) ─────────────────────────────
    if news_score >= 1:
        return {"intent": "news"}
 
    return {"intent": "general"}
 