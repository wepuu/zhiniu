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
      candidate: {
        id: "11111111-1111-4111-8111-111111111111",
        status: "deployed_observing",
        target_environment: "production",
        commit_sha: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        migration_head: "20260914_0030",
        api_image_digest: `sha256:${"b".repeat(64)}`,
        web_image_digest: `sha256:${"c".repeat(64)}`,
        configuration_fingerprint: "d".repeat(64),
        created_at: "2026-09-19T08:00:00Z",
        invite_gate_run_id: null,
        invite_gate_result_fingerprint: null,
        invite_gate_finished_at: null,
        deployment_ref: "pipeline/run/22",
      },
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
    expect(screen.getByText(/20260914_0030/)).toBeInTheDocument();
    expect(screen.getByText("pipeline/run/22")).toBeInTheDocument();
  });
});
