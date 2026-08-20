from uuid import UUID

from celery import Celery  # type: ignore[import-untyped]
from redis import Redis

from zhaoniu_api.config import Settings


class ScreeningDispatcher:
    def __init__(self, settings: Settings) -> None:
        self._celery = Celery("zhaoniu-screening-client", broker=settings.celery_broker_url)
        self._redis_url = settings.redis_url
        self._parse_input_ttl = settings.screen_parser_input_ttl_seconds

    def enqueue(self, execution_id: UUID) -> None:
        self._celery.send_task("screening.execute", args=[str(execution_id)])

    def enqueue_parse(self, run_id: UUID, text: str) -> None:
        key = f"screen-parse-input:{run_id}"
        with Redis.from_url(self._redis_url, decode_responses=True) as client:
            client.setex(key, self._parse_input_ttl, text)
        self._celery.send_task("screening.parse_natural_language", args=[str(run_id)])
