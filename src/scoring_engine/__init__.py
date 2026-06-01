"""
scoring_engine
==============
Baseline and Scoring Engine for the WellRing Elderly Health Voice Assistant.

Sub-modules:
    rules   — Symptom weights and severity bonuses
    baseline — Risk level thresholds
    scoring  — Score calculation logic
    alerts   — Action determination based on score
"""

from .rules import SYMPTOM_WEIGHTS, SEVERITY_BONUS
from .baseline import RiskLevel, get_risk_level
from .scoring import calculate_score
from .alerts import determine_action

__all__ = [
    "SYMPTOM_WEIGHTS",
    "SEVERITY_BONUS",
    "RiskLevel",
    "get_risk_level",
    "calculate_score",
    "determine_action",
]
