"""
database.py
===========
SQLite prototype database for logging interactions and alerts.
Will be migrated to PostgreSQL for production.
"""

import sqlite3
import json
import logging
from typing import Dict, Any

DB_PATH = "wellring.db"
logger = logging.getLogger(__name__)

def init_db(db_path: str = DB_PATH):
    """Initialize the SQLite database schema."""
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

def log_interaction(data: Dict[str, Any], db_path: str = DB_PATH) -> int:
    """
    Log an assessment interaction to the database.
    Returns the inserted interaction ID.
    """
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

def log_alert(interaction_id: int, timestamp: str, risk_level: str, notification_type: str, status: str, db_path: str = DB_PATH):
    """Log a sent alert (e.g., SMS, Email)."""
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
