"""
database.py
===========
Unified data-access layer for WellRing.

Backend priority (controlled by env vars):
  1. PostgreSQL  — if DATABASE_URL is set
  2. Supabase    — if USE_SUPABASE=true and SUPABASE_URL + SUPABASE_KEY are set
  3. SQLite      — local fallback (tests, offline dev)

Public API (signatures unchanged so existing code/tests keep working):
  init_db()
  log_interaction(data)           → int (row id)
  get_symptom_repeat_count(symptom, days) → int
  log_alert(...)
  add_reminder(...)
  get_reminders()
  delete_reminder(id)
  update_reminder_trigger(id, ts)

New Postgres-first functions:
  get_pg_conn()                   → psycopg2 connection (context manager)
  log_assessment_pg(data, user_id) → UUID str
  upsert_health_history(user_id, symptom, assessment_id, severity, risk_level)
  log_conversation_turn(user_id, role, content, vapi_call_id, channel)
"""

import datetime
import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional, Union

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Backend selection flags
# ---------------------------------------------------------------------------
DATABASE_URL: str = os.environ.get("DATABASE_URL", "")
USE_POSTGRES: bool = bool(DATABASE_URL)

USE_SUPABASE: bool = os.environ.get("USE_SUPABASE", "false").lower() == "true"
SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY: str = os.environ.get("SUPABASE_KEY", "")

# SQLite fallback path
DB_PATH: str = os.environ.get("WELLRING_DB_PATH", "wellring.db")

# ---------------------------------------------------------------------------
# Optional imports (Postgres / Supabase)
# ---------------------------------------------------------------------------
try:
    import psycopg2
    import psycopg2.extras  # for RealDictCursor, UUID support
    psycopg2.extras.register_uuid()
    _PG_AVAILABLE = True
except ImportError:
    _PG_AVAILABLE = False

try:
    from supabase import create_client, Client as SupabaseClient
    _SUPABASE_AVAILABLE = True
except ImportError:
    SupabaseClient = Any  # type: ignore[misc,assignment]
    _SUPABASE_AVAILABLE = False


# ===========================================================================
# PostgreSQL helpers
# ===========================================================================

@contextmanager
def get_pg_conn() -> Generator:
    """
    Context manager that yields a psycopg2 connection.
    Commits on clean exit, rolls back and re-raises on exception.
    """
    if not (_PG_AVAILABLE and DATABASE_URL):
        raise RuntimeError("PostgreSQL is not configured (DATABASE_URL missing or psycopg2 not installed).")
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _pg_cursor(conn):
    """Return a RealDictCursor so rows come back as dicts."""
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


# ===========================================================================
# Supabase helper
# ===========================================================================

def get_supabase() -> Optional['SupabaseClient']:
    if USE_SUPABASE and _SUPABASE_AVAILABLE and SUPABASE_URL and SUPABASE_KEY:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    return None


# ===========================================================================
# SQLite helpers (fallback)
# ===========================================================================

def _resolve_db_path(db_path: Optional[str]) -> str:
    if db_path is not None:
        return db_path
    return os.environ.get("WELLRING_DB_PATH", DB_PATH)


def init_db(db_path: Optional[str] = None) -> None:
    """
    Initialize the SQLite schema (used when Postgres is NOT configured).
    For Postgres: run `python -m src.db.migrate` instead.
    """
    if USE_POSTGRES:
        logger.info("PostgreSQL backend active — skipping SQLite init_db().")
        return

    db_path = _resolve_db_path(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS interactions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       TEXT    NOT NULL,
            intent          TEXT    NOT NULL,
            symptoms        TEXT    NOT NULL,
            severity        TEXT    NOT NULL,
            confidence      REAL    NOT NULL,
            score           INTEGER NOT NULL,
            risk_level      TEXT    NOT NULL,
            category        TEXT    NOT NULL,
            action          TEXT    NOT NULL,
            message         TEXT    NOT NULL,
            user_id         TEXT,
            recording_url   TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id                  TEXT PRIMARY KEY,
            name                TEXT NOT NULL,
            age                 INTEGER,
            medical_conditions  TEXT,
            caregiver_name      TEXT,
            caregiver_phone     TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS alerts_log (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            interaction_id      INTEGER,
            timestamp           TEXT    NOT NULL,
            risk_level          TEXT    NOT NULL,
            notification_type   TEXT    NOT NULL,
            status              TEXT    NOT NULL,
            FOREIGN KEY(interaction_id) REFERENCES interactions(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            type            TEXT NOT NULL,
            title           TEXT NOT NULL,
            time            TEXT NOT NULL,
            frequency       TEXT NOT NULL,
            phone           TEXT NOT NULL,
            notes           TEXT,
            last_triggered  TEXT
        )
    """)

    conn.commit()
    conn.close()
    logger.info(f"SQLite database initialized at {db_path}")


# ===========================================================================
# log_interaction  (backward-compatible entry point)
# ===========================================================================

def log_interaction(data: Dict[str, Any], db_path: Optional[str] = None) -> Union[int, str]:
    """
    Log an assessment result.

    Returns:
        UUID string (Postgres) or integer row id (SQLite/Supabase).
    """
    # -- Postgres --
    if USE_POSTGRES and _PG_AVAILABLE:
        return _log_interaction_pg(data)

    # -- Supabase --
    if USE_SUPABASE and _SUPABASE_AVAILABLE:
        result = _log_interaction_supabase(data)
        if result is not None:
            return result

    # -- SQLite fallback --
    return _log_interaction_sqlite(data, db_path)


def _log_interaction_pg(data: Dict[str, Any]) -> str:
    """Insert into Postgres `assessments` table, returns UUID string."""
    user_id = data.get("user_id")  # may be None if anonymous

    # If no user_id supplied, use (or create) the anonymous sentinel user
    if not user_id:
        user_id = _ensure_anonymous_user_pg()

    sql = """
        INSERT INTO assessments (
            user_id, intent, symptoms, severity, confidence,
            score, base_score, risk_level, category, action,
            message, steps, breakdown, vapi_call_id, recording_url
        ) VALUES (
            %(user_id)s, %(intent)s, %(symptoms)s, %(severity)s, %(confidence)s,
            %(score)s, %(base_score)s, %(risk_level)s, %(category)s, %(action)s,
            %(message)s, %(steps)s, %(breakdown)s, %(vapi_call_id)s, %(recording_url)s
        )
        RETURNING assessment_id
    """
    params = {
        "user_id":       user_id,
        "intent":        data.get("intent", "health_issue"),
        "symptoms":      data.get("symptoms", []),
        "severity":      (data.get("severity") or "low").lower(),
        "confidence":    data.get("confidence", 1.0),
        "score":         data.get("score", 0),
        "base_score":    data.get("base_score", 0),
        "risk_level":    data.get("risk_level", "LOW"),
        "category":      data.get("category", "UNKNOWN"),
        "action":        data.get("action", "monitor"),
        "message":       data.get("message", ""),
        "steps":         data.get("steps", []),
        "breakdown":     data.get("breakdown", []),
        "vapi_call_id":  data.get("vapi_call_id"),
        "recording_url": data.get("recording_url"),
    }

    with get_pg_conn() as conn:
        with _pg_cursor(conn) as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            assessment_id = str(row["assessment_id"])

    logger.info(f"[PG] Assessment logged: {assessment_id}")
    return assessment_id


def _ensure_anonymous_user_pg() -> str:
    """
    Return the UUID of the 'anonymous' sentinel user, creating it if needed.
    """
    sql_select = "SELECT user_id FROM users WHERE email = 'anonymous@wellring.internal' LIMIT 1"
    sql_insert = """
        INSERT INTO users (name, role, email)
        VALUES ('Anonymous', 'elderly', 'anonymous@wellring.internal')
        ON CONFLICT DO NOTHING
        RETURNING user_id
    """
    with get_pg_conn() as conn:
        with _pg_cursor(conn) as cur:
            cur.execute(sql_select)
            row = cur.fetchone()
            if row:
                return str(row["user_id"])
            cur.execute(sql_insert)
            row = cur.fetchone()
            return str(row["user_id"]) if row else ""


def _log_interaction_supabase(data: Dict[str, Any]) -> Optional[int]:
    supabase = get_supabase()
    if not supabase:
        return None
    try:
        res = supabase.table("interactions").insert({
            "timestamp":     data.get("timestamp", datetime.datetime.utcnow().isoformat() + "Z"),
            "intent":        data.get("intent", ""),
            "symptoms":      data.get("symptoms", []),
            "severity":      data.get("severity", ""),
            "confidence":    data.get("confidence", 1.0),
            "score":         data.get("score", 0),
            "risk_level":    data.get("risk_level", "LOW"),
            "category":      data.get("category", ""),
            "action":        data.get("action", ""),
            "message":       data.get("message", ""),
            "user_id":       data.get("user_id"),
            "recording_url": data.get("recording_url"),
        }).execute()
        if res.data:
            return res.data[0]["id"]
    except Exception as exc:
        logger.error(f"Supabase insert failed: {exc}. Falling back to SQLite.")
    return None


def _log_interaction_sqlite(data: Dict[str, Any], db_path: Optional[str]) -> int:
    db_path = _resolve_db_path(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO interactions (
            timestamp, intent, symptoms, severity, confidence,
            score, risk_level, category, action, message, user_id, recording_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("timestamp", datetime.datetime.utcnow().isoformat() + "Z"),
        data.get("intent", ""),
        json.dumps(data.get("symptoms", [])),
        data.get("severity", ""),
        data.get("confidence", 1.0),
        data.get("score", 0),
        data.get("risk_level", "LOW"),
        data.get("category", ""),
        data.get("action", ""),
        data.get("message", ""),
        data.get("user_id"),
        data.get("recording_url"),
    ))
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


# ===========================================================================
# get_symptom_repeat_count
# ===========================================================================

def get_symptom_repeat_count(symptom: str, days: int = 3, db_path: Optional[str] = None, user_id: Optional[str] = None) -> int:
    """
    Returns how many times a symptom was logged in the last `days` days.
    Used by the scoring engine to compute the history escalation multiplier.
    """
    if USE_POSTGRES and _PG_AVAILABLE:
        return _symptom_count_pg(symptom, days, user_id)

    if USE_SUPABASE and _SUPABASE_AVAILABLE:
        result = _symptom_count_supabase(symptom, days)
        if result >= 0:
            return result

    return _symptom_count_sqlite(symptom, days, db_path)


def _symptom_count_pg(symptom: str, days: int, user_id: Optional[str]) -> int:
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days)
    sql = """
        SELECT COUNT(*) AS cnt
        FROM   assessments
        WHERE  %(symptom)s = ANY(symptoms)
          AND  assessed_at >= %(cutoff)s
    """
    params: Dict[str, Any] = {"symptom": symptom, "cutoff": cutoff}
    if user_id:
        sql += " AND user_id = %(user_id)s"
        params["user_id"] = user_id

    with get_pg_conn() as conn:
        with _pg_cursor(conn) as cur:
            cur.execute(sql, params)
            return int(cur.fetchone()["cnt"])


def _symptom_count_supabase(symptom: str, days: int) -> int:
    supabase = get_supabase()
    if not supabase:
        return -1
    try:
        cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).isoformat() + "Z"
        res = (
            supabase.table("interactions")
            .select("id", count="exact")
            .gte("timestamp", cutoff)
            .contains("symptoms", [symptom])
            .execute()
        )
        return res.count if res.count is not None else 0
    except Exception as exc:
        logger.error(f"Supabase symptom count failed: {exc}")
        return -1


def _symptom_count_sqlite(symptom: str, days: int, db_path: Optional[str]) -> int:
    db_path = _resolve_db_path(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(DISTINCT i.id)
        FROM   interactions i, json_each(i.symptoms) je
        WHERE  je.value = ?
          AND  i.timestamp >= datetime('now', ? || ' days')
        """,
        (symptom, f"-{days}"),
    )
    count = cur.fetchone()[0]
    conn.close()
    return count


# ===========================================================================
# log_alert
# ===========================================================================

def log_alert(
    interaction_id: Union[int, str],
    timestamp: str,
    risk_level: str,
    notification_type: str,
    status: str,
    db_path: Optional[str] = None,
    recipient_name: Optional[str] = None,
    recipient_phone: Optional[str] = None,
    recipient_email: Optional[str] = None,
) -> None:
    """Log a sent alert / notification."""

    if USE_POSTGRES and _PG_AVAILABLE:
        _log_alert_pg(interaction_id, risk_level, notification_type, status,
                      recipient_name, recipient_phone, recipient_email)
        return

    if USE_SUPABASE and _SUPABASE_AVAILABLE:
        supabase = get_supabase()
        if supabase:
            try:
                supabase.table("alerts_log").insert({
                    "interaction_id":   interaction_id,
                    "timestamp":        timestamp,
                    "risk_level":       risk_level,
                    "notification_type": notification_type,
                    "status":           status,
                }).execute()
                return
            except Exception as exc:
                logger.error(f"Supabase alert log failed: {exc}")

    # SQLite fallback
    db_path = _resolve_db_path(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        INSERT INTO alerts_log (interaction_id, timestamp, risk_level, notification_type, status)
        VALUES (?, ?, ?, ?, ?)
    """, (interaction_id, timestamp, risk_level, notification_type, status))
    conn.commit()
    conn.close()


def _log_alert_pg(
    assessment_id: Union[int, str],
    risk_level: str,
    alert_type: str,
    status: str,
    recipient_name: Optional[str],
    recipient_phone: Optional[str],
    recipient_email: Optional[str],
) -> None:
    sql = """
        INSERT INTO alerts (
            assessment_id, alert_type, status,
            recipient_name, recipient_phone, recipient_email
        ) VALUES (
            %(assessment_id)s, %(alert_type)s, %(status)s,
            %(recipient_name)s, %(recipient_phone)s, %(recipient_email)s
        )
    """
    with get_pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {
                "assessment_id":  str(assessment_id),
                "alert_type":     alert_type,
                "status":         status,
                "recipient_name":  recipient_name,
                "recipient_phone": recipient_phone,
                "recipient_email": recipient_email,
            })


# ===========================================================================
# upsert_health_history  (new, Postgres-first)
# ===========================================================================

def upsert_health_history(
    user_id: str,
    symptom: str,
    assessment_id: Optional[str] = None,
    severity: Optional[str] = None,
    risk_level: Optional[str] = None,
    window_days: int = 3,
) -> None:
    """
    Insert or update the rolling health_history record for (user, symptom).
    Called automatically after every Postgres assessment write.
    """
    if not (USE_POSTGRES and _PG_AVAILABLE):
        return  # No-op for SQLite/Supabase

    now = datetime.datetime.utcnow()
    window_start = now - datetime.timedelta(days=window_days)

    sql = """
        INSERT INTO health_history (
            user_id, symptom, window_start, window_end,
            occurrence_count, peak_severity, peak_risk_level, last_assessment_id
        )
        VALUES (
            %(user_id)s, %(symptom)s, %(window_start)s, %(now)s,
            1, %(severity)s, %(risk_level)s, %(assessment_id)s
        )
        ON CONFLICT DO NOTHING
    """
    # We use a simple "always insert" strategy; the scoring engine counts rows.
    with get_pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {
                "user_id":       user_id,
                "symptom":       symptom,
                "window_start":  window_start,
                "now":           now,
                "severity":      (severity or "low").lower(),
                "risk_level":    (risk_level or "LOW").upper(),
                "assessment_id": assessment_id,
            })


# ===========================================================================
# log_conversation_turn  (new, Postgres-first)
# ===========================================================================

def log_conversation_turn(
    user_id: str,
    role: str,
    content: str,
    vapi_call_id: Optional[str] = None,
    channel: str = "web",
    assessment_id: Optional[str] = None,
    audio_url: Optional[str] = None,
) -> Optional[str]:
    """
    Persist a single conversation message to the `conversations` table.
    Returns the UUID of the inserted row (Postgres only).
    """
    if not (USE_POSTGRES and _PG_AVAILABLE):
        return None

    sql = """
        INSERT INTO conversations (
            user_id, assessment_id, vapi_call_id,
            channel, role, content, audio_url
        ) VALUES (
            %(user_id)s, %(assessment_id)s, %(vapi_call_id)s,
            %(channel)s, %(role)s, %(content)s, %(audio_url)s
        )
        RETURNING conversation_id
    """
    with get_pg_conn() as conn:
        with _pg_cursor(conn) as cur:
            cur.execute(sql, {
                "user_id":       user_id,
                "assessment_id": assessment_id,
                "vapi_call_id":  vapi_call_id,
                "channel":       channel,
                "role":          role,
                "content":       content,
                "audio_url":     audio_url,
            })
            return str(cur.fetchone()["conversation_id"])


# ===========================================================================
# Reminders  (SQLite-only for now; Supabase/Postgres can be added later)
# ===========================================================================

def add_reminder(
    type_val: str, title: str, time_val: str,
    frequency: str, phone: str,
    notes: Optional[str] = None, db_path: Optional[str] = None,
) -> int:
    db_path = _resolve_db_path(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO reminders (type, title, time, frequency, phone, notes, last_triggered)
        VALUES (?, ?, ?, ?, ?, ?, NULL)
    """, (type_val, title, time_val, frequency, phone, notes))
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def get_reminders(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    db_path = _resolve_db_path(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM reminders")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def delete_reminder(reminder_id: int, db_path: Optional[str] = None) -> bool:
    db_path = _resolve_db_path(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def update_reminder_trigger(reminder_id: int, timestamp: str, db_path: Optional[str] = None) -> bool:
    db_path = _resolve_db_path(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE reminders SET last_triggered = ? WHERE id = ?", (timestamp, reminder_id))
    updated = cur.rowcount > 0
    conn.commit()
    conn.close()
    return updated
