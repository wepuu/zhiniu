from zhaoniu_worker.celery_app import health_check


def test_health_task() -> None:
    assert health_check.run() == {"status": "ok"}
