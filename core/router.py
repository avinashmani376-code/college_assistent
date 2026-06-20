
"""
core/router.py
 
Intelligent request routing:
  college   → College DB → AI explanation
  search    → Tavily → Wikipedia → DDG → AI fallback
  weather   → Weather service
  news      → News service
  images    → Static media
  video     → Static media
  general   → Tavily → AI (with memory context)
  apply     → Save admission enquiry to DB
"""
 
import logging
from flask import Blueprint, request, jsonify
 
from core.intent import classify_intent, detect_language
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
 
 
def _session_id(req) -> str:
    return req.remote_addr or "default"
 
 
def _search_failed(text: str) -> bool:
    if not text or not text.strip():
        return True
    low = text.lower()
    return any(p in low for p in [
        "couldn't find", "rephrase your question", "సంబంధిత సమాచారం", "no information",
    ])
 
 
def _summarize_via_ai(user_message: str, search_context: str, history, lang: str) -> str:
    """Turn raw search context into a teacher-style student-friendly answer."""
    if lang == "te":
        prompt = (
            f"విద్యార్థి ప్రశ్న: {user_message}\n\n"
            f"వెతికిన సమాచారం:\n{search_context}\n\n"
            "పై సమాచారాన్ని తెలుగులో స్పష్టంగా, సరళంగా ఒక teacher వలె వివరించండి."
        )
    else:
        prompt = (
            f"A student asked: {user_message}\n\n"
            f"Search results:\n{search_context}\n\n"
            "Please provide a clear, student-friendly explanation based on these results. "
            "Explain like a teacher would — do not repeat raw snippets."
        )
    return query_ai(prompt=prompt, history=history, lang=lang, mode="general")
 
 
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
 
        # ── IMAGES ────────────────────────────────────────────────────────
        if intent == "images":
            reply = (
                "Here are campus photos of Ideal College."
                if lang == "en"
                else "ఇవి ఐడియల్ కాలేజ్ క్యాంపస్ ఫోటోలు."
            )
            save_memory(user_message, reply, intent="images", lang=lang, session_id=session_id)
            return jsonify({**BASE, "reply": reply, "show_images": True, "images": IMAGE_PATHS})
 
        # ── VIDEO ─────────────────────────────────────────────────────────
        if intent == "video":
            reply = (
                "Here is the full college explanation video."
                if lang == "en"
                else "ఇది కాలేజీ పూర్తి వివరాల వీడియో."
            )
            save_memory(user_message, reply, intent="video", lang=lang, session_id=session_id)
            return jsonify({**BASE, "reply": reply, "show_video": True, "video_url": VIDEO_PATH})
 
        # ── WEATHER ───────────────────────────────────────────────────────
        if intent == "weather":
            city  = intent_data.get("city", "Kakinada")
            reply = get_weather(city, lang=lang)
            save_memory(user_message, reply, intent="weather", lang=lang, session_id=session_id)
            return jsonify({**BASE, "reply": reply})
 
        # ── NEWS ──────────────────────────────────────────────────────────
        if intent == "news":
            articles, _ = fetch_news(user_message)
            reply       = summarize_news(articles, lang=lang)
            save_memory(user_message, reply, intent="news", lang=lang, session_id=session_id)
            return jsonify({**BASE, "reply": reply})
 
        # ── COLLEGE ───────────────────────────────────────────────────────
        if intent == "college":
            # Step 1: local database (fast, accurate)
            local_answer = get_college_answer(user_message, lang=lang, explain=True)
            if local_answer:
                save_memory(user_message, local_answer, intent="college", lang=lang, session_id=session_id)
                return jsonify({**BASE, "reply": local_answer})
 
            # Step 2: AI with full college context + memory
            college_context = get_college_context()
            memory_ctx      = get_recent_context(session_id=session_id)
            full_context    = college_context
            if memory_ctx:
                full_context += f"\n\nRecent conversation:\n{memory_ctx}"
            ai_reply = query_ai(
                prompt=user_message, history=history, lang=lang,
                context=full_context, mode="college",
            )
            save_memory(user_message, ai_reply, intent="college", lang=lang, session_id=session_id)
            return jsonify({**BASE, "reply": ai_reply})
 
        # ── SEARCH (explicit "what is X", "explain X" etc.) ──────────────
        if intent == "search":
            # Step 1: Tavily → AI summarization
            search_context = search_and_get_context(user_message, max_results=5)
            if search_context:
                ai_reply = _summarize_via_ai(user_message, search_context, history, lang)
                save_memory(user_message, ai_reply, intent="search", lang=lang, session_id=session_id)
                return jsonify({**BASE, "reply": ai_reply})
 
            # Step 2: Wikipedia + DuckDuckGo
            web_reply = search_and_format(user_message, lang=lang)
            if not _search_failed(web_reply):
                save_memory(user_message, web_reply, intent="search", lang=lang, session_id=session_id)
                return jsonify({**BASE, "reply": web_reply})
 
            # Step 3: AI direct (uses its training knowledge)
            memory_ctx = get_recent_context(session_id=session_id)
            context    = f"Recent conversation:\n{memory_ctx}" if memory_ctx else ""
            ai_reply   = query_ai(
                prompt=user_message, history=history, lang=lang,
                context=context, mode="general",
            )
            save_memory(user_message, ai_reply, intent="search", lang=lang, session_id=session_id)
            return jsonify({**BASE, "reply": ai_reply})
 
        # ── GENERAL ───────────────────────────────────────────────────────
        # Try Tavily first for general questions too (e.g. "who is AP CM?")
        search_context = search_and_get_context(user_message, max_results=3)
        if search_context:
            ai_reply = _summarize_via_ai(user_message, search_context, history, lang)
            save_memory(user_message, ai_reply, intent="general", lang=lang, session_id=session_id)
            return jsonify({**BASE, "reply": ai_reply})
 
        # Fallback: pure AI with memory
        memory_ctx = get_recent_context(session_id=session_id)
        context    = f"Recent conversation:\n{memory_ctx}" if memory_ctx else ""
        ai_reply   = query_ai(
            prompt=user_message, history=history, lang=lang,
            context=context, mode="general",
        )
        save_memory(user_message, ai_reply, intent="general", lang=lang, session_id=session_id)
        return jsonify({**BASE, "reply": ai_reply})
 
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
        cleaned = []
        for a in articles[:6]:
            title  = (a.get("title")  or "").strip()
            url    = (a.get("url")    or "").strip()
            source = (a.get("source") or "").strip()
            if title:
                cleaned.append({"title": title, "url": url, "source": source})
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
        if not phone or not phone.replace("+", "").replace("-", "").replace(" ", "").isdigit():
            errors["phone"] = "Valid phone number is required."
        if not course:
            errors["course"] = "Course selection is required."
        if errors:
            return jsonify({"success": False, "errors": errors}), 400
 
        row_id = save_admission(
            name=name, phone=phone, course=course,
            email=email, message=message,
        )
        if row_id == -1:
            return jsonify({
                "success": False,
                "message": "Could not save enquiry. Please try again.",
            }), 500
 
        lang = detect_language(name + " " + message)
        if lang == "te":
            reply = (
                f"ధన్యవాదాలు {name}! మీ enquiry (ID: #{row_id}) అందింది. "
                f"{course} కోర్సు గురించి మా team త్వరలో మీకు call చేస్తుంది."
            )
        else:
            reply = (
                f"Thank you {name}! Your enquiry (ID: #{row_id}) has been received. "
                f"Our team will call you soon regarding the {course} course."
            )
        return jsonify({"success": True, "id": row_id, "message": reply}), 201
 
    except Exception as exc:
        logger.exception("Apply route failed: %s", exc)
        return jsonify({
            "success": False,
            "message": "Something went wrong. Please try again.",
        }), 500
 