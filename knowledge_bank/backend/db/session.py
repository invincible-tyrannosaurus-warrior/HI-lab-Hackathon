from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "knowledge_bank.db"


def _build_database_url(explicit_url: str | None = None) -> str:
    return explicit_url or os.getenv("KB_DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")


def _build_engine(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args)


DATABASE_URL = _build_database_url()
engine = _build_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def configure_database(database_url: str | None = None):
    """Reconfigure the global engine. Tests use this to point at a temp database."""
    global DATABASE_URL, engine, SessionLocal

    DATABASE_URL = _build_database_url(database_url)
    engine = _build_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine


def get_engine():
    return engine


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
