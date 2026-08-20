import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  requestPasswordReset: vi.fn().mockResolvedValue({ status: "accepted" }),
  confirmPasswordReset: vi.fn(),
  resendEmailVerification: vi.fn(),
  verifyEmail: vi.fn(),
}));

vi.mock("@zhaoniu/api-client", () => ({
  ApiError: class ApiError extends Error {
    constructor(public status: number) {
      super(String(status));
    }
  },
  createZhaoniuClient: () => api,
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
  }: {
    children: React.ReactNode;
    href: string;
  }) => <a href={href}>{children}</a>,
}));

import { AccountRecoveryCard } from "./account-recovery-card";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("AccountRecoveryCard", () => {
  it("uses the same success message for a password reset request", async () => {
    render(<AccountRecoveryCard mode="forgot" />);
    fireEvent.change(screen.getByLabelText("注册邮箱"), {
      target: { value: "unknown@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "发送重置邮件" }));

    expect(api.requestPasswordReset).toHaveBeenCalledWith(
      "unknown@example.com",
    );
    expect(
      await screen.findByText(
        "如果该邮箱对应账户存在，我们将发送密码重置邮件。",
      ),
    ).toBeInTheDocument();
  });
});
