import re
from typing import Dict

COLLEGE_KEYWORDS = [
    "college", "about college", "college name", "name of the college", "ideal college",
    "course", "courses", "fee", "fees", "fee structure",
    "admission", "admissions", "hostel", "principal", "vice principal", "contact",
    "facility", "facilities", "campus", "timings", "timing", "naac",
    "placements", "placement", "library", "bca", "bsc", "bba", "mca", "msc",
    "scholarship", "eligibility", "department", "faculty", "lab", "laboratory",
    "andhra university", "vidyuth nagar", "kakinada college", "arts and sciences",
    "hod", "head of department", "staff", "teacher", "professor", "director",
    "కళాశాల", "కోర్సు", "కోర్సులు", "ఫీజు", "అడ్మిషన్", "హాస్టల్",
    "ప్రిన్సిపల్", "లైబ్రరీ", "ప్లేస్‌మెంట్", "సౌకర్యాలు", "సమయం"
]

WEATHER_KEYWORDS = [
    "weather", "weather report", "weather of", "weather in", "weather at",
    "temperature", "climate", "rain", "rainfall", "forecast", "humidity",
    "wind", "sunny", "cloudy", "storm", "hot", "cold", "how is weather",
    "today weather", "current weather", "mausam",
    "వాతావరణం", "ఉష్ణోగ్రత", "వర్షం", "వాతావరణ నివేదిక",
    "ఎలా ఉంది వాతావరణం", "నేటి వాతావరణం"
]

NEWS_KEYWORDS = [
    "news", "latest news", "today news", "breaking news", "headlines",
    "latest", "update", "updates", "current events", "today", "recent",
    "what happened", "happenings", "top stories", "india news",
    "వార్తలు", "తాజా వార్తలు", "తాజా అప్‌డేట్స్", "నేటి వార్తలు", "బ్రేకింగ్"
]

SEARCH_KEYWORDS = [
    "search", "find", "what is", "who is", "tell me about", "explain",
    "internet", "web", "google", "look up", "information about",
    "how does", "why is", "when did", "define", "meaning of",
    "వెతకు", "చెప్పు", "ఏమిటి", "ఎవరు", "గురించి చెప్పు"
]

IMAGE_KEYWORDS = [
    "image", "images", "photo", "photos", "campus photos", "gallery",
    "picture", "pictures", "show me", "college images",
    "ఫోటోలు", "చిత్రాలు", "క్యాంపస్ ఫోటోలు"
]

VIDEO_KEYWORDS = [
    "video", "full details", "full explanation", "explain college",
    "college video", "tour", "virtual tour",
    "వీడియో", "పూర్తి వివరాలు", "వివరణ"
]

NON_CITY_WORDS = {
    "weather", "report", "repoet", "repot", "reports", "today", "now",
    "forecast", "current", "latest", "here", "there", "please",
    "temperature", "climate", "check", "show", "get", "give",
    "what", "how", "the", "a", "an", "is", "are", "was", "will",
    "me", "my", "your", "our", "their", "tell", "know", "want",
    "of", "in", "at", "for", "about", "and", "or", "please",
    "humid", "humidity", "wind", "sunny", "cloudy", "rain", "cold", "hot"
}


def detect_language(text: str) -> str:
    if not text:
        return "en"
    telugu_chars = sum(1 for ch in text if "\u0C00" <= ch <= "\u0C7F")
    total = max(len(text.replace(" ", "")), 1)
    if telugu_chars / total > 0.08:
        return "te"
    roman_telugu = {"nenu", "meeru", "kavali", "cheppu", "undi", "ledu", "anni", "emi", "ela", "enduku"}
    words = set(re.findall(r"[a-zA-Z]+", text.lower()))
    if words & roman_telugu:
        return "te"
    return "en"


def _is_valid_city(word: str) -> bool:
    return bool(word) and len(word) > 1 and word.lower() not in NON_CITY_WORDS


def extract_city_from_weather(msg: str) -> str:
    msg_clean = msg.strip()

    # Priority 1: "in/at/of/for <city>" — most reliable
    prep_match = re.search(
        r'\b(?:in|at|of|for)\s+([a-zA-Z][a-zA-Z ]{1,30}?)(?:\s*(?:\?|$|today|now|please|weather|forecast|report)|\s*$)',
        msg_clean, re.IGNORECASE
    )
    if prep_match:
        candidate = prep_match.group(1).strip().strip("?.!, ")
        city_words = [w for w in candidate.split() if _is_valid_city(w)]
        if city_words:
            return " ".join(city_words)

    # Priority 2: "<city> weather"
    city_before = re.search(
        r'^([a-zA-Z][a-zA-Z ]{1,25}?)\s+weather',
        msg_clean, re.IGNORECASE
    )
    if city_before:
        candidate = city_before.group(1).strip()
        city_words = [w for w in candidate.split() if _is_valid_city(w)]
        if city_words:
            return " ".join(city_words)

    # Priority 3: other patterns
    patterns = [
        r"weather\s+(?:of|in|at|for)\s+([a-zA-Z][a-zA-Z ]{1,25})",
        r"temperature\s+(?:in|at|of)\s+([a-zA-Z][a-zA-Z ]{1,25})",
        r"climate\s+(?:of|in|at)\s+([a-zA-Z][a-zA-Z ]{1,25})",
    ]
    for pat in patterns:
        m = re.search(pat, msg_clean, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip().strip("?.!, ")
            city_words = [w for w in candidate.split() if _is_valid_city(w)]
            if city_words:
                return " ".join(city_words)

    # Priority 4: scan words, pick first valid non-weather word
    words = msg_clean.split()
    weather_indices = {i for i, w in enumerate(words) if w.lower() in ("weather", "temperature", "climate", "forecast")}
    for i, w in enumerate(words):
        cleaned = w.strip("?.!,")
        if _is_valid_city(cleaned) and i not in weather_indices and (i - 1) not in weather_indices:
            return cleaned

    return "Kakinada"


def classify_intent(message: str) -> Dict:
    msg = (message or "").lower().strip()

    if any(k in msg for k in IMAGE_KEYWORDS):
        return {"intent": "images"}
    if any(k in msg for k in VIDEO_KEYWORDS):
        return {"intent": "video"}

    weather_score = sum(1 for k in WEATHER_KEYWORDS if k in msg)
    if weather_score >= 1:
        return {"intent": "weather", "city": extract_city_from_weather(message)}

    news_score = sum(1 for k in NEWS_KEYWORDS if k in msg)
    if news_score >= 1:
        return {"intent": "news"}

    college_score = sum(1 for k in COLLEGE_KEYWORDS if k in msg)
    if college_score >= 1:
        return {"intent": "college"}

    search_score = sum(1 for k in SEARCH_KEYWORDS if k in msg)
    if search_score >= 1:
        return {"intent": "search"}

    return {"intent": "general"}