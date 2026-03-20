from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, Boolean, DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from youtube_competitor_tracker.db.base import Base
from youtube_competitor_tracker.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from youtube_competitor_tracker.models.snapshot import ChannelStatsSnapshot
    from youtube_competitor_tracker.models.sync_run import ChannelSyncRun
    from youtube_competitor_tracker.models.video import Video


class Channel(TimestampMixin, Base):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    youtube_channel_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    handle: Mapped[str | None] = mapped_column(String(255), index=True)
    custom_url: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    country: Mapped[str | None] = mapped_column(String(16))
    default_language: Mapped[str | None] = mapped_column(String(32))
    uploads_playlist_id: Mapped[str | None] = mapped_column(String(64))
    subscriber_count: Mapped[int | None] = mapped_column(BigInteger)
    view_count: Mapped[int | None] = mapped_column(BigInteger)
    video_count: Mapped[int | None] = mapped_column(BigInteger)
    thumbnails_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    videos: Mapped[list["Video"]] = relationship(
        back_populates="channel",
        cascade="all, delete-orphan",
    )
    stats_snapshots: Mapped[list["ChannelStatsSnapshot"]] = relationship(
        back_populates="channel",
        cascade="all, delete-orphan",
    )
    sync_runs: Mapped[list["ChannelSyncRun"]] = relationship(
        back_populates="channel",
        cascade="all, delete-orphan",
    )
