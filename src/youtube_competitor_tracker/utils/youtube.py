from __future__ import annotations

import re
from urllib.parse import urlparse

CHANNEL_ID_PATTERN = re.compile(r"^UC[a-zA-Z0-9_-]{22}$")
HANDLE_PATTERN = re.compile(r"^@?[a-zA-Z0-9._-]{3,30}$")
ISO8601_DURATION_PATTERN = re.compile(
    r"^P(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)$"
)


def is_channel_id(value: str) -> bool:
    return bool(CHANNEL_ID_PATTERN.fullmatch(value.strip()))


def normalize_handle(value: str) -> str:
    stripped = value.strip()
    if not HANDLE_PATTERN.fullmatch(stripped):
        raise ValueError(f"Unsupported handle format: {value}")
    return stripped if stripped.startswith("@") else f"@{stripped}"


def parse_channel_reference(reference: str) -> tuple[str, str]:
    """Return `(kind, value)` for supported channel reference inputs."""

    value = reference.strip()
    if is_channel_id(value):
        return ("channel_id", value)
    if value.startswith("@"):
        return ("handle", normalize_handle(value))
    if value.startswith("http://") or value.startswith("https://"):
        parsed = urlparse(value)
        host = parsed.netloc.lower()
        if host.endswith("youtube.com") or host.endswith("www.youtube.com") or host.endswith("m.youtube.com"):
            path = parsed.path.strip("/")
            if path.startswith("channel/"):
                channel_id = path.split("/", 1)[1]
                if is_channel_id(channel_id):
                    return ("channel_id", channel_id)
            if path.startswith("@"):
                return ("handle", normalize_handle(path))
        raise ValueError(f"Unsupported YouTube channel URL: {reference}")
    raise ValueError(f"Unsupported channel reference: {reference}")


def parse_iso8601_duration(value: str | None) -> int | None:
    """Convert YouTube ISO8601 durations into total seconds."""

    if not value:
        return None
    match = ISO8601_DURATION_PATTERN.fullmatch(value)
    if not match:
        return None
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    return hours * 3600 + minutes * 60 + seconds
