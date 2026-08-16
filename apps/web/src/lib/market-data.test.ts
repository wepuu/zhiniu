import { describe, expect, it } from "vitest";

import { parseFiniteDecimal, toCandles } from "./market-data";

describe("market data chart adapter", () => {
  it("converts validated decimal strings", () => {
    expect(parseFiniteDecimal("1438.20", "close")).toBe(1438.2);
    expect(
      toCandles([
        {
          trade_date: "2026-08-14",
          adjust_type: "none",
          open: "10.00",
          high: "12.00",
          low: "9.00",
          close: "11.00",
          pre_close: "10.00",
          volume: 100,
          amount: "1100.00",
          pct_change: "10.0000",
          source: "fixture",
          collected_at: "2026-08-15T00:00:00Z",
        },
      ])[0],
    ).toEqual({ time: "2026-08-14", open: 10, high: 12, low: 9, close: 11 });
  });

  it("rejects non-decimal and non-finite values", () => {
    expect(() => parseFiniteDecimal("Infinity", "close")).toThrow();
    expect(() => parseFiniteDecimal("1e309", "close")).toThrow();
  });
});
