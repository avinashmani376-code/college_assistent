# services/llm_service.py
"""
SHORT MODE (default): 1-2 sentences max. max_tokens=100.
DETAILED MODE: full answer (only when user says "explain", "details", etc.). max_tokens=500.
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
 
# Default: 2-4 short sentences, voice-friendly, no bullet fragments
_SHORT_EN = (
    "You are IDEAL AI, a concise and helpful assistant.\n"
    "Write your answer in 2 to 4 short, complete sentences. Stop when done.\n"
    "Voice-friendly rules:\n"
    "  - Natural spoken English. No bullet points. No dashes.\n"
    "  - Every sentence must be complete. No abrupt endings.\n"
    "  - Proper punctuation so text-to-speech reads smoothly.\n"
    "  - No ** or ## symbols.\n"
    "  - No filler phrases like Great question or Sure.\n"
    "Example: Who is Elon Musk? "
    "Answer: Elon Musk is an American entrepreneur best known as the CEO of Tesla and SpaceX. "
    "He also founded companies like PayPal and The Boring Company. "
    "He is widely regarded as one of the most influential people in technology."
)
_SHORT_TE = (
    "మీరు IDEAL AI, సంక్షిప్త assistant.\n"
    "2 నుండి 4 పూర్తి వాక్యాలలో సమాధానం ఇవ్వండి.\n"
    "bullet points, dashes లేదా ** వాడకండి.\n"
    "ప్రతి వాక్యం పూర్తిగా ఉండాలి. మధ్యలో ఆపకండి."
)
 
# Detailed: only when user explicitly asks
_DETAIL_EN = (
    "You are IDEAL AI, a helpful teacher for students.\n"
    "Give a thorough, easy-to-understand explanation in natural English.\n"
    "Voice-friendly rules:\n"
    "  - Write in flowing paragraphs, not bullet points.\n"
    "  - Use short, clear sentences. Each sentence must be complete.\n"
    "  - No ** or ## symbols.\n"
    "  - End with a proper concluding sentence. Never cut off mid-thought."
)
_DETAIL_TE = (
    "మీరు IDEAL AI, teacher.\n"
    "స్పష్టంగా, వివరంగా వివరించండి.\n"
    "bullet points లేదా ** వాడకండి. ప్రతి వాక్యం పూర్తిగా ఉండాలి."
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
    # Short: 180 tokens = ~2-4 complete sentences; Detailed: 600 tokens = full explanation
    max_tok = 600 if detailed else 180
    print(f"[AI] Groq: model={GROQ_MODEL} max_tokens={max_tok}", file=sys.stderr)
    client = Groq(api_key=GROQ_API_KEY)
    res = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=msgs,
        temperature=0.1,
        max_tokens=max_tok,
    )
    reply = (res.choices[0].message.content or "").strip()
    print(f"[AI] Groq reply ({len(reply)} chars): {reply[:120]}", file=sys.stderr)
    return reply
 
 
def _call_openrouter(msgs, detailed: bool) -> str:
    if not OPEN_ROUTER_API:
        raise RuntimeError("OPEN_ROUTER_API not set")
    max_tok = 600 if detailed else 180
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
    Single AI call per user query. No retries beyond provider fallback.
 
    mode    : "college" → strict 1-sentence using context only
              "general" → 1-2 sentence factual answer (default)
    detailed: True → full explanation (only when user explicitly requests it)
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
 