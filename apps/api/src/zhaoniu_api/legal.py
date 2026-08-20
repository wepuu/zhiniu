from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True, slots=True)
class LegalDocument:
    document_type: str
    version: str
    title: str
    path: str
    required_at_registration: bool

    @property
    def content_hash(self) -> str:
        identity = f"{self.document_type}:{self.version}:{self.path}"
        return sha256(identity.encode()).hexdigest()


LEGAL_DOCUMENTS: tuple[LegalDocument, ...] = (
    LegalDocument("terms_of_service", "2026-08-v1", "用户协议", "/legal/terms", True),
    LegalDocument("privacy_policy", "2026-08-v1", "隐私政策", "/legal/privacy", True),
    LegalDocument("risk_disclosure", "2026-08-v1", "研究风险揭示", "/legal/risk", False),
    LegalDocument("ai_content_notice", "2026-08-v1", "AI 内容说明", "/legal/ai", False),
)


def legal_document(document_type: str) -> LegalDocument | None:
    return next((item for item in LEGAL_DOCUMENTS if item.document_type == document_type), None)


def required_registration_documents() -> tuple[LegalDocument, ...]:
    return tuple(item for item in LEGAL_DOCUMENTS if item.required_at_registration)
