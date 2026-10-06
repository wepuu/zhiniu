import type { StockReadinessResponse } from "@zhaoniu/api-client";
import { describe, expect, it } from "vitest";

import {
  canRetryStockPreparation,
  formatReadinessTimestamp,
  readinessActionLabel,
  readinessReasonLabel,
} from "./stock-readiness";

function readiness(
  overallStatus: StockReadinessResponse["overall_status"],
  stageStatus: StockReadinessResponse["stages"][number]["status"],
): StockReadinessResponse {
  return {
    symbol: "300489",
    canonical_symbol: "300489.SZ",
    name: "光智科技",
    overall_status: overallStatus,
    next_action:
      stageStatus === "failed"
        ? "retry"
        : overallStatus === "failed"
          ? "retry"
          : overallStatus === "paused"
            ? "enable_preparation"
            : overallStatus === "partial" || overallStatus === "ready"
              ? "view"
              : "wait",
    blocking_reason_code:
      stageStatus === "failed" ? "ai_generation_failed" : null,
    progress: 75,
    updated_at: null,
    latest_price: null,
    latest_trade_date: null,
    market_freshness: "unknown",
    expected_trade_date: null,
    calendar_status: "unknown",
    calendar_checked_at: null,
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

  it("does not offer retry while preparation is paused", () => {
    expect(canRetryStockPreparation(readiness("paused", "paused"))).toBe(false);
  });
});

describe("formatReadinessTimestamp", () => {
  it("formats a retained UTC timestamp in China time", () => {
    const result = formatReadinessTimestamp("2026-09-25T11:30:00Z");

    expect(result).toContain("9");
    expect(result).toContain("25");
    expect(result).toContain("19");
    expect(result).toContain("30");
  });

  it("does not render missing or invalid timestamps", () => {
    expect(formatReadinessTimestamp(null)).toBeNull();
    expect(formatReadinessTimestamp("not-a-date")).toBeNull();
  });
});

describe("readiness guidance", () => {
  it("uses the server action instead of guessing from progress", () => {
    const state = readiness("partial", "partial");

    expect(readinessActionLabel(state)).toBe("可查看已完成研究");
    expect(readinessReasonLabel("provider_connection_failed")).toContain(
      "数据源暂时不可用",
    );
  });
});
