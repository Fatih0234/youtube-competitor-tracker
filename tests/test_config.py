from __future__ import annotations

from sqlalchemy import inspect

from youtube_competitor_tracker.config import DEFAULT_DATABASE_PATH, Settings
from youtube_competitor_tracker.db.migrations import upgrade_database
from youtube_competitor_tracker.db.session import create_engine_from_settings
from youtube_competitor_tracker.exceptions import ConfigurationError


def test_settings_default_database_url_uses_local_sqlite_path() -> None:
    settings = Settings(_env_file=None)
    assert settings.database_url == f"sqlite:///{DEFAULT_DATABASE_PATH}"


def test_require_youtube_api_key_raises_when_missing() -> None:
    settings = Settings(_env_file=None, youtube_api_key=None)

    try:
        settings.require_youtube_api_key()
    except ConfigurationError as exc:
        assert "YOUTUBE_API_KEY" in str(exc)
    else:
        raise AssertionError("Expected ConfigurationError when API key is missing.")


def test_upgrade_database_creates_core_tables(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'migrated.db'}",
    )

    upgrade_database(settings.database_url)

    engine = create_engine_from_settings(settings)
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    assert {
        "channels",
        "videos",
        "channel_stats_snapshots",
        "video_stats_snapshots",
        "channel_sync_runs",
    }.issubset(table_names)

    engine.dispose()
