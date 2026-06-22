"""
services/college_service.py
 
College data retrieval — DB first, AI only as last resort.
Returns short, direct answers. No padding.
"""
 
import os
import logging
from data.college_data import COLLEGE_DATABASE
 
logger = logging.getLogger(__name__)
 
try:
    from data.college_data import get_college_context as _get_context
    from data.college_data import COLLEGE_KEYWORDS
except Exception:
    _get_context = None
    COLLEGE_KEYWORDS = []
 
 
# Gate words: question must contain at least one of these OR a COLLEGE_KEYWORD
# to be handled here. Includes "director", "ranjith", "vasu" explicitly.
TRIGGER_WORDS = [
    "ideal", "college", "campus", "kakinada college", "vidyuth nagar",
    # people that don't appear in COLLEGE_KEYWORDS of college_data.py
    "director", "academic director", "administrative director",
    "ranjith", "vasu", "satyanarayana", "kama raju",
    "కళాశాల", "కాలేజీ", "ఐడియల్",
]
 
# Extended COLLEGE_KEYWORDS for the gate (covers words missing from college_data.py list)
_EXTRA_GATE_WORDS = [
    "director", "ranjith", "vasu", "satyanarayana", "kama raju",
    "academic", "administrative", "exam incharge",
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
    """Fast direct-match — returns string immediately, no AI needed."""
    m = _meta()
 
    # College name
    if any(k in q for k in ["college name", "name of the college", "కళాశాల పేరు"]):
        return m.get("college_name_te") if lang == "te" else m.get("college_name_en")
 
    # Location
    if any(k in q for k in ["location", "address", "where is", "ఎక్కడ"]):
        return m.get("location")
 
    # NAAC
    if "naac" in q or "accredit" in q:
        return m.get("accreditation") or "NAAC 'A' Grade"
 
    # Affiliation
    if "affiliat" in q:
        return m.get("affiliation")
 
    gen = _section_data("general_information", lang)
    if not isinstance(gen, dict):
        return None
 
    # Principal
    if "principal" in q and "vice" not in q:
        name = gen.get("principal", "")
        if name:
            return (f"మన కాలేజీ ప్రిన్సిపల్ {name} గారు."
                    if lang == "te" else
                    f"The Principal of Ideal College is {name}.")
 
    # Vice Principal
    if "vice principal" in q or ("vice" in q and "principal" in q):
        vp = gen.get("vice_principal", "")
        if vp:
            return (f"మన కాలేజీ వైస్ ప్రిన్సిపల్ {vp} గారు."
                    if lang == "te" else
                    f"The Vice Principal of Ideal College is {vp}.")
 
    # Academic Director — matches: "academic director", "ranjith", "ranjith sir"
    if any(k in q for k in ["academic director", "ranjith"]):
        name = gen.get("academic_director", "Ranjith Sir")
        return (f"మన కాలేజీ Academic Director {name} గారు."
                if lang == "te" else
                f"The Academic Director of Ideal College is {name}.")
 
    # Administrative Director — matches: "administrative director", "vasu", "vasu sir"
    if any(k in q for k in ["administrative director", "admin director", "vasu"]):
        name = gen.get("administrative_director", "Vasu Sir")
        return (f"మన కాలేజీ Administrative Director {name} గారు."
                if lang == "te" else
                f"The Administrative Director of Ideal College is {name}.")
 
    # Generic "director" — show both
    if "director" in q:
        acad  = gen.get("academic_director", "Ranjith Sir")
        admin = gen.get("administrative_director", "Vasu Sir")
        return (
            f"Academic Director: {acad}\n"
            f"Administrative Director: {admin}"
        )
 
    # Contact / Phone
    if any(k in q for k in ["contact", "phone", "ఫోన్", "number", "call"]):
        return f"📞 {gen.get('contact', '')}\n📧 {gen.get('email', '')}"
 
    # Email
    if any(k in q for k in ["email", "mail"]):
        return gen.get("email")
 
    # Website
    if any(k in q for k in ["website", "site", "link", "url"]):
        return gen.get("website")
 
    # Timings
    if any(k in q for k in ["timing", "timings", "hours", "time", "సమయం"]):
        t = gen.get("college_timings", "9:30 AM - 3:45 PM (Mon–Sat)")
        l = gen.get("lunch_break", "1:00 PM - 1:45 PM")
        return f"🕘 {t}\n🍽 Lunch: {l}"
 
    # Strength
    if any(k in q for k in ["strength", "how many students", "total students"]):
        return gen.get("college_strength")
 
    return None
 
 
# Section routing table
SECTION_HINTS = [
    (["course", "ug", "pg", "stream", "branch", "కోర్సు",
      "courses emi", "courses enti", "syllabus", "subjects"], "courses"),
    (["fee", "fees", "ఫీజు", "tuition", "fee enti", "fee ela",
      "annual fee", "how much"], "fee_structure"),
    (["hostel", "హాస్టల్", "accommodation", "hostel fee",
      "mess", "hostel enti", "boys hostel", "girls hostel"], "hostel_and_amenities"),
    (["bus", "transport", "బస్", "vehicle", "bus facility"], "transport"),
    (["library", "లైబ్రరీ", "books", "librarian"], "library"),
    (["exam", "attendance", "పరీక్ష", "minimum attendance"], "examinations"),
    (["facility", "facilities", "lab", "wifi", "playground", "cafeteria",
      "cctv", "parking", "auditorium", "ro water", "సదుపాయ"], "campus_facilities"),
    (["placement", "placements", "drives", "company", "companies", "selected",
      "ప్లేస్‌మెంట్", "recruited", "package", "campus drive"], "placements"),
    (["faculty", "hod", "department", "staff", "teacher", "professor",
      "సిబ్బంది", "hod evaru", "lecturer"], "faculty_and_departments"),
    (["governance", "exam incharge", "suresh"], "governance_and_administration"),
    (["admission", "eligibility", "documents", "అడ్మిషన్", "apply",
      "join", "how to join", "admission ela"], "admissions"),
    (["sport", "nss", "ncc", "cultural", "cricket", "volleyball"], "sports_and_activities"),
    (["history", "founder", "established", "founded"], "historical_journey"),
    (["rule", "uniform", "ragging", "mobile phone"], "student_rules"),
    (["scholarship", "financial aid"], "admissions"),
    (["soft skill", "crt", "spoken english", "competitive exam"], "crt_and_soft_skills"),
]
 
 
def _resolve_section(q: str):
    for keys, sec in SECTION_HINTS:
        if any(k in q for k in keys):
            return sec
    return None
 
 
def _format_fee(data: dict, q: str) -> str:
    """Return a short, direct fee answer for the course asked."""
    course_map = {
        "bca":            ("bca",            "₹50,000/year"),
        "bsc":            ("bsc_computers",  "₹50,000/year"),
        "bba":            ("bba",            "₹50,000/year"),
        "agriculture":    ("agriculture",    "₹55,000/year"),
        "food technology":("food_technology","₹60,000/year"),
        "food":           ("food_technology","₹60,000/year"),
        "aqua":           ("aqua_fisheries", "₹45,000/year"),
        "fisheries":      ("aqua_fisheries", "₹45,000/year"),
        "mca":            (None,             "Please contact the college for MCA fee details."),
    }
    for keyword, (key, default) in course_map.items():
        if keyword in q:
            fee = data.get(key, default) if key else default
            label = keyword.upper() if len(keyword) <= 4 else keyword.title()
            return f"The annual {label} fee at Ideal College is {fee}."
    return f"Fee range at Ideal College: {data.get('range', '₹45,000 – ₹60,000 per year')}."
 
 
def _format_section(section_key: str, q: str, lang: str = "en") -> str:
    data = _section_data(section_key, lang)
    if not data:
        return ""
 
    # Fees — short direct answer
    if section_key == "fee_structure" and isinstance(data, dict):
        return _format_fee(data, q)
 
    # Faculty — short per-department answer
    if section_key == "faculty_and_departments" and isinstance(data, dict):
        depts = data.get("departments", {}) or {}
        dept_aliases = {
            "agriculture":             ["agriculture", "agri"],
            "fisheries":               ["fisheries", "aqua", "fish"],
            "fsn_and_food_technology": ["food", "fsn", "nutrition"],
            "bba":                     ["bba", "business"],
            "computer_science":        ["computer", "cs", "bca", "mca", "computers"],
        }
        for k, aliases in dept_aliases.items():
            if any(a in q for a in aliases) and k in depts:
                d = depts[k]
                lines = [f"🏫 {d.get('name', k.replace('_', ' ').title())}"]
                if d.get("hod"):
                    lines.append(f"HOD: {d['hod']}")
                if d.get("hods"):
                    for hk, hv in d["hods"].items():
                        lines.append(f"HOD ({hk.upper()}): {hv}")
                return "\n".join(lines)
        # Generic: list all departments
        names = [d.get("name", k) for k, d in depts.items()]
        total = data.get("total_faculty")
        body  = "\n".join(f"  • {n}" for n in names)
        tail  = f"\nTotal Faculty: {total}" if total else ""
        return f"Departments:\n{body}{tail}"
 
    # Placements — short summary
    if section_key == "placements" and isinstance(data, dict):
        st = data.get("statistics", {}) or {}
        lines = ["🎓 Ideal College Placements:"]
        if "2026" in st:
            sd = st["2026"].get("seniors_drive", {}) or {}
            lines.append(
                f"2026: {sd.get('students_selected', '-')} students selected "
                f"from {sd.get('students_participated', '-')} across "
                f"{sd.get('visited_companies', '-')} companies."
            )
        if "2025" in st:
            lines.append(f"2025: {st['2025'].get('selected_students', '-')} students selected.")
        phys = data.get("companies_visited_physical") or []
        if phys:
            lines.append("Recruiters: " + ", ".join(phys[:6]) + ".")
        return "\n".join(lines)
 
    return _stringify(data)
 
 
def _ai_fallback(message: str, lang: str, college_context: str) -> str:
    """Last resort: ONE AI call using college context."""
    try:
        from services.llm_service import query_ai
        return query_ai(prompt=message, lang=lang, context=college_context, mode="college")
    except Exception as e:
        logger.warning("AI fallback failed: %s", e)
        return (
            "దయచేసి కాలేజీని నేరుగా సంప్రదించండి: 0884-2384382"
            if lang == "te" else
            "Please contact the college directly: 0884-2384382"
        )
 
 
def get_college_answer(message: str, lang: str = "en", explain: bool = True):
    if not message:
        return None
    q = message.lower().strip()
 
    # Gate: only handle if the question is about this college
    is_about_college = (
        any(t in q for t in TRIGGER_WORDS)
        or any(k.lower() in q for k in (COLLEGE_KEYWORDS or []))
        or any(k in q for k in _EXTRA_GATE_WORDS)
    )
    if not is_about_college:
        return None
 
    # 1. Fast direct match (no AI)
    quick = _quick(q, lang)
    if quick:
        return str(quick)
 
    # 2. Section-based DB answer (no AI)
    sec = _resolve_section(q)
    if sec:
        out = _format_section(sec, q, lang)
        if out:
            return out
 
    # 3. General overview
    if any(k in q for k in ["about", "info", "tell me", "details", "overview", "గురించి"]):
        m   = _meta()
        gen = _section_data("general_information", lang) or {}
        parts = [
            f"🏫 {m.get('college_name_en', 'Ideal College of Arts and Sciences')}",
            f"📍 {m.get('location', 'Vidyuth Nagar, Kakinada, Andhra Pradesh')}",
            f"🎓 Affiliation: {m.get('affiliation', 'Adikavi Nannaya University')}",
            f"🏅 Accreditation: {m.get('accreditation', 'NAAC A Grade')}",
        ]
        if gen.get("principal"):
            parts.append(f"👨‍🏫 Principal: {gen['principal']}")
        if gen.get("contact"):
            parts.append(f"📞 {gen['contact']}")
        if gen.get("website"):
            parts.append(f"🌐 {gen['website']}")
        return "\n".join(parts)
 
    # 4. Keyword scan across all sections
    for key, sec_data in _sections().items():
        kws = (sec_data.get("keywords_en") or []) + (sec_data.get("keywords_te") or [])
        if any(k.lower() in q for k in kws):
            out = _format_section(key, q, lang)
            if out:
                return out
 
    # 5. AI fallback with college context (ONE call only)
    if _has_ai_keys():
        return _ai_fallback(message, lang, get_college_context())
 
    return None
 
 
def get_college_context() -> str:
    if _get_context:
        try:
            ctx = _get_context()
            if ctx:
                return ctx
        except Exception:
            pass
    m   = _meta()
    gen = _section_data("general_information") or {}
    courses = _section_data("courses") or {}
    fee     = _section_data("fee_structure") or {}
    return (
        f"College: {m.get('college_name_en', 'Ideal College of Arts and Sciences')}\n"
        f"Location: {m.get('location', 'Vidyuth Nagar, Kakinada, Andhra Pradesh')}\n"
        f"Affiliation: {m.get('affiliation', 'Adikavi Nannaya University')}\n"
        f"Accreditation: {m.get('accreditation', 'NAAC A Grade')}\n"
        f"Principal: {gen.get('principal', 'Dr. T. Satyanarayana')}\n"
        f"Vice Principal: {gen.get('vice_principal', 'Mr. V. Kama Raju')}\n"
        f"Academic Director: {gen.get('academic_director', 'Ranjith Sir')}\n"
        f"Administrative Director: {gen.get('administrative_director', 'Vasu Sir')}\n"
        f"Timings: {gen.get('college_timings', '9:30 AM - 3:45 PM (Mon-Sat)')}\n"
        f"Lunch: {gen.get('lunch_break', '1:00 PM - 1:45 PM')}\n"
        f"Contact: {gen.get('contact', '0884-2384382')} | {gen.get('email', 'idealcolleges@gmail.com')}\n"
        f"Website: {gen.get('website', 'https://idealcollege.edu.in')}\n"
        f"UG Courses (3yr): {', '.join(courses.get('ug', []))}\n"
        f"PG Courses (2yr): {', '.join(courses.get('pg', []))}\n"
        f"Fee Range: {fee.get('range', '₹45,000–₹60,000/year')}\n"
        f"BCA Fee: {fee.get('bca', '₹50,000/year')}\n"
        f"Hostel: Available — ₹60,000/year (separate boys & girls)\n"
        f"Placements 2026: 329 selected from 362 across 9 companies\n"
    )
 
 
__all__ = ["COLLEGE_KEYWORDS", "get_college_answer", "get_college_context"]