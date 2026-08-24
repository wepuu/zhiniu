"use client";

import {
  ApiError,
  createZhaoniuClient,
  type SavedScreenResponse,
} from "@zhaoniu/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  BookmarkCheck,
  Clock3,
  LoaderCircle,
  LogIn,
  Play,
  Trash2,
  TriangleAlert,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { PageHeading } from "@/components/page-heading";
import { ResearchSectionTabs } from "@/components/research-section-tabs";
import { financialMetricLabel, translateEnum } from "@/lib/presentation";
import { Card } from "@/components/ui/card";

const api = createZhaoniuClient();

export function SavedScreensWorkspace() {
  const queryClient = useQueryClient();
  const [executionId, setExecutionId] = useState<string | null>(null);
  const [activeName, setActiveName] = useState<string | null>(null);
  const saved = useQuery({
    queryKey: ["saved-screens"],
    queryFn: () => api.getSavedScreens(),
    retry: false,
  });
  const execute = useMutation({
    mutationFn: (item: SavedScreenResponse) =>
      api.createScreenExecution(item.query, { savedScreenId: item.id }),
    onSuccess: (result, item) => {
      setExecutionId(result.id);
      setActiveName(item.name);
    },
  });
  const execution = useQuery({
    queryKey: ["saved-screen-execution", executionId],
    queryFn: () => api.getScreenExecution(executionId!),
    enabled: Boolean(executionId),
    retry: false,
    refetchInterval: (query) =>
      query.state.data?.status === "pending" ||
      query.state.data?.status === "running"
        ? 1000
        : false,
  });
  const results = useQuery({
    queryKey: ["saved-screen-results", executionId],
    queryFn: () => api.getScreenResults(executionId!),
    enabled: execution.data?.status === "succeeded",
    retry: false,
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.deleteSavedScreen(id),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["saved-screens"] }),
  });

  const authRequired =
    saved.error instanceof ApiError && saved.error.status === 401;

  return (
    <>
      <ResearchSectionTabs />
      <PageHeading
        eyebrow="已保存的研究条件"
        title="已保存筛选"
        description="保留研究条件与版本信息，在新快照上重复运行，并明确提示目录兼容性变化。"
      />

      {saved.isPending && (
        <WorkspaceState icon={LoaderCircle} animate title="正在读取筛选方案" />
      )}
      {authRequired && (
        <WorkspaceState icon={LogIn} title="登录后查看已保存筛选">
          <Link
            href="/login?next=/saved-screens"
            className="bg-blue text-paper mt-4 inline-flex rounded-xl px-4 py-2 text-sm font-medium"
          >
            登录账户
          </Link>
        </WorkspaceState>
      )}
      {saved.error && !authRequired && (
        <WorkspaceState icon={TriangleAlert} title="暂时无法读取筛选方案" />
      )}
      {saved.data?.items.length === 0 && (
        <WorkspaceState icon={BookmarkCheck} title="还没有保存的筛选方案">
          <Link
            href="/screens"
            className="text-blue mt-3 inline-flex text-sm font-medium"
          >
            前往股票筛选 <ArrowRight className="ml-1 size-4" />
          </Link>
        </WorkspaceState>
      )}

      {saved.data && saved.data.items.length > 0 && (
        <div className="mt-5 grid gap-4 lg:grid-cols-2">
          {saved.data.items.map((item) => (
            <SavedScreenCard
              key={item.id}
              item={item}
              running={execute.isPending && execute.variables?.id === item.id}
              deleting={remove.isPending && remove.variables === item.id}
              onRun={() => execute.mutate(item)}
              onDelete={() => remove.mutate(item.id)}
            />
          ))}
        </div>
      )}

      {executionId && (
        <Card className="mt-5 p-4 sm:p-5" aria-live="polite">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-blue text-xs font-semibold uppercase tracking-[0.14em]">
                最近一次运行
              </p>
              <h2 className="font-display mt-1 text-xl font-semibold">
                {activeName}
              </h2>
            </div>
            <p className="text-slate text-sm">
              {execution.data?.status === "succeeded"
                ? `匹配 ${execution.data.result_count} 家`
                : execution.data?.status === "failed"
                  ? "本次运行未完成"
                  : "正在核对研究快照"}
            </p>
          </div>
          {results.data && (
            <div className="mt-4 grid gap-2 sm:grid-cols-2">
              {results.data.items.slice(0, 6).map((item) => (
                <Link
                  key={item.symbol}
                  href={item.research_path}
                  className="bg-mist flex items-center justify-between rounded-xl px-3 py-2.5 text-sm"
                >
                  <span>
                    <span className="font-medium">{item.stock_name}</span>
                    <span className="font-data text-slate ml-2 text-xs">
                      {item.symbol}
                    </span>
                  </span>
                  <ArrowRight className="text-blue size-4" />
                </Link>
              ))}
            </div>
          )}
        </Card>
      )}
    </>
  );
}

function SavedScreenCard({
  item,
  running,
  deleting,
  onRun,
  onDelete,
}: {
  item: SavedScreenResponse;
  running: boolean;
  deleting: boolean;
  onRun: () => void;
  onDelete: () => void;
}) {
  const compatible = item.compatibility === "compatible";
  return (
    <Card className="p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="font-display text-xl font-semibold">{item.name}</h2>
            <span
              className={
                "rounded-full px-2 py-0.5 text-[11px] " +
                (compatible
                  ? "bg-blue/10 text-blue"
                  : item.compatibility === "reconfirmation_required"
                    ? "bg-amber/10 text-amber"
                    : "bg-risk/10 text-risk")
              }
            >
              {compatible
                ? "可直接运行"
                : item.compatibility === "reconfirmation_required"
                  ? "需要重新确认"
                  : "当前不支持"}
            </span>
          </div>
          {item.description && (
            <p className="text-slate mt-1 text-sm">{item.description}</p>
          )}
        </div>
        <button
          type="button"
          aria-label={`删除筛选 ${item.name}`}
          disabled={deleting}
          onClick={onDelete}
          className="text-slate hover:text-risk grid size-9 place-items-center rounded-lg"
        >
          {deleting ? (
            <LoaderCircle className="size-4 animate-spin" />
          ) : (
            <Trash2 className="size-4" />
          )}
        </button>
      </div>
      {item.original_text && (
        <div className="border-blue/10 bg-blue/5 mt-3 rounded-xl border p-3">
          <p className="text-blue text-[11px] font-semibold">
            AI 解析原文（由你保存）
          </p>
          <p className="text-ink mt-1 text-sm leading-6">
            {item.original_text}
          </p>
        </div>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        {item.query.filters.map((filter, index) => (
          <span
            key={`${filter.kind}-${index}`}
            className="bg-mist rounded-lg px-2.5 py-1.5 text-xs"
          >
            {criterionLabel(filter)}
          </span>
        ))}
      </div>
      <div className="text-slate mt-4 flex items-center justify-between gap-3 text-xs">
        <span className="inline-flex items-center gap-1">
          <Clock3 className="size-3.5" /> 更新于 {formatDate(item.updated_at)}
        </span>
        {compatible ? (
          <button
            type="button"
            disabled={running}
            onClick={onRun}
            className="bg-ink text-paper inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 font-medium disabled:opacity-50"
          >
            {running ? (
              <LoaderCircle className="size-3.5 animate-spin" />
            ) : (
              <Play className="size-3.5" />
            )}
            运行
          </button>
        ) : (
          <Link href="/screens" className="text-blue font-medium">
            回到筛选器核对
          </Link>
        )}
      </div>
    </Card>
  );
}

function WorkspaceState({
  icon: Icon,
  title,
  animate = false,
  children,
}: {
  icon: typeof BookmarkCheck;
  title: string;
  animate?: boolean;
  children?: React.ReactNode;
}) {
  return (
    <Card className="mt-5 grid min-h-72 place-items-center p-8 text-center">
      <div>
        <Icon
          className={`text-blue mx-auto size-6 ${animate ? "animate-spin" : ""}`}
        />
        <h2 className="font-display mt-3 text-xl font-semibold">{title}</h2>
        {children}
      </div>
    </Card>
  );
}

function criterionLabel(
  filter: SavedScreenResponse["query"]["filters"][number],
) {
  if (filter.kind === "industry")
    return `行业 · ${filter.industry_codes.join("、")}`;
  if (filter.kind === "event")
    return `事件 · ${translateEnum("event_type", filter.event_family)}`;
  return `${filter.kind === "peer" ? "同行" : "指标"} · ${financialMetricLabel(filter.metric_code)}`;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium" }).format(
    new Date(value),
  );
}
