import type { EventRadarEnvelope } from "@zhaoniu/api-client";

const statuses = new Set([
  "ready",
  "no_events",
  "not_built",
  "building",
  "failed",
]);

export function assertEventRadar(value: unknown): EventRadarEnvelope {
  if (!value || typeof value !== "object") {
    throw new Error("事件雷达响应无效");
  }
  const payload = value as Partial<EventRadarEnvelope>;
  if (
    typeof payload.status !== "string" ||
    !statuses.has(payload.status) ||
    !Array.isArray(payload.recent_items) ||
    !Array.isArray(payload.upcoming_items)
  ) {
    throw new Error("事件雷达响应不符合 API Schema");
  }
  return payload as EventRadarEnvelope;
}
