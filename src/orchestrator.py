"""
orchestrator.py
===============
End-to-end pipeline orchestrator for the WellRing voice agent.

Connects all stages in a single blocking call:

    Stage 1 — Audio capture   whisper_layer.record()
    Stage 2 — Transcription   whisper_layer.transcribe()
    Stage 3 — Classification  llama.classify()
    Stage 4 — Pipeline        pipeline.validate() → route() → log_request()
    Stage 5 — TTS Response    tts.speak()  ← speaks the reply back to the user

Usage (interactive loop):
    from orchestrator import run_once, run_loop

    run_loop()          # blocks until the user types "quit"

Usage (single turn, e.g. from a test or FastAPI background task):
    result = run_once()
    print(result.risk_level, result.action)
"""

from __future__ import annotations

import logging
import sys
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

# Ensure src/ is importable
_SRC = os.path.dirname(os.path.abspath(__file__))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from whisper_layer import record, transcribe, RecordResult, TranscribeResult
from llama         import classify, ClassifyResult
from pipeline      import validate, route, log_request
from tts           import speak, SpeakResult

try:
    from notifier import dispatch as notify_caregiver, NotifyResult
    _NOTIFIER_AVAILABLE = True
except ImportError:  # pragma: no cover — only missing in stripped test envs
    notify_caregiver    = None  # type: ignore[assignment]
    NotifyResult        = None  # type: ignore[assignment,misc]
    _NOTIFIER_AVAILABLE = False

_log = logging.getLogger("wellring.orchestrator")


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class TurnResult:
    """Full outcome of one voice-agent turn.

    Attributes:
        success:        True when the turn completed without fatal errors.
        transcript:     Raw Whisper text.
        intent:         Llama-classified intent.
        risk_level:     Scoring engine output (health_issue only).
        action:         Escalation action dict (health_issue only).
        request_id:     UUID written to the pipeline log.
        spoken_text:    The text that was sent to TTS (may be empty if TTS
                        was skipped due to an earlier stage failure).
        stage_errors:   Dict of stage → error string for any partial failures.
        record_result:  Raw RecordResult for diagnostics.
        transcribe_result: Raw TranscribeResult for diagnostics.
        classify_result:   Raw ClassifyResult for diagnostics.
        speak_result:      Raw SpeakResult for diagnostics.
    """
    success:           bool
    transcript:        str                = ""
    intent:            str                = ""
    risk_level:        Optional[str]      = None
    action:            Optional[Dict]     = None
    request_id:        str                = ""
    spoken_text:       str                = ""
    stage_errors:      Dict[str, str]     = field(default_factory=dict)
    record_result:     Optional[RecordResult]     = None
    transcribe_result: Optional[TranscribeResult] = None
    classify_result:   Optional[ClassifyResult]   = None
    speak_result:      Optional[SpeakResult]      = None
    notify_result:     Optional[object]           = None  # NotifyResult | None

    def __bool__(self) -> bool:
        return self.success


# ---------------------------------------------------------------------------
# Core single-turn function
# ---------------------------------------------------------------------------

def run_once(
    whisper_model: str = "small",
    duration:      int = 8,
    countdown:     bool = True,
    voice_model:   Optional[str] = None,
    tts_save_path: Optional[str] = None,
) -> TurnResult:
    """Execute one complete voice-agent turn.

    Stages:
        1. Record audio from microphone.
        2. Transcribe with Whisper.
        3. Classify with Llama (structured JSON extraction).
        4. Validate → route → log through the pipeline.
        5. Synthesise and speak the response via Piper TTS.

    Args:
        whisper_model: Whisper model size (``"small"`` recommended).
        duration:      Recording length in seconds.
        countdown:     Whether to print the 3-2-1 countdown.
        voice_model:   Path to Piper ``.onnx`` voice model file.
                       Uses :data:`tts.speaker.DEFAULT_VOICE_MODEL` if None.
        tts_save_path: Optional path to save the spoken WAV for debugging.

    Returns:
        A :class:`TurnResult` with all stage outputs populated.
    """
    errors: Dict[str, str] = {}

    # ── Stage 1: Record ───────────────────────────────────────────────────────
    _log.info("Stage 1 — Recording (%d s) …", duration)
    rec = record(duration=duration, countdown=countdown)

    if not rec:
        errors["record"] = rec.error
        _log.error("Recording failed: %s", rec.error)
        return TurnResult(success=False, stage_errors=errors, record_result=rec)

    if rec.is_silent:
        errors["record"] = "Silent recording — no speech detected."
        _log.warning("Silent recording detected.")
        return TurnResult(
            success=False,
            stage_errors=errors,
            record_result=rec,
        )

    # ── Stage 2: Transcribe ───────────────────────────────────────────────────
    _log.info("Stage 2 — Transcribing with Whisper '%s' …", whisper_model)
    tr = transcribe(rec.file_path, model_size=whisper_model)

    if not tr or tr.is_empty:
        errors["transcribe"] = tr.error or "Empty transcript."
        _log.warning("Empty transcript from Whisper.")
        return TurnResult(
            success=False,
            stage_errors=errors,
            record_result=rec,
            transcribe_result=tr,
        )

    _log.info("Transcript: '%s'", tr.text[:80])

    # ── Stage 3: Classify with Llama ──────────────────────────────────────────
    _log.info("Stage 3 — Classifying with Llama …")
    cl = classify(tr.text)

    if cl.is_fallback:
        errors["classify"] = cl.error
        _log.warning("Llama fallback used: %s", cl.error)
        # Do not abort — continue with fallback payload (confidence = 0.0)

    # ── Stage 4: Pipeline (validate → route → log) ────────────────────────────
    _log.info("Stage 4 — Pipeline (validate → route → log) …")

    # Merge the raw transcript into the classify payload so the conversation
    # handler can detect the topic (e.g. greeting/farewell/help).
    raw_payload = {**cl.payload, "transcript": tr.text}

    v = validate(raw_payload)
    if not v:
        errors["validate"] = "; ".join(v.errors)
        _log.error("Pipeline validation failed: %s", v.errors)
        request_id = log_request(raw_payload, None, v)
        return TurnResult(
            success=False,
            transcript=tr.text,
            intent=cl.payload.get("intent", "unknown"),
            request_id=request_id,
            stage_errors=errors,
            record_result=rec,
            transcribe_result=tr,
            classify_result=cl,
        )

    rr = route(v.payload)
    request_id = log_request(raw_payload, rr, v)

    if not rr:
        errors["route"] = rr.error
        _log.error("Routing error: %s", rr.error)
        return TurnResult(
            success=False,
            transcript=tr.text,
            intent=cl.payload.get("intent", "unknown"),
            request_id=request_id,
            stage_errors=errors,
            record_result=rec,
            transcribe_result=tr,
            classify_result=cl,
        )

    _log.info(
        "Turn complete — intent=%s  risk=%s  request_id=%s",
        v.payload.get("intent"),
        rr.data.get("risk_level"),
        request_id,
    )

    # ── Stage 4.5: Caregiver notification (non-fatal) ─────────────────────────
    notify_res = None
    if _NOTIFIER_AVAILABLE and rr.success and rr.data.get("risk_level"):
        _log.info("Stage 4.5 — Caregiver notification …")
        alert_payload = {
            **rr.data.get("action", {}),
            "risk_level": rr.data.get("risk_level"),
            "score":      rr.data.get("score", 0),
            "request_id": request_id,
            "symptoms":   v.payload.get("symptoms", []),
        }
        try:
            notify_res = notify_caregiver(alert_payload)
            if notify_res and not notify_res.skipped:
                _log.info(
                    "Notification dispatched — channels=%s",
                    notify_res.channels_ok,
                )
        except Exception as exc:  # noqa: BLE001
            errors["notify"] = str(exc)
            _log.error("Notifier raised: %s", exc)

    # ── Stage 5: TTS — synthesise and speak the response ─────────────────────
    _log.info("Stage 5 — TTS response …")
    spoken_text = _build_response_text(v.payload.get("intent", ""), rr)
    sr = speak(spoken_text, voice_model=voice_model, save_path=tts_save_path)
    if not sr:
        errors["speak"] = sr.error
        _log.warning("TTS failed (non-fatal): %s", sr.error)

    return TurnResult(
        success=True,
        transcript=tr.text,
        intent=v.payload.get("intent", ""),
        risk_level=rr.data.get("risk_level"),
        action=rr.data.get("action"),
        request_id=request_id,
        spoken_text=spoken_text,
        stage_errors=errors,
        record_result=rec,
        transcribe_result=tr,
        classify_result=cl,
        speak_result=sr,
        notify_result=notify_res,
    )


# ---------------------------------------------------------------------------
# Response text builder
# ---------------------------------------------------------------------------

def _build_response_text(intent: str, rr: Any) -> str:
    """Compose the spoken response text from the routing result.

    For health issues, the escalation action message is spoken.
    For general chat, a friendly acknowledgement is used.
    For unknown/error states, a safe default is returned.

    Args:
        intent: The validated intent string.
        rr:     The :class:`RouteResult` from the router.

    Returns:
        A plain-text string ready for TTS synthesis.
    """
    if intent == "health_issue":
        data = rr.data if rr and rr.success else {}
        action = data.get("action", {})
        # action is a dict from alerts.determine_action()
        if isinstance(action, dict):
            return action.get(
                "message",
                "I have detected a health concern. Please stay calm and call for help if needed.",
            )
        return "I have detected a health concern. Please stay calm."

    if intent == "general_chat":
        if not rr or not rr.success:
            return "How can I help you today?"
        data = rr.data
        # Use the topic-aware message from the conversation handler
        text = data.get("message", "I heard you. How can I help you today?")
        # Append the follow-up question if one exists (keep it as one sentence)
        follow_up = data.get("follow_up", "")
        if follow_up:
            text = f"{text} {follow_up}"
        return text

    return "I am here to help. Please speak clearly and I will do my best to assist you."


# ---------------------------------------------------------------------------
# Interactive loop
# ---------------------------------------------------------------------------

def run_loop(
    whisper_model: str = "small",
    duration:      int = 8,
    voice_model:   Optional[str] = None,
) -> None:
    """Run the voice agent in an interactive loop.

    Prints a summary after each turn.  Type ``quit`` or ``exit`` at the
    prompt to stop.

    Args:
        whisper_model: Whisper model size.
        duration:      Recording length in seconds.
        voice_model:   Path to Piper ``.onnx`` voice model file.
    """
    print("\n╔══════════════════════════════════════╗")
    print("║    WellRing Voice Agent — Ready      ║")
    print("╚══════════════════════════════════════╝")
    print("Press ENTER to speak  |  type 'quit' to exit\n")

    while True:
        try:
            user_input = input("→ ")
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye! Stay safe. 💙")
            break

        if user_input.lower().strip() in ("quit", "exit", "q"):
            print("Goodbye! Stay safe. 💙")
            break

        result = run_once(
            whisper_model=whisper_model,
            duration=duration,
            voice_model=voice_model,
        )

        print()
        if not result.success:
            print(f"⚠  Could not complete turn: {result.stage_errors}")
        elif result.intent == "general_chat":
            print("💬  General conversation — no health concern detected.")
            print(f"🔊  Spoke: {result.spoken_text}")
        else:
            print(f"📋  Transcript  : {result.transcript}")
            print(f"🏷  Intent      : {result.intent}")
            print(f"⚠  Risk Level  : {result.risk_level}")
            if isinstance(result.action, dict):
                print(f"🚨  Action      : {result.action.get('action')}")
            print(f"🔊  Spoke       : {result.spoken_text}")
        print(f"🔑  Request ID  : {result.request_id}")
        if "speak" in result.stage_errors:
            print(f"🔇  TTS error   : {result.stage_errors['speak']}")
        print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_loop()
