from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from youtube_competitor_tracker.exceptions import ConfigurationError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "youtube_competitor_tracker.db"


class Settings(BaseSettings):
    """Application settings loaded from environment variables and `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    youtube_api_key: str | None = Field(default=None, alias="YOUTUBE_API_KEY")
    database_url: str = Field(
        default=f"sqlite:///{DEFAULT_DATABASE_PATH}",
        alias="DATABASE_URL",
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    request_timeout_seconds: float = Field(default=30.0, alias="REQUEST_TIMEOUT_SECONDS")
    http_retry_attempts: int = Field(default=3, alias="HTTP_RETRY_ATTEMPTS")
    http_retry_backoff_seconds: float = Field(
        default=1.0,
        alias="HTTP_RETRY_BACKOFF_SECONDS",
    )

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        return value.strip()

    @field_validator("log_level")
    @classmethod
    def _normalize_log_level(cls, value: str) -> str:
        return value.upper().strip()

    def require_youtube_api_key(self) -> str:
        """Return the configured API key or raise a runtime configuration error."""

        if not self.youtube_api_key:
            raise ConfigurationError(
                "YOUTUBE_API_KEY is required for YouTube API commands. "
                "Set it in the environment or `.env`."
            )
        return self.youtube_api_key


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance for application code."""

    return Settings()
