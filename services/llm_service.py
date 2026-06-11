# services/llm_service.py
import os
from typing import List, Dict, Optional

from groq import Groq
from openai import OpenAI

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OPEN_ROUTER_API = os.getenv("OPEN_ROUTER_API", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-8b-8192")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-3.5-turbo")

SYSTEM_EN = (
    "You are IDEAL AI — the official AI assistant for Ideal College of Arts and Sciences, "
    "Kakinada, Andhra Pradesh. "
    "Answer clearly, concisely and helpfully. For college-related questions, use provided context. "
    "For general questions, give accurate answers. Keep responses under 5 sentences unless more detail is needed. "
    "Do NOT use markdown symbols like ** or ## in replies."
)

SYSTEM_TE = (
    "మీరు ఐడియల్ కాలేజ్ ఆఫ్ ఆర్ట్స్ అండ్ సైన్సెస్, కాకినాడ కోసం IDEAL AI. "
    "స్పష్టంగా, సరైన సమాచారంతో, సంక్షిప్తంగా సమాధానం ఇవ్వండి. "
    "సమాధానాలు 5 వాక్యాల లోపు ఉండాలి."
)


def _build_messages(prompt: str, history: Optional[List[Dict]], lang: str, context: str = "") -> List[Dict]:
    sys_content = SYSTEM_TE if lang == "te" else SYSTEM_EN
    if context:
        sys_content += f"\n\nCollege Context:\n{context}"
    messages = [{"role": "system", "content": sys_content}]
    for m in (history or [])[-6:]:
        if m.get("role") in {"user", "assistant"} and m.get("content"):
            messages.append({"role": m["role"], "content": str(m["content"])[:500]})
    messages.append({"role": "user", "content": prompt})
    return messages


def _query_groq(prompt: str, history: Optional[List[Dict]], lang: str, context: str = "") -> str:
    if not GROQ_API_KEY:
        raise RuntimeError("Missing GROQ_API_KEY")
    client = Groq(api_key=GROQ_API_KEY)
    res = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=_build_messages(prompt, history, lang, context),
        temperature=0.5,
        max_tokens=600,
    )
    return (res.choices[0].message.content or "").strip()


def _query_openrouter(prompt: str, history: Optional[List[Dict]], lang: str, context: str = "") -> str:
    if not OPEN_ROUTER_API:
        raise RuntimeError("Missing OPEN_ROUTER_API")
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPEN_ROUTER_API)
    res = client.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=_build_messages(prompt, history, lang, context),
        temperature=0.5,
        max_tokens=600,
    )
    return (res.choices[0].message.content or "").strip()


def query_ai(prompt: str, history: Optional[List[Dict]] = None, lang: str = "en", context: str = "") -> str:
    try:
        return _query_groq(prompt, history, lang, context)
    except Exception:
        try:
            return _query_openrouter(prompt, history, lang, context)
        except Exception:
            return (
                "I'm unable to reach AI providers right now. Please try again in a moment."
                if lang == "en"
                else "AI సేవలు ఇప్పుడు అందుబాటులో లేవు. కొద్దిసేపటి తర్వాత మళ్లీ ప్రయత్నించండి."
            )
