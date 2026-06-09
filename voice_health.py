import google.generativeai as genai
import typing_extensions as typing
import whisper
import wave
import sounddevice as sd
import soundfile as sf
import time
import os
import json
import httpx
from piper import PiperVoice
from dotenv import load_dotenv

load_dotenv()

# Settings
DURATION = 8
SAMPLE_RATE = 16000

# Counter for recordings
counter = 1

print("Loading Whisper...")
whisper_model = whisper.load_model("base")

print("Loading English voice...")
voice_en = PiperVoice.load("en_US-ryan-high.onnx")

print("\nAll models loaded! Ready!\n")

# Setup Gemini
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("WARNING: GEMINI_API_KEY environment variable is not set. Gemini API calls will fail.")
genai.configure(api_key=api_key)

# Health assistant system prompt
system_prompt = """You are a health assistant for elderly people.

STRICT RULES:
1. If the user mentions chest pain, heart, breathing, fallen, unconscious, bleeding, stroke - start with: ALERT - Please call emergency services immediately on 112
2. After alert, ask follow up questions calmly
3. Always speak in very simple short sentences
4. Never use difficult medical words
5. Be warm and caring like a family member"""

# Schema for structured output extraction
class SymptomExtraction(typing.TypedDict):
    intent: str
    symptoms: list[str]
    severity: str
    confidence: float

# Initialize Gemini models
extractor_model = genai.GenerativeModel("gemini-1.5-flash")
conversation_model = genai.GenerativeModel(
    "gemini-1.5-flash",
    system_instruction=system_prompt
)
chat = conversation_model.start_chat()


def record_audio():
    """Record audio from microphone"""
    global counter
    
    print("3...")
    time.sleep(1)
    print("2...")
    time.sleep(1)
    print("1...")
    time.sleep(1)
    print("SPEAK NOW! (8 seconds)")
    
    recording = sd.rec(
        int(DURATION * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype='int16'
    )
    sd.wait()
    
    # Ensure audios directory exists
    os.makedirs("audios", exist_ok=True)
    filename = f"audios/recording{counter}.wav"
    sf.write(filename, recording, SAMPLE_RATE)
    print("Processing...")
    return filename


def transcribe(filename):
    """Convert audio to text using Whisper"""
    result = whisper_model.transcribe(
        filename,
        language="en",
        fp16=False,
        temperature=0
    )
    return result['text'].strip()


def speak(text):
    """Convert text to speech using Piper"""
    with wave.open("audios/response.wav", "wb") as wav_file:
        voice_en.synthesize_wav(text, wav_file)
    os.system("aplay audios/response.wav")


def ask_gemini(user_text):
    """Send message to Gemini and get response"""
    print("Assessing risk...")
    context_for_gemini = ""
    try:
        # 1. Extract JSON using Gemini Structured Outputs
        extract_result = extractor_model.generate_content(
            f"Extract health symptoms from the user's input.\nUser input: {user_text}",
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=SymptomExtraction,
            )
        )
        parsed = json.loads(extract_result.text)
        print(f"[LLM Extracted] {parsed}")

        intent = parsed.get("intent", "general")
        severity = parsed.get("severity", "").lower().strip()
        symptoms = parsed.get("symptoms", [])
        confidence = parsed.get("confidence", 1.0)

        valid_severities = {"low", "medium", "high", "critical"}
        has_required = (
            intent == "health_issue"
            and severity in valid_severities
            and isinstance(symptoms, list)
        )

        if has_required:
            # 2. Call FastAPI backend (with normalised severity)
            payload = {
                "intent": intent,
                "symptoms": symptoms,
                "severity": severity,
                "confidence": confidence,
            }
            r = httpx.post(
                "https://wellring-backend.onrender.com/assess",
                json=payload,
                headers={"X-API-Key": "wellring-secure-2026"},
                timeout=5.0
            )
            if r.status_code == 200:
                assess_data = r.json()
                context_for_gemini = (
                    f"\n[SYSTEM: User Risk Level is {assess_data['risk_level']}. "
                    f"Action: {assess_data['action']}. "
                    f"Steps: {', '.join(assess_data['steps'])}]"
                )
            else:
                print(f"[API Error] {r.status_code}: {r.text}")
        else:
            print("[Skipping /assess — general conversation or incomplete extraction]")
    except Exception as e:
        print(f"[Assessment Error - is the server running or Gemini key valid?] {e}")

    # 3. Generate conversational response with injected backend context
    try:
        response = chat.send_message(user_text + context_for_gemini)
        reply = response.text
    except Exception as e:
        print(f"[Gemini Error] {e}")
        reply = "I'm sorry, I'm having trouble connecting to my brain."

    return reply


if __name__ == "__main__":
    print("Voice Health Assistant Ready!")
    print("Press ENTER to speak or type 'quit' to exit\n")

    while True:
        user_input = input("Press ENTER to speak (or type 'quit'): ")
        
        if user_input.lower() == "quit":
            print("Goodbye! Stay safe!")
            break
        
        # Record and transcribe
        filename = record_audio()
        user_text = transcribe(filename)
        print(f"You said: {user_text}")
        
        counter += 1
        
        # Don't call Gemini if nothing was heard
        if not user_text:
            print("Didn't catch that! Please try again.")
            continue
        
        # Get AI response
        reply = ask_gemini(user_text)
        print(f"\nAssistant: {reply}\n")
        
        # Speak the response
        speak(reply)