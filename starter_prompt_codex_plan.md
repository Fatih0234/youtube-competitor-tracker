# Starter Prompt for Codex (Plan Mode)

You are helping initialize a new Python project, using the **uv** package manager, in this GitHub repository:

- Repo: `https://github.com/Fatih0234/youtube-competitor-tracker`

## Mission

Build the **initial foundation** for a YouTube channel/video ingestion platform.

This is **not** a polished end-user product yet. It is the **data foundation** for future projects such as:
- competitor tracking
- content analysis
- trend analysis
- title/topic clustering
- AI-assisted idea generation
- channel comparison dashboards
- downstream ChatGPT project workflows

The goal of this phase is to create a **clean, maintainable, extensible skeleton project** that can reliably:
1. register YouTube channels to track,
2. fetch and persist channel metadata,
3. fetch and persist all discoverable videos for tracked channels,
4. store canonical video metadata,
5. store periodic metric snapshots for videos and optionally channels,
6. support repeatable refresh/sync runs without duplication,
7. serve as a reusable infrastructure layer for future features.

## Core philosophy

Optimize for:
- correctness
- simplicity
- maintainability
- idempotent sync behavior
- explicit boundaries between ingestion, storage, and later analysis
- easy local development
- easy future cron/job scheduling
- clear typing, logging, and tests

Do **not** optimize for fancy UI, premature abstractions, or speculative product features.

This should feel like a **boring but strong foundation**.

## Tech constraints

- Language: **Python**
- Package manager: **uv**
- Use modern Python project structure
- Prefer a clean `src/` layout
- Use type hints throughout
- Use environment variables for secrets/config
- The YouTube API key will be provided later by the user
- The project should still be buildable and testable without a live API key

## What to build in this first phase

### 1. Project structure
Set up a clean Python repository using `uv`, with a layout similar to this if appropriate:

```text
src/youtube_competitor_tracker/
    __init__.py
    config.py
    logging.py
    models/
    db/
    youtube/
    services/
    cli/
    sync/
    utils/
tests/
docs/
```

You may adapt the structure if you see a better version, but keep it simple and explicit.

### 2. Core domain entities
Design the initial data model around these core entities:

#### channels
Tracked YouTube channels.

Suggested fields:
- internal id
- youtube_channel_id
- title
- handle
- custom_url
- description
- published_at
- country
- default_language
- uploads_playlist_id
- subscriber_count
- view_count
- video_count
- thumbnails_json
- raw_json (optional but recommended)
- is_active
- created_at
- updated_at
- last_synced_at

#### videos
Canonical latest-known state of each video.

Suggested fields:
- internal id
- youtube_video_id
- youtube_channel_id or channel foreign key
- title
- description
- published_at
- channel_title
- duration
- category_id
- tags_json
- default_language
- default_audio_language
- thumbnails_json
- live_broadcast_content
- is_short (derive if reasonable, but do not overcomplicate)
- made_for_kids
- licensed_content
- caption_status or has_captions if available
- privacy_status if available
- upload_status if available
- embeddable if available
- view_count
- like_count
- comment_count
- favorite_count if returned
- raw_json (optional but recommended)
- created_at
- updated_at
- last_synced_at

#### video_stats_snapshots
Periodic point-in-time metrics for videos.

Suggested fields:
- internal id
- video foreign key
- snapshot_at
- view_count
- like_count
- comment_count
- favorite_count if available

#### channel_stats_snapshots
Optional but recommended if simple enough.

Suggested fields:
- internal id
- channel foreign key
- snapshot_at
- subscriber_count
- view_count
- video_count

#### channel_sync_runs
Operational tracking for sync jobs.

Suggested fields:
- internal id
- channel foreign key
- sync_type (initial_backfill / incremental / reconciliation)
- started_at
- finished_at
- status
- videos_discovered
- videos_inserted
- videos_updated
- snapshots_created
- error_message
- metadata_json

If you believe a slightly different schema is better, explain why and implement the improved version.

### 3. Storage choice
Choose a practical default storage layer for this starter project.

Preferred direction:
- use **SQLite** for local-first development
- use **SQLAlchemy 2.x** and **Alembic** if appropriate

Reasoning:
- easy local setup
- easy inspection
- low friction for development
- later portable to Postgres if needed

If you choose otherwise, justify it clearly.

### 4. YouTube ingestion layer
Create a YouTube API integration layer focused on public channel/video metadata ingestion.

At minimum, design and implement code paths for:
- fetching channel metadata for a specific channel id / handle / URL input
- resolving a channel into a canonical YouTube channel id
- discovering a channel's uploads playlist if needed
- listing all discoverable videos for tracked channels
- fetching detailed video metadata for batches of video ids

Important:
- design for retries and error handling
- keep API code isolated from database code
- make it possible to mock API responses in tests
- avoid deeply coupling business logic to raw HTTP calls

Use the official YouTube Data API patterns.

### 5. Sync workflow
Implement a clear first-pass sync workflow.

Minimum sync flows:

#### add-channel flow
- accept a channel reference from the user
- resolve it to a canonical YouTube channel
- fetch channel metadata
- persist the channel row
- optionally create an initial channel stats snapshot

#### initial backfill flow
- fetch all discoverable videos for that channel
- upsert canonical video rows
- create video metric snapshots
- record a sync run

#### refresh flow
- re-fetch tracked channel metadata
- refresh recent/known videos
- detect new videos
- update changed fields safely
- create fresh snapshots
- record a sync run

Idempotency matters:
- repeated syncs should not create duplicate channel/video rows
- snapshot creation should be intentional and traceable
- failures should be logged clearly

### 6. CLI interface
Provide a small but useful CLI for development and operations.

Suggested commands:
- `init-db`
- `add-channel <channel_reference>`
- `sync-channel <channel_id_or_ref>`
- `sync-all`
- `list-channels`
- `show-channel <channel_ref>`
- `list-videos --channel ...`

Use any solid CLI library if appropriate (for example Typer) but keep it simple.

### 7. Config and secrets
Use environment-based config.

Expected config values may include:
- `YOUTUBE_API_KEY`
- `DATABASE_URL`
- `LOG_LEVEL`
- sync-related knobs if useful

Provide:
- a `.env.example`
- clear setup instructions
- graceful behavior if API key is missing

### 8. Testing
Add meaningful tests.

At minimum:
- config tests
- model or persistence tests
- sync/idempotency tests where feasible
- mocked YouTube client tests
- CLI smoke tests if practical

The project should not depend on a live API key for the main test suite.

### 9. Documentation
Create concise but useful docs:
- README with project purpose and quickstart
- local setup using `uv`
- how to configure the API key
- how to run the CLI
- how the data model is organized
- what is in scope now vs later

## What is in scope

In scope for this initial project phase:
- tracked channel registry
- channel metadata ingestion
- video metadata ingestion
- stat snapshots
- sync logging
- local DB setup
- maintainable CLI
- tests and docs

## What is explicitly out of scope for now

Do **not** build these unless absolutely necessary as scaffolding:
- web frontend
- dashboards
- comments ingestion
- transcript ingestion
- thumbnail downloading pipeline
- LLM enrichment/classification
- notifications/alerts
- recommendation engines
- autonomous agent workflows
- multi-user auth
- generalized multi-platform content ingestion
- overengineered infrastructure

## Implementation guidance

Please work in **plan mode mindset** first:
1. inspect the repository state,
2. propose the initial project structure,
3. propose the schema,
4. propose the sync architecture,
5. identify tradeoffs,
6. then implement incrementally.

As you work:
- explain major choices briefly
- keep the architecture boring and clear
- favor explicit code over clever abstractions
- add TODO markers only where they are truly helpful
- keep future extensibility in mind, but do not overbuild

## Deliverables expected in this first coding pass

Aim to leave the repository with:
- initialized Python project using `uv`
- dependency setup
- source tree scaffold
- database models
- migrations if used
- YouTube client abstraction
- sync service skeleton with at least one working end-to-end flow
- CLI entrypoints
- tests
- README
- `.env.example`

## Important reasoning reminder

This repository is a **foundation project**.
It should be possible later to build many different products on top of it.
That means the current work should prioritize:
- a stable data model
- a clean ingestion pipeline
- maintainable code boundaries
- repeatable sync behavior

Do not drift into speculative product features.

Start by inspecting the current repo, then produce a short implementation plan, then begin building.
