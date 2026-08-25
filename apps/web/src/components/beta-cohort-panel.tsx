"use client";

import { ApiError, createZhaoniuClient } from "@zhaoniu/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  LoaderCircle,
  Plus,
  Send,
  ShieldAlert,
  UsersRound,
} from "lucide-react";
import { FormEvent, useState } from "react";

import { Card } from "@/components/ui/card";
import { translateReasonCode } from "@/lib/presentation";

const api = createZhaoniuClient({ baseUrl: process.env.NEXT_PUBLIC_API_URL });

export function BetaCohortPanel({ elevated }: { elevated: boolean }) {
  const client = useQueryClient();
  const [selectedId, setSelectedId] = useState<string>();
  const [name, setName] = useState("");
  const [targetSize, setTargetSize] = useState(10);
  const [emails, setEmails] = useState("");
  const [error, setError] = useState<string>();
  const cohorts = useQuery({
    queryKey: ["beta-cohorts"],
    queryFn: api.getBetaCohorts,
  });
  const activeId = selectedId ?? cohorts.data?.items[0]?.id;
  const cohort = useQuery({
    queryKey: ["beta-cohort", activeId],
    queryFn: () => api.getBetaCohort(activeId!),
    enabled: Boolean(activeId),
  });
  const refresh = async (id?: string) => {
    await client.invalidateQueries({ queryKey: ["beta-cohorts"] });
    if (id) await client.invalidateQueries({ queryKey: ["beta-cohort", id] });
  };
  const mutate = useMutation({
    mutationFn: async (work: () => Promise<unknown>) => work(),
    onSuccess: () => {
      setError(undefined);
      void refresh(activeId);
    },
    onError: (caught) =>
      setError(
        caught instanceof ApiError ? caught.message : "操作失败，请稍后重试。",
      ),
  });

  function create(event: FormEvent) {
    event.preventDefault();
    mutate.mutate(async () => {
      const created = await api.createBetaCohort({
        name,
        target_size: targetSize,
        expires_in_days: 7,
      });
      setSelectedId(created.id);
      setName("");
      await refresh(created.id);
    });
  }

  function addRecipients() {
    if (!activeId) return;
    const values = emails
      .split(/[\s,;]+/)
      .map((value) => value.trim())
      .filter(Boolean);
    mutate.mutate(async () => {
      await api.addBetaRecipients(activeId, values);
      setEmails("");
    });
  }

  const detail = cohort.data;
  const gateReasons = detail?.gate_reasons ?? [];
  const funnel = detail?.funnel ?? {};
  const recipients = detail?.recipients ?? [];
  return (
    <div className="space-y-5">
      <div>
        <p className="text-blue text-xs font-medium">INVITE BETA</p>
        <h2 className="font-display mt-1 text-xl font-semibold">
          邀请批次与准入门禁
        </h2>
        <p className="text-slate mt-2 text-sm">
          创建和预检不会发信；只有所有门禁通过、批次批准后才能投递。
        </p>
      </div>
      <div className="grid gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
        <div className="space-y-4">
          <Card className="p-4">
            <form className="space-y-3" onSubmit={create}>
              <input
                className="border-ink/15 w-full rounded-xl border px-3 py-2.5 text-sm"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="批次名称"
                minLength={2}
                required
              />
              <input
                className="border-ink/15 w-full rounded-xl border px-3 py-2.5 text-sm"
                type="number"
                min={1}
                max={100}
                value={targetSize}
                onChange={(event) => setTargetSize(Number(event.target.value))}
              />
              <button
                className="bg-ink flex w-full items-center justify-center gap-2 rounded-xl px-3 py-2.5 text-sm text-white disabled:opacity-40"
                disabled={!elevated || mutate.isPending}
              >
                <Plus className="size-4" /> 创建草稿
              </button>
            </form>
          </Card>
          <div className="space-y-2">
            {cohorts.data?.items.map((item) => (
              <button
                type="button"
                key={item.id}
                onClick={() => setSelectedId(item.id)}
                className={`border-ink/10 w-full rounded-xl border p-3 text-left text-sm ${activeId === item.id ? "bg-blue/5 border-blue/25" : "bg-paper"}`}
              >
                <span className="font-medium">{item.name}</span>
                <span className="font-data text-slate ml-2 text-[10px]">
                  {item.status}
                </span>
              </button>
            ))}
          </div>
        </div>
        <Card className="min-w-0 p-5">
          {!detail ? (
            <p className="text-slate text-sm">选择或创建一个邀请批次。</p>
          ) : (
            <div className="space-y-5">
              <div className="flex flex-wrap items-center gap-3">
                <UsersRound className="text-blue size-5" />
                <h3 className="font-display text-lg font-semibold">
                  {detail.name}
                </h3>
                <span className="font-data bg-mist rounded-full px-2 py-1 text-[10px]">
                  {detail.status}
                </span>
              </div>
              {gateReasons.length > 0 && (
                <div className="border-risk/20 bg-risk/5 rounded-xl border p-4">
                  <p className="text-risk flex items-center gap-2 text-sm font-medium">
                    <ShieldAlert className="size-4" /> 当前禁止批准和发送
                  </p>
                  <ul className="text-slate mt-2 space-y-1 text-xs">
                    {gateReasons.map((reason) => (
                      <li key={reason}>
                        · {translateReasonCode(reason)} ({reason})
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {Object.entries(funnel).map(([key, value]) => (
                  <div className="bg-mist rounded-xl p-3" key={key}>
                    <p className="font-data text-xl font-semibold">{value}</p>
                    <p className="text-slate mt-1 text-[11px]">{key}</p>
                  </div>
                ))}
              </div>
              {detail.status === "draft" && (
                <div className="space-y-2">
                  <textarea
                    className="border-ink/15 min-h-24 w-full rounded-xl border p-3 text-sm"
                    value={emails}
                    onChange={(event) => setEmails(event.target.value)}
                    placeholder="每行一个受邀邮箱"
                  />
                  <button
                    type="button"
                    className="border-ink/15 rounded-xl border px-4 py-2 text-sm disabled:opacity-40"
                    disabled={!elevated || !emails.trim() || mutate.isPending}
                    onClick={addRecipients}
                  >
                    添加受邀人
                  </button>
                </div>
              )}
              <div className="hidden flex-wrap gap-2 md:flex">
                {detail.status === "draft" && (
                  <button
                    type="button"
                    className="bg-blue rounded-xl px-4 py-2 text-sm text-white disabled:opacity-40"
                    disabled={
                      !elevated || gateReasons.length > 0 || mutate.isPending
                    }
                    onClick={() =>
                      mutate.mutate(() =>
                        api.actOnBetaCohort(detail.id, "approve"),
                      )
                    }
                  >
                    批准批次
                  </button>
                )}
                {detail.status === "approved" && (
                  <button
                    type="button"
                    className="bg-ink flex items-center gap-2 rounded-xl px-4 py-2 text-sm text-white disabled:opacity-40"
                    disabled={
                      !elevated || gateReasons.length > 0 || mutate.isPending
                    }
                    onClick={() =>
                      mutate.mutate(() =>
                        api.actOnBetaCohort(detail.id, "dispatch"),
                      )
                    }
                  >
                    <Send className="size-4" />
                    发送邀请
                  </button>
                )}
                {!["closed", "cancelled"].includes(detail.status) && (
                  <button
                    type="button"
                    className="border-ink/15 rounded-xl border px-4 py-2 text-sm disabled:opacity-40"
                    disabled={!elevated || mutate.isPending}
                    onClick={() =>
                      mutate.mutate(() =>
                        api.actOnBetaCohort(detail.id, "close"),
                      )
                    }
                  >
                    关闭并撤销未使用邀请
                  </button>
                )}
              </div>
              {mutate.isPending && (
                <LoaderCircle className="text-blue size-5 animate-spin" />
              )}
              {error && <p className="text-risk text-sm">{error}</p>}
              <div className="overflow-x-auto">
                <table className="w-full min-w-[620px] text-left text-xs">
                  <thead className="text-slate">
                    <tr>
                      <th className="py-2">邮箱</th>
                      <th>邀请</th>
                      <th>投递</th>
                      <th>验证</th>
                      <th>自选</th>
                      <th>反馈</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recipients.map((recipient) => (
                      <tr className="border-ink/8 border-t" key={recipient.id}>
                        <td className="py-3">{recipient.email}</td>
                        <td>{recipient.status}</td>
                        <td>{recipient.delivery_status ?? "—"}</td>
                        <td>{recipient.email_verified ? "是" : "否"}</td>
                        <td>{recipient.first_watchlist_item ? "是" : "否"}</td>
                        <td>{recipient.feedback_submitted ? "是" : "否"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
