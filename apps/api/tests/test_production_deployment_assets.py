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
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "apt-get update" in dockerfile
    assert "apt-get upgrade -y" in dockerfile
    assert "rm -rf /var/lib/apt/lists/*" in dockerfile
    assert 'where = ["apps/api/src", "apps/worker/src"]' in pyproject

    compose = (PRODUCTION / "docker-compose.yml").read_text(encoding="utf-8")
    assert '"zhaoniu_worker.celery_app:celery_app"' in compose
    assert '"--workdir"' not in compose


def test_production_health_checks_use_the_configured_trusted_host() -> None:
    compose = (PRODUCTION / "docker-compose.yml").read_text(encoding="utf-8")
    deploy = (PRODUCTION / "deploy.sh").read_text(encoding="utf-8")

    assert "os.environ['TRUSTED_HOSTS'].split(',')[0].strip()" in compose
    assert "headers={'Host': host}" in compose
    assert 'trusted_host=$(sed -n' in deploy
    assert '--header "Host: ${trusted_host}"' in deploy
    assert "service_is_stable worker" in deploy
    assert "service_is_stable beat" in deploy
    assert "{{.RestartCount}}" in deploy


def test_celery_beat_uses_a_writable_schedule_path() -> None:
    compose = (PRODUCTION / "docker-compose.yml").read_text(encoding="utf-8")

    assert '"--pidfile",\n        "/tmp/zhaoniu-beat.pid"' in compose
    assert '"--schedule",\n        "/tmp/zhaoniu-celerybeat-schedule"' in compose


def test_web_image_uses_a_hardened_standalone_runtime() -> None:
    dockerfile = (ROOT / "infrastructure" / "docker" / "web.Dockerfile").read_text(
        encoding="utf-8"
    )
    next_config = (ROOT / "apps" / "web" / "next.config.ts").read_text(
        encoding="utf-8"
    )

    assert "apk upgrade --no-cache" in dockerfile
    assert "ARG API_BASE_URL=http://api:8000" in dockerfile
    assert "ENV API_BASE_URL=${API_BASE_URL}" in dockerfile
    assert "/app/apps/web/.next/standalone" in dockerfile
    assert "/app/apps/web/.next/static" in dockerfile
    assert "rm -rf /usr/local/lib/node_modules/npm" in dockerfile
    assert 'CMD ["node", "apps/web/server.js"]' in dockerfile
    assert "COPY --from=build --chown=zhaoniu:zhaoniu /app /app" not in dockerfile
    assert "outputFileTracingIncludes" in next_config
    assert "@swc+helpers@*/node_modules/@swc/helpers/esm/**/*" in next_config


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
    assert "grep -Fq 'http://api:8000' /app/apps/web/server.js" in workflow[verify:deploy]
    assert "/gateway/api/v1/legal/current" in workflow[verify:deploy]
    assert "--network-alias api" in workflow[verify:deploy]
    assert "from zhaoniu_worker.celery_app import celery_app" in workflow[verify:deploy]
    assert "zhaoniu_worker.celery_app:celery_app worker --help" in workflow[verify:deploy]
    assert "zhaoniu_worker.celery_app:celery_app beat --help" in workflow[verify:deploy]
    assert "--publish 127.0.0.1::3000" in workflow[verify:deploy]
    assert (
        'curl --fail --silent --show-error "http://127.0.0.1:${web_port}/"'
        in workflow[verify:deploy]
    )
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
