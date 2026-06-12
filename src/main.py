"""
main.py
=======
WellRing FastAPI application.

Endpoints:
    GET  /health           → liveness probe
    POST /assess           → full pipeline: validate → route → log → respond
    POST /transcribe       → text-in pipeline: Llama classify → validate → route → log
    GET  /history          → recent pipeline log entries

The pipeline flow:
    Whisper → Llama → POST /assess
                           ↓
                       Pydantic (type gate)
                           ↓
                       validate()
                           ↓ fail → 422 ErrorResponse
                           ↓ ok
                       route()
                           ↓
                       log_request()
                           ↓
                       200 AssessmentResponse

Run with:
    uvicorn src.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

# Ensure src/ is importable when running from project root
_SRC = os.path.dirname(os.path.abspath(__file__))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from llama import classify
from notifier import dispatch as notify_caregiver, is_webhook_configured
from pipeline import validate, route, log_request
from pipeline.logger import get_recent_requests
from pipeline.models import (
    AssessmentRequest,
    AssessmentResponse,
    ErrorResponse,
    HealthResponse,
)

from db_session import engine, SessionLocal
from models import Base, User



_log = logging.getLogger("wellring.api")


# ── Startup / shutdown lifespan ───────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Preload heavy models at startup so the first request is instant.

    Whisper and Piper TTS are loaded lazily on first use by default, which
    can add 5-15 s of latency to the first request.  Loading them here moves
    that cost to startup time, improving UX for all subsequent callers.
    """
    # ── Init DB ───────────────────────────────────────────────────────────────
    try:
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            if not db.query(User).filter_by(user_id=1).first():
                dummy_patient = User(name="Dummy Patient", age=75, role="patient", phone="+11234567890", emergency_contact="+10987654321")
                db.add(dummy_patient)
                db.commit()
        _log.info("✅  Database initialized and dummy user verified.")
    except Exception as exc:
        _log.warning("⚠️  Database initialization failed: %s", exc)


    # ── Preload Whisper ───────────────────────────────────────────────────────
    try:
        from whisper_layer.transcriber import preload_model
        preload_model()  # loads the default "small" model
        _log.info("✅  Whisper model preloaded.")
    except Exception as exc:  # noqa: BLE001
        _log.warning("⚠️  Whisper preload skipped (non-fatal): %s", exc)

    # ── Preload Piper TTS — warn if .onnx file is missing ────────────────────
    try:
        from tts.speaker import preload_voice, DEFAULT_VOICE_MODEL
        if not os.path.isfile(DEFAULT_VOICE_MODEL):
            _log.warning(
                "⚠️  Piper voice model not found at '%s'. "
                "TTS will fail at runtime. "
                "Download en_US-ryan-high.onnx from "
                "https://rhasspy.github.io/piper-samples/ "
                "and place it in the project root, or set the "
                "WELLRING_VOICE_MODEL environment variable.",
                DEFAULT_VOICE_MODEL,
            )
        else:
            preload_voice()
            _log.info("✅  Piper TTS voice model preloaded.")
    except Exception as exc:  # noqa: BLE001
        _log.warning("⚠️  Piper preload skipped (non-fatal): %s", exc)

    yield  # application runs here

    # ── Shutdown (nothing to clean up for now) ────────────────────────────────
    _log.info("WellRing API shutting down.")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="WellRing Voice Agent API",
    description=(
        "Health risk pipeline for the WellRing elderly voice assistant. "
        "Receives structured Llama output, validates it, scores it, "
        "and returns an escalation action."
    ),
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness probe",
    tags=["infra"],
)
def health_check() -> HealthResponse:
    """Returns ``{"status": "ok"}`` — used by load balancers and monitors."""
    return HealthResponse()


# ── Status / readiness endpoint ───────────────────────────────────────────────────────

@app.get(
    "/status",
    summary="System readiness check",
    tags=["infra"],
)
def system_status() -> JSONResponse:
    """
    Detailed readiness probe.

    Checks every external dependency and returns a structured report.
    Useful for:  Docker HEALTHCHECK, k8s liveness probes, dashboards.

    Returns HTTP 200 when the core pipeline is operational, even if optional
    components (TTS model, webhook) are unavailable.
    """
    checks: dict = {}

    # ── Ollama / Llama ────────────────────────────────────────────────────────
    try:
        import ollama
        models = ollama.list()
        model_names = [
            m.model if hasattr(m, "model") else m.get("name", "")
            for m in (models.models if hasattr(models, "models") else models)
        ]
        llama_ok = any("llama" in (n or "").lower() for n in model_names)
        checks["ollama"] = {
            "ok":     llama_ok,
            "models": model_names,
            "detail": "llama3 found" if llama_ok else "llama3 not found in Ollama model list",
        }
    except Exception as exc:  # noqa: BLE001
        checks["ollama"] = {"ok": False, "detail": str(exc)}

    # ── Piper TTS model file ─────────────────────────────────────────────────────
    try:
        from tts.speaker import DEFAULT_VOICE_MODEL
        tts_ok = os.path.isfile(DEFAULT_VOICE_MODEL)
        checks["tts"] = {
            "ok":         tts_ok,
            "model_path": DEFAULT_VOICE_MODEL,
            "detail":     "model file found" if tts_ok else "model file missing — set WELLRING_VOICE_MODEL",
        }
    except Exception as exc:  # noqa: BLE001
        checks["tts"] = {"ok": False, "detail": str(exc)}

    # ── Pipeline log writability ─────────────────────────────────────────────────────
    try:
        from pipeline.logger import LOG_PATH
        log_dir = os.path.dirname(LOG_PATH)
        log_ok  = os.access(log_dir, os.W_OK) if os.path.isdir(log_dir) else os.access(".", os.W_OK)
        checks["log"] = {
            "ok":      log_ok,
            "path":    LOG_PATH,
            "detail":  "writable" if log_ok else "log directory not writable",
        }
    except Exception as exc:  # noqa: BLE001
        checks["log"] = {"ok": False, "detail": str(exc)}

    # ── Caregiver webhook ─────────────────────────────────────────────────────────
    checks["webhook"] = {
        "ok":         True,   # optional — never blocks core pipeline
        "configured": is_webhook_configured(),
        "detail":     "configured" if is_webhook_configured() else "not configured (set WELLRING_WEBHOOK_URL)",
    }

    # ── Overall readiness ────────────────────────────────────────────────────────────
    # Core pipeline is ready as long as /assess can serve requests.
    # Ollama and TTS are checked but do not block readiness in dev mode.
    ready = checks.get("log", {}).get("ok", False)

    return JSONResponse(
        status_code=status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "ready":   ready,
            "version": "1.1.0",
            "checks":  checks,
        },
    )


@app.post(
    "/assess",
    response_model=AssessmentResponse,
    responses={422: {"model": ErrorResponse}},
    summary="Assess a health report from Llama",
    tags=["pipeline"],
)
def assess(body: AssessmentRequest) -> JSONResponse:
    """
    Full pipeline endpoint.

    1. **Pydantic** enforces field types (FastAPI built-in).
    2. **Validator** checks business rules (intent ∈ VALID_INTENTS, etc.).
    3. **Router** dispatches to the correct handler.
    4. **Logger** writes a structured log entry and returns a ``request_id``.

    Returns a full ``AssessmentResponse`` or a ``422 ErrorResponse``.
    """
    raw = body.model_dump()

    # ── Step 1: business-rule validation ─────────────────────────────────────
    # Forward the transcript so the conversation handler can detect topics
    if body.transcript:
        raw["transcript"] = body.transcript

    v = validate(raw)
    if not v:
        request_id = log_request(raw, None, v)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=ErrorResponse(
                request_id=request_id,
                errors=v.errors,
            ).model_dump(),
        )

    # ── Step 2: routing ───────────────────────────────────────────────────────
    rr = route(v.payload)

    # ── Step 3: logging ───────────────────────────────────────────────────────
    request_id = log_request(raw, rr, v)

    # ── Step 4: respond ───────────────────────────────────────────────────────
    if not rr.success:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                request_id=request_id,
                errors=[rr.error],
            ).model_dump(),
        )

    response_data: dict = {
        "request_id": request_id,
        "intent": raw["intent"],
        "destination": rr.destination,
        **rr.data,
    }

    # ── Step 4.5: Caregiver notification (non-fatal, fire-and-forget) ─────────
    try:
        alert_payload = {
            **rr.data.get("action", {}),
            "risk_level": rr.data.get("risk_level", ""),
            "score":      rr.data.get("score", 0),
            "request_id": request_id,
            "symptoms":   v.payload.get("symptoms", []),
        }
        nr = notify_caregiver(alert_payload)
        if nr and not nr.skipped:
            _log.info("Caregiver notified — channels=%s", nr.channels_ok)
    except Exception as exc:  # noqa: BLE001
        _log.warning("Notifier failed (non-fatal): %s", exc)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=AssessmentResponse(**response_data).model_dump(),
    )


# ── History endpoint ──────────────────────────────────────────────────────────

@app.get(
    "/history",
    summary="Recent pipeline requests",
    tags=["infra"],
)
def history(limit: int = 20) -> JSONResponse:
    """
    Return the last ``limit`` pipeline log entries (newest first).

    Useful for dashboards, caregiver apps, and debugging.
    The ``limit`` query parameter caps at 100 to prevent large reads.
    """
    n = min(max(1, limit), 100)
    entries = get_recent_requests(n)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"count": len(entries), "entries": entries},
    )


# ── Transcribe endpoint ───────────────────────────────────────────────────────

class TranscribeRequest(BaseModel):
    """Raw transcript text to classify and assess."""

    transcript: str = Field(
        ...,
        min_length=1,
        description="Raw speech-to-text output from Whisper (or any STT engine).",
        examples=["I have chest pain and I cannot breathe properly."],
    )

    model_config = {"json_schema_extra": {
        "example": {"transcript": "I feel dizzy and my chest hurts."}
    }}


@app.post(
    "/transcribe",
    response_model=AssessmentResponse,
    responses={
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse, "description": "Llama unavailable"},
    },
    summary="Classify a raw transcript and assess health risk",
    tags=["pipeline"],
)
def transcribe_and_assess(body: TranscribeRequest) -> JSONResponse:
    """
    Text-in pipeline endpoint.

    Accepts a raw Whisper transcript, classifies it with Llama, then
    runs the standard validate → route → log pipeline.

    This is the primary entry point for the voice agent's real-time path:

        Whisper STT  →  POST /transcribe  →  AssessmentResponse
                              ↓
                         llama.classify()
                              ↓
                         validate()
                              ↓
                         route()
                              ↓
                         log_request()

    Use ``POST /assess`` when you already have a structured Llama payload.
    Use ``POST /transcribe`` when you only have raw speech text.
    """
    # ── Step 1: classify with Llama ─────────────────────────────────────────────
    try:
        cl = classify(body.transcript)
    except Exception as exc:
        _log.error("Llama classify raised an unexpected exception: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=ErrorResponse(
                request_id="unavailable",
                errors=[f"Llama classification service error: {exc}"],
            ).model_dump(),
        )

    if cl.is_fallback:
        _log.warning("Llama fallback used for transcript: %s", cl.error)

    # Inject the original transcript so the conversation router can detect topic
    raw = {**cl.payload, "transcript": body.transcript}

    # ── Step 2: validate ──────────────────────────────────────────────────────
    v = validate(raw)
    if not v:
        request_id = log_request(raw, None, v)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=ErrorResponse(
                request_id=request_id,
                errors=v.errors,
            ).model_dump(),
        )

    # ── Step 3: route ─────────────────────────────────────────────────────────
    rr = route(v.payload)

    # ── Step 4: log ───────────────────────────────────────────────────────────
    request_id = log_request(raw, rr, v)

    # ── Step 5: respond ───────────────────────────────────────────────────────
    if not rr.success:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                request_id=request_id,
                errors=[rr.error],
            ).model_dump(),
        )

    response_data: dict = {
        "request_id": request_id,
        "intent":      v.payload.get("intent", "unknown"),
        "destination": rr.destination,
        **rr.data,
    }
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=AssessmentResponse(**response_data).model_dump(),
    )
