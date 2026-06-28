"""
core/router.py
 
Routing:
  college → DB → (AI only if DB misses)
  weather → weather_service
  news    → news_service (NewsData only, NO Tavily, NO AI)
  search/general → Route A (Groq direct) or Route B (Tavily → Groq)
                   Decision made ONCE via is_static_knowledge(), ONE AI call total.
 
Route A (Fast — Groq direct, no web):
  "What is AI?", "Who is Rajinikanth?", "Explain Python" → stable knowledge
 
Route B (Search — Tavily → Groq):
  "Latest AI news", "Bitcoin price today", "Who won IPL today?" → current info
 
Context / Conversation Continuity:
  _ContextStore  — per-session lightweight context (intent, topic, city, history)
  _resolve_message — expands bare follow-ups using stored context
"""
import re
import sys
import logging
from flask import Blueprint, request, jsonify
 
from core.intent import (
    classify_intent_with_context,
    detect_language,
    is_detail_request,
    is_static_knowledge,
    _PRONOUNS,
    _FOLLOWUP_STARTERS,
    _content_words,
    extract_city_from_weather,
)
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
 
# ═══════════════════════════════════════════════════════════════
# PER-SESSION CONTEXT STORE
# ═══════════════════════════════════════════════════════════════
 
# Keyed by session_id (IP address).  Each value is a dict:
#   intent   : last classified intent
#   topic    : last subject discussed (person / place / technology / etc.)
#   city     : last weather city
#   history  : last N (user, assistant) text pairs for pronoun resolution
_sessions: dict = {}
_MAX_HISTORY = 6   # keep last 6 user turns for topic extraction
 
 
def _get_ctx(session_id: str) -> dict:
    if session_id not in _sessions:
        _sessions[session_id] = {"intent": "", "topic": "", "city": "", "history": []}
    return _sessions[session_id]
 
 
def _push_history(ctx: dict, user_msg: str, assistant_msg: str):
    ctx["history"].append({"u": user_msg, "a": assistant_msg})
    if len(ctx["history"]) > _MAX_HISTORY:
        ctx["history"].pop(0)
 
 
# ═══════════════════════════════════════════════════════════════
# PRONOUN / FOLLOW-UP RESOLUTION
# ═══════════════════════════════════════════════════════════════
 
def _extract_topic_from_history(history: list) -> str:
    """
    Walk history newest-first to find the last meaningful subject the
    user talked about.  Skips turns that are themselves bare follow-ups.
    """
    for turn in reversed(history):
        u = turn.get("u", "").strip()
        if not u:
            continue
        ulow = u.lower()
        # skip bare follow-up turns
        if any(ulow.startswith(s) for s in _FOLLOWUP_STARTERS):
            continue
        words = u.split()
        if len(words) < 2:
            continue
        cw = [w.strip("?.!,") for w in words
              if w.lower().strip("?.!,") not in {
                  "who", "what", "is", "are", "was", "tell", "me", "about",
                  "please", "can", "you", "explain", "give", "the", "a", "an",
                  "i", "want", "to", "know", "in", "on", "of", "for", "and",
              }]
        if cw:
            return " ".join(cw[:5])
    return ""
 
 
def _is_message_self_contained(raw: str) -> bool:
    """
    Returns True when the current message clearly carries its own subject
    and intent — previous context must NOT be injected.
 
    This mirrors the logic in classify_intent_with_context._is_self_contained
    but works on the raw string before classification, so the router can
    decide whether to call _resolve_message at all.
    """
    msg = raw.lower().strip()
 
    # Explicit intent keywords that make a message self-contained
    weather_hit = any(k in msg for k in WEATHER_KEYWORDS)
    college_hit = sum(1 for k in COLLEGE_KEYWORDS if k in msg) >= 1
    news_hit    = any(k in msg for k in NEWS_KEYWORDS)
 
    if weather_hit or college_hit or news_hit:
        return True
 
    # 2+ meaningful content words → has its own subject
    cw = _content_words(msg)
    if len(cw) >= 2:
        return True
 
    return False
 
 
def _resolve_message(user_message: str, ctx: dict) -> str:
    """
    Expand a bare/pronoun follow-up using context.
 
    RULE: Only expand when the current message is ambiguous (no clear subject).
    If the message is self-contained, return it unchanged — never inject context.
 
    Examples (topic in context = Rajinikanth):
      "latest movie"          →  "Rajinikanth latest movie"
      "What is his net worth?" →  "What is Rajinikanth net worth?"
      "Who directed it?"       →  "Who directed Rajinikanth"
 
    But:
      "Weather in Hyderabad"   →  "Weather in Hyderabad"  (unchanged)
      "Latest AI news"         →  "Latest AI news"         (unchanged)
      "Tell me about Elon Musk"→  "Tell me about Elon Musk"(unchanged)
    """
    raw     = user_message.strip()
    msg_low = raw.lower()
 
    # ── STEP 1: If message is self-contained, never touch it ───────────
    if _is_message_self_contained(raw):
        return user_message
 
    # ── STEP 2: Detect bare / pronoun follow-up ────────────────────────
    cw = _content_words(msg_low)
    is_pronoun = bool(set(msg_low.split()) & _PRONOUNS)
    is_bare    = (
        any(msg_low.startswith(s) for s in _FOLLOWUP_STARTERS)
        or (is_pronoun and len(cw) <= 4)
        or len(cw) <= 1
    )
 
    if not is_bare:
        return user_message   # still self-contained enough
 
    # ── STEP 3: Weather follow-up ───────────────────────────────────────
    if ctx.get("intent") == "weather" and ctx.get("city"):
        city = ctx["city"]
        return f"weather {raw} {city}"
 
    # ── STEP 4: Topic-based follow-up ──────────────────────────────────
    topic = ctx.get("topic") or _extract_topic_from_history(ctx.get("history", []))
    if not topic:
        return user_message   # no prior context to inject
 
    resolved = raw
 
    # Replace pronouns with topic
    for pronoun in ("his", "her", "its", "their", "he", "she", "it",
                    "they", "them", "him", "this", "that"):
        pat = re.compile(r'\b' + pronoun + r'\b', re.IGNORECASE)
        if pat.search(resolved):
            resolved = pat.sub(topic, resolved, count=1)
            break
 
    # If no pronoun replaced — prepend topic
    if resolved == raw:
        resolved = f"{topic} {raw}"
 
    print(f"[CONTEXT] resolved: {raw!r} → {resolved!r}", file=sys.stderr)
    return resolved
 
 
# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════
 
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
 
    # ── Route A: Groq direct ──────────────────────────────────────────
    if not use_tavily:
        print("[SEARCH] Route A: Groq direct (static knowledge)", file=sys.stderr)
        return query_ai(
            prompt=user_message,
            history=history,
            lang=lang,
            mode="general",
            detailed=detailed,
        )
 
    # ── Route B: Tavily → Groq (ONE call) ────────────────────────────
    print("[SEARCH] Route B: Tavily → Groq", file=sys.stderr)
    ctx_text = search_and_get_context(user_message, max_results=3)
 
    if ctx_text:
        print(f"[SEARCH] Tavily returned {len(ctx_text)} chars", file=sys.stderr)
        if lang == "te":
            prompt = (
                f"ప్రశ్న: {user_message}\n\nసమాచారం:\n{ctx_text}\n\n"
                + ("వివరంగా వివరించండి." if detailed
                   else "ఒక్క వాక్యంలో సమాధానం ఇవ్వండి.")
            )
        else:
            prompt = (
                f"Question: {user_message}\n\nSearch results:\n{ctx_text}\n\n"
                + ("Explain thoroughly based on above." if detailed
                   else "Answer in one or two sentences only.")
            )
        return query_ai(
            prompt=prompt, history=history, lang=lang,
            mode="general", detailed=detailed,
        )
 
    # ── Route B fallback: pure Groq ───────────────────────────────────
    print("[SEARCH] Tavily empty — fallback to pure Groq", file=sys.stderr)
    return query_ai(
        prompt=user_message, history=history, lang=lang,
        mode="general", detailed=detailed,
    )
 
 
# ═══════════════════════════════════════════════════════════════
# MAIN CHAT ROUTE
# ═══════════════════════════════════════════════════════════════
 
@router.route("/api/chat", methods=["POST"])
def api_chat():
    try:
        data         = request.get_json(silent=True) or {}
        user_message = (data.get("message") or "").strip()
        history      = data.get("history") or []
 
        if not user_message:
            return jsonify({**BASE, "reply": "Please enter a message."}), 400
 
        lang       = detect_language(user_message)
        session_id = _sid(request)
        ctx        = _get_ctx(session_id)
 
        # ── Step 1: Resolve bare follow-ups before intent classification ─
        resolved = _resolve_message(user_message, ctx)
 
        # ── Step 2: Context-aware intent classification ──────────────────
        intent_data = classify_intent_with_context(resolved, ctx)
        intent      = intent_data.get("intent")
 
        # If the classifier produced a pre-resolved message, prefer it
        if intent_data.get("_resolved_message"):
            resolved = intent_data["_resolved_message"]
 
        detailed = is_detail_request(resolved)
 
        print(f"\n[ROUTE] original={user_message!r}", file=sys.stderr)
        print(f"[ROUTE] resolved={resolved!r}", file=sys.stderr)
        print(f"[ROUTE] intent={intent} lang={lang} detailed={detailed}", file=sys.stderr)
 
        # ── IMAGES ────────────────────────────────────────────────────
        if intent == "images":
            reply = "Here are campus photos." if lang == "en" else "ఇవి క్యాంపస్ ఫోటోలు."
            _push_history(ctx, user_message, reply)
            save_memory(user_message, reply, intent="images", lang=lang, session_id=session_id)
            return jsonify({**BASE, "reply": reply,
                            "show_images": True, "images": IMAGE_PATHS})
 
        # ── VIDEO ─────────────────────────────────────────────────────
        if intent == "video":
            reply = "Here is the college video." if lang == "en" else "ఇది కాలేజీ వీడియో."
            _push_history(ctx, user_message, reply)
            save_memory(user_message, reply, intent="video", lang=lang, session_id=session_id)
            return jsonify({**BASE, "reply": reply,
                            "show_video": True, "video_url": VIDEO_PATH})
 
        # ── WEATHER ───────────────────────────────────────────────────
        if intent == "weather":
            city = intent_data.get("city") or ctx.get("city") or "Kakinada"
            # Keep city in context for follow-ups
            ctx["city"]   = city
            ctx["intent"] = "weather"
            print(f"[ROUTE] → weather city={city!r}", file=sys.stderr)
            reply = get_weather(city, lang=lang)
            _push_history(ctx, user_message, reply)
            save_memory(user_message, reply, intent="weather", lang=lang, session_id=session_id)
            return jsonify({**BASE, "reply": reply})
 
        # ── NEWS ─────────────────────────────────────────────────────
        if intent == "news":
            print("[ROUTE] → news", file=sys.stderr)
            articles, provider = fetch_news(resolved)
            print(f"[ROUTE] news: provider={provider} count={len(articles)}", file=sys.stderr)
            reply = summarize_news(articles, lang=lang)
            ctx["intent"] = "news"
            ctx["topic"]  = intent_data.get("topic", "")
            _push_history(ctx, user_message, reply)
            save_memory(user_message, reply, intent="news", lang=lang, session_id=session_id)
            return jsonify({**BASE, "reply": reply})
 
        # ── COLLEGE ───────────────────────────────────────────────────
        if intent == "college":
            print("[ROUTE] → college", file=sys.stderr)
            reply = get_college_answer(resolved, lang=lang)
            if reply:
                print(f"[ROUTE] college DB hit ({len(reply)} chars)", file=sys.stderr)
            else:
                print("[ROUTE] college DB miss → AI", file=sys.stderr)
                reply = query_ai(
                    prompt=resolved, history=history, lang=lang,
                    context=get_college_context(), mode="college", detailed=detailed,
                )
            ctx["intent"] = "college"
            ctx["topic"]  = ""
            _push_history(ctx, user_message, reply)
            save_memory(user_message, reply, intent="college", lang=lang, session_id=session_id)
            return jsonify({**BASE, "reply": reply})
 
        # ── SEARCH / GENERAL ─────────────────────────────────────────
        print(f"[ROUTE] → {intent}", file=sys.stderr)
        reply = _general_answer(resolved, history, lang, detailed)
 
        # Update context topic from the resolved subject
        if intent_data.get("topic"):
            ctx["topic"] = intent_data["topic"]
        elif not ctx.get("topic"):
            cw = _content_words(resolved.lower())
            ctx["topic"] = " ".join(cw[:4]) if cw else ""
        ctx["intent"] = intent
 
        _push_history(ctx, user_message, reply)
        save_memory(user_message, reply, intent=intent, lang=lang, session_id=session_id)
        return jsonify({**BASE, "reply": reply})
 
    except Exception as exc:
        logger.exception("Chat route failed: %s", exc)
        return jsonify({
            **BASE,
            "reply": "Sorry, something went wrong. Please try again.",
        }), 500
 
 
# ═══════════════════════════════════════════════════════════════
# NEWS SIDEBAR
# ═══════════════════════════════════════════════════════════════
 
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
 
 
# ═══════════════════════════════════════════════════════════════
# APPLY / ADMISSION
# ═══════════════════════════════════════════════════════════════
 
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
 