import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  getScreenCatalog: vi.fn(),
  getScreenCoverage: vi.fn(),
  getWatchlists: vi.fn(),
  validateScreen: vi.fn(),
  createScreenExecution: vi.fn(),
  getScreenExecution: vi.fn(),
  getScreenResults: vi.fn(),
  addWatchlistItem: vi.fn(),
}));

vi.mock("next/navigation", () => ({ usePathname: () => "/screens" }));
vi.mock("@zhaoniu/api-client", () => ({
  ApiError: class ApiError extends Error {
    constructor(public status: number) {
      super(String(status));
    }
  },
  createZhaoniuClient: () => api,
}));

import { ScreeningWorkspace } from "./screening-workspace";

function renderWorkspace() {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: {
            queries: { retry: false },
            mutations: { retry: false },
          },
        })
      }
    >
      <ScreeningWorkspace />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  api.getScreenCatalog.mockResolvedValue({
    dsl_version: "screen-query-v1",
    metrics: [
      {
        code: "roe_avg_equity_fy",
        display_name: "年度平均权益 ROE",
        dimension: "profitability",
        unit: "%",
        source_kind: "metric",
        selectors: ["latest_available", "latest_fy"],
        operators: ["gt", "gte", "lt", "lte", "between"],
      },
    ],
    peer_metric_codes: [],
    industries: [],
    event_families: [],
    limitations: [],
  });
  api.getScreenCoverage.mockResolvedValue({
    status: "partial_coverage",
    snapshot_id: "00000000-0000-4000-8000-000000000010",
    knowledge_cutoff: "2026-08-20T10:00:00Z",
    universe_count: 2,
    eligible_count: 2,
    excluded_count: 0,
    fact_counts: { metric: 2 },
    commercial_use_status: "development_evaluation_only",
    limitations: [],
  });
  api.getWatchlists.mockResolvedValue([
    { id: "list-1", name: "我的自选", item_count: 0, items: [] },
  ]);
  api.validateScreen.mockResolvedValue({
    valid: true,
    canonical_query: {
      dsl_version: "screen-query-v1",
      filters: [
        {
          kind: "metric",
          metric_code: "roe_avg_equity_fy",
          selector: "latest_fy",
          operator: "gte",
          value: "15",
        },
      ],
      sort: { field: "symbol", direction: "asc" },
    },
    query_hash: "hash",
    issues: [],
  });
  api.createScreenExecution.mockResolvedValue({
    id: "execution-1",
    status: "succeeded",
  });
  api.getScreenExecution.mockResolvedValue({
    id: "execution-1",
    status: "succeeded",
    evaluated_count: 2,
  });
  api.getScreenResults.mockResolvedValue({
    execution_id: "execution-1",
    query_cutoff: "2026-08-20T10:00:00Z",
    total: 1,
    next_cursor: null,
    items: [
      {
        symbol: "600519.SH",
        stock_name: "贵州茅台",
        exchange: "SSE",
        industry_name: "白酒",
        ordinal: 1,
        is_in_watchlist: false,
        research_path: "/stock/600519.SH",
        matched_conditions: [
          {
            criterion_key: "metric:roe_avg_equity_fy",
            label: "年度平均权益 ROE",
            value: "31.20",
            unit: "%",
            effective_on: "2025-12-31",
            evidence_type: "fundamental_metric_point",
            evidence_id: "00000000-0000-4000-8000-000000000011",
          },
        ],
      },
    ],
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ScreeningWorkspace", () => {
  it("renders snapshot coverage and an explainable result", async () => {
    renderWorkspace();
    expect(await screen.findByText("部分覆盖")).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "运行筛选" })[0]!);
    expect(
      await screen.findByRole("heading", { name: "贵州茅台" }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("年度平均权益 ROE").length).toBeGreaterThan(0);
    expect(screen.getByText("31.2 %")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /查看研究证据/ })).toHaveAttribute(
      "href",
      "/stock/600519.SH",
    );
  });

  it("shows a deterministic not-built state", async () => {
    api.getScreenCoverage.mockResolvedValueOnce({
      status: "not_built",
      universe_count: 0,
      eligible_count: 0,
      excluded_count: 0,
      fact_counts: {},
      commercial_use_status: "development_evaluation_only",
      limitations: [],
    });
    renderWorkspace();
    expect(await screen.findByText(/筛选快照尚未生成/)).toBeInTheDocument();
  });
});
