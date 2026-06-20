
# services/llm_service.py
import os
import logging
from typing import List, Dict, Optional
 
from groq import Groq
from openai import OpenAI
 
logger = logging.getLogger(__name__)
 
GROQ_API_KEY     = os.getenv("GROQ_API_KEY", "")
OPEN_ROUTER_API  = os.getenv("OPEN_ROUTER_API", "")
GROQ_MODEL       = os.getenv("GROQ_MODEL", "llama3-8b-8192")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-3.5-turbo")
 
# ── System prompts per mode ────────────────────────────────────────────────
 
_SYSTEM = {
    "college": {
        "en": (
            "You are IDEAL AI — the official assistant for Ideal College of Arts and Sciences, "
            "Kakinada, Andhra Pradesh. "
            "Answer ONLY from the college context provided. Be accurate, friendly and concise. "
            "Do NOT use markdown symbols like ** or ## in replies. "
            "Keep replies under 6 sentences unless the student needs a list."
        ),
        "te": (
            "మీరు ఐడియల్ కాలేజ్ ఆఫ్ ఆర్ట్స్ అండ్ సైన్సెస్, కాకినాడ కోసం IDEAL AI. "
            "అందించిన కాలేజీ సమాచారం ఆధారంగా మాత్రమే సమాధానం ఇవ్వండి. "
            "స్పష్టంగా, సంక్షిప్తంగా సమాధానం ఇవ్వండి. ** లేదా ## వంటి చిహ్నాలు వాడకండి."
        ),
    },
    "general": {
        "en": (
            "You are IDEAL AI — a helpful assistant for students of Ideal College of Arts and Sciences, Kakinada. "
            "Answer general knowledge questions clearly and accurately like a teacher explaining to a student. "
            "Structure your answer well. Do NOT use markdown symbols like ** or ## in replies. "
            "Keep replies under 8 sentences unless a detailed explanation is needed."
        ),
        "te": (
            "మీరు IDEAL AI — ఐడియల్ కాలేజ్ విద్యార్థులకు సహాయపడే assistant. "
            "ప్రశ్నలకు ఒక teacher వలె స్పష్టంగా, సరళంగా సమాధానం ఇవ్వండి. "
            "** లేదా ## వంటి చిహ్నాలు వాడకండి."
        ),
    },
}
 
 
def _system_prompt(mode: str, lang: str, context: str = "") -> str:
    bucket = _SYSTEM.get(mode, _SYSTEM["general"])
    base = bucket.get(lang, bucket["en"])
    if context:
        base += f"\n\nContext:\n{context}"
    return base
 
 
def _build_messages(
    prompt: str,
    history: Optional[List[Dict]],
    lang: str,
    context: str = "",
    mode: str = "general",
) -> List[Dict]:
    messages = [{"role": "system", "content": _system_prompt(mode, lang, context)}]
    for m in (history or [])[-6:]:
        if m.get("role") in {"user", "assistant"} and m.get("content"):
            messages.append({"role": m["role"], "content": str(m["content"])[:500]})
    messages.append({"role": "user", "content": prompt})
    return messages
 
 
def _query_groq(
    prompt: str,
    history: Optional[List[Dict]],
    lang: str,
    context: str = "",
    mode: str = "general",
) -> str:
    if not GROQ_API_KEY:
        raise RuntimeError("Missing GROQ_API_KEY")
    client = Groq(api_key=GROQ_API_KEY)
    res = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=_build_messages(prompt, history, lang, context, mode),
        temperature=0.4,
        max_tokens=700,
    )
    return (res.choices[0].message.content or "").strip()
 
 
def _query_openrouter(
    prompt: str,
    history: Optional[List[Dict]],
    lang: str,
    context: str = "",
    mode: str = "general",
) -> str:
    if not OPEN_ROUTER_API:
        raise RuntimeError("Missing OPEN_ROUTER_API")
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPEN_ROUTER_API)
    res = client.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=_build_messages(prompt, history, lang, context, mode),
        temperature=0.4,
        max_tokens=700,
    )
    return (res.choices[0].message.content or "").strip()
 
 
def query_ai(
    prompt: str,
    history: Optional[List[Dict]] = None,
    lang: str = "en",
    context: str = "",
    mode: str = "general",          # ← "college" or "general"
) -> str:
    """
    Primary: Groq.  Fallback: OpenRouter.
    mode = "college"  → strict college-context system prompt
    mode = "general"  → teacher-style general knowledge prompt
    """
    try:
        return _query_groq(prompt, history, lang, context, mode)
    except Exception as e:
        logger.warning("Groq failed (%s), trying OpenRouter", e)
        try:
            return _query_openrouter(prompt, history, lang, context, mode)
        except Exception as e2:
            logger.error("OpenRouter also failed: %s", e2)
            if lang == "te":
                return "AI సేవలు ఇప్పుడు అందుబాటులో లేవు. కొద్దిసేపటి తర్వాత మళ్లీ ప్రయత్నించండి."
            return "I'm unable to reach AI services right now. Please try again in a moment."
 