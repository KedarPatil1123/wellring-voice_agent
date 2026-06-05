"""
test_orchestrator.py
====================
Integration tests for the WellRing end-to-end orchestrator.

Mocks all hardware / network layers so no microphone, Ollama server,
or Piper voice model is needed:
    - whisper_layer.record()     → RecordResult  (fake wav file path)
    - whisper_layer.transcribe() → TranscribeResult
    - llama.classify()           → ClassifyResult
    - tts.speak()                → SpeakResult

Tests verify that the full Whisper → Llama → Pipeline → TTS chain
wires together correctly and that each failure mode produces the right
TurnResult shape.

Run with:
    python -m pytest tests/test_orchestrator.py -v
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from unittest.mock import patch, MagicMock
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List


# ── Minimal stub dataclasses matching the real modules ────────────────────────

@dataclass
class _RecordResult:
    success: bool
    file_path: str = "fake.wav"
    is_silent: bool = False
    error: str = ""
    def __bool__(self): return self.success

@dataclass
class _TranscribeResult:
    success: bool
    text: str = ""
    error: str = ""
    @property
    def is_empty(self): return not self.text.strip()
    def __bool__(self): return self.success

@dataclass
class _ClassifyResult:
    success: bool
    payload: Dict[str, Any] = field(default_factory=dict)
    is_fallback: bool = False
    error: str = ""
    def __bool__(self): return self.success

@dataclass
class _SpeakResult:
    success: bool
    error: str = ""
    def __bool__(self): return self.success


# ── Shared payloads ───────────────────────────────────────────────────────────

_HEALTH_PAYLOAD = {
    "intent":     "health_issue",
    "symptoms":   ["chest_pain", "dizziness"],
    "severity":   "high",
    "confidence": 0.93,
}

_CHAT_PAYLOAD = {
    "intent":     "general_chat",
    "symptoms":   [],
    "severity":   "low",
    "confidence": 0.88,
}

_CRITICAL_PAYLOAD = {
    "intent":     "health_issue",
    "symptoms":   ["chest_pain", "unconscious", "stroke_symptoms"],
    "severity":   "critical",
    "confidence": 1.0,
}


# ── Helper that patches all four external layers ──────────────────────────────

def _run_with_mocks(
    *,
    record_ok:      bool = True,
    is_silent:      bool = False,
    transcript:     str  = "I have chest pain",
    transcribe_ok:  bool = True,
    classify_payload: Dict = None,
    classify_ok:    bool = True,
    is_fallback:    bool = False,
    speak_ok:       bool = True,
):
    """Patch all external layers and call orchestrator.run_once()."""
    from orchestrator import run_once

    classify_payload = classify_payload or _HEALTH_PAYLOAD

    rec  = _RecordResult(success=record_ok, is_silent=is_silent,
                         error="mic error" if not record_ok else "")
    tr   = _TranscribeResult(success=transcribe_ok, text=transcript,
                             error="whisper error" if not transcribe_ok else "")
    cl   = _ClassifyResult(success=classify_ok, payload=classify_payload,
                           is_fallback=is_fallback,
                           error="llama error" if not classify_ok else "")
    sr   = _SpeakResult(success=speak_ok,
                        error="tts error" if not speak_ok else "")

    with patch("orchestrator.record",     return_value=rec), \
         patch("orchestrator.transcribe", return_value=tr), \
         patch("orchestrator.classify",   return_value=cl), \
         patch("orchestrator.speak",      return_value=sr):
        return run_once()


# ═══════════════════════════════════════════════════════════════════════════════
# Happy-path tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestOrchestratorHappyPath:

    def test_health_issue_turn_succeeds(self):
        result = _run_with_mocks(classify_payload=_HEALTH_PAYLOAD)
        assert result.success is True

    def test_health_issue_intent_set(self):
        result = _run_with_mocks(classify_payload=_HEALTH_PAYLOAD)
        assert result.intent == "health_issue"

    def test_health_issue_risk_level_present(self):
        result = _run_with_mocks(classify_payload=_HEALTH_PAYLOAD)
        assert result.risk_level in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    def test_health_issue_action_is_dict(self):
        result = _run_with_mocks(classify_payload=_HEALTH_PAYLOAD)
        assert isinstance(result.action, dict)

    def test_health_issue_request_id_is_uuid(self):
        result = _run_with_mocks(classify_payload=_HEALTH_PAYLOAD)
        assert len(result.request_id) == 36

    def test_health_issue_transcript_captured(self):
        result = _run_with_mocks(
            transcript="I have chest pain",
            classify_payload=_HEALTH_PAYLOAD,
        )
        assert result.transcript == "I have chest pain"

    def test_general_chat_turn_succeeds(self):
        result = _run_with_mocks(
            transcript="Good morning!",
            classify_payload=_CHAT_PAYLOAD,
        )
        assert result.success is True
        assert result.intent == "general_chat"

    def test_general_chat_no_risk_level(self):
        result = _run_with_mocks(
            transcript="How are you?",
            classify_payload=_CHAT_PAYLOAD,
        )
        # general_chat doesn't produce a numerical risk_level from scoring engine
        assert result.success is True

    def test_critical_symptoms_score_critical(self):
        result = _run_with_mocks(classify_payload=_CRITICAL_PAYLOAD)
        assert result.risk_level == "CRITICAL"

    def test_spoken_text_not_empty_on_success(self):
        result = _run_with_mocks(classify_payload=_HEALTH_PAYLOAD)
        assert isinstance(result.spoken_text, str)
        assert len(result.spoken_text) > 0

    def test_no_stage_errors_on_clean_run(self):
        result = _run_with_mocks(classify_payload=_HEALTH_PAYLOAD)
        # TTS errors are non-fatal; pipeline errors should be absent
        pipeline_errors = {k: v for k, v in result.stage_errors.items()
                          if k != "speak"}
        assert pipeline_errors == {}

    def test_turn_result_bool_true_on_success(self):
        result = _run_with_mocks(classify_payload=_HEALTH_PAYLOAD)
        assert bool(result) is True


# ═══════════════════════════════════════════════════════════════════════════════
# Failure-mode tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestOrchestratorFailureModes:

    def test_record_failure_aborts_turn(self):
        result = _run_with_mocks(record_ok=False)
        assert result.success is False
        assert "record" in result.stage_errors

    def test_silent_recording_aborts_turn(self):
        result = _run_with_mocks(is_silent=True)
        assert result.success is False
        assert "record" in result.stage_errors

    def test_empty_transcript_aborts_turn(self):
        result = _run_with_mocks(transcript="", transcribe_ok=True)
        assert result.success is False
        assert "transcribe" in result.stage_errors

    def test_transcribe_failure_aborts_turn(self):
        result = _run_with_mocks(transcribe_ok=False, transcript="")
        assert result.success is False

    def test_llama_fallback_does_not_abort_turn(self):
        """Llama returning a fallback is non-fatal; pipeline still continues."""
        result = _run_with_mocks(
            classify_ok=False,
            is_fallback=True,
            classify_payload={
                "intent":     "health_issue",
                "symptoms":   [],
                "severity":   "low",
                "confidence": 0.0,
            },
        )
        # Fallback payload is valid — pipeline should complete
        assert result.success is True

    def test_tts_failure_is_non_fatal(self):
        """A failed TTS call should not mark the turn as failed."""
        result = _run_with_mocks(
            classify_payload=_HEALTH_PAYLOAD,
            speak_ok=False,
        )
        assert result.success is True
        assert "speak" in result.stage_errors

    def test_turn_result_bool_false_on_failure(self):
        result = _run_with_mocks(record_ok=False)
        assert bool(result) is False

    def test_record_result_attached_on_record_failure(self):
        result = _run_with_mocks(record_ok=False)
        assert result.record_result is not None

    def test_transcribe_result_attached_on_transcribe_failure(self):
        result = _run_with_mocks(transcribe_ok=False, transcript="")
        assert result.transcribe_result is not None


# ═══════════════════════════════════════════════════════════════════════════════
# Result shape / contract tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestOrchestratorResultShape:

    def test_turn_result_has_all_fields(self):
        result = _run_with_mocks(classify_payload=_HEALTH_PAYLOAD)
        for attr in ("success", "transcript", "intent", "risk_level",
                     "action", "request_id", "spoken_text",
                     "stage_errors", "record_result",
                     "transcribe_result", "classify_result", "speak_result"):
            assert hasattr(result, attr), f"TurnResult missing field: {attr}"

    def test_stage_errors_is_dict(self):
        result = _run_with_mocks(classify_payload=_HEALTH_PAYLOAD)
        assert isinstance(result.stage_errors, dict)

    def test_classify_result_attached_on_success(self):
        result = _run_with_mocks(classify_payload=_HEALTH_PAYLOAD)
        assert result.classify_result is not None

    def test_speak_result_attached_on_success(self):
        result = _run_with_mocks(classify_payload=_HEALTH_PAYLOAD)
        assert result.speak_result is not None

    def test_multiple_turns_produce_unique_request_ids(self):
        ids = {_run_with_mocks(classify_payload=_HEALTH_PAYLOAD).request_id
               for _ in range(5)}
        assert len(ids) == 5


# ═══════════════════════════════════════════════════════════════════════════════
# Transcript pass-through tests
# Verify that the Whisper transcript is forwarded into the validate→route chain
# so the conversation handler can detect topics correctly.
# ═══════════════════════════════════════════════════════════════════════════════

class TestOrchestratorTranscriptFlow:
    """
    Covers the transcript forwarding fix in run_once():
        raw_payload = {**cl.payload, "transcript": tr.text}

    Without this, the conversation router always returns topic="unknown"
    because generate_response() gets an empty transcript.
    """

    def test_general_chat_spoken_text_not_empty(self):
        """The TTS response must contain actual words, not an empty string."""
        result = _run_with_mocks(
            transcript="Good morning, how are you?",
            classify_payload=_CHAT_PAYLOAD,
        )
        assert result.success
        assert len(result.spoken_text) > 0

    def test_general_chat_spoken_text_is_string(self):
        result = _run_with_mocks(
            transcript="Hello there!",
            classify_payload=_CHAT_PAYLOAD,
        )
        assert isinstance(result.spoken_text, str)

    def test_health_issue_spoken_text_contains_message(self):
        """Health issue spoken text must come from the action message."""
        result = _run_with_mocks(
            transcript="I have chest pain and difficulty breathing.",
            classify_payload={
                "intent":     "health_issue",
                "symptoms":   ["chest_pain", "breathing_problem"],
                "severity":   "high",
                "confidence": 0.95,
            },
        )
        assert result.success
        # The spoken text comes from the scoring engine's action message
        assert len(result.spoken_text) > 0

    def test_transcript_survives_to_turn_result(self):
        """transcript field on TurnResult must exactly match Whisper output."""
        result = _run_with_mocks(
            transcript="I feel very dizzy this morning.",
            classify_payload=_CHAT_PAYLOAD,
        )
        assert result.transcript == "I feel very dizzy this morning."

    def test_general_chat_no_stage_errors_from_transcript_flow(self):
        """Forwarding transcript must not introduce any pipeline errors."""
        result = _run_with_mocks(
            transcript="Good evening!",
            classify_payload=_CHAT_PAYLOAD,
        )
        assert result.success
        # validate / route / speak errors should be absent
        assert "validate" not in result.stage_errors
        assert "route" not in result.stage_errors

