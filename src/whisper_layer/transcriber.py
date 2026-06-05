"""
transcriber.py
==============
Whisper transcription wrapper for the WellRing voice pipeline.

Handles model lifecycle (lazy singleton load) and wraps
``whisper.transcribe()`` with:
    - Configurable model size (base / small / medium / large)
    - fp16=False for CPU compatibility
    - temperature=0 for deterministic output
    - Silence / empty-transcript detection
    - Structured TranscribeResult dataclass

Public API:
    transcribe(file_path: str, model_size: str) -> TranscribeResult
    preload_model(model_size: str) -> None   ← call at startup to avoid
                                               first-request latency
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

# whisper is imported at module level so tests can patch
# ``whisper_layer.transcriber.whisper.load_model`` reliably.
try:
    import whisper  # noqa: F401  (openai-whisper package)
except ImportError:
    whisper = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_MODEL: str = "small"      # "base" | "small" | "medium" | "large"
LANGUAGE:      str = "en"
FP16:          bool = False        # CPU-safe
TEMPERATURE:   int = 0             # deterministic output

_log = logging.getLogger("wellring.transcriber")

# ---------------------------------------------------------------------------
# Singleton model cache  {model_size: whisper.Whisper}
# ---------------------------------------------------------------------------
_model_cache: Dict[str, Any] = {}


def _get_model(model_size: str = DEFAULT_MODEL) -> Any:
    """Return a cached Whisper model, loading it on first call.

    Args:
        model_size: Whisper model variant (e.g. ``"small"``).

    Returns:
        A loaded Whisper model object.
    """
    if model_size not in _model_cache:
        if whisper is None:
            raise ImportError(
                "openai-whisper is not installed. "
                "Run: pip install openai-whisper"
            )
        _log.info("Loading Whisper model '%s' …", model_size)
        t0 = time.time()
        _model_cache[model_size] = whisper.load_model(model_size)
        _log.info("Whisper '%s' loaded in %.1f s", model_size, time.time() - t0)
    return _model_cache[model_size]


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class TranscribeResult:
    """Outcome of a single transcription attempt.

    Attributes:
        success:    True when Whisper produced a non-empty transcript.
        text:       Stripped transcript string.
        model_size: Which Whisper model was used.
        file_path:  The WAV file that was transcribed.
        duration_s: Time taken by Whisper in seconds.
        is_empty:   True when the transcript is blank (silence / noise).
        error:      Error description on failure.
        raw:        Full Whisper result dict (includes ``segments``, etc.).
    """
    success:    bool
    text:       str         = ""
    model_size: str         = ""
    file_path:  str         = ""
    duration_s: float       = 0.0
    is_empty:   bool        = False
    error:      str         = ""
    raw:        Dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.success


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def preload_model(model_size: str = DEFAULT_MODEL) -> None:
    """Eagerly load the Whisper model so the first transcription is instant.

    Call this at application startup (e.g. in FastAPI's lifespan event).

    Args:
        model_size: Whisper model variant to preload.
    """
    _get_model(model_size)


def transcribe(
    file_path:  str,
    model_size: str = DEFAULT_MODEL,
) -> TranscribeResult:
    """Transcribe a WAV file with Whisper.

    Args:
        file_path:  Absolute or relative path to the WAV file.
        model_size: Whisper model variant (default: ``"small"``).

    Returns:
        A :class:`TranscribeResult` with ``success``, ``text``,
        ``is_empty``, and diagnostic fields.
    """
    # ── Validate file ─────────────────────────────────────────────────────────
    if not os.path.isfile(file_path):
        return TranscribeResult(
            success=False,
            file_path=file_path,
            error=f"Audio file not found: '{file_path}'",
        )

    # ── Load model ────────────────────────────────────────────────────────────
    try:
        model = _get_model(model_size)
    except Exception as exc:  # noqa: BLE001
        return TranscribeResult(
            success=False,
            file_path=file_path,
            error=f"Failed to load Whisper model '{model_size}': {exc}",
        )

    # ── Transcribe ────────────────────────────────────────────────────────────
    t0 = time.time()
    try:
        raw = model.transcribe(
            file_path,
            language=LANGUAGE,
            fp16=FP16,
            temperature=TEMPERATURE,
        )
    except Exception as exc:  # noqa: BLE001
        return TranscribeResult(
            success=False,
            file_path=file_path,
            model_size=model_size,
            error=f"Whisper transcription error: {exc}",
        )

    elapsed = round(time.time() - t0, 2)
    text    = raw.get("text", "").strip()
    is_empty = len(text) == 0

    if is_empty:
        _log.warning("Whisper returned an empty transcript for '%s'.", file_path)
    else:
        _log.info(
            "Transcribed in %.2f s → '%s…'",
            elapsed,
            text[:60],
        )

    return TranscribeResult(
        success=not is_empty,
        text=text,
        model_size=model_size,
        file_path=file_path,
        duration_s=elapsed,
        is_empty=is_empty,
        raw=raw,
    )
