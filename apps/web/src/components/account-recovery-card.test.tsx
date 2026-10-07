import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  requestPasswordReset: vi.fn().mockResolvedValue({ status: "accepted" }),
  confirmPasswordReset: vi.fn(),
  resendEmailVerification: vi.fn(),
  verifyEmail: vi.fn(),
  verifyEmailCode: vi.fn(),
}));

const navigation = vi.hoisted(() => ({
  params: new URLSearchParams(),
}));

vi.mock("@zhaoniu/api-client", () => ({
  ApiError: class ApiError extends Error {
    constructor(
      public status: number,
      message = String(status),
    ) {
      super(message);
    }
  },
  createZhaoniuClient: () => api,
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => navigation.params,
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

beforeEach(() => {
  navigation.params = new URLSearchParams();
  api.verifyEmailCode.mockResolvedValue({ status: "verified" });
  api.resendEmailVerification.mockResolvedValue({ status: "sent" });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("AccountRecoveryCard", () => {
  it("accepts and verifies a six-digit registration code", async () => {
    navigation.params = new URLSearchParams("registration=1");
    render(<AccountRecoveryCard mode="verify" />);

    expect(
      screen.getByText("验证码已发送到注册邮箱。输入六位数字即可完成注册。"),
    ).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("邮箱验证码"), {
      target: { value: "123456" },
    });
    expect(screen.getByLabelText("邮箱验证码")).toHaveValue("123456");

    fireEvent.click(screen.getByRole("button", { name: "验证并完成注册" }));

    await waitFor(() =>
      expect(api.verifyEmailCode).toHaveBeenCalledWith("123456"),
    );
    expect(
      await screen.findByText("注册完成，邮箱验证成功。"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "进入研究工作台" }),
    ).toHaveAttribute("href", "/watchlist");
  });

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
