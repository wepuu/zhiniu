"use client";

import { ApiError, createZhaoniuClient } from "@zhaoniu/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ArrowLeft,
  CheckCircle2,
  ClipboardList,
  LayoutDashboard,
  LockKeyhole,
  Mail,
  MessageSquareText,
  RefreshCw,
  Search,
  ServerCog,
  ShieldCheck,
  Users,
} from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { Card } from "@/components/ui/card";

const api = createZhaoniuClient({ baseUrl: process.env.NEXT_PUBLIC_API_URL });
type View = "overview" | "users" | "feedback" | "providers" | "audit";

const views = [
  { id: "overview" as const, label: "运行总览", icon: LayoutDashboard },
  { id: "users" as const, label: "账户支持", icon: Users },
  { id: "feedback" as const, label: "反馈队列", icon: MessageSquareText },
  { id: "providers" as const, label: "服务商", icon: ServerCog },
  { id: "audit" as const, label: "审计记录", icon: ClipboardList },
];

function dateTime(value?: string | null) {
  return value
    ? new Intl.DateTimeFormat("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      }).format(new Date(value))
    : "—";
}

function StatusPill({ status }: { status: string }) {
  const tone =
    status === "healthy" || status === "active" || status === "delivered"
      ? "bg-emerald-50 text-emerald-700 border-emerald-200"
      : status === "disabled" || status === "unavailable" || status === "failed"
        ? "bg-red-50 text-red-700 border-red-200"
        : "bg-amber-50 text-amber-700 border-amber-200";
  return (
    <span
      className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-medium ${tone}`}
    >
      {status}
    </span>
  );
}

function PanelTitle({
  eyebrow,
  title,
  detail,
}: {
  eyebrow: string;
  title: string;
  detail?: string;
}) {
  return (
    <div className="mb-5 flex items-end justify-between gap-4">
      <div>
        <p className="font-data text-blue text-[10px] uppercase tracking-[0.18em]">
          {eyebrow}
        </p>
        <h2 className="font-display mt-1 text-xl font-semibold">{title}</h2>
      </div>
      {detail && <p className="text-slate hidden text-xs md:block">{detail}</p>}
    </div>
  );
}

export function AdminWorkspace() {
  const [view, setView] = useState<View>("overview");
  const context = useQuery({
    queryKey: ["operator-context"],
    queryFn: api.getOperatorContext,
    retry: false,
  });

  if (context.isLoading) {
    return (
      <div className="bg-mist text-slate grid min-h-screen place-items-center text-sm">
        正在验证运营权限…
      </div>
    );
  }
  if (context.error) {
    const denied =
      context.error instanceof ApiError && context.error.status === 403;
    return (
      <div className="bg-mist grid min-h-screen place-items-center px-5">
        <Card className="max-w-md p-8 text-center">
          <ShieldCheck className="text-blue mx-auto size-8" />
          <h1 className="font-display mt-4 text-2xl font-semibold">
            {denied ? "无运营权限" : "请先登录"}
          </h1>
          <p className="text-slate mt-3 text-sm leading-6">
            {denied
              ? "当前账户没有运营控制台成员身份。"
              : "运营控制台仅对已认证的内部账户开放。"}
          </p>
          <Link
            href={denied ? "/" : "/login"}
            className="bg-ink mt-6 inline-flex rounded-xl px-4 py-2.5 text-sm text-white"
          >
            <ArrowLeft className="mr-2 size-4" />
            返回知牛
          </Link>
        </Card>
      </div>
    );
  }

  const operator = context.data!;
  return (
    <div className="bg-mist text-ink min-h-screen md:grid md:grid-cols-[224px_minmax(0,1fr)]">
      <aside className="bg-ink text-paper hidden min-h-screen flex-col p-5 md:flex">
        <Link
          href="/"
          className="flex items-center gap-3 border-b border-white/10 pb-5"
        >
          <span className="grid size-9 place-items-center rounded-xl bg-white/10">
            <Activity className="size-4" />
          </span>
          <span>
            <b className="font-display block">知牛运营台</b>
            <small className="font-data text-[9px] tracking-[0.18em] text-white/45">
              OPERATIONS
            </small>
          </span>
        </Link>
        <nav className="mt-7 space-y-1" aria-label="运营控制台导航">
          {views.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setView(id)}
              className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm ${view === id ? "bg-white/12 text-white" : "hover:bg-white/6 text-white/55 hover:text-white"}`}
            >
              <Icon className="size-4" />
              {label}
            </button>
          ))}
        </nav>
        <div className="mt-auto border-t border-white/10 pt-5">
          <p className="text-xs text-white/50">当前角色</p>
          <p className="mt-1 flex items-center gap-2 text-sm">
            <ShieldCheck className="size-4" />
            {operator.role}
          </p>
        </div>
      </aside>

      <main className="min-w-0">
        <header className="border-ink/8 bg-paper/90 sticky top-0 z-20 flex min-h-16 items-center gap-3 border-b px-4 backdrop-blur md:px-8">
          <div className="md:hidden">
            <p className="font-display font-semibold">知牛运营台</p>
            <select
              value={view}
              onChange={(event) => setView(event.target.value as View)}
              className="text-slate bg-transparent text-xs"
            >
              {views.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>
          <p className="text-slate ml-auto text-xs">
            {operator.elevated ? "已完成敏感操作验证" : "只读会话"}
          </p>
          <ElevationButton elevated={operator.elevated} />
        </header>
        <div className="mx-auto max-w-[1320px] p-4 pb-20 md:p-8">
          <div className="border-blue/15 bg-blue/5 text-slate mb-5 rounded-xl border px-4 py-3 text-xs md:hidden">
            移动端用于安全查看；高风险运营动作请在桌面端完成。
          </div>
          {view === "overview" && <Overview />}
          {view === "users" && (
            <UsersPanel capabilities={operator.capabilities} />
          )}
          {view === "feedback" && (
            <FeedbackPanel capabilities={operator.capabilities} />
          )}
          {view === "providers" && (
            <ProvidersPanel capabilities={operator.capabilities} />
          )}
          {view === "audit" && <AuditPanel />}
        </div>
      </main>
    </div>
  );
}

function ElevationButton({ elevated }: { elevated: boolean }) {
  const client = useQueryClient();
  const [password, setPassword] = useState("");
  const [open, setOpen] = useState(false);
  const mutation = useMutation({
    mutationFn: () => api.elevateOperator(password),
    onSuccess: (data) => {
      client.setQueryData(["operator-context"], data);
      setOpen(false);
      setPassword("");
    },
  });
  if (elevated)
    return (
      <span className="hidden items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1.5 text-xs text-emerald-700 md:flex">
        <CheckCircle2 className="size-3.5" />
        已验证
      </span>
    );
  return (
    <div className="relative hidden md:block">
      <button
        onClick={() => setOpen(!open)}
        className="border-ink/10 bg-paper flex items-center gap-2 rounded-xl border px-3 py-2 text-xs"
      >
        <LockKeyhole className="size-3.5" />
        验证敏感操作
      </button>
      {open && (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            mutation.mutate();
          }}
          className="border-ink/10 bg-paper shadow-card absolute right-0 top-12 w-72 rounded-2xl border p-4"
        >
          <label className="text-xs font-medium">重新输入当前密码</label>
          <input
            autoFocus
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="border-ink/10 mt-2 w-full rounded-xl border px-3 py-2 text-sm"
          />
          {mutation.isError && (
            <p className="text-risk mt-2 text-xs">密码验证失败</p>
          )}
          <button
            disabled={!password || mutation.isPending}
            className="bg-blue mt-3 w-full rounded-xl px-3 py-2 text-sm text-white disabled:opacity-50"
          >
            确认验证
          </button>
        </form>
      )}
    </div>
  );
}

function Overview() {
  const query = useQuery({
    queryKey: ["operator-dashboard"],
    queryFn: api.getOperatorDashboard,
  });
  const groups = useMemo(
    () =>
      query.data
        ? ([
            ["账户", query.data.users],
            ["访问权益", query.data.access],
            ["AI 调用", query.data.ai],
            ["邮件", query.data.email],
          ] as const)
        : [],
    [query.data],
  );
  return (
    <>
      <PanelTitle
        eyebrow="Service pulse"
        title="运行总览"
        detail={
          query.data ? `更新于 ${dateTime(query.data.generated_at)}` : "加载中"
        }
      />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {groups.map(([label, values]) => (
          <Card key={label} className="p-5">
            <p className="text-slate text-xs">{label}</p>
            <p className="font-data mt-2 text-3xl font-semibold">
              {Object.values(values)[0] ?? 0}
            </p>
            <div className="border-ink/8 mt-4 space-y-2 border-t pt-3">
              {Object.entries(values)
                .slice(0, 4)
                .map(([key, value]) => (
                  <div
                    key={key}
                    className="flex justify-between gap-3 text-[11px]"
                  >
                    <span className="text-slate truncate">{key}</span>
                    <span className="font-data">{String(value ?? "—")}</span>
                  </div>
                ))}
            </div>
          </Card>
        ))}
      </div>
      {query.data && (
        <Card className="mt-5 p-5">
          <PanelTitle eyebrow="Launch gates" title="上线门禁" />
          <div className="grid gap-3 md:grid-cols-3">
            {Object.entries(query.data.system).map(([key, value]) => (
              <div key={key} className="border-ink/8 rounded-xl border p-3">
                <p className="text-slate text-[11px]">{key}</p>
                <p className="mt-1 text-sm font-medium">
                  {Array.isArray(value)
                    ? value.join("、") || "无阻塞项"
                    : String(value ?? "—")}
                </p>
              </div>
            ))}
          </div>
        </Card>
      )}
    </>
  );
}

function UsersPanel({ capabilities }: { capabilities: string[] }) {
  const client = useQueryClient();
  const [input, setInput] = useState("");
  const [queryText, setQueryText] = useState("");
  const [secret, setSecret] = useState<string | null>(null);
  const users = useQuery({
    queryKey: ["operator-users", queryText],
    queryFn: () => api.getOperatorUsers(queryText),
  });
  const action = useMutation({
    mutationFn: async ({ kind, id }: { kind: string; id: string }) =>
      kind === "sessions"
        ? api.revokeOperatorUserSessions(id)
        : kind === "verify"
          ? api.resendOperatorVerification(id)
          : kind === "access"
            ? api.issueOperatorAccessCode(id, "month")
            : api.setOperatorUserStatus(id, "disabled"),
    onSuccess: (result) => {
      if ("code" in result) setSecret(result.code);
      client.invalidateQueries({ queryKey: ["operator-users"] });
    },
  });
  const invite = useMutation({
    mutationFn: () => api.createOperatorInviteBatch(5),
    onSuccess: (result) => setSecret(result.codes.join("  ")),
  });
  return (
    <>
      <PanelTitle
        eyebrow="Account support"
        title="账户支持"
        detail="按完整邮箱或用户 ID 精确查找"
      />
      <Card className="p-4">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            setQueryText(input.trim());
          }}
          className="flex gap-2"
        >
          <div className="border-ink/10 flex flex-1 items-center gap-2 rounded-xl border bg-white px-3">
            <Search className="text-slate size-4" />
            <input
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="邮箱或用户 UUID"
              className="min-w-0 flex-1 bg-transparent py-2.5 text-sm outline-none"
            />
          </div>
          <button className="bg-ink rounded-xl px-4 text-sm text-white">
            查找
          </button>
          {capabilities.includes("invites.manage") && (
            <button
              type="button"
              onClick={() => invite.mutate()}
              className="border-blue/20 text-blue hidden rounded-xl border px-4 text-sm md:block"
            >
              生成 5 个邀请码
            </button>
          )}
        </form>
        {secret && (
          <div className="border-amber/25 bg-amber/8 mt-4 rounded-xl border p-3">
            <p className="text-xs font-medium">仅本次显示，请立即安全交付</p>
            <p className="font-data mt-2 break-all text-xs">{secret}</p>
          </div>
        )}
      </Card>
      <Card className="mt-4 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[780px] text-left text-xs">
            <thead className="bg-ink/[0.025] text-slate">
              <tr>
                {["账户", "状态", "邮箱", "访问", "最近登录", "操作"].map(
                  (item) => (
                    <th key={item} className="px-4 py-3 font-medium">
                      {item}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {users.data?.items.map((item) => (
                <tr key={item.id} className="border-ink/8 border-t">
                  <td className="px-4 py-3">
                    <b className="block">{item.email}</b>
                    <span className="font-data text-slate text-[10px]">
                      {item.id}
                    </span>
                  </td>
                  <td className="px-4">
                    <StatusPill status={item.status} />
                  </td>
                  <td className="px-4">
                    {item.email_verified ? "已验证" : "待验证"}
                  </td>
                  <td className="px-4">{item.access_status}</td>
                  <td className="px-4">{dateTime(item.last_login_at)}</td>
                  <td className="px-4">
                    <div className="hidden gap-2 md:flex">
                      {capabilities.includes("users.sessions.revoke") && (
                        <button
                          onClick={() =>
                            action.mutate({ kind: "sessions", id: item.id })
                          }
                          className="text-blue"
                        >
                          撤销会话
                        </button>
                      )}
                      {!item.email_verified && (
                        <button
                          onClick={() =>
                            action.mutate({ kind: "verify", id: item.id })
                          }
                          className="text-blue"
                        >
                          重发验证
                        </button>
                      )}
                      {capabilities.includes("access_codes.manage") && (
                        <button
                          onClick={() =>
                            action.mutate({ kind: "access", id: item.id })
                          }
                          className="text-blue"
                        >
                          月卡码
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!users.data?.items.length && (
          <p className="text-slate p-8 text-center text-sm">
            输入完整邮箱或用户 ID 开始查找
          </p>
        )}
      </Card>
    </>
  );
}

function FeedbackPanel({ capabilities }: { capabilities: string[] }) {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["operator-feedback"],
    queryFn: () => api.getOperatorFeedback(),
  });
  const update = useMutation({
    mutationFn: ({
      id,
      status,
    }: {
      id: string;
      status: "triaged" | "resolved";
    }) => api.updateOperatorFeedback(id, status),
    onSuccess: () =>
      client.invalidateQueries({ queryKey: ["operator-feedback"] }),
  });
  return (
    <>
      <PanelTitle
        eyebrow="Beta learning"
        title="反馈队列"
        detail="保留用户原始表述和处理轨迹"
      />
      <div className="space-y-3">
        {query.data?.items.map((item) => (
          <Card key={item.id} className="p-5">
            <div className="flex items-start gap-4">
              <MessageSquareText className="text-blue mt-0.5 size-4 shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <b className="text-sm">{item.feature_key}</b>
                  <StatusPill status={item.status} />
                  <span className="text-slate text-xs">
                    {item.category} · {dateTime(item.created_at)}
                  </span>
                </div>
                <p className="mt-3 text-sm leading-6">{item.message}</p>
              </div>
              {capabilities.includes("feedback.manage") && (
                <div className="hidden gap-2 md:flex">
                  <button
                    onClick={() =>
                      update.mutate({ id: item.id, status: "triaged" })
                    }
                    className="border-ink/10 rounded-lg border px-2.5 py-1.5 text-xs"
                  >
                    标记分流
                  </button>
                  <button
                    onClick={() =>
                      update.mutate({ id: item.id, status: "resolved" })
                    }
                    className="bg-ink rounded-lg px-2.5 py-1.5 text-xs text-white"
                  >
                    已解决
                  </button>
                </div>
              )}
            </div>
          </Card>
        ))}
      </div>
    </>
  );
}

function ProvidersPanel({ capabilities }: { capabilities: string[] }) {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["operator-providers"],
    queryFn: api.getProviderStatuses,
  });
  const diagnose = useMutation({
    mutationFn: (provider: "deepseek" | "resend") =>
      api.diagnoseProvider(provider),
    onSuccess: () =>
      client.invalidateQueries({ queryKey: ["operator-providers"] }),
  });
  return (
    <>
      <PanelTitle
        eyebrow="External dependencies"
        title="服务商状态"
        detail="诊断只验证契约，不发送测试邮件"
      />
      <div className="grid gap-4 lg:grid-cols-2">
        {query.data?.items.map((item) => (
          <Card key={item.provider} className="p-5">
            <div className="flex items-start justify-between">
              <div className="flex gap-3">
                <span className="bg-blue/8 text-blue grid size-10 place-items-center rounded-xl">
                  {item.provider === "resend" ? (
                    <Mail className="size-4" />
                  ) : (
                    <ServerCog className="size-4" />
                  )}
                </span>
                <div>
                  <h3 className="font-medium capitalize">{item.provider}</h3>
                  <p className="text-slate mt-1 text-xs">{item.capability}</p>
                </div>
              </div>
              <StatusPill status={item.status} />
            </div>
            <dl className="border-ink/8 mt-5 grid grid-cols-2 gap-3 border-t pt-4 text-xs">
              <div>
                <dt className="text-slate">最近检查</dt>
                <dd className="mt-1">{dateTime(item.checked_at)}</dd>
              </div>
              <div>
                <dt className="text-slate">延迟</dt>
                <dd className="font-data mt-1">
                  {item.latency_ms ? `${item.latency_ms} ms` : "—"}
                </dd>
              </div>
            </dl>
            {item.reason_code && (
              <p className="text-risk mt-3 text-xs">{item.reason_code}</p>
            )}
            {capabilities.includes("providers.diagnose") &&
              (item.provider === "deepseek" || item.provider === "resend") && (
                <button
                  onClick={() =>
                    diagnose.mutate(item.provider as "deepseek" | "resend")
                  }
                  className="border-blue/20 text-blue mt-4 hidden items-center gap-2 rounded-xl border px-3 py-2 text-xs md:flex"
                >
                  <RefreshCw
                    className={`size-3.5 ${diagnose.isPending ? "animate-spin" : ""}`}
                  />
                  运行诊断
                </button>
              )}
          </Card>
        ))}
      </div>
    </>
  );
}

function AuditPanel() {
  const query = useQuery({
    queryKey: ["operator-audit"],
    queryFn: api.getOperatorAudit,
  });
  return (
    <>
      <PanelTitle
        eyebrow="Immutable trail"
        title="运营审计"
        detail="高风险动作不记录密码、令牌或完整邮件内容"
      />
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[820px] text-left text-xs">
            <thead className="bg-ink/[0.025] text-slate">
              <tr>
                {["时间", "动作", "角色", "目标", "结果"].map((item) => (
                  <th key={item} className="px-4 py-3 font-medium">
                    {item}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {query.data?.items.map((item) => (
                <tr key={item.id} className="border-ink/8 border-t">
                  <td className="font-data px-4 py-3">
                    {dateTime(item.created_at)}
                  </td>
                  <td className="px-4 font-medium">{item.action_key}</td>
                  <td className="px-4">{item.actor_role}</td>
                  <td className="font-data px-4">
                    {item.target_type} / {item.target_id ?? "—"}
                  </td>
                  <td className="px-4">
                    <StatusPill status={item.result} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}
