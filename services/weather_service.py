
# services/weather_service.py
import os
import logging
import requests
from typing import Optional, Dict, Any
 
logger = logging.getLogger(__name__)
 
# Accept either env var name so both .env and Render config work
WEATHER_API_KEY = (
       os.getenv("OPENWEATHER_API_KEY", "")
)
 
_WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Foggy", 48: "Foggy", 51: "Light drizzle", 53: "Moderate drizzle",
    55: "Heavy drizzle", 61: "Light rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Light snow", 73: "Moderate snow", 75: "Heavy snow",
    80: "Rain showers", 81: "Heavy showers", 82: "Violent showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Heavy thunderstorm",
}
 
 
def _weatherapi(city: str) -> Optional[Dict[str, Any]]:
    """WeatherAPI.com — uses WEATHER_API_KEY."""
    if not WEATHER_API_KEY:
        return None
    try:
        resp = requests.get(
            "https://api.weatherapi.com/v1/current.json",
            params={"key": WEATHER_API_KEY, "q": city, "aqi": "no"},
            timeout=12,
        )
        if resp.status_code != 200:
            logger.warning("WeatherAPI returned %s for city=%s", resp.status_code, city)
            return None
        data = resp.json()
        cur = data.get("current", {})
        loc = data.get("location", {})
        return {
            "city":     loc.get("name", city),
            "temp":     cur.get("temp_c", "N/A"),
            "desc":     cur.get("condition", {}).get("text", "Unknown"),
            "humidity": cur.get("humidity", "N/A"),
            "wind":     cur.get("wind_kph", "N/A"),
            "provider": "WeatherAPI",
        }
    except Exception as e:
        logger.warning("WeatherAPI exception: %s", e)
        return None
 
 
def _open_meteo(city: str) -> Optional[Dict[str, Any]]:
    """Open-Meteo (free, no key required) — fallback."""
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
        current = w.json().get("current", {})
        code = current.get("weather_code", -1)
        return {
            "city":     name,
            "temp":     current.get("temperature_2m", "N/A"),
            "desc":     _WMO_CODES.get(code, "Unknown"),
            "humidity": current.get("relative_humidity_2m", "N/A"),
            "wind":     current.get("wind_speed_10m", "N/A"),
            "provider": "Open-Meteo (free)",
        }
    except Exception as e:
        logger.warning("Open-Meteo exception: %s", e)
        return None
 
 
def get_weather(city: str, lang: str = "en") -> str:
    city = (city or "Kakinada").strip()
    data = _weatherapi(city) or _open_meteo(city)
 
    if not data:
        if lang == "te":
            return (
                f"'{city}' వాతావరణ సమాచారం తీసుకోలేకపోయాను. "
                "నగరం పేరు సరిగ్గా ఉందో తనిఖీ చేయండి."
            )
        return (
            f"Couldn't fetch weather for '{city}'. "
            "Please check the city name and try again."
        )
 
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
 