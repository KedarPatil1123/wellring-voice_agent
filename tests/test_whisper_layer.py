"""
test_whisper_layer.py
=====================
Unit tests for the WellRing Whisper layer and orchestrator:
    - whisper_layer/recorder.py
    - whisper_layer/transcriber.py
    - orchestrator.py             (all hardware mocked — no mic / GPU needed)

Run with:
    python -m pytest tests/test_whisper_layer.py -v
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pytest
from unittest.mock import patch, MagicMock, call


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def silent_audio():
    """All-zero int16 array — below silence threshold."""
    return np.zeros((16_000 * 8, 1), dtype="int16")

@pytest.fixture
def noisy_audio():
    """Non-silent int16 array with realistic RMS."""
    rng = np.random.default_rng(42)
    return (rng.integers(-5000, 5000, size=(16_000 * 8, 1), dtype=np.int16))

@pytest.fixture
def tmp_wav(tmp_path):
    """A real empty WAV file path (soundfile creates it)."""
    import soundfile as sf
    path = str(tmp_path / "test.wav")
    sf.write(path, np.zeros((16_000, 1), dtype="int16"), 16_000)
    return path


# ═══════════════════════════════════════════════════════════════════════════════
# recorder.py tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestRecorder:

    @patch("whisper_layer.recorder.sf.write")
    @patch("whisper_layer.recorder.sd.wait")
    @patch("whisper_layer.recorder.sd.rec")
    def test_record_success(self, mock_rec, mock_wait, mock_write, noisy_audio, tmp_path):
        mock_rec.return_value = noisy_audio
        from whisper_layer.recorder import record
        result = record(
            output_path=str(tmp_path / "out.wav"),
            countdown=False,
        )
        assert result.success is True
        assert result.file_path.endswith(".wav")

    @patch("whisper_layer.recorder.sf.write")
    @patch("whisper_layer.recorder.sd.wait")
    @patch("whisper_layer.recorder.sd.rec")
    def test_record_silent_audio_flagged(self, mock_rec, mock_wait, mock_write, silent_audio, tmp_path):
        mock_rec.return_value = silent_audio
        from whisper_layer.recorder import record
        result = record(output_path=str(tmp_path / "out.wav"), countdown=False)
        assert result.is_silent is True
        assert result.success is True   # saved successfully even if silent

    @patch("whisper_layer.recorder.sd.rec", side_effect=OSError("No microphone"))
    def test_record_device_error_returns_failure(self, mock_rec, tmp_path):
        from whisper_layer.recorder import record
        result = record(output_path=str(tmp_path / "out.wav"), countdown=False)
        assert result.success is False
        assert "sounddevice" in result.error.lower() or "microphone" in result.error.lower()

    @patch("whisper_layer.recorder.sf.write")
    @patch("whisper_layer.recorder.sd.wait")
    @patch("whisper_layer.recorder.sd.rec")
    def test_record_uses_correct_sample_rate(self, mock_rec, mock_wait, mock_write, noisy_audio, tmp_path):
        mock_rec.return_value = noisy_audio
        from whisper_layer.recorder import record, SAMPLE_RATE
        record(output_path=str(tmp_path / "out.wav"), countdown=False, sample_rate=SAMPLE_RATE)
        _, kwargs = mock_rec.call_args
        assert kwargs.get("samplerate") == SAMPLE_RATE or mock_rec.call_args[0][1] == SAMPLE_RATE

    @patch("whisper_layer.recorder.sf.write")
    @patch("whisper_layer.recorder.sd.wait")
    @patch("whisper_layer.recorder.sd.rec")
    def test_record_duration_stored_in_result(self, mock_rec, mock_wait, mock_write, noisy_audio, tmp_path):
        mock_rec.return_value = noisy_audio
        from whisper_layer.recorder import record
        result = record(output_path=str(tmp_path / "out.wav"), countdown=False, duration=5)
        assert result.duration == 5

    @patch("whisper_layer.recorder.sf.write")
    @patch("whisper_layer.recorder.sd.wait")
    @patch("whisper_layer.recorder.sd.rec")
    def test_record_bool_true_on_success(self, mock_rec, mock_wait, mock_write, noisy_audio, tmp_path):
        mock_rec.return_value = noisy_audio
        from whisper_layer.recorder import record
        assert bool(record(output_path=str(tmp_path / "out.wav"), countdown=False))

    @patch("whisper_layer.recorder.sd.rec", side_effect=Exception("error"))
    def test_record_bool_false_on_failure(self, _, tmp_path):
        from whisper_layer.recorder import record
        assert not bool(record(output_path=str(tmp_path / "out.wav"), countdown=False))

    def test_silence_detection_zero_array(self, silent_audio):
        from whisper_layer.recorder import _is_silent
        assert _is_silent(silent_audio) is True

    def test_silence_detection_noisy_array(self, noisy_audio):
        from whisper_layer.recorder import _is_silent
        assert _is_silent(noisy_audio) is False


# ═══════════════════════════════════════════════════════════════════════════════
# transcriber.py tests
# ═══════════════════════════════════════════════════════════════════════════════

def _mock_whisper_model(text: str) -> MagicMock:
    """Create a mock whisper model that returns a given text."""
    model = MagicMock()
    model.transcribe.return_value = {"text": text, "segments": []}
    return model


class TestTranscriber:

    @patch("whisper_layer.transcriber.whisper.load_model")
    def test_transcribe_success(self, mock_load, tmp_wav):
        mock_load.return_value = _mock_whisper_model("I have chest pain")
        from whisper_layer import transcriber
        transcriber._model_cache.clear()
        result = transcriber.transcribe(tmp_wav)
        assert result.success is True
        assert result.text == "I have chest pain"

    @patch("whisper_layer.transcriber.whisper.load_model")
    def test_transcribe_empty_text_flagged(self, mock_load, tmp_wav):
        mock_load.return_value = _mock_whisper_model("   ")
        from whisper_layer import transcriber
        transcriber._model_cache.clear()
        result = transcriber.transcribe(tmp_wav)
        assert result.is_empty is True
        assert result.success is False

    def test_transcribe_missing_file_returns_failure(self):
        from whisper_layer.transcriber import transcribe
        result = transcribe("/nonexistent/path/audio.wav")
        assert result.success is False
        assert "not found" in result.error.lower()

    @patch("whisper_layer.transcriber.whisper.load_model")
    def test_transcribe_model_cached_after_first_load(self, mock_load, tmp_wav):
        mock_load.return_value = _mock_whisper_model("hello")
        from whisper_layer import transcriber
        transcriber._model_cache.clear()
        transcriber.transcribe(tmp_wav, model_size="base")
        transcriber.transcribe(tmp_wav, model_size="base")
        mock_load.assert_called_once()   # loaded only once

    @patch("whisper_layer.transcriber.whisper.load_model")
    def test_transcribe_result_has_model_size(self, mock_load, tmp_wav):
        mock_load.return_value = _mock_whisper_model("fever")
        from whisper_layer import transcriber
        transcriber._model_cache.clear()
        result = transcriber.transcribe(tmp_wav, model_size="base")
        assert result.model_size == "base"

    @patch("whisper_layer.transcriber.whisper.load_model")
    def test_transcribe_uses_fp16_false(self, mock_load, tmp_wav):
        model = _mock_whisper_model("test")
        mock_load.return_value = model
        from whisper_layer import transcriber
        transcriber._model_cache.clear()
        transcriber.transcribe(tmp_wav)
        _, kwargs = model.transcribe.call_args
        assert kwargs.get("fp16") is False

    @patch("whisper_layer.transcriber.whisper.load_model")
    def test_transcribe_uses_temperature_zero(self, mock_load, tmp_wav):
        model = _mock_whisper_model("test")
        mock_load.return_value = model
        from whisper_layer import transcriber
        transcriber._model_cache.clear()
        transcriber.transcribe(tmp_wav)
        _, kwargs = model.transcribe.call_args
        assert kwargs.get("temperature") == 0

    @patch("whisper_layer.transcriber.whisper.load_model")
    def test_transcribe_bool_true_on_success(self, mock_load, tmp_wav):
        mock_load.return_value = _mock_whisper_model("dizziness")
        from whisper_layer import transcriber
        transcriber._model_cache.clear()
        assert bool(transcriber.transcribe(tmp_wav))

    @patch("whisper_layer.transcriber.whisper.load_model")
    def test_transcribe_bool_false_on_empty(self, mock_load, tmp_wav):
        mock_load.return_value = _mock_whisper_model("")
        from whisper_layer import transcriber
        transcriber._model_cache.clear()
        assert not bool(transcriber.transcribe(tmp_wav))

    @patch("whisper_layer.transcriber.whisper.load_model")
    def test_preload_model_populates_cache(self, mock_load):
        mock_load.return_value = _mock_whisper_model("ok")
        from whisper_layer import transcriber
        transcriber._model_cache.clear()
        transcriber.preload_model("base")
        assert "base" in transcriber._model_cache

    @patch("whisper_layer.transcriber.whisper.load_model")
    def test_transcribe_duration_recorded(self, mock_load, tmp_wav):
        mock_load.return_value = _mock_whisper_model("test")
        from whisper_layer import transcriber
        transcriber._model_cache.clear()
        result = transcriber.transcribe(tmp_wav)
        assert result.duration_s >= 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# orchestrator.py tests  (all I/O mocked)
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


class TestOrchestrator:

    def test_run_once_success(self):
        with patch("orchestrator.record",      return_value=_make_rec()), \
             patch("orchestrator.transcribe",  return_value=_make_tr()), \
             patch("orchestrator.classify",    return_value=_make_cl()), \
             patch("orchestrator.log_request", return_value="test-uuid-1234"):
            from orchestrator import run_once
            result = run_once(countdown=False)
        assert result.success is True
        assert result.transcript == "I feel dizzy"
        assert result.risk_level in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    def test_run_once_record_failure(self):
        with patch("orchestrator.record", return_value=_make_rec(success=False)):
            from orchestrator import run_once
            result = run_once(countdown=False)
        assert result.success is False
        assert "record" in result.stage_errors

    def test_run_once_silent_recording(self):
        with patch("orchestrator.record", return_value=_make_rec(is_silent=True)):
            from orchestrator import run_once
            result = run_once(countdown=False)
        assert result.success is False
        assert "record" in result.stage_errors

    def test_run_once_empty_transcript(self):
        with patch("orchestrator.record",     return_value=_make_rec()), \
             patch("orchestrator.transcribe", return_value=_make_tr(success=False, text="", is_empty=True)):
            from orchestrator import run_once
            result = run_once(countdown=False)
        assert result.success is False
        assert "transcribe" in result.stage_errors

    def test_run_once_llama_fallback_still_continues(self):
        """Fallback should not abort; pipeline should still run."""
        with patch("orchestrator.record",      return_value=_make_rec()), \
             patch("orchestrator.transcribe",  return_value=_make_tr()), \
             patch("orchestrator.classify",    return_value=_make_cl(is_fallback=True)), \
             patch("orchestrator.log_request", return_value="uuid-fallback"):
            from orchestrator import run_once
            result = run_once(countdown=False)
        assert "classify" in result.stage_errors
        assert result.success is True

    def test_run_once_general_chat_intent(self):
        with patch("orchestrator.record",      return_value=_make_rec()), \
             patch("orchestrator.transcribe",  return_value=_make_tr(text="Hello!")), \
             patch("orchestrator.classify",    return_value=_make_cl(payload=_CHAT_CLASSIFY)), \
             patch("orchestrator.log_request", return_value="uuid-chat"):
            from orchestrator import run_once
            result = run_once(countdown=False)
        assert result.success is True
        assert result.intent == "general_chat"
        assert result.risk_level is None

    def test_run_once_request_id_populated(self):
        with patch("orchestrator.record",      return_value=_make_rec()), \
             patch("orchestrator.transcribe",  return_value=_make_tr()), \
             patch("orchestrator.classify",    return_value=_make_cl()), \
             patch("orchestrator.log_request", return_value="uuid-ok"):
            from orchestrator import run_once
            result = run_once(countdown=False)
        assert result.request_id == "uuid-ok"

    def test_run_once_bool_true_on_success(self):
        with patch("orchestrator.record",      return_value=_make_rec()), \
             patch("orchestrator.transcribe",  return_value=_make_tr()), \
             patch("orchestrator.classify",    return_value=_make_cl()), \
             patch("orchestrator.log_request", return_value="uuid-ok"):
            from orchestrator import run_once
            assert bool(run_once(countdown=False))

    def test_run_once_bool_false_on_failure(self):
        with patch("orchestrator.record", return_value=_make_rec(success=False)):
            from orchestrator import run_once
            assert not bool(run_once(countdown=False))

    def test_run_once_stage_results_attached(self):
        with patch("orchestrator.record",      return_value=_make_rec()), \
             patch("orchestrator.transcribe",  return_value=_make_tr()), \
             patch("orchestrator.classify",    return_value=_make_cl()), \
             patch("orchestrator.log_request", return_value="uuid-ok"):
            from orchestrator import run_once
            result = run_once(countdown=False)
        assert result.record_result     is not None
        assert result.transcribe_result is not None
        assert result.classify_result   is not None
