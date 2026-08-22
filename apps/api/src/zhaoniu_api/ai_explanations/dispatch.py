from celery import Celery  # type: ignore[import-untyped]

from zhaoniu_api.config import Settings


class AIExplanationDispatcher:
    def __init__(self, settings: Settings) -> None:
        self._celery = Celery("zhaoniu-ai-explanation-client", broker=settings.celery_broker_url)

    def enqueue(self, request_id: str) -> None:
        self._celery.send_task("ai_research.generate_explanation", args=[request_id])
