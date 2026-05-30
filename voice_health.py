import ollama
import whisper
import wave
from piper import PiperVoice
import os

# Load models
print("Loading Whisper")
whisper_model = whisper.load_model("base")

print("Loading English voice")
voice_en = PiperVoice.load("en_US-ryan-high.onnx")

print("Loading Hindi voice")
voice_hi = PiperVoice.load("hi_IN-priyamvada-medium.onnx")

print("\nAll models loaded! Ready!\n")

# Health assistant system prompt
system_prompt = """You are a health assistant for elderly people.

STRICT RULES:
1. If the user mentions chest pain, heart, breathing, fallen, unconscious, bleeding, stroke - start with: ALERT - Please call emergency services immediately on 112
2. After alert, ask follow up questions calmly
3. Always speak in very simple short sentences
4. Never use difficult medical words
5. Be warm and caring like a family member"""

def speak(text, language="english"):
    """Convert text to speech using Piper"""
    if language == "hindi":
        voice = voice_hi
    else:
        voice = voice_en
    
    with wave.open("response.wav", "wb") as wav_file:
        voice.synthesize_wav(text, wav_file)
    
    os.system("start response.wav")

def transcribe(audio_path):
    """Convert audio to text using Whisper"""
    result = whisper_model.transcribe(audio_path)
    return result['text']

print("Voice Health Assistant Ready!")
print("Type your message OR type 'audio: path/to/file' for voice input")
print("Type 'quit' to exit\n")

while True:
    user_input = input("You: ")
    
    if user_input.lower() == "quit":
        print("Goodbye! Stay safe!")
        break
    
    # Check if audio input
    if user_input.startswith("audio:"):
        audio_path = user_input.replace("audio:", "").strip()
        print("Transcribing...")
        user_text = transcribe(audio_path)
        print(f"You said: {user_text}")
    else:
        user_text = user_input
    
    # Send to Llama 3
    response = ollama.chat(
        model="llama3",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text}
        ]
    )
    
    reply = response['message']['content']
    print(f"\nAssistant: {reply}\n")
    
    # Speak the response
    speak(reply)