"use client";

import {
  createZhaoniuClient,
  type DailyBarResponse,
  type StockResponse,
} from "@zhaoniu/api-client";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  CalendarDays,
  Database,
  RefreshCw,
  TriangleAlert,
} from "lucide-react";
import { useMemo } from "react";

import {
  assertDailyBars,
  parseFiniteDecimal,
  toCandles,
} from "@/lib/market-data";

import { StockChart } from "./stock-chart";
import { Card } from "./ui/card";

const api = createZhaoniuClient({
  baseUrl: process.env.NEXT_PUBLIC_API_BASE_URL,
});

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

function EvidenceRail({
  stock,
  latest,
}: {
  stock: StockResponse;
  latest?: DailyBarResponse;
}) {
  return (
    <Card className="overflow-hidden">
      <div className="bg-ink px-5 py-4 text-white">
        <p className="font-data text-[10px] uppercase tracking-[0.2em] text-white/55">
          Evidence rail
        </p>
        <h2 className="font-display mt-1 text-lg font-semibold">数据证据</h2>
      </div>
      <dl className="divide-ink/8 divide-y px-5 text-sm">
        <div className="flex gap-3 py-4">
          <Database className="text-blue mt-0.5 size-4 shrink-0" />
          <div>
            <dt className="text-slate text-xs">数据来源</dt>
            <dd className="mt-1 font-medium">
              {latest?.source ?? stock.source ?? "—"}
            </dd>
            <p className="text-amber mt-1 text-xs">开发与技术评估源</p>
          </div>
        </div>
        <div className="flex gap-3 py-4">
          <CalendarDays className="text-blue mt-0.5 size-4 shrink-0" />
          <div>
            <dt className="text-slate text-xs">最近交易日</dt>
            <dd className="font-data mt-1">
              {stock.latest_trade_date ?? "暂无行情"}
            </dd>
          </div>
        </div>
        <div className="flex gap-3 py-4">
          <Activity className="text-blue mt-0.5 size-4 shrink-0" />
          <div>
            <dt className="text-slate text-xs">行情口径</dt>
            <dd className="mt-1">未复权日 K · CNY</dd>
            <p className="text-slate mt-1 text-xs">
              涨跌幅由 close / pre_close 确定性计算
            </p>
          </div>
        </div>
      </dl>
    </Card>
  );
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
          ADJUST · NONE
        </span>
      </div>
      {empty ? (
        <div className="grid min-h-[380px] place-items-center px-6 text-center">
          <div>
            <Database className="text-slate mx-auto size-6" />
            <p className="mt-3 font-medium">股票资料已找到，尚无日 K 行情</p>
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

function DesktopStock({
  stock,
  bars,
}: {
  stock: StockResponse;
  bars: DailyBarResponse[];
}) {
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
      <div className="mt-5 grid grid-cols-[minmax(0,1fr)_280px] gap-5">
        <ChartCard candles={candles} empty={bars.length === 0} />
        <EvidenceRail stock={stock} latest={latest} />
      </div>
    </div>
  );
}

function MobileStock({
  stock,
  bars,
}: {
  stock: StockResponse;
  bars: DailyBarResponse[];
}) {
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
        <ChartCard candles={candles} empty={bars.length === 0} />
      </div>
      <div className="mt-4">
        <EvidenceRail stock={stock} latest={latest} />
      </div>
    </div>
  );
}

export function StockDetail({ symbol }: { symbol: string }) {
  const query = useQuery({
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

  if (query.isPending) {
    return (
      <div className="grid min-h-[60vh] place-items-center" role="status">
        <div className="text-center">
          <RefreshCw className="text-blue mx-auto size-6 animate-spin" />
          <p className="mt-3 font-medium">正在读取真实行情</p>
          <p className="text-slate mt-1 text-sm">
            资料与日 K 将从版本化 API 一并载入。
          </p>
        </div>
      </div>
    );
  }

  if (query.isError) {
    return (
      <Card className="border-risk/30 mx-auto max-w-2xl p-6" role="alert">
        <TriangleAlert className="text-risk size-6" />
        <h1 className="font-display mt-4 text-2xl font-semibold">
          无法读取这只股票
        </h1>
        <p className="text-slate mt-2 text-sm">
          请确认 API 已启动、股票代码有效，然后重试。
        </p>
        <button
          className="bg-ink mt-5 rounded-xl px-4 py-2 text-sm text-white"
          onClick={() => void query.refetch()}
          type="button"
        >
          重新加载
        </button>
      </Card>
    );
  }

  return (
    <>
      <DesktopStock stock={query.data.stock} bars={query.data.bars.items} />
      <MobileStock stock={query.data.stock} bars={query.data.bars.items} />
    </>
  );
}
