import asyncio
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol
from uuid import uuid4

import httpx

from zhaoniu_api.config import Settings


class TransactionalEmailError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TransactionalEmail:
    recipient: str
    subject: str
    text_body: str
    template_key: str
    template_version: str = "v1"
    idempotency_key: str | None = None


@dataclass(frozen=True, slots=True)
class EmailDeliveryResult:
    provider: str
    message_id: str


class TransactionalEmailGateway(Protocol):
    provider_name: str

    async def send(self, message: TransactionalEmail) -> EmailDeliveryResult: ...


class DisabledEmailGateway:
    provider_name = "disabled"

    async def send(self, message: TransactionalEmail) -> EmailDeliveryResult:
        raise TransactionalEmailError("email_delivery_disabled")


class SMTPEmailGateway:
    provider_name = "smtp"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def send(self, message: TransactionalEmail) -> EmailDeliveryResult:
        try:
            return await asyncio.wait_for(asyncio.to_thread(self._send_sync, message), timeout=10)
        except TimeoutError as error:
            raise TransactionalEmailError("email_provider_timeout") from error
        except (OSError, smtplib.SMTPException) as error:
            raise TransactionalEmailError("email_provider_unavailable") from error

    def _send_sync(self, message: TransactionalEmail) -> EmailDeliveryResult:
        email = EmailMessage()
        message_id = f"<{uuid4()}@zhaoniu.local>"
        email["Message-ID"] = message_id
        email["From"] = self._settings.email_from_address
        email["To"] = message.recipient
        email["Subject"] = message.subject
        email.set_content(message.text_body)
        with smtplib.SMTP(self._settings.smtp_host, self._settings.smtp_port, timeout=8) as client:
            if self._settings.smtp_use_tls:
                client.starttls()
            if self._settings.smtp_username:
                client.login(self._settings.smtp_username, self._settings.smtp_password)
            client.send_message(email)
        return EmailDeliveryResult(provider=self.provider_name, message_id=message_id)


class ResendEmailGateway:
    provider_name = "resend"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def send(self, message: TransactionalEmail) -> EmailDeliveryResult:
        sender = (
            f"{self._settings.resend_from_name} <{self._settings.resend_from_email}>"
            if self._settings.resend_from_name
            else self._settings.resend_from_email
        )
        headers = {"Authorization": f"Bearer {self._settings.resend_api_key}"}
        if message.idempotency_key:
            headers["Idempotency-Key"] = message.idempotency_key[:256]
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    "https://api.resend.com/emails",
                    headers=headers,
                    json={
                        "from": sender,
                        "to": [message.recipient],
                        "subject": message.subject,
                        "text": message.text_body,
                        "tags": [
                            {"name": "template", "value": message.template_key},
                            {"name": "version", "value": message.template_version},
                        ],
                    },
                )
        except httpx.TimeoutException as error:
            raise TransactionalEmailError("email_provider_timeout") from error
        except httpx.HTTPError as error:
            raise TransactionalEmailError("email_provider_unavailable") from error
        if response.status_code in {401, 403}:
            raise TransactionalEmailError("email_provider_auth")
        if response.status_code == 429:
            raise TransactionalEmailError("email_provider_rate_limit")
        if response.status_code >= 500:
            raise TransactionalEmailError("email_provider_unavailable")
        if response.status_code >= 400:
            raise TransactionalEmailError("email_provider_rejected")
        message_id = response.json().get("id")
        if not isinstance(message_id, str) or not message_id:
            raise TransactionalEmailError("email_provider_invalid_response")
        return EmailDeliveryResult(provider=self.provider_name, message_id=message_id)


def build_email_gateway(settings: Settings) -> TransactionalEmailGateway:
    if settings.email_delivery_mode == "resend":
        return ResendEmailGateway(settings)
    if settings.email_delivery_mode == "smtp":
        return SMTPEmailGateway(settings)
    return DisabledEmailGateway()
