"""
validator.py
============
Input validation for the WellRing pipeline.

Validates the structured JSON produced by the Llama module before it
is forwarded to the scoring engine or the general-chat handler.

Expected input shape (from Llama):
    {
        "intent":     "health_issue" | "general_chat",
        "symptoms":   ["chest_pain", "dizziness"],   # list, may be empty
        "severity":   "low" | "medium" | "high" | "critical",
        "confidence": 0.95,                          # float, 0.0 – 1.0
        "transcript": "I have chest pain..."         # optional pass-through
    }

Public API:
    validate(payload: dict) -> ValidationResult
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

# ── Constants ────────────────────────────────────────────────────────────────

VALID_INTENTS: frozenset[str] = frozenset({"health_issue", "general_chat"})

VALID_SEVERITIES: frozenset[str] = frozenset({"low", "medium", "high", "critical"})


# ── Result dataclass ─────────────────────────────────────────────────────────

@dataclass
class ValidationResult:
    """Outcome of a single validation pass.

    Attributes:
        is_valid:  True when every required field passes its check.
        errors:    Human-readable list of validation failures.
        payload:   The normalised payload (fields lower-cased / stripped).
                   Only populated when is_valid is True.
    """

    is_valid: bool
    errors: List[str] = field(default_factory=list)
    payload: Dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:  # lets callers write ``if result:``
        return self.is_valid


# ── Core validation logic ─────────────────────────────────────────────────────

def validate(payload: Dict[str, Any]) -> ValidationResult:
    """Validate a structured Llama output dict.

    Checks performed (in order):
        1. ``intent``     — present and one of VALID_INTENTS.
        2. ``severity``   — present and one of VALID_SEVERITIES.
        3. ``symptoms``   — present and a non-None list (may be empty).
        4. ``confidence`` — present and a float in [0.0, 1.0].
        5. ``transcript`` — optional; copied verbatim into the normalised
                            payload so downstream handlers (e.g. the
                            conversation router) can detect the topic.

    Fields are normalised (stripped / lower-cased) before comparison so
    minor formatting differences from the LLM are tolerated.

    Args:
        payload: Raw dict from the Llama / FastAPI layer.

    Returns:
        A :class:`ValidationResult` with is_valid, errors, and the
        normalised payload (including ``transcript`` when provided).
    """
    errors: List[str] = []
    clean: Dict[str, Any] = {}

    # ── 1. intent ────────────────────────────────────────────────────────────
    raw_intent = payload.get("intent")
    if raw_intent is None:
        errors.append("Missing required field: 'intent'.")
    else:
        intent = str(raw_intent).lower().strip()
        if intent not in VALID_INTENTS:
            errors.append(
                f"Invalid intent '{raw_intent}'. "
                f"Must be one of: {sorted(VALID_INTENTS)}."
            )
        else:
            clean["intent"] = intent

    # ── 2. severity ──────────────────────────────────────────────────────────
    raw_severity = payload.get("severity")
    if raw_severity is None:
        errors.append("Missing required field: 'severity'.")
    else:
        severity = str(raw_severity).lower().strip()
        if severity not in VALID_SEVERITIES:
            errors.append(
                f"Invalid severity '{raw_severity}'. "
                f"Must be one of: {sorted(VALID_SEVERITIES)}."
            )
        else:
            clean["severity"] = severity

    # ── 3. symptoms ──────────────────────────────────────────────────────────
    raw_symptoms = payload.get("symptoms")
    if raw_symptoms is None:
        errors.append("Missing required field: 'symptoms' (use [] for none).")
    elif not isinstance(raw_symptoms, list):
        errors.append(
            f"Field 'symptoms' must be a list, got {type(raw_symptoms).__name__}."
        )
    else:
        clean["symptoms"] = [str(s).lower().strip() for s in raw_symptoms]

    # ── 4. confidence ────────────────────────────────────────────────────────
    raw_confidence = payload.get("confidence")
    if raw_confidence is None:
        errors.append("Missing required field: 'confidence'.")
    else:
        try:
            confidence = float(raw_confidence)
        except (TypeError, ValueError):
            errors.append(
                f"Field 'confidence' must be a number, got '{raw_confidence}'."
            )
            confidence = None  # type: ignore[assignment]

        if confidence is not None:
            if not (0.0 <= confidence <= 1.0):
                errors.append(
                    f"Field 'confidence' must be between 0.0 and 1.0, got {confidence}."
                )
            else:
                clean["confidence"] = confidence

    # ── 5. transcript (optional, pass-through) ───────────────────────────────
    # Not validated — simply forwarded so downstream handlers (e.g. the
    # general-chat conversation handler) can detect the topic from the raw
    # Whisper text without requiring a separate field in the route payload.
    raw_transcript = payload.get("transcript")
    if raw_transcript is not None:
        clean["transcript"] = str(raw_transcript)

    is_valid = len(errors) == 0
    return ValidationResult(is_valid=is_valid, errors=errors, payload=clean)
