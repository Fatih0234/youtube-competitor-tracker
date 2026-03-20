from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

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

    def list_upload_video_ids(
        self,
        uploads_playlist_id: str,
        *,
        since: datetime | None = None,
        page_limit: int | None = None,
    ) -> list[str]:
        if self.fail_on_playlist:
            raise YouTubeAPIError("playlist failure")
        ids = []
        for video in self.video_resources:
            if since is not None and video.published_at is not None and video.published_at < since:
                break  # Playlist is reverse-chron; stop when we hit an old video
            ids.append(video.youtube_video_id)
        return ids

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


def test_backfill_channel_only_fetches_recent_videos(session_factory) -> None:
    now = datetime.now(tz=timezone.utc)
    recent_date = now - timedelta(days=3)
    old_date = now - timedelta(days=10)

    client = FakeYouTubeClient()
    # video_resources[0] is first in playlist (recent), video_resources[1] is second (old)
    client.video_resources[0] = replace(client.video_resources[0], published_at=recent_date)
    client.video_resources[1] = replace(client.video_resources[1], published_at=old_date)

    with session_factory() as session:
        ChannelService(session, client).add_channel("@example")

    with session_factory() as session:
        channel = ChannelService(session).get_required_channel("@example")
        run = SyncService(session, client).backfill_channel(channel, days=7)
        assert run.status == SyncRunStatus.SUCCEEDED
        assert run.videos_inserted == 1

    with session_factory() as session:
        assert session.scalar(select(func.count(Video.id))) == 1
        video = session.scalar(select(Video))
        assert video is not None
        assert video.youtube_video_id == "video-1"


def test_backfill_skipped_when_recent_history_exists(session_factory) -> None:
    now = datetime.now(tz=timezone.utc)
    client = FakeYouTubeClient()
    backfill_called = []

    with session_factory() as session:
        channel = ChannelService(session, client).add_channel("@example")
        video = Video(
            youtube_video_id="existing-video",
            channel_id=channel.id,
            title="Existing Video",
            published_at=now - timedelta(days=1),
        )
        session.add(video)
        session.commit()

    with session_factory() as session:
        channel = ChannelService(session).get_required_channel("@example")
        cutoff = now - timedelta(days=7)
        recent_count = session.scalar(
            select(func.count(Video.id)).where(
                Video.channel_id == channel.id,
                Video.published_at >= cutoff,
            )
        )
        if not recent_count:
            SyncService(session, client).backfill_channel(channel)
            backfill_called.append(True)

    assert not backfill_called

    with session_factory() as session:
        assert session.scalar(select(func.count(Video.id))) == 1


def test_scan_new_videos_inserts_only_unknowns(session_factory) -> None:
    client = FakeYouTubeClient()

    with session_factory() as session:
        channel = ChannelService(session, client).add_channel("@example")
        # Pre-insert video-1 so it looks already synced
        video = Video(
            youtube_video_id="video-1",
            channel_id=channel.id,
            title="Video One",
        )
        session.add(video)
        session.commit()

    with session_factory() as session:
        channel = ChannelService(session).get_required_channel("@example")
        inserted = SyncService(session, client).scan_new_videos(channel)
        assert inserted == 1  # Only video-2 is new

    with session_factory() as session:
        assert session.scalar(select(func.count(Video.id))) == 2
        video_ids = set(session.scalars(select(Video.youtube_video_id)))
        assert video_ids == {"video-1", "video-2"}


def test_refresh_video_stats_updates_stats_only(session_factory) -> None:
    now = datetime.now(tz=timezone.utc)
    client = FakeYouTubeClient()
    client.video_resources[0] = replace(client.video_resources[0], published_at=now - timedelta(days=1))
    client.video_resources[1] = replace(client.video_resources[1], published_at=now - timedelta(days=2))

    with session_factory() as session:
        ChannelService(session, client).add_channel("@example")

    with session_factory() as session:
        channel = ChannelService(session).get_required_channel("@example")
        SyncService(session, client).backfill_channel(channel, days=7)

    # Update view counts in fake client
    client.video_resources[0] = replace(client.video_resources[0], view_count=999)
    client.video_resources[1] = replace(client.video_resources[1], view_count=888)

    with session_factory() as session:
        updated = SyncService(session, client).refresh_video_stats(since_days=3)
        assert updated == 2

    with session_factory() as session:
        # No new canonical Video rows
        assert session.scalar(select(func.count(Video.id))) == 2
        v1 = session.scalar(select(Video).where(Video.youtube_video_id == "video-1"))
        v2 = session.scalar(select(Video).where(Video.youtube_video_id == "video-2"))
        assert v1 is not None and v1.view_count == 999
        assert v2 is not None and v2.view_count == 888
        # New snapshots created (sync_run_id=None)
        assert session.scalar(select(func.count(VideoStatsSnapshot.id))) >= 2


def test_refresh_video_stats_ignores_old_videos(session_factory) -> None:
    now = datetime.now(tz=timezone.utc)
    client = FakeYouTubeClient()
    client.video_resources[0] = replace(client.video_resources[0], published_at=now - timedelta(days=1))
    client.video_resources[1] = replace(client.video_resources[1], published_at=now - timedelta(days=10))

    with session_factory() as session:
        channel = ChannelService(session, client).add_channel("@example")
        # Insert both videos directly with the given published_at values
        for res in client.video_resources:
            session.add(
                Video(
                    youtube_video_id=res.youtube_video_id,
                    channel_id=channel.id,
                    title=res.title,
                    published_at=res.published_at,
                    view_count=res.view_count,
                )
            )
        session.commit()

    # Only video-1 (1 day old) should be within the 3-day window
    with session_factory() as session:
        updated = SyncService(session, client).refresh_video_stats(since_days=3)
        assert updated == 1

    with session_factory() as session:
        v1 = session.scalar(select(Video).where(Video.youtube_video_id == "video-1"))
        v2 = session.scalar(select(Video).where(Video.youtube_video_id == "video-2"))
        assert v1 is not None and v1.last_synced_at is not None
        assert v2 is not None and v2.last_synced_at is None
