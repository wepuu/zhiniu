"use client";

import {
  ApiError,
  createZhaoniuClient,
  type ComparisonResponse,
} from "@zhaoniu/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeftRight,
  Bookmark,
  CheckCircle2,
  ChevronRight,
  FileSearch,
  LoaderCircle,
  ShieldAlert,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { Card } from "@/components/ui/card";
import {
  financialMetricLabel,
  formatFinancialValue,
  providerDisplayName,
  translateEnum,
} from "@/lib/presentation";

const api = createZhaoniuClient({ baseUrl: process.env.NEXT_PUBLIC_API_URL });

function newRequestId() {
  return crypto.randomUUID();
}

export function ComparisonLauncher({
  initialSymbol = "",
  initialRightSymbol = "",
}: {
  initialSymbol?: string;
  initialRightSymbol?: string;
}) {
  const router = useRouter();
  const [left, setLeft] = useState(initialSymbol);
  const [right, setRight] = useState(initialRightSymbol);
  const catalog = useQuery({
    queryKey: ["comparison-catalog"],
    queryFn: api.getComparisonCatalog,
  });
  const create = useMutation({
    mutationFn: () =>
      api.createComparison({
        left_symbol: left.trim(),
        right_symbol: right.trim(),
        include_ai: Boolean(catalog.data?.ai_available),
        client_request_id: newRequestId(),
      }),
    onSuccess: (response) => router.push(`/comparisons/${response.id}`),
  });
  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-7">
        <p className="text-blue text-xs font-medium">基于证据的确定性对比</p>
        <h1 className="font-display mt-2 text-3xl font-semibold md:text-4xl">
          公司研究对比
        </h1>
        <p className="text-slate mt-3 max-w-2xl text-sm leading-6">
          仅并列展示知识截止时间前、口径一致的确定性事实；缺失与不可比项会原样标注。
        </p>
      </div>
      <Card className="overflow-hidden">
        <div className="bg-ink p-5 text-white md:p-7">
          <div className="grid items-end gap-4 md:grid-cols-[1fr_auto_1fr]">
            <SymbolField
              label="公司 A"
              value={left}
              onChange={setLeft}
              placeholder="600519"
            />
            <ArrowLeftRight className="mx-auto mb-3 hidden size-5 text-white/55 md:block" />
            <SymbolField
              label="公司 B"
              value={right}
              onChange={setRight}
              placeholder="300750"
            />
          </div>
        </div>
        <div className="flex flex-col gap-4 p-5 md:flex-row md:items-center md:justify-between md:p-7">
          <div className="text-slate text-xs leading-5">
            <p>
              {catalog.data?.dimensions.join(" · ") ??
                "成长 · 盈利 · 现金流 · 资产负债 · 估值"}
            </p>
            <p className="mt-1">
              AI 解读：
              {catalog.data?.ai_available
                ? "可用（事实先行）"
                : "当前权益或服务未启用"}
            </p>
          </div>
          <button
            type="button"
            disabled={!left.trim() || !right.trim() || create.isPending}
            onClick={() => create.mutate()}
            className="bg-blue inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-45"
          >
            {create.isPending ? (
              <LoaderCircle className="size-4 animate-spin" />
            ) : (
              <FileSearch className="size-4" />
            )}
            生成对比研究
          </button>
        </div>
      </Card>
      {create.error && (
        <p
          className="border-risk/20 bg-risk/5 text-risk mt-4 rounded-xl border px-4 py-3 text-sm"
          role="alert"
        >
          {create.error instanceof ApiError && create.error.status === 403
            ? "当前账户没有对应权益，请联系客服开通高级研究能力。"
            : "无法创建对比，请确认两只股票已进入研究覆盖。"}
        </p>
      )}
      <ComparisonLibrary />
    </div>
  );
}

function ComparisonLibrary() {
  const history = useQuery({
    queryKey: ["comparisons", "recent"],
    queryFn: () => api.listComparisons(8),
  });
  const saved = useQuery({
    queryKey: ["saved-comparisons"],
    queryFn: api.listSavedComparisons,
  });
  const items = saved.data?.items ?? [];
  const recent = history.data?.items ?? [];
  if (!items.length && !recent.length) return null;
  return (
    <div className="mt-8 grid gap-5 lg:grid-cols-2">
      <Card className="p-5">
        <p className="text-blue text-xs font-medium">常用对比组合</p>
        <h2 className="font-display mt-2 text-xl font-semibold">已保存对比</h2>
        <div className="mt-4 space-y-2">
          {items.map((item) => (
            <Link
              key={item.id}
              href={`/comparisons?left=${encodeURIComponent(item.left_symbol)}&right=${encodeURIComponent(item.right_symbol)}`}
              className="border-ink/8 hover:border-blue/30 flex items-center justify-between rounded-xl border px-4 py-3 text-sm"
            >
              <span>
                <b className="block font-medium">{item.name}</b>
                <small className="text-slate font-data mt-1 block">
                  {item.left_symbol} / {item.right_symbol}
                </small>
              </span>
              <ChevronRight className="text-slate size-4" />
            </Link>
          ))}
        </div>
      </Card>
      <Card className="p-5">
        <p className="text-blue text-xs font-medium">最近生成记录</p>
        <h2 className="font-display mt-2 text-xl font-semibold">最近对比</h2>
        <div className="mt-4 space-y-2">
          {recent.map((item) => (
            <Link
              key={item.id}
              href={`/comparisons/${item.id}`}
              className="border-ink/8 hover:border-blue/30 flex items-center justify-between rounded-xl border px-4 py-3 text-sm"
            >
              <span>
                <b className="font-data block font-medium">
                  {item.left_symbol} / {item.right_symbol}
                </b>
                <small className="text-slate mt-1 block">
                  {item.status === "ready" || item.status === "partial"
                    ? "研究已就绪"
                    : "正在构建"}
                </small>
              </span>
              <ChevronRight className="text-slate size-4" />
            </Link>
          ))}
        </div>
      </Card>
    </div>
  );
}

function SymbolField({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}) {
  return (
    <label className="block">
      <span className="mb-2 block text-xs text-white/60">{label}</span>
      <input
        aria-label={label}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="bg-white/8 w-full rounded-xl border border-white/15 px-4 py-3 font-mono text-lg text-white placeholder:text-white/25 focus:border-white/45"
      />
    </label>
  );
}

export function ComparisonResult({ requestId }: { requestId: string }) {
  const query = useQuery({
    queryKey: ["comparison", requestId],
    queryFn: () => api.getComparison(requestId),
    refetchInterval: (state) =>
      ["pending", "building"].includes(state.state.data?.status ?? "")
        ? 1500
        : false,
  });
  if (query.isPending) return <ComparisonLoading />;
  if (query.isError || !query.data)
    return <ComparisonError onRetry={() => void query.refetch()} />;
  const comparison = query.data;
  if (["pending", "building"].includes(comparison.status))
    return <ComparisonLoading />;
  if (!comparison.snapshot)
    return <ComparisonError onRetry={() => void query.refetch()} />;
  return <ComparisonReady comparison={comparison} />;
}

function ComparisonReady({ comparison }: { comparison: ComparisonResponse }) {
  const snapshot = comparison.snapshot!;
  const snapshotMetrics = snapshot.metrics;
  const [selectedEvidence, setSelectedEvidence] = useState<string | null>(null);
  const evidence = (comparison.evidence ?? []).find(
    (item) => item.evidence_id === selectedEvidence,
  );
  const dimensions = useMemo(() => {
    const grouped = new Map<string, typeof snapshotMetrics>();
    for (const metric of snapshotMetrics)
      grouped.set(metric.dimension, [
        ...(grouped.get(metric.dimension) ?? []),
        metric,
      ]);
    return [...grouped.entries()];
  }, [snapshotMetrics]);
  return (
    <div>
      <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <Link
            href="/comparisons"
            className="text-blue inline-flex items-center gap-1 text-xs"
          >
            返回对比入口
          </Link>
          <p className="text-blue mt-4 text-xs font-medium">
            公司对比 · 规则版本{" "}
            <span className="font-data">{snapshot.profile_version}</span>
          </p>
          <h1 className="font-display mt-2 text-3xl font-semibold md:text-4xl">
            {snapshot.left.name} / {snapshot.right.name}
          </h1>
          <p className="text-slate mt-2 text-xs">
            知识截止{" "}
            {new Date(snapshot.knowledge_cutoff).toLocaleString("zh-CN")} ·{" "}
            {snapshot.same_industry
              ? "同一行业口径"
              : "跨行业，仅展示可验证事实"}
          </p>
        </div>
        <SaveComparison comparison={comparison} />
      </div>

      <div className="border-ink/10 bg-paper hidden overflow-hidden rounded-2xl border md:block">
        <div className="border-ink/10 bg-ink grid grid-cols-[220px_1fr_1fr] border-b px-5 py-4 text-white">
          <span className="text-xs text-white/55">研究维度</span>
          <CompanyHeading company={snapshot.left} />
          <CompanyHeading company={snapshot.right} />
        </div>
        {dimensions.map(([dimension, metrics]) => (
          <div key={dimension}>
            <div className="bg-mist border-ink/8 border-b px-5 py-2.5 text-xs font-medium">
              {dimension}
            </div>
            {metrics.map((metric) => (
              <div
                key={metric.code}
                className="border-ink/8 grid grid-cols-[220px_1fr_1fr] border-b px-5 py-4 last:border-b-0"
              >
                <MetricLabel
                  label={financialMetricLabel(metric.code, metric.label)}
                  comparability={metric.comparability}
                  reason={metric.reason}
                />
                <MetricValue
                  metricCode={metric.code}
                  value={metric.left}
                  onEvidence={setSelectedEvidence}
                />
                <MetricValue
                  metricCode={metric.code}
                  value={metric.right}
                  onEvidence={setSelectedEvidence}
                />
              </div>
            ))}
          </div>
        ))}
      </div>

      <div className="space-y-4 md:hidden">
        {dimensions.map(([dimension, metrics]) => (
          <Card key={dimension} className="overflow-hidden">
            <div className="bg-ink px-4 py-3 text-sm font-medium text-white">
              {dimension}
            </div>
            <div className="divide-ink/8 divide-y">
              {metrics.map((metric) => (
                <div key={metric.code} className="p-4">
                  <MetricLabel
                    label={financialMetricLabel(metric.code, metric.label)}
                    comparability={metric.comparability}
                    reason={metric.reason}
                  />
                  <div className="mt-3 grid grid-cols-2 gap-3">
                    <MetricValue
                      metricCode={metric.code}
                      compact
                      name={snapshot.left.name}
                      value={metric.left}
                      onEvidence={setSelectedEvidence}
                    />
                    <MetricValue
                      metricCode={metric.code}
                      compact
                      name={snapshot.right.name}
                      value={metric.right}
                      onEvidence={setSelectedEvidence}
                    />
                  </div>
                </div>
              ))}
            </div>
          </Card>
        ))}
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <AIComparison
          comparison={comparison}
          onEvidence={setSelectedEvidence}
        />
        <Card className="p-5">
          <p className="text-blue text-xs font-medium">确定性研究边界</p>
          <h2 className="font-display mt-2 text-xl font-semibold">
            口径与限制
          </h2>
          <ul className="text-slate mt-4 space-y-3 text-sm leading-6">
            {(snapshot.limitations.length
              ? snapshot.limitations
              : ["当前核心指标满足可比口径。"]
            ).map((item) => (
              <li key={item}>— {item}</li>
            ))}
          </ul>
        </Card>
      </div>
      {evidence && (
        <EvidenceSheet
          evidence={evidence}
          onClose={() => setSelectedEvidence(null)}
        />
      )}
    </div>
  );
}

function CompanyHeading({
  company,
}: {
  company: NonNullable<ComparisonResponse["snapshot"]>["left"];
}) {
  return (
    <div>
      <p className="font-display text-xl font-semibold">{company.name}</p>
      <p className="font-data mt-1 text-[10px] text-white/55">
        {company.symbol} · {company.industry_name ?? "行业待补充"}
      </p>
    </div>
  );
}

function MetricLabel({
  label,
  comparability,
  reason,
}: {
  label: string;
  comparability: string;
  reason?: string | null;
}) {
  return (
    <div>
      <p className="text-sm font-medium">{label}</p>
      <p
        className={`mt-1 text-[10px] ${comparability === "comparable" ? "text-emerald-700" : "text-amber"}`}
      >
        {comparability === "comparable" ? "口径一致" : (reason ?? "不可比")}
      </p>
    </div>
  );
}

function MetricValue({
  metricCode,
  value,
  onEvidence,
  compact = false,
  name,
}: {
  metricCode: string;
  value: NonNullable<ComparisonResponse["snapshot"]>["metrics"][number]["left"];
  onEvidence: (id: string) => void;
  compact?: boolean;
  name?: string;
}) {
  return (
    <div className={compact ? "bg-mist rounded-xl p-3" : "px-2"}>
      {name && <p className="text-slate mb-1 truncate text-[10px]">{name}</p>}
      <p className="font-data text-lg font-semibold">
        {formatFinancialValue({
          metricCode,
          value: value.value,
          unit: value.unit,
          context: "comparison",
        })}
      </p>
      <p className="text-slate mt-1 text-xs">
        {value.period_end ?? "期间缺失"} · {translateEnum("basis", value.basis)}
      </p>
      {value.evidence_ref && (
        <button
          type="button"
          className="text-blue mt-2 inline-flex items-center gap-1 text-[10px]"
          onClick={() => onEvidence(value.evidence_ref!)}
        >
          查看证据 <ChevronRight className="size-3" />
        </button>
      )}
    </div>
  );
}

function AIComparison({
  comparison,
  onEvidence,
}: {
  comparison: ComparisonResponse;
  onEvidence: (id: string) => void;
}) {
  const output = comparison.ai_output;
  return (
    <Card className="p-5 md:p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-blue text-xs font-medium">AI 生成内容</p>
          <h2 className="font-display mt-2 text-xl font-semibold">
            AI 对比解读
          </h2>
        </div>
        <span className="border-blue/20 bg-blue/5 text-blue rounded-full border px-2.5 py-1 text-[10px]">
          AI 生成内容
        </span>
      </div>
      {output ? (
        <div className="mt-5 space-y-5">
          <Cited
            item={output.content.headline}
            onEvidence={onEvidence}
            strong
          />
          {output.content.common_ground.map((item, index) => (
            <Cited
              key={`common-${index}`}
              item={item}
              onEvidence={onEvidence}
            />
          ))}
          {output.content.differences.map((item, index) => (
            <Cited key={`diff-${index}`} item={item} onEvidence={onEvidence} />
          ))}
          <p className="text-slate text-[10px]">
            生成服务：{providerDisplayName(output.provider)} · 模型：
            <span className="font-data">{output.model}</span> ·{" "}
            {new Date(output.generated_at).toLocaleString("zh-CN")}
          </p>
        </div>
      ) : (
        <div className="bg-mist mt-5 rounded-xl p-4 text-sm">
          <p className="font-medium">
            {comparison.ai_status === "disabled"
              ? "AI 对比解读当前未启用"
              : comparison.ai_status === "failed"
                ? "AI 解读暂时不可用"
                : "本次未请求 AI 解读"}
          </p>
          <p className="text-slate mt-1 text-xs">
            确定性对比结果仍可完整使用。
          </p>
        </div>
      )}
    </Card>
  );
}

function Cited({
  item,
  onEvidence,
  strong = false,
}: {
  item: { text: string; evidence_refs: string[] };
  onEvidence: (id: string) => void;
  strong?: boolean;
}) {
  return (
    <div>
      <p
        className={
          strong
            ? "font-display text-lg font-semibold leading-7"
            : "text-slate text-sm leading-6"
        }
      >
        {item.text}
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        {item.evidence_refs.map((ref) => (
          <button
            key={ref}
            type="button"
            onClick={() => onEvidence(ref)}
            className="bg-blue/7 text-blue rounded-full px-2 py-1 font-mono text-[9px]"
          >
            {ref}
          </button>
        ))}
      </div>
    </div>
  );
}

function SaveComparison({ comparison }: { comparison: ComparisonResponse }) {
  const client = useQueryClient();
  const save = useMutation({
    mutationFn: () =>
      api.saveComparison({
        name: `${comparison.snapshot?.left.name} / ${comparison.snapshot?.right.name}`,
        left_symbol: comparison.left_symbol,
        right_symbol: comparison.right_symbol,
      }),
    onSuccess: () =>
      client.invalidateQueries({ queryKey: ["saved-comparisons"] }),
  });
  return (
    <button
      type="button"
      onClick={() => save.mutate()}
      disabled={save.isPending || save.isSuccess}
      className="border-ink/10 bg-paper inline-flex min-h-10 items-center justify-center gap-2 rounded-xl border px-4 text-xs disabled:opacity-60"
    >
      {save.isSuccess ? (
        <CheckCircle2 className="size-4 text-emerald-700" />
      ) : (
        <Bookmark className="size-4" />
      )}
      {save.isSuccess ? "已保存" : "保存对比"}
    </button>
  );
}

function EvidenceSheet({
  evidence,
  onClose,
}: {
  evidence: NonNullable<ComparisonResponse["evidence"]>[number];
  onClose: () => void;
}) {
  return (
    <div className="bg-ink/30 fixed inset-0 z-50" onClick={onClose}>
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="对比证据"
        className="bg-paper absolute inset-x-0 bottom-0 rounded-t-3xl p-6 shadow-2xl md:inset-y-0 md:left-auto md:w-[420px] md:rounded-none"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="bg-ink/15 mx-auto mb-5 h-1 w-10 rounded-full md:hidden" />
        <p className="font-data text-blue text-[10px] uppercase tracking-[0.16em]">
          {evidence.evidence_id}
        </p>
        <h2 className="font-display mt-3 text-2xl font-semibold">
          {evidence.title}
        </h2>
        <dl className="text-slate mt-6 space-y-4 text-sm">
          <div>
            <dt className="text-xs">来源类型</dt>
            <dd className="text-ink mt-1">
              {translateEnum("source_kind", evidence.source_kind)}
            </dd>
          </div>
          <div>
            <dt className="text-xs">知识时间</dt>
            <dd className="text-ink mt-1">
              {new Date(evidence.known_at).toLocaleString("zh-CN")}
            </dd>
          </div>
        </dl>
        <Link
          href={evidence.evidence_path}
          className="bg-ink mt-7 inline-flex w-full items-center justify-center rounded-xl px-4 py-3 text-sm text-white"
        >
          回到原始研究证据
        </Link>
        <button
          type="button"
          onClick={onClose}
          className="text-slate mt-3 w-full py-2 text-sm"
        >
          关闭
        </button>
      </aside>
    </div>
  );
}

function ComparisonLoading() {
  return (
    <Card
      className="grid min-h-[420px] place-items-center p-8 text-center"
      role="status"
    >
      <div>
        <LoaderCircle className="text-blue mx-auto size-7 animate-spin" />
        <h1 className="font-display mt-4 text-2xl font-semibold">
          正在构建对比快照
        </h1>
        <p className="text-slate mt-2 text-sm">
          正在校验报告期、指标口径与证据身份。
        </p>
      </div>
    </Card>
  );
}
function ComparisonError({ onRetry }: { onRetry: () => void }) {
  return (
    <Card
      className="border-risk/20 mx-auto max-w-xl p-7 text-center"
      role="alert"
    >
      <ShieldAlert className="text-risk mx-auto size-7" />
      <h1 className="font-display mt-4 text-2xl font-semibold">
        对比研究暂时不可用
      </h1>
      <p className="text-slate mt-2 text-sm">请确认股票数据覆盖后重试。</p>
      <button
        type="button"
        onClick={onRetry}
        className="bg-ink mt-5 rounded-xl px-4 py-2 text-sm text-white"
      >
        重新读取
      </button>
    </Card>
  );
}
