from __future__ import annotations

from typing import Iterable

import typer

from youtube_competitor_tracker.config import Settings, get_settings
from youtube_competitor_tracker.db.migrations import upgrade_database
from youtube_competitor_tracker.db.session import create_session_factory, session_scope
from youtube_competitor_tracker.exceptions import TrackerError
from youtube_competitor_tracker.logging import configure_logging
from youtube_competitor_tracker.models import Channel, Video
from youtube_competitor_tracker.services.channels import ChannelService
from youtube_competitor_tracker.sync.service import SyncService
from youtube_competitor_tracker.youtube.client import YouTubeClient

app = typer.Typer(help="Developer-oriented CLI for YouTube channel/video ingestion.")


def build_settings() -> Settings:
    return get_settings()


def build_session_factory(settings: Settings):
    return create_session_factory(settings)


def build_youtube_client(settings: Settings) -> YouTubeClient:
    return YouTubeClient(
        api_key=settings.require_youtube_api_key(),
        timeout=settings.request_timeout_seconds,
        retry_attempts=settings.http_retry_attempts,
        retry_backoff_seconds=settings.http_retry_backoff_seconds,
    )


def handle_error(exc: Exception) -> None:
    typer.secho(str(exc), err=True, fg=typer.colors.RED)
    raise typer.Exit(code=1) from exc


def render_channels(channels: Iterable[Channel]) -> None:
    for channel in channels:
        typer.echo(
            f"{channel.id}\t{channel.youtube_channel_id}\t{channel.handle or '-'}\t"
            f"{channel.title}\tactive={channel.is_active}"
        )


def render_videos(videos: Iterable[Video]) -> None:
    for video in videos:
        typer.echo(
            f"{video.youtube_video_id}\t{video.published_at or '-'}\t"
            f"{video.view_count or 0}\t{video.title}"
        )


@app.command("init-db")
def init_db() -> None:
    """Apply migrations to the configured database."""

    settings = build_settings()
    configure_logging(settings.log_level)
    try:
        upgrade_database(settings.database_url)
    except Exception as exc:
        handle_error(exc)
    typer.echo(f"Database initialized at {settings.database_url}")


@app.command("add-channel")
def add_channel(channel_reference: str) -> None:
    """Resolve and store a tracked channel."""

    settings = build_settings()
    configure_logging(settings.log_level)
    youtube_client = build_youtube_client(settings)
    try:
        with session_scope(build_session_factory(settings)) as session:
            service = ChannelService(session, youtube_client)
            channel = service.add_channel(channel_reference)
            typer.echo(f"Tracked channel {channel.title} ({channel.youtube_channel_id})")
    except Exception as exc:
        handle_error(exc)
    finally:
        youtube_client.close()


@app.command("sync-channel")
def sync_channel(channel_reference_or_channel_id: str) -> None:
    """Sync a tracked channel and record fresh snapshots."""

    settings = build_settings()
    configure_logging(settings.log_level)
    youtube_client = build_youtube_client(settings)
    try:
        with session_scope(build_session_factory(settings)) as session:
            service = SyncService(session, youtube_client)
            run = service.sync_channel(channel_reference_or_channel_id)
            typer.echo(
                f"Sync run {run.id} completed: discovered={run.videos_discovered} "
                f"inserted={run.videos_inserted} updated={run.videos_updated} "
                f"snapshots={run.snapshots_created}"
            )
    except Exception as exc:
        handle_error(exc)
    finally:
        youtube_client.close()


@app.command("sync-all")
def sync_all() -> None:
    """Sync all active tracked channels."""

    settings = build_settings()
    configure_logging(settings.log_level)
    youtube_client = build_youtube_client(settings)
    try:
        with session_scope(build_session_factory(settings)) as session:
            service = SyncService(session, youtube_client)
            runs = service.sync_all()
            typer.echo(f"Completed {len(runs)} sync runs.")
    except Exception as exc:
        handle_error(exc)
    finally:
        youtube_client.close()


@app.command("list-channels")
def list_channels() -> None:
    """List locally tracked channels."""

    settings = build_settings()
    configure_logging(settings.log_level)
    try:
        with session_scope(build_session_factory(settings)) as session:
            channels = ChannelService(session).list_channels()
            render_channels(channels)
    except Exception as exc:
        handle_error(exc)


@app.command("show-channel")
def show_channel(channel_reference_or_channel_id: str) -> None:
    """Show one locally tracked channel."""

    settings = build_settings()
    configure_logging(settings.log_level)
    try:
        with session_scope(build_session_factory(settings)) as session:
            channel = ChannelService(session).get_required_channel(channel_reference_or_channel_id)
            typer.echo(f"id: {channel.id}")
            typer.echo(f"youtube_channel_id: {channel.youtube_channel_id}")
            typer.echo(f"title: {channel.title}")
            typer.echo(f"handle: {channel.handle or '-'}")
            typer.echo(f"uploads_playlist_id: {channel.uploads_playlist_id or '-'}")
            typer.echo(f"last_synced_at: {channel.last_synced_at or '-'}")
    except Exception as exc:
        handle_error(exc)


@app.command("list-videos")
def list_videos(channel: str = typer.Option(..., "--channel", help="Tracked channel id or reference.")) -> None:
    """List videos for a tracked channel."""

    settings = build_settings()
    configure_logging(settings.log_level)
    try:
        with session_scope(build_session_factory(settings)) as session:
            videos = ChannelService(session).list_videos_for_channel(channel)
            render_videos(videos)
    except Exception as exc:
        handle_error(exc)


def main() -> None:
    app()
