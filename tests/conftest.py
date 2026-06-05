"""
conftest.py
===========
Shared pytest fixtures for the WellRing FastAPI test suite.

Sets WELLRING_DB_PATH to a temporary file BEFORE any src modules are
imported, so database.py picks up the test path at module-load time.
"""

import os
import tempfile
import pytest

# ── Set the test DB path at module load (before any src import) ───────────
_tmp_db = tempfile.mktemp(suffix=".db", prefix="wellring_test_")
os.environ["WELLRING_DB_PATH"] = _tmp_db


@pytest.fixture(scope="session")
def client():
    """
    Session-scoped FastAPI TestClient.
    Uses a temporary SQLite DB that is deleted after the session.
    """
    from fastapi.testclient import TestClient
    from src.main import app

    with TestClient(app) as c:
        yield c

    # Cleanup the temp DB after all tests finish
    if os.path.exists(_tmp_db):
        os.remove(_tmp_db)
