"use client";

import type {
  PeerComparisonEnvelope,
  PeerMetricComparisonResponse,
} from "@zhaoniu/api-client";
import { Database, GitBranch, LineChart, Users } from "lucide-react";

import {
  formatPeerDecimal,
  formatPeerValue,
  peerStatusCopy,
} from "@/lib/peer-research";
import {
  financialMetricAbbreviation,
  financialMetricLabel,
  translateEnum,
} from "@/lib/presentation";

import { Card } from "./ui/card";

const dimensionNames: Record<string, string> = {
  growth: "成长",
  profitability: "盈利",
  quality: "质量",
  balance: "资产负债",
  valuation: "估值",
};

export function PeerResearchPanel({
  envelope,
  compact = false,
}: {
  envelope: PeerComparisonEnvelope;
  compact?: boolean;
}) {
  if (envelope.status !== "ready") {
    return (
      <Card className="p-6">
        <Users className="text-slate size-5" />
        <h3 className="mt-3 font-medium">{peerStatusCopy(envelope.status)}</h3>
        <p className="text-slate mt-2 text-sm">
          同行比较只使用已生成的确定性指标和可追溯行业分类，不在页面请求时临时计算。
        </p>
      </Card>
    );
  }
  const items = envelope.items ?? [];
  const available = items.filter((item) => item.status === "available");
  const insufficientPeerCount = items.filter(
    (item) => item.status === "insufficient_peers",
  ).length;
  const missingMetricCount = items.filter(
    (item) => item.status === "missing_metric",
  ).length;
  const grouped = groupByDimension(items);
  return (
    <div className="space-y-4">
      <Card className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-blue text-xs font-medium">同行业确定性基准</p>
            <h3 className="font-display mt-1 text-xl font-semibold">
              同行位置
            </h3>
            <p className="text-slate mt-2 text-sm">
              {envelope.industry?.industry_name ?? "未识别行业"} · 分类代码：
              <span className="font-data">
                {envelope.industry?.taxonomy_code ?? "待确认"}
              </span>{" "}
              · 样本来自同一模板和同一行业。
            </p>
          </div>
          <div className="bg-mist rounded-2xl px-4 py-3 text-right">
            <p className="text-slate text-xs">可用比较</p>
            <p className="font-data mt-1 text-2xl font-semibold">
              {available.length}/{envelope.total}
            </p>
          </div>
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <MiniFact
            icon={Users}
            label="行业体系"
            value={envelope.industry?.taxonomy_version ?? "—"}
          />
          <MiniFact
            icon={Database}
            label="知识截止"
            value={
              envelope.knowledge_cutoff
                ? new Date(envelope.knowledge_cutoff).toLocaleDateString(
                    "zh-CN",
                  )
                : "—"
            }
          />
          <MiniFact
            icon={GitBranch}
            label="同行范围指纹"
            value={envelope.peer_universe_fingerprint?.slice(0, 8) ?? "—"}
          />
        </div>
      </Card>
      {available.length === 0 ? (
        <Card className="p-6">
          <Database className="text-blue size-5" />
          <h4 className="font-display mt-3 text-lg font-semibold">
            同行有效样本不足
          </h4>
          <p className="text-slate mt-2 max-w-2xl text-sm leading-6">
            已识别同行范围，但本地数据库尚未覆盖同行公司的同口径指标点。系统不会用模拟数据生成中位数、分位或排名；补齐同行财务指标后，重新构建即可获得可比较结果。
          </p>
          <div className="mt-4 flex flex-wrap gap-2 text-xs">
            <span className="bg-mist rounded-full px-3 py-1.5">
              样本不足 {insufficientPeerCount}
            </span>
            <span className="bg-mist rounded-full px-3 py-1.5">
              公司指标缺失 {missingMetricCount}
            </span>
          </div>
        </Card>
      ) : (
        Object.entries(grouped).map(([dimension, items]) => (
          <Card key={dimension} className="p-5">
            <h4 className="font-display text-lg font-semibold">
              {dimensionNames[dimension] ?? dimension}
            </h4>
            <div
              className={`mt-4 grid gap-3 ${compact ? "" : "lg:grid-cols-2"}`}
            >
              {items.map((item) => (
                <PeerMetricCard key={item.metric_code} item={item} />
              ))}
            </div>
          </Card>
        ))
      )}
      <p className="text-slate text-xs">
        同行分位是数值位置，不代表投资质量排序；负市盈率等无效输入会被排除并记录在证据摘要中。
      </p>
    </div>
  );
}

function PeerMetricCard({ item }: { item: PeerMetricComparisonResponse }) {
  const available = item.status === "available";
  const abbreviation = financialMetricAbbreviation(item.metric_code);
  return (
    <div className="border-ink/10 rounded-2xl border p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium">
            {financialMetricLabel(item.metric_code)}
          </p>
          {abbreviation && (
            <p className="font-data text-slate mt-1 text-xs">{abbreviation}</p>
          )}
          <p className="text-slate mt-1 text-xs">
            {item.period_end ?? "—"} · {translateEnum("basis", item.basis)}
          </p>
        </div>
        <span className="bg-mist rounded-full px-2.5 py-1 text-[10px]">
          {peerStatusCopy(item.status)}
        </span>
      </div>
      {available ? (
        <>
          <div className="mt-4 grid grid-cols-2 gap-3">
            <MetricValue
              label="公司"
              value={formatPeerValue(
                item.company_value,
                item.unit,
                item.metric_code,
              )}
            />
            <MetricValue
              label="同行中位"
              value={formatPeerValue(
                item.peer_median,
                item.unit,
                item.metric_code,
              )}
            />
            <MetricValue
              label="下四分位（P25）"
              value={formatPeerValue(
                item.peer_p25,
                item.unit,
                item.metric_code,
              )}
            />
            <MetricValue
              label="上四分位（P75）"
              value={formatPeerValue(
                item.peer_p75,
                item.unit,
                item.metric_code,
              )}
            />
          </div>
          <DistributionBar percentile={Number(item.numeric_percentile ?? 0)} />
          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
            <span className="bg-blue/10 text-blue rounded-full px-2.5 py-1">
              {formatPeerDecimal(item.numeric_percentile, 1)}% 数值分位
            </span>
            <span className="bg-mist rounded-full px-2.5 py-1">
              数值排名 {item.numeric_rank_desc ?? "—"} / {item.sample_size + 1}
            </span>
            <span className="bg-mist rounded-full px-2.5 py-1">
              同行样本 {item.sample_size}
            </span>
          </div>
        </>
      ) : (
        <p className="text-slate mt-4 text-sm">
          {peerStatusCopy(item.status)}
          {item.reason ? `：${item.reason}` : ""}
        </p>
      )}
    </div>
  );
}

function DistributionBar({ percentile }: { percentile: number }) {
  const clamped = Math.max(0, Math.min(100, percentile));
  return (
    <div className="mt-4">
      <div className="relative h-2 rounded-full bg-slate-200">
        <div
          className="bg-blue absolute top-1/2 h-4 w-4 -translate-y-1/2 rounded-full shadow"
          style={{ left: `calc(${clamped}% - 0.5rem)` }}
        />
      </div>
      <div className="text-slate mt-1 flex justify-between text-xs">
        <span>下四分位</span>
        <span>中位数</span>
        <span>上四分位</span>
      </div>
    </div>
  );
}

function MetricValue({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-slate text-xs">{label}</p>
      <p className="font-data mt-1 text-base font-semibold">{value}</p>
    </div>
  );
}

function MiniFact({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof LineChart;
  label: string;
  value: string;
}) {
  return (
    <div className="border-ink/8 flex items-center gap-3 rounded-xl border px-3 py-2">
      <Icon className="text-blue size-4 shrink-0" />
      <div>
        <p className="text-slate text-[10px]">{label}</p>
        <p className="font-data text-xs">{value}</p>
      </div>
    </div>
  );
}

function groupByDimension(items: PeerMetricComparisonResponse[]) {
  return items.reduce<Record<string, PeerMetricComparisonResponse[]>>(
    (accumulator, item) => {
      accumulator[item.dimension] ??= [];
      accumulator[item.dimension].push(item);
      return accumulator;
    },
    {},
  );
}
