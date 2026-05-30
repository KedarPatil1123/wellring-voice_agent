import sounddevice as sd
import soundfile as sf
import numpy as np

#Audio Settings
DURATION = 5
SAMPLE_RATE = 16000  # Hz (best for Whisper)

print("Recording in 3 seconds...")
print("3...")
import time
time.sleep(1)
print("2...")
time.sleep(1)
print("1...")
time.sleep(1)

print("SPEAK NOW")
recording = sd.rec(
    int(DURATION * SAMPLE_RATE),
    samplerate=SAMPLE_RATE,
    channels=1,
    dtype='int16'
)
sd.wait()  # Wait until recording is done
print("Recording done!")

# Save the recording
sf.write("mic_test.wav", recording, SAMPLE_RATE)
print("Saved as mic_test.wav — play it to check!")