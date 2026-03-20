from __future__ import annotations

import pytest
from sqlalchemy.orm import Session, sessionmaker

from youtube_competitor_tracker import models as _models  # noqa: F401
from youtube_competitor_tracker.config import Settings
from youtube_competitor_tracker.db.base import Base
from youtube_competitor_tracker.db.session import create_engine_from_settings


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        youtube_api_key="test-api-key",
        log_level="DEBUG",
        request_timeout_seconds=5.0,
        http_retry_attempts=1,
        http_retry_backoff_seconds=0.0,
    )


@pytest.fixture
def session_factory(settings):
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)
    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
