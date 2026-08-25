import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Providers } from "./providers";

const { getProductionReleases } = vi.hoisted(() => ({
  getProductionReleases: vi.fn(),
}));

vi.mock("@zhaoniu/api-client", () => ({
  createZhaoniuClient: () => ({
    getProductionReleases,
    evaluateProductionReleaseGate: vi.fn(),
    approveProductionRelease: vi.fn(),
    recordProductionDeployment: vi.fn(),
  }),
}));

import { ProductionReleasePanel } from "./production-release-panel";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ProductionReleasePanel", () => {
  it("renders immutable evidence and a fail-closed gate without enabling actions", async () => {
    getProductionReleases.mockResolvedValue({
      items: [
        {
          id: "candidate-1",
          target_environment: "production",
          status: "blocked",
          commit_sha: "a".repeat(40),
          migration_head: "20260826_0027",
          api_image_digest: `sha256:${"b".repeat(64)}`,
          web_image_digest: `sha256:${"c".repeat(64)}`,
          configuration_fingerprint: "d".repeat(64),
          sbom_sha256: "e".repeat(64),
          backup_sha256: "f".repeat(64),
          restore_verified_at: "2026-08-25T10:00:00Z",
          quality_gate_status: "passed",
          e2e_status: "passed",
          security_scan_status: "passed",
          created_by_user_id: "creator-1",
          created_at: "2026-08-25T10:00:00Z",
          approvals: [],
          deployment_events: [],
          latest_gates: [
            {
              id: "gate-1",
              gate_type: "closed_deployment",
              status: "blocked",
              rule_set_version: "phase22-production-release-v1",
              result_fingerprint: "1".repeat(64),
              started_at: "2026-08-25T10:01:00Z",
              finished_at: "2026-08-25T10:01:01Z",
              items: [
                {
                  check_key: "registration.closed",
                  category: "access",
                  mandatory: true,
                  status: "failed",
                  reason_code: "registration_not_closed",
                  evidence: { registration_mode: "invite_only" },
                  evidence_fingerprint: "2".repeat(64),
                  checked_at: "2026-08-25T10:01:01Z",
                },
              ],
            },
          ],
        },
      ],
    });

    render(
      <Providers>
        <ProductionReleasePanel
          role="viewer"
          capabilities={["releases.read"]}
          elevated={false}
        />
      </Providers>,
    );

    expect((await screen.findAllByText("门禁阻断")).length).toBeGreaterThan(0);
    expect(screen.getByText(/registration_not_closed/)).toBeInTheDocument();
    expect(screen.getByText(/1 个强制检查未通过/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "评估关闭部署" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "评估邀请激活" })).toBeDisabled();
  });
});
