import asyncio
import json
import re
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from functools import lru_cache
from importlib import import_module
from math import ceil
from typing import Any
from uuid import uuid4

from redis.asyncio import Redis

from zhaoniu_api.ports.providers import (
    LLMGatewayError,
    LLMStructuredResponse,
    LLMUsage,
)


def provider_name(model: str) -> str:
    prefix = model.split("/", 1)[0].lower()
    return {"dashscope": "Qwen", "gemini": "Gemini", "openai": "OpenAI"}.get(
        prefix, "DeepSeek" if prefix == "deepseek" else prefix
    )


@lru_cache
def _litellm() -> Any:
    return import_module("litellm")


class LiteLLMGateway:
    def __init__(
        self,
        mode: str = "json_schema",
        *,
        redis_url: str | None = None,
        max_concurrency: int = 2,
        daily_call_limit: int = 100,
    ) -> None:
        self._mode = mode
        self._redis_url = redis_url
        self._max_concurrency = max_concurrency
        self._daily_call_limit = daily_call_limit

    def supports_structured_output(self, model: str) -> bool:
        if self._mode == "json_object":
            return True
        try:
            return bool(_litellm().supports_response_schema(model=model))
        except Exception:
            return False

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
        started = time.perf_counter()
        try:
            response_format: dict[str, Any]
            if self._mode == "json_object":
                response_format = {"type": "json_object"}
                system_prompt = (
                    f"{system_prompt}\nReturn exactly one JSON object matching this schema: "
                    f"{json.dumps(response_schema, ensure_ascii=False, separators=(',', ':'))}"
                )
            else:
                response_format = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": re.sub(r"[^a-zA-Z0-9_-]", "_", task_type)[:64],
                        "strict": True,
                        "schema": response_schema,
                    },
                }
            async with self._provider_budget(model, timeout_seconds):
                extra_body = None
                if model.startswith("deepseek/"):
                    extra_body = {
                        "thinking": {"type": "enabled" if thinking_enabled else "disabled"}
                    }
                response = await _litellm().acompletion(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": json.dumps(
                                input_data,
                                ensure_ascii=False,
                                separators=(",", ":"),
                                sort_keys=True,
                            ),
                        },
                    ],
                    response_format=response_format,
                    timeout=timeout_seconds,
                    max_retries=0,
                    temperature=0,
                    max_tokens=max_output_tokens,
                    extra_body=extra_body,
                )
        except LLMGatewayError:
            raise
        except Exception as error:
            raise LLMGatewayError(_error_code(error), _safe_message(error)) from error

        try:
            choice = response.choices[0]
            content = choice.message.content
            if not isinstance(content, str):
                raise TypeError("provider returned empty structured content")
            data = json.loads(content)
            if not isinstance(data, dict):
                raise TypeError("provider returned a non-object JSON value")
            raw_usage = getattr(response, "usage", None)
            input_tokens = int(getattr(raw_usage, "prompt_tokens", 0) or 0)
            output_tokens = int(getattr(raw_usage, "completion_tokens", 0) or 0)
            hidden = getattr(response, "_hidden_params", {}) or {}
            raw_cost = hidden.get("response_cost") if isinstance(hidden, dict) else None
            cost_microunits = (
                max(0, round(float(raw_cost) * 1_000_000)) if raw_cost is not None else None
            )
            actual_model = str(getattr(response, "model", model) or model)
            provider = provider_name(model)
            return LLMStructuredResponse(
                data=data,
                usage=LLMUsage(
                    task_type=task_type,
                    provider=provider,
                    model=actual_model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    cost_microunits=cost_microunits,
                    status="succeeded",
                    requested_model=model,
                    capability_mode=self._mode,
                ),
                finish_reason=str(getattr(choice, "finish_reason", "stop")),
            )
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise LLMGatewayError("invalid_structured_output", _safe_message(error)) from error

    @asynccontextmanager
    async def _provider_budget(self, model: str, timeout_seconds: float) -> AsyncIterator[None]:
        if not self._redis_url:
            yield
            return
        provider = model.split("/", 1)[0].lower()
        client = Redis.from_url(self._redis_url, decode_responses=True)
        lease_key: str | None = None
        token = str(uuid4())
        try:
            day_key = f"zhaoniu:llm:daily:{provider}:{datetime.now(UTC):%Y%m%d}"
            count = await client.incr(day_key)
            if count == 1:
                await client.expire(day_key, 172800)
            if count > self._daily_call_limit:
                raise LLMGatewayError(
                    "provider_daily_limit", "provider daily call budget exhausted"
                )

            lease_seconds = max(10, ceil(timeout_seconds) + 5)
            deadline = time.monotonic() + min(timeout_seconds, 10)
            while time.monotonic() < deadline and lease_key is None:
                for slot in range(self._max_concurrency):
                    candidate = f"zhaoniu:llm:slot:{provider}:{slot}"
                    if await client.set(candidate, token, ex=lease_seconds, nx=True):
                        lease_key = candidate
                        break
                if lease_key is None:
                    await asyncio.sleep(0.1)
            if lease_key is None:
                raise LLMGatewayError(
                    "provider_concurrency_limit",
                    "provider concurrency capacity unavailable",
                )
            yield
        finally:
            if lease_key:
                await client.eval(
                    "if redis.call('get', KEYS[1]) == ARGV[1] then "
                    "return redis.call('del', KEYS[1]) else return 0 end",
                    1,
                    lease_key,
                    token,
                )
            await client.aclose()


def _safe_message(error: Exception) -> str:
    message = str(error)[:300]
    message = re.sub(
        r"(?i)(api[_ -]?key|authorization|bearer)(\s*[:=]?\s*)[^\s,;]+",
        r"\1\2[REDACTED]",
        message,
    )
    message = re.sub(r"\bsk-[A-Za-z0-9_-]{8,}\b", "[REDACTED]", message)
    return f"{type(error).__name__}: {message}"


def _error_code(error: Exception) -> str:
    name = type(error).__name__.lower()
    status_code = getattr(error, "status_code", None)
    message = str(error).lower()
    if status_code == 402 or "insufficient balance" in message:
        return "provider_balance"
    if "authentication" in name or "permission" in name:
        return "provider_auth"
    if "ratelimit" in name or "quota" in name:
        return "provider_rate_limit"
    if "timeout" in name:
        return "provider_timeout"
    if "connection" in name:
        return "provider_connection"
    if "unsupported" in name or "notfound" in name:
        return "provider_model_unavailable"
    return "provider_error"
