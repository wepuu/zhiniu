from uuid import UUID

from celery import Celery  # type: ignore[import-untyped]

from zhaoniu_api.config import Settings


class ComparisonDispatcher:
    def __init__(self, settings: Settings) -> None:
        self._celery = Celery("zhaoniu-comparison-client", broker=settings.celery_broker_url)

    def enqueue(self, request_id: UUID) -> None:
        self._celery.send_task("comparisons.build", args=[str(request_id)])
