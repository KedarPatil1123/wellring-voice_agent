"""
main.py
=======
WellRing Voice Agent — FastAPI backend.

Exposes the scoring and alert engine over HTTP so that Kedar's voice
pipeline can send parsed LLM output and receive a structured risk
assessment and escalation action.

Run locally:
    uvicorn src.main:app --reload --port 8000

Interactive docs:
    http://localhost:8000/docs
"""

# Load .env file before anything else reads os.environ
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Security, Depends, status
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
import datetime
import os

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def get_api_key(api_key_header: str = Security(api_key_header)):
    expected_key = os.environ.get("WELLRING_API_KEY", "wellring-secure-2026")
    if api_key_header == expected_key:
        return api_key_header
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API Key"
    )

from src.scoring_engine import calculate_score, determine_action
from src.database import init_db, log_interaction, get_symptom_repeat_count
from src.notifications import trigger_alerts_if_needed

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="WellRing Health Risk API",
    description=(
        "Receives voice-extracted health data from the LLM pipeline and "
        "returns a risk score, risk level, and escalation action plan."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class AssessRequest(BaseModel):
    """
    Payload sent by Kedar's LLM module after parsing the user's speech.
    """
    intent: str = Field(
        ...,
        description="Intent extracted from speech. e.g. 'health_issue', 'general_query'",
        examples=["health_issue"],
    )
    symptoms: List[str] = Field(
        default=[],
        description=(
            "Symptom identifiers extracted from the user's speech. "
            "Valid keys: dizziness, fever, medicine_missed, fall_detected, "
            "chest_pain, breathing_problem, unconscious, stroke_symptoms."
        ),
        examples=[["chest_pain", "breathing_problem"]],
    )
    severity: str = Field(
        ...,
        description="Overall severity label: low | medium | high | critical",
        examples=["high"],
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="LLM confidence in its symptom extraction, range [0.0, 1.0]",
        examples=[0.95],
    )
    user_id: Optional[str] = Field(None, description="UUID of the user (patient)")

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        allowed = {"low", "medium", "high", "critical"}
        if v.lower().strip() not in allowed:
            raise ValueError(
                f"severity must be one of {sorted(allowed)}, got '{v}'"
            )
        return v.lower().strip()


class AssessResponse(BaseModel):
    """
    Full risk assessment returned to the voice pipeline.
    """
    # --- Score info ---
    score: int         = Field(..., description="Final risk score after confidence scaling")
    base_score: int    = Field(..., description="Raw score before confidence scaling")
    confidence: float  = Field(..., description="Echoed LLM confidence value")

    # --- Classification ---
    risk_level: str    = Field(..., description="LOW | MEDIUM | HIGH | CRITICAL")
    category: str      = Field(..., description="Primary clinical category (e.g. CARDIAC)")
    symptoms: List[str]= Field(..., description="Recognised symptom keys only")
    severity: str      = Field(..., description="Normalised severity label")

    # --- Escalation ---
    action: str        = Field(..., description="Escalation action identifier")
    message: str       = Field(..., description="Human-readable summary of the action")
    steps: List[str]   = Field(..., description="Ordered list of escalation steps")

    # --- Explainability ---
    breakdown: List[str] = Field(..., description="Per-component score breakdown for explainability")

    # --- Meta ---
    timestamp: str     = Field(..., description="ISO 8601 UTC timestamp of the assessment")


class HealthResponse(BaseModel):
    status: str
    version: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_model=HealthResponse, tags=["Health"])
def root():
    """Health check — confirms the API is running."""
    return HealthResponse(status="ok", version="1.0.0")


@app.get("/health", response_model=HealthResponse, tags=["Health"])
def health():
    """Alias health check endpoint."""
    return HealthResponse(status="ok", version="1.0.0")


@app.post("/assess", response_model=AssessResponse, tags=["Risk Assessment"])
def assess(payload: AssessRequest, api_key: str = Depends(get_api_key)):
    """
    Core endpoint. Accepts the LLM-parsed voice input and returns a full
    health risk assessment with escalation steps.

    **Typical flow:**
    1. User speaks → Whisper (STT) → Llama 3 (NLU) → this endpoint
    2. Scoring engine calculates risk score
    3. Alert engine determines escalation action
    4. Response is spoken back to the user and logged
    """
    try:
        # Build history counts for each symptom from the last 3 days
        history_counts = {
            s: get_symptom_repeat_count(s, days=3)
            for s in payload.symptoms
        }

        score_result = calculate_score(
            symptoms=payload.symptoms,
            severity=payload.severity,
            confidence=payload.confidence,
            history_counts=history_counts,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    alert_result = determine_action(score_result["score"], payload.confidence)

    response_data = {
        # score block
        "score": score_result["score"],
        "base_score": score_result["base_score"],
        "confidence": score_result["confidence"],
        # classification block
        "risk_level": score_result["risk_level"],
        "category": score_result["category"],
        "symptoms": score_result["symptoms"],
        "severity": score_result["severity"],
        # escalation block
        "action": alert_result["action"],
        "message": alert_result["message"],
        "steps": alert_result["steps"],
        # explainability block
        "breakdown": score_result["breakdown"],
        # meta
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    }
    
    # Log interaction to database
    log_data = response_data.copy()
    log_data["intent"] = payload.intent
    log_data["user_id"] = payload.user_id
    interaction_id = log_interaction(log_data)
    
    # Trigger alerts if necessary
    trigger_alerts_if_needed(interaction_id, response_data["risk_level"], response_data["message"], payload.user_id)

    return AssessResponse(**response_data)


@app.get("/symptoms", tags=["Reference"])
def list_symptoms():
    """
    Returns the full list of recognised symptom keys and their weights.
    Useful for Kedar's LLM module to know which symptom labels to output.
    """
    from src.scoring_engine.rules import SYMPTOM_WEIGHTS, SYMPTOM_CATEGORIES
    return {
        "symptoms": [
            {
                "key": k,
                "weight": SYMPTOM_WEIGHTS[k],
                "category": SYMPTOM_CATEGORIES.get(k, "UNKNOWN"),
            }
            for k in SYMPTOM_WEIGHTS
        ]
    }


@app.get("/risk-levels", tags=["Reference"])
def list_risk_levels():
    """
    Returns the risk level thresholds and what action each triggers.
    """
    from src.scoring_engine.alerts import _ESCALATION
    from src.scoring_engine.baseline import RiskLevel
    return {
        "levels": [
            {
                "level": level.value,
                "score_range": ranges,
                "action": _ESCALATION[level]["action"],
                "message": _ESCALATION[level]["message"],
            }
            for level, ranges in [
                (RiskLevel.LOW,      "0–30"),
                (RiskLevel.MEDIUM,   "31–60"),
                (RiskLevel.HIGH,     "61–100"),
                (RiskLevel.CRITICAL, "101+"),
            ]
        ]
    }


# ---------------------------------------------------------------------------
# Dashboard Endpoints
# ---------------------------------------------------------------------------

import sqlite3
import json
from src.database import _resolve_db_path

@app.get("/assessments", tags=["Dashboard"])
def get_assessments(limit: int = 50, risk_level: Optional[str] = None, api_key: str = Depends(get_api_key)):
    """Returns recent assessments (interactions) for the dashboard feed."""
    db_path = _resolve_db_path(None)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Check if table exists first
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='interactions'
    """)
    if not cursor.fetchone():
        conn.close()
        return []
    
    query = "SELECT * FROM interactions ORDER BY timestamp DESC LIMIT ?"
    params = [limit]
    
    if risk_level:
        query = "SELECT * FROM interactions WHERE risk_level = ? ORDER BY timestamp DESC LIMIT ?"
        params = [risk_level.upper(), limit]
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        r_dict = dict(row)
        try:
            r_dict["symptoms"] = json.loads(r_dict["symptoms"])
        except Exception:
            pass
        result.append(r_dict)
        
    return result


@app.get("/assessments/stats", tags=["Dashboard"])
def get_assessment_stats(api_key: str = Depends(get_api_key)):
    """Returns counts for dashboard cards."""
    db_path = _resolve_db_path(None)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            COUNT(*) as total_today,
            SUM(CASE WHEN risk_level = 'LOW' THEN 1 ELSE 0 END) as low,
            SUM(CASE WHEN risk_level = 'MEDIUM' THEN 1 ELSE 0 END) as medium,
            SUM(CASE WHEN risk_level = 'HIGH' THEN 1 ELSE 0 END) as high,
            SUM(CASE WHEN risk_level = 'CRITICAL' THEN 1 ELSE 0 END) as critical
        FROM interactions 
        WHERE date(timestamp) = date('now', 'localtime')
    """)
    row = cursor.fetchone()
    conn.close()
    
    return {
        "total_today": row[0] or 0,
        "low": row[1] or 0,
        "medium": row[2] or 0,
        "high": row[3] or 0,
        "critical": row[4] or 0
    }


@app.get("/patients", tags=["Dashboard"])
def get_patients(api_key: str = Depends(get_api_key)):
    """Hardcoded for demo — replace with real DB later."""
    return [
        {
            "id": 1,
            "name": "Mr. Sharma",
            "age": 72,
            "conditions": ["Hypertension", "Diabetes"],
            "emergency_contact": "+91-9876543210",
            "language": "English",
            "status": "active"
        }
    ]
