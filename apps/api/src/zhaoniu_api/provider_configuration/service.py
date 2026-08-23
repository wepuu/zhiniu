from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import Literal, cast
from uuid import UUID, uuid4

import httpx
from pydantic import SecretStr
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from zhaoniu_api.ai_research.litellm_gateway import LiteLLMGateway
from zhaoniu_api.config import Settings
from zhaoniu_api.db import (
    ProviderConfigurationRecord,
    ProviderConfigurationRevisionRecord,
    ProviderCredentialRecord,
    ProviderDiagnosticRunRecord,
    TransactionalEmailProviderEventRecord,
    User,
)
from zhaoniu_api.ports.providers import LLMGatewayError
from zhaoniu_api.provider_configuration.crypto import CredentialVault, CredentialVaultError
from zhaoniu_api.provider_configuration.models import (
    ALLOWED_DEEPSEEK_MODELS,
    DeepSeekConfiguration,
    DeepSeekDraftUpdate,
    ProviderConfigurationListResponse,
    ProviderConfigurationView,
    ProviderDraftDiagnoseResponse,
    ProviderMutationResponse,
    ProviderName,
    ProviderRevisionView,
    ResendConfiguration,
    ResendDraftUpdate,
)


class ProviderConfigurationError(ValueError):
    pass


class ProviderConfigurationConflict(ProviderConfigurationError):
    pass


@dataclass(frozen=True, slots=True)
class ProviderRuntimeConfiguration:
    provider: ProviderName
    source: str
    revision: int | None
    configuration: dict[str, object]
    credentials: dict[str, str]


def _hash_configuration(value: dict[str, object]) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def _diagnostic_reason_code(error: ProviderConfigurationError | LLMGatewayError) -> str:
    return (error.code if isinstance(error, LLMGatewayError) else str(error))[:96]


class ProviderConfigurationService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._vault = CredentialVault(
            settings.provider_credential_keys,
            settings.provider_credential_active_key_id,
        )

    async def list_configurations(self) -> ProviderConfigurationListResponse:
        return ProviderConfigurationListResponse(
            items=[await self.get_configuration("deepseek"), await self.get_configuration("resend")]
        )

    async def get_configuration(self, provider: ProviderName) -> ProviderConfigurationView:
        row = await self._configuration(provider)
        active = (
            await self._revision(row, row.active_revision) if row and row.active_revision else None
        )
        draft = (
            await self._revision(row, row.draft_revision) if row and row.draft_revision else None
        )
        active_credential = await self._credential(row, "active") if row else None
        candidate = await self._credential(row, "candidate") if row else None
        diagnostic = None
        if draft is not None:
            diagnostic = await self._session.scalar(
                select(ProviderDiagnosticRunRecord)
                .where(
                    ProviderDiagnosticRunRecord.provider == provider,
                    ProviderDiagnosticRunRecord.target == "draft",
                    ProviderDiagnosticRunRecord.configuration_revision_id == draft.id,
                    ProviderDiagnosticRunRecord.credential_generation
                    == draft.credential_generation,
                )
                .order_by(ProviderDiagnosticRunRecord.checked_at.desc())
            )
        environment_credentials = self._environment_credentials(provider)
        source = "database" if active is not None else "environment"
        if self._settings.managed_providers_hard_disabled:
            source = "disabled"
        credential_state = (
            "encrypted"
            if active_credential or candidate
            else "environment"
            if environment_credentials
            else "missing"
        )
        webhook_verified_at = None
        if provider == "resend":
            conditions = [TransactionalEmailProviderEventRecord.provider == "resend"]
            if active is not None and active.published_at is not None:
                conditions.append(
                    TransactionalEmailProviderEventRecord.received_at >= active.published_at
                )
            webhook_verified_at = await self._session.scalar(
                select(func.max(TransactionalEmailProviderEventRecord.received_at)).where(
                    *conditions
                )
            )
        latest_credential = candidate or active_credential
        return ProviderConfigurationView(
            provider=provider,
            environment=self._settings.app_env,
            source=cast(Literal["environment", "database", "disabled"], source),
            row_version=row.row_version if row else 0,
            credential_state=cast(Literal["missing", "environment", "encrypted"], credential_state),
            credential_rotated_at=latest_credential.created_at if latest_credential else None,
            active=self._revision_view(active),
            draft=self._revision_view(draft),
            diagnostic_status=(
                "healthy"
                if diagnostic and diagnostic.status == "healthy"
                else "unavailable"
                if diagnostic
                else "not_run"
            ),
            diagnostic_checked_at=diagnostic.checked_at if diagnostic else None,
            webhook_verified_at=webhook_verified_at,
        )

    async def save_draft(
        self,
        provider: ProviderName,
        payload: DeepSeekDraftUpdate | ResendDraftUpdate,
        actor: UUID,
    ) -> ProviderMutationResponse:
        row = await self._configuration_for_update(provider, create=True)
        assert row is not None
        if row.row_version != payload.expected_row_version:
            raise ProviderConfigurationConflict("provider_configuration_version_conflict")
        configuration = payload.configuration.model_dump(mode="json")
        secrets = self._secret_updates(provider, payload)
        candidate = await self._credential(row, "candidate")
        active = await self._credential(row, "active")
        current_secrets = await self._decrypt_credential(provider, candidate or active)
        if not current_secrets and row.active_revision is None:
            current_secrets = self._environment_credentials(provider)
        current_secrets.update(secrets)
        latest_credential = candidate or active
        generation = latest_credential.generation if latest_credential else None
        if secrets:
            if not self._vault.available:
                raise ProviderConfigurationError("provider_credential_vault_unavailable")
            generation = (
                max(candidate.generation if candidate else 0, active.generation if active else 0)
                + 1
            )
            await self._replace_candidate(row, provider, current_secrets, generation, actor)
        previous_draft = (
            await self._revision(row, row.draft_revision) if row.draft_revision else None
        )
        if previous_draft is not None:
            previous_draft.status = "retired"
        next_revision = (
            int(
                await self._session.scalar(
                    select(
                        func.coalesce(func.max(ProviderConfigurationRevisionRecord.revision), 0)
                    ).where(ProviderConfigurationRevisionRecord.configuration_id == row.id)
                )
                or 0
            )
            + 1
        )
        revision = ProviderConfigurationRevisionRecord(
            id=uuid4(),
            configuration_id=row.id,
            revision=next_revision,
            status="draft",
            configuration_json=configuration,
            configuration_hash=_hash_configuration(configuration),
            credential_generation=generation,
            created_by_user_id=actor,
        )
        self._session.add(revision)
        row.draft_revision = next_revision
        row.row_version += 1
        await self._session.commit()
        return ProviderMutationResponse(
            status="draft_saved", configuration=await self.get_configuration(provider)
        )

    async def import_environment(
        self, provider: ProviderName, expected_row_version: int, actor: UUID
    ) -> ProviderMutationResponse:
        configuration = self._environment_configuration(provider)
        credentials = self._environment_credentials(provider)
        if not credentials:
            raise ProviderConfigurationError("provider_environment_credentials_missing")
        if provider == "deepseek":
            payload: DeepSeekDraftUpdate | ResendDraftUpdate = DeepSeekDraftUpdate(
                expected_row_version=expected_row_version,
                configuration=DeepSeekConfiguration.model_validate(configuration),
                api_key=SecretStr(credentials["api_key"]),
            )
        else:
            if not credentials.get("api_key") or not credentials.get("webhook_secret"):
                raise ProviderConfigurationError("provider_environment_credentials_incomplete")
            payload = ResendDraftUpdate(
                expected_row_version=expected_row_version,
                configuration=ResendConfiguration.model_validate(configuration),
                api_key=SecretStr(credentials["api_key"]),
                webhook_secret=SecretStr(credentials["webhook_secret"]),
            )
        return await self.save_draft(provider, payload, actor)

    async def discard_draft(
        self, provider: ProviderName, expected_row_version: int
    ) -> ProviderMutationResponse:
        row = await self._configuration_for_update(provider)
        if row is None or row.row_version != expected_row_version:
            raise ProviderConfigurationConflict("provider_configuration_version_conflict")
        draft = await self._revision(row, row.draft_revision) if row.draft_revision else None
        if draft is not None:
            draft.status = "retired"
        await self._session.execute(
            delete(ProviderCredentialRecord).where(
                ProviderCredentialRecord.configuration_id == row.id,
                ProviderCredentialRecord.slot == "candidate",
            )
        )
        row.draft_revision = None
        row.row_version += 1
        await self._session.commit()
        return ProviderMutationResponse(
            status="draft_discarded", configuration=await self.get_configuration(provider)
        )

    async def diagnose_draft(
        self, provider: ProviderName, actor: UUID
    ) -> ProviderDraftDiagnoseResponse:
        row = await self._configuration(provider)
        draft = (
            await self._revision(row, row.draft_revision) if row and row.draft_revision else None
        )
        if row is None or draft is None:
            raise ProviderConfigurationError("provider_draft_missing")
        candidate = await self._credential(row, "candidate")
        active = await self._credential(row, "active")
        credentials = await self._decrypt_credential(provider, candidate or active)
        if not credentials and row.active_revision is None:
            credentials = self._environment_credentials(provider)
        started = perf_counter()
        status = "healthy"
        reason_code = None
        try:
            if provider == "deepseek":
                await self._diagnose_deepseek(draft.configuration_json, credentials)
            else:
                await self._diagnose_resend(draft.configuration_json, credentials, actor)
        except (ProviderConfigurationError, LLMGatewayError) as error:
            status = "unavailable"
            reason_code = _diagnostic_reason_code(error)
        checked_at = datetime.now(UTC)
        latency_ms = int((perf_counter() - started) * 1000)
        self._session.add(
            ProviderDiagnosticRunRecord(
                id=uuid4(),
                provider=provider,
                capability="structured_generation"
                if provider == "deepseek"
                else "transactional_email",
                status=status,
                latency_ms=latency_ms,
                reason_code=reason_code,
                checked_at=checked_at,
                requested_by_user_id=actor,
                configuration_revision_id=draft.id,
                credential_generation=draft.credential_generation,
                target="draft",
            )
        )
        await self._session.commit()
        return ProviderDraftDiagnoseResponse(
            provider=provider,
            status=cast(Literal["healthy", "unavailable"], status),
            reason_code=reason_code,
            latency_ms=latency_ms,
            checked_at=checked_at,
        )

    async def publish(
        self, provider: ProviderName, expected_row_version: int, actor: UUID
    ) -> ProviderMutationResponse:
        row = await self._configuration_for_update(provider)
        if row is None or row.row_version != expected_row_version:
            raise ProviderConfigurationConflict("provider_configuration_version_conflict")
        draft = await self._revision(row, row.draft_revision) if row.draft_revision else None
        if draft is None:
            raise ProviderConfigurationError("provider_draft_missing")
        enabled = bool(draft.configuration_json.get("enabled"))
        if enabled:
            candidate = await self._credential(row, "candidate")
            active = await self._credential(row, "active")
            if candidate is None and active is None:
                raise ProviderConfigurationError("provider_encrypted_credentials_required")
            latest = await self._session.scalar(
                select(ProviderDiagnosticRunRecord)
                .where(
                    ProviderDiagnosticRunRecord.provider == provider,
                    ProviderDiagnosticRunRecord.target == "draft",
                    ProviderDiagnosticRunRecord.configuration_revision_id == draft.id,
                    ProviderDiagnosticRunRecord.credential_generation
                    == draft.credential_generation,
                    ProviderDiagnosticRunRecord.status == "healthy",
                    ProviderDiagnosticRunRecord.checked_at
                    >= datetime.now(UTC) - timedelta(minutes=15),
                )
                .order_by(ProviderDiagnosticRunRecord.checked_at.desc())
            )
            if latest is None:
                raise ProviderConfigurationError("provider_draft_diagnostic_required")
        previous = await self._revision(row, row.active_revision) if row.active_revision else None
        if previous is not None:
            previous.status = "retired"
        candidate = await self._credential(row, "candidate")
        if candidate is not None:
            await self._session.execute(
                delete(ProviderCredentialRecord).where(
                    ProviderCredentialRecord.configuration_id == row.id,
                    ProviderCredentialRecord.slot == "active",
                )
            )
            await self._session.flush()
            candidate.slot = "active"
            candidate.activated_at = datetime.now(UTC)
        draft.status = "active"
        draft.published_by_user_id = actor
        draft.published_at = datetime.now(UTC)
        row.active_revision = draft.revision
        row.draft_revision = None
        row.row_version += 1
        await self._session.commit()
        return ProviderMutationResponse(
            status="published", configuration=await self.get_configuration(provider)
        )

    async def remove_credentials(
        self, provider: ProviderName, expected_row_version: int
    ) -> ProviderMutationResponse:
        row = await self._configuration_for_update(provider)
        if row is None or row.row_version != expected_row_version:
            raise ProviderConfigurationConflict("provider_configuration_version_conflict")
        active = await self._revision(row, row.active_revision) if row.active_revision else None
        if active is not None and bool(active.configuration_json.get("enabled")):
            raise ProviderConfigurationError("disable_provider_before_removing_credentials")
        await self._session.execute(
            delete(ProviderCredentialRecord).where(
                ProviderCredentialRecord.configuration_id == row.id
            )
        )
        row.row_version += 1
        await self._session.commit()
        return ProviderMutationResponse(
            status="credentials_removed", configuration=await self.get_configuration(provider)
        )

    async def runtime(self, provider: ProviderName) -> ProviderRuntimeConfiguration:
        if self._settings.managed_providers_hard_disabled:
            configuration = self._environment_configuration(provider)
            configuration["enabled"] = False
            return ProviderRuntimeConfiguration(provider, "disabled", None, configuration, {})
        row = await self._configuration(provider)
        active = (
            await self._revision(row, row.active_revision) if row and row.active_revision else None
        )
        if row is None or active is None:
            return ProviderRuntimeConfiguration(
                provider,
                "environment",
                None,
                self._environment_configuration(provider),
                self._environment_credentials(provider),
            )
        credential = await self._credential(row, "active")
        credentials = await self._decrypt_credential(provider, credential)
        return ProviderRuntimeConfiguration(
            provider, "database", active.revision, active.configuration_json, credentials
        )

    async def reencrypt_all(self, actor: UUID) -> int:
        if not self._vault.available:
            raise ProviderConfigurationError("provider_credential_vault_unavailable")
        rows = list((await self._session.scalars(select(ProviderCredentialRecord))).all())
        for row in rows:
            configuration = await self._session.get(
                ProviderConfigurationRecord, row.configuration_id
            )
            assert configuration is not None
            provider = cast(ProviderName, configuration.provider)
            secrets = await self._decrypt_credential(provider, row)
            encrypted = self._vault.encrypt(secrets, aad=self._aad(provider, row.generation))
            row.encrypted_payload = encrypted.ciphertext
            row.nonce = encrypted.nonce
            row.key_id = encrypted.key_id
            row.created_by_user_id = actor
        await self._session.commit()
        return len(rows)

    async def validate_production_runtime(self) -> None:
        if self._settings.app_env != "production":
            return
        deepseek_runtime = await self.runtime("deepseek")
        deepseek = DeepSeekConfiguration.model_validate(deepseek_runtime.configuration)
        if deepseek.enabled:
            if not deepseek_runtime.credentials.get("api_key"):
                raise ProviderConfigurationError("production_deepseek_credentials_missing")
            if (
                self._settings.legal_review_status != "approved"
                or self._settings.data_use_status != "approved"
            ):
                raise ProviderConfigurationError("production_deepseek_requires_approval")
        resend_runtime = await self.runtime("resend")
        resend = ResendConfiguration.model_validate(resend_runtime.configuration)
        if resend.enabled and (
            not resend_runtime.credentials.get("api_key")
            or not resend_runtime.credentials.get("webhook_secret")
        ):
            raise ProviderConfigurationError("production_resend_credentials_missing")

    async def _diagnose_deepseek(
        self, configuration: dict[str, object], credentials: dict[str, str]
    ) -> None:
        if not configuration.get("enabled"):
            raise ProviderConfigurationError("provider_disabled")
        api_key = credentials.get("api_key")
        if not api_key:
            raise ProviderConfigurationError("provider_credentials_missing")
        await LiteLLMGateway("json_object").generate_structured(
            model=ALLOWED_DEEPSEEK_MODELS[0],
            task_type="provider_diagnostic",
            system_prompt="Return one JSON object confirming availability.",
            input_data={"probe": "zhaoniu-provider-diagnostic"},
            response_schema={
                "type": "object",
                "properties": {"ok": {"type": "boolean"}},
                "required": ["ok"],
                "additionalProperties": False,
            },
            timeout_seconds=30,
            max_output_tokens=128,
            thinking_enabled=False,
            api_key=api_key,
        )

    async def _diagnose_resend(
        self, configuration: dict[str, object], credentials: dict[str, str], actor: UUID
    ) -> None:
        parsed = ResendConfiguration.model_validate(configuration)
        if not parsed.enabled:
            raise ProviderConfigurationError("provider_disabled")
        api_key = credentials.get("api_key")
        webhook_secret = credentials.get("webhook_secret", "")
        if not api_key or not webhook_secret.startswith("whsec_"):
            raise ProviderConfigurationError("provider_credentials_missing")
        try:
            decoded_webhook_secret = base64.b64decode(
                webhook_secret.removeprefix("whsec_"), validate=True
            )
        except ValueError as error:
            raise ProviderConfigurationError("resend_webhook_secret_invalid") from error
        if len(decoded_webhook_secret) < 16:
            raise ProviderConfigurationError("resend_webhook_secret_invalid")
        user = await self._session.get(User, actor)
        if user is None or user.email_verified_at is None:
            raise ProviderConfigurationError("verified_operator_email_required")
        since = datetime.now(UTC) - timedelta(hours=1)
        recent = await self._session.scalar(
            select(func.count())
            .select_from(ProviderDiagnosticRunRecord)
            .where(
                ProviderDiagnosticRunRecord.provider == "resend",
                ProviderDiagnosticRunRecord.requested_by_user_id == actor,
                ProviderDiagnosticRunRecord.target == "draft",
                ProviderDiagnosticRunRecord.checked_at >= since,
            )
        )
        if int(recent or 0) >= 3:
            raise ProviderConfigurationError("resend_diagnostic_rate_limit")
        sender = (
            f"{parsed.from_name} <{parsed.from_email}>" if parsed.from_name else parsed.from_email
        )
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Idempotency-Key": f"provider-diagnostic-{uuid4()}",
                        "User-Agent": "zhaoniu-provider-diagnostic/1.0",
                    },
                    json={
                        "from": sender,
                        "to": [user.email],
                        "subject": "知牛 Resend 配置测试",
                        "text": "这是一封由知牛管理后台发出的服务配置测试邮件。",
                    },
                )
        except httpx.TimeoutException as error:
            raise ProviderConfigurationError("provider_timeout") from error
        except httpx.HTTPError as error:
            raise ProviderConfigurationError("provider_connection") from error
        if response.status_code in {401, 403}:
            raise ProviderConfigurationError("provider_auth")
        if response.status_code == 429:
            raise ProviderConfigurationError("provider_rate_limit")
        if response.status_code >= 400:
            raise ProviderConfigurationError("provider_rejected")

    async def _configuration(self, provider: ProviderName) -> ProviderConfigurationRecord | None:
        return cast(
            ProviderConfigurationRecord | None,
            await self._session.scalar(
                select(ProviderConfigurationRecord).where(
                    ProviderConfigurationRecord.provider == provider,
                    ProviderConfigurationRecord.environment == self._settings.app_env,
                )
            ),
        )

    async def _configuration_for_update(
        self, provider: ProviderName, *, create: bool = False
    ) -> ProviderConfigurationRecord | None:
        row = await self._session.scalar(
            select(ProviderConfigurationRecord)
            .where(
                ProviderConfigurationRecord.provider == provider,
                ProviderConfigurationRecord.environment == self._settings.app_env,
            )
            .with_for_update()
        )
        if row is None and create:
            row = ProviderConfigurationRecord(
                id=uuid4(), provider=provider, environment=self._settings.app_env, row_version=0
            )
            self._session.add(row)
            await self._session.flush()
        return row

    async def _revision(
        self, row: ProviderConfigurationRecord | None, revision: int | None
    ) -> ProviderConfigurationRevisionRecord | None:
        if row is None or revision is None:
            return None
        return cast(
            ProviderConfigurationRevisionRecord | None,
            await self._session.scalar(
                select(ProviderConfigurationRevisionRecord).where(
                    ProviderConfigurationRevisionRecord.configuration_id == row.id,
                    ProviderConfigurationRevisionRecord.revision == revision,
                )
            ),
        )

    async def _credential(
        self, row: ProviderConfigurationRecord | None, slot: str
    ) -> ProviderCredentialRecord | None:
        if row is None:
            return None
        return cast(
            ProviderCredentialRecord | None,
            await self._session.scalar(
                select(ProviderCredentialRecord).where(
                    ProviderCredentialRecord.configuration_id == row.id,
                    ProviderCredentialRecord.slot == slot,
                )
            ),
        )

    async def _replace_candidate(
        self,
        row: ProviderConfigurationRecord,
        provider: ProviderName,
        secrets: dict[str, str],
        generation: int,
        actor: UUID,
    ) -> None:
        await self._session.execute(
            delete(ProviderCredentialRecord).where(
                ProviderCredentialRecord.configuration_id == row.id,
                ProviderCredentialRecord.slot == "candidate",
            )
        )
        encrypted = self._vault.encrypt(secrets, aad=self._aad(provider, generation))
        self._session.add(
            ProviderCredentialRecord(
                id=uuid4(),
                configuration_id=row.id,
                slot="candidate",
                encrypted_payload=encrypted.ciphertext,
                nonce=encrypted.nonce,
                key_id=encrypted.key_id,
                generation=generation,
                created_by_user_id=actor,
            )
        )

    async def _decrypt_credential(
        self, provider: ProviderName, credential: ProviderCredentialRecord | None
    ) -> dict[str, str]:
        if credential is None:
            return {}
        try:
            return self._vault.decrypt(
                credential.encrypted_payload,
                credential.nonce,
                credential.key_id,
                aad=self._aad(provider, credential.generation),
            )
        except CredentialVaultError as error:
            raise ProviderConfigurationError(str(error)) from error

    def _environment_configuration(self, provider: ProviderName) -> dict[str, object]:
        if provider == "resend":
            return ResendConfiguration(
                enabled=self._settings.email_delivery_mode == "resend",
                from_name=self._settings.resend_from_name,
                from_email=self._settings.resend_from_email,
                sending_domain=self._settings.resend_sending_domain,
            ).model_dump(mode="json")
        deepseek_models = [
            model for model in self._settings.llm_models if model in ALLOWED_DEEPSEEK_MODELS
        ] or [ALLOWED_DEEPSEEK_MODELS[0]]
        parser_models = [
            model
            for model in self._settings.screen_parser_models
            if model in ALLOWED_DEEPSEEK_MODELS
        ] or [ALLOWED_DEEPSEEK_MODELS[0]]
        explanation_models = [ALLOWED_DEEPSEEK_MODELS[0]]
        return DeepSeekConfiguration.model_validate(
            {
                "enabled": self._settings.llm_enabled,
                "max_concurrency": self._settings.llm_provider_max_concurrency,
                "daily_call_limit": self._settings.llm_provider_daily_call_limit,
                "stock_health": {
                    "enabled": self._settings.llm_enabled and bool(self._settings.llm_models),
                    "models": deepseek_models,
                    "max_attempts": min(self._settings.llm_max_attempts, len(deepseek_models)),
                    "timeout_seconds": self._settings.llm_per_model_timeout_seconds,
                    "deadline_seconds": self._settings.llm_run_deadline_seconds,
                    "max_output_tokens": 1200,
                },
                "screen_parser": {
                    "enabled": self._settings.screen_parser_enabled,
                    "models": parser_models,
                    "max_attempts": min(
                        self._settings.screen_parser_max_attempts, len(parser_models)
                    ),
                    "timeout_seconds": self._settings.screen_parser_per_model_timeout_seconds,
                    "deadline_seconds": self._settings.screen_parser_run_deadline_seconds,
                    "max_output_tokens": 1200,
                },
                "research_assistant": {
                    "enabled": self._settings.ai_explanation_enabled,
                    "models": explanation_models,
                    "max_attempts": 1,
                    "timeout_seconds": self._settings.ai_explanation_timeout_seconds,
                    "deadline_seconds": self._settings.ai_explanation_run_deadline_seconds,
                    "max_output_tokens": self._settings.ai_explanation_max_output_tokens,
                },
            }
        ).model_dump(mode="json")

    def _environment_credentials(self, provider: ProviderName) -> dict[str, str]:
        if provider == "deepseek":
            return (
                {"api_key": self._settings.deepseek_api_key}
                if self._settings.deepseek_api_key
                else {}
            )
        credentials: dict[str, str] = {}
        if self._settings.resend_api_key:
            credentials["api_key"] = self._settings.resend_api_key
        if self._settings.resend_webhook_secret:
            credentials["webhook_secret"] = self._settings.resend_webhook_secret
        return credentials

    @staticmethod
    def _secret_updates(
        provider: ProviderName, payload: DeepSeekDraftUpdate | ResendDraftUpdate
    ) -> dict[str, str]:
        updates: dict[str, str] = {}
        if payload.api_key and payload.api_key.get_secret_value():
            updates["api_key"] = payload.api_key.get_secret_value()
        if provider == "resend" and isinstance(payload, ResendDraftUpdate):
            if payload.webhook_secret and payload.webhook_secret.get_secret_value():
                updates["webhook_secret"] = payload.webhook_secret.get_secret_value()
        return updates

    def _aad(self, provider: ProviderName, generation: int) -> str:
        return f"zhaoniu:{self._settings.app_env}:{provider}:{generation}"

    @staticmethod
    def _revision_view(
        row: ProviderConfigurationRevisionRecord | None,
    ) -> ProviderRevisionView | None:
        if row is None:
            return None
        return ProviderRevisionView(
            revision=row.revision,
            status=cast(Literal["draft", "active", "retired"], row.status),
            configuration=row.configuration_json,
            configuration_hash=row.configuration_hash,
            credential_generation=row.credential_generation,
            created_at=row.created_at,
            published_at=row.published_at,
        )
