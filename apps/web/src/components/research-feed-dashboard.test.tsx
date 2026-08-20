import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { getResearchFeed, getResearchCoverage } = vi.hoisted(() => ({
  getResearchFeed: vi.fn(),
  getResearchCoverage: vi.fn(),
}));

vi.mock("@zhaoniu/api-client", () => {
  class ApiError extends Error {
    constructor(public status: number) {
      super(`status ${status}`);
    }
  }
  return {
    ApiError,
    createZhaoniuClient: () => ({ getResearchFeed, getResearchCoverage }),
  };
});

import { ApiError } from "@zhaoniu/api-client";
import { ResearchFeedDashboard } from "./research-feed-dashboard";

function renderDashboard() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <ResearchFeedDashboard />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  getResearchFeed.mockResolvedValue({
    query_cutoff: "2026-08-20T10:00:00Z",
    today: { items: [], total: 0 },
    recent: {
      total: 1,
      items: [
        {
          id: "00000000-0000-4000-8000-000000000001",
          symbol: "600519.SH",
          stock_name: "贵州茅台",
          source_kind: "fundamental",
          signal_family: "revenue_yoy",
          signal_type: "change",
          attention_level: "notice",
          known_at: "2026-08-19T10:00:00Z",
          effective_on: "2026-06-30",
          title: "营业收入变化需要继续核对",
          summary: "该观察来自确定性研究快照。",
          display_payload: {},
          evidence_path: "/stock/600519.SH",
          ai_status: "disabled",
        },
      ],
    },
    next_cursor: null,
  });
  getResearchCoverage.mockResolvedValue({
    total: 1,
    items: [
      {
        symbol: "600519.SH",
        stock_name: "贵州茅台",
        coverage: {
          fundamental: "ready",
          peer: "insufficient_data",
          corporate_event: "ready",
          ai: "disabled",
        },
      },
    ],
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ResearchFeedDashboard", () => {
  it("renders separated today and 14-day sections from the API schema", async () => {
    renderDashboard();
    expect(
      await screen.findByRole(
        "heading",
        {
          name: "贵州茅台 · 营业收入变化需要继续核对",
        },
        { timeout: 5000 },
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "今日新增00" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "最近 14 天01" }),
    ).toBeInTheDocument();
    expect(screen.getByText("研究覆盖")).toBeInTheDocument();
  });

  it("renders an explicit login state for anonymous users", async () => {
    getResearchFeed.mockRejectedValueOnce(new ApiError(401, "Unauthorized"));
    renderDashboard();
    expect(
      await screen.findByText("登录后查看你的自选研究"),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "登录账户" })).toHaveAttribute(
      "href",
      "/login",
    );
  });
});
