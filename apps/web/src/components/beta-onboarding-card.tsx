"use client";

import { createZhaoniuClient } from "@zhaoniu/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Circle, FlaskConical, X } from "lucide-react";

import { Card } from "@/components/ui/card";

const api = createZhaoniuClient();

export function BetaOnboardingCard() {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["beta-onboarding"],
    queryFn: api.getBetaOnboarding,
    retry: false,
  });
  const mutation = useMutation({
    mutationFn: api.updateBetaOnboarding,
    onSuccess: (data) => client.setQueryData(["beta-onboarding"], data),
  });
  const data = query.data;
  if (!data?.enrolled || data.dismissed) return null;
  const steps = [
    ["验证邮箱", data.email_verified],
    ["添加第一只自选股", data.watchlist_started],
    ["提交一次体验反馈", data.feedback_submitted],
  ] as const;
  const complete = steps.every(([, done]) => done);

  return (
    <Card className="relative p-6">
      <button
        type="button"
        aria-label="关闭内测引导"
        className="text-slate absolute right-4 top-4 rounded-lg p-1 hover:bg-black/5"
        onClick={() => mutation.mutate("dismiss")}
      >
        <X className="size-4" />
      </button>
      <div className="flex items-center gap-2">
        <FlaskConical className="text-blue size-5" />
        <h2 className="font-display text-lg font-semibold">
          Invite Beta 上手清单
        </h2>
      </div>
      <p className="text-slate mt-2 pr-6 text-sm leading-6">
        用三个可核验步骤完成首次研究体验。知牛提供研究证据，不构成投资建议。
      </p>
      <div className="mt-5 space-y-3">
        {steps.map(([label, done]) => (
          <div key={label} className="flex items-center gap-3 text-sm">
            {done ? (
              <CheckCircle2 className="size-4 text-emerald-600" />
            ) : (
              <Circle className="text-slate/50 size-4" />
            )}
            <span className={done ? "text-slate line-through" : "text-ink"}>
              {label}
            </span>
          </div>
        ))}
      </div>
      <button
        type="button"
        className="bg-ink mt-5 rounded-xl px-4 py-2.5 text-sm text-white disabled:opacity-45"
        disabled={!complete || data.acknowledged || mutation.isPending}
        onClick={() => mutation.mutate("acknowledge")}
      >
        {data.acknowledged ? "已完成" : "确认完成"}
      </button>
    </Card>
  );
}
