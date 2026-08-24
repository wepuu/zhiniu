import type {
  FinancialPeriodListResponse,
  FundamentalMetricResponse,
  FundamentalResearchResponse,
  ValuationListResponse,
} from "@zhaoniu/api-client";

import { parseFiniteDecimal } from "./market-data";
import { formatFinancialValue as formatPresentedFinancialValue } from "./presentation";

export const metricStatusCopy: Record<string, string> = {
  available: "可用",
  missing_input: "缺少输入",
  insufficient_history: "历史不足",
  not_applicable: "不适用",
  invalid_input: "口径无效",
};

export function assertFundamentals(
  value: FundamentalResearchResponse,
): FundamentalResearchResponse {
  const codes = new Set<string>();
  for (const dimension of value.dimensions) {
    for (const metric of dimension.items) {
      if (codes.has(metric.code)) {
        throw new TypeError(`duplicate fundamental metric: ${metric.code}`);
      }
      codes.add(metric.code);
      if (metric.value != null) {
        parseFiniteDecimal(metric.value, metric.code);
      }
    }
  }
  return value;
}

export function assertFinancialPeriods(
  value: FinancialPeriodListResponse,
): FinancialPeriodListResponse {
  if (value.total !== value.items.length) {
    throw new TypeError("financial-period response metadata is inconsistent");
  }
  return value;
}

export function assertValuations(
  value: ValuationListResponse,
): ValuationListResponse {
  if (value.total !== value.items.length) {
    throw new TypeError("valuation response metadata is inconsistent");
  }
  for (const item of value.items) {
    parseFiniteDecimal(item.value, item.metric_code);
  }
  return value;
}

export function metricByCode(
  research: FundamentalResearchResponse,
  code: string,
): FundamentalMetricResponse | undefined {
  return research.dimensions
    .flatMap((dimension) => dimension.items)
    .find((metric) => metric.code === code);
}

export function formatFinancialValue(
  value: string | null | undefined,
  unit: string,
  metricCode?: string,
): string {
  return formatPresentedFinancialValue({
    metricCode,
    value,
    unit,
    context: "detail",
  });
}

export function valuationSeries(value: ValuationListResponse) {
  const groups = new Map<string, { date: string; value: number }[]>();
  for (const item of value.items) {
    if (item.metric_code === "market_cap") continue;
    const group = groups.get(item.metric_code) ?? [];
    group.push({
      date: item.trade_date,
      value: parseFiniteDecimal(item.value, item.metric_code),
    });
    groups.set(item.metric_code, group);
  }
  return [...groups.entries()].map(([code, items]) => ({ code, items }));
}
