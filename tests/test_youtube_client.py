from __future__ import annotations

import httpx
import respx

from youtube_competitor_tracker.youtube.client import YouTubeClient


@respx.mock
def test_resolve_channel_reference_by_handle() -> None:
    route = respx.get("https://www.googleapis.com/youtube/v3/channels").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "UC1234567890123456789012",
                        "snippet": {"title": "Example Channel"},
                    }
                ]
            },
        )
    )
    client = YouTubeClient(api_key="test-key", retry_backoff_seconds=0)

    resolved = client.resolve_channel_reference("@example")

    assert resolved.channel_id == "UC1234567890123456789012"
    assert resolved.normalized_handle == "@example"
    assert route.called
    assert route.calls[0].request.url.params["forHandle"] == "example"


@respx.mock
def test_list_upload_video_ids_handles_pagination() -> None:
    route = respx.get("https://www.googleapis.com/youtube/v3/playlistItems").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "items": [{"contentDetails": {"videoId": "video-1"}}],
                    "nextPageToken": "NEXT",
                },
            ),
            httpx.Response(
                200,
                json={
                    "items": [{"contentDetails": {"videoId": "video-2"}}],
                },
            ),
        ]
    )
    client = YouTubeClient(api_key="test-key", retry_backoff_seconds=0)

    video_ids = client.list_upload_video_ids("UU123")

    assert video_ids == ["video-1", "video-2"]
    assert route.call_count == 2


@respx.mock
def test_fetch_videos_parses_metadata_fields() -> None:
    respx.get("https://www.googleapis.com/youtube/v3/videos").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "video-1",
                        "snippet": {
                            "title": "A video",
                            "publishedAt": "2025-01-01T00:00:00Z",
                            "channelTitle": "Example Channel",
                            "categoryId": "22",
                            "tags": ["one", "two"],
                            "thumbnails": {"default": {"url": "https://example.com/thumb.jpg"}},
                            "liveBroadcastContent": "none",
                        },
                        "contentDetails": {
                            "duration": "PT55S",
                            "caption": "true",
                            "licensedContent": True,
                        },
                        "status": {
                            "privacyStatus": "public",
                            "uploadStatus": "processed",
                            "embeddable": True,
                            "madeForKids": False,
                        },
                        "statistics": {
                            "viewCount": "10",
                            "likeCount": "2",
                            "commentCount": "1",
                            "favoriteCount": "0",
                        },
                    }
                ]
            },
        )
    )
    client = YouTubeClient(api_key="test-key", retry_backoff_seconds=0)

    videos = client.fetch_videos(["video-1"])

    assert len(videos) == 1
    video = videos[0]
    assert video.youtube_video_id == "video-1"
    assert video.duration_seconds == 55
    assert video.is_short is True
    assert video.view_count == 10
    assert video.caption_status == "true"
