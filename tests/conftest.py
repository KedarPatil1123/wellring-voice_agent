import os
import sys

# Force the test environment to use an in-memory SQLite database
os.environ["POSTGRES_URI"] = "sqlite:///:memory:"
