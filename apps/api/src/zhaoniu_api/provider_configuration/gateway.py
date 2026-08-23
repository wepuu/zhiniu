from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from zhaoniu_api.ai_research.litellm_gateway import LiteLLMGateway
from zhaoniu_api.config import Settings
from zhaoniu_api.ports.providers import LLMGatewayError, LLMStructuredResponse
from zhaoniu_api.provider_configuration.models import DeepSeekConfiguration
from zhaoniu_api.provider_configuration.service import ProviderConfigurationService


class ManagedLiteLLMGateway:
    """Resolve credentials at call time without exposing them to application services."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    def supports_structured_output(self, model: str) -> bool:
        return model.startswith("deepseek/")

    async def generate_structured(
        self,
        *,
        model: str,
        task_type: str,
        system_prompt: str,
        input_data: dict[str, object],
        response_schema: dict[str, Any],
        timeout_seconds: float,
        max_output_tokens: int | None = None,
        thinking_enabled: bool = False,
    ) -> LLMStructuredResponse:
        runtime = await ProviderConfigurationService(self._session, self._settings).runtime(
            "deepseek"
        )
        configuration = DeepSeekConfiguration.model_validate(runtime.configuration)
        api_key = runtime.credentials.get("api_key")
        if not configuration.enabled or not api_key:
            raise LLMGatewayError("provider_disabled", "managed DeepSeek provider is disabled")
        gateway = LiteLLMGateway(
            "json_object",
            redis_url=self._settings.redis_url,
            max_concurrency=configuration.max_concurrency,
            daily_call_limit=configuration.daily_call_limit,
        )
        return await gateway.generate_structured(
            model=model,
            task_type=task_type,
            system_prompt=system_prompt,
            input_data=input_data,
            response_schema=response_schema,
            timeout_seconds=timeout_seconds,
            max_output_tokens=max_output_tokens,
            thinking_enabled=thinking_enabled,
            api_key=api_key,
        )
