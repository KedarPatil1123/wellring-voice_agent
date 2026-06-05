"""
client.py
=========
Ollama / Llama client for the WellRing triage layer.

Wraps ``ollama.chat()`` with:
  - Structured prompt injection (from prompt.py)
  - JSON response parsing + repair (from parser.py)
  - Retry logic with exponential back-off for transient failures
  - A fallback payload when Llama is unreachable or returns garbage

Public API:
    classify(transcript: str) -> ClassifyResult
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import ollama

from .prompt import build_messages
from .parser import parse, ParseResult

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL_NAME: str = "llama3"         # Ollama model tag
MAX_RETRIES: int = 3               # Attempts before giving up
RETRY_DELAY: float = 1.0           # Base seconds between retries (doubles each time)
REQUEST_TIMEOUT: int = 30          # Seconds to wait for Ollama response

_log = logging.getLogger("wellring.llama")

# ---------------------------------------------------------------------------
# Fallback payload  (used when Llama is down or returns unparseable output)
# ---------------------------------------------------------------------------

_FALLBACK_PAYLOAD: Dict[str, Any] = {
    "intent":     "health_issue",
    "symptoms":   [],
    "severity":   "low",
    "confidence": 0.0,          # 0.0 confidence signals "do not trust this"
}


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ClassifyResult:
    """Outcome of a single transcript classification attempt.

    Attributes:
        success:     True when Llama responded and was parsed correctly.
        payload:     The structured classification dict, ready for the pipeline.
        is_fallback: True when the fallback payload was used.
        attempts:    Number of Ollama calls made.
        parse_raw:   The raw Llama text (for debugging).
        error:       Error description when success is False.
    """
    success: bool
    payload: Dict[str, Any] = field(default_factory=dict)
    is_fallback: bool = False
    attempts: int = 0
    parse_raw: str = ""
    error: str = ""

    def __bool__(self) -> bool:
        return self.success


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _call_ollama(messages: list[dict]) -> str:
    """Make a single blocking call to Ollama and return the message content.

    Args:
        messages: Ollama-compatible messages list.

    Returns:
        The assistant's reply as a plain string.

    Raises:
        Exception: Any network or Ollama error propagates up to the caller.
    """
    response = ollama.chat(
        model=MODEL_NAME,
        messages=messages,
        options={"temperature": 0},   # deterministic JSON output
    )
    # Ollama SDK ≥ 0.3 returns a ChatResponse object; older versions return a dict
    if hasattr(response, "message"):
        return response.message.content
    return response["message"]["content"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify(transcript: str) -> ClassifyResult:
    """Send a Whisper transcript to Llama and return a structured classification.

    Retry logic:
        Up to MAX_RETRIES attempts. Between attempts, waits
        RETRY_DELAY * 2^(attempt - 1) seconds (exponential back-off).

    Fallback:
        If all attempts fail, returns a safe fallback payload with
        confidence = 0.0 so the downstream scorer treats it conservatively.

    Args:
        transcript: The raw text from Whisper (will be stripped).

    Returns:
        A :class:`ClassifyResult` with ``success``, ``payload``, and
        diagnostic fields.
    """
    transcript = transcript.strip()
    if not transcript:
        _log.warning("classify() called with empty transcript — returning fallback.")
        return ClassifyResult(
            success=False,
            payload=_FALLBACK_PAYLOAD.copy(),
            is_fallback=True,
            error="Empty transcript provided.",
        )

    messages = build_messages(transcript)
    last_error: str = ""
    last_raw: str = ""

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            _log.info("Llama call attempt %d/%d …", attempt, MAX_RETRIES)
            raw_text = _call_ollama(messages)
            last_raw = raw_text

            result: ParseResult = parse(raw_text)

            if result.success:
                _log.info(
                    "Llama classified → intent=%s  severity=%s  confidence=%s",
                    result.payload.get("intent"),
                    result.payload.get("severity"),
                    result.payload.get("confidence"),
                )
                return ClassifyResult(
                    success=True,
                    payload=result.payload,
                    attempts=attempt,
                    parse_raw=raw_text,
                )

            # Parse failed — retry
            last_error = result.error
            _log.warning("Parse failed on attempt %d: %s", attempt, last_error)

        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            _log.warning("Ollama error on attempt %d: %s", attempt, last_error)

        # Exponential back-off before next attempt
        if attempt < MAX_RETRIES:
            wait = RETRY_DELAY * (2 ** (attempt - 1))
            _log.info("Retrying in %.1f s …", wait)
            time.sleep(wait)

    # All attempts exhausted — use fallback
    _log.error(
        "All %d Llama attempts failed. Using fallback payload. Last error: %s",
        MAX_RETRIES, last_error,
    )
    return ClassifyResult(
        success=False,
        payload=_FALLBACK_PAYLOAD.copy(),
        is_fallback=True,
        attempts=MAX_RETRIES,
        parse_raw=last_raw,
        error=last_error,
    )
