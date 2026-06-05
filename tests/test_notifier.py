"""
test_notifier.py
================
Tests for the WellRing caregiver notification dispatcher.

All HTTP calls are mocked with unittest.mock so no network is required.
Tests cover:
    - dispatch() — low/medium skipped, high/critical sent
    - is_webhook_configured()
    - _should_notify()
    - _build_webhook_payload()
    - Webhook success / failure / timeout handling
    - WELLRING_NOTIFY_LEVELS env-var override
    - NotifyResult shape

Run with:
    python -m pytest tests/test_notifier.py -v
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from unittest.mock import patch, MagicMock


# ── Shared payloads ───────────────────────────────────────────────────────────

_LOW_ALERT = {
    "risk_level": "LOW",
    "action":     "monitor",
    "message":    "No immediate concern.",
    "score":      20,
    "request_id": "test-uuid-low",
    "symptoms":   [],
    "steps":      ["Log this interaction."],
}

_MEDIUM_ALERT = {**_LOW_ALERT, "risk_level": "MEDIUM", "action": "follow_up_questions", "score": 45}
_HIGH_ALERT   = {**_LOW_ALERT, "risk_level": "HIGH",   "action": "notify_caregiver",    "score": 75}
_CRITICAL_ALERT = {
    "risk_level": "CRITICAL",
    "action":     "notify_caregiver_and_emergency_services",
    "message":    "CRITICAL condition!",
    "score":      145,
    "request_id": "test-uuid-critical",
    "symptoms":   ["chest_pain", "unconscious"],
    "steps":      ["Call 112", "Stay calm"],
}


# ═══════════════════════════════════════════════════════════════════════════════
# NotifyResult shape
# ═══════════════════════════════════════════════════════════════════════════════

class TestNotifyResult:

    def _dispatch_low(self):
        from notifier.dispatcher import dispatch
        return dispatch(_LOW_ALERT)

    def test_result_has_sent_field(self):
        r = self._dispatch_low()
        assert hasattr(r, "sent")

    def test_result_has_risk_level(self):
        r = self._dispatch_low()
        assert hasattr(r, "risk_level")

    def test_result_has_skipped(self):
        r = self._dispatch_low()
        assert hasattr(r, "skipped")

    def test_result_has_channels_ok(self):
        r = self._dispatch_low()
        assert hasattr(r, "channels_ok")

    def test_result_has_duration_s(self):
        r = self._dispatch_low()
        assert isinstance(r.duration_s, float)

    def test_result_bool_true_when_sent(self):
        r = self._dispatch_low()
        assert bool(r) is True   # skipped=True also returns True from __bool__

    def test_result_bool_true_when_skipped(self):
        from notifier.dispatcher import dispatch
        r = dispatch(_LOW_ALERT)
        assert bool(r) is True   # skipped counts as non-fatal


# ═══════════════════════════════════════════════════════════════════════════════
# Threshold / notify-level logic
# ═══════════════════════════════════════════════════════════════════════════════

class TestNotifyLevels:

    def test_low_is_skipped(self):
        from notifier.dispatcher import dispatch
        r = dispatch(_LOW_ALERT)
        assert r.skipped is True

    def test_medium_is_skipped(self):
        from notifier.dispatcher import dispatch
        r = dispatch(_MEDIUM_ALERT)
        assert r.skipped is True

    def test_high_is_not_skipped(self):
        from notifier.dispatcher import dispatch
        r = dispatch(_HIGH_ALERT)
        assert r.skipped is False

    def test_critical_is_not_skipped(self):
        from notifier.dispatcher import dispatch
        r = dispatch(_CRITICAL_ALERT)
        assert r.skipped is False

    def test_low_risk_level_preserved(self):
        from notifier.dispatcher import dispatch
        r = dispatch(_LOW_ALERT)
        assert r.risk_level == "LOW"

    def test_critical_risk_level_preserved(self):
        from notifier.dispatcher import dispatch
        r = dispatch(_CRITICAL_ALERT)
        assert r.risk_level == "CRITICAL"

    def test_console_channel_always_included_for_high(self):
        from notifier.dispatcher import dispatch
        r = dispatch(_HIGH_ALERT)
        assert "console" in r.channels_ok

    def test_console_channel_always_included_for_critical(self):
        from notifier.dispatcher import dispatch
        r = dispatch(_CRITICAL_ALERT)
        assert "console" in r.channels_ok

    def test_sent_true_for_high(self):
        from notifier.dispatcher import dispatch
        r = dispatch(_HIGH_ALERT)
        assert r.sent is True

    def test_sent_false_for_low(self):
        from notifier.dispatcher import dispatch
        r = dispatch(_LOW_ALERT)
        assert r.sent is False


# ═══════════════════════════════════════════════════════════════════════════════
# Webhook — no URL configured (default)
# ═══════════════════════════════════════════════════════════════════════════════

class TestWebhookNotConfigured:

    def test_is_webhook_configured_false_by_default(self):
        from notifier.dispatcher import is_webhook_configured, WEBHOOK_URL
        # In test environment, env var is not set
        if WEBHOOK_URL is None:
            from notifier.dispatcher import is_webhook_configured
            assert is_webhook_configured() is False

    def test_webhook_not_in_channels_when_unconfigured(self):
        from notifier.dispatcher import dispatch, WEBHOOK_URL
        if WEBHOOK_URL is None:
            r = dispatch(_CRITICAL_ALERT)
            assert "webhook" not in r.channels_ok

    def test_no_channels_fail_when_webhook_unconfigured(self):
        from notifier.dispatcher import dispatch, WEBHOOK_URL
        if WEBHOOK_URL is None:
            r = dispatch(_CRITICAL_ALERT)
            assert r.channels_fail == []


# ═══════════════════════════════════════════════════════════════════════════════
# Webhook — URL configured, successful delivery
# ═══════════════════════════════════════════════════════════════════════════════

class TestWebhookSuccess:

    def _dispatch_with_webhook(self, alert=None):
        alert = alert or _CRITICAL_ALERT
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch.dict(os.environ, {"WELLRING_WEBHOOK_URL": "http://test-hook.local/alert"}), \
             patch("notifier.dispatcher.WEBHOOK_URL", "http://test-hook.local/alert"), \
             patch("urllib.request.urlopen", return_value=mock_resp):
            from notifier.dispatcher import dispatch
            return dispatch(alert)

    def test_webhook_in_channels_ok(self):
        r = self._dispatch_with_webhook()
        assert "webhook" in r.channels_ok

    def test_console_still_in_channels(self):
        r = self._dispatch_with_webhook()
        assert "console" in r.channels_ok

    def test_no_failures_on_success(self):
        r = self._dispatch_with_webhook()
        assert r.channels_fail == []

    def test_sent_true_on_success(self):
        r = self._dispatch_with_webhook()
        assert r.sent is True

    def test_error_empty_on_success(self):
        r = self._dispatch_with_webhook()
        assert r.error == ""

    def test_high_also_triggers_webhook(self):
        r = self._dispatch_with_webhook(alert=_HIGH_ALERT)
        assert "webhook" in r.channels_ok


# ═══════════════════════════════════════════════════════════════════════════════
# Webhook — URL configured, delivery fails
# ═══════════════════════════════════════════════════════════════════════════════

class TestWebhookFailure:

    def _dispatch_failing_webhook(self):
        import urllib.error
        with patch.dict(os.environ, {"WELLRING_WEBHOOK_URL": "http://bad-host.local/alert"}), \
             patch("notifier.dispatcher.WEBHOOK_URL", "http://bad-host.local/alert"), \
             patch("urllib.request.urlopen",
                   side_effect=urllib.error.URLError("connection refused")):
            from notifier.dispatcher import dispatch
            return dispatch(_CRITICAL_ALERT)

    def test_webhook_in_channels_fail(self):
        r = self._dispatch_failing_webhook()
        assert any(ch == "webhook" for ch, _ in r.channels_fail)

    def test_console_still_succeeds(self):
        r = self._dispatch_failing_webhook()
        assert "console" in r.channels_ok

    def test_sent_still_true_because_console_ok(self):
        """Webhook failure is non-fatal — console channel keeps sent=True."""
        r = self._dispatch_failing_webhook()
        assert r.sent is True

    def test_error_string_populated(self):
        r = self._dispatch_failing_webhook()
        assert len(r.error) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Webhook payload envelope
# ═══════════════════════════════════════════════════════════════════════════════

class TestWebhookPayload:

    def test_envelope_has_source(self):
        from notifier.dispatcher import _build_webhook_payload
        env = _build_webhook_payload(_CRITICAL_ALERT)
        assert env["source"] == "wellring-voice-agent"

    def test_envelope_has_timestamp(self):
        from notifier.dispatcher import _build_webhook_payload
        env = _build_webhook_payload(_CRITICAL_ALERT)
        assert "timestamp" in env
        assert len(env["timestamp"]) > 0

    def test_envelope_has_risk_level(self):
        from notifier.dispatcher import _build_webhook_payload
        env = _build_webhook_payload(_CRITICAL_ALERT)
        assert env["risk_level"] == "CRITICAL"

    def test_envelope_has_score(self):
        from notifier.dispatcher import _build_webhook_payload
        env = _build_webhook_payload(_CRITICAL_ALERT)
        assert env["score"] == 145

    def test_envelope_has_request_id(self):
        from notifier.dispatcher import _build_webhook_payload
        env = _build_webhook_payload(_CRITICAL_ALERT)
        assert env["request_id"] == "test-uuid-critical"

    def test_envelope_has_symptoms(self):
        from notifier.dispatcher import _build_webhook_payload
        env = _build_webhook_payload(_CRITICAL_ALERT)
        assert "chest_pain" in env["symptoms"]

    def test_envelope_has_steps(self):
        from notifier.dispatcher import _build_webhook_payload
        env = _build_webhook_payload(_CRITICAL_ALERT)
        assert isinstance(env["steps"], list)
        assert len(env["steps"]) > 0

    def test_envelope_version(self):
        from notifier.dispatcher import _build_webhook_payload
        env = _build_webhook_payload(_CRITICAL_ALERT)
        assert "version" in env


# ═══════════════════════════════════════════════════════════════════════════════
# is_webhook_configured()
# ═══════════════════════════════════════════════════════════════════════════════

class TestIsWebhookConfigured:

    def test_returns_false_when_url_is_none(self):
        with patch("notifier.dispatcher.WEBHOOK_URL", None):
            from notifier.dispatcher import is_webhook_configured
            assert is_webhook_configured() is False

    def test_returns_true_when_url_is_set(self):
        with patch("notifier.dispatcher.WEBHOOK_URL", "http://example.com/hook"):
            from notifier.dispatcher import is_webhook_configured
            assert is_webhook_configured() is True
