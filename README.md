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
- `list-channels`
- `show-channel <channel_reference_or_channel_id>`
- `list-videos --channel <channel_reference_or_channel_id>`

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
