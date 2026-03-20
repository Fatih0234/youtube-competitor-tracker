from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from youtube_competitor_tracker.config import PROJECT_ROOT
from youtube_competitor_tracker.db.session import ensure_sqlite_directory


def build_alembic_config(database_url: str) -> Config:
    """Create an Alembic config object bound to the requested database URL."""

    ensure_sqlite_directory(database_url)
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def upgrade_database(database_url: str, revision: str = "head") -> None:
    """Apply Alembic migrations up to the requested revision."""

    command.upgrade(build_alembic_config(database_url), revision)
