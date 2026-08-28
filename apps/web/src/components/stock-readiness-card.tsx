"use client";

import {
  createZhaoniuClient,
  type StockReadinessResponse,
} from "@zhaoniu/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Clock3, RefreshCw, TriangleAlert } from "lucide-react";
import { useEffect, useRef } from "react";

import { Card } from "@/components/ui/card";
import { canRetryStockPreparation } from "@/lib/stock-readiness";

const api = createZhaoniuClient();

const STAGE_LABELS: Record<string, string> = {
  market: "行情数据",
  deterministic_research: "确定性研究",
  extended_research: "事件与同行",
  ai_research: "AI 解读",
};

export function StockReadinessCard({ symbol }: { symbol: string }) {
  const queryClient = useQueryClient();
  const startedAt = useRef(0);
  const lastStageFingerprint = useRef("");
  const readiness = useQuery({
    queryKey: ["stock-readiness", symbol],
    queryFn: async () => (await api.getStockReadiness([symbol])).items[0],
    retry: false,
    refetchInterval: (query) => {
      if (typeof document !== "undefined" && document.hidden) return false;
      const status = query.state.data?.overall_status;
      if (status !== "queued" && status !== "preparing") return false;
      return Date.now() - startedAt.current < 60_000 ? 5_000 : 15_000;
    },
  });
  useEffect(() => {
    const status = readiness.data?.overall_status;
    if (
      (status === "queued" || status === "preparing") &&
      startedAt.current === 0
    ) {
      startedAt.current = Date.now();
    }
    if (status !== "queued" && status !== "preparing") startedAt.current = 0;
  }, [readiness.data?.overall_status]);
  useEffect(() => {
    if (!readiness.data) return;
    const fingerprint = readiness.data.stages
      .map((stage) => `${stage.key}:${stage.status}:${stage.updated_at ?? ""}`)
      .join("|");
    if (
      lastStageFingerprint.current &&
      lastStageFingerprint.current !== fingerprint
    ) {
      void queryClient.invalidateQueries({ queryKey: ["stock", symbol] });
    }
    lastStageFingerprint.current = fingerprint;
  }, [queryClient, readiness.data, symbol]);
  const retry = useMutation({
    mutationFn: () => api.requestStockPreparation(symbol),
    onSuccess: async () => {
      startedAt.current = Date.now();
      await queryClient.invalidateQueries({
        queryKey: ["stock-readiness", symbol],
      });
    },
  });

  if (!readiness.data) return null;
  const state = readiness.data;
  return (
    <Card className="mx-auto mb-4 max-w-[1600px] p-4 sm:p-5" aria-live="polite">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <ReadinessIcon state={state} />
            <p className="font-medium">{overallLabel(state)}</p>
          </div>
          <p className="text-slate mt-1 text-xs">
            已完成 {state.progress}% · 可用数据会立即展示
          </p>
        </div>
        {canRetryStockPreparation(state) && (
          <button
            type="button"
            disabled={retry.isPending}
            onClick={() => retry.mutate()}
            className="border-ink/15 inline-flex min-h-9 items-center justify-center gap-2 rounded-xl border px-3 text-sm disabled:opacity-50"
          >
            <RefreshCw
              className={`size-4 ${retry.isPending ? "animate-spin" : ""}`}
            />
            重新准备
          </button>
        )}
      </div>
      <div className="mt-4 grid gap-2 sm:grid-cols-4">
        {state.stages.map((stage) => (
          <div key={stage.key} className="bg-mist rounded-xl px-3 py-2">
            <p className="text-xs font-medium">{STAGE_LABELS[stage.key]}</p>
            <p className="text-slate mt-1 text-xs">
              {stageLabel(stage.status)}
            </p>
          </div>
        ))}
      </div>
    </Card>
  );
}

function ReadinessIcon({ state }: { state: StockReadinessResponse }) {
  if (state.overall_status === "ready")
    return <CheckCircle2 className="text-positive size-4" />;
  if (state.overall_status === "failed")
    return <TriangleAlert className="text-risk size-4" />;
  return <Clock3 className="text-blue size-4" />;
}

function overallLabel(state: StockReadinessResponse) {
  return {
    queued: "研究准备已排队",
    preparing: "正在准备研究数据",
    ready: "研究数据已就绪",
    partial: "核心研究可用，扩展数据部分覆盖",
    failed: "部分研究准备失败",
    paused: "自动研究准备已暂停",
    unsupported: "部分研究不适用于该公司类型",
  }[state.overall_status];
}

function stageLabel(
  status: StockReadinessResponse["stages"][number]["status"],
) {
  return {
    queued: "已排队",
    preparing: "准备中",
    ready: "已就绪",
    partial: "部分覆盖",
    failed: "准备失败",
    paused: "已暂停",
    unsupported: "不适用",
  }[status];
}
