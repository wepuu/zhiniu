import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  getRegistrationStatus: vi.fn(),
  getCurrentLegalDocuments: vi.fn(),
  register: vi.fn(),
  login: vi.fn(),
}));

const navigation = vi.hoisted(() => ({
  params: new URLSearchParams(),
  push: vi.fn(),
  refresh: vi.fn(),
}));

vi.mock("@zhaoniu/api-client", () => ({
  ApiError: class ApiError extends Error {
    constructor(
      public status: number,
      message: string,
    ) {
      super(message);
    }
  },
  createZhaoniuClient: () => api,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: navigation.push,
    refresh: navigation.refresh,
  }),
  useSearchParams: () => navigation.params,
}));

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...props
  }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

import { ApiError } from "@zhaoniu/api-client";
import { AuthCard } from "./auth-card";

const legalDocuments = {
  items: [
    {
      document_type: "terms_of_service",
      version: "2026-08-v1",
      title: "用户协议",
      path: "/legal/terms",
      content_hash: "terms-hash",
      required_at_registration: true,
    },
    {
      document_type: "privacy_policy",
      version: "2026-08-v1",
      title: "隐私政策",
      path: "/legal/privacy",
      content_hash: "privacy-hash",
      required_at_registration: true,
    },
  ],
};

beforeEach(() => {
  navigation.params = new URLSearchParams();
  api.getRegistrationStatus.mockResolvedValue({
    status: "open",
    invitation_required: true,
    email_verification_required: true,
    password_min_length: 15,
  });
  api.getCurrentLegalDocuments.mockResolvedValue(legalDocuments);
  api.register.mockResolvedValue({});
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("AuthCard registration", () => {
  it("stops before form entry when invite registration is closed", async () => {
    api.getRegistrationStatus.mockResolvedValue({
      status: "closed",
      invitation_required: true,
      email_verification_required: true,
      password_min_length: 15,
    });

    render(<AuthCard mode="register" />);

    expect(await screen.findByText("邀请注册当前未开放")).toBeInTheDocument();
    expect(api.getCurrentLegalDocuments).not.toHaveBeenCalled();
    expect(
      screen.queryByRole("button", { name: "创建账户并发送验证邮件" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /前往登录/ })).toHaveAttribute(
      "href",
      "/login",
    );
  });

  it("prefills an emailed invitation and submits the explicit legal versions", async () => {
    navigation.params = new URLSearchParams(
      "invite=inv-abcd-efgh&email=invited%40example.com",
    );

    render(<AuthCard mode="register" />);

    const invite = await screen.findByLabelText("邀请码");
    const email = screen.getByLabelText("邮箱");
    expect(invite).toHaveValue("INV-ABCD-EFGH");
    expect(email).toHaveValue("invited@example.com");
    expect(email).toHaveAttribute("readonly");

    fireEvent.change(screen.getByLabelText("设置密码"), {
      target: { value: "long-password-value" },
    });
    fireEvent.change(screen.getByLabelText("确认密码"), {
      target: { value: "long-password-value" },
    });
    fireEvent.click(screen.getByRole("checkbox", { name: /用户协议/ }));
    fireEvent.click(screen.getByRole("checkbox", { name: /隐私政策/ }));
    fireEvent.click(
      screen.getByRole("button", { name: "创建账户并发送验证邮件" }),
    );

    expect(api.register).toHaveBeenCalledWith(
      "invited@example.com",
      "long-password-value",
      "INV-ABCD-EFGH",
      [
        {
          document_type: "terms_of_service",
          document_version: "2026-08-v1",
        },
        {
          document_type: "privacy_policy",
          document_version: "2026-08-v1",
        },
      ],
    );
    await waitFor(() =>
      expect(navigation.push).toHaveBeenCalledWith("/verify-email"),
    );
  });

  it("explains how to recover from an unavailable invitation", async () => {
    api.register.mockRejectedValue(
      new ApiError(422, "invalid_or_unavailable_invitation"),
    );

    render(<AuthCard mode="register" />);

    await screen.findByLabelText("邀请码");
    fireEvent.change(screen.getByLabelText("邀请码"), {
      target: { value: "INV-ABCD-EFGH" },
    });
    fireEvent.change(screen.getByLabelText("邮箱"), {
      target: { value: "invited@example.com" },
    });
    fireEvent.change(screen.getByLabelText("设置密码"), {
      target: { value: "long-password-value" },
    });
    fireEvent.change(screen.getByLabelText("确认密码"), {
      target: { value: "long-password-value" },
    });
    fireEvent.click(screen.getByRole("checkbox", { name: /用户协议/ }));
    fireEvent.click(screen.getByRole("checkbox", { name: /隐私政策/ }));
    fireEvent.click(
      screen.getByRole("button", { name: "创建账户并发送验证邮件" }),
    );

    expect(
      await screen.findByText(
        "邀请码无效、已过期、已使用，或与当前邮箱不匹配。请从邀请邮件重新打开注册链接。",
      ),
    ).toBeInTheDocument();
  });

  it("fails closed when registration status cannot be loaded", async () => {
    api.getRegistrationStatus.mockRejectedValue(new Error("offline"));

    render(<AuthCard mode="register" />);

    expect(await screen.findByText("暂时无法确认注册状态")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "创建账户并发送验证邮件" }),
    ).not.toBeInTheDocument();
  });
});
