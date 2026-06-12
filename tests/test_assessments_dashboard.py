"""
test_assessments_dashboard.py
=============================
Tests for:
1. /assessments list endpoint (filtering, limit, formatting)
2. /assessments/stats counts endpoint
3. Postgres retrieval code path mocks
4. users.get_user SQLite and Postgres paths
"""

import pytest
import datetime
import json
from unittest.mock import patch, MagicMock
from src.database import log_interaction
from src.users import get_user

def test_sqlite_dashboard_endpoints(client):
    # Log a few dummy interactions to the SQLite DB
    log_interaction({
        "risk_level": "LOW",
        "symptoms": ["medicine_missed"],
        "confidence": 1.0,
        "severity": "low",
        "score": 10,
        "action": "monitor",
        "message": "Keep monitoring",
        "steps": ["Step 1"],
        "breakdown": ["Base score = 10"],
        "user_id": "test_dashboard_user"
    })
    
    log_interaction({
        "risk_level": "HIGH",
        "symptoms": ["fall_detected"],
        "confidence": 0.95,
        "severity": "high",
        "score": 75,
        "action": "notify_caregiver",
        "message": "Alert caregiver",
        "steps": ["Step 1", "Step 2"],
        "breakdown": ["Base score = 75"],
        "user_id": "test_dashboard_user"
    })

    # 1. Test /assessments with limit
    r = client.get("/assessments?limit=1")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["risk_level"] == "HIGH"
    assert data[0]["symptoms"] == ["fall_detected"]

    # 2. Test /assessments with risk filter
    r = client.get("/assessments?risk_level=LOW")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    assert all(item["risk_level"] == "LOW" for item in data)

    # 3. Test /assessments/stats
    r = client.get("/assessments/stats")
    assert r.status_code == 200
    stats = r.json()
    assert "total_today" in stats
    assert stats["low"] >= 1
    assert stats["high"] >= 1
    assert isinstance(stats["critical"], int)


def test_postgres_dashboard_endpoints(client):
    # Setup mock data that would be returned by Postgres cursor
    mock_assessments = [
        {
            "id": "assessment-uuid-1",
            "assessment_id": "assessment-uuid-1",
            "timestamp": datetime.datetime.now(datetime.UTC),
            "assessed_at": datetime.datetime.now(datetime.UTC),
            "intent": "health_issue",
            "symptoms": ["fall_detected"],
            "severity": "high",
            "confidence": 0.95,
            "score": 75,
            "risk_level": "HIGH",
            "category": "FALL",
            "action": "notify_caregiver",
            "message": "Alert caregiver",
            "user_id": "test_dashboard_user"
        }
    ]
    
    # stats row mockup from cursor fetchone (RealDictRow behaves like dict)
    mock_stats = {
        "total_today": 1,
        "low": 0,
        "medium": 0,
        "high": 1,
        "critical": 0
    }

    # Mock the database cursor and connection
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = mock_assessments
    mock_cursor.fetchone.return_value = mock_stats
    
    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    
    # We will patch get_pg_conn, _pg_cursor, _use_postgres, _PG_AVAILABLE
    with patch("src.database._use_postgres", return_value=True), \
         patch("src.database._PG_AVAILABLE", return_value=True), \
         patch("src.database.get_pg_conn", return_value=mock_conn), \
         patch("src.database._pg_cursor") as mock_cursor_ctx:
        
        mock_cursor_ctx.return_value.__enter__.return_value = mock_cursor
        
        # Test /assessments endpoint
        r = client.get("/assessments?limit=5")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["id"] == "assessment-uuid-1"
        assert data[0]["risk_level"] == "HIGH"
        assert data[0]["symptoms"] == ["fall_detected"]

        # Reset cursor mock for stats call
        mock_cursor_ctx.return_value.__enter__.return_value = mock_cursor

        # Test /assessments/stats endpoint
        r = client.get("/assessments/stats")
        assert r.status_code == 200
        stats = r.json()
        assert stats["total_today"] == 1
        assert stats["high"] == 1


def test_users_get_user_paths():
    # 1. Test SQLite fallback path
    # Make sure we don't hit Postgres or Supabase
    with patch("src.users._use_postgres", return_value=False), \
         patch("src.users.USE_SUPABASE", False):
        user = get_user("nonexistent_user")
        assert user is None

    # 2. Test Postgres path
    mock_user_row = {
        "user_id": "postgres-user-uuid",
        "email": "pg@wellring.com",
        "name": "PG User"
    }
    
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = mock_user_row
    
    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    
    with patch("src.users._use_postgres", return_value=True), \
         patch("src.users._PG_AVAILABLE", return_value=True), \
         patch("src.users.get_pg_conn", return_value=mock_conn), \
         patch("src.users._pg_cursor") as mock_cursor_ctx:
        
        mock_cursor_ctx.return_value.__enter__.return_value = mock_cursor
        
        user = get_user("postgres-user-uuid")
        assert user is not None
        assert user["id"] == "postgres-user-uuid"
        assert user["email"] == "pg@wellring.com"
        assert user["name"] == "PG User"
