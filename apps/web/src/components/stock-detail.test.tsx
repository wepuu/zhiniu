import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Providers } from "./providers";
import { StockDetail } from "./stock-detail";

const stock = {
  symbol: "600519",
  canonical_symbol: "600519.SH",
  name: "贵州茅台",
  exchange: "SSE",
  board: "main",
  asset_type: "stock",
  list_date: null,
  status: "listed",
  industry: null,
  latest_price: null,
  change_percent: null,
  latest_trade_date: null,
  source: "akshare",
  collected_at: "2026-08-16T00:00:00Z",
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("StockDetail states and responsive compositions", () => {
  it("shows a purposeful loading state", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => undefined)),
    );
    render(
      <Providers>
        <StockDetail symbol="600519" />
      </Providers>,
    );
    expect(screen.getByText("正在读取真实行情")).toBeInTheDocument();
  });

  it("shows an error action after API failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(null, { status: 503 })),
    );
    render(
      <Providers>
        <StockDetail symbol="600519" />
      </Providers>,
    );
    expect(
      await screen.findByText("无法读取这只股票", {}, { timeout: 3000 }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "重新加载" }),
    ).toBeInTheDocument();
  });

  it("renders the same empty real-data state in desktop and mobile compositions", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        const body = url.includes("daily-bars")
          ? {
              symbol: "600519",
              canonical_symbol: "600519.SH",
              adjust: "none",
              items: [],
              total: 0,
            }
          : stock;
        return new Response(JSON.stringify(body), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }),
    );
    render(
      <Providers>
        <StockDetail symbol="600519" />
      </Providers>,
    );
    expect(await screen.findAllByText("贵州茅台")).toHaveLength(2);
    expect(screen.getAllByText("股票资料已找到，尚无日 K 行情")).toHaveLength(
      2,
    );
  });
});
