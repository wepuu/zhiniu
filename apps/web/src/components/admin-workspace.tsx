"use client";

import { ApiError, createZhaoniuClient } from "@zhaoniu/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ArrowLeft,
  Bot,
  CalendarClock,
  CheckCircle2,
  ClipboardList,
  DatabaseZap,
  LayoutDashboard,
  LockKeyhole,
  Mail,
  MessageSquareText,
  Play,
  RefreshCw,
  RotateCcw,
  Search,
  ServerCog,
  ShieldCheck,
  Users,
  UserRoundPlus,
  Workflow,
  Rocket,
} from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { Card } from "@/components/ui/card";
import { ProviderConfigurationPanel } from "@/components/provider-configuration-panel";
import { ProviderAcceptancePanel } from "@/components/provider-acceptance-panel";
import { BetaCohortPanel } from "@/components/beta-cohort-panel";
import { ProductionReleasePanel } from "@/components/production-release-panel";
import {
  providerDisplayName,
  translateEnum,
  translateReasonCode,
} from "@/lib/presentation";

const api = createZhaoniuClient({ baseUrl: process.env.NEXT_PUBLIC_API_URL });
type View =
  | "overview"
  | "automation"
  | "users"
  | "feedback"
  | "beta"
  | "providers"
  | "releases"
  | "audit";

const views = [
  { id: "overview" as const, label: "运行总览", icon: LayoutDashboard },
  { id: "automation" as const, label: "自动任务", icon: Workflow },
  { id: "users" as const, label: "账户支持", icon: Users },
  { id: "feedback" as const, label: "反馈队列", icon: MessageSquareText },
  { id: "beta" as const, label: "邀请内测", icon: UserRoundPlus },
  { id: "providers" as const, label: "服务商", icon: ServerCog },
  { id: "releases" as const, label: "生产发布", icon: Rocket },
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
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium ${tone}`}
    >
      {translateEnum("status", status)}
      <span className="font-data opacity-65">{status}</span>
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
        <p className="text-blue text-xs font-medium">{eyebrow}</p>
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
              运营控制台
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
            <span>{translateEnum("operator_role", operator.role)}</span>
            <span className="font-data text-[10px] text-white/45">
              {operator.role}
            </span>
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
          {view === "automation" && (
            <AutomationPanel capabilities={operator.capabilities} />
          )}
          {view === "users" && (
            <UsersPanel capabilities={operator.capabilities} />
          )}
          {view === "feedback" && (
            <FeedbackPanel capabilities={operator.capabilities} />
          )}
          {view === "beta" && <BetaCohortPanel elevated={operator.elevated} />}
          {view === "providers" && (
            <ProvidersPanel
              capabilities={operator.capabilities}
              elevated={operator.elevated}
            />
          )}
          {view === "releases" && (
            <ProductionReleasePanel
              role={operator.role}
              capabilities={operator.capabilities}
              elevated={operator.elevated}
            />
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
        eyebrow="服务运行脉搏"
        title="运行总览"
        detail={
          query.data ? `更新于 ${dateTime(query.data.generated_at)}` : "加载中"
        }
      />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {groups.map(([label, values]) => (
          <Card key={label} className="p-5">
            <p className="text-slate text-xs">{label}</p>
            <div className="mt-2 text-3xl font-semibold">
              <AdminDashboardValue value={Object.values(values)[0] ?? 0} />
            </div>
            <div className="border-ink/8 mt-4 space-y-2 border-t pt-3">
              {Object.entries(values)
                .slice(0, 4)
                .map(([key, value]) => (
                  <div
                    key={key}
                    className="flex justify-between gap-3 text-[11px]"
                  >
                    <span className="text-slate min-w-0">
                      <span className="block truncate">
                        {dashboardFieldLabel(key)}
                      </span>
                      <span className="font-data block truncate text-[9px] opacity-60">
                        {key}
                      </span>
                    </span>
                    <AdminDashboardValue value={value} />
                  </div>
                ))}
            </div>
          </Card>
        ))}
      </div>
      {query.data && (
        <Card className="mt-5 p-5">
          <PanelTitle eyebrow="上线准备检查" title="上线门禁" />
          <div className="grid gap-3 md:grid-cols-3">
            {Object.entries(query.data.system).map(([key, value]) => (
              <div key={key} className="border-ink/8 rounded-xl border p-3">
                <p className="text-slate text-xs">{dashboardFieldLabel(key)}</p>
                <p className="font-data text-slate mt-0.5 text-[9px]">{key}</p>
                <div className="mt-2 text-sm font-medium">
                  <AdminDashboardValue
                    value={value}
                    reasonList={key === "blocking_reasons"}
                  />
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </>
  );
}

const dashboardFieldLabels: Record<string, string> = {
  total: "账户总数",
  active: "正常账户",
  verified: "已验证邮箱",
  advanced_active: "高级权益有效",
  invites_available: "可用邀请码",
  activation_codes_available: "可用激活码",
  enabled: "启用状态",
  calls_24h: "近 24 小时调用",
  failures_24h: "近 24 小时失败",
  explanation_enabled: "研究助手状态",
  provider: "邮件服务状态",
  configured: "配置完成",
  submitted_24h: "近 24 小时提交",
  migration_head: "数据库迁移版本",
  beta_readiness: "内测准备状态",
  active_users: "活跃用户数",
  blocking_reasons: "当前阻塞项",
  data_use_status: "数据使用审核",
  legal_review_status: "法律审核",
};

function dashboardFieldLabel(key: string) {
  return dashboardFieldLabels[key] ?? "其他运行指标";
}

function AdminDashboardValue({
  value,
  reasonList = false,
}: {
  value: unknown;
  reasonList?: boolean;
}) {
  if (Array.isArray(value)) {
    if (!value.length) return <span>无阻塞项</span>;
    return (
      <span className="space-y-1.5">
        {value.map((item) => (
          <span key={String(item)} className="block">
            <span>
              {reasonList
                ? translateReasonCode(String(item), "admin").replace(
                    `（${String(item)}）`,
                    "",
                  )
                : translateEnum("status", String(item), "admin")}
            </span>
            <span className="font-data text-slate block text-[9px]">
              {String(item)}
            </span>
          </span>
        ))}
      </span>
    );
  }
  if (typeof value === "boolean") {
    return (
      <span className="text-right">
        <span className="block">{value ? "已启用" : "未启用"}</span>
        <span className="font-data text-slate block text-[9px]">
          {String(value)}
        </span>
      </span>
    );
  }
  if (typeof value === "string") {
    if (value === "true" || value === "false") {
      return (
        <span className="text-right">
          <span className="block">
            {value === "true" ? "已启用" : "未启用"}
          </span>
          <span className="font-data text-slate block text-[9px]">{value}</span>
        </span>
      );
    }
    const translated = translateEnum("status", value, "admin");
    const known = !translated.startsWith("状态未知");
    return (
      <span className="text-right">
        <span className="block">{known ? translated : value}</span>
        {known && (
          <span className="font-data text-slate block text-[9px]">{value}</span>
        )}
      </span>
    );
  }
  return <span className="font-data">{String(value ?? "—")}</span>;
}

function AutomationPanel({ capabilities }: { capabilities: string[] }) {
  const client = useQueryClient();
  const [selectedRun, setSelectedRun] = useState<string | null>(null);
  const [acceptanceSymbol, setAcceptanceSymbol] = useState("");
  const policies = useQuery({
    queryKey: ["automation-policies"],
    queryFn: api.getAutomationPolicies,
  });
  const runs = useQuery({
    queryKey: ["automation-runs"],
    queryFn: api.getAutomationRuns,
    refetchInterval: 15_000,
  });
  const detail = useQuery({
    queryKey: ["automation-run", selectedRun],
    queryFn: () => api.getAutomationRun(selectedRun!),
    enabled: Boolean(selectedRun),
    refetchInterval: selectedRun ? 10_000 : false,
  });
  const runNow = useMutation({
    mutationFn: (policyKey: string) => api.runAutomationPolicy(policyKey),
    onSuccess: (result) => {
      setSelectedRun(result.run_id);
      client.invalidateQueries({ queryKey: ["automation-runs"] });
    },
  });
  const resume = useMutation({
    mutationFn: (runId: string) => api.resumeAutomationRun(runId),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["automation-runs"] });
      client.invalidateQueries({ queryKey: ["automation-run"] });
    },
  });
  const refreshStock = useMutation({
    mutationFn: (symbol: string) => api.refreshAutomationStock(symbol),
    onSuccess: (result) => {
      setSelectedRun(result.run_id);
      client.invalidateQueries({ queryKey: ["automation-runs"] });
    },
  });
  const canRun = capabilities.includes("automation.run");
  const canResume = capabilities.includes("automation.resume");
  const firstPolicy = policies.data?.items[0];
  const latestRun = runs.data?.items[0];

  return (
    <>
      <PanelTitle
        eyebrow="研究生产运行"
        title="自动研究任务"
        detail="数据库记录运行事实；调度器只负责唤醒到期策略"
      />
      {firstPolicy?.hard_disabled && (
        <div className="border-amber/25 bg-amber/8 mb-4 flex items-start gap-3 rounded-2xl border p-4">
          <LockKeyhole className="text-amber mt-0.5 size-4 shrink-0" />
          <div>
            <p className="text-sm font-medium">环境级自动化开关已关闭</p>
            <p className="text-slate mt-1 text-xs leading-5">
              策略配置和手动检查仍可查看；定时任务不会自动启动。
            </p>
          </div>
        </div>
      )}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
        {firstPolicy ? (
          <AutomationPolicyCard
            key={`${firstPolicy.configuration_hash}:${firstPolicy.enabled}`}
            policy={firstPolicy}
            canManage={capabilities.includes("automation.manage")}
            canRun={canRun}
            running={runNow.isPending}
            onRun={() => runNow.mutate(firstPolicy.policy_key)}
          />
        ) : (
          <Card className="text-slate p-6 text-sm">正在读取自动化策略…</Card>
        )}
        <Card className="p-5">
          <div className="flex items-center gap-3">
            <span className="bg-blue/8 text-blue grid size-10 place-items-center rounded-xl">
              <CalendarClock className="size-4" />
            </span>
            <div>
              <p className="text-slate text-xs">最近一次运行</p>
              <p className="mt-0.5 text-sm font-medium">
                {latestRun ? dateTime(latestRun.created_at) : "尚未运行"}
              </p>
            </div>
            {latestRun && (
              <span className="ml-auto">
                <StatusPill status={latestRun.status} />
              </span>
            )}
          </div>
          {latestRun && (
            <div className="border-ink/8 mt-5 grid grid-cols-3 gap-3 border-t pt-4 text-center">
              <Metric label="股票" value={latestRun.universe_size} />
              <Metric label="成功步骤" value={latestRun.succeeded_steps} />
              <Metric label="失败步骤" value={latestRun.failed_steps} />
            </div>
          )}
        </Card>
      </div>

      <Card className="mt-4 hidden p-5 md:block">
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-slate min-w-[240px] flex-1 text-xs">
            单股验收
            <input
              value={acceptanceSymbol}
              onChange={(event) =>
                setAcceptanceSymbol(event.target.value.toUpperCase())
              }
              placeholder="输入股票代码，例如 600519"
              className="border-ink/10 text-ink mt-2 w-full rounded-xl border bg-white px-3 py-2.5"
            />
          </label>
          <button
            type="button"
            onClick={() => refreshStock.mutate(acceptanceSymbol.trim())}
            disabled={
              !canRun ||
              refreshStock.isPending ||
              !/^\d{6}(\.(SH|SZ))?$/.test(acceptanceSymbol.trim())
            }
            className="bg-ink flex items-center gap-2 rounded-xl px-4 py-2.5 text-xs text-white disabled:opacity-40"
          >
            <Play className="size-3.5" />
            运行单股链路
          </button>
        </div>
        <p className="text-slate mt-2 text-xs">
          使用当前已发布策略版本执行单股数据、研究、AI
          与覆盖链路；不会自动启用每日策略。
        </p>
        {refreshStock.isError && (
          <p className="text-risk mt-2 text-xs" role="alert">
            单股任务启动失败，请确认代码、管理员权限和服务状态后重试。
          </p>
        )}
      </Card>

      <div className="mt-6 grid gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <Card className="overflow-hidden">
          <div className="border-ink/8 flex items-center justify-between border-b px-5 py-4">
            <div>
              <h3 className="text-sm font-medium">运行记录</h3>
              <p className="text-slate mt-1 text-xs">默认显示最近 50 次</p>
            </div>
            <RefreshCw
              className={`text-slate size-4 ${runs.isFetching ? "animate-spin" : ""}`}
            />
          </div>
          <div className="divide-ink/8 divide-y">
            {runs.data?.items.map((run) => (
              <button
                key={run.id}
                onClick={() => setSelectedRun(run.id)}
                className={`hover:bg-blue/[0.025] w-full px-5 py-4 text-left ${selectedRun === run.id ? "bg-blue/[0.04]" : ""}`}
              >
                <div className="flex items-center gap-2">
                  <StatusPill status={run.status} />
                  <span className="text-slate ml-auto text-[11px]">
                    {dateTime(run.created_at)}
                  </span>
                </div>
                <p className="mt-2 text-sm font-medium">
                  {run.trigger_kind === "scheduled" ? "定时刷新" : "人工刷新"}
                  <span className="text-slate ml-2 font-normal">
                    {run.universe_size} 只股票
                  </span>
                </p>
                <p className="font-data text-slate mt-1 truncate text-[10px]">
                  {run.id}
                </p>
              </button>
            ))}
            {!runs.data?.items.length && (
              <p className="text-slate p-8 text-center text-sm">
                尚无自动化运行记录
              </p>
            )}
          </div>
        </Card>

        <AutomationRunDetailPanel
          run={detail.data}
          loading={detail.isFetching}
          canResume={canResume}
          resuming={resume.isPending}
          onResume={(runId) => resume.mutate(runId)}
        />
      </div>
    </>
  );
}

function AutomationPolicyCard({
  policy,
  canManage,
  canRun,
  running,
  onRun,
}: {
  policy: Awaited<
    ReturnType<typeof api.getAutomationPolicies>
  >["items"][number];
  canManage: boolean;
  canRun: boolean;
  running: boolean;
  onRun: () => void;
}) {
  const client = useQueryClient();
  const [enabled, setEnabled] = useState(policy.enabled);
  const [dailyTime, setDailyTime] = useState(policy.configuration.daily_time);
  const [events, setEvents] = useState(
    policy.configuration.event_pipeline_enabled,
  );
  const [peers, setPeers] = useState(
    policy.configuration.peer_research_enabled,
  );
  const [ai, setAI] = useState(policy.configuration.ai_research_enabled);
  const update = useMutation({
    mutationFn: () =>
      api.updateAutomationPolicy(policy.policy_key, enabled, {
        ...policy.configuration,
        daily_time: dailyTime,
        event_pipeline_enabled: events,
        peer_research_enabled: peers,
        ai_research_enabled: ai,
      }),
    onSuccess: () =>
      client.invalidateQueries({ queryKey: ["automation-policies"] }),
  });
  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-start gap-3">
        <span className="bg-blue/8 text-blue grid size-10 place-items-center rounded-xl">
          <Workflow className="size-4" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-medium">{policy.display_name}</h3>
            <StatusPill status={policy.enabled ? "enabled" : "disabled"} />
          </div>
          <p className="font-data text-slate mt-1 text-[10px]">
            REV {policy.revision} · {policy.configuration_hash.slice(0, 12)}
          </p>
          {!policy.enabled && (
            <p className="text-amber mt-1 text-xs">
              {policy.hard_disabled
                ? "环境紧急开关已关闭，定时策略不会运行"
                : "数据库策略总开关已关闭，手动验收仍可运行"}
            </p>
          )}
        </div>
        <button
          onClick={onRun}
          disabled={!canRun || running}
          className="bg-ink hidden items-center gap-2 rounded-xl px-3 py-2 text-xs text-white disabled:opacity-40 md:flex"
        >
          <Play className="size-3.5" />
          立即运行
        </button>
      </div>
      <div className="border-ink/8 mt-5 grid gap-4 border-t pt-5 sm:grid-cols-2">
        <label className="text-slate text-xs">
          每日检查时间（上海）
          <input
            type="time"
            value={dailyTime}
            disabled={!canManage}
            onChange={(event) => setDailyTime(event.target.value)}
            className="border-ink/10 text-ink mt-2 hidden w-full rounded-xl border bg-white px-3 py-2.5 md:block"
          />
          <span className="text-ink mt-2 block rounded-xl bg-white px-3 py-2.5 md:hidden">
            {dailyTime}
          </span>
        </label>
        <div className="text-slate text-xs">
          下次检查
          <p className="text-ink mt-2 rounded-xl bg-white px-3 py-2.5">
            {dateTime(policy.next_due_at)}
          </p>
        </div>
      </div>
      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        <PolicyToggle
          label="启用定时策略"
          checked={enabled}
          onChange={setEnabled}
          disabled={!canManage}
        />
        <PolicyToggle
          label="公司公告与事件"
          checked={events}
          onChange={setEvents}
          disabled={!canManage}
        />
        <PolicyToggle
          label="同行研究"
          checked={peers}
          onChange={setPeers}
          disabled={!canManage}
        />
        <PolicyToggle
          label="有限自动 AI"
          checked={ai}
          onChange={setAI}
          disabled={!canManage}
          icon="ai"
        />
      </div>
      {canManage && (
        <button
          onClick={() => update.mutate()}
          disabled={update.isPending}
          className="border-blue/20 text-blue mt-4 hidden rounded-xl border px-3 py-2 text-xs disabled:opacity-50 md:block"
        >
          保存新版本
        </button>
      )}
    </Card>
  );
}

function PolicyToggle({
  label,
  checked,
  onChange,
  disabled,
  icon,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
  disabled: boolean;
  icon?: "ai";
}) {
  return (
    <label className="border-ink/8 flex items-center gap-3 rounded-xl border bg-white px-3 py-2.5 text-xs">
      {icon === "ai" ? (
        <Bot className="text-blue size-3.5" />
      ) : (
        <DatabaseZap className="text-blue size-3.5" />
      )}
      <span className="flex-1">{label}</span>
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
        className="accent-blue hidden size-4 md:block"
      />
      <span
        aria-label={checked ? "已启用" : "已关闭"}
        className={`size-2 rounded-full md:hidden ${checked ? "bg-emerald-500" : "bg-slate-300"}`}
      />
    </label>
  );
}

function AutomationRunDetailPanel({
  run,
  loading,
  canResume,
  resuming,
  onResume,
}: {
  run?: Awaited<ReturnType<typeof api.getAutomationRun>>;
  loading: boolean;
  canResume: boolean;
  resuming: boolean;
  onResume: (runId: string) => void;
}) {
  if (!run) {
    return (
      <Card className="text-slate grid min-h-72 place-items-center p-8 text-center text-sm">
        选择一条运行记录查看步骤、变化与错误摘要
      </Card>
    );
  }
  const resumable = ["failed", "partial", "succeeded_with_warnings"].includes(
    run.status,
  );
  return (
    <Card className="overflow-hidden">
      <div className="border-ink/8 flex items-start gap-3 border-b p-5">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-medium">运行详情</h3>
            <StatusPill status={run.status} />
            {loading && (
              <RefreshCw className="text-slate size-3.5 animate-spin" />
            )}
          </div>
          <p className="font-data text-slate mt-1 truncate text-[10px]">
            {run.id}
          </p>
        </div>
        {resumable && canResume && (
          <button
            onClick={() => onResume(run.id)}
            disabled={resuming}
            className="border-blue/20 text-blue hidden items-center gap-2 rounded-xl border px-3 py-2 text-xs md:flex"
          >
            <RotateCcw className="size-3.5" />
            恢复失败步骤
          </button>
        )}
      </div>
      <div className="grid grid-cols-3 gap-px bg-black/[0.06] sm:grid-cols-6">
        <MetricTile label="股票" value={run.universe_size} />
        <MetricTile label="成功" value={run.succeeded_steps} />
        <MetricTile label="跳过" value={run.skipped_steps} />
        <MetricTile label="失败" value={run.failed_steps} />
        <MetricTile label="信号" value={run.signal_count} />
        <MetricTile label="提醒" value={run.alert_count} />
      </div>
      <div className="max-h-[520px] overflow-auto">
        <table className="w-full min-w-[660px] text-left text-xs">
          <thead className="bg-paper text-slate sticky top-0">
            <tr>
              {["顺序", "范围", "步骤", "状态", "执行结果", "原因", "耗时"].map(
                (item) => (
                  <th key={item} className="px-4 py-3 font-medium">
                    {item}
                  </th>
                ),
              )}
            </tr>
          </thead>
          <tbody>
            {run.steps.map((step) => (
              <tr key={step.id} className="border-ink/8 border-t">
                <td className="font-data px-4 py-3">{step.dependency_order}</td>
                <td className="px-4">
                  {translateEnum("scope_type", step.scope_type)} ·{" "}
                  <span className="font-data">
                    {step.symbol ?? step.scope_key}
                  </span>
                </td>
                <td className="px-4 font-medium">{step.step_key}</td>
                <td className="px-4">
                  <StatusPill status={step.status} />
                </td>
                <td className="px-4">
                  {step.status === "succeeded"
                    ? step.changed
                      ? "完成，有更新"
                      : "完成，无变化"
                    : step.status === "skipped"
                      ? "未执行"
                      : "执行失败"}
                </td>
                <td className="text-slate max-w-[220px] px-4">
                  {automationReasonCopy[step.error_code ?? ""] ??
                    step.error_code ??
                    "—"}
                </td>
                <td className="font-data px-4">
                  {step.duration_ms ? `${step.duration_ms} ms` : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

const automationReasonCopy: Record<string, string> = {
  financial_check_not_due: "未到财务数据检查时间",
  market_input_unchanged: "行情输入没有变化",
  fundamental_input_unchanged: "基本面输入没有变化",
  research_input_unchanged: "确定性研究输入没有变化",
  signal_inputs_unchanged: "信号依赖没有变化",
  ai_research_output_current: "已有当前版本的 AI 股票体检",
  automation_ai_disabled: "自动 AI 或股票体检路由未启用",
  deterministic_snapshot_missing: "缺少确定性研究快照",
  unsupported_issuer_type: "当前发行人模板暂不支持",
  automation_ai_call_limit_reached: "达到本次运行的 AI 调用上限",
  ai_generation_failed: "DeepSeek 生成或安全校验未通过",
  ProviderUnavailableError: "上游数据服务暂不可用",
  ProviderConnectionError: "上游连接中断",
  provider_connection_failed: "上游连接中断",
  provider_proxy_unavailable: "本地代理不可用",
  provider_timeout: "上游请求超时",
  provider_rate_limited: "上游请求受到限流",
  provider_invalid_response: "上游响应格式无效",
};

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <p className="font-data text-lg font-semibold">{value}</p>
      <p className="text-slate mt-1 text-[10px]">{label}</p>
    </div>
  );
}

function MetricTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-paper p-3 text-center">
      <p className="font-data text-base font-semibold">{value}</p>
      <p className="text-slate mt-1 text-[10px]">{label}</p>
    </div>
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
        eyebrow="账户支持"
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
      severity,
    }: {
      id: string;
      status: "triaged" | "resolved";
      severity?: "P0" | "P1" | "P2" | "P3";
    }) =>
      api.updateOperatorFeedback(id, {
        status,
        ...(severity ? { severity } : {}),
        ...(status === "resolved" ? { resolution_code: "addressed" } : {}),
      }),
    onSuccess: () =>
      client.invalidateQueries({ queryKey: ["operator-feedback"] }),
  });
  return (
    <>
      <PanelTitle
        eyebrow="内测反馈学习"
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
                  <b className="text-sm">
                    {feedbackFeatureLabel(item.feature_key)}
                    <span className="font-data text-slate ml-1 text-[9px] font-normal">
                      {item.feature_key}
                    </span>
                  </b>
                  <StatusPill status={item.status} />
                  <span className="font-data bg-mist rounded-full px-2 py-1 text-[10px]">
                    {item.severity}
                  </span>
                  <span className="text-slate text-xs">
                    {feedbackCategoryLabel(item.category)} ·{" "}
                    <span className="font-data text-[9px]">
                      {item.category}
                    </span>{" "}
                    · {dateTime(item.created_at)}
                  </span>
                </div>
                <p className="mt-3 text-sm leading-6">{item.message}</p>
              </div>
              {capabilities.includes("feedback.manage") && (
                <div className="hidden gap-2 md:flex">
                  <select
                    aria-label="反馈严重级别"
                    value={item.severity}
                    onChange={(event) =>
                      update.mutate({
                        id: item.id,
                        status: "triaged",
                        severity: event.target.value as
                          | "P0"
                          | "P1"
                          | "P2"
                          | "P3",
                      })
                    }
                    className="border-ink/10 rounded-lg border px-2 py-1.5 text-xs"
                  >
                    {(["P0", "P1", "P2", "P3"] as const).map((severity) => (
                      <option key={severity}>{severity}</option>
                    ))}
                  </select>
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

function ProvidersPanel({
  capabilities,
  elevated,
}: {
  capabilities: string[];
  elevated: boolean;
}) {
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
      {capabilities.includes("coverage.read") && (
        <ProviderAcceptancePanel
          canRun={capabilities.includes("coverage.run")}
          elevated={elevated}
        />
      )}
      {capabilities.includes("providers.config.read") && (
        <ProviderConfigurationPanel
          canManage={capabilities.includes("providers.config.manage")}
          elevated={elevated}
        />
      )}
      <section
        className={
          capabilities.includes("providers.config.read") ? "mt-9" : undefined
        }
      >
        <PanelTitle
          eyebrow="外部服务依赖"
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
                    <h3 className="font-medium">
                      {providerDisplayName(item.provider)}
                    </h3>
                    <p className="text-slate mt-1 text-xs">
                      {providerCapabilityLabel(item.capability)}
                      <span className="font-data ml-1 text-[9px] opacity-65">
                        {item.capability}
                      </span>
                    </p>
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
                <p className="text-risk mt-3 text-xs">
                  {translateReasonCode(item.reason_code, "admin")}
                </p>
              )}
              {capabilities.includes("providers.diagnose") &&
                (item.provider === "deepseek" ||
                  item.provider === "resend") && (
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
      </section>
    </>
  );
}

const feedbackFeatureLabels: Record<string, string> = {
  stock_research: "个股研究",
  research_feed: "研究动态",
  watchlist: "自选股",
  alerts: "研究提醒",
  screening: "股票筛选",
  comparison: "公司对比",
  account: "账户与访问",
  other: "其他功能",
};

const feedbackCategoryLabels: Record<string, string> = {
  bug: "功能异常",
  data_missing: "数据缺失",
  hard_to_understand: "难以理解",
  feature_request: "功能建议",
  other: "其他反馈",
};

function feedbackFeatureLabel(code: string) {
  return feedbackFeatureLabels[code] ?? "其他功能";
}

function feedbackCategoryLabel(code: string) {
  return feedbackCategoryLabels[code] ?? "其他反馈";
}

function providerCapabilityLabel(code: string) {
  const labels: Record<string, string> = {
    ai_research: "AI 研究生成",
    email_delivery: "事务邮件发送",
    transactional_email: "事务邮件发送",
  };
  return labels[code] ?? "外部服务能力";
}

function AuditPanel() {
  const query = useQuery({
    queryKey: ["operator-audit"],
    queryFn: api.getOperatorAudit,
  });
  return (
    <>
      <PanelTitle
        eyebrow="不可变审计记录"
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
