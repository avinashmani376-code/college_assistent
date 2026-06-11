# =====================================================
# data.py - COMPLETE COLLEGE DATA ARCHITECTURE
# =====================================================
# Exact Architecture as per your requirement
# Last Updated: April 2026
# =====================================================

COLLEGE_KEYWORDS = [
    "college", "admissions", "courses", "fees", "placements", "campus", "facilities",
    "hostel", "library", "principal", "location", "contact", "faculty", "hod", "staff",
    "rules", "exams", "scholarship", "bus", "wifi", "sports", "history", "agriculture",
    "fisheries", "bba", "computer science", "food technology", "fsn"
]

# =====================================================
# MAIN COLLEGE DATABASE
# =====================================================
COLLEGE_DATABASE = {
    "metadata": {
        "college_name_en": "Ideal College of Arts and Sciences",
        "college_name_te": "ఐడియల్ కాలేజ్ ఆఫ్ ఆర్ట్స్ అండ్ సైన్సెస్",
        "location": "Vidyuth Nagar, Kakinada, Andhra Pradesh",
        "affiliation": "Adikavi Nannaya University",
        "accreditation": "NAAC 'A' Grade",
        "languages_supported": ["en", "te"],
        "last_updated": "April 2026"
    },

    "sections": {

        "general_information": {
            "keywords_en": ["college name", "location", "principal", "timings", "contact", "strength"],
            "keywords_te": ["కాలేజీ పేరు", "స్థానం", "ప్రిన్సిపల్"],
            "data": {
                "en": {
                    "name": "Ideal College of Arts and Sciences",
                    "location": "Vidyuth Nagar, Kakinada, Andhra Pradesh",
                    "principal": "Dr. T. Satyanarayana",
                    "vice_principal": "Mr. V. Kama Raju",
                    "academic_director": "Ranjith Sir",
                    "administrative_director": "Vasu Sir",
                    "college_timings": "9:30 AM - 3:45 PM (Monday to Saturday)",
                    "lunch_break": "1:00 PM - 1:45 PM",
                    "contact": "0884-2384382 / 0884-2384381",
                    "email": "idealcolleges@gmail.com",
                    "website": "https://idealcollege.edu.in",
                    "college_strength": "1200 students (including Junior + Senior)"
                }
            }
        },

        "governance_and_administration": {
            "keywords_en": ["administration", "principal", "directors", "exam cell"],
            "keywords_te": ["నిర్వహణ"],
            "data": {
                "en": {
                    "academic_director": "Ranjith Sir",
                    "administrative_director": "Vasu Sir",
                    "exam_incharge": "Mr. K. Suresh Kumar"
                }
            }
        },

        "courses": {
            "keywords_en": ["courses", "ug", "pg"],
            "keywords_te": ["కోర్సులు"],
            "data": {
                "en": {
                    "ug": ["B.Sc Computers", "BCA", "B.Sc AI", "BBA", "Agriculture", "Food Technology", "Aqua & Fisheries"],
                    "pg": ["MCA", "M.Sc Organic Chemistry", "M.Sc Analytical Chemistry", "M.Sc Food Science & Technology", "M.Sc Aquaculture"],
                    "ug_duration": "3 Years",
                    "pg_duration": "2 Years"
                }
            }
        },

        "fee_structure": {
            "keywords_en": ["fees", "fee structure"],
            "keywords_te": ["ఫీజులు"],
            "data": {
                "en": {
                    "range": "₹45,000 - ₹60,000 per year",
                    "bsc_computers": "₹50,000/year",
                    "bca": "₹50,000/year",
                    "bsc_ai": "₹50,000/year",
                    "bba": "₹50,000/year",
                    "agriculture": "₹55,000/year",
                    "food_technology": "₹60,000/year",
                    "aqua_fisheries": "₹45,000/year"
                }
            }
        },

        "hostel_and_amenities": {
            "keywords_en": ["hostel", "hostel fee"],
            "keywords_te": ["హాస్టల్"],
            "data": {
                "en": {
                    "available": True,
                    "fee": "₹60,000 per year",
                    "features": ["Separate Boys & Girls Hostels", "Mess Facility (Breakfast, Lunch, Dinner)", "Warden Supervision"]
                }
            }
        },

        "transport": {
            "keywords_en": ["bus", "transport"],
            "keywords_te": ["బస్సు"],
            "data": {
                "en": "Bus facility available from various areas in and around Kakinada."
            }
        },

        "library": {
            "keywords_en": ["library"],
            "keywords_te": ["లైబ్రరీ"],
            "data": {
                "en": {
                    "librarian": "Mrs. K. Vara Lakshmi",
                    "timing": "9:30 AM - 3:45 PM",
                    "features": "Textbooks, Journals, E-resources"
                }
            }
        },

        "examinations": {
            "keywords_en": ["exams", "attendance"],
            "keywords_te": ["పరీక్షలు"],
            "data": {
                "en": {
                    "minimum_attendance": "75%",
                    "system": "Internal + University Semester exams"
                }
            }
        },

        "campus_facilities": {
            "keywords_en": ["labs", "wifi", "playground", "cafeteria", "cctv"],
            "keywords_te": ["సదుపాయాలు"],
            "data": {
                "en": ["Computer Labs", "Science Labs", "Wi-Fi", "Playground", "Cafeteria", "RO Water", "24/7 CCTV", "Parking"]
            }
        },

        "placements": {
            "keywords_en": ["placements", "selected", "companies", "drives", "2025", "2026"],
            "keywords_te": ["ప్లేస్‌మెంట్లు"],
            "data": {
                "en": {
                    "college_strength": "1200 students (including Junior + Senior)",
                    "statistics": {
                        "2025": {
                            "selected_students": 95
                        },
                        "2026": {
                            "seniors_drive": {
                                "visited_companies": 9,
                                "opportunity_companies": 9,
                                "students_participated": 362,
                                "students_selected": 329,
                                "branch_wise_participation": {
                                    "computer_science": 193,
                                    "bba": 85,
                                    "agriculture": 25
                                }
                            },
                            "passouts": 435
                        }
                    },
                    "companies_visited_physical": [
                        "Tech Mahindra",
                        "Sutherland",
                        "Concutix",
                        "Sagility",
                        "Teleperformance",
                        "Vidyant",
                        "Sand Space",
                        "First Source"
                    ],
                    "companies_online_exam": [
                        "TCS",
                        "Infosys",
                        "HCL",
                        "Cognizant",
                        "Intouch EX",
                        "L & T Mind Tree"
                    ],
                    "training": "CRT, Soft Skills, Aptitude, Spoken English, Mock Interviews",
                    "note": "Contact the Training & Placement Cell for latest detailed reports."
                }
            }
        },

        "faculty_and_departments": {
            "keywords_en": ["faculty", "hod", "staff", "teachers", "agriculture", "fisheries", "bba", "computer science"],
            "keywords_te": ["సిబ్బంది"],
            "data": {
                "en": {
                    "total_faculty": 54,
                    "departments": {
                        "agriculture": {
                            "name": "Department of Agriculture",
                            "hod": "K. Raju",
                            "faculty": [
                                {"name": "K. Raju", "designation": "HOD"},
                                {"name": "N. Mounica", "designation": "Assistant Professor"},
                                {"name": "A. Pavan Kumar", "designation": "Assistant Professor"},
                                {"name": "E. Anusha", "designation": "Assistant Professor"}
                            ]
                        },
                        "fisheries": {
                            "name": "Department of Fisheries",
                            "hod": "P. Lova Raju",
                            "faculty": [
                                {"name": "P. Lova Raju", "designation": "HOD"},
                                {"name": "D. Madhu", "designation": "Assistant Professor"},
                                {"name": "V. Ahalya", "designation": "Assistant Professor"},
                                {"name": "Md. Reshma", "designation": "Assistant Professor"},
                                {"name": "Ch. Neelima", "designation": "Assistant Professor"}
                            ]
                        },
                        "fsn_and_food_technology": {
                            "name": "Department of FSN & Food Technology",
                            "hods": {
                                "fsn": "S. Vinod Kumar",
                                "food_technology": "G. Deekshitha"
                            },
                            "faculty": [
                                {"name": "P. Prasanna", "designation": "Professor of Practice"},
                                {"name": "S. Vinod Kumar", "designation": "HOD - FSN"},
                                {"name": "G. Deekshitha", "designation": "HOD - Food Technology"},
                                {"name": "A. Lalitha", "designation": "Assistant Professor (FSN)"},
                                {"name": "K. Satya Srikshya", "designation": "Assistant Professor (FSN)"},
                                {"name": "G. Vasantha", "designation": "Assistant Professor (FT)"},
                                {"name": "Ch. Gnapika", "designation": "Assistant Professor (FT)"},
                                {"name": "P. Dasu Babu", "designation": "Assistant Professor (FT)"},
                                {"name": "K. D. Mahalakshmi Kalyani", "designation": "Assistant Professor (FT)"}
                            ]
                        },
                        "bba": {
                            "name": "Department of BBA",
                            "hod": "E. Srinilasa Rao",
                            "vice_principal": "V. Kama Raju",
                            "faculty": [
                                {"name": "V. Kama Raju", "designation": "Vice Principal"},
                                {"name": "E. Srinilasa Rao", "designation": "HOD"},
                                {"name": "M. Sasi Rekha", "designation": "Assistant Professor"},
                                {"name": "M. Pavana Kumari", "designation": "Assistant Professor"},
                                {"name": "V. Srinivas", "designation": "Assistant Professor"},
                                {"name": "K.V.S.L. Narashima Rao", "designation": "Assistant Professor"},
                                {"name": "S. Ramana", "designation": "Assistant Professor"},
                                {"name": "K. Mounika", "designation": "Assistant Professor"},
                                {"name": "N. Arjun Rao", "designation": "Assistant Professor"},
                                {"name": "P. Sirisha", "designation": "Assistant Professor"},
                                {"name": "G. Stephen", "designation": "Assistant Professor"}
                            ]
                        },
                        "computer_science": {
                            "name": "Department of Computer Science",
                            "hod": "M. Kameswara Rao",
                            "faculty": [
                                {"name": "M. Kameswara Rao", "designation": "Head of the Department"},
                                {"name": "V. Jeevan Kanth", "designation": "Assistant Professor"},
                                {"name": "T. Pridhvi Krishna", "designation": "Assistant Professor"},
                                {"name": "B. Venkata Ratnam", "designation": "Assistant Professor"},
                                {"name": "K. Macha Rao", "designation": "Assistant Professor"}
                            ]
                        }
                    },
                    "support_staff": {
                        "soft_skills": [
                            {"name": "Y. Harini", "designation": "Soft Skills Trainer"},
                            {"name": "P. Pooja", "designation": "Soft Skills Trainer"}
                        ],
                        "competitive_exams": [
                            {"name": "M. Leela Mohan Krishna", "designation": "Competitive Exam Trainer"},
                            {"name": "K. Rambabu", "designation": "Competitive Exam Trainer"},
                            {"name": "P. Kiran Kumar", "designation": "Competitive Exam Trainer"},
                            {"name": "K. Satish Kumar", "designation": "Competitive Exam Trainer"}
                        ],
                        "librarian": [
                            {"name": "K. Vara Lakshmi", "designation": "Librarian"}
                        ],
                        "telugu": [
                            {"name": "Dr. V.V. Satya Narayana", "designation": "Assistant Professor of Telugu"}
                        ]
                    }
                }
            }
        },

        "crt_and_soft_skills": {
            "keywords_en": ["crt", "soft skills", "spoken english"],
            "data": {
                "en": "Dedicated training in CRT, Soft Skills, Spoken English and Competitive Exams"
            }
        },

        "sports_and_activities": {
            "keywords_en": ["sports", "nss", "ncc", "cultural"],
            "data": {
                "en": ["Cricket", "Volleyball", "Badminton", "NSS", "NCC", "Cultural Events"]
            }
        },

        "student_rules": {
            "keywords_en": ["rules", "uniform", "ragging"],
            "data": {
                "en": {
                    "uniform": "College uniform and ID card are compulsory",
                    "ragging": "Strictly prohibited with zero tolerance",
                    "mobile": "Mobile phones restricted during class hours",
                    "attendance": "Minimum 75% attendance mandatory"
                }
            }
        },

        "health_and_safety": {
            "keywords_en": ["safety", "cctv", "medical"],
            "data": {
                "en": "24/7 CCTV surveillance, First Aid facility and Security"
            }
        },

        "admissions": {
            "keywords_en": ["admission", "eligibility", "documents"],
            "data": {
                "en": {
                    "ug_eligibility": "Passed Intermediate (10+2)",
                    "pg_eligibility": "Relevant Bachelor's Degree",
                    "documents_required": ["10th Memo", "12th Memo", "Transfer Certificate", "Aadhaar", "Photos"]
                }
            }
        },

        "historical_journey": {
            "keywords_en": ["history", "founders"],
            "data": {
                "en": {
                    "established": "Junior College (1970), Degree College (1974)",
                    "founders": ["Dr. Col. D. S. Raju", "Dr. P. V. N. Raju", "Dr. P. Chiranjeevini Kumari", "Dr. N. S. R. Sastry"]
                }
            }
        },

        "ai_responses": {
            "keywords_en": ["about college", "placements", "courses"],
            "data": {
                "en": {
                    "about_college": "Ideal College is a NAAC 'A' Grade institution with 1200 students and excellent placements.",
                    "placements": "In 2026, 329 students were selected from 362 participants.",
                    "courses": "UG & PG courses in Computers, BBA, Agriculture, Food Technology & Fisheries."
                }
            }
        }
    }
}


# ── COLLEGE CONTEXT (for AI/LLM fallback) ──────────────────────────────────
COLLEGE_CONTEXT = """
Ideal College of Arts and Sciences — NAAC 'A' Grade institution, established 2000.
Location: Vidyuth Nagar, Kakinada, Andhra Pradesh - 533003.
Affiliated to Adikavi Nannaya University.

UG Courses (3 yrs): B.Sc Computers, BCA, B.Sc AI, BBA, Agriculture, Food Technology, Aqua & Fisheries.
PG Courses (2 yrs): MCA, M.Sc Organic Chemistry, M.Sc Food Science, etc.

Contact: 0884-2384382 / 0884-2384381. Email: idealcolleges@gmail.com.
"""


# ── QUERY FUNCTION ──────────────────────────────────────────────────────────
def get_college_answer(query: str, lang: str = "en"):
    q = (query or "").lower().strip()
    sections = COLLEGE_DATABASE["sections"]
    best_section = None
    best_score = 0

    for section_name, section in sections.items():
        kw_key = f"keywords_{lang}" if lang == "te" else "keywords_en"
        keywords = section.get(kw_key, section.get("keywords_en", []))
        score = sum(1 for kw in keywords if kw.lower() in q)
        if score > best_score:
            best_score = score
            best_section = section

    if best_section and best_score > 0:
        data = best_section["data"]
        if isinstance(data, dict):
            return data.get(lang, data.get("en", ""))
        return str(data)
    return None


def get_college_context() -> str:
    return COLLEGE_CONTEXT