"""
rules.py
========
Defines symptom weights, severity bonuses, and risk categories used by the
scoring engine.

Each weight represents the base risk contribution of a detected symptom.
Severity bonuses are additive modifiers applied on top of symptom weights.
Confidence (0.0–1.0) is a multiplier supplied by the LLM to reflect how
certain it is about the extracted symptoms.
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

# ---------------------------------------------------------------------------
# Symptom Categories
# ---------------------------------------------------------------------------
# Maps each symptom to a clinical risk category.
# When multiple symptoms span different categories, the engine picks the
# highest-weighted category as the primary one.
#
# Future categories can be added here without touching scoring logic.

SYMPTOM_CATEGORIES: Dict[str, str] = {
    "chest_pain":         "CARDIAC",
    "unconscious":        "CARDIAC",
    "breathing_problem":  "RESPIRATORY",
    "fall_detected":      "FALL",
    "medicine_missed":    "MEDICATION",
    "stroke_symptoms":    "NEUROLOGICAL",
    "dizziness":          "NEUROLOGICAL",
    "fever":              "GENERAL",
}

# Priority order when resolving multiple categories (highest = most urgent)
CATEGORY_PRIORITY: Dict[str, int] = {
    "CARDIAC":       6,
    "NEUROLOGICAL":  5,
    "RESPIRATORY":   4,
    "FALL":          3,
    "MEDICATION":    2,
    "GENERAL":       1,
    "UNKNOWN":       0,
}

# ---------------------------------------------------------------------------
# NOTE — Future: Repeated-Symptom History Multiplier
# ---------------------------------------------------------------------------
# When a user reports the same symptom on consecutive days, the risk should
# escalate. Suggested logic (not yet implemented):
#
#   day 1 → score = base_score * 1.0
#   day 2 → score = base_score * 1.5
#   day 3 → score = base_score * 2.0
#
# This requires a persistent session store (e.g. Redis or SQLite) keyed on
# user_id + symptom. Tag this with: TODO(history-escalation)

