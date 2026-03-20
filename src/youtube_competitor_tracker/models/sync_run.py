from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from youtube_competitor_tracker.db.base import Base
from youtube_competitor_tracker.models.enums import SyncRunStatus, SyncType
from youtube_competitor_tracker.utils.datetime import utc_now


class ChannelSyncRun(Base):
    __tablename__ = "channel_sync_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"), index=True)
    sync_type: Mapped[SyncType] = mapped_column(
        Enum(
            SyncType,
            native_enum=False,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        )
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[SyncRunStatus] = mapped_column(
        Enum(
            SyncRunStatus,
            native_enum=False,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=SyncRunStatus.RUNNING,
    )
    videos_discovered: Mapped[int] = mapped_column(Integer, default=0)
    videos_inserted: Mapped[int] = mapped_column(Integer, default=0)
    videos_updated: Mapped[int] = mapped_column(Integer, default=0)
    snapshots_created: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    channel = relationship("Channel", back_populates="sync_runs")
    channel_snapshots = relationship("ChannelStatsSnapshot", back_populates="sync_run")
    video_snapshots = relationship("VideoStatsSnapshot", back_populates="sync_run")
