from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from youtube_competitor_tracker.models import Channel, Video, VideoStatsSnapshot
from youtube_competitor_tracker.services.viral_score import (
    compute_viral_scores,
    fetch_candidate_videos,
    fetch_snapshot_map,
    momentum_from_snapshots,
    percentile_rank,
    rank_viral_videos,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def make_channel(session, *, title="Test Channel", youtube_channel_id="UC_test") -> Channel:
    ch = Channel(
        youtube_channel_id=youtube_channel_id,
        title=title,
        is_active=True,
    )
    session.add(ch)
    session.flush()
    return ch


def make_video(
    session,
    channel: Channel,
    *,
    youtube_video_id: str = "vid_001",
    title: str = "Test Video",
    published_at: datetime | None = None,
    is_short: bool = False,
    view_count: int = 1000,
    like_count: int = 50,
    comment_count: int = 10,
) -> Video:
    if published_at is None:
        published_at = NOW - timedelta(hours=6)
    v = Video(
        channel_id=channel.id,
        youtube_video_id=youtube_video_id,
        title=title,
        channel_title=channel.title,
        published_at=published_at,
        is_short=is_short,
        view_count=view_count,
        like_count=like_count,
        comment_count=comment_count,
    )
    session.add(v)
    session.flush()
    return v


def make_snapshot(
    session,
    video: Video,
    *,
    snapshot_at: datetime,
    view_count: int = 0,
    like_count: int = 0,
    comment_count: int = 0,
) -> VideoStatsSnapshot:
    snap = VideoStatsSnapshot(
        video_id=video.id,
        snapshot_at=snapshot_at,
        view_count=view_count,
        like_count=like_count,
        comment_count=comment_count,
    )
    session.add(snap)
    session.flush()
    return snap


# ---------------------------------------------------------------------------
# Unit tests for pure helpers
# ---------------------------------------------------------------------------


def test_percentile_rank_single():
    assert percentile_rank([42.0]) == [1.0]


def test_percentile_rank_multiple():
    ranks = percentile_rank([10.0, 20.0, 30.0])
    assert ranks == pytest.approx([1 / 3, 2 / 3, 1.0])


def test_percentile_rank_ties():
    ranks = percentile_rank([5.0, 5.0, 10.0])
    # Both 5.0 get same rank; 10.0 gets highest
    assert ranks[0] == ranks[1]
    assert ranks[2] > ranks[0]


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


def test_no_snapshot_history(session_factory):
    with session_factory() as session:
        ch = make_channel(session, youtube_channel_id="UC_a")
        make_video(session, ch, youtube_video_id="v_a", view_count=500)
        session.commit()

        results = rank_viral_videos(session, now=NOW)
        assert len(results) == 1
        sv = results[0]
        assert sv.view_momentum == pytest.approx(0.0)
        assert sv.engagement_momentum == pytest.approx(0.0)
        assert sv.viral_score >= 0.0


def test_zero_views(session_factory):
    with session_factory() as session:
        ch = make_channel(session, youtube_channel_id="UC_b")
        make_video(session, ch, youtube_video_id="v_b", view_count=0, like_count=0, comment_count=0)
        session.commit()

        results = rank_viral_videos(session, now=NOW)
        assert len(results) == 1
        assert results[0].viral_score >= 0.0


def test_fresh_fast_grower_vs_old_large(session_factory):
    """A fresh video with strong momentum should outrank an old video with raw view volume."""
    with session_factory() as session:
        ch = make_channel(session, youtube_channel_id="UC_c")

        # Fresh video: published 3h ago, good momentum
        fresh = make_video(
            session, ch,
            youtube_video_id="v_fresh",
            published_at=NOW - timedelta(hours=3),
            view_count=5_000,
        )
        make_snapshot(session, fresh, snapshot_at=NOW - timedelta(hours=2), view_count=2_000)
        make_snapshot(session, fresh, snapshot_at=NOW - timedelta(hours=1), view_count=5_000)

        # Old video: published 10 days ago, massive views but no recent growth
        old = make_video(
            session, ch,
            youtube_video_id="v_old",
            published_at=NOW - timedelta(days=10),
            view_count=500_000,
        )
        make_snapshot(session, old, snapshot_at=NOW - timedelta(hours=2), view_count=499_900)
        make_snapshot(session, old, snapshot_at=NOW - timedelta(hours=1), view_count=500_000)

        session.commit()

        results = rank_viral_videos(session, now=NOW)
        assert len(results) == 2
        ids = [r.youtube_video_id for r in results]
        assert ids[0] == "v_fresh", f"Expected fresh to rank first, got order: {ids}"


def test_shorts_and_long_form_ranked_separately(session_factory):
    """Both a short and a long-form video can achieve the maximum score independently."""
    with session_factory() as session:
        ch = make_channel(session, youtube_channel_id="UC_d")
        # Only one short → percentile_rank returns 1.0
        make_video(session, ch, youtube_video_id="v_short", is_short=True, view_count=100)
        # Only one long-form → also gets 1.0
        make_video(session, ch, youtube_video_id="v_long", is_short=False, view_count=100_000)
        session.commit()

        results = rank_viral_videos(session, now=NOW)
        assert len(results) == 2
        # Both should have the maximum possible blended rank (1.0) so viral_score == freshness
        for sv in results:
            assert sv.viral_score == pytest.approx(sv.freshness, rel=1e-6)


def test_high_ratio_tiny_vs_high_growth_high_reach(session_factory):
    """A 100-view video with 50% engagement ratio should lose to a 1M-view video with strong momentum."""
    with session_factory() as session:
        ch = make_channel(session, youtube_channel_id="UC_e")

        tiny = make_video(
            session, ch,
            youtube_video_id="v_tiny",
            view_count=100,
            like_count=50,
            comment_count=0,
            published_at=NOW - timedelta(hours=4),
        )

        big = make_video(
            session, ch,
            youtube_video_id="v_big",
            view_count=1_000_000,
            like_count=20_000,
            comment_count=5_000,
            published_at=NOW - timedelta(hours=4),
        )
        make_snapshot(session, big, snapshot_at=NOW - timedelta(hours=3), view_count=800_000)
        make_snapshot(session, big, snapshot_at=NOW - timedelta(hours=1), view_count=1_000_000)

        session.commit()

        results = rank_viral_videos(session, now=NOW)
        assert len(results) == 2
        ids = [r.youtube_video_id for r in results]
        assert ids[0] == "v_big", f"Expected big to rank first, got: {ids}"


def test_12h_window_preferred(session_factory):
    """Momentum should be computed from the 12h window when enough data exists."""
    with session_factory() as session:
        ch = make_channel(session, youtube_channel_id="UC_f")
        v = make_video(session, ch, youtube_video_id="v_12h", view_count=10_000)

        # Old snapshot (outside 12h but within 48h) — slow growth
        make_snapshot(session, v, snapshot_at=NOW - timedelta(hours=20), view_count=100)
        # Recent snapshots within 12h — fast growth
        make_snapshot(session, v, snapshot_at=NOW - timedelta(hours=10), view_count=5_000)
        make_snapshot(session, v, snapshot_at=NOW - timedelta(hours=1), view_count=10_000)

        session.commit()

        snaps = session.query(VideoStatsSnapshot).filter_by(video_id=v.id).order_by(VideoStatsSnapshot.snapshot_at).all()
        vm, em = momentum_from_snapshots(snaps, NOW)

        # 12h window: from -10h (5000 views) to -1h (10000 views) = 5000 views / 9h ≈ 555/h
        # 48h window: from -20h (100) to -1h (10000) = 9900 / 19h ≈ 521/h
        # 12h should give higher momentum
        expected_12h = (10_000 - 5_000) / 9.0
        assert vm == pytest.approx(expected_12h, rel=0.01)


def test_single_candidate(session_factory):
    """With exactly one candidate, percentile_rank=1.0 so viral_score equals freshness."""
    with session_factory() as session:
        ch = make_channel(session, youtube_channel_id="UC_g")
        make_video(
            session, ch,
            youtube_video_id="v_solo",
            published_at=NOW - timedelta(hours=24),
            view_count=1_000,
        )
        session.commit()

        results = rank_viral_videos(session, now=NOW)
        assert len(results) == 1
        sv = results[0]
        # All percentile ranks = 1.0, so viral_score = freshness * (0.45+0.25+0.20+0.10) = freshness
        assert sv.viral_score == pytest.approx(sv.freshness, rel=1e-6)
