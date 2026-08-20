import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  getSavedScreens: vi.fn(),
  createScreenExecution: vi.fn(),
  getScreenExecution: vi.fn(),
  getScreenResults: vi.fn(),
  deleteSavedScreen: vi.fn(),
}));

vi.mock("next/navigation", () => ({ usePathname: () => "/saved-screens" }));
vi.mock("@zhaoniu/api-client", () => ({
  ApiError: class ApiError extends Error {
    constructor(public status: number) {
      super(String(status));
    }
  },
  createZhaoniuClient: () => api,
}));

import { SavedScreensWorkspace } from "./saved-screens-workspace";

function renderWorkspace() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <SavedScreensWorkspace />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  api.getSavedScreens.mockResolvedValue({
    total: 1,
    items: [
      {
        id: "saved-1",
        name: "高毛利观察",
        query_hash: "hash",
        source_kind: "natural_language",
        original_text: "毛利率不低于 30%",
        compatibility: "compatible",
        created_at: "2026-08-20T10:00:00Z",
        updated_at: "2026-08-20T10:00:00Z",
        query: {
          dsl_version: "screen-query-v1",
          filters: [
            {
              kind: "metric",
              metric_code: "gross_margin",
              selector: "latest_available",
              operator: "gte",
              value: "30",
            },
          ],
          sort: { field: "symbol", direction: "asc" },
        },
      },
    ],
  });
  api.createScreenExecution.mockResolvedValue({
    id: "execution-1",
    status: "pending",
  });
  api.getScreenExecution.mockResolvedValue({
    id: "execution-1",
    status: "succeeded",
    result_count: 1,
  });
  api.getScreenResults.mockResolvedValue({
    total: 1,
    items: [
      {
        symbol: "600519.SH",
        stock_name: "贵州茅台",
        research_path: "/stock/600519.SH",
      },
    ],
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("SavedScreensWorkspace", () => {
  it("renders compatibility and reruns a saved deterministic screen", async () => {
    renderWorkspace();
    expect(
      await screen.findByRole(
        "heading",
        { name: "高毛利观察" },
        { timeout: 5000 },
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("可直接运行")).toBeInTheDocument();
    expect(screen.getByText("AI 解析原文（由你保存）")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "运行" }));
    expect(
      await screen.findByText("匹配 1 家", {}, { timeout: 5000 }),
    ).toBeInTheDocument();
    expect(
      await screen.findByText("贵州茅台", {}, { timeout: 5000 }),
    ).toBeInTheDocument();
  });
});
