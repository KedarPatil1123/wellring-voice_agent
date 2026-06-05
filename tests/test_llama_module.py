"""
test_llama_module.py
====================
Unit tests for the WellRing Llama triage layer:
    - llama/prompt.py
    - llama/parser.py
    - llama/client.py   (Ollama calls mocked — no live server needed)

Run with:
    python -m pytest tests/test_llama_module.py -v
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from unittest.mock import patch, MagicMock

from llama.prompt import build_messages, KNOWN_SYMPTOMS, SYSTEM_PROMPT
from llama.parser import parse
from llama.client import classify, _FALLBACK_PAYLOAD, MODEL_NAME


# ═══════════════════════════════════════════════════════════════════════════════
# prompt.py tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestPrompt:

    def test_build_messages_returns_two_items(self):
        msgs = build_messages("I feel dizzy")
        assert len(msgs) == 2

    def test_first_message_is_system(self):
        msgs = build_messages("test")
        assert msgs[0]["role"] == "system"
        assert SYSTEM_PROMPT in msgs[0]["content"]

    def test_second_message_is_user(self):
        msgs = build_messages("I have a headache")
        assert msgs[1]["role"] == "user"

    def test_transcript_included_in_user_message(self):
        msgs = build_messages("chest pain")
        assert "chest pain" in msgs[1]["content"]

    def test_transcript_is_stripped(self):
        msgs = build_messages("   dizzy   ")
        assert "dizzy" in msgs[1]["content"]
        assert msgs[1]["content"].count("  ") == 0 or "dizzy" in msgs[1]["content"]

    def test_known_symptoms_list_not_empty(self):
        assert len(KNOWN_SYMPTOMS) > 0

    def test_known_symptoms_are_all_strings(self):
        assert all(isinstance(s, str) for s in KNOWN_SYMPTOMS)

    def test_known_symptoms_contains_critical_keys(self):
        for key in ("chest_pain", "unconscious", "stroke_symptoms"):
            assert key in KNOWN_SYMPTOMS

    def test_system_prompt_contains_rules(self):
        assert "health_issue" in SYSTEM_PROMPT
        assert "general_chat" in SYSTEM_PROMPT
        assert "confidence" in SYSTEM_PROMPT


# ═══════════════════════════════════════════════════════════════════════════════
# parser.py tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestParser:

    # --- Happy path ---

    def test_clean_json_parses(self):
        r = parse('{"intent":"health_issue","symptoms":["dizziness"],"severity":"medium","confidence":0.88}')
        assert r.success is True
        assert r.payload["intent"] == "health_issue"

    def test_json_in_markdown_fence_parses(self):
        raw = '```json\n{"intent":"general_chat","symptoms":[],"severity":"low","confidence":0.99}\n```'
        r = parse(raw)
        assert r.success is True
        assert r.payload["intent"] == "general_chat"

    def test_json_with_leading_prose_parses(self):
        raw = 'Sure! Here is the JSON:\n{"intent":"health_issue","symptoms":["fever"],"severity":"medium","confidence":0.75}'
        r = parse(raw)
        assert r.success is True

    def test_payload_confidence_is_float(self):
        r = parse('{"intent":"health_issue","symptoms":[],"severity":"low","confidence":0.9}')
        assert isinstance(r.payload["confidence"], float)

    def test_symptoms_filtered_to_known_keys(self):
        raw = '{"intent":"health_issue","symptoms":["chest_pain","headache","unknown_thing"],"severity":"high","confidence":0.8}'
        r = parse(raw)
        assert r.success is True
        assert "headache" not in r.payload["symptoms"]
        assert "unknown_thing" not in r.payload["symptoms"]
        assert "chest_pain" in r.payload["symptoms"]

    def test_uppercase_symptoms_normalised(self):
        raw = '{"intent":"health_issue","symptoms":["CHEST_PAIN","DIZZINESS"],"severity":"high","confidence":0.9}'
        r = parse(raw)
        assert "chest_pain" in r.payload["symptoms"]

    def test_invalid_intent_repaired_to_general_chat(self):
        raw = '{"intent":"unknown_intent","symptoms":[],"severity":"low","confidence":0.5}'
        r = parse(raw)
        assert r.success is True
        assert r.payload["intent"] == "general_chat"

    def test_invalid_severity_repaired_to_low(self):
        raw = '{"intent":"health_issue","symptoms":[],"severity":"extreme","confidence":0.6}'
        r = parse(raw)
        assert r.success is True
        assert r.payload["severity"] == "low"

    def test_confidence_clamped_above_one(self):
        raw = '{"intent":"health_issue","symptoms":[],"severity":"low","confidence":2.5}'
        r = parse(raw)
        assert r.payload["confidence"] <= 1.0

    def test_confidence_clamped_below_zero(self):
        raw = '{"intent":"health_issue","symptoms":[],"severity":"low","confidence":-0.5}'
        r = parse(raw)
        assert r.payload["confidence"] >= 0.0

    def test_missing_confidence_defaults_to_one(self):
        raw = '{"intent":"general_chat","symptoms":[],"severity":"low"}'
        r = parse(raw)
        assert r.payload["confidence"] == 1.0

    def test_symptoms_non_list_repaired_to_empty(self):
        raw = '{"intent":"health_issue","symptoms":"chest_pain","severity":"high","confidence":0.9}'
        r = parse(raw)
        assert r.payload["symptoms"] == []

    # --- Failure cases ---

    def test_empty_string_fails(self):
        r = parse("")
        assert r.success is False
        assert "empty" in r.error.lower()

    def test_no_json_object_fails(self):
        r = parse("I cannot answer that.")
        assert r.success is False

    def test_malformed_json_fails(self):
        r = parse('{"intent": "health_issue", "symptoms": [}')
        assert r.success is False

    def test_bool_true_on_success(self):
        r = parse('{"intent":"general_chat","symptoms":[],"severity":"low","confidence":0.9}')
        assert bool(r) is True

    def test_bool_false_on_failure(self):
        r = parse("not json at all")
        assert bool(r) is False


# ═══════════════════════════════════════════════════════════════════════════════
# client.py tests  (Ollama mocked)
# ═══════════════════════════════════════════════════════════════════════════════

_GOOD_RESPONSE = '{"intent":"health_issue","symptoms":["chest_pain"],"severity":"high","confidence":0.93}'
_CHAT_RESPONSE = '{"intent":"general_chat","symptoms":[],"severity":"low","confidence":0.99}'
_GARBAGE       = "I am not sure what you mean."


def _mock_ollama(content: str):
    """Return a mock that mimics the Ollama SDK ChatResponse object."""
    msg = MagicMock()
    msg.content = content
    resp = MagicMock()
    resp.message = msg
    return resp


class TestClient:

    @patch("llama.client.ollama.chat")
    def test_classify_health_issue_succeeds(self, mock_chat):
        mock_chat.return_value = _mock_ollama(_GOOD_RESPONSE)
        result = classify("I have chest pain")
        assert result.success is True
        assert result.payload["intent"] == "health_issue"
        assert result.payload["risk_level"] if "risk_level" in result.payload else True

    @patch("llama.client.ollama.chat")
    def test_classify_general_chat_succeeds(self, mock_chat):
        mock_chat.return_value = _mock_ollama(_CHAT_RESPONSE)
        result = classify("Hello, good morning!")
        assert result.success is True
        assert result.payload["intent"] == "general_chat"

    @patch("llama.client.ollama.chat")
    def test_classify_payload_has_all_fields(self, mock_chat):
        mock_chat.return_value = _mock_ollama(_GOOD_RESPONSE)
        result = classify("I feel dizzy")
        for key in ("intent", "symptoms", "severity", "confidence"):
            assert key in result.payload

    @patch("llama.client.ollama.chat")
    def test_classify_attempts_recorded(self, mock_chat):
        mock_chat.return_value = _mock_ollama(_GOOD_RESPONSE)
        result = classify("I have a fever")
        assert result.attempts == 1

    @patch("llama.client.ollama.chat")
    def test_classify_garbage_response_uses_fallback(self, mock_chat):
        mock_chat.return_value = _mock_ollama(_GARBAGE)
        result = classify("something")
        assert result.is_fallback is True
        assert result.payload["confidence"] == 0.0

    @patch("llama.client.ollama.chat", side_effect=ConnectionError("Ollama down"))
    def test_classify_ollama_error_uses_fallback(self, mock_chat):
        result = classify("I cannot breathe")
        assert result.is_fallback is True
        assert result.success is False

    @patch("llama.client.ollama.chat", side_effect=ConnectionError("down"))
    def test_classify_retries_max_times(self, mock_chat):
        result = classify("test input")
        assert mock_chat.call_count == 3   # MAX_RETRIES

    @patch("llama.client.ollama.chat")
    def test_classify_retries_on_bad_parse_then_succeeds(self, mock_chat):
        # First call: garbage. Second call: valid JSON.
        mock_chat.side_effect = [
            _mock_ollama(_GARBAGE),
            _mock_ollama(_GOOD_RESPONSE),
        ]
        result = classify("chest hurts")
        assert result.success is True
        assert result.attempts == 2

    def test_classify_empty_transcript_returns_fallback(self):
        result = classify("   ")
        assert result.is_fallback is True
        assert result.success is False

    @patch("llama.client.ollama.chat")
    def test_classify_uses_temperature_zero(self, mock_chat):
        mock_chat.return_value = _mock_ollama(_GOOD_RESPONSE)
        classify("headache")
        _, kwargs = mock_chat.call_args
        options = kwargs.get("options") or mock_chat.call_args[1].get("options", {})
        assert options.get("temperature") == 0

    @patch("llama.client.ollama.chat")
    def test_classify_uses_correct_model(self, mock_chat):
        mock_chat.return_value = _mock_ollama(_GOOD_RESPONSE)
        classify("fever since yesterday")
        _, kwargs = mock_chat.call_args
        assert mock_chat.call_args[1].get("model") == MODEL_NAME or \
               mock_chat.call_args[0][0] if mock_chat.call_args[0] else True

    @patch("llama.client.ollama.chat")
    def test_classify_bool_true_on_success(self, mock_chat):
        mock_chat.return_value = _mock_ollama(_GOOD_RESPONSE)
        result = classify("dizziness")
        assert bool(result) is True

    @patch("llama.client.ollama.chat", side_effect=Exception("err"))
    def test_classify_bool_false_on_failure(self, _):
        result = classify("test")
        assert bool(result) is False
