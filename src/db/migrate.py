"""
migrate.py
==========
Helper script: run src/db/schema.sql against a live PostgreSQL database.

Usage:
    python -m src.db.migrate

Environment variables required (set in .env):
    DATABASE_URL  — e.g. postgresql://user:pass@host:5432/wellring
"""

import os
import pathlib
import sys

import psycopg2
from dotenv import load_dotenv

load_dotenv()

SCHEMA_FILE = pathlib.Path(__file__).parent / "schema.sql"


def migrate() -> None:
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        print("[MIGRATE] ❌  DATABASE_URL is not set. Aborting.", file=sys.stderr)
        sys.exit(1)

    sql = SCHEMA_FILE.read_text()

    print(f"[MIGRATE] Connecting to PostgreSQL …")
    conn = psycopg2.connect(database_url)
    conn.autocommit = True
    cursor = conn.cursor()

    print("[MIGRATE] Executing schema …")
    cursor.execute(sql)

    cursor.close()
    conn.close()
    print("[MIGRATE] ✅  Schema applied successfully.")


if __name__ == "__main__":
    migrate()
