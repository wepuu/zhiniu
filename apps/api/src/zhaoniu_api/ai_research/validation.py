import re

from pydantic import ValidationError

from zhaoniu_api.ai_research.models import (
    AIResearchContext,
    CitedText,
    StockHealthResearchV1,
)
from zhaoniu_api.research.models import ObservationDimension

_NUMERIC_PATTERN = re.compile(
    r"[0-9０-９%％￥¥$]|百分之(?:一|二|三|四|五|六|七|八|九|十|百)|"
    r"(?:一|二|三|四|五|六|七|八|九|十|百|千|万|亿)"
    r"(?:年|月|日|季|期|项|条|个|成|倍|元|股|次|点)"
)
_FORBIDDEN_PATTERN = re.compile(
    r"买入|卖出|增持|减持|目标价|上涨空间|下跌空间|收益率|收益概率|"
    r"建议持有|建仓|加仓|减仓|止损|止盈|抄底|看多|看空|强烈推荐|推荐|"
    r"利好|利空|变好|变坏|\bbuy\b|\bsell\b|price target",
    re.IGNORECASE,
)


class AIOutputValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _cited_texts(payload: StockHealthResearchV1) -> list[CitedText]:
    items = [payload.headline, *payload.executive_summary]
    items.extend(
        item.interpretation for item in payload.dimensions if item.interpretation is not None
    )
    for item in payload.attention_items:
        items.extend((item.title, item.interpretation))
    return items


def _without_prose(value: object) -> object:
    if isinstance(value, dict):
        return {key: "" if key == "text" else _without_prose(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_without_prose(item) for item in value]
    return value


def validate_repair_preserves_structure(
    original: dict[str, object], repaired: StockHealthResearchV1
) -> None:
    try:
        original_payload = StockHealthResearchV1.model_validate(original)
    except ValidationError as error:
        raise AIOutputValidationError(
            "repair_structure_invalid", "repair source does not match StockHealthResearchV1"
        ) from error
    if _without_prose(original_payload.model_dump(mode="json")) != _without_prose(
        repaired.model_dump(mode="json")
    ):
        raise AIOutputValidationError(
            "repair_structure_invalid",
            "AI repair must preserve structure and evidence references",
        )


def validate_stock_health_output(
    raw: dict[str, object], context: AIResearchContext
) -> StockHealthResearchV1:
    try:
        payload = StockHealthResearchV1.model_validate(raw)
    except ValidationError as error:
        raise AIOutputValidationError(
            "schema_invalid", "model output does not match StockHealthResearchV1"
        ) from error
    evidence = {item.evidence_id: item for item in context.evidence_index}
    if not evidence:
        raise AIOutputValidationError("coverage_invalid", "AI context contains no evidence")

    dimensions = [item.dimension for item in payload.dimensions]
    expected_dimensions = list(ObservationDimension)
    if dimensions != expected_dimensions:
        raise AIOutputValidationError(
            "dimension_invalid", "dimensions must appear exactly once in canonical order"
        )

    for cited in _cited_texts(payload):
        if len(cited.evidence_refs) != len(set(cited.evidence_refs)):
            raise AIOutputValidationError("citation_invalid", "duplicate evidence reference")
        if unknown := set(cited.evidence_refs) - evidence.keys():
            raise AIOutputValidationError(
                "citation_invalid", f"unknown evidence references: {sorted(unknown)}"
            )
        if _NUMERIC_PATTERN.search(cited.text):
            raise AIOutputValidationError("numeric_claim", "AI prose must not contain numbers")
        if _FORBIDDEN_PATTERN.search(cited.text):
            raise AIOutputValidationError(
                "forbidden_language", "AI prose contains investment-advice language"
            )

    evidence_dimensions = {item.dimension for item in context.evidence_index}
    coverage_by_dimension = {item.dimension: item.status for item in context.coverage}
    for item in payload.dimensions:
        available = (
            item.dimension in evidence_dimensions
            and coverage_by_dimension.get(item.dimension) == "available"
        )
        if available and item.interpretation is None:
            raise AIOutputValidationError(
                "coverage_invalid", f"missing interpretation for {item.dimension.value}"
            )
        if not available and item.interpretation is not None:
            raise AIOutputValidationError(
                "coverage_invalid", f"unsupported interpretation for {item.dimension.value}"
            )
        if item.interpretation is not None and any(
            evidence[reference].dimension != item.dimension
            for reference in item.interpretation.evidence_refs
        ):
            raise AIOutputValidationError(
                "dimension_invalid", f"cross-dimension citation for {item.dimension.value}"
            )
    return payload
