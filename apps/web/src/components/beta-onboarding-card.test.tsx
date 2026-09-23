import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Providers } from "./providers";

const { getBetaOnboarding, updateBetaOnboarding } = vi.hoisted(() => ({
  getBetaOnboarding: vi.fn(),
  updateBetaOnboarding: vi.fn(),
}));

vi.mock("@zhaoniu/api-client", () => ({
  createZhaoniuClient: () => ({ getBetaOnboarding, updateBetaOnboarding }),
}));

import { BetaOnboardingCard } from "./beta-onboarding-card";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("BetaOnboardingCard", () => {
  it("renders persisted milestones and acknowledges only after completion", async () => {
    const completed = {
      enrolled: true,
      program_kind: "private_evaluation",
      usage_scope: "development_evaluation",
      notice_version: "private-evaluation-v1",
      email_verified: true,
      watchlist_started: true,
      first_value_symbol: "600519.SH",
      market_ready: true,
      deterministic_ready: true,
      ai_terminal: true,
      feedback_submitted: true,
      acknowledged: false,
      dismissed: false,
    };
    getBetaOnboarding.mockResolvedValue(completed);
    updateBetaOnboarding.mockResolvedValue({
      ...completed,
      acknowledged: true,
    });
    render(
      <Providers>
        <BetaOnboardingCard />
      </Providers>,
    );

    expect(
      await screen.findByText("从受邀注册走到可核验的研究结果"),
    ).toBeInTheDocument();
    expect(screen.getByText("私有非商用评估")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "确认完成体验路径" }));
    await waitFor(() => expect(updateBetaOnboarding).toHaveBeenCalled());
    expect(updateBetaOnboarding.mock.calls[0]?.[0]).toBe("acknowledge");
  });

  it("keeps completion disabled while research has not reached a terminal state", async () => {
    getBetaOnboarding.mockResolvedValue({
      enrolled: true,
      program_kind: "private_evaluation",
      email_verified: true,
      watchlist_started: true,
      market_ready: true,
      deterministic_ready: false,
      ai_terminal: false,
      feedback_submitted: false,
      acknowledged: false,
      dismissed: false,
    });

    render(
      <Providers>
        <BetaOnboardingCard />
      </Providers>,
    );

    expect(
      await screen.findByRole("button", { name: "确认完成体验路径" }),
    ).toBeDisabled();
    expect(screen.getByText("正在准备研究数据")).toBeInTheDocument();
  });

  it("does not expose onboarding to users outside a cohort", async () => {
    getBetaOnboarding.mockResolvedValue({ enrolled: false });
    const { container } = render(
      <Providers>
        <BetaOnboardingCard />
      </Providers>,
    );
    await waitFor(() => expect(getBetaOnboarding).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});
