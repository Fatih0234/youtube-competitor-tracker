from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from youtube_competitor_tracker.exceptions import ChannelNotTrackedError, YouTubeAPIError
from youtube_competitor_tracker.models import (
    Channel,
    ChannelSyncRun,
    SyncRunStatus,
    SyncType,
    Video,
    VideoStatsSnapshot,
)
from youtube_competitor_tracker.services.channels import ChannelService
from youtube_competitor_tracker.utils.datetime import utc_now
from youtube_competitor_tracker.youtube.client import YouTubeClient
from youtube_competitor_tracker.youtube.schemas import YouTubeVideoResource


@dataclass(slots=True)
class VideoSyncCounts:
    inserted: int = 0
    updated: int = 0
    snapshots_created: int = 0


class SyncService:
    """Stateful sync orchestration for tracked channels."""

    def __init__(self, session: Session, youtube_client: YouTubeClient) -> None:
        self.session = session
        self.youtube_client = youtube_client
        self.channel_service = ChannelService(session, youtube_client)

    def sync_channel(
        self,
        channel_reference: str,
        *,
        sync_type: SyncType = SyncType.INCREMENTAL,
    ) -> ChannelSyncRun:
        channel = self.channel_service.get_channel_by_reference(channel_reference)
        if channel is None:
            raise ChannelNotTrackedError(f"Channel `{channel_reference}` is not tracked.")
        return self.sync_tracked_channel(channel, sync_type=sync_type)

    def sync_tracked_channel(
        self,
        channel: Channel,
        *,
        sync_type: SyncType = SyncType.INCREMENTAL,
    ) -> ChannelSyncRun:
        started_at = utc_now()
        run = ChannelSyncRun(
            channel_id=channel.id,
            sync_type=sync_type,
            started_at=started_at,
            status=SyncRunStatus.RUNNING,
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)

        try:
            refreshed_channel = self.youtube_client.fetch_channel(
                channel.youtube_channel_id,
                fallback_handle=channel.handle,
            )
            channel, _ = self.channel_service.upsert_channel_from_resource(
                refreshed_channel,
                resolved_handle=channel.handle,
                synced_at=started_at,
            )
            self.channel_service.create_channel_snapshot(
                channel,
                captured_at=started_at,
                sync_run_id=run.id,
            )

            if not channel.uploads_playlist_id:
                raise YouTubeAPIError(
                    f"Channel `{channel.youtube_channel_id}` is missing an uploads playlist id."
                )

            discovered_video_ids = self.youtube_client.list_upload_video_ids(channel.uploads_playlist_id)
            video_resources = self.youtube_client.fetch_videos(discovered_video_ids)
            video_counts = self._upsert_videos(
                channel=channel,
                video_resources=video_resources,
                captured_at=started_at,
                sync_run_id=run.id,
            )

            missing_video_ids = sorted(
                set(discovered_video_ids) - {video.youtube_video_id for video in video_resources}
            )
            run.videos_discovered = len(discovered_video_ids)
            run.videos_inserted = video_counts.inserted
            run.videos_updated = video_counts.updated
            run.snapshots_created = 1 + video_counts.snapshots_created
            run.status = SyncRunStatus.SUCCEEDED
            run.finished_at = utc_now()
            run.metadata_json = {"missing_video_ids": missing_video_ids} if missing_video_ids else None
            self.session.commit()
            return run
        except Exception as exc:
            self.session.rollback()
            failed_run = self.session.get(ChannelSyncRun, run.id)
            if failed_run is not None:
                failed_run.status = SyncRunStatus.FAILED
                failed_run.finished_at = utc_now()
                failed_run.error_message = str(exc)
                self.session.commit()
            raise

    def backfill_channel(self, channel: Channel, *, days: int = 7) -> ChannelSyncRun:
        """Fetch and store the last `days` days of uploads for a channel."""
        started_at = utc_now()
        run = ChannelSyncRun(
            channel_id=channel.id,
            sync_type=SyncType.INITIAL_BACKFILL,
            started_at=started_at,
            status=SyncRunStatus.RUNNING,
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)

        try:
            if not channel.uploads_playlist_id:
                raise YouTubeAPIError(
                    f"Channel `{channel.youtube_channel_id}` is missing an uploads playlist id."
                )

            since = started_at - timedelta(days=days)
            video_ids = self.youtube_client.list_upload_video_ids(
                channel.uploads_playlist_id, since=since
            )
            video_resources = self.youtube_client.fetch_videos(video_ids)
            video_counts = self._upsert_videos(
                channel=channel,
                video_resources=video_resources,
                captured_at=started_at,
                sync_run_id=run.id,
            )

            run.videos_discovered = len(video_ids)
            run.videos_inserted = video_counts.inserted
            run.videos_updated = video_counts.updated
            run.snapshots_created = video_counts.snapshots_created
            run.status = SyncRunStatus.SUCCEEDED
            run.finished_at = utc_now()
            self.session.commit()
            return run
        except Exception as exc:
            self.session.rollback()
            failed_run = self.session.get(ChannelSyncRun, run.id)
            if failed_run is not None:
                failed_run.status = SyncRunStatus.FAILED
                failed_run.finished_at = utc_now()
                failed_run.error_message = str(exc)
                self.session.commit()
            raise

    def scan_new_videos(self, channel: Channel) -> int:
        """Fetch the first page of uploads and insert any unknown video IDs. Returns count inserted."""
        if not channel.uploads_playlist_id:
            return 0

        started_at = utc_now()
        run = ChannelSyncRun(
            channel_id=channel.id,
            sync_type=SyncType.INCREMENTAL,
            started_at=started_at,
            status=SyncRunStatus.RUNNING,
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)

        try:
            all_ids = self.youtube_client.list_upload_video_ids(
                channel.uploads_playlist_id, page_limit=1
            )

            existing_ids = set(
                self.session.scalars(
                    select(Video.youtube_video_id).where(
                        Video.youtube_video_id.in_(all_ids)
                    )
                )
            )
            new_ids = [vid_id for vid_id in all_ids if vid_id not in existing_ids]

            if new_ids:
                video_resources = self.youtube_client.fetch_videos(new_ids)
                video_counts = self._upsert_videos(
                    channel=channel,
                    video_resources=video_resources,
                    captured_at=started_at,
                    sync_run_id=run.id,
                )
            else:
                video_counts = VideoSyncCounts()

            run.videos_discovered = len(all_ids)
            run.videos_inserted = video_counts.inserted
            run.videos_updated = video_counts.updated
            run.snapshots_created = video_counts.snapshots_created
            run.status = SyncRunStatus.SUCCEEDED
            run.finished_at = utc_now()
            self.session.commit()
            return video_counts.inserted
        except Exception as exc:
            self.session.rollback()
            failed_run = self.session.get(ChannelSyncRun, run.id)
            if failed_run is not None:
                failed_run.status = SyncRunStatus.FAILED
                failed_run.finished_at = utc_now()
                failed_run.error_message = str(exc)
                self.session.commit()
            raise

    def refresh_video_stats(self, *, since_days: int = 3) -> int:
        """Update stats for videos published within the last `since_days` days. Returns count updated."""
        cutoff = utc_now() - timedelta(days=since_days)
        recent_videos = list(
            self.session.scalars(
                select(Video)
                .join(Channel, Video.channel_id == Channel.id)
                .where(
                    Video.published_at >= cutoff,
                    Channel.is_active.is_(True),
                )
            )
        )

        if not recent_videos:
            return 0

        captured_at = utc_now()
        video_ids = [v.youtube_video_id for v in recent_videos]
        id_to_video = {v.youtube_video_id: v for v in recent_videos}

        updated = 0
        for start in range(0, len(video_ids), 50):
            batch_ids = video_ids[start : start + 50]
            resources = self.youtube_client.fetch_videos(batch_ids)
            for resource in resources:
                video = id_to_video.get(resource.youtube_video_id)
                if video is None:
                    continue
                video.view_count = resource.view_count
                video.like_count = resource.like_count
                video.comment_count = resource.comment_count
                video.favorite_count = resource.favorite_count
                video.last_synced_at = captured_at

                snapshot = VideoStatsSnapshot(
                    video_id=video.id,
                    sync_run_id=None,
                    snapshot_at=captured_at,
                    view_count=resource.view_count,
                    like_count=resource.like_count,
                    comment_count=resource.comment_count,
                    favorite_count=resource.favorite_count,
                )
                self.session.add(snapshot)
                updated += 1

        self.session.commit()
        return updated

    def scheduled_sync_all(self, *, metrics_window_days: int = 3) -> dict:
        """Scan each active channel for new videos, then refresh stats for recent videos."""
        channels = list(
            self.session.scalars(
                select(Channel)
                .where(Channel.is_active.is_(True))
                .order_by(Channel.id.asc())
            )
        )
        new_videos = 0
        for channel in channels:
            new_videos += self.scan_new_videos(channel)

        stats_updated = self.refresh_video_stats(since_days=metrics_window_days)
        return {"new_videos": new_videos, "stats_updated": stats_updated}

    def sync_all(self) -> list[ChannelSyncRun]:
        channels = list(
            self.session.scalars(
                select(Channel)
                .where(Channel.is_active.is_(True))
                .order_by(Channel.id.asc())
            )
        )
        runs: list[ChannelSyncRun] = []
        for channel in channels:
            runs.append(self.sync_tracked_channel(channel, sync_type=SyncType.INCREMENTAL))
        return runs

    def _upsert_videos(
        self,
        *,
        channel: Channel,
        video_resources: list[YouTubeVideoResource],
        captured_at,
        sync_run_id: int,
    ) -> VideoSyncCounts:
        existing_videos = {
            video.youtube_video_id: video
            for video in self.session.scalars(
                select(Video).where(
                    Video.youtube_video_id.in_([item.youtube_video_id for item in video_resources])
                )
            )
        }
        counts = VideoSyncCounts()

        for resource in video_resources:
            video = existing_videos.get(resource.youtube_video_id)
            created = video is None
            if video is None:
                video = Video(
                    youtube_video_id=resource.youtube_video_id,
                    channel_id=channel.id,
                    title=resource.title,
                )
                self.session.add(video)

            video.channel_id = channel.id
            video.title = resource.title
            video.description = resource.description
            video.published_at = resource.published_at
            video.channel_title = resource.channel_title
            video.duration_seconds = resource.duration_seconds
            video.category_id = resource.category_id
            video.tags_json = resource.tags_json
            video.default_language = resource.default_language
            video.default_audio_language = resource.default_audio_language
            video.thumbnails_json = resource.thumbnails_json
            video.live_broadcast_content = resource.live_broadcast_content
            video.is_short = resource.is_short
            video.made_for_kids = resource.made_for_kids
            video.licensed_content = resource.licensed_content
            video.caption_status = resource.caption_status
            video.privacy_status = resource.privacy_status
            video.upload_status = resource.upload_status
            video.embeddable = resource.embeddable
            video.view_count = resource.view_count
            video.like_count = resource.like_count
            video.comment_count = resource.comment_count
            video.favorite_count = resource.favorite_count
            video.raw_json = resource.raw_json
            video.last_synced_at = captured_at
            self.session.flush()

            snapshot = VideoStatsSnapshot(
                video_id=video.id,
                sync_run_id=sync_run_id,
                snapshot_at=captured_at,
                view_count=video.view_count,
                like_count=video.like_count,
                comment_count=video.comment_count,
                favorite_count=video.favorite_count,
            )
            self.session.add(snapshot)

            if created:
                counts.inserted += 1
            else:
                counts.updated += 1
            counts.snapshots_created += 1

        self.session.flush()
        return counts
