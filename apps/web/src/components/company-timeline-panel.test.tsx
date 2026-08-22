import type { CompanyTimelineEnvelope } from "@zhaoniu/api-client";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CompanyTimelinePanel } from "./company-timeline-panel";

const ready = {
  status: "ready",
  symbol: "600519",
  canonical_symbol: "600519.SH",
  query_cutoff: "2026-08-22T08:00:00Z",
  latest_known_at: "2026-08-21T08:00:00Z",
  summary: {
    recent_30d_total: 1,
    fundamental_count: 1,
    peer_count: 0,
    corporate_event_count: 0,
    important_count: 0,
    upcoming_count: 0,
  },
  coverage: {
    fundamental: "ready",
    peer: "ready",
    corporate_event: "ready",
  },
  upcoming_events: [],
  items: [
    {
      id: "00000000-0000-4000-8000-000000000001",
      symbol: "600519",
      source_kind: "fundamental",
      signal_family: "profitability",
      signal_type: "metric_changed",
      attention_level: "notice",
      known_at: "2026-08-21T08:00:00Z",
      effective_on: "2026-06-30",
      title: "盈利能力指标发生变化",
      summary: "该变化来自已披露财务数据，需要结合报告口径继续核对。",
      display_values: [],
      source_artifact: {
        type: "fundamental",
        id: "00000000-0000-4000-8000-000000000002",
        evidence_path: "/api/v1/stocks/600519/research/observations/2",
      },
    },
  ],
} as CompanyTimelineEnvelope;

describe("CompanyTimelinePanel", () => {
  it("renders known/effective time separately and routes to evidence", () => {
    const navigate = vi.fn();
    render(
      <CompanyTimelinePanel
        symbol="600519"
        envelope={ready}
        pending={false}
        error={false}
        onRetry={vi.fn()}
        onNavigate={navigate}
      />,
    );
    expect(
      screen.getByRole("heading", { name: "研究时间线" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/发生或计划时间 2026-06-30/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /查看依据/ }));
    expect(navigate).toHaveBeenCalledWith("fundamental");
  });

  it("renders an honest not-built state", () => {
    render(
      <CompanyTimelinePanel
        symbol="600519"
        envelope={{ ...ready, status: "not_built", items: [] }}
        pending={false}
        error={false}
        onRetry={vi.fn()}
        onNavigate={vi.fn()}
        compact
      />,
    );
    expect(screen.getByText("研究时间线尚未形成")).toBeInTheDocument();
  });
});
