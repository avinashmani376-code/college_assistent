# core/responder.py

_MEDIA_FIELDS = {"show_images": False, "images": [], "show_video": False, "video_url": None}


def format_college_response(answer: str, source: str = "College Database") -> dict:
    return {"reply": answer, "intent": "college", "source": "", **_MEDIA_FIELDS}


def format_weather_response(weather_data: dict | None, city: str, lang: str = "en") -> dict:
    if weather_data:
        if lang == "te":
            reply = (
                f"📍 {weather_data['city']}లో ప్రస్తుత వాతావరణం:\n"
                f"🌡 ఉష్ణోగ్రత: {weather_data['temp']}°C\n"
                f"☁ స్థితి: {weather_data['desc']}\n"
                f"💧 తేమ: {weather_data['humidity']}%\n"
                f"💨 గాలి వేగం: {weather_data['wind']} km/h"
            )
        else:
            reply = (
                f"📍 Weather in {weather_data['city']}:\n"
                f"🌡 Temperature: {weather_data['temp']}°C\n"
                f"☁ Condition: {weather_data['desc']}\n"
                f"💧 Humidity: {weather_data['humidity']}%\n"
                f"💨 Wind: {weather_data['wind']} km/h"
            )
    else:
        if lang == "te":
            reply = f"'{city}' వాతావరణ సమాచారం తీసుకోలేకపోయాను. నగరం పేరు సరిగ్గా ఉందో తనిఖీ చేయండి."
        else:
            reply = f"Couldn't fetch weather for '{city}'. Please check the city name and try again."
    return {"reply": reply, "intent": "weather", "source": "", **_MEDIA_FIELDS}


def format_news_response(articles: list, lang: str = "en") -> dict:
    if articles:
        if lang == "te":
            lines = ["📰 తాజా అప్‌డేట్స్:\n"]
            for i, a in enumerate(articles[:5], 1):
                lines.append(f"{i}. {a['title']}")
        else:
            lines = ["📰 Latest News:\n"]
            for i, a in enumerate(articles[:5], 1):
                lines.append(f"{i}. {a['title']}")
        reply = "\n".join(lines)
    else:
        reply = "వార్తలు తీసుకోలేకపోయాను." if lang == "te" else "Couldn't fetch news right now. Please try again later."
    return {"reply": reply, "intent": "news", "source": "", **_MEDIA_FIELDS}


def format_search_response(answer: str) -> dict:
    return {"reply": answer, "intent": "search", "source": "", **_MEDIA_FIELDS}


def format_general_response(answer: str) -> dict:
    return {"reply": answer, "intent": "general", "source": "", **_MEDIA_FIELDS}


def format_error_response(message: str = "Something went wrong. Please try again.") -> dict:
    return {"reply": message, "intent": "general", "source": "", **_MEDIA_FIELDS}
