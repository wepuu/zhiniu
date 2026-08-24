"use client";

import {
  createZhaoniuClient,
  type AlertSettingsUpdate,
} from "@zhaoniu/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BellRing, ShieldCheck } from "lucide-react";
import { Card } from "@/components/ui/card";

const api = createZhaoniuClient({ baseUrl: process.env.NEXT_PUBLIC_API_URL });

export function ResearchAlertSettings() {
  const client = useQueryClient();
  const settings = useQuery({
    queryKey: ["research-alert-settings"],
    queryFn: () => api.getResearchAlertSettings(),
    retry: false,
  });
  const save = useMutation({
    mutationFn: (payload: AlertSettingsUpdate) =>
      api.updateResearchAlertSettings(payload),
    onSuccess: () =>
      client.invalidateQueries({ queryKey: ["research-alert-settings"] }),
  });
  const update = (patch: Partial<AlertSettingsUpdate>) => {
    if (settings.data) save.mutate({ ...settings.data, ...patch });
  };
  return (
    <>
      <section className="border-ink/10 border-b pb-6">
        <p className="font-data text-blue text-[11px] uppercase tracking-[0.18em]">
          研究偏好设置
        </p>
        <h1 className="font-display mt-2 text-3xl font-semibold sm:text-4xl">
          研究偏好
        </h1>
        <p className="text-slate mt-2 max-w-2xl text-sm leading-6">
          设置站内提醒门槛和研究来源。修改只影响未来匹配，不会重放历史信号。
        </p>
      </section>
      <div className="mt-6 max-w-2xl space-y-4">
        <Card className="p-5">
          <div className="flex items-center gap-3">
            <span className="bg-blue/10 text-blue grid size-10 place-items-center rounded-xl">
              <BellRing className="size-5" />
            </span>
            <div>
              <h2 className="font-medium">站内研究提醒</h2>
              <p className="text-slate mt-1 text-sm">
                自选加入后出现的新信号才会进入提醒匹配。
              </p>
            </div>
            <button
              role="switch"
              aria-checked={settings.data?.enabled ?? false}
              onClick={() => update({ enabled: !settings.data?.enabled })}
              className={`ml-auto h-7 w-12 rounded-full p-1 transition ${settings.data?.enabled ? "bg-blue" : "bg-slate/30"}`}
            >
              <span
                className={`block size-5 rounded-full bg-white transition ${settings.data?.enabled ? "translate-x-5" : ""}`}
              />
            </button>
          </div>
        </Card>
        <Card className="p-5">
          <h2 className="font-medium">最低关注级别</h2>
          <div className="mt-4 grid grid-cols-3 gap-2">
            {(["info", "notice", "important"] as const).map((level) => (
              <button
                key={level}
                onClick={() => update({ minimum_attention: level })}
                className={`rounded-xl border px-3 py-2 text-sm ${settings.data?.minimum_attention === level ? "border-blue bg-blue/5 text-blue" : "border-ink/10 text-slate"}`}
              >
                {
                  { info: "全部记录", notice: "留意以上", important: "仅重点" }[
                    level
                  ]
                }
              </button>
            ))}
          </div>
        </Card>
        <Card className="p-5">
          <h2 className="font-medium">研究来源</h2>
          <div className="mt-4 space-y-3">
            {(
              [
                ["fundamental_enabled", "关键变化"],
                ["peer_enabled", "同行位置"],
                ["corporate_event_enabled", "公司事件"],
              ] as const
            ).map(([field, label]) => (
              <label
                key={field}
                className="border-ink/8 flex items-center rounded-xl border px-4 py-3 text-sm"
              >
                <input
                  type="checkbox"
                  checked={settings.data?.[field] ?? false}
                  onChange={(event) =>
                    update({ [field]: event.target.checked })
                  }
                  className="accent-blue mr-3 size-4"
                />
                {label}
              </label>
            ))}
          </div>
        </Card>
        <Card className="flex gap-3 p-5">
          <ShieldCheck className="text-blue mt-0.5 size-5 shrink-0" />
          <div>
            <h2 className="font-medium">研究边界</h2>
            <p className="text-slate mt-1 text-sm leading-6">
              提醒用于提示需要继续核对的事实变化，不提供买卖建议、目标价或收益概率。
            </p>
          </div>
        </Card>
      </div>
    </>
  );
}
