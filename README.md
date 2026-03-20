## YouTube Competitor Tracker Foundation

This repository is the foundation layer for a local-first YouTube ingestion system.
It focuses on boring, maintainable infrastructure for:

- tracking channels
- ingesting canonical channel and video metadata
- recording time-series stat snapshots
- running repeatable syncs without duplicate canonical records
- exposing the workflow through a developer-oriented CLI

## Requirements

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/)
- a YouTube Data API key for live API commands

## Quickstart

```bash
uv sync
cp .env.example .env
```

Set `YOUTUBE_API_KEY` in `.env`. You already have a local `.env`; the project reads it automatically.

Initialize the database and add a channel:

```bash
uv run youtube-competitor-tracker init-db
uv run youtube-competitor-tracker add-channel @YouTubeCreators
uv run youtube-competitor-tracker sync-channel @YouTubeCreators
```

Inspect tracked data:

```bash
uv run youtube-competitor-tracker list-channels
uv run youtube-competitor-tracker show-channel @YouTubeCreators
uv run youtube-competitor-tracker list-videos --channel @YouTubeCreators
```

## CLI Commands

- `init-db`
- `add-channel <channel_reference>`
- `sync-channel <channel_reference_or_channel_id>`
- `sync-all`
- `scheduled-sync` — scan new videos + refresh recent stats + update viral scores
- `list-channels`
- `show-channel <channel_reference_or_channel_id>`
- `list-videos --channel <channel_reference_or_channel_id>`
- `viral-scores` — print top videos ranked by viral score
- `update-viral-scores` — recompute and persist viral scores for all recent videos (backfill / manual re-run)

## Current Scope

In scope:

- channel registration
- channel metadata ingestion
- video metadata ingestion
- channel and video stat snapshots
- sync run logging
- SQLite-first local development

Out of scope for now:

- frontend or dashboards
- transcripts, comments, or thumbnails
- LLM enrichment
- notifications or workflow automation beyond scheduling readiness

## Viral Score

Two fields are persisted on every `videos` row:

| Field | Type | Description |
|---|---|---|
| `viral_score` | `FLOAT` | Score in roughly `[0, 1]` — how viral the video is at the time of scoring |
| `viral_score_updated_at` | `DATETIME (tz)` | When the score was last computed |

### How it is calculated

Shorts and long-form videos are scored **in separate pools** so they don't compete against each other.

Within each pool, five signals are computed per video:

| Signal | Formula |
|---|---|
| `weighted_engagement` | `likes + 4 × comments` |
| `quality` | `weighted_engagement / max(view_count, 1)` |
| `reach` | `log1p(view_count)` |
| `view_momentum` | views per hour over the last 12 h (falls back to 48 h window) |
| `engagement_momentum` | weighted-engagement per hour over the same window |
| `freshness` | `exp(-age_hours / 72)` — full weight when brand-new, near-zero after ~3 days |

The four growth/quality signals are converted to **percentile ranks** `[0, 1]` within the pool. The final score is:

```
viral_score = freshness × (0.45 × view_momentum_rank
                         + 0.25 × reach_rank
                         + 0.20 × quality_rank
                         + 0.10 × engagement_momentum_rank)
```

Scores are refreshed automatically on every `scheduled-sync` run and can be recomputed manually with `update-viral-scores`.

## Data Model

The project keeps:

- one canonical `channels` row per YouTube channel
- one canonical `videos` row per YouTube video
- append-only `channel_stats_snapshots`
- append-only `video_stats_snapshots`
- operational `channel_sync_runs`

Schema and sync semantics are documented in [docs/schema-and-sync.md](/Volumes/T7/youtube-competitor-tracker/docs/schema-and-sync.md).

## Development

Run tests:

```bash
uv run pytest
```

The automated test suite does not require a live API key.
