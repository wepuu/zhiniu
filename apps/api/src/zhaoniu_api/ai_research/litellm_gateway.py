import json
import re
import time
from functools import lru_cache
from importlib import import_module
from typing import Any

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
    def supports_structured_output(self, model: str) -> bool:
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
    ) -> LLMStructuredResponse:
        started = time.perf_counter()
        try:
            response = await _litellm().acompletion(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": json.dumps(
                            input_data, ensure_ascii=False, separators=(",", ":"), sort_keys=True
                        ),
                    },
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": re.sub(r"[^a-zA-Z0-9_-]", "_", task_type)[:64],
                        "strict": True,
                        "schema": response_schema,
                    },
                },
                timeout=timeout_seconds,
                max_retries=0,
                temperature=0,
            )
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
            provider = provider_name(model)
            return LLMStructuredResponse(
                data=data,
                usage=LLMUsage(
                    task_type=task_type,
                    provider=provider,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    cost_microunits=cost_microunits,
                    status="succeeded",
                ),
                finish_reason=str(getattr(choice, "finish_reason", "stop")),
            )
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise LLMGatewayError("invalid_structured_output", _safe_message(error)) from error


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
