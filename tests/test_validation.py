"""
test_validation.py
==================
Tests for input validation on POST /assess.

Covers:
    - Invalid severity string → 422
    - Severity case sensitivity (FastAPI should normalise) → 200
    - Confidence out of range (> 1.0, < 0.0) → 422
    - Missing required field (intent, severity) → 422
    - Completely empty body → 422
    - Empty symptoms list (valid — score comes from severity bonus only)
    - Unknown symptom keys (silently ignored, not a crash)
    - Symptoms with mixed valid + unknown keys (unknown filtered out)
"""


# ---------------------------------------------------------------------------
# Severity validation
# ---------------------------------------------------------------------------

def test_invalid_severity_string_returns_422(client):
    r = client.post("/assess", json={
        "intent": "health_issue",
        "symptoms": ["dizziness"],
        "severity": "extreme",
        "confidence": 0.9,
    })
    assert r.status_code == 422


def test_severity_uppercase_is_normalised(client):
    """FastAPI validator normalises severity to lowercase — should be 200."""
    r = client.post("/assess", json={
        "intent": "health_issue",
        "symptoms": ["dizziness"],
        "severity": "LOW",
        "confidence": 0.9,
    })
    assert r.status_code == 200
    assert r.json()["severity"] == "low"


def test_severity_mixed_case_is_normalised(client):
    r = client.post("/assess", json={
        "intent": "health_issue",
        "symptoms": ["dizziness"],
        "severity": "Critical",
        "confidence": 0.9,
    })
    assert r.status_code == 200
    assert r.json()["severity"] == "critical"


# ---------------------------------------------------------------------------
# Confidence validation
# ---------------------------------------------------------------------------

def test_confidence_above_1_returns_422(client):
    r = client.post("/assess", json={
        "intent": "health_issue",
        "symptoms": ["dizziness"],
        "severity": "low",
        "confidence": 1.5,
    })
    assert r.status_code == 422


def test_confidence_below_0_returns_422(client):
    r = client.post("/assess", json={
        "intent": "health_issue",
        "symptoms": ["dizziness"],
        "severity": "low",
        "confidence": -0.1,
    })
    assert r.status_code == 422


def test_confidence_exactly_0_is_valid(client):
    r = client.post("/assess", json={
        "intent": "health_issue",
        "symptoms": ["dizziness"],
        "severity": "low",
        "confidence": 0.0,
    })
    assert r.status_code == 200
    assert r.json()["score"] == 0


def test_confidence_exactly_1_is_valid(client):
    r = client.post("/assess", json={
        "intent": "health_issue",
        "symptoms": ["medicine_missed"],
        "severity": "low",
        "confidence": 1.0,
    })
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Missing required fields
# ---------------------------------------------------------------------------

def test_missing_intent_returns_422(client):
    r = client.post("/assess", json={
        "symptoms": ["dizziness"],
        "severity": "low",
        "confidence": 0.9,
    })
    assert r.status_code == 422


def test_missing_severity_returns_422(client):
    r = client.post("/assess", json={
        "intent": "health_issue",
        "symptoms": ["dizziness"],
        "confidence": 0.9,
    })
    assert r.status_code == 422


def test_empty_body_returns_422(client):
    r = client.post("/assess", json={})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Symptom edge cases
# ---------------------------------------------------------------------------

def test_empty_symptoms_list_is_valid(client):
    """
    Empty symptoms is allowed — score is purely from severity bonus.
    severity=critical bonus = 40, confidence=1.0 → score=40.
    """
    r = client.post("/assess", json={
        "intent": "health_issue",
        "symptoms": [],
        "severity": "critical",
        "confidence": 1.0,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["score"] == 40
    assert data["symptoms"] == []


def test_unknown_symptoms_are_silently_ignored(client):
    """Unknown symptom keys should not raise an error."""
    r = client.post("/assess", json={
        "intent": "health_issue",
        "symptoms": ["purple_moon", "dancing_stars"],
        "severity": "low",
        "confidence": 1.0,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["symptoms"] == []  # all filtered out
    assert data["score"] == 0      # low bonus = 0, no valid symptoms


def test_mixed_valid_and_unknown_symptoms(client):
    """Valid symptoms are scored; unknown ones are silently dropped."""
    r = client.post("/assess", json={
        "intent": "health_issue",
        "symptoms": ["dizziness", "made_up_symptom"],
        "severity": "low",
        "confidence": 1.0,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["symptoms"] == ["dizziness"]
    # Score >= 20 (dizziness base weight), history may make it higher
    assert data["score"] >= 20
