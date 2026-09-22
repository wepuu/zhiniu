import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from zhaoniu_api.auth.resend_webhook import (
    ResendWebhookError,
    parse_resend_event,
    verify_resend_signature,
)
from zhaoniu_api.config import Settings
from zhaoniu_api.operations import BetaReadinessReport
from zhaoniu_api.operations_console.models import OperatorContext, OperatorRole
from zhaoniu_api.operations_console.service import (
    CAPABILITIES,
    OperatorAuthorizationError,
    OperatorService,
)


def _context(role: OperatorRole, *, elevated: bool = False) -> OperatorContext:
    return OperatorContext(
        role=role,
        capabilities=sorted(CAPABILITIES[role]),
        elevated=elevated,
    )


def test_viewer_is_read_only() -> None:
    context = _context("viewer")
    OperatorService.require(context, "dashboard.read")
    with pytest.raises(OperatorAuthorizationError, match="operator_capability_required"):
        OperatorService.require(context, "users.sessions.revoke")


def test_high_risk_action_requires_elevated_session() -> None:
    with pytest.raises(OperatorAuthorizationError, match="operator_step_up_required"):
        OperatorService.require(
            _context("security_admin"),
            "users.status.manage",
            elevated=True,
        )
    OperatorService.require(
        _context("security_admin", elevated=True),
        "users.status.manage",
        elevated=True,
    )


@pytest.mark.asyncio
async def test_beta_admission_rejects_unknown_candidate() -> None:
    session = SimpleNamespace(get=AsyncMock(return_value=None))

    with pytest.raises(LookupError, match="production_release_candidate_not_found"):
        await OperatorService(cast(AsyncSession, session), Settings()).beta_admission(uuid4())


@pytest.mark.asyncio
async def test_beta_admission_composes_existing_release_bound_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    candidate_id = uuid4()
    reliability = SimpleNamespace(
        id=uuid4(),
        status="passed",
        created_at=now,
        window_started_at=now - timedelta(hours=48),
        window_ended_at=now,
        release_commit="a" * 40,
        api_image_digest=f"sha256:{'c' * 64}",
        web_image_digest=f"sha256:{'d' * 64}",
        migration_head="20260914_0030",
        configuration_fingerprint="b" * 64,
    )
    release = SimpleNamespace(
        id=candidate_id,
        status="ready_invites",
        target_environment="production",
        created_at=now,
        commit_sha="a" * 40,
        api_image_digest=f"sha256:{'c' * 64}",
        web_image_digest=f"sha256:{'d' * 64}",
        migration_head="20260914_0030",
        configuration_fingerprint="b" * 64,
    )
    invite_gate = SimpleNamespace(
        id=uuid4(),
        status="passed",
        result_fingerprint="e" * 64,
        finished_at=now,
    )
    deployment = SimpleNamespace(deployment_ref="pipeline/run/22")
    gate_item = SimpleNamespace(
        check_key="provider.acceptance",
        mandatory=True,
        status="passed",
        expires_at=now + timedelta(hours=12),
    )
    session = SimpleNamespace(
        get=AsyncMock(return_value=release),
        scalar=AsyncMock(side_effect=[reliability, invite_gate, deployment]),
        scalars=AsyncMock(return_value=[gate_item]),
    )
    settings = Settings(
        app_env="production",
        automation_hard_disabled=False,
        automation_ai_enabled=True,
        watchlist_preparation_enabled=True,
    )
    monkeypatch.setattr(
        "zhaoniu_api.operations_console.service.evaluate_beta_readiness",
        AsyncMock(
            return_value=BetaReadinessReport(
                status="ready_for_invited_beta",
                active_users=3,
                capacity=500,
                blocking_reasons=[],
            )
        ),
    )
    monkeypatch.setattr(
        "zhaoniu_api.operations_console.service.InviteBetaService.gate_reasons",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "zhaoniu_api.operations_console.service.ProviderConfigurationService.runtime",
        AsyncMock(
            return_value=SimpleNamespace(
                configuration={
                    "enabled": True,
                    "daily_call_limit": 100,
                    "max_concurrency": 2,
                    "stock_health": {
                        "enabled": True,
                        "models": ["deepseek/deepseek-v4-flash"],
                        "max_attempts": 1,
                        "timeout_seconds": 60,
                        "deadline_seconds": 90,
                        "max_output_tokens": 1200,
                    },
                    "research_assistant": {
                        "enabled": False,
                        "models": ["deepseek/deepseek-v4-flash"],
                        "max_attempts": 1,
                        "timeout_seconds": 60,
                        "deadline_seconds": 90,
                        "max_output_tokens": 1200,
                    },
                },
                credentials={"api_key": "configured"},
                source="database",
                revision=5,
            )
        ),
    )
    monkeypatch.setattr(
        "zhaoniu_api.operations_console.service.ProviderConfigurationService.get_configuration",
        AsyncMock(
            return_value=SimpleNamespace(
                diagnostic_status="healthy",
                diagnostic_checked_at=now,
            )
        ),
    )

    result = await OperatorService(cast(AsyncSession, session), settings).beta_admission(
        candidate_id
    )

    assert result.status == "ready"
    assert result.candidate is not None
    assert result.candidate.id == candidate_id
    assert result.candidate.invite_gate_run_id == invite_gate.id
    assert result.candidate.deployment_ref == "pipeline/run/22"
    assert [item.key for item in result.checks] == [
        "platform.readiness",
        "release.environment",
        "invitation.gates",
        "automation.beta_paths",
        "provider.deepseek",
        "reliability.database_observation",
        "release.invite_activation",
    ]
    assert all(item.status == "passed" for item in result.checks)


@pytest.mark.asyncio
async def test_beta_admission_fails_closed_without_bound_reliability_or_current_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    candidate_id = uuid4()
    release = SimpleNamespace(
        id=candidate_id,
        status="ready_invites",
        target_environment="production",
        created_at=now,
        commit_sha="a" * 40,
        api_image_digest=f"sha256:{'c' * 64}",
        web_image_digest=f"sha256:{'d' * 64}",
        migration_head="20260914_0030",
        configuration_fingerprint="b" * 64,
    )
    session = SimpleNamespace(
        get=AsyncMock(return_value=release),
        scalar=AsyncMock(
            side_effect=[
                None,
                SimpleNamespace(
                    id=uuid4(),
                    status="passed",
                    result_fingerprint="e" * 64,
                    finished_at=now,
                ),
                SimpleNamespace(deployment_ref="pipeline/run/22"),
            ]
        ),
        scalars=AsyncMock(
            return_value=[
                SimpleNamespace(
                    check_key="provider.acceptance",
                    mandatory=True,
                    status="passed",
                    expires_at=now - timedelta(minutes=1),
                )
            ]
        ),
    )
    settings = Settings(
        app_env="production",
        automation_hard_disabled=False,
        automation_ai_enabled=True,
        watchlist_preparation_enabled=True,
    )
    monkeypatch.setattr(
        "zhaoniu_api.operations_console.service.evaluate_beta_readiness",
        AsyncMock(
            return_value=BetaReadinessReport(
                status="ready_for_invited_beta",
                active_users=3,
                capacity=500,
                blocking_reasons=[],
            )
        ),
    )
    monkeypatch.setattr(
        "zhaoniu_api.operations_console.service.InviteBetaService.gate_reasons",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "zhaoniu_api.operations_console.service.ProviderConfigurationService.runtime",
        AsyncMock(
            return_value=SimpleNamespace(
                configuration={
                    "enabled": True,
                    "daily_call_limit": 100,
                    "max_concurrency": 2,
                    "stock_health": {
                        "enabled": True,
                        "models": ["deepseek/deepseek-v4-flash"],
                        "max_attempts": 1,
                        "timeout_seconds": 60,
                        "deadline_seconds": 90,
                        "max_output_tokens": 1200,
                    },
                    "research_assistant": {
                        "enabled": False,
                        "models": ["deepseek/deepseek-v4-flash"],
                        "max_attempts": 1,
                        "timeout_seconds": 60,
                        "deadline_seconds": 90,
                        "max_output_tokens": 1200,
                    },
                },
                credentials={"api_key": "configured"},
                source="database",
                revision=5,
            )
        ),
    )
    monkeypatch.setattr(
        "zhaoniu_api.operations_console.service.ProviderConfigurationService.get_configuration",
        AsyncMock(
            return_value=SimpleNamespace(
                diagnostic_status="healthy",
                diagnostic_checked_at=now,
            )
        ),
    )

    result = await OperatorService(cast(AsyncSession, session), settings).beta_admission(
        candidate_id
    )

    assert result.status == "blocked"
    assert "beta_reliability_observation_missing" in result.blocking_reasons
    assert "invite_activation_gate_evidence_expired" in result.blocking_reasons
    reliability_check = next(
        item for item in result.checks if item.key == "reliability.database_observation"
    )
    assert reliability_check.status == "pending"


def test_resend_signature_and_event_allowlist() -> None:
    payload = json.dumps(
        {"type": "email.delivered", "created_at": "2026-08-21T10:00:00Z", "data": {}}
    ).encode()
    message_id = "msg_test"
    timestamp = "1787306400"
    raw_secret = b"test-secret"
    secret = "whsec_" + base64.b64encode(raw_secret).decode()
    signed = f"{message_id}.{timestamp}.".encode() + payload
    signature = base64.b64encode(hmac.new(raw_secret, signed, hashlib.sha256).digest()).decode()
    verify_resend_signature(
        payload,
        secret=secret,
        message_id=message_id,
        timestamp=timestamp,
        signature=f"v1,{signature}",
        now=int(timestamp),
    )
    assert parse_resend_event(payload)["type"] == "email.delivered"


def test_resend_rejects_expired_or_unknown_event() -> None:
    with pytest.raises(ResendWebhookError, match="expired_webhook_timestamp"):
        verify_resend_signature(
            b"{}",
            secret="whsec_" + base64.b64encode(b"secret").decode(),
            message_id="id",
            timestamp="1",
            signature="v1,invalid",
            now=1000,
        )
    with pytest.raises(ResendWebhookError, match="unsupported_webhook_event"):
        parse_resend_event(b'{"type":"contact.created"}')
