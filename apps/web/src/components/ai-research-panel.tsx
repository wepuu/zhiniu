"use client";

import {
  createZhaoniuClient,
  type AIResearchEnvelope,
  type CitedText,
  type EvidenceIndexEntry,
} from "@zhaoniu/api-client";
import { useQuery } from "@tanstack/react-query";
import {
  Bot,
  CalendarClock,
  CircleAlert,
  Database,
  FileSearch,
  Link2,
  LockKeyhole,
  RefreshCw,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { useRef, useState } from "react";

import { formatEvidenceValue } from "@/lib/research";

import { EvidenceSheet } from "./research-changes";
import { Card } from "./ui/card";

const api = createZhaoniuClient();

const dimensionCopy = {
  growth: "成长",
  profitability: "盈利能力",
  quality: "经营质量",
  balance: "资产负债",
  valuation: "估值",
} as const;

const coverageCopy = {
  available: "证据可用",
  missing: "数据缺失",
  not_applicable: "模板不适用",
  insufficient_history: "历史不足",
  provider_unavailable: "数据源不可用",
} as const;

function AILabel() {
  return (
    <span className="border-blue/25 bg-blue/8 text-blue inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] font-semibold">
      <Sparkles className="size-3" />
      AI 生成内容
    </span>
  );
}

function AIState({ envelope }: { envelope: AIResearchEnvelope }) {
  const copy = {
    disabled: {
      icon: LockKeyhole,
      title: "AI 研究尚未启用",
      detail: "当前部署没有配置可用模型链；关键变化仍由确定性规则提供。",
    },
    not_built: {
      icon: CalendarClock,
      title: "AI 解读尚未生成",
      detail:
        envelope.reason === "deterministic_snapshot_missing"
          ? "需要先生成确定性研究快照，AI 才能在固定证据边界内解读。"
          : "后台研究任务完成后，结构化解读会显示在这里。",
    },
    building: {
      icon: RefreshCw,
      title: "AI 研究正在构建",
      detail: "系统正在校验证据引用与安全边界，无需停留在本页等待。",
    },
    failed: {
      icon: CircleAlert,
      title: "本次 AI 研究未通过",
      detail: "生成或安全校验失败，未保存任何半成品内容。",
    },
    unsupported: {
      icon: ShieldAlert,
      title: "当前发行人模板暂不支持",
      detail: "系统没有套用不匹配的研究模板，也没有调用语言模型。",
    },
  } as const;
  const state = copy[envelope.status as keyof typeof copy];
  if (!state) return null;
  const Icon = state.icon;
  return (
    <Card className="overflow-hidden">
      <div className="border-ink/8 bg-paper flex items-center justify-between border-b px-5 py-4">
        <AILabel />
        <span className="font-data text-slate text-[10px] uppercase">
          {envelope.status}
        </span>
      </div>
      <div className="grid min-h-64 place-items-center px-6 py-10 text-center">
        <div className="max-w-lg">
          <Icon
            className={`mx-auto size-7 ${envelope.status === "building" ? "text-blue animate-spin" : "text-slate"}`}
          />
          <h2 className="font-display mt-4 text-2xl font-semibold">
            {state.title}
          </h2>
          <p className="text-slate mt-2 text-sm leading-6">{state.detail}</p>
          <p className="text-slate mt-5 text-xs">
            本页不提供匿名生成或重算入口。
          </p>
        </div>
      </div>
    </Card>
  );
}

function CitationLinks({
  content,
  evidence,
  onOpen,
}: {
  content: CitedText;
  evidence: Map<string, EvidenceIndexEntry>;
  onOpen: (item: EvidenceIndexEntry, opener: HTMLButtonElement) => void;
}) {
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {content.evidence_refs.map((reference) => {
        const item = evidence.get(reference);
        if (!item) return null;
        return (
          <button
            key={reference}
            type="button"
            onClick={(event) => onOpen(item, event.currentTarget)}
            className="border-ink/10 bg-mist/60 text-slate hover:border-blue/40 hover:text-blue inline-flex min-h-8 items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] transition"
            aria-label={`查看 AI 引用证据：${item.title}`}
          >
            <Link2 className="size-3" />
            {reference}
          </button>
        );
      })}
    </div>
  );
}

export function AIResearchPanel({
  symbol,
  envelope,
  compact = false,
}: {
  symbol: string;
  envelope: AIResearchEnvelope;
  compact?: boolean;
}) {
  const [selected, setSelected] = useState<EvidenceIndexEntry>();
  const openerRef = useRef<HTMLButtonElement | undefined>(undefined);
  const detail = useQuery({
    queryKey: [
      "stock",
      symbol,
      "research-observation",
      selected?.observation_id,
    ],
    queryFn: () => api.getResearchObservation(symbol, selected!.observation_id),
    enabled: Boolean(selected),
  });

  if (envelope.status !== "ready" || !envelope.output) {
    return <AIState envelope={envelope} />;
  }

  const output = envelope.output;
  const evidence = new Map(
    output.evidence_index.map((item) => [item.evidence_id, item]),
  );
  const openEvidence = (
    item: EvidenceIndexEntry,
    opener: HTMLButtonElement,
  ) => {
    openerRef.current = opener;
    setSelected(item);
  };
  const closeEvidence = () => {
    setSelected(undefined);
    requestAnimationFrame(() => openerRef.current?.focus());
  };

  return (
    <div>
      <Card className="overflow-hidden">
        <div className="bg-ink relative overflow-hidden px-5 py-5 text-white">
          <div className="bg-blue/20 absolute -right-10 -top-16 size-44 rounded-full blur-2xl" />
          <div className="relative flex flex-wrap items-start justify-between gap-4">
            <div>
              <AILabel />
              <p className="font-data mt-4 text-[10px] uppercase tracking-[0.18em] text-white/50">
                Evidence-bound research memo
              </p>
              <h2 className="font-display mt-1 max-w-3xl text-2xl font-semibold leading-tight">
                {output.content.headline.text}
              </h2>
              <CitationLinks
                content={output.content.headline}
                evidence={evidence}
                onOpen={openEvidence}
              />
            </div>
            <span
              className={`rounded-full px-3 py-1 text-[10px] font-semibold ${envelope.freshness === "stale" ? "bg-amber text-ink" : "bg-white/10 text-white"}`}
            >
              {envelope.freshness === "stale"
                ? "已有新证据 · 内容陈旧"
                : "相对最新快照"}
            </span>
          </div>
        </div>
        <dl
          className={`border-ink/8 grid border-b ${compact ? "grid-cols-1" : "sm:grid-cols-3"}`}
        >
          <div className="px-5 py-3">
            <dt className="text-slate text-[10px]">实际模型</dt>
            <dd className="mt-1 text-xs font-medium">
              {output.provider_display_name} · {output.model_display_name}
            </dd>
          </div>
          <div className="border-ink/8 px-5 py-3 sm:border-l">
            <dt className="text-slate text-[10px]">生成时间</dt>
            <dd className="font-data mt-1 text-xs">
              {new Date(output.generated_at).toLocaleString("zh-CN")}
            </dd>
          </div>
          <div className="border-ink/8 px-5 py-3 sm:border-l">
            <dt className="text-slate text-[10px]">数据截止</dt>
            <dd className="font-data mt-1 text-xs">
              {new Date(output.knowledge_cutoff).toLocaleString("zh-CN")}
            </dd>
          </div>
        </dl>
        <div className="px-5 py-5">
          <p className="text-slate text-[10px] uppercase tracking-[0.16em]">
            摘要
          </p>
          <div className="mt-3 space-y-4">
            {output.content.executive_summary.map((item, index) => (
              <div
                key={`${item.text}-${index}`}
                className="border-blue/25 border-l-2 pl-4"
              >
                <p className="text-sm leading-7">{item.text}</p>
                <CitationLinks
                  content={item}
                  evidence={evidence}
                  onOpen={openEvidence}
                />
              </div>
            ))}
          </div>
        </div>
      </Card>

      <div
        className={`mt-4 grid gap-4 ${compact ? "grid-cols-1" : "lg:grid-cols-2"}`}
      >
        {output.content.dimensions.map((item) => {
          const coverage = output.coverage.find(
            (entry) => entry.dimension === item.dimension,
          );
          return (
            <Card key={item.dimension} className="p-5">
              <div className="flex items-center justify-between gap-3">
                <h3 className="font-display text-lg font-semibold">
                  {dimensionCopy[item.dimension]}
                </h3>
                <span className="bg-mist text-slate rounded-full px-2.5 py-1 text-[10px]">
                  {coverage ? coverageCopy[coverage.status] : "覆盖未知"}
                </span>
              </div>
              {item.interpretation ? (
                <>
                  <p className="mt-3 text-sm leading-7">
                    {item.interpretation.text}
                  </p>
                  <CitationLinks
                    content={item.interpretation}
                    evidence={evidence}
                    onOpen={openEvidence}
                  />
                </>
              ) : (
                <p className="text-slate mt-3 text-sm leading-6">
                  {coverage?.reason ??
                    "当前没有足够的确定性证据支持该维度解读。"}
                </p>
              )}
            </Card>
          );
        })}
      </div>

      {(output.content.attention_items ?? []).length > 0 && (
        <Card className="mt-4 p-5">
          <div className="flex items-center gap-2">
            <FileSearch className="text-blue size-4" />
            <h3 className="font-display text-lg font-semibold">继续关注</h3>
          </div>
          <div className="divide-ink/8 mt-3 divide-y">
            {(output.content.attention_items ?? []).map((item, index) => (
              <div key={`${item.title.text}-${index}`} className="py-4">
                <p className="text-sm font-semibold">{item.title.text}</p>
                <p className="text-slate mt-1 text-sm leading-6">
                  {item.interpretation.text}
                </p>
                <CitationLinks
                  content={item.interpretation}
                  evidence={evidence}
                  onOpen={openEvidence}
                />
              </div>
            ))}
          </div>
        </Card>
      )}

      <Card className="mt-4 overflow-hidden">
        <div className="border-ink/8 flex items-center gap-2 border-b px-5 py-4">
          <Database className="text-blue size-4" />
          <h3 className="font-display text-lg font-semibold">确定性证据索引</h3>
        </div>
        <div
          className={`grid gap-px bg-[rgba(24,32,43,0.08)] ${compact ? "grid-cols-1" : "sm:grid-cols-2"}`}
        >
          {output.evidence_index.map((item) => (
            <button
              key={item.evidence_id}
              type="button"
              className="bg-paper hover:bg-mist/60 p-4 text-left transition"
              onClick={(event) => openEvidence(item, event.currentTarget)}
              aria-label={`查看 AI 引用证据：${item.title}`}
            >
              <p className="font-data text-blue text-[10px]">
                {item.evidence_id}
              </p>
              <p className="mt-1 text-sm font-medium">{item.title}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {item.evidence_metrics.map((metric) => (
                  <span
                    key={`${metric.metric_point_id}-${metric.role}`}
                    className="bg-mist rounded-lg px-2.5 py-1.5 text-[10px]"
                  >
                    {metric.display_name} ·{" "}
                    <strong className="font-data">
                      {formatEvidenceValue(metric.value, metric.unit)}
                    </strong>
                  </span>
                ))}
              </div>
            </button>
          ))}
        </div>
      </Card>

      <div className="text-slate mt-4 flex items-start gap-2 text-xs leading-5">
        <Bot className="mt-0.5 size-3.5 shrink-0" />
        <p>
          AI
          仅解释已选定的不可变快照；指标数值由确定性代码计算。内容不构成投资建议，仍需核对原始披露。
        </p>
      </div>

      {selected && (
        <EvidenceSheet
          compact={compact}
          observation={detail.data}
          pending={detail.isPending}
          error={detail.isError}
          onRetry={() => void detail.refetch()}
          onClose={closeEvidence}
        />
      )}
    </div>
  );
}
