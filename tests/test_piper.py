from piper import PiperVoice
import wave

# Test English voice
print("Testing English voice")
voice_en = PiperVoice.load("en_US-ryan-high.onnx")

with wave.open("test_english.wav", "wb") as wav_file:
    voice_en.synthesize_wav("Hello! I am your health assistant. How are you feeling today?", wav_file)

print("English audio saved!")

# Test Hindi voice
print("Testing Hindi voice")
voice_hi = PiperVoice.load("hi_IN-priyamvada-medium.onnx")

with wave.open("test_hindi.wav", "wb") as wav_file:
    voice_hi.synthesize_wav("नमस्ते! मैं आपका स्वास्थ्य सहायक हूं। आप कैसा महसूस कर रहे हैं?", wav_file)

print("Hindi audio saved!")