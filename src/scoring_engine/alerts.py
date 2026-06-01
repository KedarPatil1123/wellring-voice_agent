"""
alerts.py
=========
Determines the appropriate care action and escalation steps based on the
calculated risk score.

Escalation ladder:
    LOW      (0–30)   → monitor
    MEDIUM   (31–60)  → follow_up_questions
    HIGH     (61–100) → notify_caregiver
    CRITICAL (101+)   → notify_caregiver_and_emergency_services
"""

from typing import Dict, Any, List

from .baseline import RiskLevel, get_risk_level


# ---------------------------------------------------------------------------
# Action identifiers — use these constants throughout the codebase so that
# FastAPI endpoints and frontend clients never depend on raw strings.
# ---------------------------------------------------------------------------

ACTION_MONITOR          = "monitor"
ACTION_FOLLOW_UP        = "follow_up_questions"
ACTION_NOTIFY_CAREGIVER = "notify_caregiver"
ACTION_EMERGENCY        = "notify_caregiver_and_emergency_services"


# ---------------------------------------------------------------------------
# Escalation definitions per risk level
# ---------------------------------------------------------------------------

_ESCALATION: Dict[RiskLevel, Dict[str, Any]] = {
    RiskLevel.LOW: {
        "action":      ACTION_MONITOR,
        "message":     "No immediate concern. Continue monitoring the user.",
        "steps": [
            "Log this interaction.",
            "Re-check with the user in 4 hours.",
            "No caregiver notification required.",
        ],
    },
    RiskLevel.MEDIUM: {
        "action":      ACTION_FOLLOW_UP,
        "message":     "Some symptoms detected. Ask follow-up questions to clarify.",
        "steps": [
            "Ask: 'How long have you had this symptom?'",
            "Ask: 'On a scale of 1–10, how bad does it feel?'",
            "Ask: 'Did you take all your medicines today?'",
            "Re-evaluate score after answers.",
        ],
    },
    RiskLevel.HIGH: {
        "action":      ACTION_NOTIFY_CAREGIVER,
        "message":     "Significant symptoms detected. Notifying the caregiver immediately.",
        "steps": [
            "Send alert to registered caregiver.",   # hook: caregiver_contact_id
            "Ask user to sit down and stay calm.",
            "Monitor every 30 minutes.",
            "Escalate to CRITICAL if symptoms worsen.",
        ],
    },
    RiskLevel.CRITICAL: {
        "action":      ACTION_EMERGENCY,
        "message":     "CRITICAL condition! Alerting caregiver AND emergency services NOW.",
        "steps": [
            "Call emergency services immediately (112 / local emergency number).",
            "Notify registered caregiver via SMS and push notification.",
            "Keep the user calm and on the line.",
            "Do NOT let the user move unless instructed by emergency services.",
            "Log this event with timestamp for medical handover.",
        ],
    },
}


def determine_action(score: int) -> Dict[str, Any]:
    """
    Determine the full escalation response for a given risk score.

    Args:
        score: The integer risk score returned by ``calculate_score``.

    Returns:
        A dict with the shape::

            {
                "action":     str,        # action identifier constant
                "risk_level": str,        # LOW / MEDIUM / HIGH / CRITICAL
                "score":      int,        # echoed input score
                "message":    str,        # human-readable summary
                "steps":      list[str],  # ordered escalation steps
            }
    """
    level: RiskLevel = get_risk_level(score)
    escalation       = _ESCALATION[level]

    return {
        "action":     escalation["action"],
        "risk_level": level.value,
        "score":      score,
        "message":    escalation["message"],
        "steps":      escalation["steps"],
    }

