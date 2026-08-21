import base64
import hashlib
import hmac
import json

import pytest
from zhaoniu_api.auth.resend_webhook import (
    ResendWebhookError,
    parse_resend_event,
    verify_resend_signature,
)
from zhaoniu_api.operations_console.models import OperatorContext
from zhaoniu_api.operations_console.service import (
    CAPABILITIES,
    OperatorAuthorizationError,
    OperatorService,
)


def _context(role: str, *, elevated: bool = False) -> OperatorContext:
    return OperatorContext(  # type: ignore[arg-type]
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
