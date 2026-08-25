"use client";

import { createZhaoniuClient } from "@zhaoniu/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DatabaseZap, Play } from "lucide-react";

import { Card } from "@/components/ui/card";

const api = createZhaoniuClient({ baseUrl: process.env.NEXT_PUBLIC_API_URL });

const labels: Record<string, string> = {
  stock_master: "股票主数据",
  daily_bars: "日线行情",
  financial_statements: "财务报表",
  valuations: "估值数据",
  industry_membership: "行业归属",
  corporate_events: "公司事件",
  provider_usage_policy: "数据使用策略",
  structured_ai_route: "结构化 AI 路由",
};

export function ProviderAcceptancePanel({
  canRun,
  elevated,
}: {
  canRun: boolean;
  elevated: boolean;
}) {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["provider-acceptance-latest"],
    queryFn: api.getLatestProviderAcceptance,
    retry: false,
  });
  const run = useMutation({
    mutationFn: api.runProviderAcceptance,
    onSuccess: (result) => {
      client.setQueryData(["provider-acceptance-latest"], result);
    },
  });
  const result = query.data;
  const gaps = (result?.items ?? []).filter(
    (item) => item.status === "failed" || item.status === "blocked",
  );

  return (
    <section className="mt-9">
      <div className="mb-4 flex items-end justify-between gap-4">
        <div>
          <p className="text-blue text-xs font-semibold tracking-[0.18em]">
            PHASE 20
          </p>
          <h2 className="mt-1 text-xl font-semibold">
            Provider 与 Beta 数据验收
          </h2>
          <p className="text-slate mt-1 text-sm">
            对四只固定样本的留存数据、来源策略和结构化 AI 路由进行可复核检查。
          </p>
        </div>
        {canRun && (
          <button
            type="button"
            disabled={!elevated || run.isPending}
            onClick={() => run.mutate()}
            className="bg-blue hidden items-center gap-2 rounded-xl px-4 py-2 text-sm text-white disabled:cursor-not-allowed disabled:opacity-45 md:flex"
            title={elevated ? undefined : "需要先完成管理员二次验证"}
          >
            <Play className="size-4" />
            {run.isPending ? "验收中…" : "运行验收"}
          </button>
        )}
      </div>
      <Card className="p-5">
        {!result ? (
          <div className="text-slate flex items-center gap-3 text-sm">
            <DatabaseZap className="size-5" />
            {query.isLoading ? "正在读取最近基线…" : "尚无 Provider 验收基线"}
          </div>
        ) : (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-sm font-medium">
                  技术验收：{result.status === "passed" ? "通过" : "未通过"}
                </p>
                <p className="text-slate mt-1 text-xs">
                  Beta 数据资格：{result.beta_eligible ? "满足" : "不满足"} ·
                  通过 {result.succeeded_items} · 失败 {result.failed_items} ·
                  阻断 {result.blocked_items}
                </p>
              </div>
              <span
                className={`rounded-full border px-3 py-1 text-xs ${
                  result.beta_eligible
                    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                    : "border-red-200 bg-red-50 text-red-700"
                }`}
              >
                {result.beta_eligible ? "Beta eligible" : "Beta blocked"}
              </span>
            </div>
            {!!gaps?.length && (
              <div className="border-ink/8 mt-4 border-t pt-4">
                <p className="text-slate mb-2 text-xs">当前缺口</p>
                <ul className="space-y-2 text-sm">
                  {gaps.map((item) => (
                    <li
                      key={`${item.symbol ?? "global"}-${item.dataset}-${item.scenario}`}
                      className="flex flex-wrap items-center justify-between gap-2"
                    >
                      <span>
                        {item.symbol ?? "全局"} ·{" "}
                        {labels[item.dataset] ?? item.dataset}
                      </span>
                      <span className="font-data text-risk text-xs">
                        {item.reason_code ?? item.status}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </Card>
    </section>
  );
}
