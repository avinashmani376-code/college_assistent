import os
from dotenv import load_dotenv

# =====================================================
# CONFIGURATION FILE - IDEAL COLLEGE AI
# Optimized for Flask + Render.com Deployment
# Updated: April 2026
# =====================================================

# Load environment variables from .env (works both locally and on Render)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"))

# ====================== API KEYS ======================
GROQ_API_KEY       = os.getenv("GROQ_API_KEY", "")
OPEN_ROUTER_API    = os.getenv("OPEN_ROUTER_API", "")
WEATHER_API_KEY    = os.getenv("WEATHER_API_KEY", "")
GNEWS_API          = os.getenv("GNEWS_API", "")
NEWS_API_KEY       = os.getenv("NEWS_API_KEY", "")
NEWS_DATA_API      = os.getenv("NEWS_DATA_API", "")

# ====================== SECURITY ======================
SESSION_SECRET = os.getenv("SESSION_SECRET", "ideal-college-ai-secret-key-change-in-production")

# ====================== COLLEGE INFORMATION ======================
COLLEGE_NAME     = "Ideal College of Arts and Sciences"
COLLEGE_PHONE    = "0884-2384382 / 0884-2384381"
COLLEGE_EMAIL    = "idealcolleges@gmail.com"
COLLEGE_WEBSITE  = "https://idealcollege.edu.in"
COLLEGE_LOCATION = "Vidyuth Nagar, Kakinada, Andhra Pradesh"

# ====================== AI MODELS ======================
GROQ_MODEL        = os.getenv("GROQ_MODEL", "llama3-8b-8192")
OPENROUTER_MODEL  = os.getenv("OPENROUTER_MODEL", "openai/gpt-3.5-turbo")

# ====================== SYSTEM PROMPTS (Important for your AI) ======================
COLLEGE_SYSTEM_PROMPT = """You are the official AI assistant for Ideal College of Arts and Sciences,
located at Vidyuth Nagar, Kakinada, Andhra Pradesh.

LANGUAGE RULE:
- If the user writes in Telugu → reply ONLY in Telugu.
- If the user writes in English → reply ONLY in English.

BEHAVIOR:
- Be friendly, helpful, and professional.
- For college questions, give direct and accurate answers.
- Keep answers clear and concise.

COLLEGE CONTACT:
- Phone: 0884-2384382 / 0884-2384381
- Email: idealcolleges@gmail.com
- Website: https://idealcollege.edu.in
- Location: Vidyuth Nagar, Kakinada, Andhra Pradesh"""

TELUGU_SYSTEM_PROMPT = """మీరు ఐడియల్ కాలేజ్ ఆఫ్ ఆర్ట్స్ అండ్ సైన్సెస్, కాకినాడ యొక్క అధికారిక AI అసిస్టెంట్.
భాషా నియమం: తెలుగులో మాట్లాడితే తెలుగులోనే సమాధానం ఇవ్వండి.
కాలేజీ సంప్రదింపు: ఫోన్: 0884-2384382, ఇమెయిల్: idealcolleges@gmail.com"""

# ====================== MEDIA PATHS ======================
IMAGE_PATHS = ["/static/media/1.png", "/static/media/2.png"]
VIDEO_PATH  = "/static/media/college.mp4"

# ====================== ADDITIONAL SETTINGS ======================
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")
PORT = int(os.getenv("PORT", 5000))

ALLOWED_LANGUAGES = ["en", "te"]
DEFAULT_LANGUAGE = "en"

# ====================== For Render Compatibility ======================
# These variables are used by app.py and other services
__all__ = [
    "GROQ_API_KEY", "OPEN_ROUTER_API", "WEATHER_API_KEY", "GNEWS_API",
    "NEWS_API_KEY", "NEWS_DATA_API", "SESSION_SECRET",
    "COLLEGE_SYSTEM_PROMPT", "TELUGU_SYSTEM_PROMPT",
    "IMAGE_PATHS", "VIDEO_PATH",
    "GROQ_MODEL", "OPENROUTER_MODEL",
    "DEBUG", "PORT"
]