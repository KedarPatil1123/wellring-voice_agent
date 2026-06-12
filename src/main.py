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

from fastapi import FastAPI, HTTPException, Security, Depends, status, Request
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
import datetime
import os
import asyncio
import logging
import sqlite3
import json

logger = logging.getLogger(__name__)

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

from src.scoring_engine import calculate_score, determine_action, SYMPTOM_WEIGHTS
from src.database import (
    init_db, log_interaction, get_symptom_repeat_count,
    add_reminder, get_reminders, delete_reminder, update_reminder_trigger,
    get_assessments_list, get_assessment_stats
)
from src.notifications import trigger_alerts_if_needed, send_whatsapp_reminder

# ---------------------------------------------------------------------------
# Background Reminder Scheduler
# ---------------------------------------------------------------------------

async def run_reminder_scheduler():
    logger.info("Starting background reminder scheduler...")
    while True:
        try:
            await asyncio.sleep(15)  # check every 15 seconds for responsive testing
            reminders = get_reminders()
            if not reminders:
                continue
                
            now = datetime.datetime.now()
            current_time_str = now.strftime("%H:%M")
            current_date_str = now.strftime("%Y-%m-%d")
            
            for reminder in reminders:
                rem_id = reminder["id"]
                rem_type = reminder["type"]
                rem_title = reminder["title"]
                rem_time = reminder["time"]
                rem_freq = reminder["frequency"]
                rem_phone = reminder["phone"]
                rem_notes = reminder["notes"] or ""
                last_trig = reminder["last_triggered"]
                
                should_trigger = False
                trigger_timestamp = ""
                
                if rem_freq == "once" or "T" in rem_time:
                    try:
                        # e.g., "2026-06-10T14:30"
                        rem_dt = datetime.datetime.fromisoformat(rem_time.replace("Z", ""))
                        if now >= rem_dt and not last_trig:
                            should_trigger = True
                            trigger_timestamp = now.isoformat()
                    except Exception as e:
                        logger.error(f"Error parsing date {rem_time}: {e}")
                else:
                    if current_time_str == rem_time:
                        if rem_freq == "daily":
                            if last_trig != current_date_str:
                                should_trigger = True
                                trigger_timestamp = current_date_str
                        elif rem_freq == "monthly":
                            current_month = now.strftime("%Y-%m")
                            if last_trig != current_month:
                                should_trigger = True
                                trigger_timestamp = current_month
                        elif rem_freq == "yearly":
                            current_year = now.strftime("%Y")
                            if last_trig != current_year:
                                should_trigger = True
                                trigger_timestamp = current_year
                
                if should_trigger:
                    if rem_type == "call":
                        body = f"📞 WellRing Daily Voice Call Reminder:\nTime for your scheduled check-in call.\nNotes: {rem_notes}"
                    elif rem_type == "medicine":
                        body = f"💊 WellRing Medicine Reminder:\nPlease take {rem_title}.\nNotes: {rem_notes}"
                    elif rem_type == "checkup":
                        body = f"🏥 WellRing Health Checkup Reminder:\nYou have '{rem_title}' scheduled.\nNotes: {rem_notes}"
                    else:
                        body = f"⏰ WellRing Reminder: {rem_title}.\nNotes: {rem_notes}"
                    
                    logger.info(f"Triggering reminder {rem_id} ({rem_title}) for {rem_phone}")
                    success = send_whatsapp_reminder(rem_phone, body)
                    if success:
                        update_reminder_trigger(rem_id, trigger_timestamp)
        except asyncio.CancelledError:
            logger.info("Reminder scheduler task cancelled.")
            break
        except Exception as ex:
            logger.error(f"Error in reminder scheduler: {ex}")

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

scheduler_task = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler_task
    init_db()
    scheduler_task = asyncio.create_task(run_reminder_scheduler())
    yield
    if scheduler_task:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass

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
    recording_url: Optional[str] = Field(None, description="URL to the audio recording of the assessment")

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
    recording_url: Optional[str] = Field(None, description="URL to the audio recording if provided")


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


@app.post("/assess", tags=["Risk Assessment"])
async def assess(request: Request, api_key: str = Depends(get_api_key)):
    """
    Core endpoint. Accepts the LLM-parsed voice input (either flat or wrapped in Vapi's webhook format)
    and returns a health risk assessment with escalation steps.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # Check if this is a Vapi tool call request
    is_vapi = False
    tool_call_id = None
    
    # Check for Vapi tool-calls format
    if isinstance(body, dict) and "message" in body:
        msg = body["message"]
        if isinstance(msg, dict) and msg.get("type") in ("tool-calls", "function-call"):
            is_vapi = True
            tool_calls = msg.get("toolCalls", [])
            if not tool_calls and "call" in msg:
                tool_calls = [msg.get("call")]
            
            if tool_calls:
                first_call = tool_calls[0]
                tool_call_id = first_call.get("id")
                func = first_call.get("function", {})
                args = func.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        pass
                
                # Extract fields from Vapi tool call arguments
                intent = args.get("intent", "health_issue")
                symptoms = args.get("symptoms", [])
                severity = args.get("severity", "medium")
                confidence = args.get("confidence", 1.0)
                user_id = args.get("user_id")
                recording_url = args.get("recording_url")
            else:
                raise HTTPException(status_code=400, detail="Vapi tool-calls empty")
    else:
        # Standard direct AssessRequest payload
        try:
            payload = AssessRequest(**body)
            intent = payload.intent
            symptoms = payload.symptoms
            severity = payload.severity
            confidence = payload.confidence
            user_id = payload.user_id
            recording_url = payload.recording_url
        except Exception as err:
            raise HTTPException(status_code=422, detail=str(err))

    # Normalize symptoms (Vapi LLM may output symptoms with spaces or minor spelling variations)
    normalized_symptoms = []
    for s in symptoms:
        s_norm = s.lower().strip().replace(" ", "_").replace("-", "_")
        # Direct aliases
        if s_norm == "dizzy":
            s_norm = "dizziness"
        elif s_norm == "fall":
            s_norm = "fall_detected"
        elif s_norm == "stroke":
            s_norm = "stroke_symptoms"
        elif s_norm in ("short_of_breath", "difficulty_breathing", "breathing_difficulty"):
            s_norm = "breathing_problem"
        
        # Add if it matches a valid symptom key in SYMPTOM_WEIGHTS
        if s_norm in SYMPTOM_WEIGHTS:
            normalized_symptoms.append(s_norm)
        else:
            # Check for partial matches
            matched = False
            for valid_key in SYMPTOM_WEIGHTS.keys():
                if valid_key in s_norm or s_norm in valid_key:
                    normalized_symptoms.append(valid_key)
                    matched = True
                    break
            if not matched:
                normalized_symptoms.append(s)

    # Normalize severity
    severity_lower = severity.lower().strip()
    if severity_lower not in {"low", "medium", "high", "critical"}:
        severity_lower = "medium"

    try:
        # Build history counts for each symptom from the last 3 days
        history_counts = {
            s: get_symptom_repeat_count(s, days=3)
            for s in normalized_symptoms
        }

        score_result = calculate_score(
            symptoms=normalized_symptoms,
            severity=severity_lower,
            confidence=confidence,
            history_counts=history_counts,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    alert_result = determine_action(score_result["score"], confidence)

    response_data = {
        "score": score_result["score"],
        "base_score": score_result["base_score"],
        "confidence": score_result["confidence"],
        "risk_level": score_result["risk_level"],
        "category": score_result["category"],
        "symptoms": score_result["symptoms"],
        "severity": score_result.get("severity", severity_lower),
        "action": alert_result["action"],
        "message": alert_result["message"],
        "steps": alert_result["steps"],
        "breakdown": score_result["breakdown"],
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "recording_url": recording_url,
    }
    
    # Log interaction to database
    log_data = response_data.copy()
    log_data["intent"] = intent
    log_data["user_id"] = user_id
    interaction_id = log_interaction(log_data)
    
    # Trigger alerts if necessary
    trigger_alerts_if_needed(interaction_id, response_data, user_id)

    # Return structure based on who called it
    if is_vapi:
        return {
            "results": [
                {
                    "toolCallId": tool_call_id,
                    "result": {
                        "score": response_data["score"],
                        "risk_level": response_data["risk_level"],
                        "category": response_data["category"],
                        "action": response_data["action"],
                        "message": response_data["message"],
                        "steps": response_data["steps"]
                    }
                }
            ]
        }
    else:
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

@app.get("/assessments", tags=["Dashboard"])
def get_assessments(limit: int = 50, risk_level: Optional[str] = None, api_key: str = Depends(get_api_key)):
    """Returns recent assessments (interactions) for the dashboard feed."""
    return get_assessments_list(limit=limit, risk_level=risk_level)


@app.get("/assessments/stats", tags=["Dashboard"])
def get_assessment_stats_endpoint(api_key: str = Depends(get_api_key)):
    """Returns counts for dashboard cards."""
    return get_assessment_stats()


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


class ReminderCreate(BaseModel):
    type: str = Field(..., description="call | medicine | checkup")
    title: str = Field(..., description="Title/name of the reminder")
    time: str = Field(..., description="Time (HH:MM) or datetime (ISO string)")
    frequency: str = Field(..., description="daily | monthly | yearly | once")
    phone: str = Field(..., description="WhatsApp phone number")
    notes: Optional[str] = None


@app.get("/reminders", tags=["Reminders"])
def list_reminders(api_key: str = Depends(get_api_key)):
    """Retrieve all reminders."""
    return get_reminders()


@app.post("/reminders", tags=["Reminders"], status_code=status.HTTP_201_CREATED)
def create_reminder(payload: ReminderCreate, api_key: str = Depends(get_api_key)):
    """Create a new reminder schedule."""
    reminder_id = add_reminder(
        type_val=payload.type,
        title=payload.title,
        time_val=payload.time,
        frequency=payload.frequency,
        phone=payload.phone,
        notes=payload.notes
    )
    return {"id": reminder_id, "message": "Reminder scheduled successfully"}


@app.delete("/reminders/{reminder_id}", tags=["Reminders"])
def remove_reminder(reminder_id: int, api_key: str = Depends(get_api_key)):
    """Delete a reminder schedule."""
    success = delete_reminder(reminder_id)
    if not success:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return {"message": "Reminder deleted successfully"}

