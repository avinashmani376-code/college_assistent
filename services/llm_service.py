# services/llm_service.py
"""
SHORT MODE (default): 1-2 sentence answers. max_tokens=120.
DETAILED MODE: full explanation. max_tokens=500.
"""
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

# ── System prompts ─────────────────────────────────────────────────────────

_COLLEGE_EN = (
    "You are IDEAL AI for Ideal College of Arts and Sciences, Kakinada.\n"
    "STRICT RULES:\n"
    "1. Answer ONLY what was asked. Do NOT add extra information, tips, or advice.\n"
    "2. Answer in ONE sentence only.\n"
    "3. Use only the context provided. If not in context, say 'Please contact the college.'\n"
    "4. Do NOT use ** or ## symbols.\n"
    'Example: Q:"Who is principal?" A:"The Principal is Dr. T. Satyanarayana."'
)
_COLLEGE_TE = (
    "మీరు ఐడియల్ కాలేజ్ AI.\n"
    "నియమాలు:\n"
    "1. అడిగిన దానికి మాత్రమే సమాధానం ఇవ్వండి. అదనపు సమాచారం చేర్చకండి.\n"
    "2. ఒక్క వాక్యంలో మాత్రమే సమాధానం ఇవ్వండి.\n"
    "3. ** లేదా ## వాడకండి."
)

_SHORT_EN = (
    "You are IDEAL AI — a helpful assistant.\n"
    "STRICT RULES:\n"
    "1. Answer in 1-2 sentences maximum. Never more.\n"
    "2. Be direct and factual. No preamble, no 'Great question!', no filler.\n"
    "3. Do NOT explain further, give examples, or add context unless asked.\n"
    "4. Do NOT use ** or ## symbols.\n"
    'Examples:\n'
    '"Who is Narendra Modi?" → "Narendra Modi is the Prime Minister of India."\n'
    '"What is AI?" → "Artificial Intelligence (AI) is the ability of computers to '
    'perform tasks that normally require human intelligence, such as recognizing speech or making decisions."\n'
    '"Who is AP CM?" → "N. Chandrababu Naidu is the Chief Minister of Andhra Pradesh."'
)
_SHORT_TE = (
    "మీరు IDEAL AI.\n"
    "నియమాలు:\n"
    "1. గరిష్టంగా 1-2 వాక్యాల్లో మాత్రమే సమాధానం ఇవ్వండి.\n"
    "2. నేరుగా విషయానికి వెళ్ళండి. అదనపు వివరణ వద్దు.\n"
    "3. ** లేదా ## వాడకండి."
)

_DETAILED_EN = (
    "You are IDEAL AI — a helpful teacher for students.\n"
    "Give a clear, thorough explanation. Use simple language.\n"
    "Do NOT use ** or ## symbols."
)
_DETAILED_TE = (
    "మీరు IDEAL AI — teacher.\n"
    "స్పష్టంగా, వివరంగా వివరించండి. ** లేదా ## వాడకండి."
)


def _system(mode: str, lang: str, detailed: bool) -> str:
    if mode == "college":
        return _COLLEGE_TE if lang == "te" else _COLLEGE_EN
    if detailed:
        return _DETAILED_TE if lang == "te" else _DETAILED_EN
    return _SHORT_TE if lang == "te" else _SHORT_EN


def _msgs(prompt, history, lang, context, mode, detailed):
    sys = _system(mode, lang, detailed)
    if context:
        # Limit context size to avoid AI padding its answer with context noise
        sys += f"\n\nContext (use only what is relevant):\n{context[:1500]}"
    out = [{"role": "system", "content": sys}]
    for m in (history or [])[-4:]:
        if m.get("role") in {"user", "assistant"} and m.get("content"):
            out.append({"role": m["role"], "content": str(m["content"])[:300]})
    out.append({"role": "user", "content": prompt})
    return out


def _groq(msgs, detailed):
    if not GROQ_API_KEY:
        raise RuntimeError("No GROQ_API_KEY")
    print(f"[AI] Calling Groq model={GROQ_MODEL} detailed={detailed}")
    client = Groq(api_key=GROQ_API_KEY)
    res = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=msgs,
        temperature=0.2,
        max_tokens=500 if detailed else 120,  # 120 tokens ≈ 1-2 sentences hard cap
        stop=None,
    )
    reply = (res.choices[0].message.content or "").strip()
    print(f"[AI] Groq reply ({len(reply)} chars): {reply[:80]}...")
    return reply


def _openrouter(msgs, detailed):
    if not OPEN_ROUTER_API:
        raise RuntimeError("No OPEN_ROUTER_API")
    print(f"[AI] Calling OpenRouter model={OPENROUTER_MODEL}")
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPEN_ROUTER_API)
    res = client.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=msgs,
        temperature=0.2,
        max_tokens=500 if detailed else 120,
    )
    return (res.choices[0].message.content or "").strip()


def query_ai(
    prompt: str,
    history: Optional[List[Dict]] = None,
    lang: str = "en",
    context: str = "",
    mode: str = "general",
    detailed: bool = False,
) -> str:
    print(f"[AI] query_ai called: mode={mode} lang={lang} detailed={detailed}")
    m = _msgs(prompt, history, lang, context, mode, detailed)
    try:
        return _groq(m, detailed)
    except Exception as e:
        logger.warning("Groq failed: %s", e)
        print(f"[AI] Groq failed: {e}")
        try:
            return _openrouter(m, detailed)
        except Exception as e2:
            logger.error("OpenRouter failed: %s", e2)
            print(f"[AI] OpenRouter failed: {e2}")
            if lang == "te":
                return "AI సేవలు ఇప్పుడు అందుబాటులో లేవు."
            return "AI services unavailable. Please try again."
