"""
test_health.py
==============
Tests for the health-check and reference endpoints.

Covers:
    GET /        → 200 {"status": "ok", "version": "1.0.0"}
    GET /health  → 200 {"status": "ok"}
    GET /symptoms     → 200, list of symptom dicts
    GET /risk-levels  → 200, exactly 4 risk level entries
"""


def test_root_returns_ok(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"] == "1.0.0"


def test_health_endpoint_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_symptoms_reference_returns_list(client):
    r = client.get("/symptoms")
    assert r.status_code == 200
    data = r.json()
    assert "symptoms" in data
    assert len(data["symptoms"]) > 0
    # Each entry should have key, weight, category
    first = data["symptoms"][0]
    assert "key" in first
    assert "weight" in first
    assert "category" in first


def test_risk_levels_reference_returns_four_levels(client):
    r = client.get("/risk-levels")
    assert r.status_code == 200
    data = r.json()
    assert "levels" in data
    levels = [entry["level"] for entry in data["levels"]]
    assert set(levels) == {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
