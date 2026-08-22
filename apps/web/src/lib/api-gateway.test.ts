import { createZhaoniuClient } from "@zhaoniu/api-client";
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
});
