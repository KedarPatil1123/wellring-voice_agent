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
from typing import Dict, Any, Optional

# Default path — overridden by WELLRING_DB_PATH env var (used by tests and Supabase migration).
DB_PATH = "wellring.db"
logger = logging.getLogger(__name__)


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
            message TEXT NOT NULL
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
    
    conn.commit()
    conn.close()
    logger.info(f"Database initialized at {db_path}")

def log_interaction(data: Dict[str, Any], db_path: Optional[str] = None) -> int:
    """
    Log an assessment interaction to the database.
    Returns the inserted interaction ID.
    """
    db_path = _resolve_db_path(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO interactions (
            timestamp, intent, symptoms, severity, confidence,
            score, risk_level, category, action, message
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        data["message"]
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
