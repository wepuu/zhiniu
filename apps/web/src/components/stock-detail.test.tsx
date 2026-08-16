import { fireEvent, render, screen } from "@testing-library/react";
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
  issuer_type: "general",
  industry: null,
  latest_price: null,
  change_percent: null,
  latest_trade_date: null,
  source: "akshare",
  collected_at: "2026-08-16T00:00:00Z",
};

const emptyBars = {
  symbol: "600519",
  canonical_symbol: "600519.SH",
  adjust: "none",
  items: [],
  total: 0,
};

const fundamentals = {
  symbol: "600519",
  canonical_symbol: "600519.SH",
  as_of: "2026-08-16T00:00:00Z",
  latest_report_period: "2026-06-30",
  latest_report_published_at: "2026-08-15T00:00:00Z",
  published_at_precision: "date",
  issuer_type: "general",
  provider: "akshare",
  data_version: "fixture",
  metric_definition_version: "fundamentals-v1",
  freshness: "current",
  dimensions: [
    {
      code: "growth",
      display_name: "成长",
      items: [
        {
          code: "revenue_yoy",
          display_name: "营业收入同比",
          dimension: "growth",
          value: "12.5000",
          unit: "percent",
          status: "available",
          period_end: "2026-06-30",
          basis: "ytd",
          source_report_ids: ["00000000-0000-4000-8000-000000000001"],
          detail: null,
        },
      ],
    },
    { code: "profitability", display_name: "盈利能力", items: [] },
    { code: "quality", display_name: "经营质量", items: [] },
    { code: "balance", display_name: "资产负债", items: [] },
    {
      code: "valuation",
      display_name: "估值",
      items: [
        {
          code: "pe_ttm",
          display_name: "市盈率 TTM",
          dimension: "valuation",
          value: "22.50",
          unit: "multiple",
          status: "available",
          period_end: "2026-08-15",
          basis: "point_in_time",
          source_report_ids: [],
          detail: "provider:akshare",
        },
      ],
    },
  ],
};

const periods = {
  symbol: "600519",
  canonical_symbol: "600519.SH",
  items: [],
  total: 0,
};

const valuations = {
  symbol: "600519",
  canonical_symbol: "600519.SH",
  items: [],
  total: 0,
  coverage: { start: null, end: null, sample_count: 0, metric_codes: [] },
};

const observation = {
  id: "00000000-0000-4000-8000-000000000010",
  symbol: "600519.SH",
  dimension: "growth",
  observation_family: "revenue_momentum",
  observation_type: "consecutive_improvement",
  attention_level: "notice",
  movement: "up",
  title: "收入单季增速连续改善",
  summary: "最近三个季度的收入单季同比增速逐季改善。",
  current_period: "2026-06-30",
  comparison_periods: ["2025-12-31", "2026-03-31"],
  rule_id: "growth.revenue_single_quarter_momentum",
  rule_version: "1.0.0",
  observation_key: "fixture-key",
  content_fingerprint: "fixture-fingerprint",
  evidence_metrics: [
    {
      metric_point_id: "00000000-0000-4000-8000-000000000011",
      role: "current",
      metric_code: "revenue_yoy_single_quarter",
      display_name: "营业收入单季同比",
      period_end: "2026-06-30",
      fiscal_period: "H1",
      basis: "single_quarter",
      value: "15.20",
      unit: "percent",
      status: "available",
      input_report_ids: ["00000000-0000-4000-8000-000000000012"],
      input_valuation_ids: [],
      detail: {},
    },
  ],
  evidence_sources: [
    {
      report_id: "00000000-0000-4000-8000-000000000012",
      provider: "akshare",
      provider_record_id: "fixture-report",
      fiscal_period: "H1",
      period_end: "2026-06-30",
      published_at: "2026-08-15T00:00:00Z",
      published_at_precision: "date",
      known_at: "2026-08-16T00:00:00Z",
    },
  ],
  calculation: {
    method: "three_point_consecutive",
    expression: "q1 < q2 < q3",
    change_value: "3.20",
    change_unit: "percentage_point",
  },
  generated_at: "2026-08-16T00:00:00Z",
};

const snapshot = {
  status: "ready",
  snapshot: {
    id: "00000000-0000-4000-8000-000000000020",
    symbol: "600519.SH",
    knowledge_cutoff: "2026-08-16T00:00:00Z",
    data_version: "fixture-data",
    metric_version: "fundamentals-v1",
    rule_set_version: "fixture-rules",
    research_template_version: "fundamental_general:v1",
    snapshot_schema_version: "research-snapshot-v1",
    producer_kind: "deterministic",
    producer_version: "change-engine-v1",
    latest_financial_period: "2026-06-30",
    latest_valuation_date: "2026-08-15",
    input_manifest: {},
    coverage: [],
    observations: [observation],
    generated_at: "2026-08-16T00:00:00Z",
  },
};

function successfulFetch(input: RequestInfo | URL) {
  const url = String(input);
  const body = url.includes("daily-bars")
    ? emptyBars
    : url.includes("research/observations/")
      ? observation
      : url.includes("research/snapshot")
        ? snapshot
        : url.includes("research/fundamentals")
          ? fundamentals
          : url.includes("financials/periods")
            ? periods
            : url.includes("valuations")
              ? valuations
              : stock;
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

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

  it("shows an error action after market API failure", async () => {
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

  it("renders independent desktop and mobile market empty states", async () => {
    vi.stubGlobal("fetch", vi.fn(successfulFetch));
    render(
      <Providers>
        <StockDetail symbol="600519" />
      </Providers>,
    );
    expect(await screen.findAllByText("贵州茅台")).toHaveLength(2);
    const marketTabs = screen.getAllByRole("tab", { name: "行情" });
    fireEvent.click(marketTabs[0]);
    fireEvent.click(marketTabs[1]);
    expect(screen.getAllByText("股票资料已找到，暂无日 K 行情")).toHaveLength(
      2,
    );
  });

  it("opens an evidence trace in both responsive compositions", async () => {
    vi.stubGlobal("fetch", vi.fn(successfulFetch));
    render(
      <Providers>
        <StockDetail symbol="600519" />
      </Providers>,
    );
    expect(await screen.findAllByText("收入单季增速连续改善")).toHaveLength(2);
    const evidenceButtons = screen.getAllByRole("button", {
      name: "查看证据：收入单季增速连续改善",
    });
    fireEvent.click(evidenceButtons[0]);
    expect(
      await screen.findByRole("dialog", { name: "变化证据详情" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByText("three_point_consecutive"),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "关闭" }));
    fireEvent.click(evidenceButtons[1]);
    expect(
      await screen.findByRole("dialog", { name: "变化证据详情" }),
    ).toBeInTheDocument();
  });

  it("renders traceable financial metrics in both compositions", async () => {
    vi.stubGlobal("fetch", vi.fn(successfulFetch));
    render(
      <Providers>
        <StockDetail symbol="600519" />
      </Providers>,
    );
    const financialTabs = await screen.findAllByRole("tab", { name: "财务" });
    fireEvent.click(financialTabs[0]);
    fireEvent.click(financialTabs[1]);
    expect(await screen.findAllByText("营业收入同比")).toHaveLength(2);
    expect(screen.getAllByText("可追溯至 1 个报表版本")).toHaveLength(2);
  });
});
