import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Providers } from "./providers";

const { diagnoseProviderDraft, getProviderConfigurations, saveProviderDraft } =
  vi.hoisted(() => ({
    diagnoseProviderDraft: vi.fn(),
    getProviderConfigurations: vi.fn(),
    saveProviderDraft: vi.fn(),
  }));

vi.mock("@zhaoniu/api-client", () => ({
  ApiError: class ApiError extends Error {
    constructor(public status: number) {
      super("api error");
    }
  },
  createZhaoniuClient: () => ({
    getProviderConfigurations,
    saveProviderDraft,
    importProviderEnvironment: vi.fn(),
    diagnoseProviderDraft,
    publishProviderDraft: vi.fn(),
    discardProviderDraft: vi.fn(),
    removeProviderCredentials: vi.fn(),
  }),
}));

import { ProviderConfigurationPanel } from "./provider-configuration-panel";

const deepseek = {
  provider: "deepseek",
  environment: "test",
  source: "database",
  row_version: 4,
  credential_state: "encrypted",
  active: {
    revision: 2,
    status: "active",
    configuration_hash: "hash",
    configuration: {
      enabled: true,
      max_concurrency: 2,
      daily_call_limit: 100,
      stock_health: {
        enabled: true,
        models: ["deepseek/deepseek-v4-flash"],
        max_attempts: 1,
        timeout_seconds: 60,
        deadline_seconds: 90,
        max_output_tokens: 1200,
      },
      screen_parser: {
        enabled: false,
        models: ["deepseek/deepseek-v4-flash"],
        max_attempts: 1,
        timeout_seconds: 30,
        deadline_seconds: 75,
        max_output_tokens: 1200,
      },
      research_assistant: {
        enabled: true,
        models: ["deepseek/deepseek-v4-flash"],
        max_attempts: 1,
        timeout_seconds: 60,
        deadline_seconds: 90,
        max_output_tokens: 1200,
      },
    },
    created_at: "2026-08-22T00:00:00Z",
    published_at: "2026-08-22T00:05:00Z",
  },
  draft: null,
  diagnostic_status: "not_run",
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ProviderConfigurationPanel", () => {
  it("keeps credentials write-only and exposes desktop draft actions", async () => {
    getProviderConfigurations.mockResolvedValue({
      items: [
        deepseek,
        {
          provider: "resend",
          environment: "test",
          source: "environment",
          row_version: 0,
          credential_state: "missing",
          active: null,
          draft: null,
          diagnostic_status: "not_run",
        },
      ],
    });
    saveProviderDraft.mockResolvedValue({
      status: "draft_saved",
      configuration: deepseek,
    });

    render(
      <Providers>
        <ProviderConfigurationPanel canManage elevated />
      </Providers>,
    );

    expect(await screen.findByText("服务配置发布台")).toBeInTheDocument();
    expect(screen.getByText(/移动端仅供查看/)).toBeInTheDocument();
    const secret = await screen.findByLabelText("DeepSeek 接口密钥（API Key）");
    expect(secret).toHaveAttribute("placeholder", "已安全配置；留空表示不变");
    expect(secret).toHaveValue("");

    fireEvent.change(secret, { target: { value: "test-secret-value" } });
    fireEvent.click(screen.getByRole("button", { name: "保存草稿" }));
    await waitFor(() => expect(saveProviderDraft).toHaveBeenCalledOnce());
    expect(saveProviderDraft.mock.calls[0][1]).toMatchObject({
      expected_row_version: 4,
      api_key: "test-secret-value",
    });
    expect(
      screen.queryByDisplayValue("test-secret-value"),
    ).not.toBeInTheDocument();
  });

  it("explains step-up after save and prevents duplicate diagnostics", async () => {
    const draft = {
      ...deepseek,
      row_version: 5,
      active: null,
      draft: {
        ...deepseek.active,
        revision: 5,
        status: "draft",
        published_at: null,
      },
    };
    getProviderConfigurations.mockResolvedValue({ items: [draft] });

    const { rerender } = render(
      <Providers>
        <ProviderConfigurationPanel canManage elevated={false} />
      </Providers>,
    );
    expect(
      await screen.findByText(/草稿已保存。请点击页面右上角/),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "诊断草稿" })).toBeDisabled();

    diagnoseProviderDraft.mockImplementation(() => new Promise(() => {}));
    rerender(
      <Providers>
        <ProviderConfigurationPanel canManage elevated />
      </Providers>,
    );
    const diagnose = screen.getByRole("button", { name: "诊断草稿" });
    expect(diagnose).toBeEnabled();
    fireEvent.click(diagnose);
    expect(
      await screen.findByRole("button", { name: "诊断中…" }),
    ).toBeDisabled();
    expect(diagnoseProviderDraft).toHaveBeenCalledOnce();
  });
});
