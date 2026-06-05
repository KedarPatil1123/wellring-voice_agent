"""
speaker.py
==========
Piper TTS synthesis and audio playback for the WellRing voice agent.

Converts a text response string into spoken audio using the Piper TTS
engine and plays it back immediately via the system's default audio output.

Features:
    - Lazy singleton model load with an in-process cache (one load per voice)
    - Configurable voice model path via VOICE_MODEL env var or argument
    - Structured SpeakResult dataclass for error propagation
    - Playback via sounddevice (cross-platform, no external player needed)
    - Graceful fallback when Piper model file is missing

Public API:
    speak(text: str, voice_model: str | None) -> SpeakResult
    preload_voice(voice_model: str | None) -> None   ← warm up at startup

Environment variables:
    WELLRING_VOICE_MODEL   Path to the .onnx Piper voice file.
                           Defaults to  en_US-ryan-high.onnx  in the
                           project root.
"""

from __future__ import annotations

import io
import logging
import os
import time
import wave
from dataclasses import dataclass
from typing import Optional

_log = logging.getLogger("wellring.tts")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Resolve the default model path relative to the project root
_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

DEFAULT_VOICE_MODEL: str = os.environ.get(
    "WELLRING_VOICE_MODEL",
    os.path.join(_PROJECT_ROOT, "en_US-ryan-high.onnx"),
)

# Piper is imported at module level so tests can patch
# ``tts.speaker.PiperVoice`` reliably.
try:
    from piper import PiperVoice  # type: ignore[import-untyped]
except ImportError:
    PiperVoice = None  # type: ignore[assignment,misc]

# sounddevice / soundfile for cross-platform playback
try:
    import sounddevice as sd
    import soundfile as sf
except ImportError:
    sd = None  # type: ignore[assignment]
    sf = None  # type: ignore[assignment]

import numpy as np

# ---------------------------------------------------------------------------
# Singleton voice cache  {model_path: PiperVoice}
# ---------------------------------------------------------------------------

_voice_cache: dict[str, object] = {}


def _get_voice(model_path: str) -> object:
    """Return a cached PiperVoice, loading it on first call.

    Args:
        model_path: Absolute or relative path to the ``.onnx`` Piper model.

    Returns:
        A loaded :class:`PiperVoice` object.

    Raises:
        ImportError:  If ``piper-tts`` is not installed.
        FileNotFoundError: If the ``.onnx`` model file does not exist.
    """
    if PiperVoice is None:
        raise ImportError(
            "piper-tts is not installed. Run: pip install piper-tts"
        )
    if not os.path.isfile(model_path):
        raise FileNotFoundError(
            f"Piper voice model not found: '{model_path}'. "
            "Download it from https://rhasspy.github.io/piper-samples/ "
            "and place it in the project root."
        )
    if model_path not in _voice_cache:
        _log.info("Loading Piper voice model '%s' …", model_path)
        t0 = time.time()
        _voice_cache[model_path] = PiperVoice.load(model_path)
        _log.info("Piper model loaded in %.1f s", time.time() - t0)
    return _voice_cache[model_path]


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class SpeakResult:
    """Outcome of a single TTS + playback attempt.

    Attributes:
        success:      True when synthesis and playback both completed.
        text:         The input text that was synthesised.
        duration_s:   Wall-clock time for synthesis + playback in seconds.
        audio_path:   Path to the saved WAV file (``""`` if not saved).
        error:        Error description when success is False.
        model_path:   Which voice model was used.
    """
    success:    bool
    text:       str   = ""
    duration_s: float = 0.0
    audio_path: str   = ""
    error:      str   = ""
    model_path: str   = ""

    def __bool__(self) -> bool:
        return self.success


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def preload_voice(voice_model: Optional[str] = None) -> None:
    """Eagerly load the Piper voice model so the first ``speak()`` is instant.

    Call this at application startup (e.g. in FastAPI's lifespan event or
    at the top of :func:`orchestrator.run_loop`).

    Args:
        voice_model: Path to the ``.onnx`` Piper voice model.
                     Defaults to :data:`DEFAULT_VOICE_MODEL`.
    """
    model_path = voice_model or DEFAULT_VOICE_MODEL
    try:
        _get_voice(model_path)
    except Exception as exc:  # noqa: BLE001
        _log.warning("preload_voice failed (non-fatal): %s", exc)


def speak(
    text:        str,
    voice_model: Optional[str] = None,
    save_path:   Optional[str] = None,
) -> SpeakResult:
    """Synthesise *text* with Piper TTS and play it back immediately.

    Flow:
        1. Load (or retrieve cached) PiperVoice model.
        2. Synthesise WAV audio into an in-memory buffer.
        3. Optionally save the WAV to *save_path*.
        4. Play back the audio via ``sounddevice``.

    Args:
        text:        The text to synthesise.  Must be non-empty.
        voice_model: Path to the ``.onnx`` Piper voice model.
                     Defaults to :data:`DEFAULT_VOICE_MODEL`.
        save_path:   Optional path to write the output WAV file.
                     Useful for logging / debugging.

    Returns:
        A :class:`SpeakResult` with ``success``, ``duration_s``, and
        diagnostic fields.
    """
    model_path = voice_model or DEFAULT_VOICE_MODEL

    if not text or not text.strip():
        return SpeakResult(
            success=False,
            text=text,
            model_path=model_path,
            error="speak() called with empty text — nothing to synthesise.",
        )

    t0 = time.time()

    # ── 1. Load voice model ───────────────────────────────────────────────────
    try:
        voice = _get_voice(model_path)
    except (ImportError, FileNotFoundError) as exc:
        _log.error("Voice model load failed: %s", exc)
        return SpeakResult(
            success=False,
            text=text,
            model_path=model_path,
            error=str(exc),
        )
    except Exception as exc:  # noqa: BLE001
        _log.error("Unexpected error loading voice model: %s", exc)
        return SpeakResult(
            success=False,
            text=text,
            model_path=model_path,
            error=f"Voice model load error: {exc}",
        )

    # ── 2. Synthesise into in-memory buffer ───────────────────────────────────
    try:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav_out:
            voice.synthesize_wav(text.strip(), wav_out)
        buf.seek(0)
    except Exception as exc:  # noqa: BLE001
        _log.error("Piper synthesis failed: %s", exc)
        return SpeakResult(
            success=False,
            text=text,
            model_path=model_path,
            error=f"TTS synthesis error: {exc}",
        )

    # ── 3. Optionally save WAV to disk ────────────────────────────────────────
    audio_path = ""
    if save_path:
        try:
            os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
            buf.seek(0)
            with open(save_path, "wb") as fh:
                fh.write(buf.read())
            audio_path = save_path
            buf.seek(0)
            _log.debug("TTS audio saved → '%s'", save_path)
        except OSError as exc:
            _log.warning("Could not save TTS audio to '%s': %s", save_path, exc)

    # ── 4. Playback via sounddevice ───────────────────────────────────────────
    try:
        buf.seek(0)
        data, samplerate = sf.read(buf, dtype="float32")
        sd.play(data, samplerate)
        sd.wait()  # block until playback finishes
    except Exception as exc:  # noqa: BLE001
        _log.error("Audio playback failed: %s", exc)
        return SpeakResult(
            success=False,
            text=text,
            model_path=model_path,
            audio_path=audio_path,
            error=f"Playback error: {exc}",
        )

    duration = round(time.time() - t0, 2)
    _log.info(
        "TTS complete — %.2f s | %.0f chars | model=%s",
        duration,
        len(text),
        os.path.basename(model_path),
    )
    return SpeakResult(
        success=True,
        text=text,
        duration_s=duration,
        audio_path=audio_path,
        model_path=model_path,
    )
