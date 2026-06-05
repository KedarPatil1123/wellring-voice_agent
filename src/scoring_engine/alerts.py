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

# If the LLM is less than 40% confident, never escalate — ask first.
LOW_CONFIDENCE_THRESHOLD = 0.4


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


def determine_action(score: int, confidence: float = 1.0) -> Dict[str, Any]:
    """
    Determine the full escalation response for a given risk score.

    If LLM confidence is below LOW_CONFIDENCE_THRESHOLD (0.4), the action is
    always overridden to follow_up_questions regardless of the calculated score.
    This prevents escalating on a very weak or ambiguous signal.

    Args:
        score:      The integer risk score returned by ``calculate_score``.
        confidence: The LLM confidence value [0.0, 1.0]. Defaults to 1.0.

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

    # Low-confidence override: ask clarifying questions instead of acting
    if confidence < LOW_CONFIDENCE_THRESHOLD:
        return {
            "action":     ACTION_FOLLOW_UP,
            "risk_level": level.value,
            "score":      score,
            "message":    (
                f"Low detection confidence ({confidence:.0%}). "
                "Asking follow-up questions before escalating."
            ),
            "steps": [
                "Ask: 'Can you describe your symptoms more clearly?'",
                "Ask: 'How long have you been feeling this way?'",
                "Ask: 'On a scale of 1–10, how severe is it?'",
                "Re-assess after user clarification.",
            ],
        }

    escalation = _ESCALATION[level]
    return {
        "action":     escalation["action"],
        "risk_level": level.value,
        "score":      score,
        "message":    escalation["message"],
        "steps":      escalation["steps"],
    }

