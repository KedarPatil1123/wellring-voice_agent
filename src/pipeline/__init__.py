"""
pipeline
========
Request pipeline for the WellRing voice agent.

Flow:
    Whisper → Llama → FastAPI
                         ↓
                     validate()   ← validator.py
                         ↓
                     route()      ← router.py
                         ↓
              ┌──────────┴──────────────┐
        health_issue              general_chat
              ↓                         ↓
       scoring_engine          conversation handler
                         ↓
                    log_request()  ← logger.py

Sub-modules:
    validator  — Field-level validation of Llama payloads
    router     — Intent-based dispatch to scoring or chat
    logger     — Structured request metadata logging

Quick usage (from FastAPI endpoint):
    from pipeline import validate, route, log_request

    result = validate(payload)
    if not result:
        return {"errors": result.errors}

    route_result = route(result.payload)
    request_id   = log_request(payload, route_result, result)
    return {"request_id": request_id, **route_result.data}
"""

from .validator import validate, ValidationResult, VALID_INTENTS, VALID_SEVERITIES
from .router import route, RouteResult
from .logger import log_request, get_recent_requests
from .models import AssessmentRequest, AssessmentResponse, ErrorResponse, HealthResponse

__all__ = [
    # validator
    "validate",
    "ValidationResult",
    "VALID_INTENTS",
    "VALID_SEVERITIES",
    # router
    "route",
    "RouteResult",
    # logger
    "log_request",
    "get_recent_requests",
    # models
    "AssessmentRequest",
    "AssessmentResponse",
    "ErrorResponse",
    "HealthResponse",
]
