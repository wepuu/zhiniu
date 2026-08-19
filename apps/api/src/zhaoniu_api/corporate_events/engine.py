from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from typing import Any

from zhaoniu_api.corporate_events.models import (
    ATTENTION_RULE_VERSION,
    CLASSIFIER_VERSION,
    Classification,
    DisclosureDocument,
    EventCandidate,
    EventFamily,
    EventType,
    SourceFact,
)

RULES: tuple[tuple[str, EventFamily, EventType, tuple[str, ...]], ...] = (
    (
        "regulatory-investigation",
        EventFamily.REGULATORY_ACTION,
        EventType.INVESTIGATION_OPENED,
        ("立案", "调查通知"),
    ),
    (
        "regulatory-penalty",
        EventFamily.REGULATORY_ACTION,
        EventType.ADMINISTRATIVE_PENALTY,
        ("行政处罚", "处罚决定"),
    ),
    (
        "regulatory-warning",
        EventFamily.REGULATORY_ACTION,
        EventType.WARNING_LETTER,
        ("警示函", "警告函"),
    ),
    (
        "regulatory-discipline",
        EventFamily.REGULATORY_ACTION,
        EventType.DISCIPLINARY_ACTION,
        ("纪律处分", "公开谴责"),
    ),
    (
        "regulatory-inquiry",
        EventFamily.REGULATORY_ACTION,
        EventType.REGULATORY_INQUIRY,
        ("问询函", "关注函", "监管函"),
    ),
    (
        "regulatory-measure",
        EventFamily.REGULATORY_ACTION,
        EventType.REGULATORY_MEASURE,
        ("监管措施", "责令改正"),
    ),
    (
        "repurchase-cancelled",
        EventFamily.SHARE_REPURCHASE,
        EventType.REPURCHASE_CANCELLED,
        ("终止回购", "取消回购"),
    ),
    (
        "repurchase-completed",
        EventFamily.SHARE_REPURCHASE,
        EventType.REPURCHASE_COMPLETED,
        ("回购完成", "回购实施完成"),
    ),
    (
        "repurchase-adjusted",
        EventFamily.SHARE_REPURCHASE,
        EventType.REPURCHASE_ADJUSTED,
        ("调整回购", "变更回购"),
    ),
    (
        "repurchase-progress",
        EventFamily.SHARE_REPURCHASE,
        EventType.REPURCHASE_PROGRESS,
        ("回购进展", "实施回购"),
    ),
    (
        "repurchase-plan",
        EventFamily.SHARE_REPURCHASE,
        EventType.REPURCHASE_PLAN,
        ("回购方案", "回购股份方案", "回购股份预案", "拟回购"),
    ),
    (
        "pledge-release",
        EventFamily.SHARE_PLEDGE,
        EventType.PLEDGE_RELEASED,
        ("解除质押", "质押解除"),
    ),
    (
        "pledge-change",
        EventFamily.SHARE_PLEDGE,
        EventType.PLEDGE_CHANGED,
        ("质押变更", "补充质押", "延期购回"),
    ),
    (
        "pledge-created",
        EventFamily.SHARE_PLEDGE,
        EventType.PLEDGE_CREATED,
        ("股份质押", "股权质押"),
    ),
    (
        "unlock-completed",
        EventFamily.SHARE_UNLOCK,
        EventType.UNLOCK_COMPLETED,
        ("解除限售完成", "解禁完成"),
    ),
    (
        "unlock-scheduled",
        EventFamily.SHARE_UNLOCK,
        EventType.UNLOCK_SCHEDULED,
        ("解除限售", "限售股上市流通", "解禁"),
    ),
)


def classify_title(title: str) -> Classification:
    if "回购注销" in title and ("限制性股票" in title or "股权激励" in title):
        return Classification(None, None, "unsupported", "equity-incentive-cancellation")
    matches = [rule for rule in RULES if any(term in title for term in rule[3])]
    identities = {(item[1], item[2]) for item in matches}
    if not matches:
        return Classification(None, None, "unclassified")
    if len(identities) > 1:
        return Classification(None, None, "ambiguous")
    rule_id, family, event_type, _ = matches[0]
    return Classification(family, event_type, "classified", f"{CLASSIFIER_VERSION}:{rule_id}")


def extract_candidate(
    document: DisclosureDocument,
    classification: Classification,
    source_fact: SourceFact | None = None,
) -> EventCandidate | None:
    if (
        classification.status != "classified"
        or not classification.event_family
        or not classification.event_type
    ):
        return None
    payload = dict(source_fact.raw_payload) if source_fact else {}
    effective = _effective_date(payload)
    typed_payload: dict[str, Any] = {
        "kind": classification.event_family.value,
        "event_type": classification.event_type.value,
    }
    typed_payload.update(_selected_fields(payload))
    identity_basis = "source_document+family+effective_date"
    thread = _hash(
        {
            "symbol": document.symbol,
            "family": classification.event_family.value,
            "effective": effective,
        }
    )
    fingerprint = _hash(
        {
            "thread": thread,
            "document": document.source_document_id,
            "type": classification.event_type.value,
            "payload": typed_payload,
            "extractor": "corporate-event-extractor-v1",
        }
    )
    lineage = {
        "title": {"document_id": str(document.id), "field": "title"},
        **(
            {
                key: {"source_fact_id": str(source_fact.id), "field": key}
                for key in typed_payload
                if key not in {"kind", "event_type"}
            }
            if source_fact
            else {}
        ),
    }
    return EventCandidate(
        document_id=document.id,
        source_fact_id=source_fact.id if source_fact else None,
        symbol=document.symbol,
        event_family=classification.event_family,
        event_type=classification.event_type,
        title=document.title,
        source_published_at=document.source_published_at,
        source_published_precision=document.source_published_precision,
        known_at=document.known_at,
        event_effective_from=effective,
        event_effective_to=None,
        event_time_precision="date" if effective else None,
        extraction_status="complete" if source_fact else "partial",
        typed_payload=typed_payload,
        field_lineage=lineage,
        event_thread_key=thread,
        event_version_fingerprint=fingerprint,
        identity_basis=identity_basis,
    )


def attention_for(event_type: EventType) -> tuple[str, str, str]:
    if event_type in {
        EventType.INVESTIGATION_OPENED,
        EventType.ADMINISTRATIVE_PENALTY,
        EventType.DISCIPLINARY_ACTION,
    }:
        return (
            "important",
            "material-regulatory-action",
            "涉及调查、处罚或纪律处分，需核对后续正式披露",
        )
    if event_type in {
        EventType.REGULATORY_INQUIRY,
        EventType.WARNING_LETTER,
        EventType.REGULATORY_MEASURE,
        EventType.PLEDGE_CREATED,
        EventType.PLEDGE_CHANGED,
        EventType.UNLOCK_SCHEDULED,
        EventType.REPURCHASE_CANCELLED,
    }:
        return "notice", "follow-up-required", "事件可能存在后续进展，建议持续核对公告"
    return "info", "routine-disclosure", "记录已披露的公司行动及其进展"


def rule_version() -> str:
    return ATTENTION_RULE_VERSION


def _effective_date(payload: dict[str, Any]) -> date | None:
    for key in ("解禁日期", "上市流通日期", "变动日期", "实施日期", "日期", "date"):
        value = payload.get(key)
        if value in (None, ""):
            continue
        try:
            return date.fromisoformat(str(value).strip().replace("/", "-")[:10])
        except ValueError:
            continue
    return None


def _selected_fields(payload: dict[str, Any]) -> dict[str, Any]:
    allowed = (
        "股东名称",
        "质押方",
        "质押数量",
        "质押比例",
        "回购数量",
        "回购金额",
        "解禁数量",
        "解禁比例",
        "解禁日期",
        "上市流通日期",
    )
    result: dict[str, Any] = {}
    for key in allowed:
        value = payload.get(key)
        if value not in (None, "", "nan"):
            result[_snake(key)] = value
    return result


def _snake(value: str) -> str:
    mapping = {
        "股东名称": "shareholder_name",
        "质押方": "pledgor",
        "质押数量": "pledged_shares",
        "质押比例": "pledged_ratio",
        "回购数量": "repurchased_shares",
        "回购金额": "repurchase_amount",
        "解禁数量": "unlock_shares",
        "解禁比例": "unlock_ratio",
        "解禁日期": "unlock_date",
        "上市流通日期": "listing_date",
    }
    return mapping.get(value, re.sub(r"\W+", "_", value).strip("_").lower())


def _hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(
            payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")
        ).encode()
    ).hexdigest()
