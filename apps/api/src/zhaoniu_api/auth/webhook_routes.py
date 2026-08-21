from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from zhaoniu_api.auth.resend_webhook import (
    ResendWebhookError,
    parse_resend_event,
    process_resend_event,
    verify_resend_signature,
)
from zhaoniu_api.config import get_settings
from zhaoniu_api.database import session_factory

router = APIRouter(prefix="/api/v1/webhooks", tags=["provider webhooks"])


class WebhookReceipt(BaseModel):
    status: str


@router.post("/resend", response_model=WebhookReceipt)
async def receive_resend_webhook(request: Request) -> WebhookReceipt:
    settings = get_settings()
    if not settings.resend_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="webhook_disabled"
        )
    payload = await request.body()
    try:
        message_id = request.headers["svix-id"]
        verify_resend_signature(
            payload,
            secret=settings.resend_webhook_secret,
            message_id=message_id,
            timestamp=request.headers["svix-timestamp"],
            signature=request.headers["svix-signature"],
        )
        event = parse_resend_event(payload)
    except (KeyError, ResendWebhookError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    async with session_factory() as session:
        receipt = await process_resend_event(session, event, message_id)
    return WebhookReceipt(status=receipt)
