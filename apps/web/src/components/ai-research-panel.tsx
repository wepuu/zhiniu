"use client";

import {
  createZhaoniuClient,
  type AIResearchEnvelope,
  type CitedText,
  type EvidenceIndexEntry,
  type ExplanationEvidence,
  type ExplanationRequestResponse,
} from "@zhaoniu/api-client";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Bot,
  CalendarClock,
  CircleAlert,
  Database,
  FileSearch,
  Link2,
  LockKeyhole,
  MessageSquareText,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  X,
} from "lucide-react";
import { useRef, useState } from "react";

import { formatEvidenceValue } from "@/lib/research";
import {
  financialMetricLabel,
  providerDisplayName,
  translateEnum,
} from "@/lib/presentation";

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
        <span className="text-slate text-xs">
          {translateEnum("status", envelope.status)}
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

function StockHealthPanel({
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
              <p className="mt-4 text-xs font-medium text-white/60">
                证据约束研究摘要
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
              生成服务：{providerDisplayName(output.provider_display_name)} ·
              模型：
              <span className="font-data">{output.model_display_name}</span>
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
                    {financialMetricLabel(
                      metric.metric_code,
                      metric.display_name,
                    )}{" "}
                    ·{" "}
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

function AssistantCitation({
  references,
  evidence,
  onOpen,
}: {
  references: string[];
  evidence: Map<string, ExplanationEvidence>;
  onOpen: (item: ExplanationEvidence) => void;
}) {
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {references.map((reference) => {
        const item = evidence.get(reference);
        return item ? (
          <button
            key={reference}
            type="button"
            onClick={() => onOpen(item)}
            className="border-ink/10 bg-mist/60 text-blue hover:border-blue/40 min-h-8 rounded-full border px-2.5 py-1 font-mono text-[10px] transition"
          >
            {reference}
          </button>
        ) : null;
      })}
    </div>
  );
}

function AssistantEvidencePanel({
  item,
  compact,
  onClose,
}: {
  item: ExplanationEvidence;
  compact: boolean;
  onClose: () => void;
}) {
  return (
    <aside
      className={
        compact
          ? "bg-paper fixed inset-x-0 bottom-0 z-50 max-h-[72vh] overflow-y-auto rounded-t-3xl border-t border-black/10 p-5 shadow-2xl"
          : "border-ink/10 bg-paper sticky top-24 rounded-2xl border p-5"
      }
      aria-label="引用证据详情"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-data text-blue text-[10px] uppercase tracking-[0.15em]">
            {item.evidence_id}
          </p>
          <h3 className="font-display mt-2 text-lg font-semibold">
            {item.title}
          </h3>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="border-ink/10 grid size-9 shrink-0 place-items-center rounded-full border"
          aria-label="关闭证据"
        >
          <X className="size-4" />
        </button>
      </div>
      <p className="text-slate mt-4 text-sm leading-7">{item.summary}</p>
      <dl className="border-ink/8 mt-5 space-y-3 border-t pt-4 text-xs">
        <div className="flex justify-between gap-4">
          <dt className="text-slate">证据类型</dt>
          <dd>{translateEnum("source_kind", item.source_kind)}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-slate">系统已知时间</dt>
          <dd className="font-data text-right">
            {new Date(item.known_at).toLocaleString("zh-CN")}
          </dd>
        </div>
      </dl>
    </aside>
  );
}

function ResearchAssistant({
  symbol,
  compact,
}: {
  symbol: string;
  compact: boolean;
}) {
  const [request, setRequest] = useState<ExplanationRequestResponse>();
  const [selected, setSelected] = useState<ExplanationEvidence>();
  const catalog = useQuery({
    queryKey: ["stock", symbol, "ai-explanation-questions"],
    queryFn: () => api.getAIExplanationQuestions(symbol),
    retry: false,
  });
  const requestQuery = useQuery({
    queryKey: ["stock", symbol, "ai-explanation-request", request?.id],
    queryFn: () => api.getAIExplanationRequest(symbol, request!.id),
    enabled: Boolean(
      request && ["pending", "building"].includes(request.status),
    ),
    refetchInterval: 2000,
  });
  const currentRequest = requestQuery.data ?? request;
  const create = useMutation({
    mutationFn: (questionKey: string) =>
      api.createAIExplanationRequest(symbol, {
        question_key: questionKey as
          | "recent_research_changes"
          | "fundamental_changes"
          | "corporate_event_context"
          | "peer_position_context",
        client_request_id: crypto.randomUUID(),
      }),
    onSuccess: setRequest,
  });
  const retry = useMutation({
    mutationFn: () => api.retryAIExplanationRequest(symbol, currentRequest!.id),
    onSuccess: setRequest,
  });

  if (catalog.isPending) {
    return (
      <Card className="grid min-h-64 place-items-center p-8" role="status">
        <RefreshCw className="text-blue size-6 animate-spin" />
      </Card>
    );
  }
  if (catalog.isError || !catalog.data) {
    return (
      <Card className="p-6">
        <AILabel />
        <h2 className="font-display mt-5 text-xl font-semibold">
          登录后使用研究助手
        </h2>
        <p className="text-slate mt-2 text-sm leading-6">
          研究助手会保存你的请求状态，但共享同一份不含私人数据的研究结果。
        </p>
      </Card>
    );
  }
  const data = catalog.data;
  if (!data.enabled) {
    return (
      <Card className="overflow-hidden">
        <div className="border-ink/8 flex items-center justify-between border-b px-5 py-4">
          <AILabel />
          <span className="font-data text-slate text-[10px] uppercase">
            {data.access}
          </span>
        </div>
        <div className="px-6 py-10 text-center">
          <LockKeyhole className="text-slate mx-auto size-7" />
          <h2 className="font-display mt-4 text-2xl font-semibold">
            {data.access === "contact_support"
              ? "研究助手属于高级功能"
              : "研究助手暂未启用"}
          </h2>
          <p className="text-slate mx-auto mt-2 max-w-lg text-sm leading-6">
            {data.access === "contact_support"
              ? "请联系客服获取激活码，页面不会展示订阅价格或支付入口。"
              : "DeepSeek 服务尚未通过当前部署的启用门禁，确定性研究仍可正常使用。"}
          </p>
          {data.support_contact_url && data.access === "contact_support" && (
            <a
              className="bg-ink mt-5 inline-flex rounded-xl px-4 py-2 text-sm text-white"
              href={data.support_contact_url}
            >
              联系客服
            </a>
          )}
        </div>
      </Card>
    );
  }

  const output = currentRequest?.output;
  const evidence = new Map(
    (output?.evidence_index ?? []).map((item) => [item.evidence_id, item]),
  );
  return (
    <div>
      <Card className="overflow-hidden">
        <div className="bg-ink px-5 py-5 text-white">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <AILabel />
              <h2 className="font-display mt-4 text-2xl font-semibold">
                选择一个研究问题
              </h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-white/60">
                固定问题会锁定证据范围；不接收自由文本，也不回答价格与交易问题。
              </p>
            </div>
            <span className="rounded-full bg-white/10 px-3 py-1 text-[10px]">
              今日剩余 {data.remaining_today} 次
            </span>
          </div>
        </div>
        <div
          className={`grid gap-px bg-black/10 ${compact ? "grid-cols-1" : "sm:grid-cols-2"}`}
        >
          {data.questions.map((question) => (
            <button
              key={question.key}
              type="button"
              disabled={
                question.coverage !== "available" ||
                create.isPending ||
                data.remaining_today === 0
              }
              onClick={() => create.mutate(question.key)}
              className="bg-paper hover:bg-mist/70 disabled:text-slate group min-h-32 p-5 text-left transition disabled:cursor-not-allowed"
            >
              <div className="flex items-start justify-between gap-4">
                <MessageSquareText className="text-blue size-4" />
                <span className="text-slate text-[10px]">
                  {question.coverage === "available" ? "证据可用" : "证据不足"}
                </span>
              </div>
              <p className="mt-4 text-sm font-semibold">{question.label}</p>
              <p className="text-slate mt-1 text-xs leading-5">
                {question.description}
              </p>
            </button>
          ))}
        </div>
      </Card>

      {(create.isPending ||
        currentRequest?.status === "pending" ||
        currentRequest?.status === "building") && (
        <Card className="mt-4 flex items-center gap-4 p-5" role="status">
          <RefreshCw className="text-blue size-5 animate-spin" />
          <div>
            <p className="text-sm font-semibold">正在核对证据并生成解释</p>
            <p className="text-slate mt-1 text-xs">
              可以离开页面，任务状态会被保留。
            </p>
          </div>
        </Card>
      )}
      {(create.isError || currentRequest?.status === "failed") && (
        <Card className="border-risk/25 mt-4 p-5" role="alert">
          <p className="text-sm font-semibold">研究解释暂时不可用</p>
          <p className="text-slate mt-1 text-xs">
            系统没有保存未通过校验的内容。
          </p>
          {currentRequest?.status === "failed" && (
            <button
              type="button"
              disabled={retry.isPending}
              onClick={() => retry.mutate()}
              className="bg-ink mt-4 rounded-xl px-4 py-2 text-xs text-white"
            >
              显式重试
            </button>
          )}
        </Card>
      )}
      {output && (
        <div
          className={`mt-4 grid gap-4 ${selected && !compact ? "lg:grid-cols-[minmax(0,1fr)_22rem]" : "grid-cols-1"}`}
        >
          <Card className="overflow-hidden">
            <div className="border-ink/8 border-b px-5 py-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <AILabel />
                <span className="bg-mist rounded-full px-3 py-1 text-[10px]">
                  {output.freshness === "stale"
                    ? "已有新证据 · 内容陈旧"
                    : "证据仍为当前"}
                </span>
              </div>
              <h2 className="font-display mt-4 text-2xl font-semibold leading-tight">
                {output.content.headline.text}
              </h2>
              <AssistantCitation
                references={output.content.headline.evidence_refs}
                evidence={evidence}
                onOpen={setSelected}
              />
              <p className="text-slate mt-4 text-[10px]">
                生成服务：{providerDisplayName(output.provider_display_name)} ·
                模型：
                <span className="font-data">{output.model_display_name}</span> ·
                数据截止{" "}
                {new Date(output.knowledge_cutoff).toLocaleString("zh-CN")}
              </p>
            </div>
            <div className="space-y-5 px-5 py-5">
              {output.content.summary.map((item, index) => (
                <div
                  key={`${item.text}-${index}`}
                  className="border-blue/25 border-l-2 pl-4"
                >
                  <p className="text-sm leading-7">{item.text}</p>
                  <AssistantCitation
                    references={item.evidence_refs}
                    evidence={evidence}
                    onOpen={setSelected}
                  />
                </div>
              ))}
              {output.content.interpretations.map((item) => (
                <div
                  key={item.focus_key}
                  className="bg-mist/60 rounded-2xl p-4"
                >
                  <p className="text-slate text-[10px] uppercase tracking-[0.14em]">
                    {item.focus_key}
                  </p>
                  <p className="mt-2 text-sm leading-7">
                    {item.explanation.text}
                  </p>
                  <AssistantCitation
                    references={item.explanation.evidence_refs}
                    evidence={evidence}
                    onOpen={setSelected}
                  />
                </div>
              ))}
              <div className="border-ink/8 border-t pt-4">
                {output.limitations.map((item) => (
                  <p key={item} className="text-slate text-xs leading-6">
                    {item}
                  </p>
                ))}
              </div>
            </div>
          </Card>
          {selected && (
            <AssistantEvidencePanel
              item={selected}
              compact={compact}
              onClose={() => setSelected(undefined)}
            />
          )}
        </div>
      )}
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
  const [mode, setMode] = useState<"health" | "assistant">("health");
  return (
    <div>
      <div
        className="bg-mist mb-4 inline-flex rounded-xl p-1"
        role="tablist"
        aria-label="AI 研究模式"
      >
        {(
          [
            ["health", "股票体检"],
            ["assistant", "研究助手"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={mode === key}
            onClick={() => setMode(key)}
            className={`min-h-10 rounded-lg px-4 text-sm font-medium transition ${mode === key ? "bg-paper text-ink shadow-sm" : "text-slate"}`}
          >
            {label}
          </button>
        ))}
      </div>
      {mode === "health" ? (
        <StockHealthPanel
          symbol={symbol}
          envelope={envelope}
          compact={compact}
        />
      ) : (
        <ResearchAssistant symbol={symbol} compact={compact} />
      )}
    </div>
  );
}
