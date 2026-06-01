"""
alerts.py
=========
Determines the appropriate care action based on the calculated risk score.

Action mapping:
    LOW      (0–30)   → monitor
    MEDIUM   (31–60)  → follow_up_questions
    HIGH     (61–100) → notify_caregiver
    CRITICAL (101+)   → notify_caregiver_and_emergency_services
"""

from typing import Dict, Any

from .baseline import RiskLevel, get_risk_level


# ---------------------------------------------------------------------------
# Action constants (easy to extend / localise later)
# ---------------------------------------------------------------------------

ACTION_MONITOR            = "monitor"
ACTION_FOLLOW_UP          = "follow_up_questions"
ACTION_NOTIFY_CAREGIVER   = "notify_caregiver"
ACTION_EMERGENCY          = "notify_caregiver_and_emergency_services"

_ACTION_MAP: Dict[RiskLevel, str] = {
    RiskLevel.LOW:      ACTION_MONITOR,
    RiskLevel.MEDIUM:   ACTION_FOLLOW_UP,
    RiskLevel.HIGH:     ACTION_NOTIFY_CAREGIVER,
    RiskLevel.CRITICAL: ACTION_EMERGENCY,
}

# Human-readable messages paired with each action
_MESSAGE_MAP: Dict[RiskLevel, str] = {
    RiskLevel.LOW: (
        "No immediate concern. Continue monitoring the user."
    ),
    RiskLevel.MEDIUM: (
        "Some symptoms detected. Ask follow-up questions to clarify."
    ),
    RiskLevel.HIGH: (
        "Significant symptoms detected. Notifying the caregiver immediately."
    ),
    RiskLevel.CRITICAL: (
        "CRITICAL condition detected! Alerting caregiver AND emergency services NOW."
    ),
}


def determine_action(score: int) -> Dict[str, Any]:
    """
    Determine the care action and message for a given risk score.

    Args:
        score: The integer risk score returned by ``calculate_score``.

    Returns:
        A dict with the shape::

            {
                "action":     str,   # action identifier
                "risk_level": str,   # one of LOW / MEDIUM / HIGH / CRITICAL
                "score":      int,   # the input score (echo-back)
                "message":    str,   # human-readable description of the action
            }
    """
    level: RiskLevel = get_risk_level(score)
    action: str      = _ACTION_MAP[level]
    message: str     = _MESSAGE_MAP[level]

    return {
        "action":     action,
        "risk_level": level.value,
        "score":      score,
        "message":    message,
    }
