"""
models.py
=========
Pydantic request/response models for the WellRing FastAPI layer.

These models enforce types on the HTTP boundary so FastAPI can
auto-validate, auto-document (OpenAPI), and auto-serialize.

Request  → AssessmentRequest   (Llama JSON arriving at /assess)
Response ← AssessmentResponse  (full scored + routed result)
         ← ErrorResponse       (validation failures, 422)
         ← HealthResponse      (GET /health liveness check)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


# ── Request ───────────────────────────────────────────────────────────────────

class AssessmentRequest(BaseModel):
    """Structured payload produced by the Llama module.

    Sent by the Llama layer (or test clients) to ``POST /assess``.
    """

    intent: str = Field(
        ...,
        description="Classified intent from Llama.",
        examples=["health_issue", "general_chat"],
    )
    symptoms: List[str] = Field(
        default_factory=list,
        description="List of symptom keys extracted from speech.",
        examples=[["chest_pain", "dizziness"]],
    )
    severity: str = Field(
        ...,
        description="Overall severity label from Llama.",
        examples=["high"],
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="LLM prediction confidence in [0.0, 1.0].",
        examples=[0.92],
    )
    transcript: Optional[str] = Field(
        default=None,
        description="Raw Whisper transcript — used for topic detection in general_chat turns.",
        examples=["Good morning, how are you today?"],
    )

    @field_validator("intent", "severity", mode="before")
    @classmethod
    def lowercase_strip(cls, v: Any) -> str:
        """Normalise string fields before validation."""
        return str(v).lower().strip()

    model_config = {"json_schema_extra": {
        "example": {
            "intent": "health_issue",
            "symptoms": ["chest_pain", "dizziness"],
            "severity": "high",
            "confidence": 0.92,
            "transcript": "I have chest pain and I feel dizzy.",
        }
    }}


# ── Responses ─────────────────────────────────────────────────────────────────

class ActionDetail(BaseModel):
    """Escalation action block from the alerts engine."""

    action: str
    risk_level: str
    score: int
    message: str
    steps: List[str]


class AssessmentResponse(BaseModel):
    """Full pipeline response returned to the caller."""

    request_id: str = Field(..., description="UUID for request tracing.")
    intent: str
    destination: str = Field(
        ..., description="Handler that processed the request."
    )
    # Health-issue fields (None for general_chat)
    score: Optional[int] = None
    base_score: Optional[int] = None
    confidence: Optional[float] = None
    risk_level: Optional[str] = None
    category: Optional[str] = None
    symptoms: Optional[List[str]] = None
    severity: Optional[str] = None
    action: Optional[ActionDetail] = None
    # General-chat fields
    response_type: Optional[str] = None
    topic:         Optional[str] = None   # detected conversational topic
    message:       Optional[str] = None
    follow_up:     Optional[str] = None   # optional follow-up question


class ErrorResponse(BaseModel):
    """Returned when pipeline validation fails (HTTP 422)."""

    request_id: str
    errors: List[str]


class HealthResponse(BaseModel):
    """Liveness check response for ``GET /health``."""

    status: str = "ok"
    service: str = "wellring-pipeline"
    version: str = "1.0.0"
