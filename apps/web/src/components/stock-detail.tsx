"use client";

import {
  createZhaoniuClient,
  type DailyBarResponse,
  type FinancialPeriodListResponse,
  type FundamentalMetricResponse,
  type FundamentalResearchResponse,
  type StockResponse,
  type ValuationListResponse,
} from "@zhaoniu/api-client";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  BarChart3,
  CalendarDays,
  Database,
  FileText,
  RefreshCw,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import { useMemo, useState } from "react";

import {
  assertFinancialPeriods,
  assertFundamentals,
  assertValuations,
  formatFinancialValue,
  metricByCode,
  metricStatusCopy,
  valuationSeries,
} from "@/lib/fundamentals";
import {
  assertDailyBars,
  parseFiniteDecimal,
  toCandles,
} from "@/lib/market-data";

import { StockChart } from "./stock-chart";
import { Card } from "./ui/card";
import { ValuationChart } from "./valuation-chart";

const api = createZhaoniuClient({
  baseUrl: process.env.NEXT_PUBLIC_API_BASE_URL,
});

type WorkspaceTab = "market" | "financials" | "valuation";

type ResearchData = {
  fundamentals: FundamentalResearchResponse;
  periods: FinancialPeriodListResponse;
  valuations: ValuationListResponse;
};

const tabs: { code: WorkspaceTab; label: string; icon: typeof Activity }[] = [
  { code: "market", label: "行情", icon: Activity },
  { code: "financials", label: "财务", icon: FileText },
  { code: "valuation", label: "估值", icon: BarChart3 },
];

function formatDecimal(value: string | null | undefined, digits = 2) {
  if (value == null) return "—";
  return new Intl.NumberFormat("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(parseFiniteDecimal(value, "display value"));
}

function formatInteger(value: number | undefined) {
  if (value == null) return "—";
  return new Intl.NumberFormat("zh-CN").format(value);
}

function QuoteStrip({
  stock,
  latest,
}: {
  stock: StockResponse;
  latest?: DailyBarResponse;
}) {
  const items = [
    ["收盘", formatDecimal(latest?.close ?? stock.latest_price)],
    [
      "涨跌幅",
      latest?.pct_change ? `${formatDecimal(latest.pct_change)}%` : "—",
    ],
    ["最高", formatDecimal(latest?.high)],
    ["最低", formatDecimal(latest?.low)],
    ["成交量", formatInteger(latest?.volume)],
  ];
  return (
    <div className="border-ink/10 bg-paper grid grid-cols-2 overflow-hidden rounded-2xl border sm:grid-cols-5">
      {items.map(([label, value], index) => (
        <div
          key={label}
          className={`px-4 py-3 ${index > 0 ? "border-ink/8 sm:border-l" : ""}`}
        >
          <p className="text-slate text-[10px] uppercase tracking-[0.15em]">
            {label}
          </p>
          <p className="font-data mt-1 text-base font-semibold">{value}</p>
        </div>
      ))}
    </div>
  );
}

function WorkspaceTabs({
  value,
  onChange,
  mobile = false,
}: {
  value: WorkspaceTab;
  onChange: (value: WorkspaceTab) => void;
  mobile?: boolean;
}) {
  return (
    <div
      role="tablist"
      aria-label="股票研究视图"
      className={
        mobile
          ? "bg-paper border-ink/10 grid grid-cols-3 rounded-2xl border p-1"
          : "border-ink/10 flex gap-1 border-b"
      }
    >
      {tabs.map(({ code, label, icon: Icon }) => (
        <button
          key={code}
          role="tab"
          aria-selected={value === code}
          className={
            mobile
              ? `flex min-h-11 items-center justify-center gap-2 rounded-xl text-sm transition ${value === code ? "bg-ink text-white" : "text-slate"}`
              : `flex items-center gap-2 border-b-2 px-5 py-3 text-sm transition ${value === code ? "border-blue text-ink" : "text-slate hover:text-ink border-transparent"}`
          }
          onClick={() => onChange(code)}
          type="button"
        >
          <Icon className="size-4" />
          {label}
        </button>
      ))}
    </div>
  );
}

function EvidenceRail({
  stock,
  latest,
  research,
}: {
  stock: StockResponse;
  latest?: DailyBarResponse;
  research?: FundamentalResearchResponse;
}) {
  return (
    <Card className="overflow-hidden">
      <div className="bg-ink px-5 py-4 text-white">
        <p className="font-data text-[10px] uppercase tracking-[0.2em] text-white/55">
          Evidence ledger
        </p>
        <h2 className="font-display mt-1 text-lg font-semibold">数据证据</h2>
      </div>
      <dl className="divide-ink/8 divide-y px-5 text-sm">
        <div className="flex gap-3 py-4">
          <Database className="text-blue mt-0.5 size-4 shrink-0" />
          <div>
            <dt className="text-slate text-xs">数据来源</dt>
            <dd className="mt-1 font-medium">
              {research?.provider ?? latest?.source ?? stock.source ?? "—"}
            </dd>
            <p className="text-amber mt-1 text-xs">开发与技术评估数据源</p>
          </div>
        </div>
        <div className="flex gap-3 py-4">
          <CalendarDays className="text-blue mt-0.5 size-4 shrink-0" />
          <div>
            <dt className="text-slate text-xs">最新数据期间</dt>
            <dd className="font-data mt-1">
              {research?.latest_report_period ??
                stock.latest_trade_date ??
                "暂无数据"}
            </dd>
          </div>
        </div>
        <div className="flex gap-3 py-4">
          <ShieldCheck className="text-blue mt-0.5 size-4 shrink-0" />
          <div>
            <dt className="text-slate text-xs">可用时间口径</dt>
            <dd className="mt-1">
              {research?.published_at_precision === "date"
                ? "公告日后保守可用"
                : "精确发布时间"}
            </dd>
            <p className="text-slate mt-1 text-xs">
              财务指标由确定性公式计算，不使用 AI 估算
            </p>
          </div>
        </div>
      </dl>
    </Card>
  );
}

function ChartCard({
  candles,
  empty,
}: {
  candles: ReturnType<typeof toCandles>;
  empty: boolean;
}) {
  return (
    <Card className="overflow-hidden">
      <div className="border-ink/8 flex items-center justify-between border-b px-5 py-4">
        <div>
          <p className="font-display text-lg font-semibold">价格轨迹</p>
          <p className="text-slate mt-0.5 text-xs">
            按交易日升序 · 最多 120 条
          </p>
        </div>
        <span className="bg-mist font-data rounded-full px-3 py-1 text-[10px]">
          未复权 · CNY
        </span>
      </div>
      {empty ? (
        <div className="grid min-h-[380px] place-items-center px-6 text-center">
          <div>
            <Database className="text-slate mx-auto size-6" />
            <p className="mt-3 font-medium">股票资料已找到，暂无日 K 行情</p>
            <p className="text-slate mt-1 text-sm">
              同步成功后，蜡烛图会在这里显示。
            </p>
          </div>
        </div>
      ) : (
        <StockChart data={candles} />
      )}
    </Card>
  );
}

function ResearchState({
  pending,
  error,
  onRetry,
}: {
  pending: boolean;
  error: boolean;
  onRetry: () => void;
}) {
  if (pending) {
    return (
      <Card className="grid min-h-72 place-items-center p-6" role="status">
        <div className="text-center">
          <RefreshCw className="text-blue mx-auto size-5 animate-spin" />
          <p className="mt-3 font-medium">正在读取财务证据</p>
          <p className="text-slate mt-1 text-sm">
            报表、指标与估值会一起校验。
          </p>
        </div>
      </Card>
    );
  }
  if (error) {
    return (
      <Card className="border-risk/30 p-6" role="alert">
        <TriangleAlert className="text-risk size-5" />
        <p className="mt-3 font-medium">财务研究数据暂时无法读取</p>
        <p className="text-slate mt-1 text-sm">
          行情仍可使用。确认财报同步完成后再试一次。
        </p>
        <button
          className="bg-ink mt-4 rounded-xl px-4 py-2 text-sm text-white"
          onClick={onRetry}
          type="button"
        >
          重新读取
        </button>
      </Card>
    );
  }
  return null;
}

function MetricCell({ metric }: { metric: FundamentalMetricResponse }) {
  const available = metric.status === "available";
  return (
    <div className="border-ink/8 border-t py-3 first:border-t-0">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium">{metric.display_name}</p>
          <p className="font-data text-slate mt-1 text-[10px] uppercase">
            {metric.period_end ?? "无报告期"} · {metric.basis}
          </p>
        </div>
        <p
          className={`font-data text-right text-base ${available ? "text-ink" : "text-slate"}`}
        >
          {available
            ? formatFinancialValue(metric.value, metric.unit)
            : (metricStatusCopy[metric.status] ?? metric.status)}
        </p>
      </div>
      <p className="text-slate mt-1 text-[11px]">
        {metric.source_report_ids.length > 0
          ? `可追溯至 ${metric.source_report_ids.length} 个报表版本`
          : (metric.detail ?? "当前没有可追溯输入")}
      </p>
    </div>
  );
}

function FundamentalLedger({
  research,
}: {
  research: FundamentalResearchResponse;
}) {
  const dimensions = research.dimensions.filter(
    (dimension) => dimension.code !== "valuation",
  );
  const hasData = dimensions.some((dimension) =>
    dimension.items.some((item) => item.status === "available"),
  );
  return (
    <div>
      <div className="border-ink/10 bg-paper mb-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border px-4 py-3">
        <div>
          <p className="text-sm font-medium">
            {research.latest_report_period
              ? `最新报告期 ${research.latest_report_period}`
              : "尚无财务报告"}
          </p>
          <p className="text-slate mt-1 text-xs">
            {research.latest_report_published_at
              ? `公告时间 ${new Date(research.latest_report_published_at).toLocaleDateString("zh-CN")}`
              : "完成财报同步后显示公告口径"}
          </p>
        </div>
        <span className="bg-mist font-data rounded-full px-3 py-1 text-[10px]">
          {research.freshness === "current"
            ? "数据在有效期内"
            : research.freshness === "stale"
              ? "数据可能陈旧"
              : "数据不可用"}
        </span>
      </div>
      {research.issuer_type !== "general" && (
        <Card className="border-amber/30 mb-4 p-5">
          <p className="font-medium">金融企业指标模板尚未支持</p>
          <p className="text-slate mt-1 text-sm">
            系统已识别企业类型，未套用一般工商企业指标，避免产生误导。
          </p>
        </Card>
      )}
      {!hasData && research.issuer_type === "general" ? (
        <Card className="p-8 text-center">
          <Database className="text-slate mx-auto size-5" />
          <p className="mt-3 font-medium">尚无可计算的财务指标</p>
          <p className="text-slate mt-1 text-sm">
            同步三张报表后，这里会显示确定性研究指标。
          </p>
        </Card>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {dimensions.map((dimension) => (
            <Card key={dimension.code} className="p-5">
              <p className="font-display text-lg font-semibold">
                {dimension.display_name}
              </p>
              <div className="mt-3">
                {dimension.items.map((metric) => (
                  <MetricCell key={metric.code} metric={metric} />
                ))}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

const financialRows = [
  {
    label: "营业收入",
    value: (period: FinancialPeriodListResponse["items"][number]) =>
      period.income?.revenue,
  },
  {
    label: "归母净利润",
    value: (period: FinancialPeriodListResponse["items"][number]) =>
      period.income?.parent_net_profit,
  },
  {
    label: "经营现金流",
    value: (period: FinancialPeriodListResponse["items"][number]) =>
      period.cash_flow?.operating_cash_flow,
  },
  {
    label: "总资产",
    value: (period: FinancialPeriodListResponse["items"][number]) =>
      period.balance?.total_assets,
  },
  {
    label: "总负债",
    value: (period: FinancialPeriodListResponse["items"][number]) =>
      period.balance?.total_liabilities,
  },
  {
    label: "货币资金",
    value: (period: FinancialPeriodListResponse["items"][number]) =>
      period.balance?.cash,
  },
];

function FinancialComparison({
  periods,
}: {
  periods: FinancialPeriodListResponse;
}) {
  const displayed = periods.items.slice(0, 6);
  if (displayed.length === 0) return null;
  return (
    <Card className="mt-4 overflow-hidden">
      <div className="border-ink/8 border-b px-5 py-4">
        <h3 className="font-display text-lg font-semibold">报告期对照</h3>
        <p className="text-slate mt-1 text-xs">
          披露事实 · CNY · 不将缺失值写成零
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] border-collapse text-sm">
          <thead>
            <tr className="bg-mist/70 text-left">
              <th className="px-5 py-3 font-medium">科目</th>
              {displayed.map((period) => (
                <th key={period.id} className="font-data px-4 py-3 font-medium">
                  {period.fiscal_year} {period.fiscal_period}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {financialRows.map((row) => (
              <tr key={row.label} className="border-ink/8 border-t">
                <th className="px-5 py-3 text-left font-medium">{row.label}</th>
                {displayed.map((period) => (
                  <td key={period.id} className="font-data px-4 py-3">
                    {formatFinancialValue(row.value(period), "CNY")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function MobileFinancialPeriod({
  periods,
}: {
  periods: FinancialPeriodListResponse;
}) {
  const [selectedId, setSelectedId] = useState(periods.items[0]?.id ?? "");
  const selected =
    periods.items.find((item) => item.id === selectedId) ?? periods.items[0];
  if (!selected) return null;
  return (
    <Card className="mt-4 p-5">
      <label className="text-slate text-xs" htmlFor="financial-period">
        查看报告期
      </label>
      <select
        id="financial-period"
        className="border-ink/10 bg-paper mt-2 w-full rounded-xl border px-3 py-2 text-sm"
        value={selected.id}
        onChange={(event) => setSelectedId(event.target.value)}
      >
        {periods.items.map((period) => (
          <option key={period.id} value={period.id}>
            {period.fiscal_year} {period.fiscal_period} ·{" "}
            {period.is_audited ? "已审计" : "未审计"}
          </option>
        ))}
      </select>
      <dl className="divide-ink/8 mt-3 divide-y">
        {financialRows.map((row) => (
          <div
            key={row.label}
            className="flex items-center justify-between gap-4 py-3"
          >
            <dt className="text-sm">{row.label}</dt>
            <dd className="font-data text-sm">
              {formatFinancialValue(row.value(selected), "CNY")}
            </dd>
          </div>
        ))}
      </dl>
      <p className="text-slate mt-3 text-[11px]">
        {selected.provider} · 公告日{" "}
        {new Date(selected.published_at).toLocaleDateString("zh-CN")}
      </p>
    </Card>
  );
}

function ValuationPanel({
  research,
  valuations,
  compact = false,
}: {
  research: FundamentalResearchResponse;
  valuations: ValuationListResponse;
  compact?: boolean;
}) {
  const series = useMemo(() => valuationSeries(valuations), [valuations]);
  const summaryCodes = ["pe_ttm", "pb", "market_cap", "pe_ttm_percentile_3y"];
  const summary = summaryCodes
    .map((code) => metricByCode(research, code))
    .filter((item): item is FundamentalMetricResponse => Boolean(item));
  return (
    <div>
      <div className={`grid gap-3 ${compact ? "grid-cols-2" : "grid-cols-4"}`}>
        {summary.map((metric) => (
          <Card key={metric.code} className="p-4">
            <p className="text-slate text-xs">{metric.display_name}</p>
            <p className="font-data mt-2 text-lg font-semibold">
              {metric.status === "available"
                ? formatFinancialValue(metric.value, metric.unit)
                : (metricStatusCopy[metric.status] ?? metric.status)}
            </p>
            <p className="text-slate mt-1 text-[10px]">
              {metric.period_end ?? "暂无日期"}
            </p>
          </Card>
        ))}
      </div>
      <Card className="mt-4 overflow-hidden">
        <div className="border-ink/8 flex flex-wrap items-center justify-between gap-2 border-b px-5 py-4">
          <div>
            <h3 className="font-display text-lg font-semibold">历史估值轨迹</h3>
            <p className="text-slate mt-1 text-xs">
              Provider 观测值，不伪装为本地重算
            </p>
          </div>
          <span className="bg-mist font-data rounded-full px-3 py-1 text-[10px]">
            {valuations.coverage.sample_count} 个样本
          </span>
        </div>
        {series.length > 0 ? (
          <ValuationChart series={series} compact={compact} />
        ) : (
          <div className="grid min-h-64 place-items-center px-6 text-center">
            <div>
              <BarChart3 className="text-slate mx-auto size-5" />
              <p className="mt-3 font-medium">暂无历史估值观测</p>
              <p className="text-slate mt-1 text-sm">
                同步估值数据后显示 PE、PB 和 PCF。
              </p>
            </div>
          </div>
        )}
      </Card>
      <p className="text-slate mt-3 text-xs">
        实际覆盖 {valuations.coverage.start ?? "—"} 至{" "}
        {valuations.coverage.end ?? "—"}；负 PE 不参与历史分位。
      </p>
    </div>
  );
}

function DesktopStock({
  stock,
  bars,
  research,
  researchPending,
  researchError,
  retryResearch,
}: {
  stock: StockResponse;
  bars: DailyBarResponse[];
  research?: ResearchData;
  researchPending: boolean;
  researchError: boolean;
  retryResearch: () => void;
}) {
  const [tab, setTab] = useState<WorkspaceTab>("market");
  const latest = bars.at(-1);
  const candles = useMemo(() => toCandles(bars), [bars]);
  return (
    <div className="hidden md:block">
      <div className="mb-6 flex items-end justify-between gap-6">
        <div>
          <p className="font-data text-blue text-xs uppercase tracking-[0.18em]">
            {stock.canonical_symbol}
          </p>
          <h1 className="font-display mt-2 text-4xl font-semibold tracking-tight">
            {stock.name}
          </h1>
          <p className="text-slate mt-2 text-sm">
            {stock.exchange} · {stock.board} · {stock.status}
          </p>
        </div>
        <div className="text-right">
          <p className="text-slate text-xs">最近收盘</p>
          <p className="font-data mt-1 text-4xl font-semibold">
            {formatDecimal(stock.latest_price)}
          </p>
        </div>
      </div>
      <QuoteStrip stock={stock} latest={latest} />
      <div className="mt-6">
        <WorkspaceTabs value={tab} onChange={setTab} />
      </div>
      <div className="mt-5">
        {tab === "market" && (
          <div className="grid grid-cols-[minmax(0,1fr)_280px] gap-5">
            <ChartCard candles={candles} empty={bars.length === 0} />
            <EvidenceRail
              stock={stock}
              latest={latest}
              research={research?.fundamentals}
            />
          </div>
        )}
        {tab !== "market" && !research && (
          <ResearchState
            pending={researchPending}
            error={researchError}
            onRetry={retryResearch}
          />
        )}
        {tab === "financials" && research && (
          <>
            <FundamentalLedger research={research.fundamentals} />
            <FinancialComparison periods={research.periods} />
          </>
        )}
        {tab === "valuation" && research && (
          <ValuationPanel
            research={research.fundamentals}
            valuations={research.valuations}
          />
        )}
      </div>
    </div>
  );
}

function MobileStock({
  stock,
  bars,
  research,
  researchPending,
  researchError,
  retryResearch,
}: {
  stock: StockResponse;
  bars: DailyBarResponse[];
  research?: ResearchData;
  researchPending: boolean;
  researchError: boolean;
  retryResearch: () => void;
}) {
  const [tab, setTab] = useState<WorkspaceTab>("market");
  const latest = bars.at(-1);
  const candles = useMemo(() => toCandles(bars), [bars]);
  return (
    <div className="md:hidden">
      <div className="bg-ink -mx-4 -mt-6 px-4 pb-7 pt-6 text-white">
        <p className="font-data text-[10px] uppercase tracking-[0.2em] text-white/55">
          {stock.canonical_symbol}
        </p>
        <div className="mt-3 flex items-end justify-between gap-3">
          <div>
            <h1 className="font-display text-3xl font-semibold">
              {stock.name}
            </h1>
            <p className="mt-1 text-xs text-white/55">
              {stock.exchange} · {stock.board}
            </p>
          </div>
          <p className="font-data text-3xl font-semibold">
            {formatDecimal(stock.latest_price)}
          </p>
        </div>
      </div>
      <div className="mt-4">
        <QuoteStrip stock={stock} latest={latest} />
      </div>
      <div className="mt-4">
        <WorkspaceTabs value={tab} onChange={setTab} mobile />
      </div>
      <div className="mt-4">
        {tab === "market" && (
          <div className="space-y-4">
            <ChartCard candles={candles} empty={bars.length === 0} />
            <EvidenceRail
              stock={stock}
              latest={latest}
              research={research?.fundamentals}
            />
          </div>
        )}
        {tab !== "market" && !research && (
          <ResearchState
            pending={researchPending}
            error={researchError}
            onRetry={retryResearch}
          />
        )}
        {tab === "financials" && research && (
          <>
            <FundamentalLedger research={research.fundamentals} />
            <MobileFinancialPeriod periods={research.periods} />
          </>
        )}
        {tab === "valuation" && research && (
          <ValuationPanel
            research={research.fundamentals}
            valuations={research.valuations}
            compact
          />
        )}
      </div>
    </div>
  );
}

export function StockDetail({ symbol }: { symbol: string }) {
  const market = useQuery({
    queryKey: ["stock", symbol, "daily-bars", 120],
    queryFn: async () => {
      const [stock, bars] = await Promise.all([
        api.getStock(symbol),
        api.getDailyBars(symbol),
      ]);
      return { stock, bars: assertDailyBars(bars) };
    },
    retry: 1,
  });
  const research = useQuery({
    queryKey: ["stock", symbol, "fundamentals"],
    queryFn: async () => {
      const [fundamentals, periods, valuations] = await Promise.all([
        api.getFundamentals(symbol),
        api.getFinancialPeriods(symbol),
        api.getValuations(symbol),
      ]);
      return {
        fundamentals: assertFundamentals(fundamentals),
        periods: assertFinancialPeriods(periods),
        valuations: assertValuations(valuations),
      };
    },
    retry: 1,
  });

  if (market.isPending) {
    return (
      <div className="grid min-h-[60vh] place-items-center" role="status">
        <div className="text-center">
          <RefreshCw className="text-blue mx-auto size-6 animate-spin" />
          <p className="mt-3 font-medium">正在读取真实行情</p>
          <p className="text-slate mt-1 text-sm">
            股票资料与日 K 正从版本化 API 加载。
          </p>
        </div>
      </div>
    );
  }
  if (market.isError) {
    return (
      <Card className="border-risk/30 mx-auto max-w-2xl p-6" role="alert">
        <TriangleAlert className="text-risk size-6" />
        <h1 className="font-display mt-4 text-2xl font-semibold">
          无法读取这只股票
        </h1>
        <p className="text-slate mt-2 text-sm">
          确认 API 已启动、股票代码有效，然后重试。
        </p>
        <button
          className="bg-ink mt-5 rounded-xl px-4 py-2 text-sm text-white"
          onClick={() => void market.refetch()}
          type="button"
        >
          重新加载
        </button>
      </Card>
    );
  }
  const shared = {
    stock: market.data.stock,
    bars: market.data.bars.items,
    research: research.data,
    researchPending: research.isPending,
    researchError: research.isError,
    retryResearch: () => void research.refetch(),
  };
  return (
    <>
      <DesktopStock {...shared} />
      <MobileStock {...shared} />
    </>
  );
}
