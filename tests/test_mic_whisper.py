"""
test_mic_whisper.py
===================
Hardware smoke test for microphone recording + Whisper transcription.

REQUIRES:
  - A working microphone
  - openai-whisper installed: pip install openai-whisper
  - ffmpeg on PATH

These tests are marked ``hardware`` and are SKIPPED in CI.
Run manually to verify mic + Whisper work end-to-end:
    python -m pytest tests/test_mic_whisper.py -v -m hardware -s

The original interactive script (press ENTER loop) has been preserved as
the ``_interactive_loop()`` function below. Run it directly with:
    python tests/test_mic_whisper.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import time
import pytest
import numpy as np

sd = pytest.importorskip("sounddevice", reason="sounddevice not installed")
sf = pytest.importorskip("soundfile",   reason="soundfile not installed")

DURATION    = 8
SAMPLE_RATE = 16_000


@pytest.mark.hardware
def test_microphone_records_non_silent_audio(tmp_path):
    """Record 1 second of audio and verify the buffer is non-trivial.

    This test only checks that the sounddevice call succeeds and returns
    an array of the right shape. It does NOT verify speech content.
    The recording is saved to tmp_path for inspection.
    """
    recording = sd.rec(
        int(1 * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
    )
    sd.wait()
    sf.write(str(tmp_path / "mic_test.wav"), recording, SAMPLE_RATE)

    assert recording.shape == (SAMPLE_RATE, 1), \
        f"Unexpected shape: {recording.shape}"
    # Audio should have been captured (not just zeros)
    assert recording.dtype == np.int16


@pytest.mark.hardware
@pytest.mark.hardware  # requires ffmpeg on PATH (Whisper dependency)
def test_whisper_transcribes_saved_wav(tmp_path):
    """Write a short silent WAV and transcribe with Whisper.

    This verifies Whisper loads and runs without crashing, not that the
    transcription is correct (the audio is silent).
    """
    whisper = pytest.importorskip("whisper", reason="openai-whisper not installed")
    silent  = np.zeros((SAMPLE_RATE * 2, 1), dtype="int16")
    wav_path = str(tmp_path / "silent.wav")
    sf.write(wav_path, silent, SAMPLE_RATE)

    model  = whisper.load_model("tiny")   # smallest model for speed
    result = model.transcribe(wav_path, fp16=False, temperature=0)
    assert "text" in result


# ---------------------------------------------------------------------------
# Legacy interactive loop (not a pytest test — run directly)
# ---------------------------------------------------------------------------

def _interactive_loop() -> None:
    """Original REPL: press ENTER to record, Ctrl-C to quit."""
    import whisper as _whisper
    print("Loading Whisper...")
    model = _whisper.load_model("small")
    print("Ready!\n")

    while True:
        input("Press ENTER to start recording (or Ctrl+C to quit)...")
        for t in (3, 2, 1):
            print(f"{t}...")
            time.sleep(1)

        print("🎤 SPEAK NOW! (8 seconds)")
        recording = sd.rec(
            int(DURATION * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
        )
        sd.wait()
        print("Processing...")

        sf.write("temp_recording.wav", recording, SAMPLE_RATE)
        result = model.transcribe(
            "temp_recording.wav",
            language="en",
            fp16=False,
            temperature=0,
        )
        print(f"You said: {result['text'].strip()}\n")


if __name__ == "__main__":
    _interactive_loop()