from __future__ import annotations

from dataclasses import replace

import pytest
from sqlalchemy import func, select

from youtube_competitor_tracker.exceptions import YouTubeAPIError
from youtube_competitor_tracker.models import (
    Channel,
    ChannelStatsSnapshot,
    ChannelSyncRun,
    SyncRunStatus,
    Video,
    VideoStatsSnapshot,
)
from youtube_competitor_tracker.services.channels import ChannelService
from youtube_competitor_tracker.sync.service import SyncService
from youtube_competitor_tracker.youtube.schemas import (
    ResolvedChannelReference,
    YouTubeChannelResource,
    YouTubeVideoResource,
)


class FakeYouTubeClient:
    def __init__(self, *, fail_on_playlist: bool = False) -> None:
        self.fail_on_playlist = fail_on_playlist
        self.channel_resource = YouTubeChannelResource(
            youtube_channel_id="UC1234567890123456789012",
            title="Example Channel",
            handle="@example",
            custom_url="@example",
            description="Example description",
            published_at=None,
            country="US",
            default_language="en",
            uploads_playlist_id="UU1234567890123456789012",
            subscriber_count=120,
            view_count=1000,
            video_count=2,
            thumbnails_json={"default": {"url": "https://example.com/channel.jpg"}},
            raw_json={"id": "UC1234567890123456789012"},
        )
        self.video_resources = [
            YouTubeVideoResource(
                youtube_video_id="video-1",
                title="Video One",
                description="Description 1",
                published_at=None,
                channel_title="Example Channel",
                duration_seconds=75,
                category_id="22",
                tags_json=["one"],
                default_language="en",
                default_audio_language="en",
                thumbnails_json={"default": {"url": "https://example.com/video-1.jpg"}},
                live_broadcast_content="none",
                is_short=False,
                made_for_kids=False,
                licensed_content=True,
                caption_status="true",
                privacy_status="public",
                upload_status="processed",
                embeddable=True,
                view_count=100,
                like_count=10,
                comment_count=5,
                favorite_count=0,
                raw_json={"id": "video-1"},
            ),
            YouTubeVideoResource(
                youtube_video_id="video-2",
                title="Video Two",
                description="Description 2",
                published_at=None,
                channel_title="Example Channel",
                duration_seconds=45,
                category_id="22",
                tags_json=["two"],
                default_language="en",
                default_audio_language="en",
                thumbnails_json={"default": {"url": "https://example.com/video-2.jpg"}},
                live_broadcast_content="none",
                is_short=True,
                made_for_kids=False,
                licensed_content=True,
                caption_status="true",
                privacy_status="public",
                upload_status="processed",
                embeddable=True,
                view_count=200,
                like_count=20,
                comment_count=6,
                favorite_count=0,
                raw_json={"id": "video-2"},
            ),
        ]

    def resolve_channel_reference(self, reference: str) -> ResolvedChannelReference:
        return ResolvedChannelReference(
            original_reference=reference,
            kind="handle",
            channel_id=self.channel_resource.youtube_channel_id,
            normalized_handle="@example",
        )

    def fetch_channel(self, channel_id: str, *, fallback_handle: str | None = None) -> YouTubeChannelResource:
        return replace(self.channel_resource, handle=fallback_handle or self.channel_resource.handle)

    def list_upload_video_ids(self, uploads_playlist_id: str) -> list[str]:
        if self.fail_on_playlist:
            raise YouTubeAPIError("playlist failure")
        return [video.youtube_video_id for video in self.video_resources]

    def fetch_videos(self, video_ids: list[str]) -> list[YouTubeVideoResource]:
        resources = [video for video in self.video_resources if video.youtube_video_id in video_ids]
        return resources

    def close(self) -> None:
        return None


def test_add_channel_is_idempotent_for_canonical_rows(session_factory) -> None:
    client = FakeYouTubeClient()

    with session_factory() as session:
        service = ChannelService(session, client)
        service.add_channel("@example")

    with session_factory() as session:
        service = ChannelService(session, client)
        service.add_channel("@example")

    with session_factory() as session:
        channel_count = session.scalar(select(func.count(Channel.id)))
        snapshot_count = session.scalar(select(func.count(ChannelStatsSnapshot.id)))
        assert channel_count == 1
        assert snapshot_count == 2


def test_sync_channel_creates_videos_snapshots_and_sync_run(session_factory) -> None:
    client = FakeYouTubeClient()

    with session_factory() as session:
        ChannelService(session, client).add_channel("@example")

    with session_factory() as session:
        run = SyncService(session, client).sync_channel("@example")
        assert run.status == SyncRunStatus.SUCCEEDED
        assert run.videos_discovered == 2
        assert run.videos_inserted == 2
        assert run.videos_updated == 0
        assert run.snapshots_created == 3

    with session_factory() as session:
        assert session.scalar(select(func.count(Video.id))) == 2
        assert session.scalar(select(func.count(VideoStatsSnapshot.id))) == 2
        assert session.scalar(select(func.count(ChannelSyncRun.id))) == 1


def test_repeat_sync_updates_existing_videos_without_duplicate_canonical_rows(session_factory) -> None:
    client = FakeYouTubeClient()

    with session_factory() as session:
        ChannelService(session, client).add_channel("@example")

    with session_factory() as session:
        SyncService(session, client).sync_channel("@example")

    client.video_resources[0] = replace(client.video_resources[0], view_count=150)

    with session_factory() as session:
        second_run = SyncService(session, client).sync_channel("@example")
        assert second_run.videos_inserted == 0
        assert second_run.videos_updated == 2
        assert second_run.snapshots_created == 3

    with session_factory() as session:
        assert session.scalar(select(func.count(Video.id))) == 2
        assert session.scalar(select(func.count(VideoStatsSnapshot.id))) == 4
        assert session.scalar(select(func.count(ChannelStatsSnapshot.id))) == 3
        first_video = session.scalar(select(Video).where(Video.youtube_video_id == "video-1"))
        assert first_video is not None
        assert first_video.view_count == 150


def test_failed_sync_marks_run_failed(session_factory) -> None:
    add_client = FakeYouTubeClient()
    failing_client = FakeYouTubeClient(fail_on_playlist=True)

    with session_factory() as session:
        ChannelService(session, add_client).add_channel("@example")

    with session_factory() as session:
        with pytest.raises(YouTubeAPIError):
            SyncService(session, failing_client).sync_channel("@example")

    with session_factory() as session:
        run = session.scalar(select(ChannelSyncRun).order_by(ChannelSyncRun.id.desc()))
        assert run is not None
        assert run.status == SyncRunStatus.FAILED
        assert "playlist failure" in (run.error_message or "")
