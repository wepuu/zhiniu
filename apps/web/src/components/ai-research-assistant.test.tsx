import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  getAIExplanationQuestions: vi.fn(),
  getAIExplanationRequest: vi.fn(),
  createAIExplanationRequest: vi.fn(),
  retryAIExplanationRequest: vi.fn(),
  getResearchObservation: vi.fn(),
}));

vi.mock("@zhaoniu/api-client", () => ({
  createZhaoniuClient: () => api,
}));

import { AIResearchPanel } from "./ai-research-panel";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("AI research assistant", () => {
  it("uses a fixed-question segmented experience and shows the disabled gate", async () => {
    api.getAIExplanationQuestions.mockResolvedValue({
      symbol: "600519.SH",
      enabled: false,
      access: "disabled",
      remaining_today: 0,
      daily_limit: 10,
      support_contact_url: null,
      questions: [],
    });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <AIResearchPanel
          symbol="600519"
          envelope={{
            status: "disabled",
            reason: "llm_disabled",
            freshness: null,
            output: null,
          }}
        />
      </QueryClientProvider>,
    );

    expect(screen.getByRole("tab", { name: "股票体检" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "研究助手" }));

    expect(await screen.findByText("研究助手暂未启用")).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(api.getAIExplanationQuestions).toHaveBeenCalledWith("600519");
  });

  it("renders the fixed question catalog in the compact mobile composition", async () => {
    api.getAIExplanationQuestions.mockResolvedValue({
      symbol: "600519.SH",
      enabled: true,
      access: "available",
      remaining_today: 10,
      daily_limit: 10,
      support_contact_url: null,
      questions: [
        {
          key: "recent_research_changes",
          label: "最近有哪些研究变化？",
          description: "综合最新证据。",
          coverage: "available",
        },
      ],
    });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <AIResearchPanel
          symbol="600519"
          compact
          envelope={{
            status: "disabled",
            reason: "llm_disabled",
            freshness: null,
            output: null,
          }}
        />
      </QueryClientProvider>,
    );

    fireEvent.click(screen.getByRole("tab", { name: "研究助手" }));
    const question = await screen.findByText("最近有哪些研究变化？");
    expect(question.closest("button")).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });
});
