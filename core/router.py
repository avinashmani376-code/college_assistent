
"""
core/router.py
 
Routing:
  college → DB → (AI only if DB misses)
  weather → weather_service
  news    → news_service (NewsData only, NO Tavily, NO AI)
  search/general → Route A (Groq direct) or Route B (Tavily → Groq)
                   Decision made ONCE via _needs_tavily(), ONE AI call total.
 
Route A (Fast — Groq direct, no web):
  "What is AI?", "Who is Elon Musk?", "Explain Python" → stable knowledge
 
Route B (Search — Tavily → Groq):
  "Latest AI news", "Bitcoin price today", "Who won IPL today?" → current info
"""
import sys
import logging
from flask import Blueprint, request, jsonify
 
from core.intent import classify_intent, detect_language, is_detail_request, is_static_knowledge
from services.college_service import get_college_answer, get_college_context
from services.weather_service import get_weather
from services.news_service import fetch_news, summarize_news
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
 
 
def _sid(req) -> str:
    return req.remote_addr or "default"
 
 
def _empty(text: str) -> bool:
    if not text or not text.strip():
        return True
    return any(p in text.lower() for p in ["couldn't find", "rephrase", "no information"])
 
 
def _general_answer(user_message: str, history, lang: str, detailed: bool) -> str:
    """
    ONE AI call total. No duplicate searches.
 
    Route A: static knowledge → Groq directly (fast).
    Route B: current/fresh info → Tavily context → Groq once.
    """
    use_tavily = not is_static_knowledge(user_message)
    print(f"[SEARCH] needs_tavily={use_tavily} for: {user_message!r}", file=sys.stderr)
 
    # ── Route A: Groq direct — no web call ───────────────────────────────
    if not use_tavily:
        print("[SEARCH] Route A: Groq direct (static knowledge)", file=sys.stderr)
        return query_ai(
            prompt=user_message,
            history=history,
            lang=lang,
            mode="general",
            detailed=detailed,
        )
 
    # ── Route B: Tavily → Groq (ONE call) ────────────────────────────────
    print("[SEARCH] Route B: Tavily → Groq", file=sys.stderr)
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
                + ("Explain thoroughly based on above." if detailed
                   else "Answer in one or two sentences only.")
            )
        return query_ai(
            prompt=prompt, history=history, lang=lang,
            mode="general", detailed=detailed,
        )
 
    # ── Route B fallback: pure Groq (Tavily returned nothing) ────────────
    print("[SEARCH] Tavily empty — fallback to pure Groq", file=sys.stderr)
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
 
        # ── NEWS — NewsData only, NO AI, NO Tavily ─────────────────────────
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
 
        # ── SEARCH / GENERAL — ONE AI call total ───────────────────────────
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
        if not phone or not phone.replace("+", "").replace("-", "").replace(" ", "").isdigit():
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
 