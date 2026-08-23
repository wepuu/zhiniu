"use client";

import {
  ApiError,
  createZhaoniuClient,
  type ProviderConfigurationView,
} from "@zhaoniu/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bot,
  CheckCircle2,
  FlaskConical,
  KeyRound,
  Mail,
  Send,
  ShieldAlert,
  Trash2,
} from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";

import { Card } from "@/components/ui/card";

const api = createZhaoniuClient({ baseUrl: process.env.NEXT_PUBLIC_API_URL });
const FLASH = "deepseek/deepseek-v4-flash";
const PRO = "deepseek/deepseek-v4-pro";

type Provider = "deepseek" | "resend";
type RouteConfiguration = {
  enabled: boolean;
  models: string[];
  max_attempts: number;
  timeout_seconds: number;
  deadline_seconds: number;
  max_output_tokens: number;
};
type DeepSeekConfiguration = {
  enabled: boolean;
  max_concurrency: number;
  daily_call_limit: number;
  stock_health: RouteConfiguration;
  screen_parser: RouteConfiguration;
  research_assistant: RouteConfiguration;
};
type ResendConfiguration = {
  enabled: boolean;
  from_name: string;
  from_email: string;
  sending_domain: string;
};

const routeDefault = (): RouteConfiguration => ({
  enabled: false,
  models: [FLASH],
  max_attempts: 1,
  timeout_seconds: 60,
  deadline_seconds: 90,
  max_output_tokens: 1200,
});

const deepSeekDefault = (): DeepSeekConfiguration => ({
  enabled: false,
  max_concurrency: 2,
  daily_call_limit: 100,
  stock_health: routeDefault(),
  screen_parser: {
    ...routeDefault(),
    timeout_seconds: 30,
    deadline_seconds: 75,
  },
  research_assistant: { ...routeDefault(), models: [FLASH], max_attempts: 1 },
});

function currentConfiguration(view: ProviderConfigurationView) {
  return view.draft?.configuration ?? view.active?.configuration ?? {};
}

function deepSeekConfiguration(
  view: ProviderConfigurationView,
): DeepSeekConfiguration {
  const raw = currentConfiguration(view) as Partial<DeepSeekConfiguration>;
  const fallback = deepSeekDefault();
  return {
    ...fallback,
    ...raw,
    stock_health: { ...fallback.stock_health, ...(raw.stock_health ?? {}) },
    screen_parser: { ...fallback.screen_parser, ...(raw.screen_parser ?? {}) },
    research_assistant: {
      ...fallback.research_assistant,
      ...(raw.research_assistant ?? {}),
      models: [FLASH],
      max_attempts: 1,
    },
  };
}

function resendConfiguration(
  view: ProviderConfigurationView,
): ResendConfiguration {
  const raw = currentConfiguration(view) as Partial<ResendConfiguration>;
  return {
    enabled: raw.enabled ?? false,
    from_name: raw.from_name ?? "知牛研究",
    from_email: raw.from_email ?? "",
    sending_domain: raw.sending_domain ?? "",
  };
}

function statusTone(status: string) {
  if (status === "healthy" || status === "encrypted")
    return "text-emerald-700 bg-emerald-50";
  if (status === "unavailable" || status === "missing")
    return "text-red-700 bg-red-50";
  return "text-amber-700 bg-amber-50";
}

function errorText(error: unknown) {
  if (error instanceof ApiError) return `请求未完成（${error.status}）`;
  return error instanceof Error ? error.message : "请求未完成";
}

export function ProviderConfigurationPanel({
  canManage,
  elevated,
}: {
  canManage: boolean;
  elevated: boolean;
}) {
  const [selected, setSelected] = useState<Provider>("deepseek");
  const query = useQuery({
    queryKey: ["provider-configurations"],
    queryFn: api.getProviderConfigurations,
  });
  const selectedView = query.data?.items.find(
    (item) => item.provider === selected,
  );

  return (
    <section className="mt-9">
      <div className="mb-5 flex items-end justify-between gap-4">
        <div>
          <p className="font-data text-blue text-[10px] uppercase tracking-[0.18em]">
            Managed configuration
          </p>
          <h2 className="font-display mt-1 text-xl font-semibold">
            服务配置发布台
          </h2>
          <p className="text-slate mt-2 text-xs">
            密钥只写入加密凭据库；草稿完成诊断后才可发布。
          </p>
        </div>
        <span className="border-ink/10 bg-paper hidden rounded-full border px-3 py-1.5 text-xs md:inline-flex">
          {elevated ? "敏感操作已验证" : "需要密码二次验证"}
        </span>
      </div>

      <div className="grid gap-4 md:hidden">
        {query.data?.items.map((item) => (
          <ProviderSummary key={item.provider} view={item} />
        ))}
        <p className="border-blue/15 bg-blue/5 text-slate rounded-xl border px-4 py-3 text-xs">
          移动端仅供查看。请在桌面端编辑、诊断和发布配置。
        </p>
      </div>

      <div className="hidden gap-5 md:grid md:grid-cols-[240px_minmax(0,1fr)]">
        <div className="space-y-3">
          {query.data?.items.map((item) => (
            <button
              key={item.provider}
              onClick={() => setSelected(item.provider)}
              className={`w-full rounded-2xl border p-4 text-left transition ${
                selected === item.provider
                  ? "border-blue/35 bg-blue/5 shadow-sm"
                  : "border-ink/8 bg-paper hover:border-ink/20"
              }`}
            >
              <ProviderSummary view={item} compact />
            </button>
          ))}
        </div>
        {selectedView ? (
          selected === "deepseek" ? (
            <DeepSeekEditor
              key={`deepseek-${selectedView.row_version}`}
              view={selectedView}
              editable={canManage && elevated}
            />
          ) : (
            <ResendEditor
              key={`resend-${selectedView.row_version}`}
              view={selectedView}
              editable={canManage && elevated}
            />
          )
        ) : (
          <Card className="text-slate grid min-h-72 place-items-center p-8 text-sm">
            {query.isLoading ? "正在读取服务配置…" : "配置暂时不可用"}
          </Card>
        )}
      </div>
    </section>
  );
}

function ProviderSummary({
  view,
  compact = false,
}: {
  view: ProviderConfigurationView;
  compact?: boolean;
}) {
  return (
    <div
      className={compact ? "" : "border-ink/8 bg-paper rounded-2xl border p-4"}
    >
      <div className="flex items-center gap-3">
        <span className="bg-ink text-paper grid size-9 place-items-center rounded-xl">
          {view.provider === "deepseek" ? (
            <Bot className="size-4" />
          ) : (
            <Mail className="size-4" />
          )}
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-medium capitalize">{view.provider}</p>
          <p className="text-slate mt-0.5 text-[11px]">
            {view.source} · {view.environment}
          </p>
        </div>
        <span
          className={`rounded-full px-2 py-1 text-[10px] ${statusTone(view.diagnostic_status)}`}
        >
          {view.diagnostic_status}
        </span>
      </div>
      <div className="text-slate mt-4 flex items-center justify-between text-[11px]">
        <span>凭据：{view.credential_state}</span>
        <span>
          {view.draft
            ? `草稿 v${view.draft.revision}`
            : `生效 v${view.active?.revision ?? "—"}`}
        </span>
      </div>
    </div>
  );
}

function DeepSeekEditor({
  view,
  editable,
}: {
  view: ProviderConfigurationView;
  editable: boolean;
}) {
  const client = useQueryClient();
  const [configuration, setConfiguration] = useState(() =>
    deepSeekConfiguration(view),
  );
  const [apiKey, setApiKey] = useState("");
  const refresh = () =>
    client.invalidateQueries({ queryKey: ["provider-configurations"] });
  const save = useMutation({
    mutationFn: () =>
      api.saveProviderDraft("deepseek", {
        expected_row_version: view.row_version,
        configuration,
        ...(apiKey ? { api_key: apiKey } : {}),
      }),
    onSuccess: () => {
      setApiKey("");
      void refresh();
    },
  });
  const importEnvironment = useMutation({
    mutationFn: () =>
      api.importProviderEnvironment("deepseek", view.row_version),
    onSuccess: refresh,
  });
  return (
    <Card className="overflow-hidden">
      <EditorHeader
        title="DeepSeek AI 路由"
        detail="一个凭据，三条相互隔离的研究用途。"
        view={view}
      />
      <div className="space-y-6 p-6">
        <ToggleRow
          label="启用 DeepSeek"
          detail="关闭后所有 DeepSeek 研究入口失败关闭。"
          checked={configuration.enabled}
          disabled={!editable}
          onChange={(enabled) =>
            setConfiguration({ ...configuration, enabled })
          }
        />
        <SecretField
          label="DeepSeek API Key"
          value={apiKey}
          configured={view.credential_state !== "missing"}
          disabled={!editable}
          onChange={setApiKey}
        />
        <div className="grid gap-4 xl:grid-cols-3">
          <RouteEditor
            title="AI 股票体检"
            detail="结构化解释与证据引用"
            value={configuration.stock_health}
            disabled={!editable}
            onChange={(stock_health) =>
              setConfiguration({ ...configuration, stock_health })
            }
          />
          <RouteEditor
            title="自然语言选股解析"
            detail="只生成候选筛选条件"
            value={configuration.screen_parser}
            disabled={!editable}
            onChange={(screen_parser) =>
              setConfiguration({ ...configuration, screen_parser })
            }
          />
          <RouteEditor
            title="研究助手"
            detail="固定 Flash、单次调用、关闭思考"
            value={configuration.research_assistant}
            disabled
            locked
            onChange={() => undefined}
          />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <NumberField
            label="Provider 最大并发"
            value={configuration.max_concurrency}
            min={1}
            max={16}
            disabled={!editable}
            onChange={(max_concurrency) =>
              setConfiguration({ ...configuration, max_concurrency })
            }
          />
          <NumberField
            label="UTC 每日调用预算"
            value={configuration.daily_call_limit}
            min={1}
            max={10000}
            disabled={!editable}
            onChange={(daily_call_limit) =>
              setConfiguration({ ...configuration, daily_call_limit })
            }
          />
        </div>
        {save.error && <ErrorNotice error={save.error} />}
        <EditorActions
          provider="deepseek"
          view={view}
          editable={editable}
          saving={save.isPending}
          onSave={() => save.mutate()}
          onImport={() => importEnvironment.mutate()}
        />
      </div>
    </Card>
  );
}

function ResendEditor({
  view,
  editable,
}: {
  view: ProviderConfigurationView;
  editable: boolean;
}) {
  const client = useQueryClient();
  const [configuration, setConfiguration] = useState(() =>
    resendConfiguration(view),
  );
  const [apiKey, setApiKey] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");
  const webhookUrl = useMemo(
    () =>
      typeof window === "undefined"
        ? "/api/v1/webhooks/resend"
        : `${window.location.origin.replace(/:\d+$/, ":8000")}/api/v1/webhooks/resend`,
    [],
  );
  const refresh = () =>
    client.invalidateQueries({ queryKey: ["provider-configurations"] });
  const save = useMutation({
    mutationFn: () =>
      api.saveProviderDraft("resend", {
        expected_row_version: view.row_version,
        configuration,
        ...(apiKey ? { api_key: apiKey } : {}),
        ...(webhookSecret ? { webhook_secret: webhookSecret } : {}),
      }),
    onSuccess: () => {
      setApiKey("");
      setWebhookSecret("");
      void refresh();
    },
  });
  return (
    <Card className="overflow-hidden">
      <EditorHeader
        title="Resend 邮件通道"
        detail="发送身份、最小权限密钥与回执验签。"
        view={view}
      />
      <div className="space-y-6 p-6">
        <ToggleRow
          label="启用 Resend"
          detail="发布前会向当前已验证管理员发送一封测试邮件。"
          checked={configuration.enabled}
          disabled={!editable}
          onChange={(enabled) =>
            setConfiguration({ ...configuration, enabled })
          }
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            label="发件人名称"
            value={configuration.from_name}
            disabled={!editable}
            onChange={(from_name) =>
              setConfiguration({ ...configuration, from_name })
            }
          />
          <TextField
            label="发件邮箱"
            type="email"
            value={configuration.from_email}
            disabled={!editable}
            onChange={(from_email) =>
              setConfiguration({ ...configuration, from_email })
            }
          />
          <TextField
            label="已验证发送域名"
            value={configuration.sending_domain}
            disabled={!editable}
            onChange={(sending_domain) =>
              setConfiguration({ ...configuration, sending_domain })
            }
          />
          <div>
            <label className="text-slate text-xs">固定 Webhook 地址</label>
            <button
              type="button"
              onClick={() => navigator.clipboard.writeText(webhookUrl)}
              className="border-ink/10 bg-mist mt-2 block w-full truncate rounded-xl border px-3 py-2.5 text-left font-mono text-xs"
            >
              {webhookUrl}
            </button>
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <SecretField
            label="Resend Sending access Key"
            value={apiKey}
            configured={view.credential_state !== "missing"}
            disabled={!editable}
            onChange={setApiKey}
          />
          <SecretField
            label="Webhook Signing Secret"
            value={webhookSecret}
            configured={view.credential_state !== "missing"}
            disabled={!editable}
            onChange={setWebhookSecret}
          />
        </div>
        <div className="border-ink/8 bg-mist flex items-center gap-3 rounded-xl border px-4 py-3 text-xs">
          <Send className="text-blue size-4" />
          Webhook：
          {view.webhook_verified_at
            ? `已于 ${new Date(view.webhook_verified_at).toLocaleString("zh-CN")} 验证`
            : "尚未收到合法签名事件"}
        </div>
        {save.error && <ErrorNotice error={save.error} />}
        <EditorActions
          provider="resend"
          view={view}
          editable={editable}
          saving={save.isPending}
          onSave={() => save.mutate()}
          onImport={() =>
            api
              .importProviderEnvironment("resend", view.row_version)
              .then(refresh)
          }
        />
      </div>
    </Card>
  );
}

function EditorHeader({
  title,
  detail,
  view,
}: {
  title: string;
  detail: string;
  view: ProviderConfigurationView;
}) {
  return (
    <div className="border-ink/8 bg-ink text-paper border-b p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-display text-xl font-semibold">{title}</p>
          <p className="mt-1 text-xs text-white/55">{detail}</p>
        </div>
        <span className="rounded-full bg-white/10 px-3 py-1.5 text-[10px]">
          {view.source} · row {view.row_version}
        </span>
      </div>
      <div className="mt-6 grid grid-cols-4 gap-2 text-[10px]">
        {["当前配置", "草稿", "诊断", "发布"].map((label, index) => {
          const active =
            index === 0 ||
            (index === 1 && !!view.draft) ||
            (index === 2 && view.diagnostic_status === "healthy") ||
            (index === 3 && !!view.active);
          return (
            <div
              key={label}
              className={`border-t pt-2 ${active ? "border-blue text-white" : "border-white/15 text-white/35"}`}
            >
              {label}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function EditorActions({
  provider,
  view,
  editable,
  saving,
  onSave,
  onImport,
}: {
  provider: Provider;
  view: ProviderConfigurationView;
  editable: boolean;
  saving: boolean;
  onSave: () => void;
  onImport: () => void;
}) {
  const client = useQueryClient();
  const refresh = () =>
    client.invalidateQueries({ queryKey: ["provider-configurations"] });
  const diagnose = useMutation({
    mutationFn: () => api.diagnoseProviderDraft(provider),
    onSuccess: refresh,
  });
  const publish = useMutation({
    mutationFn: () => api.publishProviderDraft(provider, view.row_version),
    onSuccess: refresh,
  });
  const discard = useMutation({
    mutationFn: () => api.discardProviderDraft(provider, view.row_version),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: () => api.removeProviderCredentials(provider, view.row_version),
    onSuccess: refresh,
  });
  const error =
    diagnose.error ?? publish.error ?? discard.error ?? remove.error;
  return (
    <div className="border-ink/8 border-t pt-5">
      {error && <ErrorNotice error={error} />}
      {!editable && (
        <p
          className="text-attention mb-3 flex items-center gap-2 text-xs"
          role="status"
        >
          <ShieldAlert className="size-4" />
          {view.draft
            ? "草稿已保存。请点击页面右上角“验证敏感操作”，然后继续诊断。"
            : "需要安全管理员权限和密码二次验证。"}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <ActionButton disabled={!editable || saving} onClick={onSave}>
          {saving ? "正在保存…" : "保存草稿"}
        </ActionButton>
        <ActionButton secondary disabled={!editable} onClick={onImport}>
          导入环境配置
        </ActionButton>
        <ActionButton
          secondary
          disabled={!editable || !view.draft || diagnose.isPending}
          onClick={() => diagnose.mutate()}
        >
          <FlaskConical className="size-3.5" />
          {diagnose.isPending ? "诊断中…" : "诊断草稿"}
        </ActionButton>
        <ActionButton
          disabled={
            !editable ||
            !view.draft ||
            (Boolean(view.draft.configuration.enabled) &&
              view.diagnostic_status !== "healthy")
          }
          onClick={() =>
            window.confirm(
              "发布后 API 与 Worker 将立即切换到该版本。确认发布？",
            ) && publish.mutate()
          }
        >
          <CheckCircle2 className="size-3.5" />
          发布
        </ActionButton>
        <ActionButton
          secondary
          disabled={!editable || !view.draft}
          onClick={() =>
            window.confirm("放弃当前草稿？候选凭据将被删除。") &&
            discard.mutate()
          }
        >
          放弃草稿
        </ActionButton>
        <ActionButton
          danger
          disabled={!editable || Boolean(view.active?.configuration.enabled)}
          onClick={() =>
            window.confirm("永久删除已加密凭据？此操作不可恢复。") &&
            remove.mutate()
          }
        >
          <Trash2 className="size-3.5" />
          永久删除凭据
        </ActionButton>
      </div>
    </div>
  );
}

function RouteEditor({
  title,
  detail,
  value,
  onChange,
  disabled,
  locked = false,
}: {
  title: string;
  detail: string;
  value: RouteConfiguration;
  onChange: (value: RouteConfiguration) => void;
  disabled: boolean;
  locked?: boolean;
}) {
  const fallback = value.models.length > 1;
  return (
    <div className="border-ink/8 rounded-2xl border p-4">
      <ToggleRow
        label={title}
        detail={detail}
        checked={value.enabled}
        disabled={disabled}
        onChange={(enabled) => onChange({ ...value, enabled })}
      />
      <div className="mt-4 space-y-3">
        <label className="text-slate block text-xs">
          首选模型
          <select
            value={value.models[0]}
            disabled={disabled || locked}
            onChange={(event) =>
              onChange({
                ...value,
                models: [
                  event.target.value,
                  ...(fallback
                    ? [event.target.value === FLASH ? PRO : FLASH]
                    : []),
                ],
              })
            }
            className="border-ink/10 bg-paper text-ink mt-1.5 w-full rounded-xl border px-3 py-2.5"
          >
            <option value={FLASH}>V4 Flash</option>
            <option value={PRO}>V4 Pro</option>
          </select>
        </label>
        {!locked && (
          <label className="text-slate flex items-center gap-2 text-xs">
            <input
              type="checkbox"
              checked={fallback}
              disabled={disabled}
              onChange={(event) =>
                onChange({
                  ...value,
                  models: event.target.checked
                    ? [value.models[0], value.models[0] === FLASH ? PRO : FLASH]
                    : [value.models[0]],
                  max_attempts: event.target.checked ? 2 : 1,
                })
              }
            />
            失败时尝试备用模型
          </label>
        )}
        <div className="grid grid-cols-2 gap-2">
          <NumberField
            label="单次超时"
            value={value.timeout_seconds}
            min={10}
            max={180}
            disabled={disabled || locked}
            onChange={(timeout_seconds) =>
              onChange({
                ...value,
                timeout_seconds,
                deadline_seconds: Math.max(
                  value.deadline_seconds,
                  timeout_seconds,
                ),
              })
            }
          />
          <NumberField
            label="总时限"
            value={value.deadline_seconds}
            min={15}
            max={240}
            disabled={disabled || locked}
            onChange={(deadline_seconds) =>
              onChange({ ...value, deadline_seconds })
            }
          />
        </div>
      </div>
    </div>
  );
}

function ToggleRow({
  label,
  detail,
  checked,
  disabled,
  onChange,
}: {
  label: string;
  detail: string;
  checked: boolean;
  disabled: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="flex items-center justify-between gap-4">
      <span>
        <b className="block text-sm font-medium">{label}</b>
        <small className="text-slate mt-1 block text-xs">{detail}</small>
      </span>
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
        className="accent-blue size-4"
      />
    </label>
  );
}

function SecretField({
  label,
  value,
  configured,
  disabled,
  onChange,
}: {
  label: string;
  value: string;
  configured: boolean;
  disabled: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <label className="text-slate block text-xs">
      <span className="flex items-center gap-1.5">
        <KeyRound className="size-3.5" />
        {label}
      </span>
      <input
        type="password"
        autoComplete="new-password"
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        placeholder={configured ? "已安全配置；留空表示不变" : "输入新密钥"}
        className="border-ink/10 bg-paper text-ink placeholder:text-slate/55 mt-2 w-full rounded-xl border px-3 py-2.5"
      />
    </label>
  );
}

function TextField({
  label,
  value,
  onChange,
  disabled,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
  type?: string;
}) {
  return (
    <label className="text-slate block text-xs">
      {label}
      <input
        type={type}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className="border-ink/10 bg-paper text-ink mt-2 w-full rounded-xl border px-3 py-2.5"
      />
    </label>
  );
}

function NumberField({
  label,
  value,
  onChange,
  min,
  max,
  disabled,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min: number;
  max: number;
  disabled: boolean;
}) {
  return (
    <label className="text-slate block text-[11px]">
      {label}
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        disabled={disabled}
        onChange={(event) => onChange(Number(event.target.value))}
        className="border-ink/10 bg-paper text-ink mt-1.5 w-full rounded-xl border px-3 py-2"
      />
    </label>
  );
}

function ActionButton({
  children,
  onClick,
  disabled,
  secondary = false,
  danger = false,
}: {
  children: ReactNode;
  onClick: () => void;
  disabled: boolean;
  secondary?: boolean;
  danger?: boolean;
}) {
  const tone = danger
    ? "border-red-200 text-red-700"
    : secondary
      ? "border-ink/10 text-ink"
      : "border-ink bg-ink text-white";
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`inline-flex items-center gap-2 rounded-xl border px-3.5 py-2.5 text-xs transition disabled:cursor-not-allowed disabled:opacity-35 ${tone}`}
    >
      {children}
    </button>
  );
}

function ErrorNotice({ error }: { error: unknown }) {
  return (
    <p className="border-risk/20 bg-risk/5 text-risk mb-3 rounded-xl border px-3 py-2.5 text-xs">
      {errorText(error)}
    </p>
  );
}
