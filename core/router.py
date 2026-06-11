# core/router.py
import logging
from flask import Blueprint, request, jsonify

from core.intent import classify_intent, detect_language
from services.college_service import get_college_answer, get_college_context
from services.weather_service import get_weather
from services.news_service import fetch_news, summarize_news
from services.search_service import search_and_format
from services.llm_service import query_ai
from data.media_data import IMAGE_PATHS, VIDEO_PATH

logger = logging.getLogger(__name__)
router = Blueprint("router", __name__)


@router.route("/api/chat", methods=["POST"])
def api_chat():
    try:
        data = request.get_json(silent=True) or {}
        user_message = (data.get("message") or "").strip()
        history = data.get("history") or []

        if not user_message:
            return jsonify({"reply": "Please enter a message.", "source": "", "show_images": False,
                            "images": [], "show_video": False, "video_url": ""}), 400

        lang = detect_language(user_message)
        intent_data = classify_intent(user_message)
        intent = intent_data.get("intent")

        base = {"show_images": False, "images": [], "show_video": False, "video_url": "", "source": ""}

        if intent == "images":
            reply = "Here are campus photos." if lang == "en" else "ఇవి క్యాంపస్ ఫోటోలు."
            return jsonify({**base, "reply": reply, "show_images": True, "images": IMAGE_PATHS})

        if intent == "video":
            reply = "Here is the full college explanation video." if lang == "en" else "ఇది కాలేజీ పూర్తి వివరాల వీడియో."
            return jsonify({**base, "reply": reply, "show_video": True, "video_url": VIDEO_PATH})

        if intent == "weather":
            city = intent_data.get("city", "Kakinada")
            reply = get_weather(city, lang=lang)
            return jsonify({**base, "reply": reply})

        if intent == "news":
            articles, provider = fetch_news(user_message)
            reply = summarize_news(articles, lang=lang)
            return jsonify({**base, "reply": reply})

        if intent == "search":
            reply = search_and_format(user_message, lang=lang)
            return jsonify({**base, "reply": reply})

        if intent == "college":
            local_answer = get_college_answer(user_message, lang=lang)
            if local_answer:
                return jsonify({**base, "reply": local_answer})
            college_context = get_college_context()
            ai_reply = query_ai(prompt=user_message, history=history, lang=lang, context=college_context)
            return jsonify({**base, "reply": ai_reply})

        ai_reply = query_ai(prompt=user_message, history=history, lang=lang)
        return jsonify({**base, "reply": ai_reply})

    except Exception as exc:
        logger.exception("Chat route failed: %s", exc)
        return jsonify({
            "reply": "Sorry, something went wrong. Please try again.",
            "source": "", "show_images": False, "images": [], "show_video": False, "video_url": ""
        }), 500


@router.route("/api/news-sidebar", methods=["GET"])
def news_sidebar():
    try:
        articles, _ = fetch_news("students education college india latest")
        cleaned = []
        for a in articles[:6]:
            title = (a.get("title") or "").strip()
            url = (a.get("url") or "").strip()
            source = (a.get("source") or "").strip()
            if title:
                cleaned.append({"title": title, "url": url, "source": source})
        return jsonify({"articles": cleaned})
    except Exception:
        return jsonify({"articles": []})