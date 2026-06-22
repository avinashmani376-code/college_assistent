"""
core/router.py
 
Routing logic:
  college → DB (no AI unless DB misses) → ONE AI call max
  weather → weather_service directly
  news    → news_service directly (NOT Tavily, NOT AI)
  search  → Tavily → Wikipedia/DDG → AI  (ONE call)
  general → Tavily → AI  (ONE call)
  images/video → static
 
SHORT MODE by default (1-2 sentences).
DETAILED MODE only when user asks "explain more", "tell me more", etc.
ONE AI call per request maximum.
"""
 
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
 
logger    = logging.getLogger(__name__)
router    = Blueprint("router", __name__)
 
BASE = {
    "show_images": False,
    "images":      [],
    "show_video":  False,
    "video_url":   "",
    "source":      "",
}
 
 
def _session_id(req) -> str:
    return req.remote_addr or "default"
 
 
def _search_empty(text: str) -> bool:
    if not text or not text.strip():
        return True
    low = text.lower()
    return any(p in low for p in [
        "couldn't find", "rephrase", "సంబంధిత సమాచారం", "no information",
    ])
 
 
def _ai_with_search(user_message: str, history, lang: str, detailed: bool) -> str:
    """
    Tavily → Wikipedia/DDG → pure AI.  ONE AI call total.
    """
    # Step 1: Tavily search context
    ctx = search_and_get_context(user_message, max_results=3)
    if ctx:
        if lang == "te":
            prompt = (
                f"ప్రశ్న: {user_message}\n\n"
                f"సమాచారం:\n{ctx}\n\n"
                "పై సమాచారం ఆధారంగా 1-2 వాక్యాలలో సమాధానం ఇవ్వండి."
                if not detailed else
                f"ప్రశ్న: {user_message}\n\nసమాచారం:\n{ctx}\n\nవివరంగా వివరించండి."
            )
        else:
            prompt = (
                f"Question: {user_message}\n\nSearch results:\n{ctx}\n\n"
                "Answer in 1-2 sentences only."
                if not detailed else
                f"Question: {user_message}\n\nSearch results:\n{ctx}\n\n"
                "Explain thoroughly based on the above."
            )
        return query_ai(
            prompt=prompt, history=history, lang=lang,
            mode="general", detailed=detailed,
        )
 
    # Step 2: Wikipedia / DuckDuckGo (free, no key needed)
    web = search_and_format(user_message, lang=lang)
    if not _search_empty(web):
        # web result is already short — return it directly
        return web
 
    # Step 3: Pure AI (no search context)
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
        session_id  = _session_id(request)
        detailed    = is_detail_request(user_message)
 
        # ── IMAGES ────────────────────────────────────────────────────────
        if intent == "images":
            reply = ("Here are campus photos." if lang == "en"
                     else "ఇవి క్యాంపస్ ఫోటోలు.")
            save_memory(user_message, reply, intent="images", lang=lang, session_id=session_id)
            return jsonify({**BASE, "reply": reply, "show_images": True, "images": IMAGE_PATHS})
 
        # ── VIDEO ─────────────────────────────────────────────────────────
        if intent == "video":
            reply = ("Here is the college video." if lang == "en"
                     else "ఇది కాలేజీ వీడియో.")
            save_memory(user_message, reply, intent="video", lang=lang, session_id=session_id)
            return jsonify({**BASE, "reply": reply, "show_video": True, "video_url": VIDEO_PATH})
 
        # ── WEATHER — direct service, NO AI ──────────────────────────────
        if intent == "weather":
            city  = intent_data.get("city", "Kakinada")
            reply = get_weather(city, lang=lang)
            save_memory(user_message, reply, intent="weather", lang=lang, session_id=session_id)
            return jsonify({**BASE, "reply": reply})
 
        # ── NEWS — direct service, NO AI, NO Tavily ───────────────────────
        if intent == "news":
            articles, _ = fetch_news(user_message)
            reply       = summarize_news(articles, lang=lang)
            save_memory(user_message, reply, intent="news", lang=lang, session_id=session_id)
            return jsonify({**BASE, "reply": reply})
 
        # ── COLLEGE — DB first, ONE AI call only if DB misses ─────────────
        if intent == "college":
            reply = get_college_answer(user_message, lang=lang)
            if not reply:
                ctx = get_college_context()
                reply = query_ai(
                    prompt=user_message, history=history, lang=lang,
                    context=ctx, mode="college", detailed=detailed,
                )
            save_memory(user_message, reply, intent="college", lang=lang, session_id=session_id)
            return jsonify({**BASE, "reply": reply})
 
        # ── SEARCH / GENERAL — Tavily → fallback → AI (ONE call max) ──────
        reply = _ai_with_search(user_message, history, lang, detailed)
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
        articles, _ = fetch_news("students education college india latest")
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
                            "message": "Could not save enquiry. Please try again."}), 500
 
        lang = detect_language(name + " " + message)
        if lang == "te":
            reply = (
                f"ధన్యవాదాలు {name}! మీ enquiry (ID: #{row_id}) అందింది. "
                f"{course} కోర్సు గురించి మా team త్వరలో call చేస్తుంది."
            )
        else:
            reply = (
                f"Thank you {name}! Your enquiry (ID: #{row_id}) has been received. "
                f"Our team will call you soon regarding the {course} course."
            )
        return jsonify({"success": True, "id": row_id, "message": reply}), 201
 
    except Exception as exc:
        logger.exception("Apply route failed: %s", exc)
        return jsonify({"success": False,
                        "message": "Something went wrong. Please try again."}), 500