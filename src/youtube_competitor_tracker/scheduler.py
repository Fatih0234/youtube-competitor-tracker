from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from youtube_competitor_tracker.config import get_settings
from youtube_competitor_tracker.db.session import create_session_factory, session_scope
from youtube_competitor_tracker.sync.service import SyncService
from youtube_competitor_tracker.youtube.client import YouTubeClient

logger = logging.getLogger(__name__)


def run_scheduled_sync() -> None:
    settings = get_settings()
    youtube_client = YouTubeClient(
        api_key=settings.require_youtube_api_key(),
        timeout=settings.request_timeout_seconds,
        retry_attempts=settings.http_retry_attempts,
        retry_backoff_seconds=settings.http_retry_backoff_seconds,
    )
    try:
        with session_scope(create_session_factory(settings)) as session:
            service = SyncService(session, youtube_client)
            summary = service.scheduled_sync_all(
                metrics_window_days=settings.metrics_window_days
            )
            logger.info("Scheduled sync completed: %s", summary)
    finally:
        youtube_client.close()


def start_scheduler() -> None:
    settings = get_settings()
    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_scheduled_sync,
        "interval",
        hours=settings.scheduler_interval_hours,
        id="scheduled_sync",
    )
    run_scheduled_sync()
    try:
        scheduler.start()
    except KeyboardInterrupt:
        scheduler.shutdown()
