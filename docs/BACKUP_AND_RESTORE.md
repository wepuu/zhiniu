# PostgreSQL backup and restore

Create and verify a custom-format backup:

```text
uv run python scripts/postgres_ops.py backup --output .local/backups/zhaoniu.dump
uv run python scripts/postgres_ops.py verify --artifact .local/backups/zhaoniu.dump
```

Each backup has a JSON manifest containing SHA-256, size, creation time and Alembic head. Restore
drills must target a dedicated database named `zhaoniu_restore_*`; the tool refuses broader names.

```text
uv run python scripts/postgres_ops.py restore-drill --artifact .local/backups/zhaoniu.dump --target-database zhaoniu_restore_drill
```

Run a restore drill before every controlled-Beta release and after migration changes. Retention,
off-host encryption and production credentials belong to the deployment platform, not this repo.

## Phase 23 staging host

The staging host uses `/usr/local/sbin/zhaoniu-backup`. It verifies a PostgreSQL custom-format dump,
encrypts it with an age recipient, writes raw/encrypted SHA-256 values and the Alembic head to a JSON
manifest, and transfers both encrypted artifact and manifest with rsync over SSH. Deployment is
blocked if this off-host backup fails. Plain dumps are removed before the command returns.

The daily systemd timer runs at 18:00 UTC. Local encrypted artifacts are kept for three days; the
separate receiver enforces 14 daily and 8 weekly generations. Recovery uses
`zhaoniu-restore-drill`, which accepts only a dedicated `zhaoniu_restore_*` database name. The age
identity and remote SSH credentials never enter GitHub or the application environment.
