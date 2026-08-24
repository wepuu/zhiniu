"use client";

import {
  ApiError,
  createZhaoniuClient,
  type BetaFeedbackCreate,
} from "@zhaoniu/api-client";
import { CheckCircle2, LoaderCircle, MessageSquareText } from "lucide-react";
import { FormEvent, useState } from "react";

const api = createZhaoniuClient();

const features: Array<[BetaFeedbackCreate["feature_key"], string]> = [
  ["stock_research", "个股研究"],
  ["research_feed", "研究动态"],
  ["peer_research", "同行研究"],
  ["event_radar", "事件雷达"],
  ["screening", "研究筛选"],
  ["account", "账户与访问"],
  ["other", "其他"],
];

const categories: Array<[BetaFeedbackCreate["category"], string]> = [
  ["bug", "功能异常"],
  ["data_missing", "数据缺失"],
  ["hard_to_understand", "难以理解"],
  ["feature_request", "功能建议"],
  ["other", "其他"],
];

export function BetaFeedbackCard() {
  const [feature, setFeature] =
    useState<BetaFeedbackCreate["feature_key"]>("stock_research");
  const [category, setCategory] =
    useState<BetaFeedbackCreate["category"]>("bug");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<
    "success" | "rate_limited" | "error" | null
  >(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setResult(null);
    try {
      await api.createBetaFeedback({
        feature_key: feature,
        category,
        message: message.trim(),
      });
      setMessage("");
      setResult("success");
    } catch (error) {
      setResult(
        error instanceof ApiError && error.status === 429
          ? "rate_limited"
          : "error",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="border-ink/10 bg-paper shadow-card rounded-2xl border p-6 sm:p-7">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-data text-blue text-[10px] uppercase tracking-[0.18em]">
            内测体验反馈
          </p>
          <h2 className="font-display mt-2 text-2xl font-semibold">体验反馈</h2>
          <p className="text-slate mt-2 text-sm leading-6">
            告诉我们哪项研究能力需要修正。反馈用于改进内测，不会触发投资建议或自动生成研究。
          </p>
        </div>
        <span className="bg-blue/8 text-blue grid size-11 shrink-0 place-items-center rounded-xl">
          <MessageSquareText className="size-5" />
        </span>
      </div>

      <form className="mt-6 space-y-4" onSubmit={submit}>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="text-sm font-medium">
            相关功能
            <select
              className="border-ink/15 bg-paper focus:border-blue mt-2 w-full rounded-xl border px-3 py-3 outline-none"
              value={feature}
              onChange={(event) =>
                setFeature(
                  event.target.value as BetaFeedbackCreate["feature_key"],
                )
              }
            >
              {features.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm font-medium">
            反馈类型
            <select
              className="border-ink/15 bg-paper focus:border-blue mt-2 w-full rounded-xl border px-3 py-3 outline-none"
              value={category}
              onChange={(event) =>
                setCategory(
                  event.target.value as BetaFeedbackCreate["category"],
                )
              }
            >
              {categories.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <label className="block text-sm font-medium">
          具体情况
          <textarea
            className="border-ink/15 focus:border-blue mt-2 min-h-28 w-full resize-y rounded-xl border bg-white px-4 py-3 outline-none transition"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            minLength={20}
            maxLength={2000}
            placeholder="请说明出现问题的页面、股票代码和你预期看到的内容（至少 20 个字）"
            required
          />
        </label>
        <p className="text-slate text-xs">
          请勿填写密码、激活码、身份证件或其他敏感信息。
        </p>
        <button
          className="bg-ink flex min-h-11 w-full items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-medium text-white disabled:opacity-50"
          disabled={submitting || message.trim().length < 20}
        >
          {submitting && <LoaderCircle className="size-4 animate-spin" />}
          提交反馈
        </button>
      </form>

      {result === "success" && (
        <p
          className="text-blue mt-4 flex items-center gap-2 text-sm"
          role="status"
        >
          <CheckCircle2 className="size-4" />{" "}
          反馈已记录，感谢你帮助完善内测体验。
        </p>
      )}
      {result === "rate_limited" && (
        <p className="text-risk mt-4 text-sm" role="alert">
          提交较频繁，请稍后再试。
        </p>
      )}
      {result === "error" && (
        <p className="text-risk mt-4 text-sm" role="alert">
          暂时无法提交反馈，请稍后重试。
        </p>
      )}
    </section>
  );
}
