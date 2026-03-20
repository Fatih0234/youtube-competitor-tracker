from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(tz=UTC)


def parse_rfc3339(value: str | None) -> datetime | None:
    """Parse a YouTube RFC3339 timestamp into a timezone-aware datetime."""

    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
