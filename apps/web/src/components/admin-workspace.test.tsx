import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Providers } from "./providers";

const {
  getOperatorContext,
  getOperatorDashboard,
  getAutomationPolicies,
  getAutomationRuns,
  getAutomationRun,
} = vi.hoisted(() => ({
  getOperatorContext: vi.fn(),
  getOperatorDashboard: vi.fn(),
  getAutomationPolicies: vi.fn(),
  getAutomationRuns: vi.fn(),
  getAutomationRun: vi.fn(),
}));

vi.mock("@zhaoniu/api-client", () => ({
  ApiError: class ApiError extends Error {
    constructor(public status: number) {
      super("api error");
    }
  },
  createZhaoniuClient: () => ({
    getOperatorContext,
    getOperatorDashboard,
    getAutomationPolicies,
    getAutomationRuns,
    getAutomationRun,
  }),
}));

import { AdminWorkspace } from "./admin-workspace";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("AdminWorkspace", () => {
  it("renders the operations shell and keeps mobile actions read-only", async () => {
    getOperatorContext.mockResolvedValue({
      role: "viewer",
      capabilities: ["dashboard.read"],
      elevated: false,
      elevated_until: null,
    });
    getOperatorDashboard.mockResolvedValue({
      generated_at: "2026-08-21T10:00:00Z",
      environment: "test",
      users: { total: 7 },
      access: { advanced_active: 1 },
      ai: { enabled: false },
      email: { provider: "disabled" },
      coverage: {},
      system: { migration_head: "20260821_0019", blocking_reasons: [] },
    });
    render(
      <Providers>
        <AdminWorkspace />
      </Providers>,
    );

    expect((await screen.findAllByText("知牛运营台")).length).toBeGreaterThan(
      0,
    );
    expect(screen.getByText(/移动端用于安全查看/)).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByText("20260821_0019")).toBeInTheDocument(),
    );
  });

  it("renders the automation policy and run history in the existing console", async () => {
    getOperatorContext.mockResolvedValue({
      role: "viewer",
      capabilities: ["dashboard.read", "automation.read"],
      elevated: false,
      elevated_until: null,
    });
    getOperatorDashboard.mockResolvedValue({
      generated_at: "2026-08-21T10:00:00Z",
      environment: "test",
      users: { total: 7 },
      access: {},
      ai: {},
      email: {},
      coverage: {},
      system: { migration_head: "20260821_0019" },
    });
    getAutomationPolicies.mockResolvedValue({
      items: [
        {
          id: "policy-1",
          policy_key: "priority_daily_refresh",
          display_name: "优先股票池每日研究刷新",
          enabled: false,
          hard_disabled: true,
          revision: 1,
          configuration_hash: "1234567890abcdef",
          configuration: {
            timezone: "Asia/Shanghai",
            daily_time: "19:30",
            max_universe_size: 100,
            financial_reporting_interval_hours: 72,
            financial_normal_interval_hours: 168,
            event_pipeline_enabled: true,
            peer_research_enabled: true,
            ai_research_enabled: false,
          },
          next_due_at: null,
          last_evaluated_at: null,
          updated_at: "2026-08-21T10:00:00Z",
        },
      ],
    });
    getAutomationRuns.mockResolvedValue({ items: [], total: 0 });
    render(
      <Providers>
        <AdminWorkspace />
      </Providers>,
    );

    fireEvent.click(await screen.findByRole("button", { name: "自动任务" }));
    expect(await screen.findByText("自动研究任务")).toBeInTheDocument();
    expect(
      await screen.findByText("环境级自动化开关已关闭"),
    ).toBeInTheDocument();
    expect(
      await screen.findByText("优先股票池每日研究刷新"),
    ).toBeInTheDocument();
    expect(await screen.findByText("尚无自动化运行记录")).toBeInTheDocument();
    expect(getAutomationRun).not.toHaveBeenCalled();
  });
});
