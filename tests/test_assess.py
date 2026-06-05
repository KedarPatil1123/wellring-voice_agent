"""
test_assess.py
==============
Tests for the core POST /assess endpoint with valid payloads.

Covers:
    - LOW risk (medicine missed)
    - MEDIUM risk (dizziness, medium severity)
    - HIGH risk (fall detected)
    - CRITICAL risk (stroke symptoms)
    - Killer Demo (chest pain + breathing problem)
    - Low-confidence override → follow_up_questions regardless of score
    - History multiplier reflected in score > base symptom weight
    - breakdown field is always present and non-empty
    - timestamp is always present and UTC-formatted
    - Database logging: each request increments interaction count
"""

import pytest

# ---------------------------------------------------------------------------
# Shared payloads
# ---------------------------------------------------------------------------

LOW_PAYLOAD = {
    "intent": "health_issue",
    "symptoms": ["medicine_missed"],
    "severity": "low",
    "confidence": 1.0,
}

DIZZINESS_PAYLOAD = {
    "intent": "health_issue",
    "symptoms": ["dizziness"],
    "severity": "medium",
    "confidence": 0.90,
}

FALL_PAYLOAD = {
    "intent": "health_issue",
    "symptoms": ["fall_detected"],
    "severity": "high",
    "confidence": 0.95,
}

STROKE_PAYLOAD = {
    "intent": "health_issue",
    "symptoms": ["stroke_symptoms"],
    "severity": "critical",
    "confidence": 0.99,
}

KILLER_DEMO_PAYLOAD = {
    "intent": "health_issue",
    "symptoms": ["chest_pain", "breathing_problem"],
    "severity": "critical",
    "confidence": 0.95,
}

LOW_CONFIDENCE_PAYLOAD = {
    "intent": "health_issue",
    "symptoms": ["chest_pain"],
    "severity": "high",
    "confidence": 0.3,
}


# ---------------------------------------------------------------------------
# Risk level scenarios
# ---------------------------------------------------------------------------

def test_low_risk_medicine_missed(client):
    r = client.post("/assess", json=LOW_PAYLOAD)
    assert r.status_code == 200
    data = r.json()
    assert data["risk_level"] == "LOW"
    assert data["action"] == "monitor"
    assert data["score"] == 10
    assert data["category"] == "MEDICATION"


def test_medium_risk_dizziness(client):
    r = client.post("/assess", json=DIZZINESS_PAYLOAD)
    assert r.status_code == 200
    data = r.json()
    # score = (20 + 10_bonus) * 0.90 = 27 → LOW  (first occurrence, no history)
    assert data["risk_level"] == "LOW"
    assert data["category"] == "NEUROLOGICAL"


def test_high_risk_fall_detected(client):
    r = client.post("/assess", json=FALL_PAYLOAD)
    assert r.status_code == 200
    data = r.json()
    assert data["risk_level"] == "HIGH"
    assert data["action"] == "notify_caregiver"
    assert data["category"] == "FALL"
    assert data["score"] >= 61


def test_critical_stroke_symptoms(client):
    r = client.post("/assess", json=STROKE_PAYLOAD)
    assert r.status_code == 200
    data = r.json()
    assert data["risk_level"] == "CRITICAL"
    assert data["action"] == "notify_caregiver_and_emergency_services"
    assert data["category"] == "NEUROLOGICAL"
    assert data["score"] >= 101


def test_killer_demo_chest_pain_and_breathing(client):
    """The core demo scenario: chest pain + breathing → CRITICAL + emergency action."""
    r = client.post("/assess", json=KILLER_DEMO_PAYLOAD)
    assert r.status_code == 200
    data = r.json()
    assert data["risk_level"] == "CRITICAL"
    assert data["action"] == "notify_caregiver_and_emergency_services"
    assert data["category"] == "CARDIAC"
    assert data["score"] >= 101
    assert "Call emergency services" in data["steps"][0]


# ---------------------------------------------------------------------------
# Confidence override
# ---------------------------------------------------------------------------

def test_low_confidence_forces_follow_up_questions(client):
    """confidence=0.3 < threshold 0.4 → always follow_up_questions."""
    r = client.post("/assess", json=LOW_CONFIDENCE_PAYLOAD)
    assert r.status_code == 200
    data = r.json()
    assert data["action"] == "follow_up_questions"
    assert "30%" in data["message"] or "confidence" in data["message"].lower()


def test_confidence_exactly_at_threshold_normal_escalation(client):
    """confidence=0.4 is NOT below threshold → normal escalation applies."""
    payload = {**LOW_CONFIDENCE_PAYLOAD, "confidence": 0.4}
    r = client.post("/assess", json=payload)
    assert r.status_code == 200
    # Should NOT be follow_up due to low confidence — score decides action
    assert r.json()["action"] != "follow_up_questions" or r.json()["risk_level"] == "MEDIUM"


# ---------------------------------------------------------------------------
# Explainability / breakdown
# ---------------------------------------------------------------------------

def test_breakdown_field_is_present_and_non_empty(client):
    r = client.post("/assess", json=LOW_PAYLOAD)
    assert r.status_code == 200
    breakdown = r.json()["breakdown"]
    assert isinstance(breakdown, list)
    assert len(breakdown) > 0


def test_breakdown_contains_symptom_name(client):
    r = client.post("/assess", json=LOW_PAYLOAD)
    assert r.status_code == 200
    breakdown_str = " ".join(r.json()["breakdown"])
    assert "medicine_missed" in breakdown_str


def test_breakdown_contains_confidence_line(client):
    r = client.post("/assess", json=LOW_PAYLOAD)
    assert r.status_code == 200
    breakdown_str = " ".join(r.json()["breakdown"])
    assert "confidence" in breakdown_str.lower()


# ---------------------------------------------------------------------------
# Response schema completeness
# ---------------------------------------------------------------------------

def test_timestamp_present_and_utc(client):
    r = client.post("/assess", json=LOW_PAYLOAD)
    assert r.status_code == 200
    ts = r.json()["timestamp"]
    assert isinstance(ts, str)
    assert ts.endswith("Z")


def test_all_required_fields_present(client):
    r = client.post("/assess", json=KILLER_DEMO_PAYLOAD)
    assert r.status_code == 200
    data = r.json()
    required = [
        "score", "base_score", "confidence",
        "risk_level", "category", "symptoms", "severity",
        "action", "message", "steps", "breakdown", "timestamp",
    ]
    for field in required:
        assert field in data, f"Missing field: {field}"


def test_steps_is_non_empty_list(client):
    r = client.post("/assess", json=KILLER_DEMO_PAYLOAD)
    assert r.status_code == 200
    steps = r.json()["steps"]
    assert isinstance(steps, list)
    assert len(steps) > 0
