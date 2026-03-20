from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from youtube_competitor_tracker.exceptions import (
    ChannelNotFoundError,
    UnsupportedChannelReferenceError,
    YouTubeAPIError,
)
from youtube_competitor_tracker.utils.datetime import parse_rfc3339
from youtube_competitor_tracker.utils.youtube import (
    normalize_handle,
    parse_channel_reference,
    parse_iso8601_duration,
)
from youtube_competitor_tracker.youtube.schemas import (
    ResolvedChannelReference,
    YouTubeChannelResource,
    YouTubeVideoResource,
)

logger = logging.getLogger(__name__)

TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}


class YouTubeClient:
    """Thin, typed wrapper around the YouTube Data API v3."""

    def __init__(
        self,
        api_key: str,
        *,
        http_client: httpx.Client | None = None,
        timeout: float = 30.0,
        retry_attempts: int = 3,
        retry_backoff_seconds: float = 1.0,
    ) -> None:
        self._api_key = api_key
        self._retry_attempts = max(1, retry_attempts)
        self._retry_backoff_seconds = max(0.0, retry_backoff_seconds)
        self._owns_client = http_client is None
        self._client = http_client or httpx.Client(
            base_url="https://www.googleapis.com/youtube/v3",
            timeout=timeout,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def resolve_channel_reference(self, reference: str) -> ResolvedChannelReference:
        """Resolve a supported channel reference into a canonical channel id."""

        try:
            kind, value = parse_channel_reference(reference)
        except ValueError as exc:
            raise UnsupportedChannelReferenceError(str(exc)) from exc

        if kind == "channel_id":
            return ResolvedChannelReference(
                original_reference=reference,
                kind=kind,
                channel_id=value,
            )

        handle = normalize_handle(value)
        payload = self._request_json(
            "/channels",
            {
                "part": "id,snippet",
                "forHandle": handle.lstrip("@"),
                "maxResults": 1,
            },
        )
        items = payload.get("items", [])
        if not items:
            raise ChannelNotFoundError(f"No channel found for handle {handle}.")
        return ResolvedChannelReference(
            original_reference=reference,
            kind="handle",
            channel_id=items[0]["id"],
            normalized_handle=handle,
        )

    def fetch_channel(
        self,
        channel_id: str,
        *,
        fallback_handle: str | None = None,
    ) -> YouTubeChannelResource:
        payload = self._request_json(
            "/channels",
            {
                "part": "snippet,contentDetails,statistics,status,brandingSettings",
                "id": channel_id,
                "maxResults": 1,
            },
        )
        items = payload.get("items", [])
        if not items:
            raise ChannelNotFoundError(f"No channel found for id {channel_id}.")
        return self._parse_channel_item(items[0], fallback_handle=fallback_handle)

    def list_upload_video_ids(self, uploads_playlist_id: str) -> list[str]:
        video_ids: list[str] = []
        next_page_token: str | None = None

        while True:
            payload = self._request_json(
                "/playlistItems",
                {
                    "part": "contentDetails",
                    "playlistId": uploads_playlist_id,
                    "maxResults": 50,
                    "pageToken": next_page_token,
                },
            )
            for item in payload.get("items", []):
                video_id = item.get("contentDetails", {}).get("videoId")
                if video_id:
                    video_ids.append(video_id)
            next_page_token = payload.get("nextPageToken")
            if not next_page_token:
                return video_ids

    def fetch_videos(self, video_ids: list[str]) -> list[YouTubeVideoResource]:
        if not video_ids:
            return []

        resources: list[YouTubeVideoResource] = []
        for start in range(0, len(video_ids), 50):
            batch = video_ids[start : start + 50]
            payload = self._request_json(
                "/videos",
                {
                    "part": "snippet,contentDetails,statistics,status",
                    "id": ",".join(batch),
                    "maxResults": 50,
                },
            )
            resources.extend(self._parse_video_item(item) for item in payload.get("items", []))
        return resources

    def _request_json(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        merged_params = {**params, "key": self._api_key}

        for attempt in range(1, self._retry_attempts + 1):
            try:
                response = self._client.get(path, params=merged_params)
            except httpx.TransportError as exc:
                if attempt == self._retry_attempts:
                    raise YouTubeAPIError(f"Transport error calling YouTube API: {exc}") from exc
                self._sleep_before_retry(attempt)
                continue

            if response.status_code in TRANSIENT_STATUS_CODES and attempt < self._retry_attempts:
                logger.warning("Transient YouTube API response %s for %s", response.status_code, path)
                self._sleep_before_retry(attempt)
                continue

            if response.is_error:
                raise YouTubeAPIError(self._format_api_error(response))

            return response.json()

        raise YouTubeAPIError(f"Failed to call YouTube API endpoint {path}.")

    def _sleep_before_retry(self, attempt: int) -> None:
        time.sleep(self._retry_backoff_seconds * attempt)

    def _format_api_error(self, response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return f"YouTube API request failed with status {response.status_code}."

        message = payload.get("error", {}).get("message")
        if message:
            return f"YouTube API request failed with status {response.status_code}: {message}"
        return f"YouTube API request failed with status {response.status_code}."

    @staticmethod
    def _parse_int(value: str | int | None) -> int | None:
        if value is None:
            return None
        return int(value)

    def _parse_channel_item(
        self,
        item: dict[str, Any],
        *,
        fallback_handle: str | None = None,
    ) -> YouTubeChannelResource:
        snippet = item.get("snippet", {})
        content_details = item.get("contentDetails", {})
        statistics = item.get("statistics", {})
        branding_settings = item.get("brandingSettings", {}).get("channel", {})
        custom_url = snippet.get("customUrl") or branding_settings.get("customUrl")
        handle = fallback_handle
        if isinstance(custom_url, str) and custom_url.startswith("@"):
            handle = custom_url

        return YouTubeChannelResource(
            youtube_channel_id=item["id"],
            title=snippet.get("title", ""),
            handle=handle,
            custom_url=custom_url,
            description=snippet.get("description"),
            published_at=parse_rfc3339(snippet.get("publishedAt")),
            country=branding_settings.get("country"),
            default_language=snippet.get("defaultLanguage") or branding_settings.get("defaultLanguage"),
            uploads_playlist_id=content_details.get("relatedPlaylists", {}).get("uploads"),
            subscriber_count=self._parse_int(statistics.get("subscriberCount")),
            view_count=self._parse_int(statistics.get("viewCount")),
            video_count=self._parse_int(statistics.get("videoCount")),
            thumbnails_json=snippet.get("thumbnails"),
            raw_json=item,
        )

    def _parse_video_item(self, item: dict[str, Any]) -> YouTubeVideoResource:
        snippet = item.get("snippet", {})
        content_details = item.get("contentDetails", {})
        status = item.get("status", {})
        statistics = item.get("statistics", {})
        duration_seconds = parse_iso8601_duration(content_details.get("duration"))

        return YouTubeVideoResource(
            youtube_video_id=item["id"],
            title=snippet.get("title", ""),
            description=snippet.get("description"),
            published_at=parse_rfc3339(snippet.get("publishedAt")),
            channel_title=snippet.get("channelTitle"),
            duration_seconds=duration_seconds,
            category_id=snippet.get("categoryId"),
            tags_json=snippet.get("tags"),
            default_language=snippet.get("defaultLanguage"),
            default_audio_language=snippet.get("defaultAudioLanguage"),
            thumbnails_json=snippet.get("thumbnails"),
            live_broadcast_content=snippet.get("liveBroadcastContent"),
            is_short=bool(duration_seconds is not None and duration_seconds <= 60),
            made_for_kids=status.get("madeForKids"),
            licensed_content=content_details.get("licensedContent"),
            caption_status=content_details.get("caption"),
            privacy_status=status.get("privacyStatus"),
            upload_status=status.get("uploadStatus"),
            embeddable=status.get("embeddable"),
            view_count=self._parse_int(statistics.get("viewCount")),
            like_count=self._parse_int(statistics.get("likeCount")),
            comment_count=self._parse_int(statistics.get("commentCount")),
            favorite_count=self._parse_int(statistics.get("favoriteCount")),
            raw_json=item,
        )
