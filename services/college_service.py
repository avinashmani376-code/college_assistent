
"""
services/college_service.py
 
College data retrieval with optional AI explanation layer.
Never returns raw JSON — always produces human-readable text.
"""
 
import os
import logging
from data.college_data import COLLEGE_KEYWORDS, COLLEGE_DATABASE
 
logger = logging.getLogger(__name__)
 
try:
    from data.college_data import get_college_context as _get_context
except Exception:
    _get_context = None
 
 
TRIGGER_WORDS = [
    "ideal", "college", "campus", "kakinada college", "vidyuth nagar",
    "కళాశాల", "కాలేజీ", "ఐడియల్",
]
 
 
def _has_ai_keys() -> bool:
    return bool(os.getenv("GROQ_API_KEY", "") or os.getenv("OPEN_ROUTER_API", ""))
 
 
def _meta():
    return COLLEGE_DATABASE.get("metadata", {}) or {}
 
 
def _sections():
    return COLLEGE_DATABASE.get("sections", {}) or {}
 
 
def _section_data(key, lang="en"):
    sec = _sections().get(key, {}) or {}
    data = sec.get("data", {}) or {}
    return data.get(lang) or data.get("en") or data
 
 
def _stringify(value, indent=0) -> str:
    pad = "  " * indent
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        out = []
        for v in value:
            if isinstance(v, dict):
                if "name" in v:
                    role = v.get("designation") or v.get("role") or ""
                    out.append(f"{pad}• {v['name']}{(' — ' + role) if role else ''}")
                else:
                    out.append(_stringify(v, indent))
            else:
                out.append(f"{pad}• {v}")
        return "\n".join(out)
    if isinstance(value, dict):
        out = []
        for k, v in value.items():
            label = str(k).replace("_", " ").title()
            sv = _stringify(v, indent + 1)
            if "\n" in sv or (isinstance(v, (list, dict)) and v):
                out.append(f"{pad}{label}:\n{sv}")
            else:
                out.append(f"{pad}{label}: {sv}")
        return "\n".join(out)
    return str(value)
 
 
def _quick(q: str, lang: str):
    """Fast exact-match answers for the most common questions."""
    m = _meta()
 
    if any(k in q for k in ["college name", "name of the college", "కళాశాల పేరు", "కాలేజీ పేరు"]):
        return m.get("college_name_te") if lang == "te" else m.get("college_name_en")
 
    if any(k in q for k in ["location", "address", "where", "ఎక్కడ"]):
        return m.get("location")
 
    if "naac" in q or "grade" in q or "accredit" in q:
        return m.get("accreditation") or "NAAC 'A' Grade"
 
    if "affiliat" in q:
        return m.get("affiliation")
 
    gen = _section_data("general_information", lang)
    if isinstance(gen, dict):
        if "principal" in q and "vice" not in q and gen.get("principal"):
            name = gen["principal"]
            return (
                f"మన కాలేజీ ప్రిన్సిపల్ {name} గారు."
                if lang == "te"
                else f"The Principal of Ideal College is {name}."
            )
        if ("vice" in q and "principal" in q) or "vice principal" in q:
            vp = gen.get("vice_principal", "")
            if vp:
                return (
                    f"మన కాలేజీ వైస్ ప్రిన్సిపల్ {vp} గారు."
                    if lang == "te"
                    else f"The Vice Principal of Ideal College is {vp}."
                )
        if "academic director" in q or "ranjith" in q:
            return f"Academic Director: {gen.get('academic_director', 'Ranjith Sir')}"
        if "administrative director" in q or "vasu" in q:
            return f"Administrative Director: {gen.get('administrative_director', 'Vasu Sir')}"
        if any(k in q for k in ["contact", "phone", "ఫోన్", "number"]):
            return f"📞 {gen.get('contact', '')}\n📧 {gen.get('email', '')}"
        if any(k in q for k in ["email", "mail"]):
            return gen.get("email")
        if any(k in q for k in ["website", "site", "link"]):
            return gen.get("website")
        if any(k in q for k in ["timing", "hours", "time", "సమయం", "time enti"]):
            return (
                f"🕘 {gen.get('college_timings', '')}\n"
                f"🍽 Lunch: {gen.get('lunch_break', '')}\n"
                f"👨‍🎓 Students: {gen.get('college_strength', '')}"
            )
        if any(k in q for k in ["strength", "students", "how many students"]):
            return gen.get("college_strength")
 
    return None
 
 
SECTION_HINTS = [
    (["course", "ug", "pg", "stream", "branch", "కోర్సు", "courses emi", "courses enti"], "courses"),
    (["fee", "fees", "ఫీజు", "tuition", "fee enti", "fee ela", "annual fee"], "fee_structure"),
    (["hostel", "హాస్టల్", "accommodation", "hostel fee", "mess", "hostel enti"], "hostel_and_amenities"),
    (["bus", "transport", "బస్", "vehicle", "bus facility"], "transport"),
    (["library", "లైబ్రరీ", "books", "librarian"], "library"),
    (["exam", "attendance", "పరీక్ష", "minimum attendance"], "examinations"),
    (["facility", "facilities", "lab", "wifi", "playground", "cafeteria",
      "cctv", "parking", "auditorium", "ro water", "సదుపాయ"], "campus_facilities"),
    (["placement", "placements", "drives", "company", "companies", "selected",
      "ప్లేస్‌మెంట్", "recruited", "package", "job", "campus drive"], "placements"),
    (["faculty", "hod", "department", "staff", "teacher", "professor",
      "సిబ్బంది", "evaru hod", "hod evaru"], "faculty_and_departments"),
    (["governance", "director", "admin", "exam incharge"], "governance_and_administration"),
    (["admission", "eligibility", "documents", "అడ్మిషన్", "apply", "join",
      "admission ela", "admission kosam"], "admissions"),
    (["sport", "nss", "ncc", "cultural", "cricket", "volleyball", "activity"], "sports_and_activities"),
    (["history", "founder", "established", "founded", "estab"], "historical_journey"),
    (["rule", "uniform", "ragging", "mobile", "attendance rule"], "student_rules"),
    (["scholarship", "scholarships", "financial aid"], "admissions"),
    (["soft skill", "crt", "spoken english", "competitive exam"], "crt_and_soft_skills"),
]
 
 
def _resolve_section(q: str):
    for keys, sec in SECTION_HINTS:
        if any(k in q for k in keys):
            return sec
    return None
 
 
def _format_section(section_key: str, q: str, lang: str = "en") -> str:
    data = _section_data(section_key, lang)
    if not data:
        return ""
 
    if section_key == "faculty_and_departments" and isinstance(data, dict):
        depts = data.get("departments", {}) or {}
        target = None
        dept_aliases = {
            "agriculture":          ["agriculture", "agri"],
            "fisheries":            ["fisheries", "aqua", "fish"],
            "fsn_and_food_technology": ["food", "fsn", "nutrition", "food technology"],
            "bba":                  ["bba", "business"],
            "computer_science":     ["computer", "cs", "bca", "mca", "ai", "computers"],
        }
        for k, aliases in dept_aliases.items():
            if any(a in q for a in aliases) and k in depts:
                target = k
                break
        if target:
            d = depts[target]
            lines = [f"🏫 {d.get('name', target.replace('_', ' ').title())}"]
            if d.get("hod"):
                lines.append(f"HOD: {d['hod']}")
            if d.get("hods"):
                for k, v in d["hods"].items():
                    lines.append(f"HOD ({k.upper()}): {v}")
            faculty = d.get("faculty") or []
            if faculty:
                lines.append("Faculty:")
                for f in faculty:
                    lines.append(f"  • {f.get('name', '')} — {f.get('designation', '')}")
            return "\n".join(lines)
        names = [d.get("name", k) for k, d in depts.items()]
        total = data.get("total_faculty")
        body = "\n".join(f"  • {n}" for n in names)
        tail = f"\nTotal Faculty: {total}" if total else ""
        return f"Departments ({len(names)}):\n{body}{tail}"
 
    if section_key == "placements" and isinstance(data, dict):
        lines = ["🎓 Placements at Ideal College"]
        st = data.get("statistics", {}) or {}
        if "2026" in st:
            sd = st["2026"].get("seniors_drive", {}) or {}
            lines.append(
                f"2026 Drive — Companies: {sd.get('visited_companies', '-')}, "
                f"Participated: {sd.get('students_participated', '-')}, "
                f"Selected: {sd.get('students_selected', '-')}."
            )
        if "2025" in st:
            lines.append(f"2025 — {st['2025'].get('selected_students', '-')} students selected.")
        phys = data.get("companies_visited_physical") or []
        if phys:
            lines.append("Top recruiters: " + ", ".join(phys[:8]) + ".")
        if data.get("training"):
            lines.append(f"Training: {data['training']}.")
        return "\n".join(lines)
 
    return _stringify(data)
 
 
def _explain_with_ai(raw_answer: str, question: str, lang: str) -> str:
    """Ask AI to rewrite a raw database answer as a friendly explanation."""
    if not _has_ai_keys():
        return raw_answer
    try:
        from services.llm_service import query_ai
        if lang == "te":
            prompt = (
                f"విద్యార్థి ప్రశ్న: {question}\n\n"
                f"కాలేజీ డేటాబేస్ సమాచారం:\n{raw_answer}\n\n"
                "పై సమాచారాన్ని తెలుగులో స్పష్టంగా, సరళంగా విద్యార్థికి అర్థమయ్యే విధంగా వివరించండి. "
                "5 వాక్యాల లోపు ఉండాలి."
            )
        else:
            prompt = (
                f"Question: {question}\n\n"
                f"College Database says:\n{raw_answer}\n\n"
                "Rewrite the above as a clear, teacher-style explanation for a student. "
                "Keep it accurate, add helpful context where relevant, and keep it under 5 sentences."
            )
        result = query_ai(prompt=prompt, lang=lang, mode="college")
        # Don't use AI result if it looks like an error
        bad_phrases = ["unable to reach", "try again", "providers", "moment",
                       "సేవలు అందుబాటులో లేవు"]
        if any(p in result.lower() for p in bad_phrases):
            return raw_answer
        return result
    except Exception as e:
        logger.warning("_explain_with_ai failed: %s", e)
        return raw_answer
 
 
def get_college_answer(message: str, lang: str = "en", explain: bool = True):
    if not message:
        return None
    q = message.lower().strip()
 
    # Check if the question is actually about the college
    is_about_college = (
        any(t in q for t in TRIGGER_WORDS)
        or any(k.lower() in q for k in COLLEGE_KEYWORDS)
    )
    if not is_about_college:
        return None
 
    # 1. Try quick direct-match answers
    quick = _quick(q, lang)
    if quick:
        raw = str(quick)
        if explain and _has_ai_keys() and len(raw) < 300:
            return _explain_with_ai(raw, message, lang)
        return raw
 
    # 2. Try section-based answers
    sec = _resolve_section(q)
    if sec:
        out = _format_section(sec, q, lang)
        if out:
            if explain and _has_ai_keys():
                return _explain_with_ai(out, message, lang)
            return out
 
    # 3. General "about college" fallback
    if any(k in q for k in ["about", "info", "tell me", "details", "overview", "ఏమి", "గురించి"]):
        m = _meta()
        gen = _section_data("general_information", lang) or {}
        parts = [
            f"🏫 {m.get('college_name_en', 'Ideal College of Arts and Sciences')}",
            f"📍 {m.get('location', 'Vidyuth Nagar, Kakinada, Andhra Pradesh')}",
            f"🎓 Affiliation: {m.get('affiliation', 'Adikavi Nannaya University')}",
            f"🏅 Accreditation: {m.get('accreditation', 'NAAC A Grade')}",
        ]
        if gen.get("principal"):
            parts.append(f"👨‍🏫 Principal: {gen['principal']}")
        if gen.get("college_timings"):
            parts.append(f"🕘 Timings: {gen['college_timings']}")
        if gen.get("contact"):
            parts.append(f"📞 {gen['contact']}")
        if gen.get("website"):
            parts.append(f"🌐 {gen['website']}")
        return "\n".join(parts)
 
    # 4. Scan all section keywords
    for key, sec_data in _sections().items():
        kws = (sec_data.get("keywords_en") or []) + (sec_data.get("keywords_te") or [])
        if any(k.lower() in q for k in kws):
            out = _format_section(key, q, lang)
            if out:
                if explain and _has_ai_keys():
                    return _explain_with_ai(out, message, lang)
                return out
 
    return None
 
 
def get_college_context() -> str:
    if _get_context:
        try:
            ctx = _get_context()
            if ctx:
                return ctx
        except Exception:
            pass
    m = _meta()
    gen = _section_data("general_information") or {}
    courses = _section_data("courses") or {}
    fee = _section_data("fee_structure") or {}
    return (
        f"College: {m.get('college_name_en', 'Ideal College of Arts and Sciences')}\n"
        f"Location: {m.get('location', 'Vidyuth Nagar, Kakinada, Andhra Pradesh')}\n"
        f"Affiliation: {m.get('affiliation', '')}\n"
        f"Accreditation: {m.get('accreditation', '')}\n"
        f"Principal: {gen.get('principal', '')}\n"
        f"Vice Principal: {gen.get('vice_principal', '')}\n"
        f"Timings: {gen.get('college_timings', '')}\n"
        f"Contact: {gen.get('contact', '')} | {gen.get('email', '')}\n"
        f"Website: {gen.get('website', '')}\n"
        f"UG Courses (3yr): {', '.join(courses.get('ug', []))}\n"
        f"PG Courses (2yr): {', '.join(courses.get('pg', []))}\n"
        f"Fee Range: {fee.get('range', '')}\n"
        f"Hostel: Available — ₹60,000/year\n"
        f"Placements 2026: 329 selected from 362 participants across 9 companies\n"
    )
 
 
__all__ = ["COLLEGE_KEYWORDS", "get_college_answer", "get_college_context"]
 