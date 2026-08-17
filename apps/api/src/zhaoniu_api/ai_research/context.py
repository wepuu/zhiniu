import hashlib
import json

from zhaoniu_api.ai_research.models import AIResearchContext, EvidenceIndexEntry
from zhaoniu_api.research.models import ResearchObservation, ResearchSnapshotDocument

CONTEXT_VERSION = "ai-context-v1"
MAX_OBSERVATIONS = 5
_ATTENTION_RANK = {"important": 3, "notice": 2, "info": 1}


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def digest(payload: object) -> str:
    return hashlib.sha256(_canonical_json(payload).encode()).hexdigest()


def select_observations(
    observations: list[ResearchObservation], *, limit: int = MAX_OBSERVATIONS
) -> list[ResearchObservation]:
    ordered = sorted(
        observations,
        key=lambda item: (
            -_ATTENTION_RANK[item.attention_level.value],
            -item.current_period.toordinal(),
            item.observation_key,
        ),
    )
    selected: list[ResearchObservation] = []
    seen_dimensions: set[str] = set()
    for item in ordered:
        if item.dimension.value not in seen_dimensions:
            selected.append(item)
            seen_dimensions.add(item.dimension.value)
        if len(selected) == limit:
            return selected
    selected_ids = {item.id for item in selected}
    selected.extend(item for item in ordered if item.id not in selected_ids)
    return selected[:limit]


def _evidence_id(snapshot_id: object, observation: ResearchObservation) -> str:
    metric_ids = sorted(str(item.metric_point_id) for item in observation.evidence_metrics)
    source_ids = sorted(
        f"{item.provider}:{item.provider_record_id}:{item.report_id}"
        for item in observation.evidence_sources
    )
    material = [str(snapshot_id), str(observation.id), metric_ids, source_ids]
    return f"EV-{digest(material)[:12].upper()}"


def build_context(snapshot: ResearchSnapshotDocument) -> AIResearchContext:
    entries: list[EvidenceIndexEntry] = []
    seen_ids: set[str] = set()
    for observation in select_observations(snapshot.observations):
        evidence_id = _evidence_id(snapshot.id, observation)
        if evidence_id in seen_ids:
            raise ValueError("evidence id collision")
        seen_ids.add(evidence_id)
        entries.append(
            EvidenceIndexEntry(
                evidence_id=evidence_id,
                observation_id=observation.id,
                dimension=observation.dimension,
                title=observation.title,
                summary=observation.summary,
                current_period=observation.current_period,
                evidence_metrics=observation.evidence_metrics,
                evidence_sources=observation.evidence_sources,
                calculation=observation.calculation,
            )
        )
    context = AIResearchContext(
        snapshot_id=snapshot.id,
        symbol=snapshot.symbol,
        knowledge_cutoff=snapshot.knowledge_cutoff,
        data_version=snapshot.data_version,
        metric_version=snapshot.metric_version,
        rule_set_version=snapshot.rule_set_version,
        research_template_version=snapshot.research_template_version,
        coverage=snapshot.coverage,
        evidence_index=entries,
    )
    return context.model_copy(
        update={"context_hash": digest(context.model_dump(mode="json", exclude={"context_hash"}))}
    )
