"""
baseline.py
===========
Defines risk level thresholds and the logic to map a numeric score
to a named RiskLevel.

Risk bands:
    LOW      : 0  – 30
    MEDIUM   : 31 – 60
    HIGH     : 61 – 100
    CRITICAL : 101+
"""

from enum import Enum


# ---------------------------------------------------------------------------
# Risk Level Enum
# ---------------------------------------------------------------------------

class RiskLevel(str, Enum):
    LOW      = "LOW"
    MEDIUM   = "MEDIUM"
    HIGH     = "HIGH"
    CRITICAL = "CRITICAL"


# ---------------------------------------------------------------------------
# Thresholds (inclusive lower bound)
# ---------------------------------------------------------------------------

_THRESHOLDS = [
    (101, RiskLevel.CRITICAL),
    (61,  RiskLevel.HIGH),
    (31,  RiskLevel.MEDIUM),
    (0,   RiskLevel.LOW),
]


def get_risk_level(score: int) -> RiskLevel:
    """
    Map a numeric risk score to a RiskLevel.

    Args:
        score: The calculated integer risk score.

    Returns:
        The appropriate RiskLevel for that score.
    """
    for threshold, level in _THRESHOLDS:
        if score >= threshold:
            return level
    return RiskLevel.LOW
