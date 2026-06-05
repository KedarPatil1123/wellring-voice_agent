"""
test_pipeline.py
================
Unit tests for the WellRing pipeline layer:
    - validator.py
    - router.py
    - logger.py
    - main.py  (FastAPI endpoint via TestClient)

Run with:
    python -m pytest tests/test_pipeline.py -v
"""

import sys
import os

# Add src/ to path so imports resolve without installation
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import json
import pytest
from fastapi.testclient import TestClient

from pipeline.validator import validate, VALID_INTENTS, VALID_SEVERITIES
from pipeline.router import route
from pipeline.logger import log_request, _LOG_FILE
from main import app

client = TestClient(app)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def health_payload():
    return {
        "intent": "health_issue",
        "symptoms": ["chest_pain", "dizziness"],
        "severity": "high",
        "confidence": 0.92,
    }

@pytest.fixture
def chat_payload():
    return {
        "intent": "general_chat",
        "symptoms": [],
        "severity": "low",
        "confidence": 0.85,
    }

@pytest.fixture
def bad_payload():
    return {
        "intent": "UNKNOWN_INTENT",
        "symptoms": None,
        "severity": "ultra",
        "confidence": 1.5,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# validator.py tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidator:

    def test_valid_health_payload_passes(self, health_payload):
        result = validate(health_payload)
        assert result.is_valid is True
        assert result.errors == []

    def test_valid_chat_payload_passes(self, chat_payload):
        result = validate(chat_payload)
        assert result.is_valid is True

    def test_empty_symptoms_list_is_valid(self):
        result = validate({
            "intent": "general_chat",
            "symptoms": [],
            "severity": "low",
            "confidence": 0.5,
        })
        assert result.is_valid is True

    def test_invalid_intent_fails(self):
        r = validate({"intent": "bad", "symptoms": [], "severity": "low", "confidence": 0.5})
        assert not r.is_valid
        assert any("intent" in e.lower() for e in r.errors)

    def test_invalid_severity_fails(self):
        r = validate({"intent": "general_chat", "symptoms": [], "severity": "ultra", "confidence": 0.5})
        assert not r.is_valid
        assert any("severity" in e.lower() for e in r.errors)

    def test_missing_symptoms_fails(self):
        r = validate({"intent": "health_issue", "severity": "high", "confidence": 0.9})
        assert not r.is_valid
        assert any("symptoms" in e.lower() for e in r.errors)

    def test_symptoms_not_list_fails(self):
        r = validate({"intent": "health_issue", "symptoms": "chest_pain", "severity": "high", "confidence": 0.9})
        assert not r.is_valid
        assert any("list" in e.lower() for e in r.errors)

    def test_confidence_below_zero_fails(self):
        r = validate({"intent": "health_issue", "symptoms": [], "severity": "low", "confidence": -0.1})
        assert not r.is_valid
        assert any("confidence" in e.lower() for e in r.errors)

    def test_confidence_above_one_fails(self):
        r = validate({"intent": "health_issue", "symptoms": [], "severity": "low", "confidence": 1.5})
        assert not r.is_valid

    def test_confidence_boundary_zero_passes(self):
        r = validate({"intent": "general_chat", "symptoms": [], "severity": "low", "confidence": 0.0})
        assert r.is_valid

    def test_confidence_boundary_one_passes(self):
        r = validate({"intent": "general_chat", "symptoms": [], "severity": "low", "confidence": 1.0})
        assert r.is_valid

    def test_multiple_errors_collected(self, bad_payload):
        r = validate(bad_payload)
        assert not r.is_valid
        assert len(r.errors) >= 3  # intent + severity + symptoms + confidence

    def test_normalised_payload_lowercase(self):
        r = validate({
            "intent": "HEALTH_ISSUE",
            "symptoms": ["CHEST_PAIN"],
            "severity": "HIGH",
            "confidence": 0.9,
        })
        assert r.is_valid
        assert r.payload["intent"] == "health_issue"
        assert r.payload["severity"] == "high"
        assert r.payload["symptoms"] == ["chest_pain"]

    def test_bool_converts_correctly(self, health_payload):
        r = validate(health_payload)
        assert bool(r) is True

    def test_all_valid_intents_accepted(self):
        for intent in VALID_INTENTS:
            r = validate({"intent": intent, "symptoms": [], "severity": "low", "confidence": 0.5})
            assert r.is_valid, f"Intent '{intent}' should be valid"

    def test_all_valid_severities_accepted(self):
        for sev in VALID_SEVERITIES:
            r = validate({"intent": "general_chat", "symptoms": [], "severity": sev, "confidence": 0.5})
            assert r.is_valid, f"Severity '{sev}' should be valid"

    def test_transcript_forwarded_to_payload(self):
        """transcript is optional but must pass through to the normalised payload."""
        r = validate({
            "intent": "general_chat",
            "symptoms": [],
            "severity": "low",
            "confidence": 0.8,
            "transcript": "Good morning!",
        })
        assert r.is_valid
        assert r.payload.get("transcript") == "Good morning!"

    def test_missing_transcript_does_not_fail_validation(self):
        """Omitting transcript must not add a validation error."""
        r = validate({
            "intent": "general_chat",
            "symptoms": [],
            "severity": "low",
            "confidence": 0.8,
        })
        assert r.is_valid
        assert "transcript" not in r.payload


# ═══════════════════════════════════════════════════════════════════════════════
# router.py tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestRouter:

    def test_health_issue_routes_to_scoring_engine(self, health_payload):
        v = validate(health_payload)
        rr = route(v.payload)
        assert rr.destination == "health_issue"
        assert rr.success is True
        assert "risk_level" in rr.data
        assert "score" in rr.data

    def test_general_chat_routes_to_chat_handler(self, chat_payload):
        v = validate(chat_payload)
        rr = route(v.payload)
        assert rr.destination == "general_chat"
        assert rr.success is True
        assert rr.data["response_type"] == "conversational"

    def test_unknown_intent_returns_failure(self):
        rr = route({"intent": "mystery"})
        assert rr.success is False
        assert "mystery" in rr.error

    def test_route_result_bool_true_on_success(self, health_payload):
        v = validate(health_payload)
        rr = route(v.payload)
        assert bool(rr) is True

    def test_route_result_bool_false_on_failure(self):
        rr = route({"intent": "bad"})
        assert bool(rr) is False

    def test_health_routing_returns_action(self, health_payload):
        v = validate(health_payload)
        rr = route(v.payload)
        assert "action" in rr.data

    def test_health_routing_risk_level_is_string(self, health_payload):
        v = validate(health_payload)
        rr = route(v.payload)
        assert isinstance(rr.data["risk_level"], str)
        assert rr.data["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    def test_critical_symptom_scores_critical(self):
        payload = {
            "intent": "health_issue",
            "symptoms": ["chest_pain", "unconscious", "stroke_symptoms"],
            "severity": "critical",
            "confidence": 1.0,
        }
        v = validate(payload)
        rr = route(v.payload)
        assert rr.data["risk_level"] == "CRITICAL"

    def test_low_severity_empty_symptoms_scores_low(self):
        payload = {
            "intent": "health_issue",
            "symptoms": [],
            "severity": "low",
            "confidence": 1.0,
        }
        v = validate(payload)
        rr = route(v.payload)
        assert rr.data["risk_level"] == "LOW"


# ═══════════════════════════════════════════════════════════════════════════════
# logger.py tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestLogger:

    def test_log_request_returns_string_uuid(self, health_payload):
        v = validate(health_payload)
        rr = route(v.payload)
        rid = log_request(health_payload, rr, v)
        assert isinstance(rid, str)
        assert len(rid) == 36  # UUID4 format

    def test_log_file_created(self, health_payload):
        v = validate(health_payload)
        rr = route(v.payload)
        log_request(health_payload, rr, v)
        assert os.path.exists(_LOG_FILE)

    def test_log_entry_is_valid_json(self, health_payload):
        v = validate(health_payload)
        rr = route(v.payload)
        rid = log_request(health_payload, rr, v)
        with open(_LOG_FILE, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
        # Find our entry
        entry = next(
            (json.loads(l) for l in lines if json.loads(l).get("request_id") == rid),
            None,
        )
        assert entry is not None

    def test_log_entry_contains_expected_fields(self, health_payload):
        v = validate(health_payload)
        rr = route(v.payload)
        rid = log_request(health_payload, rr, v)
        with open(_LOG_FILE, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
        entry = next(json.loads(l) for l in lines if json.loads(l).get("request_id") == rid)
        for field in ("timestamp", "request_id", "intent", "severity",
                      "confidence", "symptoms", "route_ok", "risk_level"):
            assert field in entry, f"Missing field: {field}"

    def test_log_works_without_route_result(self, health_payload):
        v = validate(health_payload)
        rid = log_request(health_payload, None, v)
        assert isinstance(rid, str)

    def test_unique_request_ids(self, health_payload):
        v = validate(health_payload)
        rr = route(v.payload)
        ids = {log_request(health_payload, rr, v) for _ in range(5)}
        assert len(ids) == 5  # all unique


# ═══════════════════════════════════════════════════════════════════════════════
# FastAPI endpoint tests (main.py)
# ═══════════════════════════════════════════════════════════════════════════════

class TestFastAPIEndpoints:

    def test_health_check_returns_ok(self):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_assess_health_issue_returns_200(self, health_payload):
        r = client.post("/assess", json=health_payload)
        assert r.status_code == 200
        body = r.json()
        assert "request_id" in body
        assert body["intent"] == "health_issue"
        assert body["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    def test_assess_general_chat_returns_200(self, chat_payload):
        r = client.post("/assess", json=chat_payload)
        assert r.status_code == 200
        body = r.json()
        assert body["destination"] == "general_chat"

    def test_assess_invalid_payload_returns_422(self):
        r = client.post("/assess", json={
            "intent": "not_valid",
            "symptoms": [],
            "severity": "low",
            "confidence": 0.9,
        })
        assert r.status_code == 422

    def test_assess_missing_required_field_returns_422(self):
        # Missing 'severity' — Pydantic catches this before pipeline
        r = client.post("/assess", json={
            "intent": "health_issue",
            "symptoms": ["chest_pain"],
            "confidence": 0.9,
        })
        assert r.status_code == 422

    def test_assess_response_has_request_id(self, health_payload):
        r = client.post("/assess", json=health_payload)
        assert "request_id" in r.json()

    def test_assess_critical_payload(self):
        r = client.post("/assess", json={
            "intent": "health_issue",
            "symptoms": ["chest_pain", "unconscious", "stroke_symptoms"],
            "severity": "critical",
            "confidence": 1.0,
        })
        assert r.status_code == 200
        assert r.json()["risk_level"] == "CRITICAL"

    def test_assess_confidence_out_of_range_returns_422(self):
        r = client.post("/assess", json={
            "intent": "health_issue",
            "symptoms": [],
            "severity": "low",
            "confidence": 2.0,
        })
        assert r.status_code == 422

    def test_docs_endpoint_accessible(self):
        r = client.get("/docs")
        assert r.status_code == 200
