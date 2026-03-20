from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from youtube_competitor_tracker.db.base import Base
from youtube_competitor_tracker.utils.datetime import utc_now


class ChannelStatsSnapshot(Base):
    __tablename__ = "channel_stats_snapshots"
    __table_args__ = (UniqueConstraint("channel_id", "sync_run_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"), index=True)
    sync_run_id: Mapped[int | None] = mapped_column(ForeignKey("channel_sync_runs.id"), index=True)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    subscriber_count: Mapped[int | None] = mapped_column(BigInteger)
    view_count: Mapped[int | None] = mapped_column(BigInteger)
    video_count: Mapped[int | None] = mapped_column(BigInteger)

    channel = relationship("Channel", back_populates="stats_snapshots")
    sync_run = relationship("ChannelSyncRun", back_populates="channel_snapshots")


class VideoStatsSnapshot(Base):
    __tablename__ = "video_stats_snapshots"
    __table_args__ = (UniqueConstraint("video_id", "sync_run_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"), index=True)
    sync_run_id: Mapped[int | None] = mapped_column(ForeignKey("channel_sync_runs.id"), index=True)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    view_count: Mapped[int | None] = mapped_column(BigInteger)
    like_count: Mapped[int | None] = mapped_column(BigInteger)
    comment_count: Mapped[int | None] = mapped_column(BigInteger)
    favorite_count: Mapped[int | None] = mapped_column(BigInteger)

    video = relationship("Video", back_populates="stats_snapshots")
    sync_run = relationship("ChannelSyncRun", back_populates="video_snapshots")
