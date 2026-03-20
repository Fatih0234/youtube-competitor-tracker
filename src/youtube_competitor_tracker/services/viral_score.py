from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import exp, log1p

from sqlalchemy import select
from sqlalchemy.orm import Session

from youtube_competitor_tracker.models import Channel, Video, VideoStatsSnapshot


@dataclass(slots=True, frozen=True)
class ScoredVideo:
    channel_title: str
    youtube_video_id: str
    title: str
    published_at: datetime | None
    is_short: bool
    view_count: int
    like_count: int
    comment_count: int
    weighted_engagement: float
    quality: float
    view_momentum: float
    engagement_momentum: float
    freshness: float
    viral_score: float


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def weighted_engagement(like_count: int, comment_count: int) -> float:
    return like_count + 4 * comment_count


def quality(weng: float, view_count: int) -> float:
    return weng / max(view_count, 1)


def reach(view_count: int) -> float:
    return log1p(view_count)


def freshness(age_hours: float) -> float:
    return exp(-age_hours / 72)


def momentum_from_snapshots(
    snapshots: list[VideoStatsSnapshot],
    now: datetime,
) -> tuple[float, float]:
    """Return (view_momentum, engagement_momentum) in units-per-hour.

    Prefers a 12-hour window; falls back to 48h; returns (0.0, 0.0) if
    fewer than 2 snapshots or no window spans at least 1 minute.
    """
    if len(snapshots) < 2:
        return 0.0, 0.0

    def _compute(oldest: VideoStatsSnapshot, newest: VideoStatsSnapshot) -> tuple[float, float] | None:
        delta_hours = (newest.snapshot_at - oldest.snapshot_at).total_seconds() / 3600
        if delta_hours < 1 / 60:  # less than 1 minute
            return None
        dv = (newest.view_count or 0) - (oldest.view_count or 0)
        dl = (newest.like_count or 0) - (oldest.like_count or 0)
        dc = (newest.comment_count or 0) - (oldest.comment_count or 0)
        dweng = dl + 4 * dc
        return dv / delta_hours, dweng / delta_hours

    def _snap_ts(s: VideoStatsSnapshot) -> float:
        sat = s.snapshot_at
        if sat.tzinfo is None:
            sat = sat.replace(tzinfo=timezone.utc)
        return sat.timestamp()

    cutoff_12h = now.timestamp() - 12 * 3600
    within_12h = [s for s in snapshots if _snap_ts(s) >= cutoff_12h]
    if len(within_12h) >= 2:
        result = _compute(within_12h[0], within_12h[-1])
        if result is not None:
            return result

    result = _compute(snapshots[0], snapshots[-1])
    return result if result is not None else (0.0, 0.0)


def percentile_rank(values: list[float]) -> list[float]:
    """Return per-item percentile rank in [0, 1].

    Ties broken by first occurrence (lower index = lower rank).
    For n=1 returns [1.0].
    """
    n = len(values)
    if n == 0:
        return []
    if n == 1:
        return [1.0]
    sorted_vals = sorted(set(values))
    rank_map: dict[float, float] = {}
    for v in values:
        if v not in rank_map:
            rank_map[v] = (sorted_vals.index(v) + 1) / n
    return [rank_map[v] for v in values]


# ---------------------------------------------------------------------------
# DB layer
# ---------------------------------------------------------------------------


def fetch_candidate_videos(
    session: Session,
    *,
    max_age_days: int = 14,
    now: datetime,
) -> list[Video]:
    from datetime import timedelta

    cutoff = now - timedelta(days=max_age_days)
    stmt = (
        select(Video)
        .join(Channel, Video.channel_id == Channel.id)
        .where(
            Channel.is_active == True,  # noqa: E712
            Video.published_at >= cutoff,
        )
    )
    return list(session.scalars(stmt).all())


def fetch_snapshot_map(
    session: Session,
    video_ids: list[int],
    *,
    now: datetime,
) -> dict[int, list[VideoStatsSnapshot]]:
    """Return {video_id: [snapshots ordered by snapshot_at asc]} for 48h window."""
    if not video_ids:
        return {}

    from datetime import timedelta

    cutoff = now - timedelta(hours=48)
    stmt = (
        select(VideoStatsSnapshot)
        .where(
            VideoStatsSnapshot.video_id.in_(video_ids),
            VideoStatsSnapshot.snapshot_at >= cutoff,
        )
        .order_by(VideoStatsSnapshot.snapshot_at.asc())
    )
    result: dict[int, list[VideoStatsSnapshot]] = {}
    for snap in session.scalars(stmt).all():
        result.setdefault(snap.video_id, []).append(snap)
    return result


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def compute_viral_scores(
    videos: list[Video],
    snapshot_map: dict[int, list[VideoStatsSnapshot]],
    now: datetime,
) -> list[ScoredVideo]:
    if not videos:
        return []

    # Build intermediate records
    records: list[dict] = []
    for video in videos:
        snaps = snapshot_map.get(video.id, [])
        if video.published_at:
            pub = video.published_at
            if pub.tzinfo is None:
                pub = pub.replace(tzinfo=timezone.utc)
            age_hours = (now - pub).total_seconds() / 3600
        else:
            age_hours = 0.0
        vc = video.view_count or 0
        lc = video.like_count or 0
        cc = video.comment_count or 0
        weng = weighted_engagement(lc, cc)
        vm, em = momentum_from_snapshots(snaps, now)
        records.append(
            {
                "video": video,
                "age_hours": age_hours,
                "vc": vc,
                "lc": lc,
                "cc": cc,
                "weng": weng,
                "qual": quality(weng, vc),
                "reach": reach(vc),
                "view_momentum": vm,
                "eng_momentum": em,
                "freshness": freshness(age_hours),
            }
        )

    def _score_group(group: list[dict]) -> list[ScoredVideo]:
        if not group:
            return []
        vm_ranks = percentile_rank([r["view_momentum"] for r in group])
        reach_ranks = percentile_rank([r["reach"] for r in group])
        qual_ranks = percentile_rank([r["qual"] for r in group])
        em_ranks = percentile_rank([r["eng_momentum"] for r in group])

        scored = []
        for r, vmr, rr, qr, emr in zip(group, vm_ranks, reach_ranks, qual_ranks, em_ranks):
            v: Video = r["video"]
            vscore = r["freshness"] * (0.45 * vmr + 0.25 * rr + 0.20 * qr + 0.10 * emr)
            scored.append(
                ScoredVideo(
                    channel_title=v.channel_title or "",
                    youtube_video_id=v.youtube_video_id,
                    title=v.title,
                    published_at=v.published_at,
                    is_short=v.is_short,
                    view_count=r["vc"],
                    like_count=r["lc"],
                    comment_count=r["cc"],
                    weighted_engagement=r["weng"],
                    quality=r["qual"],
                    view_momentum=r["view_momentum"],
                    engagement_momentum=r["eng_momentum"],
                    freshness=r["freshness"],
                    viral_score=vscore,
                )
            )
        return scored

    shorts = [r for r in records if r["video"].is_short]
    long_form = [r for r in records if not r["video"].is_short]

    all_scored = _score_group(shorts) + _score_group(long_form)
    all_scored.sort(key=lambda sv: sv.viral_score, reverse=True)
    return all_scored


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def rank_viral_videos(
    session: Session,
    *,
    max_age_days: int = 14,
    now: datetime | None = None,
) -> list[ScoredVideo]:
    if now is None:
        now = datetime.now(timezone.utc)

    videos = fetch_candidate_videos(session, max_age_days=max_age_days, now=now)
    video_ids = [v.id for v in videos]
    snapshot_map = fetch_snapshot_map(session, video_ids, now=now)
    return compute_viral_scores(videos, snapshot_map, now)
