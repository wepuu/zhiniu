"use client";

import {
  createZhaoniuClient,
  type ProductionDeploymentEventCreate,
  type ProductionReleaseApprovalCreate,
} from "@zhaoniu/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, CircleX, Play, RotateCcw, Rocket } from "lucide-react";
import { useState } from "react";

import { Card } from "@/components/ui/card";

const api = createZhaoniuClient({ baseUrl: process.env.NEXT_PUBLIC_API_URL });

const statusLabel: Record<string, string> = {
  draft: "候选草稿",
  blocked: "门禁阻断",
  ready_closed: "可关闭部署",
  deployed_observing: "已部署观察",
  ready_invites: "可开放邀请",
  released: "已发布",
  rolled_back: "已回滚",
  rejected: "已拒绝",
  passed: "通过",
  failed: "失败",
};

function shortHash(value: string) {
  return `${value.slice(0, 12)}…${value.slice(-8)}`;
}

export function ProductionReleasePanel({
  role,
  capabilities,
  elevated,
}: {
  role: string;
  capabilities: string[];
  elevated: boolean;
}) {
  const client = useQueryClient();
  const candidates = useQuery({
    queryKey: ["production-releases"],
    queryFn: () => api.getProductionReleases(),
  });
  const [activeId, setActiveId] = useState<string>();
  const [deploymentRef, setDeploymentRef] = useState("");
  const [securityApproval, setSecurityApproval] = useState<
    "engineering" | "data_compliance"
  >("engineering");
  const selectedId = activeId ?? candidates.data?.items[0]?.id;
  const active = candidates.data?.items.find((item) => item.id === selectedId);
  const refresh = async () => {
    await client.invalidateQueries({ queryKey: ["production-releases"] });
  };
  const gate = useMutation({
    mutationFn: (gateType: "closed_deployment" | "invite_activation") =>
      api.evaluateProductionReleaseGate(selectedId!, gateType),
    onSuccess: refresh,
  });
  const approval = useMutation({
    mutationFn: (payload: ProductionReleaseApprovalCreate) =>
      api.approveProductionRelease(selectedId!, payload),
    onSuccess: refresh,
  });
  const deployment = useMutation({
    mutationFn: (payload: ProductionDeploymentEventCreate) =>
      api.recordProductionDeployment(selectedId!, payload),
    onSuccess: async () => {
      setDeploymentRef("");
      await refresh();
    },
  });
  const canManage = capabilities.includes("releases.manage") && elevated;
  const canApprove = capabilities.includes("releases.approve") && elevated;
  const canRecord = capabilities.includes("releases.record") && elevated;
  const approvalRole =
    role === "operations" ? "product_operations" : securityApproval;
  const existingApproval = (active?.approvals ?? []).some(
    (item) => item.approval_role === approvalRole,
  );
  const failedItems =
    active?.latest_gates?.flatMap((run) =>
      (run.items ?? []).filter(
        (item) => item.mandatory && item.status === "failed",
      ),
    ) ?? [];

  return (
    <section>
      <div className="mb-5 flex items-end justify-between gap-4">
        <div>
          <p className="text-blue text-xs font-semibold tracking-[0.18em]">
            PHASE 22
          </p>
          <h2 className="font-display mt-1 text-xl font-semibold">
            生产发布门禁
          </h2>
          <p className="text-slate mt-1 text-sm">
            固定构建、迁移、恢复与审批证据；实际部署仍由受控流水线执行。
          </p>
        </div>
        <span className="border-ink/10 bg-paper text-slate hidden rounded-full border px-3 py-1 text-xs md:block">
          fail closed · 双阶段
        </span>
      </div>

      <div className="grid gap-5 xl:grid-cols-[300px_minmax(0,1fr)]">
        <Card className="p-4">
          <p className="text-slate mb-3 text-xs">发布候选</p>
          {candidates.isLoading && (
            <p className="text-slate text-sm">正在读取…</p>
          )}
          {!candidates.isLoading && !candidates.data?.items.length && (
            <p className="text-slate text-sm">
              尚无候选。请由流水线或 CLI 写入已校验的证据清单。
            </p>
          )}
          <div className="space-y-2">
            {candidates.data?.items.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setActiveId(item.id)}
                className={`w-full rounded-xl border p-3 text-left ${
                  selectedId === item.id
                    ? "border-blue/35 bg-blue/5"
                    : "border-ink/8 hover:border-ink/20"
                }`}
              >
                <span className="font-data block text-xs">
                  {item.commit_sha.slice(0, 12)}
                </span>
                <span className="text-slate mt-1 block text-xs">
                  {statusLabel[item.status] ?? item.status}
                </span>
              </button>
            ))}
          </div>
        </Card>

        <Card className="p-5">
          {!active ? (
            <div className="text-slate flex min-h-40 items-center justify-center text-sm">
              选择一个发布候选查看门禁证据
            </div>
          ) : (
            <>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <Rocket className="text-blue size-5" />
                    <h3 className="font-display font-semibold">
                      {statusLabel[active.status] ?? active.status}
                    </h3>
                  </div>
                  <p className="font-data text-slate mt-2 text-xs">
                    commit {shortHash(active.commit_sha)} · migration{" "}
                    {active.migration_head}
                  </p>
                </div>
                <span
                  className={`rounded-full border px-3 py-1 text-xs ${
                    ["ready_closed", "ready_invites", "released"].includes(
                      active.status,
                    )
                      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                      : "border-amber-200 bg-amber-50 text-amber-700"
                  }`}
                >
                  {active.status}
                </span>
              </div>

              <div className="border-ink/8 mt-5 grid gap-3 border-y py-4 text-xs md:grid-cols-2">
                <Evidence
                  label="API 镜像"
                  value={shortHash(active.api_image_digest)}
                />
                <Evidence
                  label="Web 镜像"
                  value={shortHash(active.web_image_digest)}
                />
                <Evidence
                  label="SBOM SHA-256"
                  value={shortHash(active.sbom_sha256)}
                />
                <Evidence
                  label="备份 SHA-256"
                  value={shortHash(active.backup_sha256)}
                />
              </div>

              <div className="mt-5 grid gap-4 lg:grid-cols-2">
                {(active.latest_gates ?? []).map((run) => (
                  <div
                    key={run.id}
                    className="border-ink/8 rounded-xl border p-4"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-medium">
                        {run.gate_type === "closed_deployment"
                          ? "关闭注册部署门禁"
                          : "邀请激活门禁"}
                      </p>
                      <span className="text-xs">
                        {statusLabel[run.status] ?? run.status}
                      </span>
                    </div>
                    <p className="font-data text-slate mt-1 text-[10px]">
                      {shortHash(run.result_fingerprint)}
                    </p>
                    <ul className="mt-3 space-y-2">
                      {(run.items ?? []).map((item) => (
                        <li key={item.check_key} className="flex gap-2 text-xs">
                          {item.status === "passed" ? (
                            <CheckCircle2 className="size-4 shrink-0 text-emerald-600" />
                          ) : (
                            <CircleX className="text-risk size-4 shrink-0" />
                          )}
                          <span>
                            {item.check_key}
                            {item.reason_code && (
                              <span className="text-slate ml-1">
                                · {item.reason_code}
                              </span>
                            )}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>

              {!!failedItems.length && (
                <p className="bg-risk/5 text-risk mt-4 rounded-xl px-4 py-3 text-xs">
                  当前有 {failedItems.length}{" "}
                  个强制检查未通过，不能推进发布状态。
                </p>
              )}

              <div className="border-ink/8 mt-5 hidden flex-wrap items-end gap-3 border-t pt-5 md:flex">
                <ActionButton
                  disabled={!canManage || gate.isPending}
                  onClick={() => gate.mutate("closed_deployment")}
                  label="评估关闭部署"
                />
                <ActionButton
                  disabled={!canManage || gate.isPending}
                  onClick={() => gate.mutate("invite_activation")}
                  label="评估邀请激活"
                />
                {role === "security_admin" && (
                  <label className="text-slate text-xs">
                    审批职责
                    <select
                      value={securityApproval}
                      onChange={(event) =>
                        setSecurityApproval(
                          event.target.value as
                            | "engineering"
                            | "data_compliance",
                        )
                      }
                      className="border-ink/15 bg-paper mt-1 block rounded-lg border px-2 py-2"
                    >
                      <option value="engineering">工程</option>
                      <option value="data_compliance">数据合规</option>
                    </select>
                  </label>
                )}
                {(role === "security_admin" || role === "operations") && (
                  <ActionButton
                    disabled={
                      !canApprove || existingApproval || approval.isPending
                    }
                    onClick={() =>
                      approval.mutate({
                        approval_role: approvalRole,
                        decision: "approved",
                      })
                    }
                    label={existingApproval ? "该职责已签字" : "记录批准"}
                  />
                )}
                <label className="text-slate min-w-56 flex-1 text-xs">
                  流水线部署引用
                  <input
                    value={deploymentRef}
                    onChange={(event) => setDeploymentRef(event.target.value)}
                    placeholder="deployment/run/immutable-id"
                    className="border-ink/15 bg-paper mt-1 w-full rounded-lg border px-3 py-2"
                  />
                </label>
                {active.status === "ready_closed" && (
                  <ActionButton
                    disabled={
                      !canRecord || !deploymentRef || deployment.isPending
                    }
                    onClick={() =>
                      deployment.mutate({
                        event_type: "deployed",
                        deployment_ref: deploymentRef,
                      })
                    }
                    label="记录已部署"
                  />
                )}
                {active.status === "ready_invites" && (
                  <ActionButton
                    disabled={
                      !canRecord || !deploymentRef || deployment.isPending
                    }
                    onClick={() =>
                      deployment.mutate({
                        event_type: "released",
                        deployment_ref: deploymentRef,
                      })
                    }
                    label="记录已开放"
                  />
                )}
                {["deployed_observing", "ready_invites", "released"].includes(
                  active.status,
                ) && (
                  <button
                    type="button"
                    disabled={
                      !canRecord || !deploymentRef || deployment.isPending
                    }
                    onClick={() =>
                      deployment.mutate({
                        event_type: "rolled_back",
                        deployment_ref: deploymentRef,
                        reason_code: "operator_initiated_rollback",
                      })
                    }
                    className="border-risk/25 text-risk flex items-center gap-2 rounded-lg border px-3 py-2 text-xs disabled:opacity-40"
                  >
                    <RotateCcw className="size-3.5" />
                    记录回滚
                  </button>
                )}
              </div>
              {!elevated && (
                <p className="text-slate mt-3 hidden text-xs md:block">
                  敏感操作需要先完成管理员二次验证。
                </p>
              )}
            </>
          )}
        </Card>
      </div>
    </section>
  );
}

function Evidence({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-slate">{label}</p>
      <p className="font-data mt-1">{value}</p>
    </div>
  );
}

function ActionButton({
  label,
  disabled,
  onClick,
}: {
  label: string;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="bg-ink text-paper flex items-center gap-2 rounded-lg px-3 py-2 text-xs disabled:cursor-not-allowed disabled:opacity-40"
    >
      <Play className="size-3.5" />
      {label}
    </button>
  );
}
