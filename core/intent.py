# core/intent.py
import re
from typing import Dict
 
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
    "sports", "nss", "ncc", "cultural", "cricket", "volleyball",
    "established", "founded", "history",
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
 
WEATHER_KEYWORDS = [
    "weather", "temperature", "climate", "rain", "rainfall", "forecast",
    "humidity", "wind speed", "sunny", "cloudy", "storm",
    "today weather", "current weather", "mausam",
    "వాతావరణం", "ఉష్ణోగ్రత", "వర్షం", "నేటి వాతావరణం",
]
 
NEWS_KEYWORDS = [
    "news", "latest news", "today news", "breaking news", "headlines",
    "latest updates", "current events", "recent news", "top stories",
    "india news", "telugu news", "current affairs", "affairs",
    "వార్తలు", "తాజా వార్తలు", "నేటి వార్తలు", "బ్రేకింగ్",
]
 
SEARCH_KEYWORDS = [
    "what is", "who is", "who was", "what are", "what was",
    "explain", "define", "meaning of", "tell me about", "tell me more about",
    "how does", "how did", "why is", "why was", "when did",
    "where is", "information about", "search", "find",
    "ఏమిటి", "ఎవరు", "గురించి చెప్పు", "వివరణ",
]
 
# Detail request: user wants long answer
DETAIL_KEYWORDS = [
    "explain more", "tell me more", "elaborate", "more details",
    "in detail", "detailed explanation", "full explanation",
    "describe in detail", "explain everything",
]
 
IMAGE_KEYWORDS = [
    "image", "images", "photo", "photos", "campus photos", "gallery",
    "picture", "pictures", "college images",
    "ఫోటోలు", "చిత్రాలు",
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
    """True when user explicitly asks for more detail."""
    t = text.lower()
    return any(k in t for k in DETAIL_KEYWORDS)
 
 
def _is_valid_city(word: str) -> bool:
    return bool(word) and len(word) > 1 and word.lower() not in NON_CITY_WORDS
 
 
def extract_city_from_weather(msg: str) -> str:
    c = msg.strip()
    # "weather in Kakinada"
    m = re.search(
        r'\b(?:in|at|of|for)\s+([A-Za-z][A-Za-z ]{1,30}?)'
        r'(?:\s*(?:\?|$|today|now|please|weather|forecast)|\s*$)',
        c, re.IGNORECASE,
    )
    if m:
        cw = [w for w in m.group(1).strip().strip("?.!, ").split() if _is_valid_city(w)]
        if cw:
            return " ".join(cw)
    # "Kakinada weather"
    m2 = re.search(r'^([A-Za-z][A-Za-z ]{1,25}?)\s+weather', c, re.IGNORECASE)
    if m2:
        cw = [w for w in m2.group(1).strip().split() if _is_valid_city(w)]
        if cw:
            return " ".join(cw)
    # Other patterns
    for pat in [
        r"weather\s+(?:of|in|at|for)\s+([A-Za-z][A-Za-z ]{1,25})",
        r"temperature\s+(?:in|at|of)\s+([A-Za-z][A-Za-z ]{1,25})",
    ]:
        m3 = re.search(pat, c, re.IGNORECASE)
        if m3:
            cw = [w for w in m3.group(1).strip().strip("?.!, ").split() if _is_valid_city(w)]
            if cw:
                return " ".join(cw)
    # Scan words
    words = c.split()
    wx = {i for i, w in enumerate(words)
          if w.lower() in ("weather", "temperature", "climate", "forecast")}
    for i, w in enumerate(words):
        clean = w.strip("?.!,")
        if _is_valid_city(clean) and i not in wx and (i - 1) not in wx:
            return clean
    return "Kakinada"
 
 
def classify_intent(message: str) -> Dict:
    msg = (message or "").lower().strip()
 
    if any(k in msg for k in IMAGE_KEYWORDS):
        return {"intent": "images"}
    if any(k in msg for k in VIDEO_KEYWORDS):
        return {"intent": "video"}
 
    weather_score = sum(1 for k in WEATHER_KEYWORDS if k in msg)
    news_score    = sum(1 for k in NEWS_KEYWORDS    if k in msg)
    search_score  = sum(1 for k in SEARCH_KEYWORDS  if k in msg)
    college_score = sum(1 for k in COLLEGE_KEYWORDS if k in msg)
    college_score += sum(2 for k in ROMAN_TELUGU_COLLEGE if k in msg)
 
    if weather_score >= 1 and college_score <= weather_score:
        return {"intent": "weather", "city": extract_city_from_weather(message)}
 
    if news_score >= 1 and college_score == 0:
        return {"intent": "news"}
 
    if college_score >= 1:
        return {"intent": "college"}
 
    if search_score >= 1:
        return {"intent": "search"}
 
    if news_score >= 1:
        return {"intent": "news"}
 
    return {"intent": "general"}
 