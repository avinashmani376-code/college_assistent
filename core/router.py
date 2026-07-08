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
 
 
def _resolve_message(user_message: str, ctx: dict) -> str:
    """
    Expand a bare / pronoun follow-up message using context.

    RULE: Only modify the message when it is NOT self-contained.
    Uses _is_self_contained() as the single source of truth — the same
    function used by _general_answer() — so both paths behave identically.

    Self-contained  → return unchanged (current topic ignored completely)
    Not self-contained → expand with prior topic (pronoun/continuation)

    Examples (topic in context = Rajinikanth):
      "What is his latest movie?" → "What is Rajinikanth latest movie?"
      "latest movie"              → "Rajinikanth latest movie"
      "Budget?"                   → "Rajinikanth Budget"
      "News about AI"             → "News about AI"  (unchanged — self-contained)
      "Dark Matter"               → "Dark Matter"    (unchanged — self-contained)
    """
    raw     = user_message.strip()
    msg_low = raw.lower()

    # ── Weather follow-up: checked FIRST, before self-contained gate ─────
    # Single-word weather queries ("Tomorrow?", "Rain?", "Weekend?") are
    # technically self-contained (1 content word) but need city injection.
    # Detect them by ctx.intent=="weather" + no explicit city in the message.
    if ctx.get("intent") == "weather" and ctx.get("city"):
        city = ctx["city"]
        msg_low_clean = msg_low.rstrip("?.!")
        # Only inject if the message doesn't already specify a city
        city_already = city.lower() in msg_low
        # If user already has "weather in X" or explicitly names a different city,
        # it is a self-contained weather query — don't inject.
        has_explicit_location = (
            "weather in" in msg_low or "weather at" in msg_low
            or "weather for" in msg_low
            or any(k in msg_low for k in
                   ("mumbai","delhi","hyderabad","bangalore","chennai","kolkata",
                    "vizag","vijayawada","guntur","tirupati","nellore","kurnool",
                    "rajahmundry","eluru","ongole","anantapur","kadapa"))
        )
        has_weather_word = any(k in msg_low for k in
                               ("temperature", "forecast", "rain",
                                "sunny", "cloudy", "wind", "humidity", "weekend",
                                "tomorrow", "tonight", "morning", "evening",
                                "monday","tuesday","wednesday","thursday","friday",
                                "saturday","sunday","next week","today"))
        if has_weather_word and not city_already and not has_explicit_location:
            return f"weather {raw} {city}"

    # ── Single gate: if self-contained, never inject context ─────────────
    # Uses the same logic as _general_answer so both paths are consistent.
    if _is_self_contained(user_message):
        return user_message

    # ── Topic-based follow-up ───────────────────────────────────────────
    topic = ctx.get("topic") or _extract_topic_from_history(ctx.get("history", []))
    if not topic:
        return user_message   # no prior context — nothing to inject

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
 
 
# ── Bare continuation phrases that need a prior topic ────────────────────
# These have NO subject of their own — they only work as follow-ups.
_BARE_CONTINUATIONS = {
    "explain about", "tell me more", "continue", "go on", "more",
    "explain more", "tell more", "more details", "more info",
    "and then", "what about it", "what next", "next", "elaborate",
    "details", "more information", "give more", "say more",
}


def _is_bare_continuation(message: str) -> bool:
    """
    True when the message is a continuation phrase with no subject.
    Examples: "Explain about", "Tell me more", "Continue"
    These REQUIRE a prior topic to make sense.
    """
    msg = message.strip().lower().rstrip("?.!")
    return msg in _BARE_CONTINUATIONS or any(
        msg == s or msg == s + "." or msg == s + "?"
        for s in _BARE_CONTINUATIONS
    )


def _is_self_contained(message: str) -> bool:
    """
    True when the message carries its own clear subject.
    Self-contained queries get empty history so prior topics don't leak.

    A message is self-contained when:
    - No pronouns (he/she/it/they/his/their/those/these)
    - Not a bare follow-up starter (tell me more, continue, latest movie…)
    - At least 1 meaningful content word after stripping fillers
    """
    msg = message.lower().strip()

    # Pronouns signal reference to prior topic
    if set(msg.split()) & _PRONOUNS:
        return False

    # Bare follow-up starters signal continuation — check word-boundary aware
    # to avoid "news about AI".startswith("new") false-positive
    msg_words = msg.split()
    for starter in _FOLLOWUP_STARTERS:
        starter_words = starter.split()
        # Match only if the leading WORDS are identical (not just substring)
        if msg_words[:len(starter_words)] == starter_words:
            # Only treat as follow-up if no extra meaningful subject follows
            remaining = msg_words[len(starter_words):]
            remaining_content = [w for w in remaining
                                 if w not in {"the", "a", "an", "of", "in", "on", "about"}]
            if not remaining_content:
                return False   # pure follow-up, no subject

    # Bare continuations have no subject at all
    if _is_bare_continuation(msg):
        return False

    # At least 1 content word = has its own subject
    cw = _content_words(msg)
    return len(cw) >= 1


def _general_answer(user_message: str, history, lang: str, detailed: bool,
                    ctx: dict = None) -> str:
    """
    ONE AI call total. No duplicate searches.

    Bug 1 fix: self-contained queries use empty history (no prior topic leakage).
    Bug 3 fix: bare continuations with no prior ctx topic ask user for a topic.

    Route A: static knowledge → Groq directly (fast).
    Route B: current/fresh info → Tavily context → Groq once.
    """
    # ── Bug 3: bare continuation with no prior topic → ask user ──────────
    if _is_bare_continuation(user_message):
        prior_topic = (ctx or {}).get("topic", "")
        if not prior_topic:
            print("[SEARCH] Bare continuation with no prior topic → asking user",
                  file=sys.stderr)
            if lang == "te":
                return "మీరు ఏ విషయం గురించి వివరణ కావాలో చెప్పగలరా?"
            return "What topic would you like me to explain? Please mention a subject."

    # ── Bug 1: clear history for self-contained queries ───────────────────
    if _is_self_contained(user_message):
        safe_history = []
        print("[SEARCH] Self-contained query — history cleared to prevent leakage",
              file=sys.stderr)
    else:
        safe_history = history or []

    use_tavily = not is_static_knowledge(user_message)
    print(f"[SEARCH] needs_tavily={use_tavily} for: {user_message!r}", file=sys.stderr)

    # ── Route A: Groq direct ──────────────────────────────────────────
    if not use_tavily:
        print("[SEARCH] Route A: Groq direct (static knowledge)", file=sys.stderr)
        return query_ai(
            prompt=user_message,
            history=safe_history,
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
            prompt=prompt, history=safe_history, lang=lang,
            mode="general", detailed=detailed,
        )

    # ── Route B fallback: pure Groq ───────────────────────────────────
    print("[SEARCH] Tavily empty — fallback to pure Groq", file=sys.stderr)
    return query_ai(
        prompt=user_message, history=safe_history, lang=lang,
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
        reply = _general_answer(resolved, history, lang, detailed, ctx=ctx)
 
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