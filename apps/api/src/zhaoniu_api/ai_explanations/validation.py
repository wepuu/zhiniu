import re

from zhaoniu_api.ai_explanations.models import ResearchExplanationV1

NUMERIC_CLAIM = re.compile(
    r"[0-9０-９]|\d|[%％]|百分之|[零二三四五六七八九十百千万亿]|(?:元|万元|亿元|日期|年|月|日)"
)
ADVICE_LANGUAGE = re.compile(
    r"买入|卖出|加仓|减仓|建仓|持有建议|目标价|收益率|上涨概率|下跌概率|推荐|抄底|止损"
)


def validate_explanation(document: ResearchExplanationV1, evidence_ids: set[str]) -> None:
    cited = [
        document.headline,
        *document.summary,
        *(item.explanation for item in document.interpretations),
        *document.attention_items,
    ]
    for item in cited:
        if any(reference not in evidence_ids for reference in item.evidence_refs):
            raise ValueError("invalid_evidence_reference")
        if NUMERIC_CLAIM.search(item.text):
            raise ValueError("numeric_claim_not_allowed")
        if ADVICE_LANGUAGE.search(item.text):
            raise ValueError("investment_advice_language_not_allowed")
    if document.question_key == "corporate_event_context" and any(
        item.focus_key != "corporate_event" for item in document.interpretations
    ):
        raise ValueError("question_scope_mismatch")
    if document.question_key == "peer_position_context" and any(
        item.focus_key != "peer" for item in document.interpretations
    ):
        raise ValueError("question_scope_mismatch")
