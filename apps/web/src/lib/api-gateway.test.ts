import { ApiError, createZhaoniuClient } from "@zhaoniu/api-client";
import { afterEach, describe, expect, it, vi } from "vitest";

describe("browser API gateway", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("keeps browser requests on the embedded-browser-safe same-origin path", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ symbol: "600519" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetcher);

    await createZhaoniuClient().getStock("600519");

    expect(fetcher).toHaveBeenCalledWith(
      "/gateway/api/v1/stocks/600519",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("routes authenticated explanation catalogs through the same-origin gateway", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ questions: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetcher);

    await createZhaoniuClient().getAIExplanationQuestions("600519");

    expect(fetcher).toHaveBeenCalledWith(
      "/gateway/api/v1/stocks/600519/ai/questions",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("preserves API detail codes for actionable mutation errors", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ detail: "default_watchlist_cannot_be_deleted" }),
        {
          status: 409,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetcher);

    await expect(
      createZhaoniuClient().deleteWatchlist("watchlist-id"),
    ).rejects.toEqual(
      expect.objectContaining<ApiError>({
        status: 409,
        name: "ApiError",
        message: "default_watchlist_cannot_be_deleted",
      }),
    );
  });
});
