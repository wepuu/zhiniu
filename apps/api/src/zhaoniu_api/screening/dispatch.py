from uuid import UUID

from celery import Celery  # type: ignore[import-untyped]

from zhaoniu_api.config import Settings


class ScreeningDispatcher:
    def __init__(self, settings: Settings) -> None:
        self._celery = Celery("zhaoniu-screening-client", broker=settings.celery_broker_url)

    def enqueue(self, execution_id: UUID) -> None:
        self._celery.send_task("screening.execute", args=[str(execution_id)])
