"""
llama
=====
Llama triage layer for the WellRing voice agent.

Takes a raw Whisper transcript and returns a structured classification
dict ready for the pipeline validator.

Sub-modules:
    prompt  — System prompt + few-shot examples + build_messages()
    parser  — Defensive JSON extraction + field repair
    client  — Ollama wrapper with retry / fallback logic

Quick usage:
    from llama import classify

    result = classify("I have chest pain and I cannot breathe")
    if result:
        # result.payload → {"intent":"health_issue","symptoms":[...],...}
        pipeline_payload = result.payload
"""

from .client import classify, ClassifyResult, MODEL_NAME, MAX_RETRIES
from .parser import parse, ParseResult
from .prompt import build_messages, KNOWN_SYMPTOMS, SYSTEM_PROMPT

__all__ = [
    # client
    "classify",
    "ClassifyResult",
    "MODEL_NAME",
    "MAX_RETRIES",
    # parser
    "parse",
    "ParseResult",
    # prompt
    "build_messages",
    "KNOWN_SYMPTOMS",
    "SYSTEM_PROMPT",
]
