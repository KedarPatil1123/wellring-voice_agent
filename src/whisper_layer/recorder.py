"""
recorder.py
===========
Microphone audio capture for the WellRing voice pipeline.

Wraps sounddevice + soundfile into a clean, testable interface that saves
a WAV file and returns its path.  The orchestrator calls record() and
passes the returned path straight to the transcriber.

Settings (all overridable at call time):
    SAMPLE_RATE  16 000 Hz  — Whisper's native sample rate
    DURATION     8 seconds  — comfortable window for elderly speakers
    CHANNELS     1          — mono
    DTYPE        int16      — compact, lossless for speech

Public API:
    record(
        output_path: str | None,
        duration:    int,
        sample_rate: int,
        countdown:   bool,
    ) -> RecordResult
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

import sounddevice as sd
import soundfile as sf
import numpy as np

# ---------------------------------------------------------------------------
# Default settings  (keep in sync with voice_health.py)
# ---------------------------------------------------------------------------

SAMPLE_RATE: int = 16_000   # Hz — Whisper's native rate
DURATION:    int = 8        # seconds
CHANNELS:    int = 1        # mono
DTYPE:       str = "int16"

_AUDIO_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "audios",
)

_log = logging.getLogger("wellring.recorder")


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class RecordResult:
    """Outcome of a single recording attempt.

    Attributes:
        success:     True when audio was captured and saved.
        file_path:   Absolute path to the saved WAV file.
        duration:    Actual recording duration in seconds.
        sample_rate: Sample rate used.
        error:       Error description on failure.
        is_silent:   True when the recording is below the silence threshold.
    """
    success:     bool
    file_path:   str   = ""
    duration:    int   = 0
    sample_rate: int   = 0
    error:       str   = ""
    is_silent:   bool  = False

    def __bool__(self) -> bool:
        return self.success


# ---------------------------------------------------------------------------
# Silence detection
# ---------------------------------------------------------------------------

_SILENCE_RMS_THRESHOLD = 50   # int16 RMS below this → treat as silence


def _is_silent(recording: np.ndarray) -> bool:
    """Return True when the recording's RMS energy is below the threshold.

    Args:
        recording: NumPy array of int16 samples.

    Returns:
        True if the recording appears silent.
    """
    rms = float(np.sqrt(np.mean(recording.astype(np.float32) ** 2)))
    return rms < _SILENCE_RMS_THRESHOLD


# ---------------------------------------------------------------------------
# Countdown helper
# ---------------------------------------------------------------------------

def _countdown() -> None:
    """Print a 3-second countdown before recording starts."""
    for n in ("3...", "2...", "1..."):
        print(n)
        time.sleep(1)
    print("🎤  SPEAK NOW!")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def record(
    output_path:  Optional[str] = None,
    duration:     int           = DURATION,
    sample_rate:  int           = SAMPLE_RATE,
    countdown:    bool          = True,
) -> RecordResult:
    """Record audio from the default microphone and save it as a WAV file.

    Args:
        output_path:  Destination WAV path.  If None, a timestamped file is
                      created inside ``audios/``.
        duration:     Recording length in seconds.
        sample_rate:  Sample rate in Hz (default 16 000).
        countdown:    If True, print a 3-second countdown before recording.

    Returns:
        A :class:`RecordResult` with ``success``, ``file_path``,
        ``is_silent``, and diagnostic fields.
    """
    # ── Resolve output path ───────────────────────────────────────────────────
    if output_path is None:
        os.makedirs(_AUDIO_DIR, exist_ok=True)
        timestamp = int(time.time())
        output_path = os.path.join(_AUDIO_DIR, f"recording_{timestamp}.wav")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    # ── Countdown ─────────────────────────────────────────────────────────────
    if countdown:
        _countdown()

    # ── Record ────────────────────────────────────────────────────────────────
    try:
        _log.info("Recording for %d s at %d Hz …", duration, sample_rate)
        recording: np.ndarray = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=CHANNELS,
            dtype=DTYPE,
        )
        sd.wait()
        _log.info("Recording complete → %s", output_path)
    except Exception as exc:  # noqa: BLE001
        return RecordResult(
            success=False,
            error=f"sounddevice error: {exc}",
        )

    # ── Check silence ─────────────────────────────────────────────────────────
    silent = _is_silent(recording)
    if silent:
        _log.warning("Recording appears silent (RMS below threshold).")

    # ── Save to disk ──────────────────────────────────────────────────────────
    try:
        sf.write(output_path, recording, sample_rate)
    except Exception as exc:  # noqa: BLE001
        return RecordResult(
            success=False,
            error=f"Failed to save WAV: {exc}",
        )

    return RecordResult(
        success=True,
        file_path=output_path,
        duration=duration,
        sample_rate=sample_rate,
        is_silent=silent,
    )
