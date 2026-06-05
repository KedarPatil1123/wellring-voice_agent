# WellRing Architecture

## System Flow

```mermaid
graph TD;
    User[Elderly User Voice] --> Whisper[Whisper STT]
    Whisper --> Llama[Llama 3.2:1b NLU]
    Llama -- JSON Payload --> FastAPI[/assess Endpoint]
    FastAPI --> DBCheck[(History Lookup)]
    DBCheck --> Scoring[Scoring Engine]
    Scoring -- History Multiplier --> Scoring
    Scoring -- Confidence Threshold --> Scoring
    Scoring --> ResponseBuilder[Response Builder]
    ResponseBuilder --> DBLog[(Log Interaction)]
    ResponseBuilder --> Alerts[Notification Service]
    Alerts -- SMS --> Caregiver[Caregiver Phone]
    ResponseBuilder -- Text --> Piper[Piper TTS]
    Piper --> Audio[Audio Response to User]
```

## Key Components

1. **Voice Pipeline (`voice_health.py`)**
   - Transcribes audio using Whisper.
   - Extracts structured `intent`, `symptoms`, `severity`, and `confidence` using Llama.
   - Converts the backend's text response to speech using Piper.

2. **Scoring Engine (`src/scoring_engine/`)**
   - Applies baseline weights to symptoms.
   - Escalates score if symptoms repeat frequently (History Multiplier).
   - Downgrades confidence and forces follow-up if LLM certainty is low.
   - Outputs a human-readable `breakdown` of the calculation.

3. **Backend Service (`src/main.py`)**
   - FastAPI REST API integrating the scoring engine.

4. **Database (`src/database.py`)**
   - Stores interactions and alerts. Supports both SQLite (local) and Supabase PostgreSQL (production).

5. **Notification System (`src/notifications.py`)**
   - Triggers Twilio SMS to the assigned caregiver for HIGH and CRITICAL risk levels.
