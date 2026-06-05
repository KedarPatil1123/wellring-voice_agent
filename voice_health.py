"""
voice_health.py
===============
WellRing Voice Health Assistant — entry point.

Starts the interactive voice agent loop.

Usage:
    python voice_health.py

This is a thin wrapper around :func:`orchestrator.run_loop`.
All pipeline logic lives in ``src/``:

    src/orchestrator.py          ← run_once() / run_loop()
    src/whisper_layer/           ← Stage 1: Record + Transcribe
    src/llama/                   ← Stage 2: Classify
    src/pipeline/                ← Stage 3: Validate → Route → Log
    src/scoring_engine/          ← Stage 4: Score + Escalate
    src/tts/                     ← Stage 5: Synthesise + Speak

For the FastAPI server instead:
    uvicorn src.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import os
import sys

# ---------------------------------------------------------------------------
# Ensure src/ is importable when running from project root
# ---------------------------------------------------------------------------
_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# ---------------------------------------------------------------------------
# Configure logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Start the WellRing interactive voice loop."""
    try:
        from orchestrator import run_loop
    except ImportError as exc:
        print(
            f"\n❌  Could not import the orchestrator: {exc}\n"
            "    Make sure you are running from the project root and that\n"
            "    all dependencies are installed:  pip install -r requirements.txt\n"
        )
        sys.exit(1)

    run_loop()


if __name__ == "__main__":
    main()