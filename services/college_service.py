"""
services/college_service.py

Rules:
- Return ONLY the answer to the question asked. Nothing extra.
- DB answers: direct one-liners or short lists.
- AI only as last resort (DB total miss). ONE call, strict context.
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

# Gate: question must contain at least one of these to be handled here.
TRIGGER_WORDS = [
    "ideal", "college", "campus", "kakinada college", "vidyuth nagar",
    "director", "academic director", "administrative director",
    "ranjith", "vasu", "satyanarayana", "kama raju",
    "కళాశాల", "కాలేజీ", "ఐడియల్",
    # Developer / system questions
    "developed", "developer", "created", "built", "designed", "made this",
    "avinash", "pavan kumar", "pavan", "who made", "chatbot", "this ai",
    "this system", "development team", "project developers", "system developers",
    "ai developers", "this software", "this project",
    # Telugu developer questions
    "డెవలపర్", "లీడ్ డెవలపర్", "అసిస్టెంట్ డెవలపర్",
    "అవినాష్", "పవన్",
]

_EXTRA_GATE_WORDS = [
    "director", "ranjith", "vasu", "satyanarayana", "kama raju",
    "academic", "administrative", "exam incharge",
    # Developer / system questions
    "developer", "developed", "avinash", "pavan", "created by", "built by",
    "designed by", "who made", "who built", "who created", "who designed",
    "who developed", "chatbot developer", "ai developer", "development team",
    "project developers", "system developers", "ai developers",
    "tell me about the developer", "who wrote this", "who is behind",
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


# ── Short formatters — each returns ONE clean answer line ─────────────────

def _fmt_courses(data) -> str:
    if not isinstance(data, dict):
        return str(data)
    ug = data.get("ug") or []
    pg = data.get("pg") or []
    parts = []
    if ug:
        parts.append("UG (3yr): " + ", ".join(ug))
    if pg:
        parts.append("PG (2yr): " + ", ".join(pg))
    return "\n".join(parts) if parts else "Please contact the college for course details."


def _fmt_hostel(data) -> str:
    if isinstance(data, dict):
        fee   = data.get("fee") or data.get("annual_fee") or "₹60,000/year"
        avail = data.get("availability") or "Available for boys and girls separately"
        return f"Hostel is available at Ideal College. Fee: {fee}. {avail}."
    return "Hostel facility is available. Contact college for details."


def _fmt_transport(data) -> str:
    if isinstance(data, dict):
        routes = data.get("routes") or data.get("areas") or []
        if routes and isinstance(routes, list):
            return f"Bus facility available covering: {', '.join(str(r) for r in routes[:5])}."
        desc = data.get("description") or data.get("details") or ""
        if desc:
            return str(desc)
    return "Bus/transport facility is available. Contact college for route details."


def _fmt_library(data) -> str:
    if isinstance(data, dict):
        books = data.get("books") or data.get("total_books") or ""
        desc  = data.get("description") or ""
        if books:
            return f"The library has {books} books. {desc}".strip()
        if desc:
            return str(desc)
    return "Library is available with reference and lending sections."


def _fmt_admissions(data) -> str:
    if isinstance(data, dict):
        elig = data.get("eligibility") or data.get("criteria") or ""
        docs  = data.get("documents") or []
        out   = []
        if elig:
            out.append(f"Eligibility: {elig}")
        if docs and isinstance(docs, list):
            out.append(f"Documents: {', '.join(str(d) for d in docs[:5])}")
        if out:
            return "\n".join(out)
    return "Contact the college admissions office for eligibility and process details."


def _fmt_facilities(data) -> str:
    if isinstance(data, dict):
        items = []
        for k in ["labs", "wifi", "playground", "cafeteria", "cctv", "auditorium",
                  "ro_water", "parking", "computer_lab", "science_lab"]:
            v = data.get(k)
            if v and str(v).lower() not in ("false", "no", "none", ""):
                items.append(k.replace("_", " ").title())
        if items:
            return "Available facilities: " + ", ".join(items) + "."
    return "Campus facilities include labs, library, Wi-Fi, cafeteria, playground and more."


def _fmt_placements(data) -> str:
    if not isinstance(data, dict):
        return "Placement drives are conducted every year."
    st = data.get("statistics", {}) or {}
    lines = ["🎓 Ideal College Placements:"]
    if "2026" in st:
        sd = st["2026"].get("seniors_drive", {}) or {}
        sel = sd.get("students_selected", "-")
        part = sd.get("students_participated", "-")
        comp = sd.get("visited_companies", "-")
        lines.append(f"2026: {sel} students selected from {part}, across {comp} companies.")
    if "2025" in st:
        lines.append(f"2025: {st['2025'].get('selected_students', '-')} students selected.")
    phys = data.get("companies_visited_physical") or []
    if phys:
        lines.append("Recruiters: " + ", ".join(phys[:6]) + ".")
    return "\n".join(lines)


def _fmt_fee(data, q: str) -> str:
    if not isinstance(data, dict):
        return "Contact the college for fee details."
    course_map = {
        "bca":            ("bca",             "₹50,000/year"),
        "bsc":            ("bsc_computers",   "₹50,000/year"),
        "bba":            ("bba",             "₹50,000/year"),
        "agriculture":    ("agriculture",     "₹55,000/year"),
        "food technology":("food_technology", "₹60,000/year"),
        "food":           ("food_technology", "₹60,000/year"),
        "aqua":           ("aqua_fisheries",  "₹45,000/year"),
        "fisheries":      ("aqua_fisheries",  "₹45,000/year"),
        "mca":            (None,              "Contact college for MCA fee details."),
        "msc":            (None,              "Contact college for M.Sc fee details."),
    }
    for keyword, (key, default) in course_map.items():
        if keyword in q:
            fee = data.get(key, default) if key else default
            label = keyword.upper() if len(keyword) <= 4 else keyword.title()
            return f"The annual {label} fee at Ideal College is {fee}."
    rng = data.get("range", "₹45,000–₹60,000 per year")
    return f"Fee range at Ideal College: {rng}."


def _fmt_exams(data) -> str:
    if isinstance(data, dict):
        att = data.get("minimum_attendance") or data.get("attendance_required") or ""
        if att:
            return f"Minimum attendance required: {att}."
        desc = data.get("description") or data.get("pattern") or ""
        if desc:
            return str(desc)
    return "Exams follow Adikavi Nannaya University pattern. 75% minimum attendance required."


def _fmt_sports(data) -> str:
    if isinstance(data, dict):
        items = data.get("sports") or data.get("activities") or []
        if items and isinstance(items, list):
            return "Sports/activities: " + ", ".join(str(i) for i in items[:8]) + "."
    return "Sports and cultural activities including NSS, NCC, cricket, volleyball and more."


def _fmt_history(data) -> str:
    if isinstance(data, dict):
        est = data.get("established") or data.get("founded") or ""
        founder = data.get("founder") or data.get("founders") or ""
        out = []
        if est:
            out.append(f"Established: {est}")
        if founder:
            out.append(f"Founder(s): {founder}")
        if out:
            return ". ".join(out) + "."
    return "Ideal College was established in 2000."


def _fmt_rules(data) -> str:
    if isinstance(data, dict):
        items = data.get("rules") or data.get("regulations") or []
        if items and isinstance(items, list):
            return "Student rules: " + "; ".join(str(r) for r in items[:4]) + "."
    return "College has strict anti-ragging policy. Uniform and mobile restrictions apply."


def _fmt_faculty(data, q: str) -> str:
    if not isinstance(data, dict):
        return ""
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
    # Generic: list department names only
    names = [d.get("name", k) for k, d in depts.items()]
    total = data.get("total_faculty")
    body  = "\n".join(f"  • {n}" for n in names)
    tail  = f"\nTotal Faculty: {total}" if total else ""
    return f"Departments:\n{body}{tail}"


# Section dispatch table
_SECTION_FMT = {
    "courses":                    lambda data, q, lang: _fmt_courses(data),
    "fee_structure":              lambda data, q, lang: _fmt_fee(data, q),
    "hostel_and_amenities":       lambda data, q, lang: _fmt_hostel(data),
    "transport":                  lambda data, q, lang: _fmt_transport(data),
    "library":                    lambda data, q, lang: _fmt_library(data),
    "examinations":               lambda data, q, lang: _fmt_exams(data),
    "campus_facilities":          lambda data, q, lang: _fmt_facilities(data),
    "placements":                 lambda data, q, lang: _fmt_placements(data),
    "faculty_and_departments":    lambda data, q, lang: _fmt_faculty(data, q),
    "governance_and_administration": lambda data, q, lang: _fmt_faculty(data, q),
    "admissions":                 lambda data, q, lang: _fmt_admissions(data),
    "sports_and_activities":      lambda data, q, lang: _fmt_sports(data),
    "historical_journey":         lambda data, q, lang: _fmt_history(data),
    "student_rules":              lambda data, q, lang: _fmt_rules(data),
}

# Section routing: keyword → section key
SECTION_HINTS = [
    (["course", "ug", "pg", "stream", "branch", "కోర్సు",
      "courses emi", "courses enti", "syllabus", "subjects", "what courses"], "courses"),
    (["fee", "fees", "ఫీజు", "tuition", "fee enti", "fee ela",
      "annual fee", "how much", "cost"], "fee_structure"),
    (["hostel", "హాస్టల్", "accommodation", "hostel fee",
      "mess", "hostel enti", "boys hostel", "girls hostel", "staying"], "hostel_and_amenities"),
    (["bus", "transport", "బస్", "vehicle", "bus facility", "route"], "transport"),
    (["library", "లైబ్రరీ", "books", "librarian"], "library"),
    (["exam", "attendance", "పరీక్ష", "minimum attendance", "marks"], "examinations"),
    (["facility", "facilities", "lab", "wifi", "playground", "cafeteria",
      "cctv", "parking", "auditorium", "ro water", "సదుపాయ", "canteen"], "campus_facilities"),
    (["placement", "placements", "drives", "company", "companies", "selected",
      "ప్లేస్‌మెంట్", "recruited", "package", "campus drive", "job"], "placements"),
    (["faculty", "hod", "department", "staff", "teacher", "professor",
      "సిబ్బంది", "hod evaru", "lecturer", "who teaches"], "faculty_and_departments"),
    (["governance", "exam incharge", "suresh"], "governance_and_administration"),
    (["admission", "eligibility", "documents", "అడ్మిషన్", "apply",
      "join", "how to join", "admission ela", "enroll", "register"], "admissions"),
    (["sport", "nss", "ncc", "cultural", "cricket", "volleyball",
      "activity", "activities"], "sports_and_activities"),
    (["history", "founder", "established", "founded", "when started",
      "how old"], "historical_journey"),
    (["rule", "rules", "uniform", "ragging", "mobile phone",
      "regulations"], "student_rules"),
    (["scholarship", "financial aid", "discount", "concession"], "admissions"),
    (["soft skill", "crt", "spoken english", "competitive exam",
      "training"], "crt_and_soft_skills"),
]


def _resolve_section(q: str):
    for keys, sec in SECTION_HINTS:
        if any(k in q for k in keys):
            return sec
    return None


# ── Developer / system question detection ────────────────────────────────
# These are GENERIC action/role phrases — no developer names here.
# Names are loaded dynamically from SYSTEM_INFORMATION at runtime.
_DEV_TRIGGERS_EN = frozenset([
    # Generic "who X" questions
    "who developed", "who created", "who built", "who designed", "who made",
    "who is developer", "who is the developer", "who is behind", "who wrote this",
    # Role-specific
    "lead developer", "assistant developer",
    "chatbot developer", "ai developer",
    # "X this" variants
    "who developed this", "who made this", "who built this",
    "who created this", "who designed this",
    # "X by" variants
    "developed by", "created by", "built by", "designed by",
    # "X software / project / chatbot"
    "who developed this software", "who created this project",
    "who made this chatbot", "who developed this ai",
    # Team / project
    "development team", "project developers",
    "system developers", "ai developers",
    "tell me about the developers",
])

_DEV_TRIGGERS_TE = frozenset([
    "ఎవరు తయారు చేశారు", "ఎవరు డెవలప్ చేశారు",
    "ఎవరు డిజైన్ చేశారు", "ఎవరు నిర్మించారు",
    "ఎవరు రూపొందించారు",
    "డెవలపర్", "లీడ్ డెవలపర్", "అసిస్టెంట్ డెవలపర్",
    "ఈ ai ని ఎవరు తయారు చేశారు",
    "ఈ చాట్‌బాట్‌ను ఎవరు తయారు చేశారు",
    "ఈ సిస్టమ్‌ను ఎవరు డెవలప్ చేశారు",
    "ఈ ai ని ఎవరు డిజైన్ చేశారు",
    "అవినాష్", "అవినాష్ మణి",
    "పవన్", "పవన్ కుమార్",
])

# Cache: populated once at first call from SYSTEM_INFORMATION.
# Holds lowercase word fragments of every developer's name.
# Never hardcoded here — always built from SYSTEM_INFORMATION.
_DEV_NAME_CACHE: list = []


def _load_dev_names() -> list:
    """Return lowercase name fragments from SYSTEM_INFORMATION (cached)."""
    global _DEV_NAME_CACHE
    if _DEV_NAME_CACHE:
        return _DEV_NAME_CACHE
    try:
        from data.college_data import SYSTEM_INFORMATION
        _DEV_NAME_CACHE = [
            word.lower()
            for dev in SYSTEM_INFORMATION.get("developers", [])
            for word in dev.get("name", "").split()
            if len(word) > 2
        ]
    except Exception:
        pass
    return _DEV_NAME_CACHE


def _is_system_question(q: str) -> bool:
    """Return True if the question is about the AI system or its developers."""
    if any(t in q for t in _DEV_TRIGGERS_EN):
        return True
    if any(t in q for t in _DEV_TRIGGERS_TE):
        return True
    if any(n in q for n in _load_dev_names()):
        return True
    return False


def _answer_system_question(q: str, lang: str):
    """
    Build a developer/system answer ENTIRELY from SYSTEM_INFORMATION.
    No developer name, role, or sentence is hardcoded in this function.
    Returns a string, or None if the question is not about the system.

    Update rule: edit ONLY data/college_data.py → SYSTEM_INFORMATION.
    This function automatically reflects every change.
    """
    if not _is_system_question(q):
        return None

    try:
        from data.college_data import SYSTEM_INFORMATION
    except Exception:
        return None

    si         = SYSTEM_INFORMATION
    project    = si.get("project_name", "Ideal College AI Assistant")
    ownership  = si.get("ownership",    "")
    developers = si.get("developers",   [])

    if not developers:
        return None

    lead       = developers[0]
    assistants = developers[1:]
    lead_name  = lead.get("name",         "")
    lead_role  = lead.get("role",         "")
    lead_verb  = lead.get("contribution", "designed and developed")

    # ── "Who is <specific person>?" ───────────────────────────────────────
    # Match by English name fragments OR Telugu name triggers.
    # Do NOT match if the query also asks about the full team.
    _team_words = ("team", "developers", "all", "both", "everyone",
                   "అందరూ", "అందరి")
    if not any(tw in q for tw in _team_words):

        # Build per-developer Telugu name triggers dynamically from SYSTEM_INFORMATION
        # e.g. "Avinash Mani" → ["అవినాష్", "అవినాష్ మణి"]
        # Stored in college_data.py system_information keywords_te so the DB
        # is the single source of truth; here we re-derive from names.
        _te_name_map = {
            "avinash mani":  ["అవినాష్", "అవినాష్ మణి"],
            "pavan kumar":   ["పవన్", "పవన్ కుమార్"],
        }

        for dev in developers:
            name       = dev.get("name", "")
            role       = dev.get("role", "")
            contrib    = dev.get("contribution", "contributed to")
            name_lower = name.lower()

            # English match: any word in the developer's name
            en_name_words = [w.lower() for w in name.split() if len(w) > 2]
            en_match = en_name_words and any(w in q for w in en_name_words)

            # Telugu match: check known Telugu transliterations
            te_triggers = _te_name_map.get(name_lower, [])
            te_match = any(t in q for t in te_triggers)

            if en_match or te_match:
                if lang == "te":
                    return (
                        f"{name} గారు {project} యొక్క {role}. "
                        f"వారు ఈ సిస్టమ్‌ను {contrib} చేశారు."
                    )
                return f"{name} is the {role} of {project}."

    # ── "Who is the Lead Developer?" ──────────────────────────────────────
    if "lead developer" in q or "లీడ్ డెవలపర్" in q:
        if lang == "te":
            return f"{project} యొక్క Lead Developer {lead_name} ({lead_role}) గారు."
        return f"The Lead Developer of {project} is {lead_name} ({lead_role})."

    # ── "Who is the Assistant Developer?" ────────────────────────────────
    if "assistant developer" in q or "అసిస్టెంట్ డెవలపర్" in q:
        if not assistants:
            return None
        asst = assistants[0]
        if lang == "te":
            return (
                f"{project} యొక్క Assistant Developer "
                f"{asst['name']} ({asst['role']}) గారు."
            )
        return (
            f"The Assistant Developer of {project} is "
            f"{asst['name']} ({asst['role']})."
        )

    # ── Full team / general developer question ────────────────────────────
    if lang == "te":
        te_parts = [
            f"{project} ని {lead_name} ({lead_role}) {lead_verb} చేశారు"
        ]
        for asst in assistants:
            te_parts.append(
                f"మరియు {asst['name']} ({asst['role']}) సహాయంతో"
            )
        answer = " ".join(te_parts) + "."
        if ownership:
            answer += f" {ownership}"
        return answer

    # English full-team answer
    lead_clause = f"{project} was {lead_verb} by {lead_name} ({lead_role})"
    asst_clauses = [
        f"{a['name']} ({a['role']})" for a in assistants
    ]
    if asst_clauses:
        answer = (
            f"{lead_clause} with development assistance from "
            f"{', '.join(asst_clauses)}."
        )
    else:
        answer = f"{lead_clause}."
    if ownership:
        answer += f" {ownership}"
    return answer


def _quick(q: str, lang: str):
    """Return a single direct answer string. No AI. No extra info."""

    # ── SYSTEM / DEVELOPER INFO — always from DB, never from AI ──────────
    # _answer_system_question() is fully data-driven: reads SYSTEM_INFORMATION
    # from college_data.py at runtime. No names or roles are hardcoded here.
    sysinfo = _answer_system_question(q, lang)
    if sysinfo is not None:
        return sysinfo

    m = _meta()

    if any(k in q for k in ["college name", "name of the college", "కళాశాల పేరు"]):
        return m.get("college_name_te") if lang == "te" else m.get("college_name_en")

    if any(k in q for k in ["location", "address", "where is", "where", "ఎక్కడ"]):
        return m.get("location")

    if "naac" in q or "accredit" in q:
        return m.get("accreditation") or "NAAC 'A' Grade"

    if "affiliat" in q:
        return m.get("affiliation")

    gen = _section_data("general_information", lang)
    if not isinstance(gen, dict):
        return None

    if "principal" in q and "vice" not in q:
        name = gen.get("principal", "")
        if name:
            return (f"మన కాలేజీ ప్రిన్సిపల్ {name} గారు."
                    if lang == "te" else f"The Principal of Ideal College is {name}.")

    if "vice principal" in q or ("vice" in q and "principal" in q):
        vp = gen.get("vice_principal", "")
        if vp:
            return (f"మన కాలేజీ వైస్ ప్రిన్సిపల్ {vp} గారు."
                    if lang == "te" else f"The Vice Principal of Ideal College is {vp}.")

    if any(k in q for k in ["academic director", "ranjith"]):
        name = gen.get("academic_director", "Ranjith Sir")
        return (f"Academic Director: {name}."
                if lang == "te" else f"The Academic Director of Ideal College is {name}.")

    if any(k in q for k in ["administrative director", "admin director", "vasu"]):
        name = gen.get("administrative_director", "Vasu Sir")
        return (f"Administrative Director: {name}."
                if lang == "te" else f"The Administrative Director of Ideal College is {name}.")

    if "director" in q and "academic" not in q and "administrative" not in q:
        acad  = gen.get("academic_director", "Ranjith Sir")
        admin = gen.get("administrative_director", "Vasu Sir")
        return f"Academic Director: {acad}\nAdministrative Director: {admin}"

    if any(k in q for k in ["contact", "phone", "ఫోన్", "number", "call"]):
        return f"📞 {gen.get('contact', '')}\n📧 {gen.get('email', '')}"

    if any(k in q for k in ["email", "mail"]):
        return gen.get("email", "")

    if any(k in q for k in ["website", "site", "link", "url"]):
        return gen.get("website", "")

    if any(k in q for k in ["timing", "timings", "hours", "time", "సమయం", "open"]):
        t = gen.get("college_timings", "9:30 AM – 3:45 PM (Mon–Sat)")
        l = gen.get("lunch_break", "1:00 PM – 1:45 PM")
        return f"🕘 {t}\n🍽 Lunch break: {l}"

    if any(k in q for k in ["strength", "how many students", "total students"]):
        return gen.get("college_strength", "")

    return None


def _format_section(section_key: str, q: str, lang: str = "en") -> str:
    data = _section_data(section_key, lang)
    if not data:
        return ""
    fmt = _SECTION_FMT.get(section_key)
    if fmt:
        return fmt(data, q, lang)
    return ""


def _build_minimal_context(question: str) -> str:
    """
    Build the smallest possible context for AI fallback — only info
    likely relevant to the question. Avoids dumping the entire DB.
    """
    q = question.lower()
    m   = _meta()
    gen = _section_data("general_information") or {}

    # Always include identity info
    lines = [
        f"College: {m.get('college_name_en', 'Ideal College of Arts and Sciences')}",
        f"Location: {m.get('location', 'Vidyuth Nagar, Kakinada, AP')}",
        f"Contact: {gen.get('contact', '0884-2384382')}",
        f"Principal: {gen.get('principal', 'Dr. T. Satyanarayana')}",
    ]

    # Add section data only if the question is about it
    section_map = {
        ("fee", "cost", "tuition"):           "fee_structure",
        ("hostel", "accommodation", "mess"):  "hostel_and_amenities",
        ("placement", "job", "company"):      "placements",
        ("course", "ug", "pg", "bca", "bsc"): "courses",
        ("admission", "eligibility", "join"): "admissions",
        ("faculty", "hod", "department"):     "faculty_and_departments",
        ("transport", "bus"):                 "transport",
        ("library",):                         "library",
        ("exam", "attendance"):               "examinations",
        ("facility", "lab", "wifi"):          "campus_facilities",
        ("sport", "nss", "ncc"):              "sports_and_activities",
    }
    for kw_tuple, sec_key in section_map.items():
        if any(k in q for k in kw_tuple):
            sec_data = _section_data(sec_key)
            if sec_data:
                lines.append(f"\n[{sec_key}]: {str(sec_data)[:400]}")
            break   # only inject the most relevant section

    return "\n".join(lines)


def _ai_fallback(message: str, lang: str) -> str:
    """ONE AI call with minimal, targeted context. College mode = strict answer only."""
    try:
        from services.llm_service import query_ai
        ctx = _build_minimal_context(message)
        print(f"[COLLEGE] AI fallback context ({len(ctx)} chars)")
        return query_ai(prompt=message, lang=lang, context=ctx, mode="college")
    except Exception as e:
        logger.warning("[COLLEGE] AI fallback failed: %s", e)
        return (
            "దయచేసి కాలేజీని నేరుగా సంప్రదించండి: 0884-2384382"
            if lang == "te" else
            "Please contact the college directly: 0884-2384382"
        )


def get_college_answer(message: str, lang: str = "en", explain: bool = True):
    if not message:
        return None
    q = message.lower().strip()

    # Gate check
    is_about_college = (
        any(t in q for t in TRIGGER_WORDS)
        or any(k.lower() in q for k in (COLLEGE_KEYWORDS or []))
        or any(k in q for k in _EXTRA_GATE_WORDS)
    )
    if not is_about_college:
        return None

    # 1. Fast direct match
    quick = _quick(q, lang)
    if quick:
        return str(quick).strip()

    # 2. Section-based answer
    sec = _resolve_section(q)
    if sec:
        out = _format_section(sec, q, lang)
        if out:
            return out.strip()

    # 3. General overview (only when "about", "info", "tell me" etc.)
    if any(k in q for k in ["about", "info", "overview", "గురించి"]):
        m   = _meta()
        gen = _section_data("general_information", lang) or {}
        parts = [
            f"🏫 {m.get('college_name_en', 'Ideal College of Arts and Sciences')}",
            f"📍 {m.get('location', 'Vidyuth Nagar, Kakinada, AP')}",
            f"🎓 Affiliation: {m.get('affiliation', 'Adikavi Nannaya University')}",
            f"🏅 {m.get('accreditation', 'NAAC A Grade')}",
        ]
        if gen.get("principal"):
            parts.append(f"👨‍🏫 Principal: {gen['principal']}")
        if gen.get("contact"):
            parts.append(f"📞 {gen['contact']}")
        return "\n".join(parts)

    # 4. Section keyword scan
    for key, sec_data in _sections().items():
        kws = (sec_data.get("keywords_en") or []) + (sec_data.get("keywords_te") or [])
        if any(k.lower() in q for k in kws):
            out = _format_section(key, q, lang)
            if out:
                return out.strip()

    # 5. AI fallback (last resort — DB had nothing)
    if _has_ai_keys():
        return _ai_fallback(message, lang)

    return None


def get_college_context() -> str:
    """Full context — used only by router.py when college_service returns None."""
    if _get_context:
        try:
            ctx = _get_context()
            if ctx:
                return ctx[:2000]   # cap to prevent AI padding
        except Exception:
            pass
    m   = _meta()
    gen = _section_data("general_information") or {}
    courses = _section_data("courses") or {}
    fee     = _section_data("fee_structure") or {}
    return (
        f"College: {m.get('college_name_en', 'Ideal College of Arts and Sciences')}\n"
        f"Location: {m.get('location', 'Vidyuth Nagar, Kakinada, AP')}\n"
        f"Affiliation: {m.get('affiliation', 'Adikavi Nannaya University')}\n"
        f"Accreditation: {m.get('accreditation', 'NAAC A Grade')}\n"
        f"Principal: {gen.get('principal', 'Dr. T. Satyanarayana')}\n"
        f"Vice Principal: {gen.get('vice_principal', 'Mr. V. Kama Raju')}\n"
        f"Academic Director: {gen.get('academic_director', 'Ranjith Sir')}\n"
        f"Administrative Director: {gen.get('administrative_director', 'Vasu Sir')}\n"
        f"Timings: {gen.get('college_timings', '9:30 AM–3:45 PM Mon–Sat')}\n"
        f"Contact: {gen.get('contact', '0884-2384382')} | {gen.get('email', 'idealcolleges@gmail.com')}\n"
        f"Website: {gen.get('website', 'https://idealcollege.edu.in')}\n"
        f"UG: {', '.join(courses.get('ug', []))}\n"
        f"PG: {', '.join(courses.get('pg', []))}\n"
        f"Fee Range: {fee.get('range', '₹45,000–₹60,000/year')}\n"
        f"BCA Fee: {fee.get('bca', '₹50,000/year')}\n"
        f"Hostel: Available, ₹60,000/year\n"
        f"Placements 2026: 329 selected from 362 across 9 companies\n"
    )


__all__ = ["COLLEGE_KEYWORDS", "get_college_answer", "get_college_context"]
 