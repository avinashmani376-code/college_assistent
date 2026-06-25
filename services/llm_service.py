# services/llm_service.py
"""
SHORT MODE (default): 1 sentence. max_tokens=80.
DETAILED MODE: full answer. max_tokens=500.
All debug logs go to stderr (visible in Render logs).
"""
import os
import sys
import logging
from typing import List, Dict, Optional
 
from groq import Groq
from openai import OpenAI
 
logger = logging.getLogger(__name__)
 
GROQ_API_KEY     = os.getenv("GROQ_API_KEY",     "")
OPEN_ROUTER_API  = os.getenv("OPEN_ROUTER_API",  "")
GROQ_MODEL       = os.getenv("GROQ_MODEL",       "llama3-8b-8192")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-3.5-turbo")
 
print(f"[AI] LLM init: Groq={'SET' if GROQ_API_KEY else 'MISSING'} "
      f"OpenRouter={'SET' if OPEN_ROUTER_API else 'MISSING'} "
      f"model={GROQ_MODEL}", file=sys.stderr)
 
# ── System prompts ──────────────────────────────────────────────────────────
 
_COLLEGE_EN = (
    "You are IDEAL AI for Ideal College of Arts and Sciences, Kakinada.\n"
    "Answer in ONE sentence only. Use ONLY the provided context.\n"
    "Do NOT add extra information or advice.\n"
    "Do NOT use ** or ## symbols.\n"
    'Example: "The Principal of Ideal College is Dr. T. Satyanarayana."'
)
_COLLEGE_TE = (
    "మీరు ఐడియల్ కాలేజ్ AI.\n"
    "ఒక్క వాక్యంలో మాత్రమే సమాధానం ఇవ్వండి.\n"
    "** లేదా ## వాడకండి."
)
 
_SHORT_EN = (
    "You are IDEAL AI — a concise, factual assistant.\n"
    "RULE: Answer in exactly ONE sentence. Stop after that sentence.\n"
    "Do NOT explain, expand, or add examples unless asked.\n"
    "Do NOT use ** or ## symbols.\n"
    "Examples:\n"
    '"Who is Narendra Modi?" → "Narendra Modi is the Prime Minister of India."\n'
    '"What is AI?" → "Artificial Intelligence (AI) enables computers to perform tasks that normally require human intelligence."\n'
    '"Who is AP CM?" → "N. Chandrababu Naidu is the Chief Minister of Andhra Pradesh."'
)
_SHORT_TE = (
    "మీరు IDEAL AI — సంక్షిప్త assistant.\n"
    "నియమం: ఒక్క వాక్యంలో మాత్రమే సమాధానం ఇవ్వండి.\n"
    "** లేదా ## వాడకండి."
)
 
_DETAIL_EN = (
    "You are IDEAL AI — a helpful teacher for students.\n"
    "Give a clear, thorough explanation using simple language.\n"
    "Do NOT use ** or ## symbols."
)
_DETAIL_TE = (
    "మీరు IDEAL AI — teacher.\n"
    "స్పష్టంగా, వివరంగా వివరించండి.\n"
    "** లేదా ## వాడకండి."
)
 
 
def _pick_system(mode: str, lang: str, detailed: bool) -> str:
    if mode == "college":
        return _COLLEGE_TE if lang == "te" else _COLLEGE_EN
    if detailed:
        return _DETAIL_TE if lang == "te" else _DETAIL_EN
    return _SHORT_TE if lang == "te" else _SHORT_EN
 
 
def _build(prompt, history, lang, context, mode, detailed):
    sys_prompt = _pick_system(mode, lang, detailed)
    if context:
        sys_prompt += f"\n\nContext:\n{context}"
    msgs = [{"role": "system", "content": sys_prompt}]
    for m in (history or [])[-4:]:
        if m.get("role") in {"user", "assistant"} and m.get("content"):
            msgs.append({"role": m["role"], "content": str(m["content"])[:300]})
    msgs.append({"role": "user", "content": prompt})
    return msgs
 
 
def _call_groq(msgs, detailed: bool) -> str:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not set")
    max_tok = 500 if detailed else 80   # 80 tokens ≈ 1 sentence hard cap
    print(f"[AI] Groq: model={GROQ_MODEL} max_tokens={max_tok}", file=sys.stderr)
    client = Groq(api_key=GROQ_API_KEY)
    res = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=msgs,
        temperature=0.1,          # very low = more deterministic/concise
        max_tokens=max_tok,
    )
    reply = (res.choices[0].message.content or "").strip()
    print(f"[AI] Groq reply ({len(reply)} chars): {reply[:100]}", file=sys.stderr)
    return reply
 
 
def _call_openrouter(msgs, detailed: bool) -> str:
    if not OPEN_ROUTER_API:
        raise RuntimeError("OPEN_ROUTER_API not set")
    max_tok = 500 if detailed else 80
    print(f"[AI] OpenRouter: model={OPENROUTER_MODEL} max_tokens={max_tok}", file=sys.stderr)
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPEN_ROUTER_API)
    res = client.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=msgs,
        temperature=0.1,
        max_tokens=max_tok,
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
    mode    : "college" → strict 1-sentence using context only
              "general" → short factual answer (default)
    detailed: True → full explanation (only when user says "explain more" etc.)
    """
    print(f"[AI] query_ai: mode={mode} lang={lang} detailed={detailed} "
          f"prompt={prompt[:60]!r}", file=sys.stderr)
    msgs = _build(prompt, history, lang, context, mode, detailed)
    try:
        return _call_groq(msgs, detailed)
    except Exception as e:
        logger.warning("Groq failed: %s", e)
        print(f"[AI] Groq failed: {e}", file=sys.stderr)
        try:
            return _call_openrouter(msgs, detailed)
        except Exception as e2:
            logger.error("OpenRouter failed: %s", e2)
            print(f"[AI] OpenRouter failed: {e2}", file=sys.stderr)
            if lang == "te":
                return "AI సేవలు ఇప్పుడు అందుబాటులో లేవు. కొద్దిసేపటి తర్వాత మళ్లీ ప్రయత్నించండి."
            return "AI services are unavailable right now. Please try again in a moment."