
"""
core/router.py
 
Routing:
  college → DB → (AI only if DB misses)
  weather → weather_service
  news    → news_service  (NO Tavily, NO AI)
  search/general → smart: Groq direct for static facts, Tavily only for fresh info
 
Smart Tavily logic:
  "What is AI?" "Who is Narendra Modi?" → Groq directly (fast, no web call)
  "Who is AP CM?" "Latest events" → Tavily → Groq
"""
import sys
import logging
from flask import Blueprint, request, jsonify
 
from core.intent import classify_intent, detect_language, is_detail_request
from services.college_service import get_college_answer, get_college_context
from services.weather_service import get_weather
from services.news_service import fetch_news, summarize_news
from services.search_service import search_and_format
from services.llm_service import query_ai
from services.memory_service import save_memory, get_recent_context, save_admission
from services.tavily_service import search_and_get_context
 
IMAGE_PATHS = ["/static/media/1.png", "/static/media/2.png"]
VIDEO_PATH  = "/static/media/college.mp4"
 
logger = logging.getLogger(__name__)
router = Blueprint("router", __name__)
 
BASE = {
    "show_images": False,
    "images":      [],
    "show_video":  False,
    "video_url":   "",
    "source":      "",
}
 
# ── Static knowledge: Groq already knows these — no Tavily needed ──────────
_STATIC_TRIGGERS = [
    "what is", "what are", "define", "meaning of",
    "explain what", "what does", "explain", "describe",
]
 
_KNOWN_STATIC = [
    # Technology
    "ai", "artificial intelligence", "machine learning", "deep learning",
    "neural network", "blockchain", "cloud computing", "internet of things",
    "python", "java", "javascript", "html", "css", "sql", "database",
    "algorithm", "data structure", "operating system", "computer",
    "programming", "software", "hardware", "internet", "network",
    "cybersecurity", "encryption", "virus", "malware", "api", "oop",
    "big data", "data science", "computer vision", "nlp",
    # Science
    "solar system", "photosynthesis", "gravity", "atom", "dna",
    "evolution", "relativity", "quantum", "black hole", "galaxy",
    "electricity", "magnetism", "thermodynamics", "cell", "genetics",
    # Social
    "democracy", "communism", "capitalism", "economics", "constitution",
    "parliament", "judiciary", "globalization", "inflation", "gdp",
]
 
_FAMOUS_PEOPLE = [
    "narendra modi", "elon musk", "bill gates", "steve jobs",
    "mark zuckerberg", "jeff bezos", "warren buffett",
    "mahatma gandhi", "jawaharlal nehru", "subhas chandra bose",
    "albert einstein", "isaac newton", "nikola tesla", "thomas edison",
    "shakespeare", "napoleon", "abraham lincoln", "winston churchill",
    "sachin tendulkar", "virat kohli", "ms dhoni", "rohit sharma",
    "amitabh bachchan", "shah rukh khan",
    "apj abdul kalam", "rabindranath tagore", "swami vivekananda",
    "aryabhatta", "chanakya", "dr ambedkar", "br ambedkar",
    "srinivasa ramanujan", "cv raman",
]
 
# Real-time triggers → always use Tavily
_REALTIME_TRIGGERS = [
    "today", "current", "latest", "recent", "now",
    "2024", "2025", "2026",
    "who is cm", "who is pm", "who is president", "who is ceo",
    "who is ap cm", "who is telangana cm", "who is governor",
    "who is minister", "stock", "price", "rate", "score",
    "match result", "election result",
]
 
 
def _needs_tavily(question: str) -> bool:
    """
    Returns True only if fresh web data is actually needed.
    Static facts → False (use Groq directly, faster).
    Real-time/current info → True (use Tavily).
    """
    q = question.lower().strip()
 
    # Explicit real-time signals → always Tavily
    if any(r in q for r in _REALTIME_TRIGGERS):
        return True
 
    # "what is X" / "explain X" with known entity → skip Tavily
    is_static_q = any(t in q for t in _STATIC_TRIGGERS)
    is_known    = any(e in q for e in _KNOWN_STATIC)
    if is_static_q and is_known:
        return False
 
    # "who is [famous person]" → Groq knows them, skip Tavily
    if ("who is" in q or "who was" in q) and any(p in q for p in _FAMOUS_PEOPLE):
        return False
 
    # Default: use Tavily for unknown queries
    return True
 
 
def _sid(req) -> str:
    return req.remote_addr or "default"
 
 
def _empty(text: str) -> bool:
    if not text or not text.strip():
        return True
    return any(p in text.lower() for p in ["couldn't find", "rephrase", "no information"])
 
 
def _general_answer(user_message: str, history, lang: str, detailed: bool) -> str:
    """
    Smart routing:
    - Static knowledge questions → Groq directly (fast, no web call)
    - Fresh/current questions → Tavily → Groq
    ONE AI call total.
    """
    use_tavily = _needs_tavily(user_message)
    print(f"[SEARCH] needs_tavily={use_tavily} for: {user_message!r}", file=sys.stderr)
 
    if not use_tavily:
        # ── Path A: Groq direct (no web search) ───────────────────────────
        print("[SEARCH] Path A: Groq direct (static knowledge)", file=sys.stderr)
        return query_ai(
            prompt=user_message,
            history=history,
            lang=lang,
            mode="general",
            detailed=detailed,
        )
 
    # ── Path B: Tavily → Groq ─────────────────────────────────────────────
    print("[SEARCH] Path B: Tavily → Groq", file=sys.stderr)
    ctx = search_and_get_context(user_message, max_results=3)
 
    if ctx:
        print(f"[SEARCH] Tavily returned {len(ctx)} chars of context", file=sys.stderr)
        if lang == "te":
            prompt = (
                f"ప్రశ్న: {user_message}\n\nసమాచారం:\n{ctx}\n\n"
                + ("వివరంగా వివరించండి." if detailed
                   else "ఒక్క వాక్యంలో సమాధానం ఇవ్వండి.")
            )
        else:
            prompt = (
                f"Question: {user_message}\n\nSearch results:\n{ctx}\n\n"
                + ("Explain thoroughly based on above."
                   if detailed else "Answer in one sentence only.")
            )
        return query_ai(
            prompt=prompt, history=history, lang=lang,
            mode="general", detailed=detailed,
        )
 
    # ── Path B fallback: Wikipedia/DDG ────────────────────────────────────
    print("[SEARCH] Tavily empty — trying Wikipedia/DDG", file=sys.stderr)
    web = search_and_format(user_message, lang=lang)
 
    if not _empty(web):
        print(f"[SEARCH] Wikipedia/DDG returned {len(web)} chars", file=sys.stderr)
        if not detailed and len(web) > 250:
            # Compress long Wikipedia text to 1 sentence
            prompt = (
                f"Question: {user_message}\n\nContext:\n{web}\n\n"
                "Answer in one sentence only."
            )
            return query_ai(
                prompt=prompt, history=history, lang=lang,
                mode="general", detailed=False,
            )
        return web
 
    # ── Final fallback: pure Groq ─────────────────────────────────────────
    print("[SEARCH] All web sources empty — pure Groq", file=sys.stderr)
    return query_ai(
        prompt=user_message, history=history, lang=lang,
        mode="general", detailed=detailed,
    )
 
 
@router.route("/api/chat", methods=["POST"])
def api_chat():
    try:
        data         = request.get_json(silent=True) or {}
        user_message = (data.get("message") or "").strip()
        history      = data.get("history") or []
 
        if not user_message:
            return jsonify({**BASE, "reply": "Please enter a message."}), 400
 
        lang        = detect_language(user_message)
        intent_data = classify_intent(user_message)
        intent      = intent_data.get("intent")
        session_id  = _sid(request)
        detailed    = is_detail_request(user_message)
 
        print(f"\n[ROUTE] msg={user_message!r}", file=sys.stderr)
        print(f"[ROUTE] intent={intent} lang={lang} detailed={detailed}", file=sys.stderr)
 
        # ── IMAGES ─────────────────────────────────────────────────────────
        if intent == "images":
            print("[ROUTE] → images", file=sys.stderr)
            reply = "Here are campus photos." if lang == "en" else "ఇవి క్యాంపస్ ఫోటోలు."
            save_memory(user_message, reply, intent="images", lang=lang, session_id=session_id)
            return jsonify({**BASE, "reply": reply,
                            "show_images": True, "images": IMAGE_PATHS})
 
        # ── VIDEO ──────────────────────────────────────────────────────────
        if intent == "video":
            print("[ROUTE] → video", file=sys.stderr)
            reply = "Here is the college video." if lang == "en" else "ఇది కాలేజీ వీడియో."
            save_memory(user_message, reply, intent="video", lang=lang, session_id=session_id)
            return jsonify({**BASE, "reply": reply,
                            "show_video": True, "video_url": VIDEO_PATH})
 
        # ── WEATHER ────────────────────────────────────────────────────────
        if intent == "weather":
            city = intent_data.get("city", "Kakinada")
            print(f"[ROUTE] → weather city={city!r}", file=sys.stderr)
            reply = get_weather(city, lang=lang)
            save_memory(user_message, reply, intent="weather", lang=lang, session_id=session_id)
            return jsonify({**BASE, "reply": reply})
 
        # ── NEWS — direct fetch, NO AI, NO Tavily ──────────────────────────
        if intent == "news":
            print("[ROUTE] → news", file=sys.stderr)
            articles, provider = fetch_news(user_message)
            print(f"[ROUTE] news: provider={provider} count={len(articles)}", file=sys.stderr)
            reply = summarize_news(articles, lang=lang)
            save_memory(user_message, reply, intent="news", lang=lang, session_id=session_id)
            return jsonify({**BASE, "reply": reply})
 
        # ── COLLEGE — DB first, ONE AI call if miss ────────────────────────
        if intent == "college":
            print("[ROUTE] → college", file=sys.stderr)
            reply = get_college_answer(user_message, lang=lang)
            if reply:
                print(f"[ROUTE] college DB hit ({len(reply)} chars)", file=sys.stderr)
            else:
                print("[ROUTE] college DB miss → AI", file=sys.stderr)
                reply = query_ai(
                    prompt=user_message, history=history, lang=lang,
                    context=get_college_context(), mode="college", detailed=detailed,
                )
            save_memory(user_message, reply, intent="college", lang=lang, session_id=session_id)
            return jsonify({**BASE, "reply": reply})
 
        # ── SEARCH / GENERAL ───────────────────────────────────────────────
        print(f"[ROUTE] → {intent}", file=sys.stderr)
        reply = _general_answer(user_message, history, lang, detailed)
        save_memory(user_message, reply, intent=intent, lang=lang, session_id=session_id)
        return jsonify({**BASE, "reply": reply})
 
    except Exception as exc:
        logger.exception("Chat route failed: %s", exc)
        return jsonify({
            **BASE,
            "reply": "Sorry, something went wrong. Please try again.",
        }), 500
 
 
@router.route("/api/news-sidebar", methods=["GET"])
def news_sidebar():
    try:
        articles, _ = fetch_news("india education latest")
        cleaned = [
            {
                "title":  (a.get("title")  or "").strip(),
                "url":    (a.get("url")    or "").strip(),
                "source": (a.get("source") or "").strip(),
            }
            for a in articles[:6]
            if (a.get("title") or "").strip()
        ]
        return jsonify({"articles": cleaned})
    except Exception:
        return jsonify({"articles": []})
 
 
@router.route("/api/apply", methods=["POST"])
def api_apply():
    try:
        data    = request.get_json(silent=True) or {}
        name    = (data.get("name")    or "").strip()
        phone   = (data.get("phone")   or "").strip()
        course  = (data.get("course")  or "").strip()
        email   = (data.get("email")   or "").strip()
        message = (data.get("message") or "").strip()
 
        errors = {}
        if not name:
            errors["name"] = "Name is required."
        if not phone or not phone.replace("+","").replace("-","").replace(" ","").isdigit():
            errors["phone"] = "Valid phone number is required."
        if not course:
            errors["course"] = "Course selection is required."
        if errors:
            return jsonify({"success": False, "errors": errors}), 400
 
        row_id = save_admission(name=name, phone=phone, course=course,
                                email=email, message=message)
        if row_id == -1:
            return jsonify({"success": False,
                            "message": "Could not save. Please try again."}), 500
 
        lang = detect_language(name + " " + message)
        if lang == "te":
            reply = (f"ధన్యవాదాలు {name}! మీ enquiry (#{row_id}) అందింది. "
                     f"{course} కోర్సు గురించి మా team త్వరలో call చేస్తుంది.")
        else:
            reply = (f"Thank you {name}! Your enquiry (#{row_id}) was received. "
                     f"Our team will contact you soon about the {course} course.")
        return jsonify({"success": True, "id": row_id, "message": reply}), 201
 
    except Exception as exc:
        logger.exception("Apply failed: %s", exc)
        return jsonify({"success": False, "message": "Something went wrong."}), 500
 