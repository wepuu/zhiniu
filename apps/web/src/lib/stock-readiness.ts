import type { StockReadinessResponse } from "@zhaoniu/api-client";

export function canRetryStockPreparation(
  state: StockReadinessResponse,
): boolean {
  return (
    state.overall_status === "failed" ||
    state.overall_status === "paused" ||
    state.stages.some((stage) => stage.status === "failed")
  );
}
