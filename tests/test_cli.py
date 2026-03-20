from __future__ import annotations

from typer.testing import CliRunner

from youtube_competitor_tracker.cli import app as cli_module
from youtube_competitor_tracker.cli.app import app
from youtube_competitor_tracker.config import Settings
from youtube_competitor_tracker.db.session import create_session_factory
from tests.test_sync_service import FakeYouTubeClient

runner = CliRunner()


def configure_cli_dependencies(monkeypatch, tmp_path):
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'cli.db'}",
        youtube_api_key="test-api-key",
        log_level="DEBUG",
        request_timeout_seconds=5.0,
        http_retry_attempts=1,
        http_retry_backoff_seconds=0.0,
    )

    monkeypatch.setattr(cli_module, "build_settings", lambda: settings)
    monkeypatch.setattr(cli_module, "build_session_factory", lambda configured: create_session_factory(configured))
    monkeypatch.setattr(cli_module, "build_youtube_client", lambda configured: FakeYouTubeClient())
    return settings


def test_init_db_command(monkeypatch, tmp_path) -> None:
    configure_cli_dependencies(monkeypatch, tmp_path)

    result = runner.invoke(app, ["init-db"])

    assert result.exit_code == 0
    assert "Database initialized" in result.stdout


def test_add_channel_and_list_channels_commands(monkeypatch, tmp_path) -> None:
    configure_cli_dependencies(monkeypatch, tmp_path)
    runner.invoke(app, ["init-db"])

    add_result = runner.invoke(app, ["add-channel", "@example"])
    list_result = runner.invoke(app, ["list-channels"])

    assert add_result.exit_code == 0
    assert "Tracked channel Example Channel" in add_result.stdout
    assert list_result.exit_code == 0
    assert "Example Channel" in list_result.stdout


def test_sync_channel_command(monkeypatch, tmp_path) -> None:
    configure_cli_dependencies(monkeypatch, tmp_path)
    runner.invoke(app, ["init-db"])
    runner.invoke(app, ["add-channel", "@example"])

    result = runner.invoke(app, ["sync-channel", "@example"])

    assert result.exit_code == 0
    assert "discovered=2" in result.stdout
