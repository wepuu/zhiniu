import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PRODUCTION = ROOT / "infrastructure" / "production"
STAGING_WORKFLOW = ROOT / ".github" / "workflows" / "deploy-staging.yml"


def test_production_compose_uses_immutable_images_and_loopback_ports() -> None:
    compose = (PRODUCTION / "docker-compose.yml").read_text(encoding="utf-8")

    assert "build:" not in compose
    assert "proxy:" not in compose
    assert "${API_IMAGE:?" in compose
    assert "${WEB_IMAGE:?" in compose
    assert '"127.0.0.1:${API_HOST_PORT:-8000}:8000"' in compose
    assert '"127.0.0.1:${WEB_HOST_PORT:-3000}:3000"' in compose
    assert "--concurrency" in compose
    assert 'max-size: "10m"' in compose


def test_api_image_applies_available_base_security_updates() -> None:
    dockerfile = (ROOT / "infrastructure" / "docker" / "api.Dockerfile").read_text(
        encoding="utf-8"
    )

    assert "apt-get update" in dockerfile
    assert "apt-get upgrade -y" in dockerfile
    assert "rm -rf /var/lib/apt/lists/*" in dockerfile


def test_deploy_is_fail_closed_around_backup_and_health() -> None:
    deploy = (PRODUCTION / "deploy.sh").read_text(encoding="utf-8")

    backup = deploy.index('"${backup_script}" --remote-required')
    migration = deploy.index("compose run --rm migrate")
    service_update = deploy.index("compose up -d --remove-orphans api worker beat web")
    health = deploy.index("if ! wait_for_health")
    assert backup < migration < service_update < health
    assert "invalid API image" in deploy
    assert "requested commit is no longer main" in deploy
    assert "image revision does not match commit" in deploy
    assert "alembic downgrade" not in deploy


def test_staging_images_publish_and_verify_before_optional_deploy() -> None:
    workflow = STAGING_WORKFLOW.read_text(encoding="utf-8")

    build = workflow.index("  build_scan_publish:")
    verify = workflow.index("  verify_images:")
    deploy = workflow.index("  deploy:")
    assert build < verify < deploy
    assert "if: github.event.workflow_run.conclusion == 'success'" in workflow[build:verify]
    assert "STAGING_DEPLOY_ENABLED" not in workflow[build:verify]
    assert "Verify images are private before authentication" in workflow[verify:deploy]
    assert "Pull immutable image digests" in workflow[verify:deploy]
    assert "Smoke-test image runtimes" in workflow[verify:deploy]
    assert "vars.STAGING_DEPLOY_ENABLED == 'true'" in workflow[deploy:]


def test_nginx_keeps_dependencies_private_and_marks_staging_noindex() -> None:
    nginx = (PRODUCTION / "nginx-app.zhiniu.cc.conf").read_text(encoding="utf-8")

    assert "proxy_pass http://127.0.0.1:8000" in nginx
    assert "proxy_pass http://127.0.0.1:3000" in nginx
    assert 'X-Robots-Tag "noindex, nofollow"' in nginx
    assert "allow REPLACE_WITH_ADMIN_IP" in nginx
    assert "deny all" in nginx


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is not installed")
@pytest.mark.parametrize(
    "script",
    ["deploy.sh", "backup.sh", "restore-drill.sh", "install-host-assets.sh"],
)
def test_production_shell_syntax(script: str) -> None:
    subprocess.run(["bash", "-n", str(PRODUCTION / script)], check=True)
