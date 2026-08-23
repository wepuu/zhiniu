import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
const api = vi.hoisted(() => ({
  getComparisonCatalog: vi.fn(),
  createComparison: vi.fn(),
  getComparison: vi.fn(),
  saveComparison: vi.fn(),
  listComparisons: vi.fn(),
  listSavedComparisons: vi.fn(),
}));

vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@zhaoniu/api-client", () => ({
  ApiError: class ApiError extends Error {
    constructor(public status: number) {
      super(String(status));
    }
  },
  createZhaoniuClient: () => api,
}));

import { ComparisonLauncher, ComparisonResult } from "./comparison-workspace";

function renderWithQuery(node: ReactNode) {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      {node}
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  api.getComparisonCatalog.mockResolvedValue({
    dimensions: ["成长与规模", "盈利能力"],
    ai_available: true,
    saved_limit: 10,
  });
  api.listComparisons.mockResolvedValue({ items: [] });
  api.listSavedComparisons.mockResolvedValue({ items: [], limit: 10 });
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ComparisonWorkspace", () => {
  it("creates a comparison from two symbols", async () => {
    api.createComparison.mockResolvedValue({
      id: "request-1",
      status: "pending",
    });
    renderWithQuery(<ComparisonLauncher initialSymbol="600519" />);
    await screen.findByText("AI 解读：可用（事实先行）");
    fireEvent.change(screen.getByLabelText("公司 B"), {
      target: { value: "300750" },
    });
    fireEvent.click(screen.getByRole("button", { name: "生成对比研究" }));
    await waitFor(() => expect(api.createComparison).toHaveBeenCalled());
    expect(api.createComparison.mock.calls[0][0]).toMatchObject({
      left_symbol: "600519",
      right_symbol: "300750",
      include_ai: true,
    });
  });

  it("renders deterministic values and an explicit disabled AI state", async () => {
    api.getComparison.mockResolvedValue({
      id: "request-1",
      left_symbol: "600519.SH",
      right_symbol: "300750.SZ",
      status: "partial",
      include_ai: true,
      ai_status: "disabled",
      requested_cutoff: "2026-08-23T00:00:00Z",
      created_at: "2026-08-23T00:00:00Z",
      evidence: [],
      snapshot: {
        schema_version: "company-comparison-v1",
        profile_version: "standard-v1",
        knowledge_cutoff: "2026-08-23T00:00:00Z",
        left: {
          symbol: "600519.SH",
          ticker: "600519",
          name: "贵州茅台",
          exchange: "SH",
          board: "main",
          industry_name: "白酒",
        },
        right: {
          symbol: "300750.SZ",
          ticker: "300750",
          name: "宁德时代",
          exchange: "SZ",
          board: "chinext",
          industry_name: "电池",
        },
        same_industry: false,
        metrics: [
          {
            code: "roe",
            label: "净资产收益率",
            dimension: "盈利能力",
            comparability: "comparable",
            left: {
              value: "31.2",
              unit: "percent",
              status: "available",
              period_end: "2025-12-31",
              basis: "fy",
            },
            right: {
              value: "24.1",
              unit: "percent",
              status: "available",
              period_end: "2025-12-31",
              basis: "fy",
            },
          },
        ],
        recent_signals: [],
        limitations: ["两家公司不在同一可验证行业口径。"],
      },
    });
    renderWithQuery(<ComparisonResult requestId="request-1" />);
    expect(await screen.findByText("贵州茅台 / 宁德时代")).toBeInTheDocument();
    expect(screen.getByText("AI 对比解读当前未启用")).toBeInTheDocument();
    expect(screen.getAllByText("净资产收益率").length).toBeGreaterThan(0);
  });
});
