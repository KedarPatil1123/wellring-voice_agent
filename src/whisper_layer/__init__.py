"""
whisper_layer
=============
Audio capture + transcription layer for the WellRing voice pipeline.

Sub-modules:
    recorder     — Microphone capture → WAV file (sounddevice + soundfile)
    transcriber  — WAV file → text transcript (OpenAI Whisper)

Quick usage:
    from whisper_layer import record, transcribe

    rec = record()                  # captures 8 s from mic
    if rec and not rec.is_silent:
        tr = transcribe(rec.file_path)
        if tr:
            text = tr.text          # → passed to llama.classify()
"""

from .recorder    import record,     RecordResult,     SAMPLE_RATE, DURATION
from .transcriber import transcribe, TranscribeResult, preload_model, DEFAULT_MODEL

__all__ = [
    # recorder
    "record",
    "RecordResult",
    "SAMPLE_RATE",
    "DURATION",
    # transcriber
    "transcribe",
    "TranscribeResult",
    "preload_model",
    "DEFAULT_MODEL",
]
