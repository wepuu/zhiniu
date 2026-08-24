import type { PeerComparisonEnvelope } from "@zhaoniu/api-client";

import { formatFinancialValue, translateEnum } from "./presentation";

const envelopeStatuses = new Set([
  "ready",
  "not_built",
  "unsupported_template",
  "missing_industry",
  "insufficient_peers",
]);

const metricStatuses = new Set([
  "available",
  "not_applicable",
  "unsupported_template",
  "missing_industry",
  "missing_metric",
  "incomparable_basis",
  "insufficient_peers",
  "invalid_inputs",
  "not_built",
]);

export function assertPeerComparisons(value: unknown): PeerComparisonEnvelope {
  if (!value || typeof value !== "object") {
    throw new Error("Invalid peer comparison payload");
  }
  const envelope = value as PeerComparisonEnvelope;
  if (!envelopeStatuses.has(envelope.status)) {
    throw new Error("Invalid peer comparison status");
  }
  if (!Array.isArray(envelope.items)) {
    throw new Error("Invalid peer comparison items");
  }
  for (const item of envelope.items) {
    if (!metricStatuses.has(item.status)) {
      throw new Error(`Invalid peer metric status: ${item.status}`);
    }
    if (item.numeric_percentile != null) {
      const parsed = Number(item.numeric_percentile);
      if (!Number.isFinite(parsed) || parsed < 0 || parsed > 100) {
        throw new Error("Invalid peer numeric percentile");
      }
    }
  }
  return envelope;
}

export function peerStatusCopy(status: string) {
  const copy: Record<string, string> = {
    ready: "同行数据已生成",
    not_built: "同行基准尚未生成",
    unsupported_template: "当前发行人模板暂不支持同行比较",
    missing_industry: "尚未识别正式行业分类",
    insufficient_peers: "同行有效样本不足",
    available: "可比较",
    missing_metric: "缺少同口径指标",
    incomparable_basis: "指标口径不可混合",
    invalid_inputs: "输入值未通过质量校验",
    not_applicable: "不适用",
  };
  return copy[status] ?? translateEnum("status", status);
}

export function formatPeerDecimal(
  value: string | null | undefined,
  digits = 2,
) {
  if (value == null) return "—";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  return new Intl.NumberFormat("zh-CN", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(numeric);
}

export function formatPeerValue(
  value: string | null | undefined,
  unit?: string | null,
  metricCode?: string,
) {
  return formatFinancialValue({
    metricCode,
    value,
    unit,
    context: "comparison",
  });
}
