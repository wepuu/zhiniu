"use client";

import type {
  CorporateEventResponse,
  EventRadarEnvelope,
  EventRadarItemResponse,
} from "@zhaoniu/api-client";
import {
  CalendarClock,
  ChevronRight,
  CircleAlert,
  ExternalLink,
  FileSearch,
  RefreshCw,
  ShieldAlert,
  X,
} from "lucide-react";
import { useState } from "react";

import { Card } from "./ui/card";

const familyLabels: Record<string, string> = {
  share_repurchase: "股份回购",
  share_pledge: "股份质押",
  share_unlock: "限售解禁",
  regulatory_action: "监管行动",
  shareholder_change: "股东增减持",
  litigation_arbitration: "诉讼仲裁",
};

const levelLabels: Record<string, string> = {
  important: "重点核对",
  notice: "持续关注",
  info: "一般信息",
};

function StateCard({
  status,
  onRetry,
}: {
  status: EventRadarEnvelope["status"] | "transport_error";
  onRetry: () => void;
}) {
  const copy = {
    not_built: [
      "事件雷达尚未构建",
      "完成公告同步与事件构建后，这里会显示可回溯的事件。",
    ],
    building: ["事件雷达正在构建", "后台正在整理公告、事件版本与关注层级。"],
    failed: [
      "事件雷达构建失败",
      "旧快照不会被覆盖，请检查后台任务后重试读取。",
    ],
    no_events: [
      "暂未识别到支持的事件",
      "在当前知识截止时间内，没有匹配 Phase 7 范围的公司事件。",
    ],
    transport_error: [
      "事件雷达暂时不可用",
      "其他研究内容不受影响，请检查 API 服务后重试。",
    ],
    ready: ["", ""],
  }[status];
  const loading = status === "building";
  return (
    <Card className="grid min-h-64 place-items-center p-6" role="status">
      <div className="max-w-md text-center">
        {loading ? (
          <RefreshCw className="text-blue mx-auto size-6 animate-spin" />
        ) : (
          <FileSearch className="text-slate mx-auto size-6" />
        )}
        <h3 className="font-display mt-4 text-xl font-semibold">{copy[0]}</h3>
        <p className="text-slate mt-2 text-sm leading-6">{copy[1]}</p>
        {(status === "failed" || status === "transport_error") && (
          <button
            type="button"
            className="bg-ink mt-5 rounded-xl px-4 py-2 text-sm text-white"
            onClick={onRetry}
          >
            重新读取
          </button>
        )}
      </div>
    </Card>
  );
}

function EventCard({
  item,
  onOpen,
}: {
  item: EventRadarItemResponse;
  onOpen: (event: CorporateEventResponse) => void;
}) {
  const level = item.attention_level;
  return (
    <button
      type="button"
      className="border-ink/10 bg-paper hover:border-blue/40 group w-full rounded-2xl border p-4 text-left transition"
      onClick={() => onOpen(item.event)}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="bg-mist rounded-full px-2.5 py-1 text-[10px] font-medium">
              {familyLabels[item.event.event_family] ?? item.event.event_family}
            </span>
            <span
              className={`rounded-full px-2.5 py-1 text-[10px] font-medium ${
                level === "important"
                  ? "bg-risk/10 text-risk"
                  : level === "notice"
                    ? "bg-amber-100 text-amber-800"
                    : "bg-blue/10 text-blue"
              }`}
            >
              {levelLabels[level]}
            </span>
          </div>
          <h4 className="mt-3 line-clamp-2 font-medium leading-6">
            {item.event.title}
          </h4>
          <p className="text-slate mt-2 text-xs leading-5">
            {item.attention_reason}
          </p>
          <p className="font-data text-slate mt-3 text-[10px]">
            公告{" "}
            {new Date(item.event.source_published_at).toLocaleDateString(
              "zh-CN",
            )}
            {item.event.event_effective_from
              ? ` · 生效 ${item.event.event_effective_from}`
              : ""}
          </p>
        </div>
        <ChevronRight className="text-slate group-hover:text-blue mt-1 size-4 shrink-0" />
      </div>
    </button>
  );
}

function EvidencePanel({
  event,
  onClose,
}: {
  event: CorporateEventResponse;
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50"
      role="dialog"
      aria-modal="true"
      aria-label="事件证据"
    >
      <button
        type="button"
        aria-label="关闭事件证据"
        className="absolute inset-0 bg-black/30"
        onClick={onClose}
      />
      <aside className="bg-paper absolute inset-x-0 bottom-0 max-h-[82vh] overflow-y-auto rounded-t-3xl p-5 shadow-2xl md:inset-y-0 md:left-auto md:w-[440px] md:rounded-none md:p-7">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-blue text-xs font-medium">事件证据</p>
            <h3 className="font-display mt-2 text-xl font-semibold leading-8">
              {event.title}
            </h3>
          </div>
          <button
            type="button"
            aria-label="关闭"
            onClick={onClose}
            className="rounded-full p-2 hover:bg-black/5"
          >
            <X className="size-5" />
          </button>
        </div>
        <dl className="border-ink/10 mt-6 divide-y border-y text-sm">
          <div className="flex justify-between gap-4 py-3">
            <dt className="text-slate">事件类型</dt>
            <dd>{familyLabels[event.event_family]}</dd>
          </div>
          <div className="flex justify-between gap-4 py-3">
            <dt className="text-slate">提取状态</dt>
            <dd>{event.extraction_status === "complete" ? "完整" : "部分"}</dd>
          </div>
          <div className="flex justify-between gap-4 py-3">
            <dt className="text-slate">知识可得时间</dt>
            <dd className="font-data text-right">
              {new Date(event.known_at).toLocaleString("zh-CN")}
            </dd>
          </div>
        </dl>
        <div className="mt-6">
          <h4 className="font-medium">原始披露</h4>
          <div className="mt-3 space-y-3">
            {(event.sources ?? []).map((source) => (
              <a
                key={source.document_id}
                href={source.source_url || undefined}
                target="_blank"
                rel="noreferrer"
                className="border-ink/10 hover:border-blue/40 block rounded-xl border p-4"
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="text-slate text-xs uppercase">
                    {source.source_owner}
                  </span>
                  {source.source_url && <ExternalLink className="size-3.5" />}
                </div>
                <p className="mt-2 text-sm leading-6">{source.title}</p>
              </a>
            ))}
          </div>
        </div>
        <p className="text-slate mt-6 text-xs leading-5">
          关注层级由确定性规则生成，仅用于整理披露，不构成投资建议。
        </p>
      </aside>
    </div>
  );
}

export function EventRadarPanel({
  envelope,
  pending,
  error,
  onRetry,
}: {
  envelope?: EventRadarEnvelope;
  pending: boolean;
  error: boolean;
  onRetry: () => void;
}) {
  const [selected, setSelected] = useState<CorporateEventResponse>();
  if (pending && !envelope)
    return <StateCard status="building" onRetry={onRetry} />;
  if (error && !envelope)
    return <StateCard status="transport_error" onRetry={onRetry} />;
  if (!envelope || envelope.status !== "ready") {
    return (
      <StateCard status={envelope?.status ?? "not_built"} onRetry={onRetry} />
    );
  }
  const recentItems = envelope.recent_items ?? [];
  const upcomingItems = envelope.upcoming_items ?? [];
  return (
    <div className="space-y-5">
      <Card className="overflow-hidden p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-blue text-xs font-medium tracking-wide">
              CORPORATE DISCLOSURE
            </p>
            <h3 className="font-display mt-2 text-2xl font-semibold">
              事件雷达
            </h3>
            <p className="text-slate mt-2 max-w-2xl text-sm leading-6">
              从公告中识别公司行动与监管事件，保留版本、时间语义和原始证据。
            </p>
          </div>
          <div className="flex gap-2 text-[10px]">
            <span className="bg-mist rounded-full px-3 py-1.5">
              {envelope.freshness === "stale" ? "有更新待构建" : "当前"}
            </span>
            <span className="bg-mist rounded-full px-3 py-1.5">
              覆盖 {envelope.coverage_status === "complete" ? "完整" : "部分"}
            </span>
          </div>
        </div>
        <div className="border-ink/8 mt-5 grid grid-cols-2 border-t pt-4 text-sm md:grid-cols-4">
          <div>
            <p className="text-slate text-xs">近期披露</p>
            <p className="font-data mt-1 text-xl">{recentItems.length}</p>
          </div>
          <div>
            <p className="text-slate text-xs">即将生效</p>
            <p className="font-data mt-1 text-xl">{upcomingItems.length}</p>
          </div>
          <div className="mt-4 md:mt-0">
            <p className="text-slate text-xs">来源状态</p>
            <p className="mt-1">
              {envelope.source_health === "healthy" ? "正常" : "降级"}
            </p>
          </div>
          <div className="mt-4 md:mt-0">
            <p className="text-slate text-xs">知识截止</p>
            <p className="font-data mt-1 text-xs">
              {envelope.knowledge_cutoff
                ? new Date(envelope.knowledge_cutoff).toLocaleDateString(
                    "zh-CN",
                  )
                : "—"}
            </p>
          </div>
        </div>
      </Card>
      {upcomingItems.length > 0 && (
        <section>
          <div className="mb-3 flex items-center gap-2">
            <CalendarClock className="text-blue size-4" />
            <h3 className="font-medium">即将生效</h3>
          </div>
          <div className="grid gap-3 lg:grid-cols-2">
            {upcomingItems.map((item) => (
              <EventCard key={item.event.id} item={item} onOpen={setSelected} />
            ))}
          </div>
        </section>
      )}
      <section>
        <div className="mb-3 flex items-center gap-2">
          <ShieldAlert className="text-blue size-4" />
          <h3 className="font-medium">近期披露</h3>
        </div>
        <div className="grid gap-3 lg:grid-cols-2">
          {recentItems.map((item) => (
            <EventCard key={item.event.id} item={item} onOpen={setSelected} />
          ))}
        </div>
      </section>
      <div className="text-slate flex items-start gap-2 text-xs leading-5">
        <CircleAlert className="mt-0.5 size-4 shrink-0" />
        <p>事件分类、抽取和关注层级均为确定性规则结果；请以原始披露为准。</p>
      </div>
      {selected && (
        <EvidencePanel
          event={selected}
          onClose={() => setSelected(undefined)}
        />
      )}
    </div>
  );
}
