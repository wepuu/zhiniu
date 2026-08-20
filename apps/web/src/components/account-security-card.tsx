"use client";

import {
  ApiError,
  createZhaoniuClient,
  type MeResponse,
  type SessionListResponse,
} from "@zhaoniu/api-client";
import {
  BadgeCheck,
  Laptop,
  LoaderCircle,
  MailWarning,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

const api = createZhaoniuClient();

export function AccountSecurityCard() {
  const [me, setMe] = useState<MeResponse | null>(null);
  const [sessions, setSessions] = useState<SessionListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    void Promise.all([api.getMe(), api.getSessions()])
      .then(([account, activeSessions]) => {
        setMe(account);
        setSessions(activeSessions);
      })
      .catch(() => setMessage("请登录后查看账户安全状态。"))
      .finally(() => setLoading(false));
  }, []);

  async function resend() {
    setMessage(null);
    try {
      const result = await api.resendEmailVerification();
      setMessage(
        result.status === "delivery_unavailable"
          ? "邮件服务暂时不可用，请稍后再试。"
          : "验证邮件已发送，请检查收件箱。",
      );
    } catch (error) {
      setMessage(
        error instanceof ApiError && error.status === 429
          ? "发送过于频繁，请稍后再试。"
          : "暂时无法发送验证邮件。",
      );
    }
  }

  async function revoke(sessionId: string) {
    await api.revokeSession(sessionId);
    setSessions((current) =>
      current
        ? {
            ...current,
            items: current.items.filter((item) => item.id !== sessionId),
            total: current.total - 1,
          }
        : current,
    );
  }

  return (
    <section className="border-ink/10 bg-paper shadow-card rounded-2xl border p-6 sm:p-7 lg:col-span-2">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-data text-blue text-[10px] uppercase tracking-[0.18em]">
            Security
          </p>
          <h2 className="font-display mt-2 text-2xl font-semibold">
            账户与安全
          </h2>
          <p className="text-slate mt-2 text-sm leading-6">
            确认邮箱状态，并检查仍在使用账户的设备。
          </p>
        </div>
        <span className="bg-blue/8 text-blue grid size-11 shrink-0 place-items-center rounded-xl">
          <ShieldCheck className="size-5" />
        </span>
      </div>
      {loading ? (
        <p className="text-slate mt-6 flex items-center gap-2 text-sm">
          <LoaderCircle className="size-4 animate-spin" /> 正在读取安全状态
        </p>
      ) : me ? (
        <div className="mt-6 grid min-w-0 gap-5 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] [&>*]:min-w-0">
          <div className="border-ink/8 bg-mist min-w-0 rounded-xl border p-4">
            <div className="flex items-start gap-3">
              {me.user.email_verified_at ? (
                <BadgeCheck className="text-blue mt-0.5 size-5" />
              ) : (
                <MailWarning className="text-attention mt-0.5 size-5" />
              )}
              <div className="min-w-0">
                <p
                  className="truncate text-sm font-medium"
                  title={me.user.email}
                >
                  {me.user.email}
                </p>
                <p className="text-slate mt-1 text-xs">
                  {me.user.email_verified_at ? "邮箱已验证" : "邮箱尚未验证"}
                </p>
              </div>
            </div>
            {!me.user.email_verified_at && (
              <button
                type="button"
                onClick={() => void resend()}
                className="border-blue/20 text-blue mt-4 min-h-10 w-full rounded-lg border text-sm font-medium"
              >
                重新发送验证邮件
              </button>
            )}
            <Link
              href="/forgot-password"
              className="text-blue mt-4 inline-flex text-sm font-medium"
            >
              通过邮箱重置密码
            </Link>
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <Laptop className="text-blue size-4" />
              <h3 className="text-sm font-semibold">登录设备</h3>
            </div>
            <div className="mt-3 space-y-2">
              {sessions?.items.map((session) => (
                <div
                  key={session.id}
                  className="border-ink/8 flex items-center justify-between gap-3 rounded-xl border px-3.5 py-3 text-sm"
                >
                  <div className="min-w-0">
                    <p className="truncate font-medium">
                      {session.user_agent || "未知设备"}
                    </p>
                    <p className="text-slate mt-1 text-xs">
                      {session.is_current ? "当前设备" : "其他活动会话"}
                    </p>
                  </div>
                  {!session.is_current && (
                    <button
                      type="button"
                      onClick={() => void revoke(session.id)}
                      className="text-risk shrink-0 text-xs font-medium"
                    >
                      退出
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : null}
      {message && (
        <p className="border-ink/8 mt-4 rounded-xl border px-3 py-2 text-sm">
          {message}
        </p>
      )}
    </section>
  );
}
