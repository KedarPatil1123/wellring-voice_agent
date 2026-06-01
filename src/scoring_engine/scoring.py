"""
scoring.py
==========
Core scoring logic for the WellRing health risk engine.

Workflow:
    1. Sum the weights of every detected symptom (from rules.SYMPTOM_WEIGHTS).
    2. Add the severity bonus (from rules.SEVERITY_BONUS).
    3. Map the total to a RiskLevel (from baseline.get_risk_level).
    4. Return a structured result dict ready for FastAPI responses.
"""

from typing import List, Dict, Any

from .rules import SYMPTOM_WEIGHTS, SEVERITY_BONUS
from .baseline import RiskLevel, get_risk_level


def calculate_score(
    symptoms: List[str],
    severity: str,
) -> Dict[str, Any]:
    """
    Calculate the health risk score for a given set of symptoms and severity.

    Args:
        symptoms: List of symptom identifiers extracted from the user's speech
                  (e.g. ["chest_pain", "dizziness"]).  Unknown symptom keys
                  are ignored with a warning so the engine stays robust.
        severity: Overall severity label — one of "low", "medium", "high",
                  "critical" (case-insensitive).

    Returns:
        A dict with the shape::

            {
                "score":      int,       # total numeric risk score
                "risk_level": str,       # one of LOW / MEDIUM / HIGH / CRITICAL
                "symptoms":   list[str], # echo back recognised symptoms
                "severity":   str,       # normalised severity label
            }

    Raises:
        ValueError: If `severity` is not a recognised severity label.
    """
    severity_key = severity.lower().strip()

    # Validate severity
    if severity_key not in SEVERITY_BONUS:
        valid = list(SEVERITY_BONUS.keys())
        raise ValueError(
            f"Unknown severity '{severity}'. Must be one of {valid}."
        )

    # --- Step 1: Sum symptom weights ---
    symptom_score: int = 0
    recognised_symptoms: List[str] = []

    for symptom in symptoms:
        key = symptom.lower().strip()
        if key in SYMPTOM_WEIGHTS:
            symptom_score += SYMPTOM_WEIGHTS[key]
            recognised_symptoms.append(key)
        else:
            # Unknown symptom — log and skip rather than crash
            print(f"[scoring] WARNING: Unknown symptom '{symptom}' ignored.")

    # --- Step 2: Add severity bonus ---
    bonus: int = SEVERITY_BONUS[severity_key]
    total_score: int = symptom_score + bonus

    # --- Step 3: Map to risk level ---
    risk_level: RiskLevel = get_risk_level(total_score)

    return {
        "score":      total_score,
        "risk_level": risk_level.value,   # plain string — JSON-serialisable
        "symptoms":   recognised_symptoms,
        "severity":   severity_key,
    }
