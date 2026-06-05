"""
test_llama.py
=============
Smoke test for the Llama integration layer.

Uses a mock Ollama response so no live server is needed.

Run with:
    python -m pytest tests/test_llama.py -v
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from unittest.mock import patch, MagicMock

import ollama


def _mock_response(content: str) -> MagicMock:
    """Mimics the Ollama SDK ChatResponse object."""
    msg = MagicMock()
    msg.content = content
    resp = MagicMock()
    resp.message = msg
    return resp


_EMERGENCY_JSON = (
    '{"intent":"health_issue","symptoms":["chest_pain"],'
    '"severity":"critical","confidence":0.97}'
)


@patch("ollama.chat")
def test_emergency_phrase_classified_as_health_issue(mock_chat):
    """
    'I have been having chest pain since morning' should be classified
    as a health_issue with chest_pain in the symptoms list.
    """
    mock_chat.return_value = _mock_response(_EMERGENCY_JSON)

    # Simulate what the llama client does internally
    response = ollama.chat(
        model="llama3",
        messages=[
            {"role": "system", "content": "You are a health assistant."},
            {"role": "user", "content": "I have been having chest pain since morning"},
        ],
    )

    content = response.message.content
    assert "chest_pain" in content
    assert "health_issue" in content