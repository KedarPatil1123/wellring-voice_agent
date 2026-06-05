# WellRing Voice Agent

An AI-powered voice health assistant for elderly people that listens, understands, and responds in real-time.

## What it does

- 🎙️ **Listens** to the user's voice (via microphone)
- 🧠 **Transcribes** speech to text using OpenAI Whisper
- 🤖 **Classifies** health intent using Llama 3 (via Ollama)
- ✅ **Validates** the structured response through a 5-field pipeline
- 🚨 **Scores** health risk and triggers emergency escalation if needed
- 🔊 **Speaks** the response back using Piper TTS

## Architecture

```
Microphone
    ↓
whisper_layer/          ← Stage 1: Record + Transcribe
    recorder.py         (sounddevice → WAV file)
    transcriber.py      (Whisper model → text)
    ↓
llama/                  ← Stage 2: Classify
    prompt.py           (system prompt + few-shot examples)
    client.py           (Ollama wrapper, retry + fallback)
    parser.py           (JSON extraction + field repair)
    ↓
pipeline/               ← Stage 3: Validate → Route → Log
    validator.py        (intent, severity, symptoms, confidence, transcript)
    router.py           (health_issue → scoring | general_chat → conversation)
    conversation.py     (topic-aware chat response templates)
    logger.py           (structured JSON log → logs/pipeline.log)
    models.py           (Pydantic FastAPI request/response models)
    ↓
scoring_engine/         ← Stage 4: Score + Escalate
    rules.py            (symptom weights, severity bonuses)
    scoring.py          (calculate_score with confidence multiplier)
    baseline.py         (RiskLevel thresholds)
    alerts.py           (determine_action → emergency | urgent | monitor)
    ↓
tts/                    ← Stage 5: Synthesise + Speak
    speaker.py          (Piper TTS → WAV → playback)
    ↓
src/orchestrator.py     ← Ties all stages into run_once() / run_loop()
src/main.py             ← FastAPI: GET /health  POST /assess  POST /transcribe  GET /history
```

## Project Structure

```
wellring-voice_agent/
├── src/
│   ├── main.py                 ← FastAPI app (GET /health, POST /assess, POST /transcribe, GET /history)
│   ├── orchestrator.py         ← End-to-end run_once() / run_loop()
│   ├── whisper_layer/
│   │   ├── recorder.py         ← Microphone capture (silence detection)
│   │   └── transcriber.py      ← Whisper STT (lazy singleton model load)
│   ├── llama/
│   │   ├── prompt.py           ← System prompt + few-shot examples
│   │   ├── client.py           ← Ollama wrapper (retry + exponential backoff + fallback)
│   │   └── parser.py           ← Defensive JSON extraction
│   ├── pipeline/
│   │   ├── validator.py        ← Field-level validation (+ transcript pass-through)
│   │   ├── router.py           ← Intent-based dispatch
│   │   ├── conversation.py     ← Topic-aware general-chat response templates
│   │   ├── logger.py           ← Structured JSON request log
│   │   └── models.py           ← Pydantic FastAPI models
│   ├── scoring_engine/
│   │   ├── rules.py            ← Symptom weights & severity bonuses
│   │   ├── scoring.py          ← Risk score calculation
│   │   ├── baseline.py         ← RiskLevel thresholds
│   │   └── alerts.py           ← Escalation action logic
│   └── tts/
│       └── speaker.py          ← Piper TTS synthesis + playback (lazy singleton)
├── tests/
│   ├── test_pipeline.py        ← 44 tests: validator, router, logger, FastAPI
│   ├── test_llama_module.py    ← 40 tests: prompt, parser, client (mocked)
│   ├── test_orchestrator.py    ← 31 tests: end-to-end (all layers mocked)
│   ├── test_api.py             ← 91 tests: /health, /assess, /transcribe, /history
│   ├── test_scoring_engine.py  ← Scoring engine + alerts
│   ├── test_conversation.py    ← Topic detection + response generation
│   ├── test_whisper_layer.py   ← Whisper layer tests (hardware-marked)
│   └── test_tts.py             ← TTS tests (hardware-marked)
├── logs/
│   └── pipeline.log            ← Structured JSON request log (auto-created)
├── voice_health.py             ← Entry point: delegates to orchestrator.run_loop()
├── requirements.txt
└── README.md
```

## Setup Instructions

### Prerequisites

- Python 3.9+
- Git
- [Ollama](https://ollama.com/download) (for Llama 3)
- [ffmpeg](https://gyan.dev/ffmpeg/builds/) (for Whisper audio processing)

### Installation

```bash
# 1. Clone the repo
git clone <repo-url>
cd wellring-voice_agent

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate  # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Download Llama 3 via Ollama
ollama pull llama3

# 5. Download Piper voice model
# Go to https://rhasspy.github.io/piper-samples/
# Download en_US-ryan-high.onnx and en_US-ryan-high.onnx.json
# Place both files in the project root folder
```

### Run the voice agent

```bash
python voice_health.py
```

Press ENTER to speak. The agent will:
1. Count down 3-2-1 and listen for 8 seconds
2. Transcribe with Whisper
3. Classify with Llama 3
4. Score health risk
5. Speak the response back

### Run the FastAPI server

```bash
uvicorn src.main:app --reload --port 8000
```

- **Docs**: http://localhost:8000/docs
- **Health**: http://localhost:8000/health
- **Assess**: `POST /assess` — structured Llama payload → risk score
- **Transcribe**: `POST /transcribe` — raw speech text → Llama → risk score
- **History**: `GET /history` — recent pipeline log entries

### Run tests

```bash
# All no-hardware tests (280+ tests, ~45 s)
python -m pytest tests/ -q

# Individual suites
python -m pytest tests/test_pipeline.py -v         # validator / router / logger
python -m pytest tests/test_api.py -v              # FastAPI endpoints
python -m pytest tests/test_orchestrator.py -v     # end-to-end (mocked)
python -m pytest tests/test_scoring_engine.py -v   # risk scoring
python -m pytest tests/test_conversation.py -v     # chat handler
```

## Emergency Detection

The pipeline detects emergency symptoms via the scoring engine:

| Symptom              | Weight |
|----------------------|--------|
| chest_pain           | 40     |
| unconscious          | 50     |
| stroke_symptoms      | 45     |
| breathing_problem    | 35     |
| fall_detected        | 30     |
| fever                | 15     |
| dizziness            | 10     |
| medicine_missed      | 10     |

Risk levels: `LOW → MEDIUM → HIGH → CRITICAL`

On `CRITICAL`, the agent responds:
> **ALERT — Please call emergency services immediately on 112**

## API Reference

### `GET /health`

```json
{ "status": "ok", "service": "wellring-voice-agent", "version": "1.1.0" }
```

---

### `POST /assess`

Submit a pre-classified Llama payload (used by the orchestrator):

```json
{
  "intent":     "health_issue",
  "symptoms":   ["chest_pain", "dizziness"],
  "severity":   "high",
  "confidence": 0.92,
  "transcript": "I have chest pain and I feel dizzy."
}
```

**Response (200)**:
```json
{
  "request_id": "uuid-...",
  "intent":     "health_issue",
  "risk_level": "HIGH",
  "score":      72,
  "action": {
    "action":  "call_emergency",
    "message": "ALERT — Please call 112 immediately.",
    "steps":   ["Call 112", "Stay calm", "..."]
  },
  "destination": "health_issue"
}
```

---

### `POST /transcribe`

Submit raw speech text — Llama classifies it, then the full pipeline runs:

```json
{ "transcript": "I have been feeling dizzy since this morning." }
```

Returns the same `AssessmentResponse` as `POST /assess`.  
Use this endpoint when you have raw Whisper output and want the full pipeline.

---

### `GET /history?limit=20`

Returns the last N pipeline log entries (newest first, capped at 100):

```json
{
  "count": 3,
  "entries": [
    { "request_id": "uuid-...", "timestamp": "...", "intent": "health_issue", ... }
  ]
}
```


## Architecture

```
Microphone
    ↓
whisper_layer/          ← Stage 1: Record + Transcribe
    recorder.py         (sounddevice → WAV file)
    transcriber.py      (Whisper model → text)
    ↓
llama/                  ← Stage 2: Classify
    prompt.py           (system prompt + few-shot examples)
    client.py           (Ollama wrapper, retry + fallback)
    parser.py           (JSON extraction + field repair)
    ↓
pipeline/               ← Stage 3: Validate → Route → Log
    validator.py        (intent, severity, symptoms, confidence)
    router.py           (health_issue → scoring | general_chat → stub)
    logger.py           (structured JSON log → logs/pipeline.log)
    models.py           (Pydantic FastAPI request/response models)
    ↓
scoring_engine/         ← Stage 4: Score + Escalate
    rules.py            (symptom weights, severity bonuses)
    scoring.py          (calculate_score with confidence multiplier)
    baseline.py         (RiskLevel thresholds)
    alerts.py           (determine_action → emergency | urgent | monitor)
    ↓
tts/                    ← Stage 5: Synthesise + Speak
    speaker.py          (Piper TTS → WAV → playback)
    ↓
src/orchestrator.py     ← Ties all stages into run_once() / run_loop()
src/main.py             ← FastAPI: GET /health  POST /assess
```

## Project Structure

```
wellring-voice_agent/
├── src/
│   ├── main.py                 ← FastAPI app (GET /health, POST /assess)
│   ├── orchestrator.py         ← End-to-end run_once() / run_loop()
│   ├── whisper_layer/
│   │   ├── recorder.py         ← Microphone capture
│   │   └── transcriber.py      ← Whisper STT
│   ├── llama/
│   │   ├── prompt.py           ← System prompt + few-shot examples
│   │   ├── client.py           ← Ollama wrapper (retry + fallback)
│   │   └── parser.py           ← Defensive JSON extraction
│   ├── pipeline/
│   │   ├── validator.py        ← Field-level validation
│   │   ├── router.py           ← Intent-based dispatch
│   │   ├── logger.py           ← Structured JSON request log
│   │   └── models.py           ← Pydantic FastAPI models
│   ├── scoring_engine/
│   │   ├── rules.py            ← Symptom weights & severity bonuses
│   │   ├── scoring.py          ← Risk score calculation
│   │   ├── baseline.py         ← RiskLevel thresholds
│   │   └── alerts.py           ← Escalation action logic
│   └── tts/
│       └── speaker.py          ← Piper TTS synthesis + playback
├── tests/
│   ├── test_pipeline.py        ← 40 tests: validator, router, logger, FastAPI
│   ├── test_llama_module.py    ← 40 tests: prompt, parser, client (mocked)
│   ├── test_orchestrator.py    ← 26 tests: end-to-end (all layers mocked)
│   ├── test_whisper_layer.py   ← Whisper layer tests (requires audio device)
│   └── test_tts.py             ← TTS tests (requires Piper voice model)
├── logs/
│   └── pipeline.log            ← Structured JSON request log (auto-created)
├── requirements.txt
└── README.md
```

## Setup Instructions

### Prerequisites

- Python 3.9+
- Git
- [Ollama](https://ollama.com/download) (for Llama 3)
- [ffmpeg](https://gyan.dev/ffmpeg/builds/) (for Whisper audio processing)

### Installation

```bash
# 1. Clone the repo
git clone <repo-url>
cd wellring-voice_agent

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate  # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Download Llama 3 via Ollama
ollama pull llama3

# 5. Download Piper voice model
# Go to https://rhasspy.github.io/piper-samples/
# Download en_US-ryan-high.onnx and en_US-ryan-high.onnx.json
# Place both files in the project root folder
```

### Run the voice agent

```bash
python src/orchestrator.py
```

Press ENTER to speak. The agent will listen for 8 seconds, respond, and speak back.

### Run the FastAPI server

```bash
uvicorn src.main:app --reload --port 8000
```

- **Docs**: http://localhost:8000/docs
- **Health**: http://localhost:8000/health
- **Assess**: `POST /assess` with JSON body

### Run tests

```bash
# Pipeline + Llama + Orchestrator (no hardware needed)
python -m pytest tests/test_pipeline.py tests/test_llama_module.py tests/test_orchestrator.py -v

# All tests (requires microphone + Piper voice model)
python -m pytest tests/ -v
```

## Emergency Detection

The pipeline detects emergency symptoms via the scoring engine:

| Symptom          | Weight |
|------------------|--------|
| chest_pain       | 40     |
| unconscious      | 50     |
| stroke_symptoms  | 45     |
| difficulty_breathing | 35 |
| fallen           | 20     |
| bleeding         | 25     |

Risk levels: `LOW → MEDIUM → HIGH → CRITICAL`

On `CRITICAL`, the agent responds:
> **ALERT — Please call emergency services immediately on 112**

## API Reference

### `POST /assess`

```json
{
  "intent":     "health_issue",
  "symptoms":   ["chest_pain", "dizziness"],
  "severity":   "high",
  "confidence": 0.92
}
```

**Response (200)**:
```json
{
  "request_id": "uuid-...",
  "intent":     "health_issue",
  "risk_level": "HIGH",
  "score":      72,
  "action": {
    "action":     "call_emergency",
    "message":    "ALERT — Please call 112 immediately.",
    "steps":      ["Call 112", "Stay calm", "..."]
  }
}
```
