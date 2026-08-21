import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BetaFeedbackCard } from "./beta-feedback-card";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("BetaFeedbackCard", () => {
  it("submits bounded structured beta feedback", async () => {
    const fetcher = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            id: "00000000-0000-4000-8000-000000000099",
            feature_key: "stock_research",
            category: "data_missing",
            status: "new",
            created_at: "2026-08-21T00:00:00Z",
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
    );
    vi.stubGlobal("fetch", fetcher);
    render(<BetaFeedbackCard />);

    fireEvent.change(screen.getByLabelText("反馈类型"), {
      target: { value: "data_missing" },
    });
    fireEvent.change(screen.getByLabelText("具体情况"), {
      target: { value: "600519 的同行研究页面缺少可追溯的行业归属说明。" },
    });
    fireEvent.click(screen.getByRole("button", { name: "提交反馈" }));

    expect(
      await screen.findByText("反馈已记录，感谢你帮助完善内测体验。"),
    ).toBeInTheDocument();
    const [, init] = fetcher.mock.calls[0] as unknown as [string, RequestInit];
    expect(JSON.parse(String(init.body))).toMatchObject({
      feature_key: "stock_research",
      category: "data_missing",
    });
  });
});
