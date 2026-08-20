"use client";

import {
  createZhaoniuClient,
  type ResearchObservation,
  type ResearchSnapshotEnvelope,
} from "@zhaoniu/api-client";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  BookOpenCheck,
  CalendarClock,
  Database,
  FlaskConical,
  Layers3,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { formatEvidenceValue } from "@/lib/research";

import { Card } from "./ui/card";

const api = createZhaoniuClient();

const dimensionCopy: Record<ResearchObservation["dimension"], string> = {
  growth: "成长",
  profitability: "盈利能力",
  quality: "经营质量",
  balance: "资产负债",
  valuation: "估值",
};

const attentionCopy: Record<ResearchObservation["attention_level"], string> = {
  info: "信息",
  notice: "留意",
  important: "重点",
};

function MovementIcon({
  movement,
}: {
  movement: ResearchObservation["movement"];
}) {
  const className =
    movement === "up" || movement === "crossed_up"
      ? "text-blue"
      : movement === "down" || movement === "crossed_down"
        ? "text-risk"
        : "text-slate";
  if (movement === "up" || movement === "crossed_up") {
    return <ArrowUpRight className={`size-4 ${className}`} />;
  }
  if (movement === "down" || movement === "crossed_down") {
    return <ArrowDownRight className={`size-4 ${className}`} />;
  }
  return <ArrowRight className={`size-4 ${className}`} />;
}

function ChangeCard({
  observation,
  onOpen,
}: {
  observation: ResearchObservation;
  onOpen: (opener: HTMLButtonElement) => void;
}) {
  return (
    <button
      type="button"
      className="border-ink/10 bg-paper hover:border-blue/45 group w-full rounded-2xl border p-5 text-left shadow-[0_1px_1px_rgba(24,32,43,0.03)] transition hover:-translate-y-0.5 hover:shadow-[0_12px_32px_rgba(41,95,143,0.09)]"
      onClick={(event) => onOpen(event.currentTarget)}
      aria-label={`查看证据：${observation.title}`}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="bg-mist text-slate rounded-full px-2.5 py-1 text-[10px]">
            {dimensionCopy[observation.dimension]}
          </span>
          <span
            className={`rounded-full px-2.5 py-1 text-[10px] ${
              observation.attention_level === "important"
                ? "bg-risk/10 text-risk"
                : observation.attention_level === "notice"
                  ? "bg-amber/10 text-amber"
                  : "bg-blue/10 text-blue"
            }`}
          >
            {attentionCopy[observation.attention_level]}
          </span>
        </div>
        <MovementIcon movement={observation.movement} />
      </div>
      <h3 className="font-display mt-4 text-xl font-semibold tracking-tight">
        {observation.title}
      </h3>
      <p className="text-slate mt-2 line-clamp-2 text-sm leading-6">
        {observation.summary}
      </p>
      <div className="border-ink/8 mt-5 flex items-center justify-between border-t pt-3">
        <span className="font-data text-slate text-[10px] uppercase">
          {observation.current_period}
        </span>
        <span className="text-blue flex items-center gap-1 text-xs font-medium">
          查看证据链{" "}
          <ArrowRight className="size-3.5 transition group-hover:translate-x-0.5" />
        </span>
      </div>
    </button>
  );
}

function EvidenceBody({ observation }: { observation: ResearchObservation }) {
  const valuationSources = observation.evidence_metrics.flatMap((metric) =>
    (metric.input_valuation_ids ?? []).map((id) => ({
      id,
      period: metric.period_end,
      provider:
        typeof metric.detail?.provider === "string"
          ? metric.detail.provider
          : "provider",
      sampleCount:
        typeof metric.detail?.sample_count === "number"
          ? metric.detail.sample_count
          : undefined,
    })),
  );
  return (
    <div className="pb-8">
      <div className="bg-ink px-6 pb-6 pt-5 text-white">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="font-data text-[10px] uppercase tracking-[0.2em] text-white/50">
              Evidence trace · {observation.rule_id}
            </p>
            <h2 className="font-display mt-3 text-2xl font-semibold">
              {observation.title}
            </h2>
          </div>
        </div>
        <p className="mt-3 text-sm leading-6 text-white/70">
          {observation.summary}
        </p>
      </div>

      <div className="relative px-6 pt-7 before:absolute before:bottom-8 before:left-[37px] before:top-10 before:w-px before:bg-[linear-gradient(to_bottom,rgba(41,95,143,.45),rgba(41,95,143,.08))]">
        <section className="relative pl-10">
          <span className="bg-paper border-blue text-blue absolute left-0 top-0 grid size-6 place-items-center rounded-full border">
            <BookOpenCheck className="size-3.5" />
          </span>
          <p className="text-slate text-[10px] uppercase tracking-[0.16em]">
            规则结论
          </p>
          <p className="mt-2 text-sm font-medium leading-6">
            {observation.summary}
          </p>
        </section>

        <section className="relative mt-8 pl-10">
          <span className="bg-paper border-blue text-blue absolute left-0 top-0 grid size-6 place-items-center rounded-full border">
            <Layers3 className="size-3.5" />
          </span>
          <p className="text-slate text-[10px] uppercase tracking-[0.16em]">
            指标输入
          </p>
          <div className="border-ink/10 mt-3 overflow-hidden rounded-xl border">
            {observation.evidence_metrics.map((metric, index) => (
              <div
                key={`${metric.metric_point_id}-${metric.role}`}
                className={`flex items-start justify-between gap-4 px-4 py-3 ${index ? "border-ink/8 border-t" : ""}`}
              >
                <div>
                  <p className="text-sm font-medium">{metric.display_name}</p>
                  <p className="font-data text-slate mt-1 text-[10px]">
                    {metric.period_end} · {metric.role}
                  </p>
                </div>
                <p className="font-data text-sm font-semibold">
                  {formatEvidenceValue(metric.value, metric.unit)}
                </p>
              </div>
            ))}
          </div>
        </section>

        <section className="relative mt-8 pl-10">
          <span className="bg-paper border-blue text-blue absolute left-0 top-0 grid size-6 place-items-center rounded-full border">
            <FlaskConical className="size-3.5" />
          </span>
          <p className="text-slate text-[10px] uppercase tracking-[0.16em]">
            确定性计算
          </p>
          <div className="bg-mist mt-3 rounded-xl p-4">
            <p className="text-sm font-medium">
              {observation.calculation.method}
            </p>
            <code className="font-data text-slate mt-2 block break-words text-[11px] leading-5">
              {observation.calculation.expression}
            </code>
            {observation.calculation.change_value && (
              <p className="font-data text-blue mt-2 text-sm font-semibold">
                变化 {observation.calculation.change_value}
                {observation.calculation.change_unit === "percentage_point"
                  ? " 个百分点"
                  : ""}
              </p>
            )}
          </div>
        </section>

        <section className="relative mt-8 pl-10">
          <span className="bg-paper border-blue text-blue absolute left-0 top-0 grid size-6 place-items-center rounded-full border">
            <Database className="size-3.5" />
          </span>
          <p className="text-slate text-[10px] uppercase tracking-[0.16em]">
            来源记录
          </p>
          {observation.evidence_sources.length ? (
            <div className="mt-3 space-y-3">
              {observation.evidence_sources.map((source) => (
                <div
                  key={source.report_id}
                  className="border-ink/10 rounded-xl border p-4 text-sm"
                >
                  <p className="font-medium">
                    {source.provider} 规范化财报记录
                  </p>
                  <p className="text-slate font-data mt-1 break-all text-[10px]">
                    {source.provider_record_id}
                  </p>
                  <div className="text-slate mt-3 grid gap-1 text-xs">
                    <span>报告期 {source.period_end}</span>
                    <span>
                      公告时间{" "}
                      {new Date(source.published_at).toLocaleString("zh-CN")}
                    </span>
                    <span>
                      系统可知时间{" "}
                      {new Date(source.known_at).toLocaleString("zh-CN")}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : valuationSources.length ? (
            <div className="mt-3 space-y-3">
              {valuationSources.map((source) => (
                <div
                  key={source.id}
                  className="border-ink/10 rounded-xl border p-4 text-sm"
                >
                  <p className="font-medium">{source.provider} 估值观测记录</p>
                  <p className="text-slate font-data mt-1 break-all text-[10px]">
                    {source.id}
                  </p>
                  <div className="text-slate mt-3 grid gap-1 text-xs">
                    <span>观测日 {source.period}</span>
                    {source.sampleCount != null && (
                      <span>有效窗口样本 {source.sampleCount} 个观测日</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate mt-3 text-sm">
              当前观察没有可展示的来源引用。
            </p>
          )}
        </section>
      </div>
    </div>
  );
}

export function EvidenceSheet({
  observation,
  compact,
  pending,
  error,
  onRetry,
  onClose,
}: {
  observation?: ResearchObservation;
  compact: boolean;
  pending: boolean;
  error: boolean;
  onRetry: () => void;
  onClose: () => void;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-50" role="presentation">
      <button
        type="button"
        aria-label="关闭证据详情"
        className="absolute inset-0 bg-black/35"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="变化证据详情"
        className={
          compact
            ? "bg-paper absolute inset-x-0 bottom-0 max-h-[88vh] overflow-y-auto rounded-t-3xl shadow-2xl"
            : "bg-paper absolute inset-y-0 right-0 w-full max-w-[520px] overflow-y-auto shadow-2xl"
        }
      >
        <button
          ref={closeRef}
          type="button"
          aria-label="关闭"
          onClick={onClose}
          className="bg-paper/95 text-ink absolute right-4 top-4 z-10 grid size-9 place-items-center rounded-full shadow-sm"
        >
          <X className="size-4" />
        </button>
        {error ? (
          <div
            className="grid min-h-72 place-items-center px-6 text-center"
            role="alert"
          >
            <div>
              <p className="font-medium">证据详情暂时无法读取</p>
              <button
                type="button"
                className="bg-ink mt-4 rounded-xl px-4 py-2 text-sm text-white"
                onClick={onRetry}
              >
                重新读取
              </button>
            </div>
          </div>
        ) : pending || !observation ? (
          <div className="grid min-h-72 place-items-center" role="status">
            <p className="text-slate text-sm">正在读取不可变证据快照…</p>
          </div>
        ) : (
          <EvidenceBody observation={observation} />
        )}
      </div>
    </div>
  );
}

export function ResearchChanges({
  symbol,
  envelope,
  compact = false,
}: {
  symbol: string;
  envelope: ResearchSnapshotEnvelope;
  compact?: boolean;
}) {
  const [selectedId, setSelectedId] = useState<string>();
  const openerRef = useRef<HTMLButtonElement | undefined>(undefined);
  const detail = useQuery({
    queryKey: ["stock", symbol, "research-observation", selectedId],
    queryFn: () => api.getResearchObservation(symbol, selectedId!),
    enabled: Boolean(selectedId),
  });
  const close = () => {
    setSelectedId(undefined);
    requestAnimationFrame(() => openerRef.current?.focus());
  };

  if (envelope.status === "not_built" || !envelope.snapshot) {
    return (
      <Card className="grid min-h-72 place-items-center p-8 text-center">
        <div>
          <CalendarClock className="text-slate mx-auto size-6" />
          <h2 className="font-display mt-4 text-xl font-semibold">
            研究快照尚未生成
          </h2>
          <p className="text-slate mt-2 max-w-md text-sm leading-6">
            完成确定性研究快照构建后，这里会按当前可知数据展示关键变化。
          </p>
        </div>
      </Card>
    );
  }

  const snapshot = envelope.snapshot;
  return (
    <div>
      <div className="border-ink/10 bg-paper mb-4 flex flex-wrap items-end justify-between gap-4 rounded-2xl border px-5 py-4">
        <div>
          <p className="font-data text-blue text-[10px] uppercase tracking-[0.18em]">
            Deterministic change engine
          </p>
          <h2 className="font-display mt-1 text-2xl font-semibold">关键变化</h2>
          <p className="text-slate mt-1 text-xs">
            截至 {new Date(snapshot.knowledge_cutoff).toLocaleString("zh-CN")}{" "}
            的可知信息
          </p>
        </div>
        <div className="text-right">
          <p className="font-data text-sm font-semibold">
            {snapshot.observations.length} 条
          </p>
          <p className="text-slate mt-1 text-[10px]">
            规则集 {snapshot.rule_set_version.split(":").at(-1)?.slice(0, 8)}
          </p>
        </div>
      </div>

      {snapshot.observations.length ? (
        <div
          className={`grid gap-4 ${compact ? "grid-cols-1" : "lg:grid-cols-2"}`}
        >
          {snapshot.observations.map((observation) => (
            <ChangeCard
              key={observation.id}
              observation={observation}
              onOpen={(opener) => {
                openerRef.current = opener;
                setSelectedId(observation.id);
              }}
            />
          ))}
        </div>
      ) : (
        <Card className="grid min-h-64 place-items-center p-8 text-center">
          <div>
            <BookOpenCheck className="text-blue mx-auto size-6" />
            <h3 className="font-display mt-4 text-xl font-semibold">
              当前没有需单独列出的变化
            </h3>
            <p className="text-slate mt-2 max-w-md text-sm leading-6">
              现有证据未触发已启用规则。这不代表公司基本面没有变化，也不构成投资判断。
            </p>
          </div>
        </Card>
      )}

      <div className="text-slate mt-4 flex items-start gap-2 text-xs leading-5">
        <FlaskConical className="mt-0.5 size-3.5 shrink-0" />
        <p>
          结论由版本化规则和确定性代码生成；证据引用原始报表或估值观测，未使用
          AI 计算指标。
        </p>
      </div>

      {selectedId && (
        <EvidenceSheet
          compact={compact}
          observation={detail.data}
          pending={detail.isPending}
          error={detail.isError}
          onRetry={() => void detail.refetch()}
          onClose={close}
        />
      )}
    </div>
  );
}
