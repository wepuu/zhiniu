"use client";

import { createZhaoniuClient } from "@zhaoniu/api-client";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Clock3, ShieldCheck } from "lucide-react";

import { Card } from "@/components/ui/card";
import { translateReasonCode } from "@/lib/presentation";

const api = createZhaoniuClient({ baseUrl: process.env.NEXT_PUBLIC_API_URL });

const categoryLabels: Record<string, string> = {
  platform: "平台基础",
  access: "邀请准入",
  automation: "自动准备",
  provider: "AI 服务",
  reliability: "可靠性证据",
  release: "发布门禁",
};

function dateTime(value?: string | null) {
  return value
    ? new Intl.DateTimeFormat("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      }).format(new Date(value))
    : "—";
}

function shortIdentity(value: string) {
  return value.length > 16 ? `${value.slice(0, 12)}…` : value;
}

export function BetaAdmissionPanel() {
  const query = useQuery({
    queryKey: ["beta-admission"],
    queryFn: () => api.getBetaAdmission(),
    refetchInterval: 60_000,
  });

  if (query.isLoading) {
    return (
      <Card className="mb-5 p-5 text-sm text-slate-500">
        正在汇总 Beta 准入证据…
      </Card>
    );
  }
  if (query.error || !query.data) {
    return (
      <Card className="mb-5 border-red-200 bg-red-50 p-5 text-sm text-red-700">
        暂时无法读取 Beta 准入证据，请稍后重试。
      </Card>
    );
  }

  const snapshot = query.data;
  const ready = snapshot.status === "ready";
  return (
    <Card className="mb-5 overflow-hidden">
      <div className="border-b border-slate-100 p-5 md:flex md:items-start md:justify-between">
        <div className="flex items-start gap-3">
          <span
            className={`grid size-10 shrink-0 place-items-center rounded-xl ${ready ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}
          >
            <ShieldCheck className="size-5" />
          </span>
          <div>
            <p className="text-xs font-medium text-blue-700">受控 Beta 准入</p>
            <h2 className="mt-1 text-lg font-semibold">
              {ready ? "准入证据已满足" : "仍有阻塞项"}
            </h2>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              这里只汇总已留存事实；不会自动放开注册、邀请或生产权限。
            </p>
          </div>
        </div>
        <p className="mt-3 text-xs text-slate-500 md:mt-0">
          {snapshot.environment} · {dateTime(snapshot.generated_at)}
        </p>
      </div>
      {snapshot.candidate ? (
        <div className="grid gap-3 border-b border-slate-100 bg-slate-50/70 px-5 py-4 text-xs text-slate-600 md:grid-cols-2 xl:grid-cols-4">
          <div>
            <p className="text-slate-400">候选版本</p>
            <p className="mt-1 font-mono" title={snapshot.candidate.commit_sha}>
              {shortIdentity(snapshot.candidate.commit_sha)}
            </p>
          </div>
          <div>
            <p className="text-slate-400">迁移头 / 状态</p>
            <p className="mt-1 font-mono">
              {snapshot.candidate.migration_head} · {snapshot.candidate.status}
            </p>
          </div>
          <div>
            <p className="text-slate-400">配置指纹</p>
            <p
              className="mt-1 font-mono"
              title={snapshot.candidate.configuration_fingerprint}
            >
              {shortIdentity(snapshot.candidate.configuration_fingerprint)}
            </p>
          </div>
          <div>
            <p className="text-slate-400">部署证据</p>
            <p className="mt-1 break-all font-mono">
              {snapshot.candidate.deployment_ref ?? "尚未记录"}
            </p>
          </div>
        </div>
      ) : (
        <div className="border-b border-amber-100 bg-amber-50 px-5 py-3 text-xs text-amber-800">
          尚未创建生产候选版本，所有候选绑定门禁保持阻塞。
        </div>
      )}
      <div className="grid gap-px bg-slate-100 md:grid-cols-2 xl:grid-cols-3">
        {snapshot.checks.map((check) => {
          const passed = check.status === "passed";
          const pending = check.status === "pending";
          const Icon = passed ? CheckCircle2 : pending ? Clock3 : AlertTriangle;
          return (
            <div key={check.key} className="bg-white p-4">
              <div className="flex items-center gap-2">
                <Icon
                  className={`size-4 ${passed ? "text-emerald-600" : pending ? "text-amber-600" : "text-red-600"}`}
                />
                <p className="text-sm font-medium">
                  {categoryLabels[check.category] ?? check.category}
                </p>
                <span className="ml-auto font-mono text-[10px] text-slate-400">
                  {check.status}
                </span>
              </div>
              <p className="mt-2 break-all font-mono text-[10px] text-slate-500">
                {check.key}
              </p>
              {check.reason_code && (
                <p className="mt-2 text-xs leading-5 text-slate-600">
                  {translateReasonCode(check.reason_code)}
                  <span className="ml-1 font-mono text-[10px] text-slate-400">
                    {check.reason_code}
                  </span>
                </p>
              )}
              {check.observed_at && (
                <p className="mt-2 text-[11px] text-slate-400">
                  证据时间 {dateTime(check.observed_at)}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}
