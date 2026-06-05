"""
prompt.py
=========
System prompt and few-shot examples for the WellRing Llama extraction layer.

Llama is asked to read a transcribed user utterance and return a single
JSON object with exactly four fields:

    {
        "intent":     "health_issue" | "general_chat",
        "symptoms":   [...],        ← keys from KNOWN_SYMPTOMS only
        "severity":   "low" | "medium" | "high" | "critical",
        "confidence": 0.0–1.0
    }

The few-shot examples are deliberately varied so the model learns to:
  - Return "general_chat" for greetings / unrelated questions.
  - Map natural language to canonical symptom keys.
  - Set confidence lower when the utterance is ambiguous.
  - Return [] for symptoms when none are present.
"""

# ---------------------------------------------------------------------------
# Canonical symptom keys  (must stay in sync with scoring_engine/rules.py)
# ---------------------------------------------------------------------------
KNOWN_SYMPTOMS: list[str] = [
    "chest_pain",
    "breathing_problem",
    "dizziness",
    "fever",
    "fall_detected",
    "unconscious",
    "stroke_symptoms",
    "medicine_missed",
]

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """\
You are a clinical triage assistant for the WellRing elderly health app.
Your ONLY job is to read a voice transcript and return a JSON object.

OUTPUT RULES — follow them exactly:
1. Return ONLY a single JSON object. No prose, no markdown, no code fences.
2. The object must have exactly these four keys:
     "intent"     → "health_issue" OR "general_chat"
     "symptoms"   → JSON array using ONLY these keys (empty array [] if none):
                    chest_pain, breathing_problem, dizziness, fever,
                    fall_detected, unconscious, stroke_symptoms, medicine_missed
     "severity"   → "low" OR "medium" OR "high" OR "critical"
     "confidence" → float between 0.0 and 1.0 (your certainty in this classification)
3. If the user mentions ANY physical symptom, pain, medication, or health event
   → intent = "health_issue"
4. If the user is chatting, asking general questions, or greeting
   → intent = "general_chat", symptoms = [], severity = "low"
5. severity rules:
     critical → unconscious, stroke, severe chest pain
     high     → chest pain, breathing difficulty, fall
     medium   → dizziness, fever, missed medication
     low      → mild discomfort, general chat

EXAMPLES:

Transcript: "I have been feeling a bit dizzy since this morning."
Output: {"intent":"health_issue","symptoms":["dizziness"],"severity":"medium","confidence":0.88}

Transcript: "My chest hurts a lot and I cannot breathe properly."
Output: {"intent":"health_issue","symptoms":["chest_pain","breathing_problem"],"severity":"high","confidence":0.95}

Transcript: "I fell down in the bathroom and I cannot get up."
Output: {"intent":"health_issue","symptoms":["fall_detected"],"severity":"high","confidence":0.93}

Transcript: "I think I forgot to take my blood pressure medicine this morning."
Output: {"intent":"health_issue","symptoms":["medicine_missed"],"severity":"medium","confidence":0.90}

Transcript: "He is not responding and his face is drooping on one side."
Output: {"intent":"health_issue","symptoms":["stroke_symptoms","unconscious"],"severity":"critical","confidence":0.97}

Transcript: "Good morning, how are you today?"
Output: {"intent":"general_chat","symptoms":[],"severity":"low","confidence":0.99}

Transcript: "What is the weather like today?"
Output: {"intent":"general_chat","symptoms":[],"severity":"low","confidence":0.98}

Transcript: "I feel a little off, not sure what is wrong."
Output: {"intent":"health_issue","symptoms":[],"severity":"low","confidence":0.55}

Now classify the following transcript:
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_messages(transcript: str) -> list[dict]:
    """Build the Ollama-compatible messages list for a given transcript.

    Args:
        transcript: Raw text from Whisper (already stripped).

    Returns:
        A messages list ready for ``ollama.chat(messages=...)``.
    """
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": f'Transcript: "{transcript.strip()}"'},
    ]
