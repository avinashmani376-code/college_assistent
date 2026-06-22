# services/llm_service.py
"""
LLM service — Groq (primary) → OpenRouter (fallback).
 
SHORT MODE (default):  1-2 sentence answer
DETAILED MODE:         full explanation when user explicitly asks
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
 
_SHORT_COLLEGE_EN = """You are IDEAL AI — the assistant for Ideal College of Arts and Sciences, Kakinada.
RULES:
- Answer in 1-2 sentences maximum.
- Be direct. Answer only what was asked.
- Do NOT add extra advice, history, or context unless asked.
- Do NOT use ** or ## formatting.
Example: "BCA fee enti?" → "The annual BCA fee at Ideal College is ₹50,000."
STOP. Do not add more."""
 
_SHORT_COLLEGE_TE = """మీరు ఐడియల్ కాలేజ్ AI assistant.
నియమాలు:
- 1-2 వాక్యాలలో మాత్రమే సమాధానం ఇవ్వండి.
- అడిగిన దానికి మాత్రమే సమాధానం ఇవ్వండి.
- ** లేదా ## వాడకండి."""
 
_SHORT_GENERAL_EN = """You are IDEAL AI — a helpful assistant for college students.
RULES:
- Answer in 1-2 sentences maximum.
- Be direct and factual.
- Do NOT write essays. Do NOT add history or context unless asked.
- Do NOT use ** or ## formatting.
Examples:
Q: "Who is Narendra Modi?" → "Narendra Modi is the Prime Minister of India."
Q: "What is AI?" → "Artificial Intelligence (AI) is technology that enables computers to perform tasks that normally require human intelligence."
Q: "Who is AP CM?" → "N. Chandrababu Naidu is the Chief Minister of Andhra Pradesh."
STOP after answering. Nothing more."""
 
_SHORT_GENERAL_TE = """మీరు IDEAL AI — విద్యార్థులకు సహాయపడే assistant.
నియమాలు:
- 1-2 వాక్యాలలో మాత్రమే సమాధానం ఇవ్వండి.
- నేరుగా, స్పష్టంగా సమాధానం ఇవ్వండి.
- ** లేదా ## వాడకండి."""
 
_DETAILED_GENERAL_EN = """You are IDEAL AI — a helpful teacher for college students.
The user wants a detailed explanation. Explain clearly and thoroughly like a good teacher.
Use simple language. Structure the answer well. Do NOT use ** or ## formatting."""
 
_DETAILED_GENERAL_TE = """మీరు IDEAL AI — విద్యార్థులకు వివరంగా చెప్పే teacher.
స్పష్టంగా, సరళంగా వివరించండి. ** లేదా ## వాడకండి."""
 
 
def _pick_system(mode: str, lang: str, detailed: bool) -> str:
    if mode == "college":
        return _SHORT_COLLEGE_TE if lang == "te" else _SHORT_COLLEGE_EN
    if detailed:
        return _DETAILED_GENERAL_TE if lang == "te" else _DETAILED_GENERAL_EN
    return _SHORT_GENERAL_TE if lang == "te" else _SHORT_GENERAL_EN
 
 
def _build_messages(
    prompt: str,
    history: Optional[List[Dict]],
    lang: str,
    context: str,
    mode: str,
    detailed: bool,
) -> List[Dict]:
    sys_content = _pick_system(mode, lang, detailed)
    if context:
        sys_content += f"\n\nContext:\n{context}"
    msgs = [{"role": "system", "content": sys_content}]
    for m in (history or [])[-4:]:          # keep last 4 turns only
        if m.get("role") in {"user", "assistant"} and m.get("content"):
            msgs.append({"role": m["role"], "content": str(m["content"])[:400]})
    msgs.append({"role": "user", "content": prompt})
    return msgs
 
 
def _call_groq(msgs: List[Dict], detailed: bool) -> str:
    if not GROQ_API_KEY:
        raise RuntimeError("No GROQ_API_KEY")
    client = Groq(api_key=GROQ_API_KEY)
    res = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=msgs,
        temperature=0.3,
        max_tokens=400 if detailed else 150,   # SHORT MODE capped at 150 tokens
    )
    return (res.choices[0].message.content or "").strip()
 
 
def _call_openrouter(msgs: List[Dict], detailed: bool) -> str:
    if not OPEN_ROUTER_API:
        raise RuntimeError("No OPEN_ROUTER_API")
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPEN_ROUTER_API)
    res = client.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=msgs,
        temperature=0.3,
        max_tokens=400 if detailed else 150,
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
    """
    mode:     "college" or "general"
    detailed: True → full explanation; False (default) → 1-2 sentence answer
    """
    msgs = _build_messages(prompt, history, lang, context, mode, detailed)
    try:
        return _call_groq(msgs, detailed)
    except Exception as e:
        logger.warning("Groq failed (%s), trying OpenRouter", e)
        try:
            return _call_openrouter(msgs, detailed)
        except Exception as e2:
            logger.error("OpenRouter also failed: %s", e2)
            if lang == "te":
                return "AI సేవలు ఇప్పుడు అందుబాటులో లేవు. కొద్దిసేపటి తర్వాత మళ్లీ ప్రయత్నించండి."
            return "I'm unable to reach AI services right now. Please try again in a moment."