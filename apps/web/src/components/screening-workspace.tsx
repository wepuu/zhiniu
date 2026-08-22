"use client";

import {
  ApiError,
  createZhaoniuClient,
  type ScreenCatalogResponse,
  type ScreenQuery,
  type ScreenResultItem,
} from "@zhaoniu/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  Binoculars,
  Check,
  Filter,
  LoaderCircle,
  LogIn,
  Plus,
  RefreshCw,
  Save,
  SlidersHorizontal,
  TriangleAlert,
  X,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { PageHeading } from "@/components/page-heading";
import { NaturalLanguageScreenInput } from "@/components/natural-language-screen-input";
import { ResearchSectionTabs } from "@/components/research-section-tabs";
import { Card } from "@/components/ui/card";

const api = createZhaoniuClient();

type Operator = "gt" | "gte" | "lt" | "lte" | "between";
type MetricDraft = {
  id: string;
  kind: "metric";
  metricCode: string;
  operator: Operator;
  value: string;
  upperValue: string;
};
type PeerDraft = Omit<MetricDraft, "kind"> & { kind: "peer" };
type IndustryDraft = {
  id: string;
  kind: "industry";
  industryCode: string;
  taxonomyCode: string;
  taxonomyVersion: string;
};
type EventDraft = {
  id: string;
  kind: "event";
  eventFamily:
    | "share_repurchase"
    | "share_pledge"
    | "share_unlock"
    | "regulatory_action"
    | "shareholder_change"
    | "litigation_arbitration";
  mode: "exists" | "not_exists";
  withinDays: string;
};
type DraftCriterion = MetricDraft | PeerDraft | IndustryDraft | EventDraft;

const operatorLabels: Record<Operator, string> = {
  gt: "大于",
  gte: "大于等于",
  lt: "小于",
  lte: "小于等于",
  between: "介于",
};

function newCriterion(
  catalog?: ScreenCatalogResponse,
  kind: DraftCriterion["kind"] = "metric",
): DraftCriterion {
  const id = crypto.randomUUID();
  if (kind === "industry") {
    const industry = catalog?.industries[0];
    return {
      id,
      kind,
      industryCode: industry?.industry_code ?? "",
      taxonomyCode: industry?.taxonomy_code ?? "",
      taxonomyVersion: industry?.taxonomy_version ?? "",
    };
  }
  if (kind === "event") {
    return {
      id,
      kind,
      eventFamily: "regulatory_action",
      mode: "not_exists",
      withinDays: "365",
    };
  }
  const metricCode =
    kind === "peer"
      ? (catalog?.peer_metric_codes[0] ?? "roe_avg_equity_fy")
      : (catalog?.metrics[0]?.code ?? "roe_avg_equity_fy");
  return {
    id,
    kind,
    metricCode,
    operator: "gte",
    value: kind === "peer" ? "80" : "15",
    upperValue: "",
  };
}

function toScreenQuery(criteria: DraftCriterion[]): ScreenQuery {
  return {
    dsl_version: "screen-query-v1",
    filters: criteria.map((criterion) => {
      if (criterion.kind === "industry") {
        return {
          kind: "industry" as const,
          taxonomy_code: criterion.taxonomyCode,
          taxonomy_version: criterion.taxonomyVersion,
          industry_codes: [criterion.industryCode],
        };
      }
      if (criterion.kind === "event") {
        return {
          kind: "event" as const,
          event_family: criterion.eventFamily,
          mode: criterion.mode,
          within_days: Number(criterion.withinDays),
        };
      }
      if (criterion.kind === "peer") {
        return {
          kind: "peer" as const,
          metric_code: criterion.metricCode,
          operator: criterion.operator,
          value: criterion.value,
          ...(criterion.operator === "between"
            ? { upper_value: criterion.upperValue }
            : {}),
        };
      }
      return {
        kind: "metric" as const,
        metric_code: criterion.metricCode,
        selector: criterion.metricCode.endsWith("_fy")
          ? ("latest_fy" as const)
          : ("latest_available" as const),
        operator: criterion.operator,
        value: criterion.value,
        ...(criterion.operator === "between"
          ? { upper_value: criterion.upperValue }
          : {}),
      };
    }),
    sort: { field: "symbol", direction: "asc" },
  };
}

function fromScreenQuery(query: ScreenQuery): DraftCriterion[] {
  return query.filters.map((criterion) => {
    const id = crypto.randomUUID();
    if (criterion.kind === "industry") {
      return {
        id,
        kind: "industry" as const,
        industryCode: criterion.industry_codes[0] ?? "",
        taxonomyCode: criterion.taxonomy_code,
        taxonomyVersion: criterion.taxonomy_version,
      };
    }
    if (criterion.kind === "event") {
      return {
        id,
        kind: "event" as const,
        eventFamily: criterion.event_family,
        mode: criterion.mode,
        withinDays: String(criterion.within_days),
      };
    }
    return {
      id,
      kind: criterion.kind,
      metricCode: criterion.metric_code,
      operator: criterion.operator,
      value: String(criterion.value),
      upperValue:
        criterion.upper_value == null ? "" : String(criterion.upper_value),
    };
  });
}

function criterionReady(criterion: DraftCriterion) {
  if (criterion.kind === "industry") return Boolean(criterion.industryCode);
  if (criterion.kind === "event") return Number(criterion.withinDays) > 0;
  return (
    Boolean(criterion.value) &&
    (criterion.operator !== "between" || Boolean(criterion.upperValue))
  );
}

export function ScreeningWorkspace() {
  const queryClient = useQueryClient();
  const [criteria, setCriteria] = useState<DraftCriterion[]>(() => [
    newCriterion(),
  ]);
  const [executionId, setExecutionId] = useState<string | null>(null);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [watchlistMessage, setWatchlistMessage] = useState<string | null>(null);
  const [confirmedParseRunId, setConfirmedParseRunId] = useState<
    string | undefined
  >();
  const [originalText, setOriginalText] = useState<string | undefined>();
  const [saveName, setSaveName] = useState("");
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  const catalog = useQuery({
    queryKey: ["screen-catalog"],
    queryFn: () => api.getScreenCatalog(),
    retry: false,
  });
  const coverage = useQuery({
    queryKey: ["screen-coverage"],
    queryFn: () => api.getScreenCoverage(),
    retry: false,
  });
  const watchlists = useQuery({
    queryKey: ["watchlists"],
    queryFn: () => api.getWatchlists(),
    retry: false,
  });

  const execution = useQuery({
    queryKey: ["screen-execution", executionId],
    queryFn: () => api.getScreenExecution(executionId!),
    enabled: Boolean(executionId),
    retry: false,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "pending" || status === "running" ? 1200 : false;
    },
  });
  const results = useQuery({
    queryKey: ["screen-results", executionId],
    queryFn: () => api.getScreenResults(executionId!),
    enabled: execution.data?.status === "succeeded",
    retry: false,
  });

  const validation = useMutation({
    mutationFn: (query: ScreenQuery) => api.validateScreen(query),
  });
  const createExecution = useMutation({
    mutationFn: (value: { query: ScreenQuery; confirmedParseRunId?: string }) =>
      api.createScreenExecution(value.query, {
        confirmedParseRunId: value.confirmedParseRunId,
      }),
    onSuccess: (value) => {
      setExecutionId(value.id);
      setFiltersOpen(false);
    },
  });
  const saveScreen = useMutation({
    mutationFn: () =>
      api.createSavedScreen({
        name: saveName.trim(),
        query,
        sourceParseRunId: confirmedParseRunId,
        originalText,
      }),
    onSuccess: async () => {
      setSaveMessage("筛选方案已保存，可在“已保存筛选”中继续使用。");
      setSaveName("");
      await queryClient.invalidateQueries({ queryKey: ["saved-screens"] });
    },
    onError: () => setSaveMessage("保存未完成，请检查名称是否重复后重试。"),
  });
  const addToWatchlist = useMutation({
    mutationFn: async (symbol: string) => {
      const list = watchlists.data?.[0];
      if (!list) throw new Error("watchlist_missing");
      return api.addWatchlistItem(list.id, symbol);
    },
    onSuccess: async (_, symbol) => {
      setWatchlistMessage(symbol + " 已加入自选");
      await queryClient.invalidateQueries({ queryKey: ["watchlists"] });
      await results.refetch();
    },
    onError: (error) =>
      setWatchlistMessage(
        error instanceof ApiError && error.status === 401
          ? "请先登录，再加入自选"
          : "加入自选失败，请稍后重试",
      ),
  });

  const query = toScreenQuery(criteria);
  const coverageEstimate = useQuery({
    queryKey: ["screen-coverage-estimate", query],
    queryFn: () => api.estimateScreenCoverage(query),
    enabled: Boolean(catalog.data) && criteria.every(criterionReady),
    retry: false,
  });
  const busy = validation.isPending || createExecution.isPending;

  async function runScreen() {
    setWatchlistMessage(null);
    const checked = await validation.mutateAsync(query);
    if (!checked.valid || !checked.canonical_query) return;
    createExecution.mutate({
      query: checked.canonical_query,
      confirmedParseRunId,
    });
  }

  const builder = (
    <FilterBuilder
      catalog={catalog.data}
      criteria={criteria}
      setCriteria={(value) => {
        setCriteria(value);
        setConfirmedParseRunId(undefined);
        setOriginalText(undefined);
      }}
      busy={busy}
      validationIssues={validation.data?.issues ?? []}
      onRun={runScreen}
    />
  );

  return (
    <>
      <ResearchSectionTabs />
      <PageHeading
        eyebrow="Research Screener"
        title="股票筛选"
        description="使用可解释、可回溯的确定性条件，在当前研究快照中查找符合条件的公司。"
      />
      <NaturalLanguageScreenInput
        onApply={(parsedQuery, parseRunId, parsedOriginalText) => {
          setCriteria(fromScreenQuery(parsedQuery));
          setConfirmedParseRunId(parseRunId);
          setOriginalText(parsedOriginalText);
          setExecutionId(null);
          setSaveMessage("AI 候选条件已带入，请核对后运行确定性筛选。");
        }}
      />
      <CoverageBanner coverage={coverage.data} isPending={coverage.isPending} />
      {coverageEstimate.data && (
        <p className="text-slate mt-2 text-xs">
          当前条件所需事实同时可用：
          <span className="font-data text-ink ml-1 font-semibold">
            {coverageEstimate.data.all_criteria_available_count}
          </span>
          /{coverageEstimate.data.eligible_count}{" "}
          家；这表示可评估范围，不表示满足阈值。
        </p>
      )}
      {execution.data?.status === "succeeded" && (
        <div className="border-ink/10 bg-paper mt-4 flex flex-col gap-2 rounded-xl border p-3 sm:flex-row sm:items-center">
          <label className="text-slate flex-1 text-xs">
            保存本次研究条件
            <input
              value={saveName}
              maxLength={80}
              onChange={(event) => setSaveName(event.target.value)}
              placeholder="例如：高毛利且近期无监管事项"
              className="border-ink/10 text-ink mt-1 min-h-10 w-full rounded-lg border px-3 text-sm"
            />
          </label>
          <button
            type="button"
            disabled={!saveName.trim() || saveScreen.isPending}
            onClick={() => saveScreen.mutate()}
            className="bg-ink text-paper inline-flex min-h-10 items-center justify-center gap-2 rounded-lg px-4 text-sm font-medium disabled:opacity-50 sm:self-end"
          >
            {saveScreen.isPending ? (
              <LoaderCircle className="size-4 animate-spin" />
            ) : (
              <Save className="size-4" />
            )}
            保存筛选
          </button>
        </div>
      )}
      {saveMessage && (
        <p className="text-blue mt-2 text-xs" role="status">
          {saveMessage}
        </p>
      )}

      <button
        type="button"
        onClick={() => setFiltersOpen(true)}
        className="border-ink/10 bg-paper text-ink mt-5 flex min-h-11 w-full items-center justify-center gap-2 rounded-xl border px-4 text-sm font-medium shadow-sm lg:hidden"
      >
        <Filter className="size-4" /> 设置筛选条件
        <span className="bg-blue/10 text-blue rounded-full px-2 py-0.5 text-xs">
          {criteria.length}
        </span>
      </button>

      <div className="mt-5 grid gap-5 lg:grid-cols-[360px_minmax(0,1fr)]">
        <aside className="hidden lg:block">{builder}</aside>
        <ResultsPanel
          execution={execution.data}
          executionError={execution.error ?? createExecution.error}
          results={results.data?.items}
          total={results.data?.total}
          isPending={
            createExecution.isPending ||
            execution.data?.status === "pending" ||
            execution.data?.status === "running"
          }
          hasRun={Boolean(executionId)}
          onAdd={(symbol) => addToWatchlist.mutate(symbol)}
          watchlistMessage={watchlistMessage}
          addingSymbol={addToWatchlist.variables}
        />
      </div>

      {filtersOpen && (
        <div className="fixed inset-0 z-50 flex items-end bg-black/35 lg:hidden">
          <button
            aria-label="关闭筛选条件"
            className="absolute inset-0"
            onClick={() => setFiltersOpen(false)}
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-label="筛选条件"
            className="bg-mist relative max-h-[88vh] w-full overflow-y-auto rounded-t-[28px] p-4 pb-8 shadow-2xl"
          >
            <div className="bg-slate/30 mx-auto mb-4 h-1 w-10 rounded-full" />
            <button
              type="button"
              aria-label="关闭"
              onClick={() => setFiltersOpen(false)}
              className="absolute right-5 top-5 grid size-9 place-items-center rounded-full bg-white"
            >
              <X className="size-4" />
            </button>
            {builder}
          </div>
        </div>
      )}
    </>
  );
}

function CoverageBanner({
  coverage,
  isPending,
}: {
  coverage: Awaited<ReturnType<typeof api.getScreenCoverage>> | undefined;
  isPending: boolean;
}) {
  if (isPending) return null;
  if (!coverage || coverage.status === "not_built") {
    return (
      <div className="border-amber/25 bg-amber/8 text-ink mt-5 rounded-xl border px-4 py-3 text-sm">
        筛选快照尚未生成。请先运行后台快照构建任务。
      </div>
    );
  }
  return (
    <div className="border-blue/15 bg-blue/5 mt-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border px-4 py-3 text-sm">
      <p>
        <span className="text-blue font-medium">
          {coverage.status === "ready" ? "覆盖可用" : "部分覆盖"}
        </span>
        <span className="text-slate ml-2">
          {coverage.eligible_count} 家进入覆盖评估 · 可用事实{" "}
          {Object.values(coverage.fact_counts ?? {}).reduce(
            (sum, count) => sum + count,
            0,
          )}{" "}
          条
        </span>
      </p>
      <p className="font-data text-slate text-xs">
        截止 {formatDateTime(coverage.knowledge_cutoff)} · 技术评估数据
      </p>
    </div>
  );
}

function FilterBuilder({
  catalog,
  criteria,
  setCriteria,
  busy,
  validationIssues,
  onRun,
}: {
  catalog?: ScreenCatalogResponse;
  criteria: DraftCriterion[];
  setCriteria: (value: DraftCriterion[]) => void;
  busy: boolean;
  validationIssues: { message: string }[];
  onRun: () => void;
}) {
  return (
    <Card className="p-4 sm:p-5">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-blue text-xs font-semibold uppercase tracking-[0.14em]">
            Conditions
          </p>
          <h2 className="font-display mt-1 text-xl font-semibold">筛选条件</h2>
        </div>
        <span className="text-slate text-xs">全部满足（AND）</span>
      </div>
      <div className="mt-4 space-y-3">
        {criteria.map((criterion, index) => {
          const metric =
            criterion.kind === "metric" || criterion.kind === "peer"
              ? catalog?.metrics.find(
                  (item) => item.code === criterion.metricCode,
                )
              : undefined;
          return (
            <div key={criterion.id} className="bg-mist rounded-xl p-3">
              <div className="mb-2 flex items-center justify-between">
                <span className="font-data text-slate text-[11px]">
                  条件 {index + 1}
                </span>
                {criteria.length > 1 && (
                  <button
                    type="button"
                    aria-label={"删除条件 " + (index + 1)}
                    onClick={() =>
                      setCriteria(
                        criteria.filter((item) => item.id !== criterion.id),
                      )
                    }
                    className="text-slate hover:text-risk p-1"
                  >
                    <X className="size-4" />
                  </button>
                )}
              </div>
              <label className="text-slate block text-xs">
                条件类型
                <select
                  value={criterion.kind}
                  onChange={(event) => {
                    const next = newCriterion(
                      catalog,
                      event.target.value as DraftCriterion["kind"],
                    );
                    next.id = criterion.id;
                    setCriteria(
                      criteria.map((item) =>
                        item.id === criterion.id ? next : item,
                      ),
                    );
                  }}
                  className="border-ink/10 bg-paper text-ink mt-1 min-h-10 w-full rounded-lg border px-3 text-sm"
                >
                  <option value="metric">财务与估值指标</option>
                  <option value="peer">同行分位</option>
                  <option value="industry">行业分类</option>
                  <option value="event">公司事件</option>
                </select>
              </label>

              {(criterion.kind === "metric" || criterion.kind === "peer") && (
                <>
                  <label className="text-slate mt-2 block text-xs">
                    {criterion.kind === "peer" ? "同行指标" : "指标"}
                    <select
                      value={criterion.metricCode}
                      onChange={(event) =>
                        setCriteria(
                          criteria.map((item) =>
                            item.id === criterion.id
                              ? { ...criterion, metricCode: event.target.value }
                              : item,
                          ),
                        )
                      }
                      className="border-ink/10 bg-paper text-ink mt-1 min-h-10 w-full rounded-lg border px-3 text-sm"
                    >
                      {(criterion.kind === "peer"
                        ? catalog?.metrics.filter((item) =>
                            catalog.peer_metric_codes.includes(item.code),
                          )
                        : catalog?.metrics
                      )?.map((item) => (
                        <option key={item.code} value={item.code}>
                          {item.display_name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="mt-2 grid grid-cols-[1fr_1fr] gap-2">
                    <label className="text-slate text-xs">
                      关系
                      <select
                        value={criterion.operator}
                        onChange={(event) =>
                          setCriteria(
                            criteria.map((item) =>
                              item.id === criterion.id
                                ? {
                                    ...criterion,
                                    operator: event.target.value as Operator,
                                  }
                                : item,
                            ),
                          )
                        }
                        className="border-ink/10 bg-paper text-ink mt-1 min-h-10 w-full rounded-lg border px-2 text-sm"
                      >
                        {(metric?.operators ?? ["gte", "lte", "between"]).map(
                          (value) => (
                            <option key={value} value={value}>
                              {operatorLabels[value as Operator]}
                            </option>
                          ),
                        )}
                      </select>
                    </label>
                    <label className="text-slate text-xs">
                      数值{" "}
                      {criterion.kind === "peer"
                        ? "(分位 0–100)"
                        : metric?.unit
                          ? "(" + metric.unit + ")"
                          : ""}
                      <input
                        inputMode="decimal"
                        value={criterion.value}
                        onChange={(event) =>
                          setCriteria(
                            criteria.map((item) =>
                              item.id === criterion.id
                                ? { ...criterion, value: event.target.value }
                                : item,
                            ),
                          )
                        }
                        className="border-ink/10 bg-paper text-ink font-data mt-1 min-h-10 w-full rounded-lg border px-3 text-sm"
                      />
                    </label>
                  </div>
                  {criterion.operator === "between" && (
                    <label className="text-slate mt-2 block text-xs">
                      上限
                      <input
                        inputMode="decimal"
                        value={criterion.upperValue}
                        onChange={(event) =>
                          setCriteria(
                            criteria.map((item) =>
                              item.id === criterion.id
                                ? {
                                    ...criterion,
                                    upperValue: event.target.value,
                                  }
                                : item,
                            ),
                          )
                        }
                        className="border-ink/10 bg-paper text-ink font-data mt-1 min-h-10 w-full rounded-lg border px-3 text-sm"
                      />
                    </label>
                  )}
                </>
              )}

              {criterion.kind === "industry" && (
                <label className="text-slate mt-2 block text-xs">
                  行业
                  <select
                    value={criterion.industryCode}
                    onChange={(event) =>
                      setCriteria(
                        criteria.map((item) =>
                          item.id === criterion.id
                            ? {
                                ...criterion,
                                industryCode: event.target.value,
                                taxonomyCode:
                                  catalog?.industries.find(
                                    (candidate) =>
                                      candidate.industry_code ===
                                      event.target.value,
                                  )?.taxonomy_code ?? criterion.taxonomyCode,
                                taxonomyVersion:
                                  catalog?.industries.find(
                                    (candidate) =>
                                      candidate.industry_code ===
                                      event.target.value,
                                  )?.taxonomy_version ??
                                  criterion.taxonomyVersion,
                              }
                            : item,
                        ),
                      )
                    }
                    className="border-ink/10 bg-paper text-ink mt-1 min-h-10 w-full rounded-lg border px-3 text-sm"
                  >
                    {catalog?.industries.map((item) => (
                      <option
                        key={item.industry_code}
                        value={item.industry_code}
                      >
                        {item.industry_name}
                      </option>
                    ))}
                  </select>
                </label>
              )}

              {criterion.kind === "event" && (
                <>
                  <label className="text-slate mt-2 block text-xs">
                    事件类型
                    <select
                      value={criterion.eventFamily}
                      onChange={(event) =>
                        setCriteria(
                          criteria.map((item) =>
                            item.id === criterion.id
                              ? {
                                  ...criterion,
                                  eventFamily: event.target
                                    .value as EventDraft["eventFamily"],
                                }
                              : item,
                          ),
                        )
                      }
                      className="border-ink/10 bg-paper text-ink mt-1 min-h-10 w-full rounded-lg border px-3 text-sm"
                    >
                      <option value="regulatory_action">监管措施</option>
                      <option value="share_pledge">股权质押</option>
                      <option value="share_unlock">股份解禁</option>
                      <option value="share_repurchase">股份回购</option>
                      <option value="shareholder_change">股东增减持</option>
                      <option value="litigation_arbitration">诉讼仲裁</option>
                    </select>
                  </label>
                  <div className="mt-2 grid grid-cols-2 gap-2">
                    <label className="text-slate text-xs">
                      状态
                      <select
                        value={criterion.mode}
                        onChange={(event) =>
                          setCriteria(
                            criteria.map((item) =>
                              item.id === criterion.id
                                ? {
                                    ...criterion,
                                    mode: event.target
                                      .value as EventDraft["mode"],
                                  }
                                : item,
                            ),
                          )
                        }
                        className="border-ink/10 bg-paper text-ink mt-1 min-h-10 w-full rounded-lg border px-2 text-sm"
                      >
                        <option value="not_exists">未发生</option>
                        <option value="exists">已发生</option>
                      </select>
                    </label>
                    <label className="text-slate text-xs">
                      时间范围（天）
                      <input
                        inputMode="numeric"
                        value={criterion.withinDays}
                        onChange={(event) =>
                          setCriteria(
                            criteria.map((item) =>
                              item.id === criterion.id
                                ? {
                                    ...criterion,
                                    withinDays: event.target.value,
                                  }
                                : item,
                            ),
                          )
                        }
                        className="border-ink/10 bg-paper text-ink font-data mt-1 min-h-10 w-full rounded-lg border px-3 text-sm"
                      />
                    </label>
                  </div>
                </>
              )}
            </div>
          );
        })}
      </div>
      {validationIssues.length > 0 && (
        <p className="text-risk mt-3 text-xs">{validationIssues[0]?.message}</p>
      )}
      <button
        type="button"
        disabled={!catalog || criteria.length >= 8}
        onClick={() => setCriteria([...criteria, newCriterion(catalog)])}
        className="text-blue mt-3 inline-flex min-h-9 items-center gap-1 text-sm font-medium disabled:opacity-40"
      >
        <Plus className="size-4" /> 添加条件
      </button>
      <button
        type="button"
        disabled={
          busy || !catalog || criteria.some((item) => !criterionReady(item))
        }
        onClick={onRun}
        className="bg-blue mt-4 flex min-h-11 w-full items-center justify-center gap-2 rounded-xl px-4 text-sm font-medium text-white disabled:opacity-50"
      >
        {busy ? (
          <LoaderCircle className="size-4 animate-spin" />
        ) : (
          <Binoculars className="size-4" />
        )}
        运行筛选
      </button>
      <p className="text-slate mt-3 text-xs leading-5">
        只展示事实条件的交集；缺失数据不会被视为符合。
      </p>
    </Card>
  );
}

function ResultsPanel({
  execution,
  executionError,
  results,
  total,
  isPending,
  hasRun,
  onAdd,
  watchlistMessage,
  addingSymbol,
}: {
  execution?: Awaited<ReturnType<typeof api.getScreenExecution>>;
  executionError: unknown;
  results?: ScreenResultItem[];
  total?: number;
  isPending: boolean;
  hasRun: boolean;
  onAdd: (symbol: string) => void;
  watchlistMessage: string | null;
  addingSymbol?: string;
}) {
  if (!hasRun) {
    return (
      <EmptyState
        icon={SlidersHorizontal}
        title="设置条件后开始筛选"
        detail="结果会保存命中的条件、事实值和证据来源，方便逐项核对。"
      />
    );
  }
  if (executionError instanceof ApiError && executionError.status === 401) {
    return (
      <EmptyState
        icon={LogIn}
        title="登录后运行股票筛选"
        detail="筛选执行记录属于你的个人研究工作区。"
      >
        <Link
          href="/login?next=/screens"
          className="bg-blue mt-4 inline-flex rounded-xl px-4 py-2 text-sm font-medium text-white"
        >
          登录账户
        </Link>
      </EmptyState>
    );
  }
  if (isPending) {
    return (
      <EmptyState
        icon={LoaderCircle}
        animate
        title="正在核对研究快照"
        detail="后台正在逐项匹配，通常只需几秒。"
      />
    );
  }
  if (execution?.status === "failed" || executionError) {
    return (
      <EmptyState
        icon={TriangleAlert}
        title="本次筛选未完成"
        detail={execution?.error_summary ?? "请检查后台任务服务后重试。"}
      />
    );
  }
  if (results && results.length === 0) {
    return (
      <EmptyState
        icon={RefreshCw}
        title="没有公司同时满足这些条件"
        detail="可以放宽一个阈值，或减少条件后再次运行。"
      />
    );
  }
  return (
    <section aria-label="筛选结果">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
        <div>
          <p className="text-blue text-xs font-semibold uppercase tracking-[0.14em]">
            Results
          </p>
          <h2 className="font-display mt-1 text-2xl font-semibold">
            符合条件的公司
          </h2>
        </div>
        <p className="text-slate text-sm">
          {total ?? 0} 家 · 已评估 {execution?.evaluated_count ?? 0} 家
        </p>
      </div>
      {watchlistMessage && (
        <p
          role="status"
          className="border-blue/15 bg-blue/5 mb-3 rounded-xl border px-3 py-2 text-sm"
        >
          {watchlistMessage}
        </p>
      )}
      <div className="space-y-3">
        {results?.map((item) => (
          <ResultCard
            key={item.symbol}
            item={item}
            onAdd={onAdd}
            adding={addingSymbol === item.symbol}
          />
        ))}
      </div>
      <p className="text-slate mt-4 text-xs">
        结果基于固定知识截止时间，不构成证券投资建议。
      </p>
    </section>
  );
}

function ResultCard({
  item,
  onAdd,
  adding,
}: {
  item: ScreenResultItem;
  onAdd: (symbol: string) => void;
  adding: boolean;
}) {
  return (
    <Card className="p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-data text-blue text-xs">{item.symbol}</p>
          <h3 className="font-display mt-1 text-xl font-semibold">
            {item.stock_name}
          </h3>
          <p className="text-slate mt-1 text-xs">
            {item.exchange}
            {item.industry_name ? " · " + item.industry_name : ""}
          </p>
        </div>
        <button
          type="button"
          disabled={item.is_in_watchlist || adding}
          onClick={() => onAdd(item.symbol)}
          className="border-ink/10 text-ink inline-flex min-h-9 items-center gap-1.5 rounded-lg border px-3 text-xs font-medium disabled:opacity-55"
        >
          {item.is_in_watchlist ? (
            <Check className="size-3.5" />
          ) : adding ? (
            <LoaderCircle className="size-3.5 animate-spin" />
          ) : (
            <Plus className="size-3.5" />
          )}
          {item.is_in_watchlist ? "已在自选" : "加入自选"}
        </button>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {item.matched_conditions.map((condition) => (
          <div
            key={condition.criterion_key}
            className="bg-mist rounded-lg px-3 py-2"
          >
            <p className="text-slate text-[11px]">{condition.label}</p>
            <p className="font-data mt-0.5 text-sm font-semibold">
              {formatConditionValue(condition.value, condition.unit)}
            </p>
          </div>
        ))}
      </div>
      <Link
        href={item.research_path}
        className="text-blue mt-4 inline-flex items-center gap-1 text-sm font-medium"
      >
        查看研究证据 <ArrowRight className="size-4" />
      </Link>
    </Card>
  );
}

function EmptyState({
  icon: Icon,
  title,
  detail,
  animate = false,
  children,
}: {
  icon: typeof Binoculars;
  title: string;
  detail: string;
  animate?: boolean;
  children?: React.ReactNode;
}) {
  return (
    <Card className="grid min-h-[360px] place-items-center p-8 text-center">
      <div>
        <span className="bg-blue/8 mx-auto grid size-12 place-items-center rounded-2xl">
          <Icon
            className={"text-blue size-5 " + (animate ? "animate-spin" : "")}
          />
        </span>
        <h2 className="font-display mt-4 text-2xl font-semibold">{title}</h2>
        <p className="text-slate mx-auto mt-2 max-w-md text-sm leading-6">
          {detail}
        </p>
        {children}
      </div>
    </Card>
  );
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return "未知";
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatConditionValue(
  value: string | number | boolean,
  unit: string | null | undefined,
) {
  if (typeof value === "boolean") return value ? "是" : "否";
  const numeric = Number(value);
  const rendered = Number.isFinite(numeric)
    ? new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 4 }).format(
        numeric,
      )
    : String(value);
  const unitLabel: Record<string, string> = {
    percent: "%",
    percentile: "分位",
    multiple: "倍",
    ratio: "倍",
    CNY: "元",
  };
  return unit ? rendered + " " + (unitLabel[unit] ?? unit) : rendered;
}
