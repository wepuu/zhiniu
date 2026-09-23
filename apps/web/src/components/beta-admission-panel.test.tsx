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

    expect(await screen.findByText("商业发布仍有阻塞项")).toBeInTheDocument();
    expect(
      screen.getByText("reliability.database_observation"),
    ).toBeInTheDocument();
    expect(screen.getByText(/不会自动修改任何权限/)).toBeInTheDocument();
    expect(screen.getByText(/20260914_0030/)).toBeInTheDocument();
    expect(screen.getByText("pipeline/run/22")).toBeInTheDocument();
  });

  it("separates private evaluation registration from commercial release gates", async () => {
    getBetaAdmission.mockResolvedValue({
      generated_at: "2026-09-23T14:00:00Z",
      environment: "production",
      status: "blocked",
      candidate: null,
      blocking_reasons: ["production_release_not_ready_for_invites"],
      checks: [
        {
          key: "invitation.gates",
          category: "access",
          status: "passed",
          reason_code: null,
          observed_at: null,
          expires_at: null,
          evidence: {
            program_kind: "private_evaluation",
            usage_scope: "development_evaluation",
            commercial_provider_gate_required: false,
          },
        },
        {
          key: "release.invite_activation",
          category: "release",
          status: "pending",
          reason_code: "production_release_not_ready_for_invites",
          observed_at: null,
          expires_at: null,
          evidence: {},
        },
      ],
    });

    render(
      <QueryClientProvider client={new QueryClient()}>
        <BetaAdmissionPanel />
      </QueryClientProvider>,
    );

    expect(
      await screen.findByText("非商用测试邀请注册已就绪"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/商业数据权利只影响未来商业发布/),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("当前数据权利不满足邀请 Beta 使用"),
    ).not.toBeInTheDocument();
  });
});
