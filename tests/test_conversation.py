"""
test_conversation.py
====================
Unit tests for the WellRing general-chat conversation handler:
    - pipeline/conversation.py    (_detect_topic, generate_response)
    - pipeline/router.py          (_handle_general_chat integration)

Run with:
    python -m pytest tests/test_conversation.py -v
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from pipeline.conversation import (
    generate_response,
    _detect_topic,
    ConversationResult,
    _TOPIC_KEYWORDS,
    _RESPONSES,
    _FOLLOW_UPS,
)


# ═══════════════════════════════════════════════════════════════════════════════
# _detect_topic
# ═══════════════════════════════════════════════════════════════════════════════

class TestDetectTopic:

    def test_greeting_hello(self):
        assert _detect_topic("hello there") == "greeting"

    def test_greeting_hi(self):
        assert _detect_topic("hi, how are you") == "greeting"

    def test_greeting_good_morning(self):
        assert _detect_topic("Good morning!") == "greeting"

    def test_farewell_bye(self):
        assert _detect_topic("Bye, see you later") == "farewell"

    def test_farewell_goodnight(self):
        assert _detect_topic("Good night, WellRing") == "farewell"

    def test_wellbeing_how_are_you(self):
        assert _detect_topic("How are you today?") == "wellbeing"

    def test_gratitude_thank_you(self):
        assert _detect_topic("Thank you for your help") == "gratitude"

    def test_gratitude_thanks(self):
        assert _detect_topic("thanks!") == "gratitude"

    def test_weather(self):
        assert _detect_topic("Is it going to rain today?") == "weather"

    def test_help(self):
        assert _detect_topic("Help me, what can you do?") == "help"

    def test_time(self):
        assert _detect_topic("What time is it?") == "time"

    def test_boredom(self):
        assert _detect_topic("I'm so bored today.") == "boredom"

    def test_compliment(self):
        assert _detect_topic("Good job, WellRing!") == "compliment"

    def test_unknown_returns_unknown(self):
        assert _detect_topic("xyzzy frobnicator") == "unknown"

    def test_empty_string_returns_unknown(self):
        assert _detect_topic("") == "unknown"

    def test_case_insensitive(self):
        assert _detect_topic("HELLO THERE") == "greeting"

    def test_partial_match_in_sentence(self):
        assert _detect_topic("I wanted to say thank you so much") == "gratitude"


# ═══════════════════════════════════════════════════════════════════════════════
# generate_response — result shape & contract
# ═══════════════════════════════════════════════════════════════════════════════

class TestGenerateResponse:

    def _payload(self, transcript: str = "") -> dict:
        return {"intent": "general_chat", "transcript": transcript}

    def test_returns_conversation_result(self):
        r = generate_response(self._payload("hello"))
        assert isinstance(r, ConversationResult)

    def test_success_is_always_true(self):
        for phrase in ("hello", "bye", "xyzzy", ""):
            assert generate_response(self._payload(phrase)).success is True

    def test_text_is_non_empty_string(self):
        for phrase in ("hello", "bye", "help me", ""):
            r = generate_response(self._payload(phrase))
            assert isinstance(r.text, str)
            assert len(r.text) > 0

    def test_topic_is_string(self):
        r = generate_response(self._payload("hello"))
        assert isinstance(r.topic, str)

    def test_follow_up_is_string(self):
        r = generate_response(self._payload("anything"))
        assert isinstance(r.follow_up, str)

    def test_greeting_topic_detected(self):
        r = generate_response(self._payload("Good morning WellRing"))
        assert r.topic == "greeting"

    def test_farewell_has_no_follow_up(self):
        r = generate_response(self._payload("Goodbye, see you later"))
        assert r.topic == "farewell"
        assert r.follow_up == ""

    def test_gratitude_has_no_follow_up(self):
        r = generate_response(self._payload("Thank you!"))
        assert r.topic == "gratitude"
        assert r.follow_up == ""

    def test_help_includes_wellring_name(self):
        r = generate_response(self._payload("What can you do?"))
        assert r.topic == "help"
        assert len(r.text) > 0

    def test_unknown_topic_still_returns_response(self):
        r = generate_response(self._payload("xyzzy frobnicator"))
        assert r.topic == "unknown"
        assert len(r.text) > 0

    def test_empty_transcript_still_returns_response(self):
        r = generate_response(self._payload(""))
        assert len(r.text) > 0

    def test_missing_transcript_key_safe(self):
        """payload without 'transcript' key must not crash."""
        r = generate_response({"intent": "general_chat"})
        assert r.success is True
        assert len(r.text) > 0

    def test_bool_true_on_success(self):
        assert bool(generate_response(self._payload("hello")))

    def test_topic_is_from_known_set_or_unknown(self):
        known = set(_TOPIC_KEYWORDS.keys()) | {"unknown"}
        r = generate_response(self._payload("hello"))
        assert r.topic in known

    def test_response_text_comes_from_template(self):
        """Response text must be one of the pre-defined templates."""
        r = generate_response(self._payload("hello"))
        all_templates = [t for ts in _RESPONSES.values() for t in ts]
        assert r.text in all_templates

    def test_all_topics_produce_non_empty_response(self):
        """Every topic in _TOPIC_KEYWORDS must map to at least one template."""
        for topic, keywords in _TOPIC_KEYWORDS.items():
            sample_phrase = keywords[0]
            r = generate_response(self._payload(sample_phrase))
            assert len(r.text) > 0, f"No response for topic '{topic}'"


# ═══════════════════════════════════════════════════════════════════════════════
# Router integration — general_chat route now includes topic + follow_up
# ═══════════════════════════════════════════════════════════════════════════════

class TestRouterGeneralChat:

    def _route(self, transcript: str = "hello") -> dict:
        from pipeline.router import route
        payload = {
            "intent":     "general_chat",
            "symptoms":   [],
            "severity":   "low",
            "confidence": 0.9,
            "transcript": transcript,
        }
        result = route(payload)
        assert result.success, f"route() failed: {result.error}"
        return result.data

    def test_route_general_chat_succeeds(self):
        from pipeline.router import route
        result = route({
            "intent": "general_chat", "symptoms": [],
            "severity": "low", "confidence": 0.9,
        })
        assert result.success is True

    def test_route_returns_message_key(self):
        data = self._route("hello")
        assert "message" in data
        assert len(data["message"]) > 0

    def test_route_returns_topic_key(self):
        data = self._route("hello there")
        assert "topic" in data

    def test_route_returns_follow_up_key(self):
        data = self._route("help me")
        assert "follow_up" in data

    def test_route_returns_response_type_conversational(self):
        data = self._route()
        assert data["response_type"] == "conversational"

    def test_greeting_transcript_produces_greeting_topic(self):
        data = self._route("Good morning!")
        assert data["topic"] == "greeting"

    def test_farewell_has_empty_follow_up(self):
        data = self._route("Goodbye, take care!")
        assert data["follow_up"] == ""

    def test_unknown_transcript_still_returns_message(self):
        data = self._route("xyzzy frobnicator nonsense")
        assert len(data["message"]) > 0
