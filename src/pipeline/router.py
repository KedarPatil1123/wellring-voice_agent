"""
router.py
=========
Intent-based request router for the WellRing pipeline.

Receives a *validated* payload from validator.py and dispatches it to
the appropriate downstream handler:

    health_issue  →  scoring_engine.calculate_score  (returns risk result)
    general_chat  →  _handle_general_chat             (returns echo/stub)

Public API:
    route(payload: dict) -> RouteResult
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

# Import the scoring engine that already lives in src/scoring_engine/
import sys
import os

# Ensure src/ is on the path when this module is run directly
_SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from scoring_engine import calculate_score, determine_action  # noqa: E402
from pipeline.conversation import generate_response           # noqa: E402


# ── Result dataclass ─────────────────────────────────────────────────────────

@dataclass
class RouteResult:
    """Outcome of a routing decision.

    Attributes:
        destination:  The handler that was invoked
                      (``"scoring_engine"`` | ``"general_chat"``).
        success:      False if the handler raised an exception.
        data:         The handler's response dict.
        error:        Error message when success is False.
    """

    destination: str
    success: bool = True
    data: Dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def __bool__(self) -> bool:
        return self.success


# ── Private handlers ─────────────────────────────────────────────────────────

def _handle_health_issue(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Forward a health-related payload to the scoring engine.

    Args:
        payload: Normalised and validated Llama output containing
                 ``symptoms``, ``severity``, and ``confidence``.

    Returns:
        The full scoring result dict from :func:`calculate_score` plus
        the recommended escalation action from :func:`determine_action`.
    """
    result = calculate_score(
        symptoms=payload["symptoms"],
        severity=payload["severity"],
        confidence=payload.get("confidence", 1.0),
    )
    result["action"] = determine_action(result["score"])
    return result


def _handle_general_chat(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch a conversational turn to the conversation handler.

    Calls :func:`pipeline.conversation.generate_response` which picks a
    topic-aware reply from a template bank (no extra LLM call required).

    Args:
        payload: Normalised Llama output with ``intent == "general_chat"``.
                 Optionally contains ``transcript`` for topic detection.

    Returns:
        A dict with ``intent``, ``response_type``, ``topic``, ``message``,
        and ``follow_up`` keys.
    """
    result = generate_response(payload)
    return {
        "intent":        payload.get("intent", "general_chat"),
        "response_type": "conversational",
        "topic":         result.topic,
        "message":       result.text,
        "follow_up":     result.follow_up,
    }


# ── Dispatch table ────────────────────────────────────────────────────────────

_HANDLERS = {
    "health_issue": _handle_health_issue,
    "general_chat": _handle_general_chat,
}


# ── Public API ────────────────────────────────────────────────────────────────

def route(payload: Dict[str, Any]) -> RouteResult:
    """Route a validated payload to the correct downstream handler.

    Args:
        payload: A *validated* dict produced by :func:`validator.validate`.
                 Must contain at minimum the ``intent`` key.

    Returns:
        A :class:`RouteResult` with ``destination``, ``success``, and
        ``data`` (or ``error``) populated.
    """
    intent: str = payload.get("intent", "")
    handler = _HANDLERS.get(intent)

    if handler is None:
        return RouteResult(
            destination="unknown",
            success=False,
            error=f"No handler registered for intent '{intent}'.",
        )

    try:
        data = handler(payload)
        return RouteResult(destination=intent, success=True, data=data)
    except Exception as exc:  # noqa: BLE001
        return RouteResult(
            destination=intent,
            success=False,
            error=f"Handler '{intent}' raised an exception: {exc}",
        )
