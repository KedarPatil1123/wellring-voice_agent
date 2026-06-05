"""
notifier
========
Caregiver alert dispatcher for the WellRing voice agent.

When the scoring engine produces a HIGH or CRITICAL risk level, this
module delivers an out-of-band notification to the registered caregiver.

Supported delivery channels (configured via environment variables):
    Webhook   — HTTP POST JSON payload to WELLRING_WEBHOOK_URL
    Console   — always on (structured log line, useful in development)

Architecture:
    dispatch(alert_payload)
        → _should_notify(risk_level)   ← LOW/MEDIUM silently skipped
        → _send_webhook(payload)       ← if WELLRING_WEBHOOK_URL is set
        → _log_alert(payload)          ← always

Environment variables:
    WELLRING_WEBHOOK_URL     URL to POST alert payloads to.
                             If unset, webhook delivery is skipped.
    WELLRING_WEBHOOK_TIMEOUT Seconds to wait for webhook response (default 5).
    WELLRING_NOTIFY_LEVELS   Comma-separated risk levels that trigger a
                             notification (default: HIGH,CRITICAL).

Public API:
    dispatch(alert_payload: dict) -> NotifyResult
    is_webhook_configured()       -> bool
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Configuration  (all overridable via environment variables)
# ---------------------------------------------------------------------------

WEBHOOK_URL: Optional[str] = os.environ.get("WELLRING_WEBHOOK_URL", "").strip() or None
WEBHOOK_TIMEOUT: int       = int(os.environ.get("WELLRING_WEBHOOK_TIMEOUT", "5"))

_DEFAULT_NOTIFY_LEVELS = {"HIGH", "CRITICAL"}
_raw_levels = os.environ.get("WELLRING_NOTIFY_LEVELS", "")
NOTIFY_LEVELS: frozenset[str] = (
    frozenset(lvl.strip().upper() for lvl in _raw_levels.split(",") if lvl.strip())
    if _raw_levels
    else frozenset(_DEFAULT_NOTIFY_LEVELS)
)

_log = logging.getLogger("wellring.notifier")


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class NotifyResult:
    """Outcome of a single caregiver notification attempt.

    Attributes:
        sent:          True when at least one channel delivered successfully.
        risk_level:    The risk level that triggered the notification.
        channels_ok:   List of channel names that succeeded.
        channels_fail: List of (channel, error) tuples for failures.
        skipped:       True when the risk level is below the notify threshold.
        duration_s:    Total time taken to dispatch all channels.
        error:         Summary error string when sent is False.
    """
    sent:          bool
    risk_level:    str                       = ""
    channels_ok:   List[str]                 = field(default_factory=list)
    channels_fail: List[tuple]               = field(default_factory=list)
    skipped:       bool                      = False
    duration_s:    float                     = 0.0
    error:         str                       = ""

    def __bool__(self) -> bool:
        return self.sent or self.skipped


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _should_notify(risk_level: str) -> bool:
    """Return True when the risk level warrants a caregiver notification."""
    return risk_level.upper() in NOTIFY_LEVELS


def _build_webhook_payload(alert: Dict[str, Any]) -> Dict[str, Any]:
    """Wrap the alert payload in a standard WellRing notification envelope."""
    return {
        "source":       "wellring-voice-agent",
        "version":      "1.1.0",
        "timestamp":    time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "risk_level":   alert.get("risk_level", "UNKNOWN"),
        "action":       alert.get("action", ""),
        "message":      alert.get("message", ""),
        "score":        alert.get("score", 0),
        "request_id":   alert.get("request_id", ""),
        "symptoms":     alert.get("symptoms", []),
        "steps":        alert.get("steps", []),
    }


def _send_webhook(payload: Dict[str, Any]) -> None:
    """POST the alert payload to WELLRING_WEBHOOK_URL.

    Args:
        payload: The notification envelope dict.

    Raises:
        RuntimeError: If the HTTP request fails or returns a non-2xx status.
    """
    import urllib.request
    import urllib.error

    body = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(
        url=WEBHOOK_URL,   # type: ignore[arg-type]
        data=body,
        headers={
            "Content-Type":  "application/json",
            "User-Agent":    "WellRing-VoiceAgent/1.1.0",
            "X-Risk-Level":  payload.get("risk_level", ""),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=WEBHOOK_TIMEOUT) as resp:
            status = resp.status
            if not (200 <= status < 300):
                raise RuntimeError(
                    f"Webhook returned non-2xx status: {status}"
                )
            _log.info("Webhook delivered → %s  status=%d", WEBHOOK_URL, status)
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Webhook URL error: {exc.reason}") from exc


def _log_alert(payload: Dict[str, Any], skipped: bool = False) -> None:
    """Emit a structured log line for every notification attempt."""
    if skipped:
        _log.info(
            "Notification skipped (risk=%s below threshold=%s)",
            payload.get("risk_level"), sorted(NOTIFY_LEVELS),
        )
    else:
        _log.warning(
            "CAREGIVER ALERT | risk=%s | score=%s | action=%s | request_id=%s",
            payload.get("risk_level"),
            payload.get("score"),
            payload.get("action"),
            payload.get("request_id"),
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_webhook_configured() -> bool:
    """Return True when a webhook URL has been configured."""
    return WEBHOOK_URL is not None


def dispatch(alert_payload: Dict[str, Any]) -> NotifyResult:
    """Dispatch a caregiver alert for the given scoring-engine output.

    The alert is only sent when the risk level is in :data:`NOTIFY_LEVELS`
    (default: HIGH and CRITICAL).  LOW and MEDIUM are silently skipped.

    Channels attempted (in order):
        1. Webhook  — only if WELLRING_WEBHOOK_URL is configured
        2. Console  — structured log line, always

    Args:
        alert_payload: The dict returned by
                       :func:`scoring_engine.alerts.determine_action`,
                       optionally enriched with ``request_id`` and
                       ``symptoms`` from the pipeline.

    Returns:
        A :class:`NotifyResult` describing which channels succeeded.
    """
    t0         = time.time()
    risk_level = str(alert_payload.get("risk_level", "")).upper()

    # ── Guard: below notify threshold ────────────────────────────────────────
    if not _should_notify(risk_level):
        _log_alert(alert_payload, skipped=True)
        return NotifyResult(
            sent=False,
            risk_level=risk_level,
            skipped=True,
            duration_s=round(time.time() - t0, 3),
        )

    envelope    = _build_webhook_payload(alert_payload)
    channels_ok: List[str]   = []
    channels_fail: List[tuple] = []

    # ── Channel 1: Webhook ────────────────────────────────────────────────────
    if WEBHOOK_URL:
        try:
            _send_webhook(envelope)
            channels_ok.append("webhook")
        except Exception as exc:  # noqa: BLE001
            channels_fail.append(("webhook", str(exc)))
            _log.error("Webhook delivery failed: %s", exc)
    else:
        _log.debug("Webhook channel skipped — WELLRING_WEBHOOK_URL not set.")

    # ── Channel 2: Console log (always) ──────────────────────────────────────
    _log_alert(envelope)
    channels_ok.append("console")

    duration = round(time.time() - t0, 3)
    sent     = len(channels_ok) > 0

    error = ""
    if channels_fail:
        error = "; ".join(f"{ch}: {err}" for ch, err in channels_fail)

    return NotifyResult(
        sent=sent,
        risk_level=risk_level,
        channels_ok=channels_ok,
        channels_fail=channels_fail,
        skipped=False,
        duration_s=duration,
        error=error,
    )
