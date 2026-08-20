import asyncio
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol
from uuid import uuid4

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


def build_email_gateway(settings: Settings) -> TransactionalEmailGateway:
    if settings.email_delivery_mode == "smtp":
        return SMTPEmailGateway(settings)
    return DisabledEmailGateway()
