"""
Weather service.
 
Primary:  OpenWeatherMap (api.openweathermap.org) — matches the key in .env
Fallback: Open-Meteo (free, no key required)
 
Environment variables accepted (first non-empty wins):
  OPENWEATHER_API_KEY   ← from .env
  WEATHER_API_KEY       ← from Render config
"""
import os
import logging
import requests
from typing import Optional, Dict, Any
 
logger = logging.getLogger(__name__)
 
# Accept either name so .env and Render both work
_OWM_KEY = (
    os.getenv("OPENWEATHER_API_KEY", "")
    or os.getenv("WEATHER_API_KEY", "")
)
 
_WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Foggy", 48: "Foggy", 51: "Light drizzle", 53: "Moderate drizzle",
    55: "Heavy drizzle", 61: "Light rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Light snow", 73: "Moderate snow", 75: "Heavy snow",
    80: "Rain showers", 81: "Heavy showers", 82: "Violent showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail",
}
 
 
def _openweathermap(city: str) -> Optional[Dict[str, Any]]:
    """OpenWeatherMap current weather — uses the key from .env."""
    if not _OWM_KEY:
        return None
    try:
        resp = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={
                "q":     city,
                "appid": _OWM_KEY,
                "units": "metric",
            },
            timeout=10,
        )
        if resp.status_code != 200:
            logger.warning("OWM returned %s for city=%r: %s", resp.status_code, city, resp.text[:200])
            return None
        d   = resp.json()
        main = d.get("main", {})
        wind = d.get("wind", {})
        weather = (d.get("weather") or [{}])[0]
        return {
            "city":     d.get("name", city),
            "temp":     round(main.get("temp", 0), 1),
            "desc":     weather.get("description", "").capitalize(),
            "humidity": main.get("humidity", "N/A"),
            "wind":     round(wind.get("speed", 0) * 3.6, 1),  # m/s → km/h
            "provider": "OpenWeatherMap",
        }
    except Exception as e:
        logger.warning("OWM exception: %s", e)
        return None
 
 
def _open_meteo(city: str) -> Optional[Dict[str, Any]]:
    """Open-Meteo — completely free, no key needed."""
    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1},
            timeout=10,
        )
        if geo.status_code != 200:
            return None
        results = geo.json().get("results") or []
        if not results:
            return None
        lat  = results[0]["latitude"]
        lon  = results[0]["longitude"]
        name = results[0].get("name", city)
 
        w = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude":  lat,
                "longitude": lon,
                "current":   "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
            },
            timeout=10,
        )
        if w.status_code != 200:
            return None
        cur  = w.json().get("current", {})
        code = cur.get("weather_code", -1)
        return {
            "city":     name,
            "temp":     cur.get("temperature_2m", "N/A"),
            "desc":     _WMO_CODES.get(code, "Unknown"),
            "humidity": cur.get("relative_humidity_2m", "N/A"),
            "wind":     cur.get("wind_speed_10m", "N/A"),
            "provider": "Open-Meteo",
        }
    except Exception as e:
        logger.warning("Open-Meteo exception: %s", e)
        return None
 
 
def get_weather(city: str, lang: str = "en") -> str:
    city = (city or "Kakinada").strip()
    data = _openweathermap(city) or _open_meteo(city)
 
    if not data:
        if lang == "te":
            return (
                f"'{city}' వాతావరణ సమాచారం తీసుకోలేకపోయాను. "
                "నగరం పేరు సరిగ్గా ఉందో చూడండి."
            )
        return f"Couldn't fetch weather for '{city}'. Please check the city name and try again."
 
    if lang == "te":
        return (
            f"📍 {data['city']}లో ప్రస్తుత వాతావరణం:\n"
            f"🌡 ఉష్ణోగ్రత: {data['temp']}°C\n"
            f"☁ స్థితి: {data['desc']}\n"
            f"💧 తేమ: {data['humidity']}%\n"
            f"💨 గాలి వేగం: {data['wind']} km/h"
        )
    return (
        f"📍 Weather in {data['city']}:\n"
        f"🌡 Temperature: {data['temp']}°C\n"
        f"☁ Condition: {data['desc']}\n"
        f"💧 Humidity: {data['humidity']}%\n"
        f"💨 Wind: {data['wind']} km/h"
    )