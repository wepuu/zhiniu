import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BetaAdmissionPanel } from "./beta-admission-panel";

const { getBetaAdmission } = vi.hoisted(() => ({
  getBetaAdmission: vi.fn(),
}));

vi.mock("@zhaoniu/api-client", () => ({
  createZhaoniuClient: () => ({ getBetaAdmission }),
}));

describe("BetaAdmissionPanel", () => {
  beforeEach(() => {
    getBetaAdmission.mockReset();
  });

  it("shows retained blockers without implying automatic activation", async () => {
    getBetaAdmission.mockResolvedValue({
      generated_at: "2026-09-21T08:00:00Z",
      environment: "production",
      status: "blocked",
      blocking_reasons: ["beta_reliability_observation_stale"],
      checks: [
        {
          key: "reliability.database_observation",
          category: "reliability",
          status: "blocked",
          reason_code: "beta_reliability_observation_stale",
          observed_at: "2026-09-19T08:00:00Z",
          expires_at: "2026-09-20T08:00:00Z",
          evidence: {},
        },
      ],
    });

    render(
      <QueryClientProvider client={new QueryClient()}>
        <BetaAdmissionPanel />
      </QueryClientProvider>,
    );

    expect(await screen.findByText("仍有阻塞项")).toBeInTheDocument();
    expect(
      screen.getByText("reliability.database_observation"),
    ).toBeInTheDocument();
    expect(screen.getByText(/不会自动放开注册/)).toBeInTheDocument();
  });
});
