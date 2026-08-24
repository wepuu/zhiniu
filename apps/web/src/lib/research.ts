import type {
  ResearchObservation,
  ResearchSnapshotEnvelope,
} from "@zhaoniu/api-client";

import { formatFinancialValue } from "./presentation";

function assertObservation(observation: ResearchObservation) {
  if (
    !observation.id ||
    !observation.title ||
    !observation.rule_id ||
    !Array.isArray(observation.evidence_metrics) ||
    !Array.isArray(observation.evidence_sources)
  ) {
    throw new Error("Invalid research observation payload");
  }
  for (const metric of observation.evidence_metrics) {
    if (metric.value != null && !Number.isFinite(Number(metric.value))) {
      throw new Error(`Invalid research metric value: ${metric.metric_code}`);
    }
  }
}

export function assertResearchSnapshot(
  payload: ResearchSnapshotEnvelope,
): ResearchSnapshotEnvelope {
  if (payload.status === "not_built") return payload;
  if (payload.status !== "ready" || !payload.snapshot) {
    throw new Error("Invalid research snapshot payload");
  }
  for (const observation of payload.snapshot.observations) {
    assertObservation(observation);
  }
  return payload;
}

export function formatEvidenceValue(value: string | null, unit: string) {
  return formatFinancialValue({ value, unit, context: "detail" });
}
