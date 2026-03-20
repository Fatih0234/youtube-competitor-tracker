## Schema and Sync Notes

The foundation layer keeps current-state records separate from time-series snapshots.

### Canonical tables

- `channels`: one row per tracked YouTube channel
- `videos`: one row per canonical YouTube video

These rows are upserted on repeat syncs. Re-running a sync updates the existing row instead of creating duplicates.

### Snapshot tables

- `channel_stats_snapshots`
- `video_stats_snapshots`

Snapshots are append-only. Every sync creates one fresh snapshot for each touched channel and video, even when metrics did not change. When a snapshot is produced by a sync run, it stores `sync_run_id` for traceability.

### Operational table

- `channel_sync_runs`

Each sync attempt records:

- the channel
- sync type
- start and finish times
- success or failure status
- discovered and touched video counts
- snapshot count
- error details when a run fails

## Supported Workflows

### `add-channel`

1. Resolve a supported channel reference.
2. Fetch current channel metadata.
3. Upsert the canonical `channels` row.
4. Create one channel snapshot.

### `sync-channel`

1. Start a `channel_sync_runs` row with `running` status.
2. Refresh channel metadata and create a channel snapshot.
3. Enumerate the uploads playlist.
4. Fetch video details in batches.
5. Upsert canonical `videos` rows.
6. Create one video snapshot per touched video.
7. Finalize the sync run as `succeeded` or `failed`.

### `sync-all`

Sync all active tracked channels sequentially using the same `sync-channel` flow.

## Supported Channel References

Version 1 supports:

- raw YouTube channel IDs
- `@handles`
- standard YouTube channel URLs using `/channel/<id>` or `/@handle`
