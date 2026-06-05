"""
users.py
========
User Profile system. Handles fetching patient and caregiver info
from either Supabase or the local SQLite database.
"""

import sqlite3
import os
import logging
from typing import Optional, Dict, Any
from src.database import get_supabase, _resolve_db_path, USE_SUPABASE

logger = logging.getLogger(__name__)

def get_user(user_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fetch user profile by UUID or string ID."""
    if USE_SUPABASE:
        supabase = get_supabase()
        if supabase:
            try:
                res = supabase.table("users").select("*").eq("id", user_id).execute()
                if res.data and len(res.data) > 0:
                    return res.data[0]
            except Exception as e:
                logger.error(f"Supabase get_user failed: {e}. Falling back to SQLite.")

    # SQLite Fallback
    db_path = _resolve_db_path(db_path)
    conn = sqlite3.connect(db_path)
    # Return rows as dicts
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)
    return None

def get_caregiver_phone(user_id: Optional[str], default_phone: str) -> str:
    """
    Get the caregiver's phone number for a given user.
    Falls back to `default_phone` if user or caregiver phone is missing.
    """
    if not user_id:
        return default_phone
        
    user = get_user(user_id)
    if user and user.get("caregiver_phone"):
        return user["caregiver_phone"]
        
    return default_phone
