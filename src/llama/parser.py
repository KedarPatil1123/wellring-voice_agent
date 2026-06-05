"""
parser.py
=========
Parses the raw text response from Llama into a clean, validated dict.

Llama sometimes wraps its JSON in markdown fences, adds commentary before
the brace, or omits optional fields. This module defensively extracts and
repairs whatever it gets before handing it to the pipeline validator.

Public API:
    parse(raw_text: str) -> ParseResult
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .prompt import KNOWN_SYMPTOMS

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ParseResult:
    """Outcome of parsing a raw Llama response.

    Attributes:
        success:  True if a usable dict was extracted.
        payload:  The extracted (and repaired) dict.
        raw:      The original raw text for debugging.
        error:    Description of any parse failure.
    """
    success: bool
    payload: Dict[str, Any] = field(default_factory=dict)
    raw: str = ""
    error: str = ""

    def __bool__(self) -> bool:
        return self.success


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Regex that finds the first {...} block in the text (handles nested braces)
_JSON_BLOCK_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)

_VALID_INTENTS   = {"health_issue", "general_chat"}
_VALID_SEVERITIES = {"low", "medium", "high", "critical"}


def _extract_json_str(text: str) -> Optional[str]:
    """Pull the first JSON object out of arbitrary text.

    Strategy (in order):
        1. Strip markdown code fences and try the whole string.
        2. Regex-search for the first ``{...}`` block.

    Args:
        text: Raw Llama output string.

    Returns:
        A JSON string candidate, or None if nothing found.
    """
    # Strip ```json ... ``` or ``` ... ``` fences
    cleaned = re.sub(r"```(?:json)?", "", text).strip()

    # Try the cleaned text directly first
    try:
        json.loads(cleaned)
        return cleaned
    except (json.JSONDecodeError, ValueError):
        pass

    # Fall back to regex extraction
    match = _JSON_BLOCK_RE.search(cleaned)
    return match.group(0) if match else None


def _repair(data: Dict[str, Any]) -> Dict[str, Any]:
    """Apply light repairs to the extracted dict.

    Repairs applied:
        - Lowercase + strip ``intent`` and ``severity``.
        - Filter ``symptoms`` to only KNOWN_SYMPTOMS keys.
        - Clamp ``confidence`` to [0.0, 1.0].
        - Insert safe defaults for any missing field.

    Args:
        data: Parsed JSON dict from Llama.

    Returns:
        Repaired dict.
    """
    out: Dict[str, Any] = {}

    # intent
    intent = str(data.get("intent", "general_chat")).lower().strip()
    out["intent"] = intent if intent in _VALID_INTENTS else "general_chat"

    # severity
    severity = str(data.get("severity", "low")).lower().strip()
    out["severity"] = severity if severity in _VALID_SEVERITIES else "low"

    # symptoms — filter to known keys only, silently drop unknown
    raw_symptoms = data.get("symptoms", [])
    if not isinstance(raw_symptoms, list):
        raw_symptoms = []
    out["symptoms"] = [
        s.lower().strip()
        for s in raw_symptoms
        if isinstance(s, str) and s.lower().strip() in KNOWN_SYMPTOMS
    ]

    # confidence
    try:
        conf = float(data.get("confidence", 1.0))
        out["confidence"] = max(0.0, min(1.0, conf))
    except (TypeError, ValueError):
        out["confidence"] = 1.0

    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse(raw_text: str) -> ParseResult:
    """Extract and repair the Llama JSON response.

    Args:
        raw_text: The raw string returned by Ollama / Llama.

    Returns:
        A :class:`ParseResult` with ``success``, ``payload``, ``raw``,
        and ``error``.
    """
    if not raw_text or not raw_text.strip():
        return ParseResult(
            success=False,
            raw=raw_text,
            error="Llama returned an empty response.",
        )

    json_str = _extract_json_str(raw_text)
    if json_str is None:
        return ParseResult(
            success=False,
            raw=raw_text,
            error="No JSON object found in Llama response.",
        )

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        return ParseResult(
            success=False,
            raw=raw_text,
            error=f"JSON decode error: {exc}",
        )

    if not isinstance(data, dict):
        return ParseResult(
            success=False,
            raw=raw_text,
            error=f"Expected a JSON object, got {type(data).__name__}.",
        )

    repaired = _repair(data)

    return ParseResult(success=True, payload=repaired, raw=raw_text)
