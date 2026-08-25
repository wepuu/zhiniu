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
