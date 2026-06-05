"""
test_piper.py
=============
Hardware smoke test for the Piper TTS voice synthesis.

REQUIRES:
  - piper-tts installed:  pip install piper-tts
  - en_US-ryan-high.onnx in the project root
  - hi_IN-priyamvada-medium.onnx in the project root (optional)
  - A working audio output device

These tests are marked ``hardware`` and are SKIPPED in CI.
Run manually on a machine with Piper installed:
    python -m pytest tests/test_piper.py -v -m hardware
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import wave
import pytest

# ── Skip the entire module when piper-tts is not installed ───────────────────
piper = pytest.importorskip("piper", reason="piper-tts not installed")
PiperVoice = piper.PiperVoice

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_EN_MODEL  = os.path.join(_PROJECT_ROOT, "en_US-ryan-high.onnx")
_HI_MODEL  = os.path.join(_PROJECT_ROOT, "hi_IN-priyamvada-medium.onnx")


@pytest.mark.hardware
@pytest.mark.skipif(not os.path.isfile(_EN_MODEL),
                    reason=f"English voice model not found: {_EN_MODEL}")
def test_english_voice_synthesis(tmp_path):
    """Synthesise a short phrase to a WAV file using the English Piper model."""
    voice = PiperVoice.load(_EN_MODEL)
    out = str(tmp_path / "test_english.wav")
    with wave.open(out, "wb") as wav_file:
        voice.synthesize_wav(
            "Hello! I am your health assistant. How are you feeling today?",
            wav_file,
        )
    assert os.path.isfile(out)
    assert os.path.getsize(out) > 44  # larger than a bare WAV header


@pytest.mark.hardware
@pytest.mark.skipif(not os.path.isfile(_HI_MODEL),
                    reason=f"Hindi voice model not found: {_HI_MODEL}")
def test_hindi_voice_synthesis(tmp_path):
    """Synthesise a short phrase to a WAV file using the Hindi Piper model."""
    voice = PiperVoice.load(_HI_MODEL)
    out = str(tmp_path / "test_hindi.wav")
    with wave.open(out, "wb") as wav_file:
        voice.synthesize_wav(
            "नमस्ते! मैं आपका स्वास्थ्य सहायक हूं। आप कैसा महसूस कर रहे हैं?",
            wav_file,
        )
    assert os.path.isfile(out)
    assert os.path.getsize(out) > 44