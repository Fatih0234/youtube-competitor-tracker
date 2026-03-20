from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from youtube_competitor_tracker.config import Settings


def ensure_sqlite_directory(database_url: str) -> None:
    """Create the local directory for SQLite databases when needed."""

    sqlite_prefix = "sqlite:///"
    if not database_url.startswith(sqlite_prefix):
        return
    database_path = Path(database_url.removeprefix(sqlite_prefix))
    if database_path.name == ":memory:":
        return
    database_path.parent.mkdir(parents=True, exist_ok=True)


def create_engine_from_settings(settings: Settings) -> Engine:
    """Create a SQLAlchemy engine from application settings."""

    ensure_sqlite_directory(settings.database_url)
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    return create_engine(settings.database_url, future=True, connect_args=connect_args)


def create_session_factory(settings: Settings) -> sessionmaker[Session]:
    """Create a sessionmaker bound to the configured engine."""

    engine = create_engine_from_settings(settings)
    return sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]):
    """Provide a transactional scope around a series of database operations."""

    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
