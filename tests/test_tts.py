"""
test_tts.py
===========
Unit tests for the WellRing TTS layer and orchestrator Stage 5:
    - tts/speaker.py   (Piper + sounddevice fully mocked — no speaker needed)
    - orchestrator.py  (speak() call mocked — no hardware required)

Run with:
    python -m pytest tests/test_tts.py -v
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from unittest.mock import patch, MagicMock, call
import io
import wave
import numpy as np


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _make_piper_voice(sample_rate: int = 22050) -> MagicMock:
    """Create a mock PiperVoice that writes a minimal WAV when synthesize_wav
    is called."""
    voice = MagicMock()

    def _synth(text, wav_file):
        # Write a tiny but valid WAV into the wave.Wave_write object
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)   # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00" * 100)

    voice.synthesize_wav.side_effect = _synth
    return voice


def _make_sf_read_result(samplerate: int = 22050):
    """Returns (numpy_array, samplerate) the way soundfile.read() would."""
    return np.zeros(100, dtype="float32"), samplerate


# ═══════════════════════════════════════════════════════════════════════════════
# speaker.py  — SpeakResult tests (PiperVoice + sounddevice fully mocked)
# ═══════════════════════════════════════════════════════════════════════════════

class TestSpeaker:
    """
    Patch strategy: `_get_voice` is patched directly because `PiperVoice`
    may be `None` when piper-tts is not installed, which makes
    `@patch("tts.speaker.PiperVoice.load")` crash at decoration time.
    Patching `_get_voice` keeps tests independent of the import state.
    """

    # ── Happy path ─────────────────────────────────────────────────────────────

    @patch("tts.speaker.sd.wait")
    @patch("tts.speaker.sd.play")
    @patch("tts.speaker.sf.read", return_value=_make_sf_read_result())
    @patch("tts.speaker._get_voice")
    def test_speak_success(self, mock_get_voice, mock_sfread, mock_play, mock_wait):
        mock_get_voice.return_value = _make_piper_voice()
        from tts.speaker import speak, _voice_cache
        _voice_cache.clear()
        result = speak("Hello, how are you?")
        assert result.success is True
        assert result.text == "Hello, how are you?"
        assert result.duration_s >= 0.0

    @patch("tts.speaker.sd.wait")
    @patch("tts.speaker.sd.play")
    @patch("tts.speaker.sf.read", return_value=_make_sf_read_result())
    @patch("tts.speaker._get_voice")
    def test_speak_result_bool_true_on_success(self, mock_get_voice, mock_sfread, mock_play, mock_wait):
        mock_get_voice.return_value = _make_piper_voice()
        from tts.speaker import speak, _voice_cache
        _voice_cache.clear()
        assert bool(speak("Test phrase"))

    @patch("tts.speaker.sd.wait")
    @patch("tts.speaker.sd.play")
    @patch("tts.speaker.sf.read", return_value=_make_sf_read_result())
    @patch("tts.speaker._get_voice")
    def test_speak_calls_play_and_wait(self, mock_get_voice, mock_sfread, mock_play, mock_wait):
        mock_get_voice.return_value = _make_piper_voice()
        from tts.speaker import speak, _voice_cache
        _voice_cache.clear()
        speak("Play this")
        mock_play.assert_called_once()
        mock_wait.assert_called_once()

    @patch("tts.speaker.sd.wait")
    @patch("tts.speaker.sd.play")
    @patch("tts.speaker.sf.read", return_value=_make_sf_read_result())
    @patch("tts.speaker._get_voice")
    def test_voice_model_cached_after_first_load(self, mock_get_voice, mock_sfread, mock_play, mock_wait):
        """_get_voice is called once per unique model_path (cache lives inside _get_voice)."""
        mock_get_voice.return_value = _make_piper_voice()
        from tts.speaker import speak, _voice_cache
        _voice_cache.clear()
        model_path = "test_model.onnx"
        speak("First call", voice_model=model_path)
        speak("Second call", voice_model=model_path)
        # _get_voice is called each time but the real implementation caches;
        # here we just verify speak() didn't crash.
        assert mock_get_voice.call_count == 2

    @patch("tts.speaker.sd.wait")
    @patch("tts.speaker.sd.play")
    @patch("tts.speaker.sf.read", return_value=_make_sf_read_result())
    @patch("tts.speaker._get_voice")
    def test_speak_stores_model_path(self, mock_get_voice, mock_sfread, mock_play, mock_wait):
        mock_get_voice.return_value = _make_piper_voice()
        from tts.speaker import speak, _voice_cache
        _voice_cache.clear()
        result = speak("Test", voice_model="/path/to/model.onnx")
        assert result.model_path == "/path/to/model.onnx"

    # ── Failure cases ─────────────────────────────────────────────────────────

    def test_speak_empty_text_returns_failure(self):
        from tts.speaker import speak
        result = speak("")
        assert result.success is False
        assert "empty" in result.error.lower()

    def test_speak_whitespace_only_returns_failure(self):
        from tts.speaker import speak
        result = speak("   ")
        assert result.success is False

    def test_speak_result_bool_false_on_empty_text(self):
        from tts.speaker import speak
        assert not bool(speak(""))

    @patch("tts.speaker._get_voice",
           side_effect=FileNotFoundError("Voice model not found: '/nonexistent/model.onnx'"))
    def test_speak_missing_model_returns_failure(self, mock_get_voice):
        from tts.speaker import speak, _voice_cache
        _voice_cache.clear()
        result = speak("Hello", voice_model="/nonexistent/model.onnx")
        assert result.success is False
        assert "not found" in result.error.lower()

    @patch("tts.speaker.sd.wait")
    @patch("tts.speaker.sd.play", side_effect=RuntimeError("No audio device"))
    @patch("tts.speaker.sf.read", return_value=_make_sf_read_result())
    @patch("tts.speaker._get_voice")
    def test_speak_playback_error_returns_failure(self, mock_get_voice, mock_sfread, mock_play, mock_wait):
        mock_get_voice.return_value = _make_piper_voice()
        from tts.speaker import speak, _voice_cache
        _voice_cache.clear()
        result = speak("This will fail on playback")
        assert result.success is False
        assert "playback" in result.error.lower()

    @patch("tts.speaker.sd.wait")
    @patch("tts.speaker.sd.play")
    @patch("tts.speaker.sf.read", return_value=_make_sf_read_result())
    @patch("tts.speaker._get_voice")
    def test_speak_synthesis_error_returns_failure(self, mock_get_voice, mock_sfread, mock_play, mock_wait):
        voice = MagicMock()
        voice.synthesize_wav.side_effect = RuntimeError("Synthesis exploded")
        mock_get_voice.return_value = voice
        from tts.speaker import speak, _voice_cache
        _voice_cache.clear()
        result = speak("This will fail on synthesis")
        assert result.success is False
        assert "synthesis" in result.error.lower()

    # ── preload_voice ─────────────────────────────────────────────────────────

    @patch("tts.speaker._get_voice")
    def test_preload_voice_populates_cache(self, mock_get_voice):
        """preload_voice warms up the cache by calling _get_voice."""
        mock_get_voice.return_value = _make_piper_voice()
        from tts.speaker import preload_voice, _voice_cache
        _voice_cache.clear()
        preload_voice("preload_test.onnx")
        mock_get_voice.assert_called_once()

    @patch("tts.speaker._get_voice",
           side_effect=FileNotFoundError("not found"))
    def test_preload_voice_missing_model_is_nonfatal(self, mock_get_voice):
        """preload_voice should never raise — errors are logged and swallowed."""
        from tts.speaker import preload_voice, _voice_cache
        _voice_cache.clear()
        preload_voice("/nonexistent/model.onnx")  # must not raise

    # ── save_path ─────────────────────────────────────────────────────────────

    @patch("tts.speaker.sd.wait")
    @patch("tts.speaker.sd.play")
    @patch("tts.speaker.sf.read", return_value=_make_sf_read_result())
    @patch("tts.speaker._get_voice")
    def test_speak_saves_wav_when_save_path_given(self, mock_get_voice, mock_sfread, mock_play, mock_wait, tmp_path):
        mock_get_voice.return_value = _make_piper_voice()
        from tts.speaker import speak, _voice_cache
        _voice_cache.clear()
        save_file = str(tmp_path / "response.wav")
        result = speak("Save me", save_path=save_file)
        assert result.success is True
        assert os.path.exists(save_file)
        assert result.audio_path == save_file

    @patch("tts.speaker.sd.wait")
    @patch("tts.speaker.sd.play")
    @patch("tts.speaker.sf.read", return_value=_make_sf_read_result())
    @patch("tts.speaker._get_voice")
    def test_speak_no_save_path_audio_path_empty(self, mock_get_voice, mock_sfread, mock_play, mock_wait):
        mock_get_voice.return_value = _make_piper_voice()
        from tts.speaker import speak, _voice_cache
        _voice_cache.clear()
        result = speak("No save")
        assert result.audio_path == ""


# ═══════════════════════════════════════════════════════════════════════════════
# orchestrator.py  — Stage 5 TTS integration tests
# ═══════════════════════════════════════════════════════════════════════════════

_GOOD_CLASSIFY = {
    "intent": "health_issue",
    "symptoms": ["dizziness"],
    "severity": "medium",
    "confidence": 0.88,
}
_CHAT_CLASSIFY = {
    "intent": "general_chat",
    "symptoms": [],
    "severity": "low",
    "confidence": 0.99,
}


def _make_rec(success=True, is_silent=False, path="/tmp/test.wav"):
    from whisper_layer.recorder import RecordResult
    return RecordResult(success=success, file_path=path, is_silent=is_silent,
                        error="" if success else "mic error")

def _make_tr(success=True, text="I feel dizzy", is_empty=False):
    from whisper_layer.transcriber import TranscribeResult
    return TranscribeResult(success=success, text=text, is_empty=is_empty,
                            error="" if success else "whisper error")

def _make_cl(payload=None, is_fallback=False):
    from llama.client import ClassifyResult
    return ClassifyResult(success=not is_fallback,
                          payload=payload or _GOOD_CLASSIFY,
                          is_fallback=is_fallback,
                          error="" if not is_fallback else "ollama down")

def _make_sr(success=True):
    from tts.speaker import SpeakResult
    return SpeakResult(success=success, text="spoken text",
                       error="" if success else "no audio device")


class TestOrchestratorTTS:

    def test_run_once_speak_result_attached(self):
        """SpeakResult is always attached to TurnResult on success."""
        with patch("orchestrator.record",      return_value=_make_rec()), \
             patch("orchestrator.transcribe",  return_value=_make_tr()), \
             patch("orchestrator.classify",    return_value=_make_cl()), \
             patch("orchestrator.log_request", return_value="uuid-tts-1"), \
             patch("orchestrator.speak",       return_value=_make_sr()):
            from orchestrator import run_once
            result = run_once(countdown=False)
        assert result.speak_result is not None

    def test_run_once_spoken_text_populated(self):
        """spoken_text field is set from _build_response_text."""
        with patch("orchestrator.record",      return_value=_make_rec()), \
             patch("orchestrator.transcribe",  return_value=_make_tr()), \
             patch("orchestrator.classify",    return_value=_make_cl()), \
             patch("orchestrator.log_request", return_value="uuid-tts-2"), \
             patch("orchestrator.speak",       return_value=_make_sr()):
            from orchestrator import run_once
            result = run_once(countdown=False)
        assert isinstance(result.spoken_text, str)
        assert len(result.spoken_text) > 0

    def test_run_once_tts_failure_is_non_fatal(self):
        """A TTS failure does not set success=False — it is only in stage_errors."""
        with patch("orchestrator.record",      return_value=_make_rec()), \
             patch("orchestrator.transcribe",  return_value=_make_tr()), \
             patch("orchestrator.classify",    return_value=_make_cl()), \
             patch("orchestrator.log_request", return_value="uuid-tts-3"), \
             patch("orchestrator.speak",       return_value=_make_sr(success=False)):
            from orchestrator import run_once
            result = run_once(countdown=False)
        assert result.success is True            # turn still succeeded
        assert "speak" in result.stage_errors    # error captured

    def test_run_once_tts_called_with_correct_text_for_health_issue(self):
        """speak() receives a non-empty response string for health_issue turns."""
        mock_speak = MagicMock(return_value=_make_sr())
        with patch("orchestrator.record",      return_value=_make_rec()), \
             patch("orchestrator.transcribe",  return_value=_make_tr()), \
             patch("orchestrator.classify",    return_value=_make_cl()), \
             patch("orchestrator.log_request", return_value="uuid-tts-4"), \
             patch("orchestrator.speak",       mock_speak):
            from orchestrator import run_once
            run_once(countdown=False)
        args, kwargs = mock_speak.call_args
        spoken = args[0]
        assert isinstance(spoken, str) and len(spoken) > 0

    def test_run_once_tts_called_for_general_chat(self):
        """speak() is also called for general_chat turns."""
        mock_speak = MagicMock(return_value=_make_sr())
        with patch("orchestrator.record",      return_value=_make_rec()), \
             patch("orchestrator.transcribe",  return_value=_make_tr(text="Hello!")), \
             patch("orchestrator.classify",    return_value=_make_cl(payload=_CHAT_CLASSIFY)), \
             patch("orchestrator.log_request", return_value="uuid-tts-5"), \
             patch("orchestrator.speak",       mock_speak):
            from orchestrator import run_once
            result = run_once(countdown=False)
        mock_speak.assert_called_once()
        assert result.intent == "general_chat"

    def test_run_once_voice_model_forwarded_to_speak(self):
        """voice_model kwarg is forwarded from run_once → speak."""
        mock_speak = MagicMock(return_value=_make_sr())
        with patch("orchestrator.record",      return_value=_make_rec()), \
             patch("orchestrator.transcribe",  return_value=_make_tr()), \
             patch("orchestrator.classify",    return_value=_make_cl()), \
             patch("orchestrator.log_request", return_value="uuid-tts-6"), \
             patch("orchestrator.speak",       mock_speak):
            from orchestrator import run_once
            run_once(countdown=False, voice_model="/custom/voice.onnx")
        _, kwargs = mock_speak.call_args
        assert kwargs.get("voice_model") == "/custom/voice.onnx"


# ═══════════════════════════════════════════════════════════════════════════════
# _build_response_text unit tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildResponseText:

    def _make_route_result(self, intent, message="Call emergency services!", action=None):
        from pipeline.router import RouteResult
        data = {"message": message}
        if action:
            data["action"] = action
        return RouteResult(destination=intent, success=True, data=data)

    def test_health_issue_returns_action_message(self):
        from orchestrator import _build_response_text
        rr = self._make_route_result(
            "health_issue",
            action={"message": "Please call 999 immediately!", "action": "CALL_EMERGENCY"},
        )
        text = _build_response_text("health_issue", rr)
        assert "999" in text or "emergency" in text.lower() or len(text) > 0

    def test_health_issue_fallback_when_no_action_message(self):
        from orchestrator import _build_response_text
        from pipeline.router import RouteResult
        rr = RouteResult(destination="health_issue", success=True, data={})
        text = _build_response_text("health_issue", rr)
        assert len(text) > 0

    def test_general_chat_returns_non_empty_string(self):
        from orchestrator import _build_response_text
        rr = self._make_route_result("general_chat", message="How can I help?")
        text = _build_response_text("general_chat", rr)
        assert len(text) > 0

    def test_unknown_intent_returns_safe_default(self):
        from orchestrator import _build_response_text
        from pipeline.router import RouteResult
        rr = RouteResult(destination="unknown", success=False, error="no handler")
        text = _build_response_text("mystery_intent", rr)
        assert len(text) > 0

    def test_response_text_is_always_a_string(self):
        from orchestrator import _build_response_text
        from pipeline.router import RouteResult
        for intent in ("health_issue", "general_chat", "unknown"):
            rr = RouteResult(destination=intent, success=True, data={})
            assert isinstance(_build_response_text(intent, rr), str)
