"use client";

import {
  ApiError,
  createZhaoniuClient,
  type ScreenQuery,
} from "@zhaoniu/api-client";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ArrowDown,
  Bot,
  LoaderCircle,
  LockKeyhole,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Card } from "@/components/ui/card";

const api = createZhaoniuClient({
  baseUrl: process.env.NEXT_PUBLIC_API_BASE_URL,
});

export function NaturalLanguageScreenInput({
  onApply,
}: {
  onApply: (
    query: ScreenQuery,
    parseRunId: string,
    originalText: string,
  ) => void;
}) {
  const [text, setText] = useState("");
  const [parseRunId, setParseRunId] = useState<string | null>(null);
  const createParse = useMutation({
    mutationFn: () => api.createNaturalLanguageScreenParse(text.trim()),
    onSuccess: (run) => setParseRunId(run.id),
  });
  const parse = useQuery({
    queryKey: ["natural-language-screen-parse", parseRunId],
    queryFn: () => api.getNaturalLanguageScreenParse(parseRunId!),
    enabled: Boolean(parseRunId),
    retry: false,
    refetchInterval: (query) =>
      query.state.data?.status === "pending" ||
      query.state.data?.status === "running"
        ? 1000
        : false,
  });
  const run = parse.data ?? createParse.data;
  const authRequired =
    (createParse.error instanceof ApiError &&
      createParse.error.status === 401) ||
    (parse.error instanceof ApiError && parse.error.status === 401);
  const pending =
    createParse.isPending ||
    run?.status === "pending" ||
    run?.status === "running";

  return (
    <Card className="border-blue/15 bg-[linear-gradient(135deg,rgba(41,95,143,0.08),rgba(251,252,252,0.98)_48%)] p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="bg-blue text-paper inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold">
              <Sparkles className="size-3" /> AI 条件解析
            </span>
            <span className="text-slate text-xs">
              结果仍由确定性筛选引擎计算
            </span>
          </div>
          <h2 className="font-display mt-3 text-xl font-semibold sm:text-2xl">
            用一句话描述你的研究条件
          </h2>
          <p className="text-slate mt-1 text-sm leading-6">
            例如：毛利率不低于 30%，且最近一年没有监管措施。
          </p>
        </div>
        <Bot className="text-blue/70 size-6" />
      </div>
      <div className="mt-4 flex flex-col gap-2 sm:flex-row">
        <textarea
          aria-label="自然语言筛选条件"
          value={text}
          maxLength={500}
          rows={2}
          onChange={(event) => {
            setText(event.target.value);
            setParseRunId(null);
            createParse.reset();
          }}
          placeholder="输入研究条件，AI 只负责转换为可确认的筛选条件"
          className="border-ink/10 bg-paper text-ink placeholder:text-slate/70 min-h-20 flex-1 resize-none rounded-xl border px-3.5 py-3 text-sm leading-6"
        />
        <button
          type="button"
          disabled={text.trim().length < 2 || pending}
          onClick={() => createParse.mutate()}
          className="bg-ink text-paper inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-5 text-sm font-medium disabled:opacity-50 sm:self-stretch"
        >
          {pending ? (
            <LoaderCircle className="size-4 animate-spin" />
          ) : (
            <Sparkles className="size-4" />
          )}
          {pending ? "正在解析" : "解析条件"}
        </button>
      </div>
      <div className="text-slate mt-2 flex justify-between text-[11px]">
        <span>不会保存这段原文，除非你主动保存为筛选方案。</span>
        <span className="font-data">{text.length}/500</span>
      </div>

      {authRequired && (
        <ParseNotice icon={LockKeyhole} title="登录后使用 AI 条件解析">
          <Link href="/login?next=/screens" className="text-blue font-medium">
            登录账户
          </Link>
        </ParseNotice>
      )}
      {run?.status === "disabled" && (
        <ParseNotice icon={Bot} title="AI 条件解析尚未启用">
          你仍可使用下方条件构建器完成确定性筛选。
        </ParseNotice>
      )}
      {run?.status === "rejected" && (
        <ParseNotice icon={Bot} title="这段描述超出研究筛选边界">
          请改为财务、估值、同行、行业或公司事件等客观条件。
        </ParseNotice>
      )}
      {run?.status === "failed" && (
        <ParseNotice icon={Bot} title="本次条件解析未完成">
          可重新提交，或直接使用下方条件构建器。
        </ParseNotice>
      )}
      {run?.status === "succeeded" &&
        run.result?.semantic_status === "ambiguous" && (
          <ParseNotice icon={Bot} title="还需要你确认一个细节">
            {run.result.clarification ?? run.result.summary}
          </ParseNotice>
        )}
      {run?.status === "succeeded" &&
        run.result?.semantic_status === "unsupported" && (
          <ParseNotice icon={Bot} title="当前筛选目录暂不支持这组条件">
            {run.result.summary}
          </ParseNotice>
        )}
      {run?.status === "succeeded" &&
        run.result?.semantic_status === "ready" &&
        run.result.query && (
          <div className="border-blue/15 bg-paper mt-4 flex flex-col gap-3 rounded-xl border p-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-blue text-xs font-semibold">已生成候选条件</p>
              <p className="text-ink mt-1 text-sm">{run.result.summary}</p>
            </div>
            <button
              type="button"
              onClick={() => onApply(run.result!.query!, run.id, text.trim())}
              className="border-blue/20 text-blue inline-flex min-h-10 shrink-0 items-center justify-center gap-1.5 rounded-lg border px-3 text-sm font-medium"
            >
              确认并带入条件 <ArrowDown className="size-4" />
            </button>
          </div>
        )}
    </Card>
  );
}

function ParseNotice({
  icon: Icon,
  title,
  children,
}: {
  icon: typeof Bot;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className="border-ink/8 bg-paper mt-4 flex gap-3 rounded-xl border p-3"
      role="status"
    >
      <Icon className="text-blue mt-0.5 size-4 shrink-0" />
      <div>
        <p className="text-sm font-medium">{title}</p>
        <div className="text-slate mt-1 text-xs leading-5">{children}</div>
      </div>
    </div>
  );
}
