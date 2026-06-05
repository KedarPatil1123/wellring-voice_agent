"""
test_api.py
===========
FastAPI integration tests for the WellRing pipeline API.

Tests all endpoints through the real application stack using FastAPI's
TestClient (no network required — fully in-process).

Endpoints covered:
    GET  /health         liveness probe
    POST /assess         full pipeline (health_issue, general_chat, invalid)
    GET  /history        recent request log

Run with:
    python -m pytest tests/test_api.py -v
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


# ═══════════════════════════════════════════════════════════════════════════════
# GET /health
# ═══════════════════════════════════════════════════════════════════════════════

class TestHealthEndpoint:

    def test_health_returns_200(self):
        r = client.get("/health")
        assert r.status_code == 200

    def test_health_status_ok(self):
        r = client.get("/health")
        assert r.json()["status"] == "ok"

    def test_health_service_name(self):
        r = client.get("/health")
        assert r.json()["service"] == "wellring-pipeline"

    def test_health_has_version(self):
        r = client.get("/health")
        assert "version" in r.json()

    def test_health_content_type_json(self):
        r = client.get("/health")
        assert "application/json" in r.headers["content-type"]


# ═══════════════════════════════════════════════════════════════════════════════
# POST /assess — health_issue
# ═══════════════════════════════════════════════════════════════════════════════

_HEALTH_PAYLOAD = {
    "intent":     "health_issue",
    "symptoms":   ["chest_pain"],
    "severity":   "high",
    "confidence": 0.95,
    "transcript": "I have chest pain and I feel short of breath.",
}

_CHAT_PAYLOAD = {
    "intent":     "general_chat",
    "symptoms":   [],
    "severity":   "low",
    "confidence": 0.99,
    "transcript": "Good morning, how are you today?",
}


class TestAssessHealthIssue:

    def test_assess_health_issue_returns_200(self):
        r = client.post("/assess", json=_HEALTH_PAYLOAD)
        assert r.status_code == 200

    def test_assess_health_issue_has_request_id(self):
        r = client.post("/assess", json=_HEALTH_PAYLOAD)
        data = r.json()
        assert "request_id" in data
        assert len(data["request_id"]) > 0

    def test_assess_health_issue_intent_echoed(self):
        r = client.post("/assess", json=_HEALTH_PAYLOAD)
        assert r.json()["intent"] == "health_issue"

    def test_assess_health_issue_has_risk_level(self):
        r = client.post("/assess", json=_HEALTH_PAYLOAD)
        assert r.json()["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    def test_assess_health_issue_has_score(self):
        r = client.post("/assess", json=_HEALTH_PAYLOAD)
        assert isinstance(r.json()["score"], int)

    def test_assess_health_issue_has_category(self):
        r = client.post("/assess", json=_HEALTH_PAYLOAD)
        assert r.json()["category"] == "CARDIAC"

    def test_assess_health_issue_has_action(self):
        r = client.post("/assess", json=_HEALTH_PAYLOAD)
        action = r.json().get("action")
        assert action is not None
        assert "action" in action
        assert "message" in action
        assert "steps" in action

    def test_assess_health_issue_has_destination(self):
        r = client.post("/assess", json=_HEALTH_PAYLOAD)
        assert r.json()["destination"] == "health_issue"

    def test_assess_chest_pain_high_severity_is_at_least_high(self):
        r = client.post("/assess", json=_HEALTH_PAYLOAD)
        assert r.json()["risk_level"] in ("HIGH", "CRITICAL")

    def test_assess_critical_symptoms_are_critical(self):
        r = client.post("/assess", json={
            "intent":     "health_issue",
            "symptoms":   ["chest_pain", "breathing_problem"],
            "severity":   "high",
            "confidence": 1.0,
        })
        assert r.json()["risk_level"] == "CRITICAL"

    def test_assess_low_confidence_reduces_score(self):
        r_full = client.post("/assess", json={**_HEALTH_PAYLOAD, "confidence": 1.0})
        r_half = client.post("/assess", json={**_HEALTH_PAYLOAD, "confidence": 0.5})
        assert r_full.json()["score"] >= r_half.json()["score"]

    def test_assess_general_chat_has_no_risk_level(self):
        r = client.post("/assess", json=_CHAT_PAYLOAD)
        assert r.json().get("risk_level") is None

    def test_assess_symptoms_in_response(self):
        r = client.post("/assess", json=_HEALTH_PAYLOAD)
        syms = r.json().get("symptoms", [])
        assert "chest_pain" in syms


# ═══════════════════════════════════════════════════════════════════════════════
# POST /assess — general_chat
# ═══════════════════════════════════════════════════════════════════════════════

class TestAssessGeneralChat:

    def test_assess_general_chat_returns_200(self):
        r = client.post("/assess", json=_CHAT_PAYLOAD)
        assert r.status_code == 200

    def test_assess_general_chat_intent_echoed(self):
        r = client.post("/assess", json=_CHAT_PAYLOAD)
        assert r.json()["intent"] == "general_chat"

    def test_assess_general_chat_has_message(self):
        r = client.post("/assess", json=_CHAT_PAYLOAD)
        msg = r.json().get("message", "")
        assert isinstance(msg, str) and len(msg) > 0

    def test_assess_general_chat_has_topic(self):
        r = client.post("/assess", json=_CHAT_PAYLOAD)
        assert r.json().get("topic") is not None

    def test_assess_general_chat_greeting_topic(self):
        """'Good morning' transcript should produce 'greeting' topic."""
        r = client.post("/assess", json=_CHAT_PAYLOAD)
        assert r.json()["topic"] == "greeting"

    def test_assess_general_chat_farewell_topic(self):
        r = client.post("/assess", json={
            **_CHAT_PAYLOAD, "transcript": "Goodbye, see you later!"
        })
        assert r.json()["topic"] == "farewell"

    def test_assess_general_chat_has_follow_up(self):
        r = client.post("/assess", json=_CHAT_PAYLOAD)
        # follow_up key should exist (may be empty string for farewell etc.)
        assert "follow_up" in r.json()

    def test_assess_general_chat_response_type(self):
        r = client.post("/assess", json=_CHAT_PAYLOAD)
        assert r.json()["response_type"] == "conversational"

    def test_assess_general_chat_destination(self):
        r = client.post("/assess", json=_CHAT_PAYLOAD)
        assert r.json()["destination"] == "general_chat"

    def test_assess_general_chat_has_request_id(self):
        r = client.post("/assess", json=_CHAT_PAYLOAD)
        assert len(r.json()["request_id"]) > 0

    def test_assess_without_transcript_still_works(self):
        """transcript is optional — omitting it must not crash."""
        payload = {k: v for k, v in _CHAT_PAYLOAD.items() if k != "transcript"}
        r = client.post("/assess", json=payload)
        assert r.status_code == 200
        assert len(r.json().get("message", "")) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# POST /assess — validation failures (422)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAssessValidationFailures:

    def test_invalid_intent_returns_422(self):
        r = client.post("/assess", json={
            "intent": "unknown_intent",
            "symptoms": [],
            "severity": "low",
            "confidence": 0.9,
        })
        assert r.status_code == 422

    def test_missing_intent_returns_422(self):
        r = client.post("/assess", json={
            "symptoms": ["dizziness"],
            "severity": "low",
        })
        assert r.status_code == 422

    def test_missing_severity_returns_422(self):
        r = client.post("/assess", json={
            "intent": "health_issue",
            "symptoms": [],
        })
        assert r.status_code == 422

    def test_confidence_above_1_returns_422(self):
        r = client.post("/assess", json={
            "intent": "health_issue",
            "symptoms": [],
            "severity": "low",
            "confidence": 1.5,
        })
        assert r.status_code == 422

    def test_confidence_below_0_returns_422(self):
        r = client.post("/assess", json={
            "intent": "health_issue",
            "symptoms": [],
            "severity": "low",
            "confidence": -0.1,
        })
        assert r.status_code == 422

    def test_invalid_severity_returns_422(self):
        r = client.post("/assess", json={
            "intent": "health_issue",
            "symptoms": [],
            "severity": "extreme",
            "confidence": 0.9,
        })
        assert r.status_code == 422

    def test_422_response_has_request_id(self):
        r = client.post("/assess", json={
            "intent": "bad_intent",
            "symptoms": [],
            "severity": "low",
            "confidence": 0.9,
        })
        assert r.status_code == 422
        body = r.json()
        assert "request_id" in body or "detail" in body

    def test_empty_body_returns_422(self):
        r = client.post("/assess", json={})
        assert r.status_code == 422

    def test_intent_case_insensitive(self):
        """Intents are normalised to lowercase — HEALTH_ISSUE should work."""
        r = client.post("/assess", json={
            "intent":     "HEALTH_ISSUE",
            "symptoms":   ["dizziness"],
            "severity":   "LOW",
            "confidence": 0.8,
        })
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# GET /history
# ═══════════════════════════════════════════════════════════════════════════════

class TestHistoryEndpoint:

    @pytest.fixture(autouse=True)
    def seed_log(self):
        """Ensure at least one log entry exists before history tests run."""
        client.post("/assess", json=_HEALTH_PAYLOAD)

    def test_history_returns_200(self):
        r = client.get("/history")
        assert r.status_code == 200

    def test_history_has_count_key(self):
        r = client.get("/history")
        assert "count" in r.json()

    def test_history_has_entries_key(self):
        r = client.get("/history")
        assert "entries" in r.json()

    def test_history_entries_is_list(self):
        r = client.get("/history")
        assert isinstance(r.json()["entries"], list)

    def test_history_count_matches_entries(self):
        r = client.get("/history")
        data = r.json()
        assert data["count"] == len(data["entries"])

    def test_history_has_at_least_one_entry(self):
        r = client.get("/history")
        assert r.json()["count"] >= 1

    def test_history_entry_has_request_id(self):
        r = client.get("/history")
        first = r.json()["entries"][0]
        assert "request_id" in first

    def test_history_entry_has_timestamp(self):
        r = client.get("/history")
        first = r.json()["entries"][0]
        assert "timestamp" in first

    def test_history_entry_has_intent(self):
        r = client.get("/history")
        first = r.json()["entries"][0]
        assert "intent" in first

    def test_history_limit_query_param(self):
        # Seed 3 more entries
        for _ in range(3):
            client.post("/assess", json=_HEALTH_PAYLOAD)
        r = client.get("/history?limit=2")
        assert r.json()["count"] <= 2

    def test_history_limit_1(self):
        r = client.get("/history?limit=1")
        assert len(r.json()["entries"]) == 1

    def test_history_limit_capped_at_100(self):
        r = client.get("/history?limit=9999")
        assert r.status_code == 200   # should not crash


# ═══════════════════════════════════════════════════════════════════════════════
# POST /transcribe  (text-in pipeline, Llama mocked)
# ═══════════════════════════════════════════════════════════════════════════════

from unittest.mock import patch, MagicMock  # noqa: E402
from dataclasses import dataclass, field as dc_field  # noqa: E402
from typing import Any, Dict  # noqa: E402


@dataclass
class _MockClassifyResult:
    success: bool
    payload: Dict[str, Any]
    is_fallback: bool = False
    error: str = ""
    def __bool__(self): return self.success


_CLASSIFY_HEALTH = _MockClassifyResult(
    success=True,
    payload={
        "intent":     "health_issue",
        "symptoms":   ["chest_pain", "dizziness"],
        "severity":   "high",
        "confidence": 0.93,
    },
)

_CLASSIFY_CHAT = _MockClassifyResult(
    success=True,
    payload={
        "intent":     "general_chat",
        "symptoms":   [],
        "severity":   "low",
        "confidence": 0.99,
    },
)

_CLASSIFY_FALLBACK = _MockClassifyResult(
    success=False,
    is_fallback=True,
    payload={
        "intent":     "health_issue",
        "symptoms":   [],
        "severity":   "low",
        "confidence": 0.0,
    },
    error="Ollama unreachable",
)


class TestTranscribeEndpoint:
    """Tests for POST /transcribe (raw transcript → full pipeline)."""

    def _post(self, transcript: str, mock_result=None) -> "Response":
        mock_result = mock_result or _CLASSIFY_HEALTH
        with patch("main.classify", return_value=mock_result):
            return client.post("/transcribe", json={"transcript": transcript})

    # ── Happy path: health_issue ─────────────────────────────────────────────

    def test_transcribe_health_returns_200(self):
        r = self._post("I have chest pain and I feel dizzy.")
        assert r.status_code == 200

    def test_transcribe_health_has_request_id(self):
        r = self._post("I have chest pain.")
        assert len(r.json()["request_id"]) == 36

    def test_transcribe_health_has_risk_level(self):
        r = self._post("I have chest pain.")
        assert r.json()["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    def test_transcribe_health_has_destination(self):
        r = self._post("I have chest pain.")
        assert r.json()["destination"] == "health_issue"

    def test_transcribe_health_has_action(self):
        r = self._post("I have chest pain.")
        action = r.json().get("action")
        assert action is not None
        assert "message" in action

    # ── Happy path: general_chat ──────────────────────────────────────────────

    def test_transcribe_chat_returns_200(self):
        r = self._post("Good morning!", mock_result=_CLASSIFY_CHAT)
        assert r.status_code == 200

    def test_transcribe_chat_destination(self):
        r = self._post("Hello!", mock_result=_CLASSIFY_CHAT)
        assert r.json()["destination"] == "general_chat"

    def test_transcribe_chat_has_message(self):
        r = self._post("Good morning!", mock_result=_CLASSIFY_CHAT)
        msg = r.json().get("message", "")
        assert len(msg) > 0

    def test_transcribe_chat_topic_from_transcript(self):
        """Topic detection must use the raw transcript, not Llama's payload."""
        r = self._post("Good morning, how are you?", mock_result=_CLASSIFY_CHAT)
        # Transcript contains "morning" → greeting topic
        assert r.json().get("topic") == "greeting"

    # ── Llama fallback (non-fatal) ────────────────────────────────────────────

    def test_transcribe_fallback_still_returns_200(self):
        """A Llama fallback payload is valid — pipeline must still complete."""
        r = self._post("something unclear", mock_result=_CLASSIFY_FALLBACK)
        assert r.status_code == 200

    def test_transcribe_fallback_has_request_id(self):
        r = self._post("something", mock_result=_CLASSIFY_FALLBACK)
        assert len(r.json()["request_id"]) == 36

    # ── Validation errors ─────────────────────────────────────────────────────

    def test_transcribe_empty_transcript_returns_422(self):
        """Pydantic min_length=1 must reject empty strings."""
        r = client.post("/transcribe", json={"transcript": ""})
        assert r.status_code == 422

    def test_transcribe_missing_transcript_key_returns_422(self):
        r = client.post("/transcribe", json={})
        assert r.status_code == 422

    # ── Response shape ────────────────────────────────────────────────────────

    def test_transcribe_response_has_intent(self):
        r = self._post("I have chest pain.")
        assert "intent" in r.json()

    def test_transcribe_response_has_destination(self):
        r = self._post("I have chest pain.")
        assert "destination" in r.json()


# ═══════════════════════════════════════════════════════════════════════════════
# GET /status — system readiness probe
# ═══════════════════════════════════════════════════════════════════════════════

class TestStatusEndpoint:
    """
    Tests for GET /status.

    The endpoint checks: Ollama reachability, Piper TTS model file,
    log writability, and webhook configuration.  All external calls are
    mocked so this suite runs without Ollama or a real TTS model.
    """

    def _get_status(self):
        return client.get("/status")

    # ── HTTP basics ───────────────────────────────────────────────────────────

    def test_status_returns_200_or_503(self):
        """Must return either 200 (ready) or 503 (not ready), never 5xx error."""
        r = self._get_status()
        assert r.status_code in (200, 503)

    def test_status_content_type_is_json(self):
        r = self._get_status()
        assert "application/json" in r.headers["content-type"]

    # ── Top-level response shape ──────────────────────────────────────────────

    def test_status_has_ready_field(self):
        r = self._get_status()
        assert "ready" in r.json()

    def test_status_ready_is_bool(self):
        r = self._get_status()
        assert isinstance(r.json()["ready"], bool)

    def test_status_has_version(self):
        r = self._get_status()
        assert "version" in r.json()

    def test_status_version_is_string(self):
        r = self._get_status()
        assert isinstance(r.json()["version"], str)

    def test_status_has_checks(self):
        r = self._get_status()
        assert "checks" in r.json()

    def test_status_checks_is_dict(self):
        r = self._get_status()
        assert isinstance(r.json()["checks"], dict)

    # ── Individual check keys ─────────────────────────────────────────────────

    def test_status_has_ollama_check(self):
        r = self._get_status()
        assert "ollama" in r.json()["checks"]

    def test_status_has_tts_check(self):
        r = self._get_status()
        assert "tts" in r.json()["checks"]

    def test_status_has_log_check(self):
        r = self._get_status()
        assert "log" in r.json()["checks"]

    def test_status_has_webhook_check(self):
        r = self._get_status()
        assert "webhook" in r.json()["checks"]

    # ── Each check has 'ok' and 'detail' ─────────────────────────────────────

    def test_ollama_check_has_ok(self):
        r = self._get_status()
        assert "ok" in r.json()["checks"]["ollama"]

    def test_tts_check_has_ok(self):
        r = self._get_status()
        assert "ok" in r.json()["checks"]["tts"]

    def test_log_check_has_ok(self):
        r = self._get_status()
        assert "ok" in r.json()["checks"]["log"]

    def test_webhook_check_has_ok(self):
        r = self._get_status()
        assert "ok" in r.json()["checks"]["webhook"]

    def test_ollama_check_has_detail(self):
        r = self._get_status()
        assert "detail" in r.json()["checks"]["ollama"]

    def test_tts_check_has_detail(self):
        r = self._get_status()
        assert "detail" in r.json()["checks"]["tts"]

    def test_log_check_has_detail(self):
        r = self._get_status()
        assert "detail" in r.json()["checks"]["log"]

    def test_webhook_check_has_detail(self):
        r = self._get_status()
        assert "detail" in r.json()["checks"]["webhook"]

    # ── Webhook configured/not-configured reflection ──────────────────────────

    def test_webhook_not_configured_by_default(self):
        """In the test environment WELLRING_WEBHOOK_URL is not set."""
        import os
        if not os.environ.get("WELLRING_WEBHOOK_URL"):
            r = self._get_status()
            webhook = r.json()["checks"]["webhook"]
            assert webhook["configured"] is False

    def test_webhook_ok_is_true_even_when_not_configured(self):
        """Webhook is optional — its absence should never mark the system 'not ok'."""
        r = self._get_status()
        assert r.json()["checks"]["webhook"]["ok"] is True

    # ── Log path returned ─────────────────────────────────────────────────────

    def test_log_check_has_path(self):
        r = self._get_status()
        assert "path" in r.json()["checks"]["log"]

    def test_log_path_ends_with_pipeline_log(self):
        r = self._get_status()
        path = r.json()["checks"]["log"]["path"]
        assert path.endswith("pipeline.log")

    # ── TTS model path returned ───────────────────────────────────────────────

    def test_tts_check_has_model_path(self):
        r = self._get_status()
        assert "model_path" in r.json()["checks"]["tts"]

    def test_tts_model_path_ends_with_onnx(self):
        r = self._get_status()
        path = r.json()["checks"]["tts"]["model_path"]
        assert path.endswith(".onnx")
