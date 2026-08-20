import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  getAccess: vi.fn(),
  activateAccess: vi.fn(),
}));

vi.mock("@zhaoniu/api-client", () => ({
  ApiError: class ApiError extends Error {
    constructor(public status: number) {
      super(String(status));
    }
  },
  createZhaoniuClient: () => api,
}));

import { AdvancedAccessCard } from "./advanced-access-card";

beforeEach(() => {
  api.getAccess.mockResolvedValue({
    access_status: "basic",
    features: ["watchlist"],
    limits: { watchlist_groups: 1 },
    valid_until: null,
    activation_available: true,
    support_contact_url: "https://support.example.com",
  });
  api.activateAccess.mockResolvedValue({
    access_status: "enabled",
    features: ["watchlist", "natural_language_screening"],
    limits: { watchlist_groups: 5 },
    valid_until: "2026-09-21T00:00:00Z",
    activation_available: true,
    support_contact_url: "https://support.example.com",
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("AdvancedAccessCard", () => {
  it("loads basic access and activates a supplied code", async () => {
    render(<AdvancedAccessCard />);

    expect(await screen.findByText("未开通")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("激活码"), {
      target: { value: "ACT-TEST-CODE" },
    });
    fireEvent.click(screen.getByRole("button", { name: "激活高级功能" }));

    expect(api.activateAccess).toHaveBeenCalledWith("ACT-TEST-CODE");
    expect(await screen.findByText("高级功能已开通。")).toBeInTheDocument();
    expect(screen.getByText("有效期至")).toBeInTheDocument();
  });
});
