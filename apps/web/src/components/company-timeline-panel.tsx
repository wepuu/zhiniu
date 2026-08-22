"use client";

import {
  createZhaoniuClient,
  type CompanyTimelineEnvelope,
  type CompanyTimelineItem,
} from "@zhaoniu/api-client";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Building2,
  CalendarClock,
  ChevronRight,
  CircleDot,
  GitBranch,
  RefreshCw,
  Scale,
  TriangleAlert,
  UsersRound,
  X,
} from "lucide-react";
import { useMemo, useState } from "react";

import { Card } from "./ui/card";

const api = createZhaoniuClient();

const sourceCopy = {
  fundamental: {
    label: "基本面",
    icon: Building2,
    tone: "bg-blue/10 text-blue",
  },
  peer: { label: "同行", icon: UsersRound, tone: "bg-amber/15 text-amber-800" },
  corporate_event: {
    label: "公司事件",
    icon: Scale,
    tone: "bg-risk/10 text-risk",
  },
} as const;

const attentionCopy = {
  info: "记录",
  notice: "需关注",
  important: "重点核对",
} as const;

type SourceFilter = "all" | CompanyTimelineItem["source_kind"];

function formatKnownAt(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function groupByDate(items: CompanyTimelineItem[]) {
  return items.reduce<Record<string, CompanyTimelineItem[]>>((groups, item) => {
    const date = new Intl.DateTimeFormat("zh-CN", {
      year: "numeric",
      month: "long",
      day: "numeric",
    }).format(new Date(item.known_at));
    groups[date] = [...(groups[date] ?? []), item];
    return groups;
  }, {});
}

function TimelineState({
  envelope,
  error,
  onRetry,
}: {
  envelope?: CompanyTimelineEnvelope;
  error: boolean;
  onRetry: () => void;
}) {
  const copy = error
    ? ["研究时间线暂时不可用", "请检查 API 服务后重试。"]
    : envelope?.status === "not_built"
      ? [
          "研究时间线尚未形成",
          "完成确定性研究、同行或事件构建后，这里会按知悉时间展示变化。",
        ]
      : envelope?.status === "partial"
        ? [
            "部分研究来源尚未准备完成",
            "已有变化仍会如实展示，缺失来源不会用推测补齐。",
          ]
        : [
            "当前时间范围内没有研究变化",
            "这表示已构建来源暂未形成新的研究信号。",
          ];
  return (
    <Card className="border-ink/10 p-8 text-center">
      {error ? (
        <TriangleAlert className="text-risk mx-auto size-5" />
      ) : (
        <CircleDot className="text-slate mx-auto size-5" />
      )}
      <h3 className="mt-3 font-medium">{copy[0]}</h3>
      <p className="text-slate mx-auto mt-1 max-w-lg text-sm">{copy[1]}</p>
      {error && (
        <button
          type="button"
          onClick={onRetry}
          className="bg-ink mt-4 rounded-xl px-4 py-2 text-sm text-white"
        >
          重新读取
        </button>
      )}
    </Card>
  );
}

function ThreadSheet({
  symbol,
  eventId,
  onClose,
}: {
  symbol: string;
  eventId: string;
  onClose: () => void;
}) {
  const thread = useQuery({
    queryKey: ["stock", symbol, "event-thread", eventId],
    queryFn: () => api.getEventThread(symbol, eventId),
  });
  return (
    <div
      className="fixed inset-0 z-50 bg-black/35"
      role="presentation"
      onClick={onClose}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-label="事件进展"
        className="bg-paper absolute inset-x-0 bottom-0 max-h-[86vh] overflow-y-auto rounded-t-3xl p-5 shadow-2xl md:inset-y-0 md:left-auto md:right-0 md:w-[460px] md:rounded-none md:p-7"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-blue text-xs font-medium">EVENT THREAD</p>
            <h3 className="font-display mt-1 text-2xl font-semibold">
              事件进展
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="关闭事件进展"
            className="rounded-full p-2 hover:bg-black/5"
          >
            <X className="size-5" />
          </button>
        </div>
        {thread.isPending && (
          <div
            className="text-slate flex items-center gap-2 py-10 text-sm"
            role="status"
          >
            <RefreshCw className="size-4 animate-spin" /> 正在读取事件版本
          </div>
        )}
        {thread.isError && (
          <p className="text-risk py-8 text-sm">事件进展暂时无法读取。</p>
        )}
        <div className="mt-6 space-y-0">
          {thread.data?.items.map((item, index) => (
            <div
              key={item.id}
              className="relative grid grid-cols-[20px_1fr] gap-3 pb-6"
            >
              {index < thread.data.items.length - 1 && (
                <span className="bg-ink/10 absolute bottom-0 left-[9px] top-5 w-px" />
              )}
              <span className="bg-paper border-blue mt-1 size-5 rounded-full border-[5px]" />
              <div>
                <p className="text-slate font-data text-xs">
                  {formatKnownAt(item.known_at)}
                </p>
                <p className="mt-1 font-medium">{item.title}</p>
                <p className="text-slate mt-1 text-xs">
                  阶段：{item.event_type}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

export function CompanyTimelinePanel({
  symbol,
  envelope,
  pending,
  error,
  onRetry,
  onNavigate,
  compact = false,
}: {
  symbol: string;
  envelope?: CompanyTimelineEnvelope;
  pending: boolean;
  error: boolean;
  onRetry: () => void;
  onNavigate: (source: CompanyTimelineItem["source_kind"]) => void;
  compact?: boolean;
}) {
  const [filter, setFilter] = useState<SourceFilter>("all");
  const [selectedEvent, setSelectedEvent] = useState<string>();
  const allItems = useMemo(() => envelope?.items ?? [], [envelope?.items]);
  const upcomingEvents = envelope?.upcoming_events ?? [];
  const visible = useMemo(
    () =>
      allItems.filter(
        (item) => filter === "all" || item.source_kind === filter,
      ),
    [allItems, filter],
  );
  const groups = groupByDate(visible);

  if (pending) {
    return (
      <Card className="grid min-h-64 place-items-center p-6" role="status">
        <div className="text-center">
          <RefreshCw className="text-blue mx-auto size-5 animate-spin" />
          <p className="mt-3 font-medium">正在整理公司研究时间线</p>
        </div>
      </Card>
    );
  }
  if (error || !envelope || allItems.length === 0) {
    return (
      <TimelineState envelope={envelope} error={error} onRetry={onRetry} />
    );
  }

  const summary = envelope.summary;
  return (
    <div>
      <div className="mb-4 flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
        <div>
          <p className="text-blue text-xs font-medium uppercase tracking-[0.14em]">
            Company research
          </p>
          <h2 className="font-display mt-1 text-2xl font-semibold">
            研究时间线
          </h2>
          <p className="text-slate mt-1 text-sm">
            按系统可知时间排序，发生或计划时间单独标记。
          </p>
        </div>
        <div className="flex max-w-full gap-2 overflow-x-auto pb-1 [scrollbar-width:none]">
          {(["all", "fundamental", "peer", "corporate_event"] as const).map(
            (value) => (
              <button
                key={value}
                type="button"
                onClick={() => setFilter(value)}
                className={`min-h-9 shrink-0 rounded-full px-4 text-xs font-medium ${filter === value ? "bg-ink text-white" : "border-ink/10 bg-paper text-slate border"}`}
              >
                {value === "all" ? "全部" : sourceCopy[value].label}
              </button>
            ),
          )}
        </div>
      </div>

      <div
        className={`grid gap-4 ${compact ? "" : "lg:grid-cols-[minmax(0,1fr)_280px]"}`}
      >
        <div className="space-y-6">
          {Object.entries(groups).map(([date, items]) => (
            <section key={date} aria-label={date}>
              <p className="text-slate mb-3 text-xs font-medium">{date}</p>
              <div className="border-ink/10 ml-2 border-l pl-5">
                {items.map((item) => {
                  const source = sourceCopy[item.source_kind];
                  const Icon = source.icon;
                  return (
                    <article key={item.id} className="relative pb-4 last:pb-0">
                      <span className="bg-paper border-blue absolute -left-[27px] top-5 size-3 rounded-full border-[3px]" />
                      <Card className="border-ink/10 p-4 sm:p-5">
                        <div className="flex flex-wrap items-center gap-2">
                          <span
                            className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-medium ${source.tone}`}
                          >
                            <Icon className="size-3" /> {source.label}
                          </span>
                          <span className="text-slate text-[11px]">
                            {attentionCopy[item.attention_level]}
                          </span>
                          <span className="text-slate font-data ml-auto text-[11px]">
                            知悉 {formatKnownAt(item.known_at)}
                          </span>
                        </div>
                        <h3 className="mt-3 font-medium leading-6">
                          {item.title}
                        </h3>
                        <p className="text-slate mt-1.5 text-sm leading-6">
                          {item.summary}
                        </p>
                        {item.effective_on && (
                          <p className="text-slate mt-3 flex items-center gap-1.5 text-xs">
                            <CalendarClock className="size-3.5" />{" "}
                            发生或计划时间 {item.effective_on}
                          </p>
                        )}
                        <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-black/5 pt-3">
                          <button
                            type="button"
                            onClick={() => onNavigate(item.source_kind)}
                            className="text-blue inline-flex items-center gap-1 text-xs font-medium"
                          >
                            查看依据 <ChevronRight className="size-3.5" />
                          </button>
                          {item.source_kind === "corporate_event" &&
                            item.event_thread && (
                              <button
                                type="button"
                                onClick={() =>
                                  setSelectedEvent(item.source_artifact.id)
                                }
                                className="text-slate inline-flex items-center gap-1 text-xs"
                              >
                                <GitBranch className="size-3.5" /> 事件进展{" "}
                                {item.event_thread.current_index}/
                                {item.event_thread.version_count}
                              </button>
                            )}
                        </div>
                      </Card>
                    </article>
                  );
                })}
              </div>
            </section>
          ))}
        </div>

        {!compact && (
          <aside className="space-y-4">
            <Card className="border-ink/10 p-5">
              <p className="text-slate text-xs">最近 30 天</p>
              <p className="font-data mt-1 text-3xl font-semibold">
                {summary.recent_30d_total}
              </p>
              <div className="text-slate mt-4 grid grid-cols-2 gap-3 text-xs">
                <span>基本面 {summary.fundamental_count}</span>
                <span>同行 {summary.peer_count}</span>
                <span>事件 {summary.corporate_event_count}</span>
                <span>重点核对 {summary.important_count}</span>
              </div>
            </Card>
            <Card className="border-ink/10 p-5">
              <div className="flex items-center gap-2">
                <CalendarClock className="text-blue size-4" />
                <h3 className="font-medium">即将发生</h3>
              </div>
              {upcomingEvents.length === 0 ? (
                <p className="text-slate mt-3 text-sm">
                  当前没有可可靠确定日期的未来事件。
                </p>
              ) : (
                <div className="mt-3 space-y-3">
                  {upcomingEvents.map((item) => (
                    <button
                      key={item.event_id}
                      type="button"
                      onClick={() => setSelectedEvent(item.event_id)}
                      className="group w-full text-left"
                    >
                      <p className="font-data text-blue text-xs">
                        {item.effective_on}
                      </p>
                      <p className="mt-1 text-sm leading-5">{item.title}</p>
                      <ArrowRight className="text-slate mt-1 size-3.5 transition group-hover:translate-x-1" />
                    </button>
                  ))}
                </div>
              )}
            </Card>
          </aside>
        )}
      </div>
      {selectedEvent && (
        <ThreadSheet
          symbol={symbol}
          eventId={selectedEvent}
          onClose={() => setSelectedEvent(undefined)}
        />
      )}
    </div>
  );
}
