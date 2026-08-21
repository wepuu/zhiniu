import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ResearchCoverageCard } from "./research-coverage-card";

afterEach(cleanup);

describe("ResearchCoverageCard", () => {
  it("explains coverage gaps without turning them into a score", () => {
    render(
      <ResearchCoverageCard
        pending={false}
        error={false}
        coverage={{
          symbol: "600519",
          canonical_symbol: "600519.SH",
          snapshot_id: null,
          knowledge_cutoff: "2026-08-21T00:00:00Z",
          evaluated_at: "2026-08-21T00:00:00Z",
          coverage_schema_version: "research-coverage-v1",
          evaluator_version: "coverage-evaluator-v1",
          policy_version: "coverage-policy-v1",
          limitations: [],
          dimensions: [
            {
              dimension: "financial",
              availability: "partial",
              freshness: "current",
              source_health: "healthy",
              reason_codes: ["financial_insufficient_history"],
              latest_artifact_at: "2026-08-20T00:00:00Z",
            },
            {
              dimension: "fundamental_research",
              availability: "ready",
              freshness: "current",
              source_health: "healthy",
              reason_codes: [],
              latest_artifact_at: "2026-08-20T00:00:00Z",
            },
            {
              dimension: "peer_research",
              availability: "not_built",
              freshness: "unknown",
              source_health: "unknown",
              reason_codes: ["peer_research_not_built"],
              latest_artifact_at: null,
            },
            {
              dimension: "event_radar",
              availability: "ready",
              freshness: "current",
              source_health: "healthy",
              reason_codes: [],
              latest_artifact_at: "2026-08-20T00:00:00Z",
            },
            {
              dimension: "ai_research",
              availability: "disabled",
              freshness: "unknown",
              source_health: "unknown",
              reason_codes: ["ai_disabled"],
              latest_artifact_at: null,
            },
          ],
        }}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "研究覆盖" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("已有财务数据，但历史期数不足。"),
    ).toBeInTheDocument();
    expect(screen.getByText("当前环境未启用 AI 生成。")).toBeInTheDocument();
    expect(screen.queryByText(/健康分|排名|推荐/)).not.toBeInTheDocument();
  });

  it("keeps the existing research usable when coverage cannot load", () => {
    render(<ResearchCoverageCard pending={false} error />);
    expect(screen.getByText("暂时无法核对研究覆盖情况")).toBeInTheDocument();
    expect(
      screen.getByText("下方已有研究内容仍可继续查阅。"),
    ).toBeInTheDocument();
  });
});
