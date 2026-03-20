from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from youtube_competitor_tracker.db.base import Base
from youtube_competitor_tracker.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from youtube_competitor_tracker.models.channel import Channel
    from youtube_competitor_tracker.models.snapshot import VideoStatsSnapshot


class Video(TimestampMixin, Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(primary_key=True)
    youtube_video_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    channel_title: Mapped[str | None] = mapped_column(String(255))
    duration_seconds: Mapped[int | None]
    category_id: Mapped[str | None] = mapped_column(String(32))
    tags_json: Mapped[list[str] | None] = mapped_column(JSON)
    default_language: Mapped[str | None] = mapped_column(String(32))
    default_audio_language: Mapped[str | None] = mapped_column(String(32))
    thumbnails_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    live_broadcast_content: Mapped[str | None] = mapped_column(String(32))
    is_short: Mapped[bool] = mapped_column(Boolean, default=False)
    made_for_kids: Mapped[bool | None] = mapped_column(Boolean)
    licensed_content: Mapped[bool | None] = mapped_column(Boolean)
    caption_status: Mapped[str | None] = mapped_column(String(32))
    privacy_status: Mapped[str | None] = mapped_column(String(32))
    upload_status: Mapped[str | None] = mapped_column(String(32))
    embeddable: Mapped[bool | None] = mapped_column(Boolean)
    view_count: Mapped[int | None] = mapped_column(BigInteger)
    like_count: Mapped[int | None] = mapped_column(BigInteger)
    comment_count: Mapped[int | None] = mapped_column(BigInteger)
    favorite_count: Mapped[int | None] = mapped_column(BigInteger)
    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    viral_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    viral_score_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    channel: Mapped["Channel"] = relationship(back_populates="videos")
    stats_snapshots: Mapped[list["VideoStatsSnapshot"]] = relationship(
        back_populates="video",
        cascade="all, delete-orphan",
    )
