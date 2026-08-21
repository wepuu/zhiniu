import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Providers } from "./providers";

const { getOperatorContext, getOperatorDashboard } = vi.hoisted(() => ({
  getOperatorContext: vi.fn(),
  getOperatorDashboard: vi.fn(),
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
      system: { migration_head: "20260821_0018", blocking_reasons: [] },
    });
    render(
      <Providers>
        <AdminWorkspace />
      </Providers>,
    );

    expect((await screen.findAllByText("知牛运营台")).length).toBeGreaterThan(0);
    expect(screen.getByText(/移动端用于安全查看/)).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByText("20260821_0018")).toBeInTheDocument(),
    );
  });
});
