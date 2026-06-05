"""
tts
===
Text-to-speech layer for the WellRing voice agent.

Wraps Piper TTS to synthesise the agent's spoken responses and play them
back to the user via the system's default audio output.

Sub-modules:
    speaker  — Core synthesis + playback with SpeakResult dataclass

Quick usage:
    from tts import speak

    result = speak("Hello! How are you feeling today?")
    if not result:
        print(f"TTS failed: {result.error}")
"""

from .speaker import speak, SpeakResult, preload_voice

__all__ = [
    "speak",
    "SpeakResult",
    "preload_voice",
]
