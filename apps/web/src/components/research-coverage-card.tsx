import type {
  CoverageDimension,
  StockCoverageResponse,
} from "@zhaoniu/api-client";
import {
  Bot,
  Building2,
  CalendarClock,
  CheckCircle2,
  CircleDashed,
  FileWarning,
  Radar,
} from "lucide-react";

import { Card } from "./ui/card";

const primaryDimensions = [
  "financial",
  "fundamental_research",
  "peer_research",
  "event_radar",
  "ai_research",
] as const;

const labels: Record<string, string> = {
  market: "行情",
  financial: "财务数据",
  fundamental_research: "关键变化",
  industry: "行业归属",
  peer_research: "同行研究",
  event_radar: "事件雷达",
  screening: "研究筛选",
  ai_research: "AI 解读",
};

const icons = {
  financial: Building2,
  fundamental_research: FileWarning,
  peer_research: CircleDashed,
  event_radar: Radar,
  ai_research: Bot,
};

const availabilityCopy: Record<CoverageDimension["availability"], string> = {
  ready: "已覆盖",
  partial: "部分覆盖",
  not_built: "尚未生成",
  missing_source_data: "缺少源数据",
  unsupported: "当前模板不支持",
  disabled: "当前未启用",
  blocked_by_policy: "受数据使用策略限制",
};

const reasonCopy: Record<string, string> = {
  market_daily_bars_missing: "尚未取得可用日行情。",
  financial_missing_report: "尚未取得可追溯财务报告。",
  financial_insufficient_history: "已有财务数据，但历史期数不足。",
  fundamental_snapshot_not_built: "已有输入尚未形成确定性研究快照。",
  industry_missing_membership: "尚未确认可追溯的行业归属。",
  peer_research_not_built: "同行口径或可比样本尚未准备完成。",
  peer_not_built: "同行口径或可比样本尚未准备完成。",
  peer_missing_industry: "缺少可追溯行业归属，暂不能建立同行样本。",
  event_radar_not_built: "公告与事件雷达尚未形成快照。",
  event_not_built: "公告与事件雷达尚未形成快照。",
  event_no_supported_events: "当前时间范围内没有识别到受支持的公司事件。",
  event_source_degraded: "公告来源覆盖不完整，需继续核对。",
  screening_snapshot_not_built: "当前股票尚未进入最新筛选快照。",
  ai_not_built: "确定性快照已有，AI 解读尚未生成。",
  ai_disabled: "当前环境未启用 AI 生成。",
  ai_snapshot_stale: "AI 解读基于较早的确定性研究快照。",
  unsupported_issuer_template: "当前发行人类型不套用一般工商企业模板。",
  ai_unsupported_issuer_type: "当前发行人类型暂不支持 AI 解读。",
  policy_development_source_only: "当前数据源授权范围不允许用于此环境。",
  provider_unavailable: "最近一次上游采集不可用，保留数据仍按其截止时间展示。",
};

function DimensionRow({ item }: { item: CoverageDimension }) {
  const Icon = icons[item.dimension as keyof typeof icons] ?? CircleDashed;
  const current = item.availability === "ready" && item.freshness === "current";
  const detail = (item.reason_codes ?? [])
    .map((code) => reasonCopy[code])
    .filter(Boolean)
    .join(" ");
  return (
    <li className="border-ink/8 flex items-start gap-3 border-t py-3 first:border-t-0">
      <span
        className={`mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg ${current ? "bg-blue/10 text-blue" : "bg-mist text-slate"}`}
      >
        <Icon className="size-4" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm font-medium">{labels[item.dimension]}</p>
          <span className="text-slate shrink-0 text-xs">
            {availabilityCopy[item.availability]}
            {item.freshness === "stale" ? " · 待更新" : ""}
          </span>
        </div>
        {detail && (
          <p className="text-slate mt-1 text-xs leading-5">{detail}</p>
        )}
      </div>
    </li>
  );
}

export function ResearchCoverageCard({
  coverage,
  pending,
  error,
}: {
  coverage?: StockCoverageResponse;
  pending: boolean;
  error: boolean;
}) {
  if (pending) {
    return (
      <Card className="mb-4 flex items-center gap-3 p-4" role="status">
        <CircleDashed className="text-blue size-4 animate-spin" />
        <p className="text-sm">正在核对研究覆盖情况</p>
      </Card>
    );
  }
  if (error || !coverage) {
    return (
      <Card className="mb-4 p-4">
        <p className="text-sm font-medium">暂时无法核对研究覆盖情况</p>
        <p className="text-slate mt-1 text-xs">
          下方已有研究内容仍可继续查阅。
        </p>
      </Card>
    );
  }
  const byKey = new Map(
    coverage.dimensions.map((item) => [item.dimension, item]),
  );
  const items = primaryDimensions
    .map((key) => byKey.get(key))
    .filter((item): item is CoverageDimension => Boolean(item));
  const ready = items.filter(
    (item) => item.availability === "ready" && item.freshness !== "stale",
  ).length;
  return (
    <Card className="mb-4 overflow-hidden">
      <div className="border-ink/8 flex items-start justify-between gap-4 border-b px-5 py-4">
        <div>
          <p className="font-data text-blue text-[10px] uppercase tracking-[0.18em]">
            Research coverage
          </p>
          <h2 className="font-display mt-1 text-lg font-semibold">研究覆盖</h2>
          <p className="text-slate mt-1 text-xs">
            展示事实数据、确定性研究与 AI 解读各自的准备状态，不构成评分。
          </p>
        </div>
        <span className="bg-mist font-data inline-flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1 text-xs">
          <CheckCircle2 className="text-blue size-3.5" /> {ready}/{items.length}
        </span>
      </div>
      <ul className="px-5">
        {items.map((item) => (
          <DimensionRow key={item.dimension} item={item} />
        ))}
      </ul>
      <div className="border-ink/8 bg-mist/60 text-slate flex items-center gap-2 border-t px-5 py-3 text-xs">
        <CalendarClock className="size-3.5 shrink-0" />
        截止 {new Date(coverage.knowledge_cutoff).toLocaleString("zh-CN")}
      </div>
    </Card>
  );
}
