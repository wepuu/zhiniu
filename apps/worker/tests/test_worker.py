from zhaoniu_worker.celery_app import celery_app, health_check


def test_health_task() -> None:
    assert health_check.run() == {"status": "ok"}


def test_ai_research_task_is_registered() -> None:
    assert "ai_research.generate_stock_health" in celery_app.tasks
