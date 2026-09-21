from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


def _load_module() -> ModuleType:
    path = (
        Path(__file__).resolve().parents[3]
        / "infrastructure"
        / "production"
        / "phase25g-host-evidence.py"
    )
    spec = importlib.util.spec_from_file_location("phase25g_host_evidence", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


evidence = _load_module()


def test_phase25g_accepts_honest_post_deployment_snapshot_window() -> None:
    args = evidence._parser().parse_args(
        ["--configuration-fingerprint", "d" * 64, "--window-hours", "0"]
    )
    assert args.window_hours == 0


def _healthy_facts() -> dict[str, object]:
    return {
        "containers": [
            {
                "service": service,
                "present": True,
                "running": True,
                "health": "healthy"
                if service in {"postgres", "redis", "api", "web"}
                else "not_configured",
                "restart_count": 0,
                "oom_killed": False,
            }
            for service in evidence.SERVICES
        ],
        "worker_healthy": True,
        "broker_queue_depth": 0,
        "broker_queue_limit": 10,
        "broker_queue_available": True,
        "kernel_oom_check_available": True,
        "kernel_oom_event_count": 0,
        "backup_timer_enabled": True,
        "backup_timer_active": True,
        "latest_backup_age_seconds": 60,
        "backup_max_age_seconds": 3600,
        "docker_free_bytes": 20 * 1024**3,
        "docker_min_free_bytes": 15 * 1024**3,
        "memory_available_bytes": 1024 * 1024**2,
        "memory_min_available_bytes": 512 * 1024**2,
        "api_ready": True,
        "web_ready": True,
    }


def test_phase25g_host_evidence_passes_only_with_healthy_host_facts() -> None:
    assert evidence.evaluate_host_facts(_healthy_facts()) == []


def test_phase25g_host_evidence_returns_bounded_blocking_reasons() -> None:
    facts = _healthy_facts()
    containers = facts["containers"]
    assert isinstance(containers, list)
    containers[2]["oom_killed"] = True
    containers[4]["restart_count"] = 2
    facts["worker_healthy"] = False
    facts["broker_queue_depth"] = 11
    facts["kernel_oom_event_count"] = 1
    facts["latest_backup_age_seconds"] = None
    facts["api_ready"] = False

    assert evidence.evaluate_host_facts(facts) == [
        "api_not_ready",
        "backup_missing",
        "broker_queue_depth_exceeded",
        "container_api_oom_killed",
        "container_beat_restarted",
        "kernel_oom_detected",
        "worker_unavailable",
    ]


def test_phase25g_release_metadata_requires_exact_immutable_images(tmp_path: Path) -> None:
    release_file = tmp_path / "current-release.json"
    release_file.write_text(
        json.dumps(
            {
                "commit_sha": "a" * 40,
                "api_image": "ghcr.io/wepuu/zhiniu-api@sha256:" + "b" * 64,
                "web_image": "ghcr.io/wepuu/zhiniu-web@sha256:" + "c" * 64,
                "migration_head": "20260914_0030",
                "environment": "staging",
            }
        ),
        encoding="utf-8",
    )

    release = evidence._read_release(release_file)
    assert release["commit_sha"] == "a" * 40

    release_file.write_text(
        release_file.read_text(encoding="utf-8").replace(
            "ghcr.io/wepuu/zhiniu-api@sha256:" + "b" * 64,
            "ghcr.io/wepuu/zhiniu-api:latest",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="release_api_image_invalid"):
        evidence._read_release(release_file)


def test_phase25g_collector_reads_only_bounded_operational_facts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release_file = tmp_path / "current-release.json"
    release_file.write_text(
        json.dumps(
            {
                "commit_sha": "a" * 40,
                "api_image": "ghcr.io/wepuu/zhiniu-api@sha256:" + "b" * 64,
                "web_image": "ghcr.io/wepuu/zhiniu-web@sha256:" + "c" * 64,
                "migration_head": "20260914_0030",
                "environment": "staging",
            }
        ),
        encoding="utf-8",
    )
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    (backup_dir / "zhaoniu-20260919T000000Z.json").write_text("{}", encoding="utf-8")
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemAvailable:       1048576 kB\n", encoding="utf-8")

    def runner(command: tuple[str, ...]) -> object:
        if command[:2] == ("docker", "inspect"):
            service = command[2].removeprefix("zhaoniu-staging-").removesuffix("-1")
            health = (
                {"Status": "healthy"}
                if service in {"postgres", "redis", "api", "web"}
                else None
            )
            return evidence.CommandResult(
                0,
                json.dumps(
                    [
                        {
                            "State": {
                                "Running": True,
                                "OOMKilled": False,
                                "Health": health,
                            },
                            "RestartCount": 0,
                        }
                    ]
                ),
            )
        if command[0] == "docker" and "redis-cli" in command:
            return evidence.CommandResult(0, "0\n")
        if command[0] == "docker" and "celery" in command:
            return evidence.CommandResult(0, "pong\n")
        if command[0] == "journalctl":
            return evidence.CommandResult(1, "")
        return evidence.CommandResult(0, "healthy\n")

    monkeypatch.setattr(
        evidence.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(free=20 * 1024**3),
    )
    args = SimpleNamespace(
        release_file=release_file,
        project_name="zhaoniu-staging",
        configuration_fingerprint="d" * 64,
        window_hours=48,
        broker_queue_limit=10,
        backup_timer="zhaoniu-backup.timer",
        public_host="app.zhiniu.cc",
        backup_dir=backup_dir,
        backup_max_age_hours=26,
        docker_root=tmp_path,
        docker_min_free_gib=15,
        meminfo_file=meminfo,
        memory_min_available_mib=512,
    )

    facts = evidence.collect_host_facts(args, runner=runner)

    assert facts["release"]["commit_sha"] == "a" * 40
    assert facts["broker_queue_depth"] == 0
    assert facts["worker_healthy"] is True
    assert evidence.evaluate_host_facts(facts) == []
