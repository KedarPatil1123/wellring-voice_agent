# WellRing API Documentation

The WellRing backend is built using FastAPI and exposes endpoints for health assessments and reference data.

## Base URL
Local development: `http://localhost:8000`

## Endpoints

### 1. Health Check
`GET /`
`GET /health`

**Response (200 OK):**
```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

### 2. Assessment Engine
`POST /assess`

Takes an LLM-extracted symptom payload and returns a risk level, score, and recommended action.

**Request Body:**
```json
{
  "intent": "health_issue",
  "symptoms": ["chest_pain", "breathing_problem"],
  "severity": "critical",
  "confidence": 0.95,
  "user_id": "uuid-of-the-patient"
}
```

**Response (200 OK):**
```json
{
  "score": 124,
  "base_score": 130,
  "confidence": 0.95,
  "risk_level": "CRITICAL",
  "category": "CARDIAC",
  "symptoms": ["chest_pain", "breathing_problem"],
  "severity": "critical",
  "action": "notify_caregiver_and_emergency_services",
  "message": "Critical: chest_pain, breathing_problem detected. Calling caregiver and emergency services.",
  "steps": [
    "Call emergency services (911) immediately.",
    "Ensure the patient is in a safe position.",
    "Monitor breathing and pulse."
  ],
  "breakdown": [
    "chest_pain: +50 (first occurrence)",
    "breathing_problem: +40 (first occurrence)",
    "Severity (critical): +40",
    "Score scaled by confidence (0.95): 130 -> 124"
  ],
  "timestamp": "2026-06-05T12:00:00.000000Z"
}
```

### 3. Symptoms Reference
`GET /symptoms`

Returns a list of all recognized symptoms and their baseline weights.

### 4. Risk Levels Reference
`GET /risk-levels`

Returns the criteria and thresholds for LOW, MEDIUM, HIGH, and CRITICAL risk levels.
