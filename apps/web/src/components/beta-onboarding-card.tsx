"use client";

import { createZhaoniuClient } from "@zhaoniu/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  Circle,
  DatabaseZap,
  FlaskConical,
  Sparkles,
  X,
} from "lucide-react";
import Link from "next/link";

import { Card } from "@/components/ui/card";

const api = createZhaoniuClient();

export function BetaOnboardingCard() {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["beta-onboarding"],
    queryFn: api.getBetaOnboarding,
    retry: false,
    refetchInterval: (state) => {
      const data = state.state.data;
      return data?.enrolled && !data.ai_terminal ? 15_000 : false;
    },
  });
  const mutation = useMutation({
    mutationFn: api.updateBetaOnboarding,
    onSuccess: (data) => client.setQueryData(["beta-onboarding"], data),
  });
  const data = query.data;
  if (!data?.enrolled || data.dismissed) return null;

  const privateEvaluation = data.program_kind === "private_evaluation";
  const steps = [
    { label: "邮箱已验证", done: data.email_verified },
    { label: "已添加第一只自选股", done: data.watchlist_started },
    { label: "基础行情已就绪", done: data.market_ready },
    { label: "确定性研究已就绪", done: data.deterministic_ready },
    { label: "AI 研究已到达终态", done: data.ai_terminal },
    { label: "已提交一次体验反馈", done: data.feedback_submitted },
  ] as const;
  const complete = steps.every((step) => step.done);
  const companyHref = data.first_value_symbol
    ? `/stock/${data.first_value_symbol.split(".")[0]}`
    : "/watchlist";

  return (
    <Card className="border-blue/15 relative overflow-hidden bg-[linear-gradient(135deg,rgba(246,249,251,0.98),rgba(255,255,255,0.98))] p-0">
      <div className="border-blue/15 bg-blue/[0.04] flex flex-wrap items-center justify-between gap-3 border-b px-5 py-3 sm:px-6">
        <div className="flex items-center gap-2">
          <FlaskConical className="text-blue size-4" />
          <span className="text-blue text-xs font-semibold tracking-[0.16em]">
            {privateEvaluation ? "私有非商用评估" : "受控 BETA"}
          </span>
        </div>
        <span className="font-data text-slate text-[10px]">
          {data.notice_version ?? "evaluation"} ·{" "}
          {data.usage_scope ?? "范围待确认"}
        </span>
      </div>
      <button
        type="button"
        aria-label="关闭评估引导"
        className="text-slate absolute right-4 top-14 rounded-lg p-1 hover:bg-black/5"
        onClick={() => mutation.mutate("dismiss")}
      >
        <X className="size-4" />
      </button>

      <div className="grid gap-6 p-5 sm:p-6 lg:grid-cols-[minmax(0,1fr)_240px]">
        <div>
          <p className="text-slate text-xs">首次研究价值路径</p>
          <h2 className="font-display mt-1 text-xl font-semibold">
            从受邀注册走到可核验的研究结果
          </h2>
          <p className="text-slate mt-2 max-w-2xl pr-6 text-sm leading-6">
            自选股会按需准备行情、确定性研究与 AI 解读。
            {privateEvaluation
              ? "评估环境的免费公开数据可能延迟、缺失或仅部分覆盖；"
              : "受控 Beta 的数据仍受生产准入与覆盖范围约束；"}
            页面状态会明确区分准备中、失败与不支持。
          </p>

          <div className="mt-5 grid gap-2 sm:grid-cols-2">
            {steps.map((step, index) => (
              <div
                key={step.label}
                className={`flex min-h-12 items-center gap-3 rounded-xl border px-3 py-2.5 text-sm ${
                  step.done
                    ? "border-emerald-200 bg-emerald-50/70"
                    : "border-ink/10 bg-white/75"
                }`}
              >
                <span className="font-data text-slate w-4 text-[10px]">
                  {String(index + 1).padStart(2, "0")}
                </span>
                {step.done ? (
                  <CheckCircle2 className="size-4 shrink-0 text-emerald-600" />
                ) : (
                  <Circle className="text-slate/45 size-4 shrink-0" />
                )}
                <span className={step.done ? "text-emerald-950" : "text-ink"}>
                  {step.label}
                </span>
              </div>
            ))}
          </div>
        </div>

        <aside className="border-ink/8 bg-paper rounded-2xl border p-4">
          <div className="flex items-center gap-2">
            {data.deterministic_ready ? (
              <Sparkles className="size-4 text-emerald-600" />
            ) : (
              <DatabaseZap className="text-blue size-4" />
            )}
            <p className="text-sm font-medium">
              {data.deterministic_ready ? "已有研究可查看" : "正在准备研究数据"}
            </p>
          </div>
          <p className="text-slate mt-2 text-xs leading-5">
            {data.first_value_symbol
              ? `首个研究标的：${data.first_value_symbol}`
              : "添加一只自选股后，系统会自动开始准备。"}
          </p>
          <Link
            href={companyHref}
            className="bg-ink mt-4 block rounded-xl px-4 py-2.5 text-center text-sm text-white"
          >
            {data.first_value_symbol ? "查看公司研究" : "前往我的自选"}
          </Link>
          <button
            type="button"
            className="border-ink/15 mt-2 w-full rounded-xl border px-4 py-2.5 text-sm disabled:opacity-45"
            disabled={!complete || data.acknowledged || mutation.isPending}
            onClick={() => mutation.mutate("acknowledge")}
          >
            {data.acknowledged ? "评估路径已完成" : "确认完成体验路径"}
          </button>
        </aside>
      </div>
    </Card>
  );
}
