import json
import sqlite3
import datetime
import os
from typing import Dict, Any

def log_event(data: Dict[str, Any]) -> bool:
    """
    Logs raw pipeline events (e.g. chat messages, non-scored interactions)
    to SQLite to maintain a complete history.
    """
    # Use the same logic as _resolve_db_path from src.database
    db_path = os.environ.get("WELLRING_DB_PATH", "wellring.db")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # We can re-use the interactions table or create a raw_events table.
        # For simplicity and alignment with Sai's request, we log it into interactions
        # with default/empty values for scoring-specific fields if they are missing.
        
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
        
        timestamp = data.get("timestamp", datetime.datetime.utcnow().isoformat() + "Z")
        intent = data.get("intent", "unknown")
        symptoms = json.dumps(data.get("symptoms", []))
        severity = data.get("severity", "none")
        confidence = float(data.get("confidence", 0.0))
        score = int(data.get("score", 0))
        risk_level = data.get("risk_level", "NONE")
        category = data.get("category", "NONE")
        action = data.get("action", "none")
        message = data.get("message", "")
        user_id = data.get("user_id")

        cursor.execute('''
            INSERT INTO interactions (
                timestamp, intent, symptoms, severity, confidence,
                score, risk_level, category, action, message, user_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            timestamp, intent, symptoms, severity, confidence,
            score, risk_level, category, action, message, user_id
        ))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error logging event: {e}")
        return False
