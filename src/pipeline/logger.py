"""
logger.py
=========
Request metadata logger for the WellRing pipeline.

Writes a structured log entry for every request that passes through the
pipeline so that requests can be audited, replayed, or analysed later.

Log format  — one JSON line per request written to:
    logs/pipeline.log          (default, relative to project root)

Each entry contains:
    timestamp   ISO-8601 UTC timestamp
    request_id  UUID4 string for correlation
    intent      The routed intent (health_issue | general_chat | unknown)
    severity    Severity label from the payload
    confidence  LLM confidence score
    symptoms    List of recognised symptoms
    route_ok    True when routing succeeded
    risk_level  Risk level from the scoring engine (health_issue only)
    action      Recommended action (health_issue only)
    errors      Any validation or routing error messages

Public API:
    log_request(payload, route_result, validation_result) -> str
        Returns the request_id for downstream correlation.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Optional imports – validator / router types are used for type hints only
try:
    from .validator import ValidationResult
    from .router import RouteResult
except ImportError:  # allow running standalone
    ValidationResult = Any  # type: ignore[assignment,misc]
    RouteResult = Any  # type: ignore[assignment,misc]

import sys
_SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)
from repository import save_assessment


# ── Configuration ─────────────────────────────────────────────────────────────

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_LOG_DIR  = os.path.join(_PROJECT_ROOT, "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "pipeline.log")

# Public alias used by GET /status to check log writability
LOG_PATH: str = _LOG_FILE


def _ensure_log_dir() -> None:
    """Create the logs/ directory if it does not already exist."""
    os.makedirs(_LOG_DIR, exist_ok=True)


# ── Standard Python logger (console output) ───────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
_log = logging.getLogger("wellring.pipeline")


# ── Public API ────────────────────────────────────────────────────────────────

def log_request(
    payload: Dict[str, Any],
    route_result: Optional[Any] = None,
    validation_result: Optional[Any] = None,
) -> str:
    """Write a structured JSON log entry for a single pipeline request.

    Args:
        payload:           The *original* (pre-normalisation) dict received
                           from FastAPI / Llama. Only safe scalar fields are
                           extracted — the full dict is never stored.
        route_result:      The :class:`RouteResult` returned by the router,
                           or ``None`` if routing was skipped (e.g. validation
                           failed).
        validation_result: The :class:`ValidationResult` from the validator,
                           or ``None`` if validation was skipped.

    Returns:
        The ``request_id`` (UUID4 string) assigned to this log entry.
        Callers can attach this ID to their FastAPI response for tracing.
    """
    _ensure_log_dir()

    request_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    # ── Build the log entry ───────────────────────────────────────────────────
    entry: Dict[str, Any] = {
        "timestamp": timestamp,
        "request_id": request_id,
        # Fields extracted directly from the raw payload
        "intent": payload.get("intent", "unknown"),
        "severity": payload.get("severity", "unknown"),
        "confidence": payload.get("confidence", None),
        "symptoms": payload.get("symptoms", []),
        # Validation outcome
        "validation_ok": (
            bool(validation_result.is_valid)
            if validation_result is not None
            else None
        ),
        "validation_errors": (
            list(validation_result.errors)
            if validation_result is not None
            else []
        ),
        # Routing outcome
        "route_ok": (
            bool(route_result.success)
            if route_result is not None
            else None
        ),
        "destination": (
            route_result.destination
            if route_result is not None
            else "none"
        ),
        "route_error": (
            route_result.error
            if route_result is not None
            else ""
        ),
        # Scoring result (health_issue only)
        "risk_level": None,
        "action": None,
    }

    if route_result is not None and route_result.success:
        data = route_result.data
        entry["risk_level"] = data.get("risk_level")
        entry["action"] = data.get("action")
        
        # Save assessment to Postgres
        if entry["intent"] == "health_issue":
            save_assessment(
                user_id=1,
                symptoms=entry["symptoms"],
                risk_level=entry["risk_level"],
                score=data.get("score"),
                severity=entry["severity"],
                confidence=entry["confidence"],
                action=str(entry["action"].get("action", "")) if isinstance(entry["action"], dict) else str(entry["action"]),
                message=str(entry["action"].get("message", "")) if isinstance(entry["action"], dict) else ""
            )

    # ── Write JSON line to log file ───────────────────────────────────────────
    try:
        with open(_LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError as exc:
        _log.error("Failed to write log entry: %s", exc)

    # ── Mirror a human-readable summary to the console ────────────────────────
    _log.info(
        "request_id=%s  intent=%-14s  severity=%-8s  "
        "confidence=%s  route_ok=%s  risk_level=%s",
        request_id,
        entry["intent"],
        entry["severity"],
        entry["confidence"],
        entry["route_ok"],
        entry["risk_level"],
    )

    return request_id


def get_recent_requests(n: int = 20) -> list:
    """Return the last *n* pipeline log entries as a list of dicts.

    Reads from :data:`_LOG_FILE` (``logs/pipeline.log``).  Returns an empty
    list when the log file does not exist yet or cannot be read.

    Args:
        n: Maximum number of entries to return (most-recent first).

    Returns:
        List of dicts, each matching the structure written by
        :func:`log_request`.  Entries are returned newest-first.
    """
    if not os.path.isfile(_LOG_FILE):
        return []

    entries: list = []
    try:
        with open(_LOG_FILE, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
        # Take last n lines, parse each as JSON, skip malformed lines
        for line in reversed(lines[-n:]):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                _log.warning("Skipping malformed log line: %s", line[:80])
    except OSError as exc:
        _log.error("Failed to read log file: %s", exc)

    # entries are already in reverse order (newest first) from the reversed() loop
    return entries
