# services/college_service.py
"""
Reliable college-data retrieval.
- Triggers strongly on words "ideal" / "college" / "campus" / Telugu equivalents.
- Walks COLLEGE_DATABASE directly so answers always come from the local DB.
- Returns clean, readable text — never raw JSON.
"""

from data.college_data import COLLEGE_KEYWORDS, COLLEGE_DATABASE

try:
    from data.college_data import get_college_context as _get_context
except Exception:
    _get_context = None


TRIGGER_WORDS = [
    "ideal", "college", "campus", "kakinada college", "vidyuth nagar",
    "కళాశాల", "కాలేజీ", "ఐడియల్"
]


def _meta(): return COLLEGE_DATABASE.get("metadata", {}) or {}
def _sections(): return COLLEGE_DATABASE.get("sections", {}) or {}
def _section_data(key, lang="en"):
    sec = _sections().get(key, {}) or {}
    data = sec.get("data", {}) or {}
    return data.get(lang) or data.get("en") or data


def _stringify(value, indent=0) -> str:
    pad = "  " * indent
    if value is None: return ""
    if isinstance(value, str): return value
    if isinstance(value, (int, float, bool)): return str(value)
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
        if "principal" in q and gen.get("principal"):
            return f"Principal: {gen['principal']}"
        if ("vice" in q and "principal" in q) and gen.get("vice_principal"):
            return f"Vice Principal: {gen['vice_principal']}"
        if "contact" in q or "phone" in q or "ఫోన్" in q:
            return f"📞 {gen.get('contact','')}\n📧 {gen.get('email','')}"
        if "email" in q or "mail" in q: return gen.get("email")
        if "website" in q or "site" in q: return gen.get("website")
        if "timing" in q or "hours" in q or "సమయం" in q:
            return f"🕘 {gen.get('college_timings','')}\n🍽 Lunch: {gen.get('lunch_break','')}"
        if "strength" in q or "students" in q: return gen.get("college_strength")
    return None


SECTION_HINTS = [
    (["course", "ug", "pg", "stream", "branch", "కోర్సు"], "courses"),
    (["fee", "fees", "ఫీజు", "tuition"], "fee_structure"),
    (["hostel", "హాస్టల్", "accommodation"], "hostel_and_amenities"),
    (["bus", "transport", "బస్", "vehicle"], "transport"),
    (["library", "లైబ్రరీ", "books"], "library"),
    (["exam", "attendance", "పరీక్ష"], "examinations"),
    (["facility", "facilities", "lab", "wifi", "playground", "cafeteria", "cctv", "సదుపాయ"], "campus_facilities"),
    (["placement", "placements", "drives", "company", "companies", "selected", "ప్లేస్‌మెంట్"], "placements"),
    (["faculty", "hod", "department", "staff", "teacher", "professor", "సిబ్బంది"], "faculty_and_departments"),
    (["governance", "director", "admin"], "governance_and_administration"),
]


def _resolve_section(q: str):
    for keys, sec in SECTION_HINTS:
        if any(k in q for k in keys): return sec
    return None


def _format_section(section_key: str, q: str, lang: str = "en") -> str:
    data = _section_data(section_key, lang)
    if not data: return ""

    if section_key == "faculty_and_departments" and isinstance(data, dict):
        depts = data.get("departments", {}) or {}
        target = None
        dept_aliases = {
            "agriculture": ["agriculture", "agri"],
            "fisheries": ["fisheries", "aqua", "fish"],
            "fsn_and_food_technology": ["food", "fsn", "nutrition"],
            "bba": ["bba", "business"],
            "computer_science": ["computer", "cs", "bca", "mca", "ai", "computers"],
        }
        for k, aliases in dept_aliases.items():
            if any(a in q for a in aliases) and k in depts:
                target = k; break
        if target:
            d = depts[target]
            lines = [f"🏫 {d.get('name', target.replace('_',' ').title())}"]
            if d.get("hod"): lines.append(f"HOD: {d['hod']}")
            if d.get("hods"):
                for k, v in d["hods"].items():
                    lines.append(f"HOD ({k.upper()}): {v}")
            faculty = d.get("faculty") or []
            if faculty:
                lines.append("Faculty:")
                for f in faculty:
                    lines.append(f"  • {f.get('name','')} — {f.get('designation','')}")
            return "\n".join(lines)
        names = [d.get("name", k) for k, d in depts.items()]
        total = data.get("total_faculty")
        head = f"Departments ({len(names)}):" if names else "Departments:"
        body = "\n".join(f"  • {n}" for n in names)
        tail = f"\nTotal Faculty: {total}" if total else ""
        return f"{head}\n{body}{tail}"

    if section_key == "placements" and isinstance(data, dict):
        lines = ["🎓 Placements at Ideal College"]
        st = data.get("statistics", {}) or {}
        if "2026" in st:
            sd = st["2026"].get("seniors_drive", {}) or {}
            lines.append(f"2026 — Companies visited: {sd.get('visited_companies','-')}, "
                         f"Students participated: {sd.get('students_participated','-')}, "
                         f"Selected: {sd.get('students_selected','-')}.")
        if "2025" in st:
            lines.append(f"2025 — Selected: {st['2025'].get('selected_students','-')} students.")
        if data.get("companies_visited_physical"):
            lines.append("Top recruiters: " + ", ".join(data["companies_visited_physical"][:8]) + ".")
        if data.get("training"):
            lines.append(f"Training: {data['training']}.")
        return "\n".join(lines)

    return _stringify(data)


def get_college_answer(message: str, lang: str = "en"):
    if not message: return None
    q = message.lower().strip()
    is_about_college = (any(t in q for t in TRIGGER_WORDS)
                        or any(k.lower() in q for k in COLLEGE_KEYWORDS))
    if not is_about_college: return None

    quick = _quick(q, lang)
    if quick: return str(quick)

    sec = _resolve_section(q)
    if sec:
        out = _format_section(sec, q, lang)
        if out: return out

    if any(k in q for k in ["about", "info", "tell me", "details", "overview", "ఏమి", "గురించి"]):
        m = _meta()
        gen = _section_data("general_information", lang) or {}
        parts = [
            f"🏫 {m.get('college_name_en','Ideal College of Arts and Sciences')}",
            f"📍 {m.get('location','Vidyuth Nagar, Kakinada, Andhra Pradesh')}",
            f"🎓 Affiliation: {m.get('affiliation','Adikavi Nannaya University')}",
            f"🏅 Accreditation: {m.get('accreditation','NAAC A Grade')}",
        ]
        if gen.get("principal"): parts.append(f"👨‍🏫 Principal: {gen['principal']}")
        if gen.get("college_timings"): parts.append(f"🕘 Timings: {gen['college_timings']}")
        if gen.get("contact"): parts.append(f"📞 {gen['contact']}")
        if gen.get("website"): parts.append(f"🌐 {gen['website']}")
        return "\n".join(parts)

    for key, sec_data in _sections().items():
        kws = (sec_data.get("keywords_en") or []) + (sec_data.get("keywords_te") or [])
        if any(k.lower() in q for k in kws):
            out = _format_section(key, q, lang)
            if out: return out

    return None


def get_college_context() -> str:
    if _get_context:
        try:
            ctx = _get_context()
            if ctx: return ctx
        except Exception:
            pass
    m = _meta()
    gen = _section_data("general_information") or {}
    courses = _section_data("courses") or {}
    fee = _section_data("fee_structure") or {}
    return (
        f"College: {m.get('college_name_en','Ideal College of Arts and Sciences')}\n"
        f"Location: {m.get('location','Vidyuth Nagar, Kakinada, Andhra Pradesh')}\n"
        f"Affiliation: {m.get('affiliation','')}\n"
        f"Accreditation: {m.get('accreditation','')}\n"
        f"Principal: {gen.get('principal','')}\n"
        f"Timings: {gen.get('college_timings','')}\n"
        f"Contact: {gen.get('contact','')} | {gen.get('email','')}\n"
        f"Website: {gen.get('website','')}\n"
        f"UG Courses: {', '.join(courses.get('ug', []))}\n"
        f"PG Courses: {', '.join(courses.get('pg', []))}\n"
        f"Fees: {fee.get('range','')}\n"
    )


__all__ = ["COLLEGE_KEYWORDS", "get_college_answer", "get_college_context"]