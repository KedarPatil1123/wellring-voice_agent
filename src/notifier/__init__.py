"""
notifier
========
Caregiver alert dispatcher for the WellRing voice agent.

Delivers HIGH/CRITICAL risk notifications to registered caregivers via:
    - Webhook  (WELLRING_WEBHOOK_URL env var)
    - Console  (always — structured log line)

Quick usage:
    from notifier import dispatch, NotifyResult

    result = dispatch({
        "risk_level": "CRITICAL",
        "action":     "notify_caregiver_and_emergency_services",
        "message":    "CRITICAL condition! ...",
        "score":      145,
        "request_id": "uuid-...",
        "symptoms":   ["chest_pain", "unconscious"],
        "steps":      ["Call 112", ...],
    })
    if result.sent:
        print("Caregiver notified via:", result.channels_ok)
"""

from .dispatcher import dispatch, NotifyResult, is_webhook_configured, NOTIFY_LEVELS

__all__ = [
    "dispatch",
    "NotifyResult",
    "is_webhook_configured",
    "NOTIFY_LEVELS",
]
