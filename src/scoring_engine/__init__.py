"""
scoring_engine
==============
Baseline and Scoring Engine for the WellRing Elderly Health Voice Assistant.

Sub-modules:
    rules    — Symptom weights, severity bonuses, and risk categories
    baseline — Risk level thresholds and RiskLevel enum
    scoring  — Score calculation with confidence multiplier and categorisation
    alerts   — Escalation action determination based on score
"""

from .rules import SYMPTOM_WEIGHTS, SEVERITY_BONUS, SYMPTOM_CATEGORIES, CATEGORY_PRIORITY
from .baseline import RiskLevel, get_risk_level
from .scoring import calculate_score
from .alerts import determine_action

__all__ = [
    # rules
    "SYMPTOM_WEIGHTS",
    "SEVERITY_BONUS",
    "SYMPTOM_CATEGORIES",
    "CATEGORY_PRIORITY",
    # baseline
    "RiskLevel",
    "get_risk_level",
    # scoring
    "calculate_score",
    # alerts
    "determine_action",
]
