from __future__ import annotations

from enum import Enum


class SyncType(str, Enum):
    INITIAL_BACKFILL = "initial_backfill"
    INCREMENTAL = "incremental"
    RECONCILIATION = "reconciliation"


class SyncRunStatus(str, Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
