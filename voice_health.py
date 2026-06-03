import ollama
import whisper
import wave
import sounddevice as sd
import soundfile as sf
import time
import os
import json
import httpx
from piper import PiperVoice

# Settings
DURATION = 8
SAMPLE_RATE = 16000

# Counter for recordings
counter = 1

# Load all models
print("Loading Whisper...")
whisper_model = whisper.load_model("base")

print("Loading English voice...")
voice_en = PiperVoice.load("en_US-ryan-high.onnx")

print("\nAll models loaded! Ready!\n")

# Health assistant system prompt
system_prompt = """You are a health assistant for elderly people.

STRICT RULES:
1. If the user mentions chest pain, heart, breathing, fallen, unconscious, bleeding, stroke - start with: ALERT - Please call emergency services immediately on 112
2. After alert, ask follow up questions calmly
3. Always speak in very simple short sentences
4. Never use difficult medical words
5. Be warm and caring like a family member"""

# Conversation history
conversation = [{"role": "system", "content": system_prompt}]

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

def ask_llama(user_text):
    """Send message to Llama 3 and get response"""
    # 1. Extract JSON
    extract_msgs = [
        {"role": "system", "content": """Extract health symptoms from the user's input.
Output ONLY JSON matching this format:
{
  "intent": "health_issue" or "general",
  "symptoms": ["chest_pain", "breathing_problem", "dizziness", "fever", "medicine_missed", "fall_detected", "unconscious", "stroke_symptoms"],
  "severity": "low", "medium", "high", or "critical",
  "confidence": 0.95
}"""},
        {"role": "user", "content": user_text}
    ]
    
    print("Assessing risk...")
    extraction = ollama.chat(model="llama3", messages=extract_msgs, format="json")
    context_for_llama = ""
    try:
        parsed = json.loads(extraction['message']['content'])
        print(f"[LLM Extracted] {parsed}")

        # Only call the backend when it's a real health issue with required fields
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
            r = httpx.post("http://localhost:8000/assess", json=payload, timeout=5.0)
            if r.status_code == 200:
                assess_data = r.json()
                context_for_llama = (
                    f"\n[SYSTEM: User Risk Level is {assess_data['risk_level']}. "
                    f"Action: {assess_data['action']}. "
                    f"Steps: {', '.join(assess_data['steps'])}]"
                )
            else:
                print(f"[API Error] {r.status_code}: {r.text}")
        else:
            print("[Skipping /assess — general conversation or incomplete extraction]")
    except Exception as e:
        print(f"[Assessment Error - is the server running?] {e}")

    # 3. Generate conversational response
    conversation.append({"role": "user", "content": user_text + context_for_llama})
    
    response = ollama.chat(
        model="llama3",
        messages=conversation
    )
    
    reply = response['message']['content']
    conversation.append({"role": "assistant", "content": reply})
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
        
        # Don't call Llama if nothing was heard
        if not user_text:
            print("Didn't catch that! Please try again.")
            continue
        
        # Get AI response
        reply = ask_llama(user_text)
        print(f"\nAssistant: {reply}\n")
        
        # Speak the response
        speak(reply)