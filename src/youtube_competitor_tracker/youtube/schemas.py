from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class ResolvedChannelReference:
    original_reference: str
    kind: str
    channel_id: str
    normalized_handle: str | None = None


@dataclass(slots=True)
class YouTubeChannelResource:
    youtube_channel_id: str
    title: str
    handle: str | None
    custom_url: str | None
    description: str | None
    published_at: datetime | None
    country: str | None
    default_language: str | None
    uploads_playlist_id: str | None
    subscriber_count: int | None
    view_count: int | None
    video_count: int | None
    thumbnails_json: dict[str, Any] | None
    raw_json: dict[str, Any]


@dataclass(slots=True)
class YouTubeVideoResource:
    youtube_video_id: str
    title: str
    description: str | None
    published_at: datetime | None
    channel_title: str | None
    duration_seconds: int | None
    category_id: str | None
    tags_json: list[str] | None
    default_language: str | None
    default_audio_language: str | None
    thumbnails_json: dict[str, Any] | None
    live_broadcast_content: str | None
    is_short: bool
    made_for_kids: bool | None
    licensed_content: bool | None
    caption_status: str | None
    privacy_status: str | None
    upload_status: str | None
    embeddable: bool | None
    view_count: int | None
    like_count: int | None
    comment_count: int | None
    favorite_count: int | None
    raw_json: dict[str, Any]
