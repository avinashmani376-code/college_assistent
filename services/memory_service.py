"""
services/memory_service.py

SQLite-based memory for conversation history, user preferences,
and student admission enquiries.
Only used when helpful — never required for every response.
"""

import os
import sqlite3
import logging
from typing import Optional, List, Dict
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = os.path.join("/tmp", "ideal_college_memory.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    try:
        conn = _get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role       TEXT NOT NULL,
                message    TEXT NOT NULL,
                intent     TEXT,
                lang       TEXT DEFAULT 'en',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS preferences (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                pref_key   TEXT NOT NULL,
                pref_value TEXT NOT NULL,
                updated_at TEXT DEFAULT (datetime('now')),
                UNIQUE(session_id, pref_key)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS admissions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                phone      TEXT NOT NULL,
                email      TEXT,
                course     TEXT NOT NULL,
                message    TEXT,
                status     TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning("memory_service init_db failed: %s", e)


def save_memory(
    user_message: str,
    ai_reply: str,
    intent: str = "general",
    lang: str = "en",
    session_id: str = "default"
) -> None:
    try:
        conn = _get_conn()
        conn.execute(
            "INSERT INTO conversations (session_id, role, message, intent, lang) VALUES (?, ?, ?, ?, ?)",
            (session_id, "user", user_message, intent, lang)
        )
        conn.execute(
            "INSERT INTO conversations (session_id, role, message, intent, lang) VALUES (?, ?, ?, ?, ?)",
            (session_id, "assistant", ai_reply, intent, lang)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning("save_memory failed: %s", e)


def get_memory(session_id: str = "default", limit: int = 10) -> List[Dict]:
    try:
        conn = _get_conn()
        rows = conn.execute(
            """SELECT role, message, intent, lang, created_at
               FROM conversations
               WHERE session_id = ?
               ORDER BY id DESC LIMIT ?""",
            (session_id, limit)
        ).fetchall()
        conn.close()
        return [dict(r) for r in reversed(rows)]
    except Exception as e:
        logger.warning("get_memory failed: %s", e)
        return []


def get_recent_context(session_id: str = "default", limit: int = 4) -> str:
    """Return recent Q&A pairs as a compact string for AI context injection."""
    try:
        rows = get_memory(session_id=session_id, limit=limit * 2)
        if not rows:
            return ""
        lines = []
        for r in rows[-limit * 2:]:
            prefix = "User" if r["role"] == "user" else "Assistant"
            lines.append(f"{prefix}: {r['message'][:200]}")
        return "\n".join(lines)
    except Exception as e:
        logger.warning("get_recent_context failed: %s", e)
        return ""


def save_preference(key: str, value: str, session_id: str = "default") -> None:
    try:
        conn = _get_conn()
        conn.execute(
            """INSERT INTO preferences (session_id, pref_key, pref_value, updated_at)
               VALUES (?, ?, ?, datetime('now'))
               ON CONFLICT(session_id, pref_key) DO UPDATE SET
                 pref_value = excluded.pref_value,
                 updated_at = excluded.updated_at""",
            (session_id, key, value)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning("save_preference failed: %s", e)


def get_preference(key: str, session_id: str = "default") -> Optional[str]:
    try:
        conn = _get_conn()
        row = conn.execute(
            "SELECT pref_value FROM preferences WHERE session_id = ? AND pref_key = ?",
            (session_id, key)
        ).fetchone()
        conn.close()
        return row["pref_value"] if row else None
    except Exception as e:
        logger.warning("get_preference failed: %s", e)
        return None


def save_admission(
    name: str,
    phone: str,
    course: str,
    email: str = "",
    message: str = ""
) -> int:
    """Save a student admission enquiry. Returns the new record id."""
    try:
        conn = _get_conn()
        cur = conn.execute(
            """INSERT INTO admissions (name, phone, email, course, message)
               VALUES (?, ?, ?, ?, ?)""",
            (name.strip(), phone.strip(), email.strip(), course.strip(), message.strip())
        )
        conn.commit()
        row_id = cur.lastrowid
        conn.close()
        return row_id
    except Exception as e:
        logger.warning("save_admission failed: %s", e)
        return -1


def get_admissions(limit: int = 50) -> List[Dict]:
    """Fetch latest admission enquiries (for admin use)."""
    try:
        conn = _get_conn()
        rows = conn.execute(
            """SELECT id, name, phone, email, course, message, status, created_at
               FROM admissions ORDER BY id DESC LIMIT ?""",
            (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning("get_admissions failed: %s", e)
        return []


init_db()
