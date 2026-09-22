#!/usr/bin/env python3
"""Collect immutable host-side evidence for the Phase 25G Beta gate.

The application database owns SLO and trading-calendar observations.  This
collector deliberately covers only facts that the application cannot observe:
container OOM/restarts, broker depth, worker health, host resources, backup
timer state and loopback health.  It never reads or emits secret values.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SERVICES = ("postgres", "redis", "api", "worker", "beat", "web")
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
COMMIT_HEX = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
IMAGE_DIGEST = re.compile(r"^sha256:([0-9a-f]{64})$")


@dataclass(frozen=True, slots=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str = ""


Runner = Callable[[Sequence[str]], CommandResult]


def run_command(command: Sequence[str]) -> CommandResult:
    completed = subprocess.run(  # noqa: S603 - commands are fixed argument arrays
        list(command),
        capture_output=True,
        check=False,
        text=True,
        timeout=20,
    )
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def _read_release(path: Path) -> dict[str, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    required = ("commit_sha", "api_image", "web_image", "migration_head", "environment")
    if not isinstance(raw, dict) or any(not isinstance(raw.get(key), str) for key in required):
        raise ValueError("release_metadata_invalid")
    release = {key: raw[key].strip() for key in required}
    if not COMMIT_HEX.fullmatch(release["commit_sha"]):
        raise ValueError("release_commit_invalid")
    if release["environment"] not in {"staging", "production"}:
        raise ValueError("release_environment_invalid")
    for key, repository in (
        ("api_image", "ghcr.io/wepuu/zhiniu-api@"),
        ("web_image", "ghcr.io/wepuu/zhiniu-web@"),
    ):
        if not release[key].startswith(repository) or not IMAGE_DIGEST.fullmatch(
            release[key].removeprefix(repository)
        ):
            raise ValueError(f"release_{key}_invalid")
    return release


def _container_fact(service: str, project_name: str, runner: Runner) -> dict[str, Any]:
    name = f"{project_name}-{service}-1"
    result = runner(("docker", "inspect", name))
    if result.returncode != 0:
        return {
            "service": service,
            "present": False,
            "running": False,
            "health": "missing",
            "restart_count": None,
            "oom_killed": None,
        }
    payload = json.loads(result.stdout)
    if not isinstance(payload, list) or len(payload) != 1:
        raise ValueError(f"container_inspect_invalid:{service}")
    state = payload[0].get("State", {})
    health = state.get("Health")
    return {
        "service": service,
        "present": True,
        "running": bool(state.get("Running")),
        "health": health.get("Status", "not_configured")
        if isinstance(health, dict)
        else "not_configured",
        "restart_count": int(payload[0].get("RestartCount", 0)),
        "oom_killed": bool(state.get("OOMKilled")),
    }


def evaluate_host_facts(facts: dict[str, Any]) -> list[str]:
    """Return stable blocking reason codes for collected host facts."""

    blocking: list[str] = []
    for item in facts["containers"]:
        service = item["service"]
        if not item["present"]:
            blocking.append(f"container_{service}_missing")
            continue
        if not item["running"]:
            blocking.append(f"container_{service}_not_running")
        if item["oom_killed"]:
            blocking.append(f"container_{service}_oom_killed")
        if item["restart_count"]:
            blocking.append(f"container_{service}_restarted")
        if service in {"postgres", "redis", "api", "web"} and item["health"] != "healthy":
            blocking.append(f"container_{service}_unhealthy")

    if not facts["worker_healthy"]:
        blocking.append("worker_unavailable")
    if not facts["broker_queue_available"]:
        blocking.append("broker_queue_unavailable")
    elif facts["broker_queue_depth"] > facts["broker_queue_limit"]:
        blocking.append("broker_queue_depth_exceeded")
    if not facts["kernel_oom_check_available"]:
        blocking.append("kernel_oom_check_unavailable")
    elif facts["kernel_oom_event_count"]:
        blocking.append("kernel_oom_detected")
    if not facts["backup_timer_enabled"]:
        blocking.append("backup_timer_disabled")
    if not facts["backup_timer_active"]:
        blocking.append("backup_timer_inactive")
    if facts["latest_backup_age_seconds"] is None:
        blocking.append("backup_missing")
    elif facts["latest_backup_age_seconds"] > facts["backup_max_age_seconds"]:
        blocking.append("backup_stale")
    if facts["docker_free_bytes"] < facts["docker_min_free_bytes"]:
        blocking.append("docker_disk_headroom_low")
    if facts["memory_available_bytes"] < facts["memory_min_available_bytes"]:
        blocking.append("memory_headroom_low")
    if not facts["api_ready"]:
        blocking.append("api_not_ready")
    if not facts["web_ready"]:
        blocking.append("web_not_ready")
    return sorted(set(blocking))


def _memory_available_bytes(meminfo_path: Path) -> int:
    for line in meminfo_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) * 1024
    raise ValueError("mem_available_missing")


def _latest_backup_age_seconds(backup_dir: Path, now: datetime) -> int | None:
    manifests = list(backup_dir.glob("zhaoniu-*.json"))
    if not manifests:
        return None
    latest = max(manifests, key=lambda item: item.stat().st_mtime)
    return max(0, int(now.timestamp() - latest.stat().st_mtime))


def collect_host_facts(args: argparse.Namespace, *, runner: Runner = run_command) -> dict[str, Any]:
    now = datetime.now(UTC)
    release = _read_release(args.release_file)
    containers = [_container_fact(service, args.project_name, runner) for service in SERVICES]

    worker = runner(
        (
            "docker",
            "exec",
            f"{args.project_name}-worker-1",
            "celery",
            "-A",
            "zhaoniu_worker.celery_app:celery_app",
            "inspect",
            "ping",
            "--timeout",
            "10",
        )
    )
    queue = runner(
        (
            "docker",
            "exec",
            f"{args.project_name}-redis-1",
            "redis-cli",
            "LLEN",
            "celery",
        )
    )
    if queue.returncode != 0 or not queue.stdout.strip().isdigit():
        queue_depth = 0
        queue_available = False
    else:
        queue_depth = int(queue.stdout.strip())
        queue_available = True

    kernel_oom = runner(
        (
            "journalctl",
            "--kernel",
            "--since",
            "now" if args.window_hours == 0 else f"{args.window_hours} hours ago",
            "--no-pager",
            "--grep",
            "Out of memory|Killed process|oom-kill",
        )
    )
    kernel_oom_available = kernel_oom.returncode in {0, 1}
    kernel_oom_event_count = (
        len([line for line in kernel_oom.stdout.splitlines() if line.strip()])
        if kernel_oom.returncode == 0
        else 0
    )

    timer_enabled = runner(("systemctl", "is-enabled", args.backup_timer))
    timer_active = runner(("systemctl", "is-active", args.backup_timer))
    api = runner(
        (
            "curl",
            "--fail",
            "--silent",
            "--show-error",
            "--max-time",
            "5",
            "--header",
            f"Host: {args.public_host}",
            "http://127.0.0.1:8000/readyz",
        )
    )
    web = runner(
        (
            "curl",
            "--fail",
            "--silent",
            "--show-error",
            "--max-time",
            "5",
            "http://127.0.0.1:3000/",
        )
    )

    return {
        "release": release,
        "configuration_fingerprint": args.configuration_fingerprint,
        "collected_at": now.isoformat(),
        "window_hours": args.window_hours,
        "hostname": socket.gethostname(),
        "containers": containers,
        "worker_healthy": worker.returncode == 0 and "pong" in worker.stdout.lower(),
        "broker_queue_depth": queue_depth,
        "broker_queue_limit": args.broker_queue_limit,
        "broker_queue_available": queue_available,
        "kernel_oom_check_available": kernel_oom_available,
        "kernel_oom_event_count": kernel_oom_event_count,
        "backup_timer_enabled": timer_enabled.returncode == 0,
        "backup_timer_active": timer_active.returncode == 0,
        "latest_backup_age_seconds": _latest_backup_age_seconds(args.backup_dir, now),
        "backup_max_age_seconds": args.backup_max_age_hours * 3600,
        "docker_free_bytes": shutil.disk_usage(args.docker_root).free,
        "docker_min_free_bytes": args.docker_min_free_gib * 1024**3,
        "memory_available_bytes": _memory_available_bytes(args.meminfo_file),
        "memory_min_available_bytes": args.memory_min_available_mib * 1024**2,
        "api_ready": api.returncode == 0,
        "web_ready": web.returncode == 0,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect immutable Phase 25G host reliability evidence."
    )
    parser.add_argument(
        "--configuration-fingerprint",
        required=True,
        help="Exact SHA-256 fingerprint used by the release candidate.",
    )
    parser.add_argument(
        "--release-file",
        type=Path,
        default=Path("/opt/zhiniu/releases/current/current-release.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/opt/zhiniu/releases/reliability-evidence"),
    )
    parser.add_argument("--project-name", default="zhaoniu-staging")
    parser.add_argument("--public-host", default="app.zhiniu.cc")
    parser.add_argument("--backup-timer", default="zhaoniu-backup.timer")
    parser.add_argument("--backup-dir", type=Path, default=Path("/var/backups/zhiniu"))
    parser.add_argument("--docker-root", type=Path, default=Path("/var/lib/docker"))
    parser.add_argument("--meminfo-file", type=Path, default=Path("/proc/meminfo"))
    parser.add_argument(
        "--window-hours",
        type=int,
        choices=(0, 24, 48),
        default=48,
        help="Use 0 only for an immediate post-deployment snapshot.",
    )
    parser.add_argument("--broker-queue-limit", type=int, default=10)
    parser.add_argument("--backup-max-age-hours", type=int, default=26)
    parser.add_argument("--docker-min-free-gib", type=int, default=15)
    parser.add_argument("--memory-min-available-mib", type=int, default=512)
    return parser


def main() -> int:
    args = _parser().parse_args()
    args.configuration_fingerprint = args.configuration_fingerprint.strip().lower()
    if not HEX_64.fullmatch(args.configuration_fingerprint):
        raise SystemExit("configuration fingerprint must be a 64-character SHA-256 hex value")
    if any(
        value < 0
        for value in (
            args.broker_queue_limit,
            args.backup_max_age_hours,
            args.docker_min_free_gib,
            args.memory_min_available_mib,
        )
    ):
        raise SystemExit("numeric thresholds must be nonnegative")

    facts = collect_host_facts(args)
    blocking_reasons = evaluate_host_facts(facts)
    evidence = {
        "schema_version": "phase25g-host-evidence-v1",
        "status": "failed" if blocking_reasons else "passed",
        **facts,
        "blocking_reasons": blocking_reasons,
    }
    canonical = json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    evidence["result_fingerprint"] = hashlib.sha256(canonical.encode()).hexdigest()

    args.output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    args.output_dir.chmod(0o700)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output = args.output_dir / (
        f"phase25g-host-{timestamp}-{facts['release']['commit_sha'][:12]}.json"
    )
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(evidence, stream, ensure_ascii=False, indent=2)
        stream.write("\n")

    print(f"status={evidence['status']}")
    print(f"evidence_path={output}")
    print(f"result_fingerprint={evidence['result_fingerprint']}")
    for reason in blocking_reasons:
        print(f"blocking_reason={reason}")
    return 1 if blocking_reasons else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"phase25g_evidence_error={type(error).__name__}", file=sys.stderr)
        raise SystemExit(2) from error
