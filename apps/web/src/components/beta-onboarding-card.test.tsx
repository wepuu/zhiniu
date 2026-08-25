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
      email_verified: true,
      watchlist_started: true,
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

    expect(await screen.findByText("Invite Beta 上手清单")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "确认完成" }));
    await waitFor(() => expect(updateBetaOnboarding).toHaveBeenCalled());
    expect(updateBetaOnboarding.mock.calls[0]?.[0]).toBe("acknowledge");
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
