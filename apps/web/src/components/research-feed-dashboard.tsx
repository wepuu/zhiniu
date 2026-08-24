"use client";

import {
  ApiError,
  createZhaoniuClient,
  type FeedSignalResponse,
} from "@zhaoniu/api-client";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  BellRing,
  BookOpenCheck,
  CircleDotDashed,
  Radar,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Card } from "@/components/ui/card";
import { ResearchSectionTabs } from "@/components/research-section-tabs";
import { researchTitle } from "@/lib/presentation";

const api = createZhaoniuClient({ baseUrl: process.env.NEXT_PUBLIC_API_URL });
const sourceLabels = {
  fundamental: "关键变化",
  peer: "同行位置",
  corporate_event: "公司事件",
} as const;
const attentionLabels = {
  info: "记录",
  notice: "留意",
  important: "重点",
} as const;

function SignalCard({ signal }: { signal: FeedSignalResponse }) {
  return (
    <Card className="group overflow-hidden p-0">
      <div className="flex items-start gap-4 p-5 sm:p-6">
        <span
          className={`mt-1 size-2.5 shrink-0 rounded-full ${signal.attention_level === "important" ? "bg-risk" : signal.attention_level === "notice" ? "bg-amber" : "bg-blue"}`}
        />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-data text-blue text-[10px] uppercase tracking-[0.14em]">
              {sourceLabels[signal.source_kind]}
            </span>
            <span className="bg-mist text-slate rounded-full px-2 py-1 text-[10px]">
              {attentionLabels[signal.attention_level]}
            </span>
            <time className="font-data text-slate ml-auto text-[10px]">
              {new Date(signal.known_at).toLocaleString("zh-CN", {
                month: "2-digit",
                day: "2-digit",
                hour: "2-digit",
                minute: "2-digit",
              })}
            </time>
          </div>
          <h3 className="font-display mt-3 text-lg font-semibold leading-7">
            {signal.stock_name} ·{" "}
            {researchTitle(signal.signal_family, signal.title)}
          </h3>
          <p className="text-slate mt-2 text-sm leading-6">{signal.summary}</p>
          <div className="mt-4 flex items-center gap-3">
            <span className="font-data text-slate text-[10px]">
              {signal.symbol}
            </span>
            <span className="text-slate text-xs">
              AI{" "}
              {signal.ai_status === "ready"
                ? "解读可用"
                : signal.ai_status === "disabled"
                  ? "未启用"
                  : "尚未生成"}
            </span>
            <Link
              href={signal.evidence_path}
              className="text-blue ml-auto inline-flex items-center gap-1 text-sm font-medium"
            >
              查看依据{" "}
              <ArrowRight className="size-3.5 transition group-hover:translate-x-0.5" />
            </Link>
          </div>
        </div>
      </div>
    </Card>
  );
}

export function ResearchFeedDashboard() {
  const [source, setSource] = useState<
    "all" | "fundamental" | "peer" | "corporate_event"
  >("all");
  const feed = useQuery({
    queryKey: ["research-feed", source],
    queryFn: () =>
      api.getResearchFeed({
        sourceKind: source === "all" ? undefined : source,
      }),
    retry: (count, error) =>
      !(error instanceof ApiError && error.status === 401) && count < 1,
  });
  const coverage = useQuery({
    queryKey: ["research-coverage"],
    queryFn: () => api.getResearchCoverage(),
    retry: false,
  });
  const unauthorized =
    feed.error instanceof ApiError && feed.error.status === 401;

  return (
    <>
      <ResearchSectionTabs />
      <section className="border-ink/10 flex flex-col gap-4 border-b pb-6 lg:flex-row lg:items-end">
        <div>
          <p className="text-blue text-xs font-medium">个人研究工作台</p>
          <h1 className="font-display mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
            自选研究
          </h1>
          <p className="text-slate mt-2 max-w-2xl text-sm leading-6">
            把自选公司的关键变化、同行位置与公司事件汇入一条按知悉时间排序、可回溯依据的研究流。
          </p>
        </div>
        <div className="flex gap-2 lg:ml-auto">
          <Link
            href="/alerts"
            className="border-ink/10 bg-paper hover:border-blue/30 inline-flex items-center gap-2 rounded-xl border px-4 py-2 text-sm"
          >
            <BellRing className="size-4" /> 研究提醒
          </Link>
          <Link
            href="/watchlist"
            className="bg-blue inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm text-white"
          >
            管理自选 <ArrowRight className="size-4" />
          </Link>
        </div>
      </section>

      {unauthorized ? (
        <Card className="mt-8 p-8 text-center">
          <BookOpenCheck className="text-blue mx-auto size-8" />
          <h2 className="font-display mt-4 text-xl font-semibold">
            登录后查看你的自选研究
          </h2>
          <p className="text-slate mt-2 text-sm">
            研究流只读取你的自选范围，不会复制全局研究数据。
          </p>
          <Link
            href="/login"
            className="bg-blue mt-5 inline-flex rounded-xl px-5 py-2.5 text-sm text-white"
          >
            登录账户
          </Link>
        </Card>
      ) : (
        <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
          <section>
            <div className="mb-4 flex flex-wrap items-center gap-2">
              {(["all", "fundamental", "peer", "corporate_event"] as const).map(
                (item) => (
                  <button
                    key={item}
                    onClick={() => setSource(item)}
                    className={`rounded-full px-3 py-1.5 text-xs ${source === item ? "bg-ink text-white" : "border-ink/10 bg-paper text-slate border"}`}
                  >
                    {item === "all" ? "全部" : sourceLabels[item]}
                  </button>
                ),
              )}
              {feed.isFetching && (
                <span className="font-data text-slate ml-auto flex items-center gap-1 text-[10px]">
                  <CircleDotDashed className="size-3 animate-spin" /> 更新中
                </span>
              )}
            </div>
            {feed.isLoading ? (
              <Card className="h-44 animate-pulse" />
            ) : feed.isError ? (
              <Card className="text-risk p-6 text-sm">
                研究流暂时不可用，请检查应用服务后重试。
              </Card>
            ) : (
              <div className="space-y-8">
                <FeedBlock
                  title="今日新增"
                  items={feed.data?.today.items ?? []}
                  empty="今天还没有新研究信号。"
                />
                <FeedBlock
                  title="最近 14 天"
                  items={feed.data?.recent.items ?? []}
                  empty="自选范围内暂时没有可展示的历史变化。"
                />
              </div>
            )}
          </section>
          <aside>
            <div className="mb-4 flex items-center gap-2">
              <Radar className="text-blue size-4" />
              <h2 className="font-display text-xl font-semibold">研究覆盖</h2>
            </div>
            <Card className="divide-ink/8 divide-y overflow-hidden">
              {coverage.data?.items.map((item) => (
                <div key={item.symbol} className="p-4">
                  <div className="flex items-baseline justify-between">
                    <strong className="text-sm">{item.stock_name}</strong>
                    <span className="font-data text-slate text-[10px]">
                      {item.symbol}
                    </span>
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-2 text-[11px]">
                    {Object.entries(item.coverage).map(([key, value]) => (
                      <span key={key} className="text-slate">
                        <i
                          className={`mr-1.5 inline-block size-1.5 rounded-full ${value === "ready" ? "bg-blue" : value === "unsupported" ? "bg-slate" : "bg-amber"}`}
                        />
                        {
                          {
                            fundamental: "变化",
                            peer: "同行",
                            corporate_event: "事件",
                            ai: "AI",
                          }[key as "fundamental"]
                        }
                      </span>
                    ))}
                  </div>
                </div>
              ))}
              {!coverage.data?.items.length && (
                <p className="text-slate p-5 text-sm">
                  添加自选股后，这里会显示各研究维度的覆盖状态。
                </p>
              )}
            </Card>
          </aside>
        </div>
      )}
    </>
  );
}

function FeedBlock({
  title,
  items,
  empty,
}: {
  title: string;
  items: FeedSignalResponse[];
  empty: string;
}) {
  return (
    <section>
      <h2 className="font-display mb-4 text-xl font-semibold">
        {title}
        <span className="font-data text-slate ml-2 text-[10px]">
          {String(items.length).padStart(2, "0")}
        </span>
      </h2>
      <div className="grid gap-4">
        {items.map((item) => (
          <SignalCard key={item.id} signal={item} />
        ))}
        {!items.length && (
          <Card className="text-slate p-6 text-sm">{empty}</Card>
        )}
      </div>
    </section>
  );
}
