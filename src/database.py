"""
database.py
===========
SQLite prototype database for logging interactions and alerts.
Will be migrated to PostgreSQL for production.
"""

import sqlite3
import json
import logging
import os
import datetime
from typing import Dict, Any, Optional

try:
    from supabase import create_client, Client
except ImportError:
    Client = Any

# Default path — overridden by WELLRING_DB_PATH env var (used by tests and Supabase migration).
DB_PATH = "wellring.db"
logger = logging.getLogger(__name__)

USE_SUPABASE = os.environ.get("USE_SUPABASE", "false").lower() == "true"
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

def get_supabase() -> Optional['Client']:
    if USE_SUPABASE and SUPABASE_URL and SUPABASE_KEY:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    return None


def _resolve_db_path(db_path: Optional[str]) -> str:
    """Return the active DB path: explicit arg → env var → default."""
    if db_path is not None:
        return db_path
    return os.environ.get("WELLRING_DB_PATH", DB_PATH)

def init_db(db_path: Optional[str] = None):
    """Initialize the SQLite database schema."""
    db_path = _resolve_db_path(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Interactions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            intent TEXT NOT NULL,
            symptoms TEXT NOT NULL,
            severity TEXT NOT NULL,
            confidence REAL NOT NULL,
            score INTEGER NOT NULL,
            risk_level TEXT NOT NULL,
            category TEXT NOT NULL,
            action TEXT NOT NULL,
            message TEXT NOT NULL,
            user_id TEXT
        )
    ''')
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            age INTEGER,
            medical_conditions TEXT,
            caregiver_name TEXT,
            caregiver_phone TEXT
        )
    ''')
    
    # We can add an alerts_log table here if we want to track notifications separately
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            interaction_id INTEGER,
            timestamp TEXT NOT NULL,
            risk_level TEXT NOT NULL,
            notification_type TEXT NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY(interaction_id) REFERENCES interactions(id)
        )
    ''')

    # Reminders table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            time TEXT NOT NULL,
            frequency TEXT NOT NULL,
            phone TEXT NOT NULL,
            notes TEXT,
            last_triggered TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info(f"Database initialized at {db_path}")

def log_interaction(data: Dict[str, Any], db_path: Optional[str] = None) -> int:
    """
    Log an assessment interaction to the database.
    Returns the inserted interaction ID.
    """
    if USE_SUPABASE:
        supabase = get_supabase()
        if supabase:
            try:
                res = supabase.table("interactions").insert({
                    "timestamp": data["timestamp"],
                    "intent": data.get("intent", ""),
                    "symptoms": data.get("symptoms", []),
                    "severity": data.get("severity", ""),
                    "confidence": data.get("confidence", 1.0),
                    "score": data["score"],
                    "risk_level": data["risk_level"],
                    "category": data["category"],
                    "action": data["action"],
                    "message": data["message"],
                    "user_id": data.get("user_id")
                }).execute()
                if res.data and len(res.data) > 0:
                    return res.data[0]["id"]
                return -1
            except Exception as e:
                logger.error(f"Supabase insert failed: {e}. Falling back to SQLite.")

    db_path = _resolve_db_path(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO interactions (
            timestamp, intent, symptoms, severity, confidence,
            score, risk_level, category, action, message, user_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data["timestamp"],
        data.get("intent", ""),
        json.dumps(data.get("symptoms", [])),
        data.get("severity", ""),
        data.get("confidence", 1.0),
        data["score"],
        data["risk_level"],
        data["category"],
        data["action"],
        data["message"],
        data.get("user_id")
    ))
    
    interaction_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return interaction_id

def get_symptom_repeat_count(symptom: str, days: int = 3, db_path: Optional[str] = None) -> int:
    """
    Returns how many times a symptom was logged in the last `days` days.

    Uses SQLite's json_each() to search inside the stored JSON symptom arrays.
    The scoring engine uses this count to apply the history escalation multiplier:
        history_multiplier = 1.0 + (repeat_count * 0.2), capped at 2.0

    Args:
        symptom: Symptom key to look up (e.g. "dizziness").
        days:    Look-back window in days. Default 3.
        db_path: Path to the SQLite database (resolved from env if None).

    Returns:
        Integer count of how many past interactions contained this symptom
        within the look-back window (0 = first occurrence).
    """
    if USE_SUPABASE:
        supabase = get_supabase()
        if supabase:
            try:
                # Calculate the cutoff timestamp
                cutoff_date = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).isoformat() + "Z"
                
                # PostgREST `cs` (contains) on JSONB array
                res = supabase.table("interactions") \
                    .select("id", count="exact") \
                    .gte("timestamp", cutoff_date) \
                    .contains("symptoms", [symptom]) \
                    .execute()
                
                return res.count if res.count is not None else 0
            except Exception as e:
                logger.error(f"Supabase select failed: {e}. Falling back to SQLite.")

    db_path = _resolve_db_path(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT COUNT(DISTINCT i.id)
        FROM   interactions i,
               json_each(i.symptoms) je
        WHERE  je.value = ?
          AND  i.timestamp >= datetime('now', ? || ' days')
        """,
        (symptom, f"-{days}"),
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count


def log_alert(interaction_id: int, timestamp: str, risk_level: str, notification_type: str, status: str, db_path: Optional[str] = None):
    """Log a sent alert (e.g., SMS, Email)."""
    if USE_SUPABASE:
        supabase = get_supabase()
        if supabase:
            try:
                supabase.table("alerts_log").insert({
                    "interaction_id": interaction_id,
                    "timestamp": timestamp,
                    "risk_level": risk_level,
                    "notification_type": notification_type,
                    "status": status
                }).execute()
                return
            except Exception as e:
                logger.error(f"Supabase alert log failed: {e}. Falling back to SQLite.")

    db_path = _resolve_db_path(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO alerts_log (
            interaction_id, timestamp, risk_level, notification_type, status
        ) VALUES (?, ?, ?, ?, ?)
    ''', (
        interaction_id, timestamp, risk_level, notification_type, status
    ))
    
    conn.commit()
    conn.close()


def add_reminder(type_val: str, title: str, time_val: str, frequency: str, phone: str, notes: Optional[str] = None, db_path: Optional[str] = None) -> int:
    """Add a new scheduled reminder."""
    db_path = _resolve_db_path(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO reminders (type, title, time, frequency, phone, notes, last_triggered)
        VALUES (?, ?, ?, ?, ?, ?, NULL)
    ''', (type_val, title, time_val, frequency, phone, notes))
    
    reminder_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return reminder_id


def get_reminders(db_path: Optional[str] = None) -> list:
    """Retrieve all reminders as dictionaries."""
    db_path = _resolve_db_path(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM reminders')
    rows = cursor.fetchall()
    
    reminders = []
    for r in rows:
        reminders.append({
            "id": r["id"],
            "type": r["type"],
            "title": r["title"],
            "time": r["time"],
            "frequency": r["frequency"],
            "phone": r["phone"],
            "notes": r["notes"],
            "last_triggered": r["last_triggered"]
        })
        
    conn.close()
    return reminders


def delete_reminder(reminder_id: int, db_path: Optional[str] = None) -> bool:
    """Delete a reminder by ID."""
    db_path = _resolve_db_path(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM reminders WHERE id = ?', (reminder_id,))
    rows_deleted = cursor.rowcount
    
    conn.commit()
    conn.close()
    return rows_deleted > 0


def update_reminder_trigger(reminder_id: int, timestamp: str, db_path: Optional[str] = None) -> bool:
    """Update last_triggered timestamp for a reminder."""
    db_path = _resolve_db_path(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('UPDATE reminders SET last_triggered = ? WHERE id = ?', (timestamp, reminder_id))
    rows_updated = cursor.rowcount
    
    conn.commit()
    conn.close()
    return rows_updated > 0

