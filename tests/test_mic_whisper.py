import sounddevice as sd
import soundfile as sf
import whisper
import time
import numpy as np

# Settings
DURATION = 8  # increased to 8 seconds
SAMPLE_RATE = 16000

# Load Whisper
print("Loading Whisper...")
model = whisper.load_model("small")  # upgraded from base to small
print("Ready!\n")

while True:
    input("Press ENTER to start recording (or Ctrl+C to quit)...")
    
    print("3...")
    time.sleep(1)
    print("2...")
    time.sleep(1)
    print("1...")
    time.sleep(1)
    
    print("🎤 SPEAK NOW! (8 seconds)")
    recording = sd.rec(
        int(DURATION * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype='int16'
    )
    sd.wait()
    print("Processing...")
    
    # Save recording
    sf.write("temp_recording.wav", recording, SAMPLE_RATE)
    
    # Transcribe with Whisper
    result = model.transcribe(
        "temp_recording.wav",
        language="en",        # force English
        fp16=False,           # better accuracy on CPU
        temperature=0,        # more deterministic
    )
    text = result['text'].strip()
    
    print(f"You said: {text}\n")