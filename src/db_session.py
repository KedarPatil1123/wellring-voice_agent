import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sqlalchemy.pool import StaticPool

# Assuming POSTGRES_URI is available in environment variables, or fallback to localhost
# e.g., postgresql://postgres:password@localhost:5432/wellring_db
DATABASE_URL = os.getenv("POSTGRES_URI", "postgresql://postgres:password@localhost:5432/wellring_db")

connect_args = {}
engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    engine_kwargs["poolclass"] = StaticPool

engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False, **engine_kwargs)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Dependency to provide a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
