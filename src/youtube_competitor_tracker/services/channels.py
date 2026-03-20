from __future__ import annotations

from datetime import datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from youtube_competitor_tracker.exceptions import ChannelNotTrackedError
from youtube_competitor_tracker.models import Channel, ChannelStatsSnapshot, Video
from youtube_competitor_tracker.utils.datetime import utc_now
from youtube_competitor_tracker.utils.youtube import parse_channel_reference
from youtube_competitor_tracker.youtube.client import YouTubeClient
from youtube_competitor_tracker.youtube.schemas import YouTubeChannelResource


class ChannelService:
    """Persistence-oriented operations for tracked channels and local reads."""

    def __init__(self, session: Session, youtube_client: YouTubeClient | None = None) -> None:
        self.session = session
        self.youtube_client = youtube_client

    def add_channel(self, channel_reference: str) -> Channel:
        if self.youtube_client is None:
            raise RuntimeError("A YouTube client is required for add_channel.")

        resolved = self.youtube_client.resolve_channel_reference(channel_reference)
        resource = self.youtube_client.fetch_channel(
            resolved.channel_id,
            fallback_handle=resolved.normalized_handle,
        )
        channel, _ = self.upsert_channel_from_resource(
            resource,
            resolved_handle=resolved.normalized_handle,
            synced_at=utc_now(),
        )
        self.create_channel_snapshot(channel)
        self.session.commit()
        return channel

    def list_channels(self) -> list[Channel]:
        statement = select(Channel).order_by(Channel.title.asc(), Channel.id.asc())
        return list(self.session.scalars(statement))

    def list_videos_for_channel(self, channel_reference: str) -> list[Video]:
        channel = self.get_required_channel(channel_reference)
        statement = (
            select(Video)
            .where(Video.channel_id == channel.id)
            .order_by(Video.published_at.desc(), Video.id.desc())
        )
        return list(self.session.scalars(statement))

    def get_required_channel(self, channel_reference: str) -> Channel:
        channel = self.get_channel_by_reference(channel_reference)
        if channel is None:
            raise ChannelNotTrackedError(f"Channel `{channel_reference}` is not tracked.")
        return channel

    def get_channel_by_reference(self, channel_reference: str) -> Channel | None:
        reference = channel_reference.strip()
        statement: Select[tuple[Channel]]

        if reference.isdigit():
            statement = select(Channel).where(Channel.id == int(reference))
            return self.session.scalar(statement)

        try:
            kind, normalized = parse_channel_reference(reference)
        except ValueError:
            statement = select(Channel).where(Channel.custom_url == reference)
            return self.session.scalar(statement)

        if kind == "channel_id":
            statement = select(Channel).where(Channel.youtube_channel_id == normalized)
            return self.session.scalar(statement)

        statement = select(Channel).where(Channel.handle == normalized)
        return self.session.scalar(statement)

    def upsert_channel_from_resource(
        self,
        resource: YouTubeChannelResource,
        *,
        resolved_handle: str | None = None,
        synced_at: datetime | None = None,
    ) -> tuple[Channel, bool]:
        channel = self.session.scalar(
            select(Channel).where(Channel.youtube_channel_id == resource.youtube_channel_id)
        )
        created = channel is None
        if channel is None:
            channel = Channel(
                youtube_channel_id=resource.youtube_channel_id,
                title=resource.title,
            )
            self.session.add(channel)

        channel.title = resource.title
        channel.handle = resource.handle or resolved_handle
        channel.custom_url = resource.custom_url
        channel.description = resource.description
        channel.published_at = resource.published_at
        channel.country = resource.country
        channel.default_language = resource.default_language
        channel.uploads_playlist_id = resource.uploads_playlist_id
        channel.subscriber_count = resource.subscriber_count
        channel.view_count = resource.view_count
        channel.video_count = resource.video_count
        channel.thumbnails_json = resource.thumbnails_json
        channel.raw_json = resource.raw_json
        channel.last_synced_at = synced_at or utc_now()

        self.session.flush()
        return channel, created

    def create_channel_snapshot(
        self,
        channel: Channel,
        *,
        captured_at: datetime | None = None,
        sync_run_id: int | None = None,
    ) -> ChannelStatsSnapshot:
        snapshot = ChannelStatsSnapshot(
            channel_id=channel.id,
            sync_run_id=sync_run_id,
            snapshot_at=captured_at or utc_now(),
            subscriber_count=channel.subscriber_count,
            view_count=channel.view_count,
            video_count=channel.video_count,
        )
        self.session.add(snapshot)
        self.session.flush()
        return snapshot
