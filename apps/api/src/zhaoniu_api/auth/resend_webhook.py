from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from zhaoniu_api.db import (
    TransactionalEmailDeliveryRecord,
    TransactionalEmailProviderEventRecord,
)

ALLOWED_EVENTS = {
    "email.sent",
    "email.delivered",
    "email.delivery_delayed",
    "email.bounced",
    "email.failed",
    "email.complained",
    "email.suppressed",
}
STATUS_BY_EVENT = {
    "email.sent": "submitted",
    "email.delivered": "delivered",
    "email.delivery_delayed": "delayed",
    "email.bounced": "bounced",
    "email.failed": "failed",
    "email.complained": "complained",
    "email.suppressed": "suppressed",
}


class ResendWebhookError(ValueError):
    pass


def verify_resend_signature(
    payload: bytes,
    *,
    secret: str,
    message_id: str,
    timestamp: str,
    signature: str,
    now: int | None = None,
) -> None:
    try:
        sent_at = int(timestamp)
    except ValueError as error:
        raise ResendWebhookError("invalid_webhook_timestamp") from error
    if abs((now or int(time.time())) - sent_at) > 300:
        raise ResendWebhookError("expired_webhook_timestamp")
    try:
        key = base64.b64decode(secret.removeprefix("whsec_"), validate=True)
    except ValueError as error:
        raise ResendWebhookError("invalid_webhook_secret") from error
    signed = f"{message_id}.{timestamp}.".encode() + payload
    expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
    candidates = [part.split(",", 1)[1] for part in signature.split() if part.startswith("v1,")]
    if not any(hmac.compare_digest(expected, candidate) for candidate in candidates):
        raise ResendWebhookError("invalid_webhook_signature")


def parse_resend_event(payload: bytes) -> dict[str, Any]:
    try:
        event = json.loads(payload)
    except json.JSONDecodeError as error:
        raise ResendWebhookError("invalid_webhook_payload") from error
    if not isinstance(event, dict) or event.get("type") not in ALLOWED_EVENTS:
        raise ResendWebhookError("unsupported_webhook_event")
    return event


async def process_resend_event(
    session: AsyncSession, event: dict[str, Any], provider_event_id: str
) -> str:
    event_type = str(event["type"])
    raw_data = event.get("data")
    data: dict[str, Any] = raw_data if isinstance(raw_data, dict) else {}
    provider_message_id = data.get("email_id") or data.get("id")
    created_raw = event.get("created_at") or data.get("created_at")
    try:
        event_created_at = datetime.fromisoformat(str(created_raw).replace("Z", "+00:00"))
    except ValueError:
        event_created_at = datetime.now(UTC)

    record = TransactionalEmailProviderEventRecord(
        id=uuid4(),
        provider="resend",
        provider_event_id=provider_event_id[:160],
        event_type=event_type,
        provider_message_id=str(provider_message_id)[:200] if provider_message_id else None,
        event_created_at=event_created_at,
        status="received",
        reason_code=str(data.get("reason"))[:96] if data.get("reason") else None,
    )
    session.add(record)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        return "duplicate"

    delivery = None
    if provider_message_id:
        delivery = await session.scalar(
            select(TransactionalEmailDeliveryRecord)
            .where(
                TransactionalEmailDeliveryRecord.provider == "resend",
                TransactionalEmailDeliveryRecord.provider_message_id == str(provider_message_id),
            )
            .with_for_update()
        )
    if delivery and (delivery.last_event_at is None or event_created_at >= delivery.last_event_at):
        delivery.status = STATUS_BY_EVENT[event_type]
        delivery.last_event_at = event_created_at
        if event_type == "email.delivered":
            delivery.delivered_at = event_created_at
        if event_type in {"email.failed", "email.bounced", "email.suppressed"}:
            delivery.error_code = event_type.replace("email.", "email_provider_")
    record.status = "processed" if delivery else "unmatched"
    record.processed_at = datetime.now(UTC)
    await session.commit()
    return record.status
