"""
scoring.py
==========
Core scoring logic for the WellRing health risk engine.

Workflow:
    1. Sum the weights of every detected symptom (from rules.SYMPTOM_WEIGHTS).
    2. Add the severity bonus (from rules.SEVERITY_BONUS).
    3. Multiply by confidence (0.0–1.0) supplied by the LLM.
    4. Determine the primary risk category from detected symptoms.
    5. Map the final score to a RiskLevel (from baseline.get_risk_level).
    6. Return a structured result dict ready for FastAPI responses.

Expected input from Kedar's Llama module:
    {
        "intent":     "health_issue",
        "symptoms":   ["chest_pain"],
        "severity":   "high",
        "confidence": 0.95          ← optional, defaults to 1.0
    }
"""

from typing import List, Dict, Any, Optional

from .rules import (
    SYMPTOM_WEIGHTS,
    SEVERITY_BONUS,
    SYMPTOM_CATEGORIES,
    CATEGORY_PRIORITY,
)
from .baseline import RiskLevel, get_risk_level


def _resolve_category(symptoms: List[str]) -> str:
    """
    Return the highest-priority clinical category among detected symptoms.

    Priority order: CARDIAC > NEUROLOGICAL > RESPIRATORY > FALL >
                    MEDICATION > GENERAL > UNKNOWN

    Args:
        symptoms: Recognised symptom keys.

    Returns:
        Category string (e.g. "CARDIAC").
    """
    best_category = "UNKNOWN"
    best_priority = -1

    for symptom in symptoms:
        category = SYMPTOM_CATEGORIES.get(symptom, "UNKNOWN")
        priority = CATEGORY_PRIORITY.get(category, 0)
        if priority > best_priority:
            best_priority = priority
            best_category = category

    return best_category


MAX_HISTORY_MULTIPLIER = 2.0   # cap so a 10-day streak doesn't blow up the score


def calculate_score(
    symptoms:       List[str],
    severity:       str,
    confidence:     float = 1.0,
    history_counts: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    """
    Calculate the health risk score for a given set of symptoms, severity,
    LLM confidence, and optional symptom history.

    Formula:
        For each recognised symptom:
            history_multiplier = min(1.0 + repeat_count * 0.2, 2.0)
            weighted_score    += round(base_weight * history_multiplier)
        base_score  = weighted_symptom_score + severity_bonus
        final_score = round(base_score * confidence)

    Args:
        symptoms:       List of symptom identifiers extracted from speech.
                        Unknown keys are ignored with a warning.
        severity:       Overall severity label — "low" | "medium" | "high" |
                        "critical" (case-insensitive).
        confidence:     LLM prediction confidence [0.0, 1.0]. Defaults to 1.0.
        history_counts: Optional dict mapping symptom key → number of times
                        it was logged in the recent look-back window.
                        Defaults to {} (no history → multiplier = 1.0 for all).

    Returns:
        A dict with the shape::

            {
                "score":      int,        # final score after confidence scaling
                "base_score": int,        # raw score before confidence scaling
                "confidence": float,      # echoed back for traceability
                "risk_level": str,        # LOW / MEDIUM / HIGH / CRITICAL
                "category":   str,        # primary clinical category
                "symptoms":   list[str],  # recognised symptoms only
                "severity":   str,        # normalised severity label
                "breakdown":  list[str],  # human-readable per-component explanation
            }

    Raises:
        ValueError: If severity is not a recognised label.
        ValueError: If confidence is outside [0.0, 1.0].
    """
    if history_counts is None:
        history_counts = {}

    # --- Validate inputs ---
    severity_key = severity.lower().strip()
    if severity_key not in SEVERITY_BONUS:
        raise ValueError(
            f"Unknown severity '{severity}'. Must be one of {list(SEVERITY_BONUS)}."
        )
    if not (0.0 <= confidence <= 1.0):
        raise ValueError(
            f"Confidence must be between 0.0 and 1.0, got {confidence}."
        )

    # --- Step 1: Sum symptom weights with history multiplier ---
    symptom_score: int = 0
    recognised:    List[str] = []
    breakdown:     List[str] = []

    for symptom in symptoms:
        key = symptom.lower().strip()
        if key not in SYMPTOM_WEIGHTS:
            print(f"[scoring] WARNING: Unknown symptom '{symptom}' — ignored.")
            continue

        base_weight  = SYMPTOM_WEIGHTS[key]
        repeat_count = history_counts.get(key, 0)
        multiplier   = min(1.0 + repeat_count * 0.2, MAX_HISTORY_MULTIPLIER)
        contribution = round(base_weight * multiplier)
        symptom_score += contribution
        recognised.append(key)

        if repeat_count > 0:
            breakdown.append(
                f"{key}: +{contribution} (×{multiplier:.1f}, seen {repeat_count}× before)"
            )
        else:
            breakdown.append(f"{key}: +{contribution} (first occurrence)")

    # --- Step 2: Add severity bonus ---
    bonus:      int = SEVERITY_BONUS[severity_key]
    base_score: int = symptom_score + bonus
    if bonus > 0:
        breakdown.append(f"severity:{severity_key} +{bonus}")

    # --- Step 3: Apply confidence multiplier ---
    final_score: int = round(base_score * confidence)
    breakdown.append(f"confidence ×{confidence} → final score: {final_score}")

    # --- Step 4: Determine primary risk category ---
    category: str = _resolve_category(recognised)

    # --- Step 5: Map to risk level ---
    risk_level: RiskLevel = get_risk_level(final_score)

    return {
        "score":      final_score,
        "base_score": base_score,
        "confidence": confidence,
        "risk_level": risk_level.value,
        "category":   category,
        "symptoms":   recognised,
        "severity":   severity_key,
        "breakdown":  breakdown,
    }
