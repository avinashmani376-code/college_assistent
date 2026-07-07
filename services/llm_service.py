# services/llm_service.py
"""
SHORT MODE (default): structured format. max_tokens=380.
DETAILED MODE: full structured explanation. max_tokens=700.
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
 
# Default: structured ChatGPT-style response with emoji heading,
# Overview, Key Points, Interesting Fact. Clean and professional.
_SHORT_EN = (
    "You are IDEAL AI, a helpful and professional assistant.\n"
    "Format EVERY response exactly like the examples below.\n"
    "Rules:\n"
    "  1. Start with a relevant emoji and the topic as a heading.\n"
    "  2. Write a short Overview paragraph (2-3 sentences).\n"
    "  3. Add Key Points as bullet lines starting with •\n"
    "  4. Add one Interesting Fact bullet.\n"
    "  5. Use simple English. No ** or ## or markdown formatting.\n"
    "  6. Never merge two different topics. Each question gets a fresh response.\n"
    "\n"
    "Example 1:\n"
    "🌌 Solar System\n"
    "Overview\n"
    "The Solar System consists of the Sun, eight planets, moons, and other celestial bodies held together by gravity. It is located in the Milky Way galaxy and formed about 4.6 billion years ago.\n"
    "Key Points\n"
    "• The Sun contains more than 99% of the Solar System's mass.\n"
    "• There are 8 planets: Mercury, Venus, Earth, Mars, Jupiter, Saturn, Uranus, Neptune.\n"
    "• Earth is the only known planet with life.\n"
    "• The Solar System is about 4.6 billion years old.\n"
    "Interesting Fact\n"
    "• Light from the Sun takes about 8 minutes to reach Earth.\n"
    "\n"
    "Example 2:\n"
    "🎬 Rajinikanth\n"
    "Overview\n"
    "Rajinikanth is one of India's most iconic film stars, known for his unique style and massive fan following across the world. He has worked in Tamil, Telugu, Hindi, and Kannada films.\n"
    "Key Points\n"
    "• Real name: Shivaji Rao Gaekwad.\n"
    "• Known for blockbusters like Baasha, Muthu, Enthiran, and Kabali.\n"
    "• Recipient of Padma Bhushan and Padma Vibhushan awards.\n"
    "• Has a dedicated fan base called Rajini fans across India and globally.\n"
    "Interesting Fact\n"
    "• He started his career as a bus conductor before entering films."
)
_SHORT_TE = (
    "మీరు IDEAL AI, helpful assistant.\n"
    "ప్రతి సమాధానం ఇలా రాయండి:\n"
    "1. Emoji + Topic heading\n"
    "2. Overview: 2-3 వాక్యాలు\n"
    "3. Key Points: • తో మొదలయ్యే bullets\n"
    "4. Interesting Fact: ఒక bullet\n"
    "** లేదా ## వాడకండి. సరళమైన తెలుగు వాడండి."
)
 
# Detailed: same structure as short but with more depth per section
_DETAIL_EN = (
    "You are IDEAL AI, a helpful teacher for students.\n"
    "Format EVERY response exactly like the example below.\n"
    "Rules:\n"
    "  1. Start with a relevant emoji and the topic as a heading.\n"
    "  2. Write an Overview paragraph (3-4 sentences, clear introduction).\n"
    "  3. Add Key Points section with 4-6 bullet lines starting with •\n"
    "  4. Add Interesting Facts section with 2-3 bullet lines.\n"
    "  5. End with a short Conclusion (1-2 sentences).\n"
    "  6. Use simple English. Short paragraphs. No ** or ## or markdown.\n"
    "  7. Never merge two different topics. Each question gets a fresh, clean response.\n"
    "\n"
    "Example:\n"
    "🕳 Black Hole\n"
    "Overview\n"
    "A black hole is a region in space where gravity is so strong that nothing, not even light, can escape from it. Black holes form when massive stars collapse at the end of their life. They are invisible but detectable through their effects on nearby matter.\n"
    "Key Points\n"
    "• Formed from collapsing massive stars.\n"
    "• The boundary around a black hole is called the event horizon.\n"
    "• Nothing can escape once it crosses the event horizon.\n"
    "• Scientists detect them through X-ray emissions and gravitational effects.\n"
    "• The center of most galaxies contains a supermassive black hole.\n"
    "Interesting Facts\n"
    "• The first black hole image was captured in 2019 by the Event Horizon Telescope.\n"
    "• Time passes more slowly near a black hole due to intense gravity.\n"
    "Conclusion\n"
    "Black holes are among the most fascinating and extreme objects in the universe. Scientists continue to study them to better understand the laws of physics."
)
_DETAIL_TE = (
    "మీరు IDEAL AI, teacher.\n"
    "ప్రతి సమాధానం ఇలా రాయండి:\n"
    "1. Emoji + Topic heading\n"
    "2. Overview: 3-4 వాక్యాలు\n"
    "3. Key Points: • తో మొదలయ్యే 4-6 bullets\n"
    "4. Interesting Facts: 2-3 bullets\n"
    "5. Conclusion: 1-2 వాక్యాలు\n"
    "** లేదా ## వాడకండి. సరళమైన తెలుగు వాడండి."
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
    max_tok = 700 if detailed else 380
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
    max_tok = 700 if detailed else 380
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