"""
conftest.py
===========
Root-level pytest configuration for the WellRing voice agent test suite.

Automatically adds ``src/`` to sys.path so every test file can import
from ``pipeline``, ``llama``, ``whisper_layer``, etc. without each file
needing its own ``sys.path.insert(0, ...)`` block.

Run all no-hardware tests with:
    python -m pytest tests/test_pipeline.py tests/test_llama_module.py \\
        tests/test_llama.py tests/test_orchestrator.py \\
        tests/test_whisper_layer.py tests/test_tts.py -v
"""

import sys
import os

# Make src/ importable for all test files
_SRC = os.path.join(os.path.dirname(__file__), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
