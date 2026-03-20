from __future__ import annotations


class TrackerError(Exception):
    """Base exception for application-level failures."""


class ConfigurationError(TrackerError):
    """Raised when required runtime configuration is missing or invalid."""


class ChannelNotFoundError(TrackerError):
    """Raised when a channel cannot be found in the API or local database."""


class UnsupportedChannelReferenceError(TrackerError):
    """Raised when a provided channel reference format is not supported."""


class ChannelNotTrackedError(TrackerError):
    """Raised when a sync is requested for a channel not stored locally."""


class YouTubeAPIError(TrackerError):
    """Raised when the YouTube API returns an unrecoverable error."""
