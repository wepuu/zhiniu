import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Providers } from "./providers";

vi.mock("./stock-chart", () => ({
  StockChart: () => <div data-testid="stock-chart" />,
}));

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

const marketBars = {
  ...emptyBars,
  items: [
    {
      trade_date: "2026-08-21",
      adjust_type: "none",
      open: "1400.00",
      high: "1430.00",
      low: "1395.00",
      close: "1420.00",
      pre_close: "1405.00",
      volume: 100000,
      amount: "142000000.00",
      pct_change: "1.0676",
      source: "akshare",
      collected_at: "2026-08-22T01:00:00Z",
    },
  ],
  total: 1,
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

const aiResearch = {
  status: "ready",
  reason: null,
  freshness: "current",
  output: {
    output_id: "00000000-0000-4000-8000-000000000030",
    run_id: "00000000-0000-4000-8000-000000000031",
    symbol: "600519.SH",
    snapshot_id: snapshot.snapshot.id,
    knowledge_cutoff: snapshot.snapshot.knowledge_cutoff,
    research_type: "stock_health",
    ai_generated: true,
    provider_display_name: "DeepSeek",
    model_display_name: "research-model",
    context_version: "ai-context-v1",
    context_hash: "context-hash",
    prompt_version: "stock-health-prompt-v1",
    prompt_hash: "prompt-hash",
    output_schema_version: "stock-health-v1",
    model_route_version: "model-route-v1",
    route_hash: "route-hash",
    content: {
      schema_version: "stock-health-v1",
      headline: {
        text: "收入动能值得结合后续披露持续核对",
        evidence_refs: ["EV-FIXTURE0001"],
      },
      executive_summary: [
        {
          text: "现有证据显示收入动能发生连续变化。",
          evidence_refs: ["EV-FIXTURE0001"],
        },
        {
          text: "该变化仍需结合后续报告确认持续性。",
          evidence_refs: ["EV-FIXTURE0001"],
        },
      ],
      dimensions: [
        {
          dimension: "growth",
          interpretation: {
            text: "成长维度出现连续变化，后续披露可用于核对。",
            evidence_refs: ["EV-FIXTURE0001"],
          },
        },
        { dimension: "profitability", interpretation: null },
        { dimension: "quality", interpretation: null },
        { dimension: "balance", interpretation: null },
        { dimension: "valuation", interpretation: null },
      ],
      attention_items: [],
    },
    evidence_index: [
      {
        evidence_id: "EV-FIXTURE0001",
        observation_id: observation.id,
        dimension: "growth",
        title: observation.title,
        summary: observation.summary,
        current_period: observation.current_period,
        evidence_metrics: observation.evidence_metrics,
        evidence_sources: observation.evidence_sources,
        calculation: observation.calculation,
      },
    ],
    coverage: [
      { dimension: "growth", status: "available", reason: null },
      { dimension: "profitability", status: "missing", reason: "证据不足" },
      { dimension: "quality", status: "missing", reason: "证据不足" },
      { dimension: "balance", status: "missing", reason: "证据不足" },
      { dimension: "valuation", status: "missing", reason: "证据不足" },
    ],
    generated_at: "2026-08-16T01:00:00Z",
  },
};

const peerComparisons = {
  status: "ready",
  symbol: "600519",
  canonical_symbol: "600519.SH",
  industry: {
    taxonomy_code: "akshare_dev_industry",
    taxonomy_version: "phase6-dev-v1",
    industry_code: "baijiu",
    industry_name: "白酒",
    source: "stock_master",
    source_reference: "stocks.industry_code",
    commercial_use_status: "TBD / requires legal review",
    redistribution_status: "TBD / requires legal review",
  },
  peer_universe_fingerprint: "peer-fingerprint",
  knowledge_cutoff: "2026-08-16T00:00:00Z",
  items: [
    {
      metric_code: "roe",
      metric_kind: "fundamental",
      dimension: "profitability",
      status: "available",
      reason: null,
      company_value: "18.20",
      unit: "percent",
      period_end: "2025-12-31",
      fiscal_period: "FY",
      basis: "fy",
      peer_median: "10.70",
      peer_p25: "7.80",
      peer_p75: "16.50",
      numeric_percentile: "82.00",
      numeric_rank_desc: 2,
      sample_size: 8,
      evidence: {
        benchmark_snapshot_id: "00000000-0000-4000-8000-000000000040",
        company_source_kind: "fundamental",
        company_source_id: "00000000-0000-4000-8000-000000000041",
        peer_input_count: 8,
        peer_source_ids: [],
        excluded_invalid_value_count: 0,
        knowledge_cutoff: "2026-08-16T00:00:00Z",
      },
    },
  ],
  total: 1,
};

const eventRadar = {
  status: "ready",
  freshness: "current",
  source_health: "healthy",
  coverage_status: "partial",
  symbol: "600519",
  canonical_symbol: "600519.SH",
  snapshot_id: "00000000-0000-4000-8000-000000000050",
  knowledge_cutoff: "2026-08-16T00:00:00Z",
  generated_at: "2026-08-16T01:00:00Z",
  upcoming_items: [],
  recent_items: [
    {
      section: "recent",
      attention_level: "notice",
      attention_rule_id: "follow-up-required",
      attention_rule_version: "event-attention-v1",
      attention_reason: "事件可能存在后续进展，建议持续核对公告",
      event: {
        id: "00000000-0000-4000-8000-000000000051",
        symbol: "600519",
        canonical_symbol: "600519.SH",
        event_family: "share_pledge",
        event_type: "pledge_created",
        title: "关于控股股东股份质押的公告",
        event_thread_key: "event-thread",
        identity_basis: "source_document+family+effective_date",
        source_published_at: "2026-08-15T00:00:00Z",
        known_at: "2026-08-16T00:00:00Z",
        extraction_status: "partial",
        typed_payload: { kind: "share_pledge", event_type: "pledge_created" },
        field_lineage: {},
        sources: [],
      },
    },
  ],
};

const coverage = {
  symbol: "600519",
  canonical_symbol: "600519.SH",
  snapshot_id: null,
  knowledge_cutoff: "2026-08-16T00:00:00Z",
  evaluated_at: "2026-08-16T00:00:00Z",
  coverage_schema_version: "research-coverage-v1",
  evaluator_version: "coverage-evaluator-v1",
  policy_version: "coverage-policy-v1",
  limitations: [],
  dimensions: [
    {
      dimension: "market",
      availability: "ready",
      freshness: "current",
      source_health: "degraded",
      reason_codes: ["provider_unavailable"],
      latest_artifact_at: "2026-08-21T00:00:00Z",
    },
    {
      dimension: "financial",
      availability: "ready",
      freshness: "current",
      source_health: "healthy",
      reason_codes: [],
      latest_artifact_at: "2026-08-16T00:00:00Z",
    },
    {
      dimension: "fundamental_research",
      availability: "ready",
      freshness: "current",
      source_health: "healthy",
      reason_codes: [],
      latest_artifact_at: "2026-08-16T00:00:00Z",
    },
    {
      dimension: "peer_research",
      availability: "ready",
      freshness: "current",
      source_health: "healthy",
      reason_codes: [],
      latest_artifact_at: "2026-08-16T00:00:00Z",
    },
    {
      dimension: "event_radar",
      availability: "ready",
      freshness: "current",
      source_health: "healthy",
      reason_codes: [],
      latest_artifact_at: "2026-08-16T00:00:00Z",
    },
    {
      dimension: "ai_research",
      availability: "ready",
      freshness: "current",
      source_health: "healthy",
      reason_codes: [],
      latest_artifact_at: "2026-08-16T00:00:00Z",
    },
  ],
};

function successfulFetch(input: RequestInfo | URL) {
  const url = String(input);
  const body = url.includes("daily-bars")
    ? emptyBars
    : url.includes("/coverage")
      ? coverage
      : url.includes("event-radar")
        ? eventRadar
        : url.includes("peer-comparisons")
          ? peerComparisons
          : url.includes("ai-research")
            ? aiResearch
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
  cleanup();
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

  it("uses the latest market date and source health in the market evidence rail", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        if (String(input).includes("daily-bars")) {
          return Promise.resolve(
            new Response(JSON.stringify(marketBars), {
              status: 200,
              headers: { "Content-Type": "application/json" },
            }),
          );
        }
        return successfulFetch(input);
      }),
    );
    render(
      <Providers>
        <StockDetail symbol="600519" />
      </Providers>,
    );
    await screen.findAllByText("贵州茅台");
    for (const tab of screen.getAllByRole("tab", { name: "行情" })) {
      fireEvent.click(tab);
    }
    expect(screen.getAllByText("2026-08-21")).toHaveLength(2);
    await waitFor(() =>
      expect(
        screen
          .getAllByTestId("market-source-health")
          .map((item) => item.textContent),
      ).toEqual([
        "来源暂时降级，保留最近已验证行情",
        "来源暂时降级，保留最近已验证行情",
      ]),
    );
    expect(screen.getAllByText("未复权日 K")).toHaveLength(2);
  });

  it("opens an evidence trace in both responsive compositions", async () => {
    vi.stubGlobal("fetch", vi.fn(successfulFetch));
    render(
      <Providers>
        <StockDetail symbol="600519" />
      </Providers>,
    );
    const changeTabs = await screen.findAllByRole("tab", { name: "关键变化" });
    fireEvent.click(changeTabs[0]);
    fireEvent.click(changeTabs[1]);
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

  it("renders AI research with explicit labels and traceable evidence", async () => {
    vi.stubGlobal("fetch", vi.fn(successfulFetch));
    render(
      <Providers>
        <StockDetail symbol="600519" />
      </Providers>,
    );
    expect(await screen.findAllByRole("tab", { name: "研究" })).toHaveLength(2);
    const aiTabs = screen.getAllByRole("tab", { name: "AI 解读" });
    fireEvent.click(aiTabs[0]);
    fireEvent.click(aiTabs[1]);
    expect(screen.getAllByText("AI 生成内容")).toHaveLength(2);
    expect(
      screen.getAllByText("收入动能值得结合后续披露持续核对"),
    ).toHaveLength(2);
    const citations = screen.getAllByRole("button", {
      name: "查看 AI 引用证据：收入单季增速连续改善",
    });
    fireEvent.click(citations[0]);
    expect(
      await screen.findByRole("dialog", { name: "变化证据详情" }),
    ).toBeInTheDocument();
  });

  it("renders peer position in both responsive research compositions", async () => {
    vi.stubGlobal("fetch", vi.fn(successfulFetch));
    render(
      <Providers>
        <StockDetail symbol="600519" />
      </Providers>,
    );
    const peerTabs = await screen.findAllByRole("tab", { name: "同行位置" });
    fireEvent.click(peerTabs[0]);
    fireEvent.click(peerTabs[1]);
    expect(screen.getAllByText("同行位置")).toHaveLength(4);
    expect(screen.getAllByText("82.0% 数值分位")).toHaveLength(2);
    expect(screen.getAllByText("同行样本 8")).toHaveLength(2);
  });

  it("renders event radar independently in desktop and mobile research", async () => {
    vi.stubGlobal("fetch", vi.fn(successfulFetch));
    render(
      <Providers>
        <StockDetail symbol="600519" />
      </Providers>,
    );
    const eventTabs = await screen.findAllByRole("tab", { name: "事件雷达" });
    fireEvent.click(eventTabs[0]);
    fireEvent.click(eventTabs[1]);
    expect(screen.getAllByRole("heading", { name: "事件雷达" })).toHaveLength(
      2,
    );
    expect(screen.getAllByText("关于控股股东股份质押的公告")).toHaveLength(2);
  });

  it("shows unsupported AI state without a generation action", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        if (String(input).includes("ai-research")) {
          return Promise.resolve(
            new Response(
              JSON.stringify({
                status: "unsupported",
                reason: "unsupported_issuer_type",
                freshness: null,
                output: null,
              }),
              { status: 200, headers: { "Content-Type": "application/json" } },
            ),
          );
        }
        return successfulFetch(input);
      }),
    );
    render(
      <Providers>
        <StockDetail symbol="000001" />
      </Providers>,
    );
    const aiTabs = await screen.findAllByRole("tab", { name: "AI 解读" });
    fireEvent.click(aiTabs[0]);
    fireEvent.click(aiTabs[1]);
    expect(screen.getAllByText("当前发行人模板暂不支持")).toHaveLength(2);
    expect(
      screen.queryByRole("button", { name: /生成|重算/ }),
    ).not.toBeInTheDocument();
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
    expect(await screen.findAllByText("营业收入同比增长率")).toHaveLength(2);
    expect(screen.getAllByText("可追溯至 1 个报表版本")).toHaveLength(2);
  });
});
