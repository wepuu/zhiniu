import type { StockReadinessResponse } from "@zhaoniu/api-client";
import { describe, expect, it } from "vitest";

import { canRetryStockPreparation } from "./stock-readiness";

function readiness(
  overallStatus: StockReadinessResponse["overall_status"],
  stageStatus: StockReadinessResponse["stages"][number]["status"],
): StockReadinessResponse {
  return {
    symbol: "300489",
    canonical_symbol: "300489.SZ",
    name: "光智科技",
    overall_status: overallStatus,
    progress: 75,
    updated_at: null,
    latest_price: null,
    latest_trade_date: null,
    stages: [
      {
        key: "ai_research",
        status: stageStatus,
        progress: 0,
        reason_code: stageStatus === "failed" ? "ai_generation_failed" : null,
        updated_at: null,
      },
    ],
  };
}

describe("canRetryStockPreparation", () => {
  it("allows retry when a partial result contains a failed AI stage", () => {
    expect(canRetryStockPreparation(readiness("partial", "failed"))).toBe(true);
  });

  it("does not offer retry for a stable partial result", () => {
    expect(canRetryStockPreparation(readiness("partial", "partial"))).toBe(
      false,
    );
  });
});
