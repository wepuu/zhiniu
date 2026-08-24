"use client";

import { ApiError, createZhaoniuClient } from "@zhaoniu/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BellRing, CheckCheck, ExternalLink } from "lucide-react";
import Link from "next/link";

import { researchTitle } from "@/lib/presentation";
import { Card } from "@/components/ui/card";

const api = createZhaoniuClient({ baseUrl: process.env.NEXT_PUBLIC_API_URL });

export function ResearchAlerts() {
  const client = useQueryClient();
  const alerts = useQuery({
    queryKey: ["research-alerts"],
    queryFn: () => api.getResearchAlerts(),
    retry: false,
  });
  const allRead = useMutation({
    mutationFn: () => api.markAllResearchAlertsRead(),
    onSuccess: () =>
      client.invalidateQueries({ queryKey: ["research-alerts"] }),
  });
  const read = useMutation({
    mutationFn: (id: string) => api.markResearchAlertRead(id),
    onSuccess: () =>
      client.invalidateQueries({ queryKey: ["research-alerts"] }),
  });
  const unauthorized =
    alerts.error instanceof ApiError && alerts.error.status === 401;
  return (
    <>
      <section className="border-ink/10 flex items-end gap-4 border-b pb-6">
        <div>
          <p className="font-data text-blue text-[11px] uppercase tracking-[0.18em]">
            In-app alerts
          </p>
          <h1 className="font-display mt-2 text-3xl font-semibold sm:text-4xl">
            研究提醒
          </h1>
          <p className="text-slate mt-2 text-sm leading-6">
            只提醒加入自选后新出现、且达到你的关注门槛的研究信号。
          </p>
        </div>
        {!!alerts.data?.unread_count && (
          <button
            onClick={() => allRead.mutate()}
            className="border-ink/10 bg-paper ml-auto inline-flex items-center gap-2 rounded-xl border px-4 py-2 text-sm"
          >
            <CheckCheck className="size-4" />
            全部已读
          </button>
        )}
      </section>
      {unauthorized ? (
        <Card className="mt-8 p-8 text-center">
          <BellRing className="text-blue mx-auto size-8" />
          <h2 className="font-display mt-4 text-xl font-semibold">
            登录后查看研究提醒
          </h2>
          <Link
            href="/login"
            className="bg-blue mt-5 inline-flex rounded-xl px-5 py-2.5 text-sm text-white"
          >
            登录账户
          </Link>
        </Card>
      ) : (
        <div className="mt-6 max-w-4xl space-y-3">
          {alerts.isLoading ? (
            <Card className="h-36 animate-pulse" />
          ) : alerts.isError ? (
            <Card className="text-risk p-6">提醒暂时不可用，请稍后重试。</Card>
          ) : alerts.data?.items.length ? (
            alerts.data.items.map((item) => (
              <Card
                key={item.id}
                className={`${item.read_at ? "opacity-70" : "border-blue/20"} p-5`}
              >
                <div className="flex gap-4">
                  <span
                    className={`mt-2 size-2 shrink-0 rounded-full ${item.read_at ? "bg-slate/40" : "bg-blue"}`}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-data text-blue text-[10px] uppercase">
                        {item.signal.stock_name} · {item.signal.symbol}
                      </span>
                      <time className="font-data text-slate ml-auto text-[10px]">
                        {new Date(item.created_at).toLocaleString("zh-CN")}
                      </time>
                    </div>
                    <h2 className="font-display mt-2 text-lg font-semibold">
                      {researchTitle(
                        item.signal.signal_family,
                        item.signal.title,
                      )}
                    </h2>
                    <p className="text-slate mt-2 text-sm leading-6">
                      {item.signal.summary}
                    </p>
                    <div className="mt-4 flex items-center gap-4">
                      {!item.read_at && (
                        <button
                          onClick={() => read.mutate(item.id)}
                          className="text-blue text-xs"
                        >
                          标为已读
                        </button>
                      )}
                      <Link
                        href={item.signal.evidence_path}
                        className="text-blue ml-auto inline-flex items-center gap-1 text-sm"
                      >
                        查看依据 <ExternalLink className="size-3.5" />
                      </Link>
                    </div>
                  </div>
                </div>
              </Card>
            ))
          ) : (
            <Card className="p-8 text-center">
              <BellRing className="text-slate mx-auto size-7" />
              <h2 className="font-display mt-3 text-lg font-semibold">
                暂无研究提醒
              </h2>
              <p className="text-slate mt-2 text-sm">
                历史信号不会补发提醒；新信号出现后会按你的设置匹配。
              </p>
            </Card>
          )}
        </div>
      )}
    </>
  );
}
