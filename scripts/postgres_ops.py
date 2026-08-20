"""Cross-platform PostgreSQL backup and isolated restore-drill helper."""

import argparse
import hashlib
import json
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

COMPOSE_FILE = Path(
    os.getenv("ZHAONIU_COMPOSE_FILE", "infrastructure/production/docker-compose.yml")
)


def run_compose(arguments: list[str], *, stdout: object | None = None) -> None:
    subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), *arguments],
        check=True,
        stdout=stdout,
    )


def capture_compose(arguments: list[str]) -> str:
    result = subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def backup(output: Path) -> None:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.suffix != ".dump":
        raise ValueError("backup output must use the .dump suffix")
    with output.open("wb") as stream:
        run_compose(
            [
                "exec",
                "-T",
                "postgres",
                "sh",
                "-c",
                'pg_dump --format=custom --no-owner --username="$POSTGRES_USER" "$POSTGRES_DB"',
            ],
            stdout=stream,
        )
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    migration_head = capture_compose(
        [
            "exec",
            "-T",
            "postgres",
            "sh",
            "-c",
            'psql --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" '
            "-Atc 'SELECT version_num FROM alembic_version'",
        ]
    )
    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "artifact": output.name,
        "sha256": digest,
        "format": "postgres-custom",
        "migration_head": migration_head,
    }
    output.with_suffix(".json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def verify(artifact: Path) -> None:
    artifact = artifact.resolve()
    manifest_path = artifact.with_suffix(".json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    if digest != manifest.get("sha256"):
        raise ValueError("backup checksum mismatch")
    subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(COMPOSE_FILE),
            "exec",
            "-T",
            "postgres",
            "pg_restore",
            "--list",
        ],
        input=artifact.read_bytes(),
        stdout=subprocess.DEVNULL,
        check=True,
    )


def restore_drill(artifact: Path, target_database: str) -> None:
    if re.fullmatch(r"zhaoniu_restore_[a-z0-9_]+", target_database) is None:
        raise ValueError("restore target must start with zhaoniu_restore_")
    artifact = artifact.resolve()
    verify(artifact)
    run_compose(
        [
            "exec",
            "-T",
            "postgres",
            "sh",
            "-c",
            f'dropdb --if-exists --username="$POSTGRES_USER" "{target_database}" && '
            f'createdb --username="$POSTGRES_USER" "{target_database}"',
        ]
    )
    process = subprocess.Popen(
        [
            "docker",
            "compose",
            "-f",
            str(COMPOSE_FILE),
            "exec",
            "-T",
            "postgres",
            "sh",
            "-c",
            f'pg_restore --no-owner --username="$POSTGRES_USER" --dbname="{target_database}"',
        ],
        stdin=subprocess.PIPE,
    )
    if process.stdin is None:
        raise RuntimeError("restore process did not expose stdin")
    process.stdin.write(artifact.read_bytes())
    process.stdin.close()
    if process.wait() != 0:
        raise RuntimeError("restore drill failed")
    restored_head = capture_compose(
        [
            "exec",
            "-T",
            "postgres",
            "sh",
            "-c",
            f'psql --username="$POSTGRES_USER" --dbname="{target_database}" '
            "-Atc 'SELECT version_num FROM alembic_version'",
        ]
    )
    print(json.dumps({"target_database": target_database, "migration_head": restored_head}))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    commands = root.add_subparsers(dest="command", required=True)
    backup_command = commands.add_parser("backup")
    backup_command.add_argument("--output", type=Path, required=True)
    verify_command = commands.add_parser("verify")
    verify_command.add_argument("--artifact", type=Path, required=True)
    restore_command = commands.add_parser("restore-drill")
    restore_command.add_argument("--artifact", type=Path, required=True)
    restore_command.add_argument("--target-database", required=True)
    return root


def main() -> None:
    args = parser().parse_args()
    if args.command == "backup":
        backup(args.output)
    elif args.command == "verify":
        verify(args.artifact)
    else:
        restore_drill(args.artifact, args.target_database)


if __name__ == "__main__":
    main()
