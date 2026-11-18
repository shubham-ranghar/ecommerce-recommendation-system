"""Database setup: one SQLite file shared by the data script, the API and the evaluation."""
from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# backend/ folder (this file lives in backend/app/)
BACKEND_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BACKEND_DIR / "data" / "shop.db"

# You can point to another database with the SHOP_DATABASE_URL environment variable (used by tests).
DATABASE_URL = os.environ.get("SHOP_DATABASE_URL", f"sqlite:///{DB_PATH.as_posix()}")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base class for all ORM models."""


def get_db() -> Iterator[Session]:
    """FastAPI dependency: open a session for one request and always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
