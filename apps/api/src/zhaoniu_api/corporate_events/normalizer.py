from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, time, timedelta, timezone
from typing import Any, cast

from zhaoniu_api.corporate_events.errors import DisclosureNormalizationError
from zhaoniu_api.corporate_events.models import (
    DisclosureDocument,
    RawDisclosure,
    RawEventFact,
    SourceFact,
)
from zhaoniu_api.domain.models import resolve_symbol

CN_TZ = timezone(timedelta(hours=8))


def first(payload: dict[str, object], *names: str) -> object | None:
    for name in names:
        value = payload.get(name)
        if value is not None and str(value).strip() not in ("", "nan", "NaT"):
            return value
    return None


def parse_source_datetime(
    value: object, *, date_only_conservative: bool = True
) -> tuple[datetime, str, datetime]:
    if isinstance(value, datetime):
        source = value if value.tzinfo else value.replace(tzinfo=CN_TZ)
        source = source.astimezone(UTC)
        return source, "datetime", source
    if isinstance(value, date):
        parsed = value
    else:
        raw = str(value).strip().replace("/", "-")
        try:
            parsed_dt = datetime.fromisoformat(raw)
        except ValueError:
            try:
                parsed = date.fromisoformat(raw[:10])
            except ValueError as exc:
                raise DisclosureNormalizationError("invalid source publication time") from exc
        else:
            source = parsed_dt if parsed_dt.tzinfo else parsed_dt.replace(tzinfo=CN_TZ)
            source = source.astimezone(UTC)
            return source, "datetime", source
    source = datetime.combine(parsed, time.min, tzinfo=CN_TZ).astimezone(UTC)
    known = datetime.combine(
        parsed + timedelta(days=1) if date_only_conservative else parsed,
        time.min,
        tzinfo=CN_TZ,
    ).astimezone(UTC)
    return source, "date", known


class AKShareDisclosureNormalizer:
    def disclosures(
        self, rows: list[RawDisclosure], *, ingested_at: datetime | None = None
    ) -> list[DisclosureDocument]:
        ingested = ingested_at or datetime.now(UTC)
        result: list[DisclosureDocument] = []
        for row in rows:
            payload = row.payload
            title_value = first(payload, "公告标题", "公告名称", "标题", "title")
            published_value = first(payload, "公告时间", "公告日期", "日期", "time", "date")
            if title_value is None or published_value is None:
                raise DisclosureNormalizationError(
                    "disclosure is missing title or publication time"
                )
            published, precision, known_at = parse_source_datetime(published_value)
            canonical = resolve_symbol(row.requested_symbol).canonical
            url = str(first(payload, "公告链接", "网址", "url", "link") or "").strip()
            explicit_id = first(payload, "公告ID", "公告编号", "id")
            identity_material = f"{canonical}|{title_value}|{published.isoformat()}|{url}"
            source_id = str(explicit_id or hashlib.sha256(identity_material.encode()).hexdigest())
            content = {
                "symbol": canonical,
                "title": str(title_value).strip(),
                "published": published.isoformat(),
                "url": url,
            }
            result.append(
                DisclosureDocument(
                    symbol=canonical,
                    source_owner=row.source_owner,
                    source_document_id=source_id,
                    title=str(title_value).strip(),
                    source_url=url,
                    source_published_at=published,
                    source_published_precision=precision,
                    known_at=known_at,
                    ingested_at=ingested,
                    content_fingerprint=_hash(content),
                )
            )
        return result

    def source_facts(
        self, rows: list[RawEventFact], *, ingested_at: datetime | None = None
    ) -> list[SourceFact]:
        ingested = ingested_at or datetime.now(UTC)
        result: list[SourceFact] = []
        for row in rows:
            canonical = resolve_symbol(row.requested_symbol).canonical
            published_value = first(
                row.payload,
                "公告日期",
                "公告时间",
                "变动日期",
                "解禁日期",
                "日期",
                "date",
            )
            if published_value is None:
                published = None
                known_at = ingested
            else:
                published, _, known_at = parse_source_datetime(published_value)
            payload = _json_safe(row.payload)
            fact_id = _hash(
                {
                    "owner": row.source_owner,
                    "symbol": canonical,
                    "family": row.event_family.value,
                    "payload": payload,
                }
            )
            result.append(
                SourceFact(
                    symbol=canonical,
                    source_owner=row.source_owner,
                    source_fact_id=fact_id,
                    event_family=row.event_family,
                    raw_payload=payload,
                    source_published_at=published,
                    known_at=known_at,
                    ingested_at=ingested,
                )
            )
        return result


def _json_safe(payload: dict[str, object]) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(json.dumps(payload, ensure_ascii=False, default=str)))


def _hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(
            payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")
        ).encode()
    ).hexdigest()
