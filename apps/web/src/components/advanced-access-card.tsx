"use client";

import {
  ApiError,
  createZhaoniuClient,
  type AccessEnvelope,
} from "@zhaoniu/api-client";
import { BadgeCheck, KeyRound, LoaderCircle } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

const api = createZhaoniuClient();

const statusLabel: Record<AccessEnvelope["access_status"], string> = {
  basic: "未开通",
  enabled: "已开通",
  expired: "已到期",
};

function displayDate(value: string | null | undefined) {
  if (!value) return null;
  return new Intl.DateTimeFormat("zh-CN", { dateStyle: "long" }).format(
    new Date(value),
  );
}

export function AdvancedAccessCard() {
  const [access, setAccess] = useState<AccessEnvelope | null>(null);
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        setAccess(await api.getAccess());
      } catch {
        setMessage("暂时无法读取高级功能状态，请稍后重试。");
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, []);

  async function activate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setMessage(null);
    try {
      const updated = await api.activateAccess(code);
      setAccess(updated);
      setCode("");
      setMessage("高级功能已开通。");
    } catch (error) {
      setMessage(
        error instanceof ApiError && error.status === 503
          ? "当前暂不可激活，请联系客服。"
          : "激活码不可用，请核对后重试。",
      );
    } finally {
      setSubmitting(false);
    }
  }

  const validUntil = displayDate(access?.valid_until);

  return (
    <section className="border-ink/10 bg-paper shadow-card rounded-2xl border p-6 sm:p-7">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-data text-blue text-[10px] uppercase tracking-[0.18em]">
            Access
          </p>
          <h1 className="font-display mt-2 text-2xl font-semibold">高级功能</h1>
          <p className="text-slate mt-2 text-sm leading-6">
            解锁自然语言研究筛选等增强能力，研究数据与证据边界保持不变。
          </p>
        </div>
        <span className="bg-blue/8 text-blue grid size-11 shrink-0 place-items-center rounded-xl">
          {access?.access_status === "enabled" ? (
            <BadgeCheck className="size-5" />
          ) : (
            <KeyRound className="size-5" />
          )}
        </span>
      </div>

      <div className="border-ink/8 bg-mist mt-6 rounded-xl border px-4 py-3">
        {loading ? (
          <span className="text-slate flex items-center gap-2 text-sm">
            <LoaderCircle className="size-4 animate-spin" /> 正在读取状态
          </span>
        ) : (
          <div className="flex items-center justify-between gap-4 text-sm">
            <span className="text-slate">当前状态</span>
            <strong>
              {access ? statusLabel[access.access_status] : "读取失败"}
            </strong>
          </div>
        )}
        {validUntil && (
          <div className="border-ink/8 mt-3 flex items-center justify-between gap-4 border-t pt-3 text-sm">
            <span className="text-slate">有效期至</span>
            <strong className="font-data">{validUntil}</strong>
          </div>
        )}
      </div>

      {access?.access_status !== "enabled" && (
        <form className="mt-5" onSubmit={activate}>
          <label className="block text-sm font-medium">
            激活码
            <input
              className="border-ink/15 focus:border-blue font-data mt-2 w-full rounded-xl border bg-white px-4 py-3 uppercase outline-none transition"
              value={code}
              onChange={(event) => setCode(event.target.value)}
              placeholder="ACT-..."
              disabled={!access?.activation_available || submitting}
              required
            />
          </label>
          <button
            className="bg-blue mt-4 flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
            disabled={!access?.activation_available || submitting}
          >
            {submitting && <LoaderCircle className="size-4 animate-spin" />}
            激活高级功能
          </button>
        </form>
      )}

      <p className="text-slate mt-5 text-sm leading-6">
        {access?.activation_available
          ? "请联系知牛客服获取激活码。"
          : "高级功能激活暂未开放，请联系客服了解可用情况。"}
      </p>
      {access?.support_contact_url && (
        <a
          className="text-blue mt-2 inline-flex text-sm font-medium"
          href={access.support_contact_url}
        >
          联系客服
        </a>
      )}
      {message && (
        <p className="border-ink/8 mt-4 rounded-xl border px-3 py-2 text-sm">
          {message}
        </p>
      )}
    </section>
  );
}
