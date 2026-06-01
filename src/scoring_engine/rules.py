"""
rules.py
========
Defines symptom weights and severity bonuses used by the scoring engine.

Each weight represents the base risk contribution of a detected symptom.
Severity bonuses are additive modifiers applied on top of symptom weights.
"""

from typing import Dict

# ---------------------------------------------------------------------------
# Symptom Weights
# ---------------------------------------------------------------------------
# Each key matches a symptom identifier that Llama3 may extract from speech.
# Values represent how much risk that symptom contributes to the total score.

SYMPTOM_WEIGHTS: Dict[str, int] = {
    "dizziness":          20,
    "fever":              15,
    "medicine_missed":    10,
    "fall_detected":      60,
    "chest_pain":         50,
    "breathing_problem":  40,
    "unconscious":       100,
    "stroke_symptoms":   100,
}

# ---------------------------------------------------------------------------
# Severity Bonus
# ---------------------------------------------------------------------------
# Represents how much extra risk is added based on the overall severity
# reported by the user or inferred by the LLM.

SEVERITY_BONUS: Dict[str, int] = {
    "low":      0,
    "medium":  10,
    "high":    20,
    "critical": 40,
}
