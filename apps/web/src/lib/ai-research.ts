import type { AIResearchEnvelope } from "@zhaoniu/api-client";

const statuses = new Set([
  "ready",
  "not_built",
  "building",
  "failed",
  "disabled",
  "unsupported",
]);

export function assertAIResearch(value: AIResearchEnvelope) {
  if (!statuses.has(value.status)) {
    throw new Error("AI research response has an invalid status");
  }
  if (value.status === "ready" && !value.output) {
    throw new Error("Ready AI research response is missing its output");
  }
  if (value.output) {
    const evidenceIds = new Set(
      value.output.evidence_index.map((item) => item.evidence_id),
    );
    const cited = [
      value.output.content.headline,
      ...value.output.content.executive_summary,
      ...value.output.content.dimensions.flatMap((item) =>
        item.interpretation ? [item.interpretation] : [],
      ),
      ...(value.output.content.attention_items ?? []).flatMap((item) => [
        item.title,
        item.interpretation,
      ]),
    ];
    if (
      cited.some(
        (item) =>
          item.evidence_refs.length === 0 ||
          item.evidence_refs.some((reference) => !evidenceIds.has(reference)),
      )
    ) {
      throw new Error("AI research response contains an invalid citation");
    }
  }
  return value;
}
