import os

from zhaoniu_worker.celery_app import celery_app, health_check


def test_health_task() -> None:
    assert health_check.run() == {"status": "ok"}


def test_ai_research_task_is_registered() -> None:
    assert "ai_research.generate_stock_health" in celery_app.tasks


def test_worker_uses_loop_safe_database_connections() -> None:
    assert os.environ["ZHAONIU_DISABLE_DB_POOL"] == "1"
    assert "screening.parse_natural_language" in celery_app.tasks


def test_coverage_backfill_is_registered_without_a_schedule() -> None:
    assert "coverage.run_backfill" in celery_app.tasks
    assert not celery_app.conf.beat_schedule
