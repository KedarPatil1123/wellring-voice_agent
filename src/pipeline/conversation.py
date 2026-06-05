"""
conversation.py
===============
General-chat response handler for the WellRing voice agent.

When the Llama classifier determines the user's intent is ``general_chat``
(not a health issue), this module generates an appropriate conversational
reply using a set of intent-aware response templates.

Design principles:
    - Pure functions — no I/O, no state, fully testable.
    - Fast — no LLM call; responses are template-driven for low latency.
    - Safe — always returns a non-empty, carer-appropriate response.

Public API:
    generate_response(payload: dict) -> ConversationResult
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class ConversationResult:
    """Outcome of a general-chat turn.

    Attributes:
        text:          The reply text to speak to the user.
        follow_up:     An optional follow-up question to keep the conversation
                       going (empty string when not applicable).
        topic:         The detected conversational topic (e.g. 'greeting',
                       'wellbeing', 'weather', 'help', 'unknown').
        success:       Always True — the handler is designed to never fail.
    """
    text:      str
    follow_up: str  = ""
    topic:     str  = "unknown"
    success:   bool = True

    def __bool__(self) -> bool:
        return self.success


# ── Topic detection ───────────────────────────────────────────────────────────

_TOPIC_KEYWORDS: Dict[str, List[str]] = {
    "greeting": [
        "hello", "hi", "hey", "morning", "afternoon", "evening",
        "good morning", "good afternoon", "good evening", "howdy",
    ],
    "farewell": [
        "bye", "goodbye", "see you", "take care", "night", "goodnight",
        "good night", "later",
    ],
    "wellbeing": [
        "how are you", "how do you do", "how's it going", "how are things",
        "feeling", "are you ok", "are you okay",
    ],
    "gratitude": [
        "thank you", "thanks", "thank", "appreciate", "grateful",
        "cheers",
    ],
    "weather": [
        "weather", "rain", "sunny", "cloudy", "cold", "warm", "hot",
        "forecast", "temperature", "outside",
    ],
    "help": [
        "help", "what can you do", "what do you do", "how do you work",
        "assist", "support", "options", "tell me", "explain",
    ],
    "time": [
        "time", "what time", "what's the time", "clock", "hour",
    ],
    "boredom": [
        "bored", "boring", "nothing to do", "lonely", "alone",
    ],
    "compliment": [
        "good job", "well done", "great", "excellent", "amazing",
        "you're great", "fantastic",
    ],
}


def _detect_topic(text: str) -> str:
    """Return the conversational topic for a given transcript.

    Args:
        text: The user's transcribed speech (case-insensitive).

    Returns:
        A topic label from :data:`_TOPIC_KEYWORDS`, or ``"unknown"``.
    """
    lowered = text.lower()
    for topic, keywords in _TOPIC_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            return topic
    return "unknown"


# ── Response templates ────────────────────────────────────────────────────────

_RESPONSES: Dict[str, List[str]] = {
    "greeting": [
        "Hello! It's lovely to hear from you. How are you feeling today?",
        "Good to see you! How can I help you today?",
        "Hi there! I hope you're having a nice day.",
        "Hello! I'm here and listening. How are you doing?",
    ],
    "farewell": [
        "Take care and have a wonderful day!",
        "Goodbye! I'll be here if you need me.",
        "See you soon! Stay well.",
        "Goodnight! Rest well and I'll be here tomorrow.",
    ],
    "wellbeing": [
        "I'm doing great, thank you for asking! More importantly — how are you feeling?",
        "I'm always ready to help! Are you doing okay today?",
        "Thank you for checking on me! How about you — anything I can help with?",
    ],
    "gratitude": [
        "You're very welcome! I'm always happy to help.",
        "That's very kind of you! Is there anything else I can do?",
        "It's my pleasure! Just let me know if you need anything.",
    ],
    "weather": [
        "I don't have access to the current weather, but you could check outside or ask a family member. "
        "How are you feeling today?",
        "I'm not connected to weather services, but I hope it's a nice day wherever you are!",
    ],
    "help": [
        "I'm WellRing, your voice health companion. I can listen to how you're feeling, "
        "check in on your health, and alert your caregiver if needed. "
        "Just tell me how you're doing!",
        "I can help you report symptoms, remind you about medicine, or simply chat. "
        "What would you like to talk about?",
    ],
    "time": [
        "I don't have a clock, but you might be able to check the time on a nearby device. "
        "Is there anything else I can help with?",
    ],
    "boredom": [
        "I understand. Would you like to tell me a bit about your day? I'm here to listen.",
        "I'm happy to chat! Is there something on your mind, or shall I ask how you're feeling?",
        "Let's talk! How has your day been so far?",
    ],
    "compliment": [
        "That's very kind, thank you! I do my best to be helpful.",
        "You're making me smile! Is there anything I can do for you today?",
    ],
    "unknown": [
        "I heard you! Could you tell me a little more about what's on your mind?",
        "I'm here and listening. What would you like to chat about today?",
        "That's interesting! I'm always here if you need to talk or report how you're feeling.",
        "Got it! Feel free to tell me how you're doing, or just have a chat.",
    ],
}

_FOLLOW_UPS: Dict[str, str] = {
    "greeting":   "Are you feeling well today?",
    "farewell":   "",
    "wellbeing":  "Is there anything specific you'd like to check in about?",
    "gratitude":  "",
    "weather":    "How are you feeling physically today?",
    "help":       "Would you like to do a quick health check-in?",
    "time":       "Is there anything I can help you with right now?",
    "boredom":    "Shall we do a quick health check so I know you're all right?",
    "compliment": "Is there anything I can help you with today?",
    "unknown":    "How are you feeling today?",
}


# ── Public API ────────────────────────────────────────────────────────────────

def generate_response(payload: Dict[str, Any]) -> ConversationResult:
    """Generate a conversational reply for a general-chat turn.

    Args:
        payload: The validated Llama output dict. The ``transcript`` key
                 (if present) is used for topic detection.

    Returns:
        A :class:`ConversationResult` with the reply text and optional
        follow-up question.
    """
    transcript: str = payload.get("transcript", "")

    topic = _detect_topic(transcript)

    candidates = _RESPONSES.get(topic, _RESPONSES["unknown"])
    text       = random.choice(candidates)
    follow_up  = _FOLLOW_UPS.get(topic, "")

    return ConversationResult(
        text=text,
        follow_up=follow_up,
        topic=topic,
        success=True,
    )
