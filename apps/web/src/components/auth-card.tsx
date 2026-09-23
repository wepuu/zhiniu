"use client";

import { ApiError, createZhaoniuClient } from "@zhaoniu/api-client";
import {
  ArrowRight,
  Check,
  KeyRound,
  LoaderCircle,
  LockKeyhole,
  MailCheck,
  RefreshCw,
  ShieldCheck,
  Telescope,
} from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

const api = createZhaoniuClient();

type RegistrationState = "loading" | "open" | "closed" | "error";

type RegistrationRequirement = {
  id: string;
  label: string;
  complete: boolean;
};

const registrationSteps = [
  {
    label: "确认邀请",
    detail: "邀请码和受邀邮箱需保持一致",
    icon: KeyRound,
  },
  {
    label: "创建账户",
    detail: "设置独立密码并确认协议",
    icon: ShieldCheck,
  },
  {
    label: "验证邮箱",
    detail: "通过邮件链接完成账户验证",
    icon: MailCheck,
  },
];

export function AuthCard({ mode }: { mode: "login" | "register" }) {
  const isRegister = mode === "register";
  const router = useRouter();
  const search = useSearchParams();
  const invitedEmail = isRegister ? (search.get("email") ?? "").trim() : "";
  const [email, setEmail] = useState(invitedEmail);
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [invitationCode, setInvitationCode] = useState(
    isRegister ? (search.get("invite") ?? "").trim().toUpperCase() : "",
  );
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [privacyAccepted, setPrivacyAccepted] = useState(false);
  const [registrationState, setRegistrationState] = useState<RegistrationState>(
    isRegister ? "loading" : "open",
  );
  const [registrationReload, setRegistrationReload] = useState(0);
  const [passwordMinLength, setPasswordMinLength] = useState(15);
  const [legalVersions, setLegalVersions] = useState<{
    terms_of_service: string;
    privacy_policy: string;
  } | null>(null);

  useEffect(() => {
    if (!isRegister) return;
    let active = true;

    void api
      .getRegistrationStatus()
      .then(async (status) => {
        if (!active) return;
        setPasswordMinLength(status.password_min_length);
        if (status.status === "closed") {
          setRegistrationState("closed");
          return;
        }
        const response = await api.getCurrentLegalDocuments();
        if (!active) return;
        const terms = response.items.find(
          (item) => item.document_type === "terms_of_service",
        );
        const privacy = response.items.find(
          (item) => item.document_type === "privacy_policy",
        );
        if (!terms || !privacy)
          throw new Error("required legal documents missing");
        setLegalVersions({
          terms_of_service: terms.version,
          privacy_policy: privacy.version,
        });
        setRegistrationState("open");
      })
      .catch(() => {
        if (active) setRegistrationState("error");
      });

    return () => {
      active = false;
    };
  }, [isRegister, registrationReload]);

  function reloadRegistrationStatus() {
    setRegistrationState("loading");
    setError(null);
    setRegistrationReload((value) => value + 1);
  }

  function updateField(update: () => void) {
    update();
    if (error) setError(null);
  }

  const registrationRequirements: RegistrationRequirement[] = isRegister
    ? [
        {
          id: "registration-invitation-code",
          label: "填写邀请码",
          complete: Boolean(invitationCode.trim()),
        },
        {
          id: "auth-email",
          label: "填写有效邮箱",
          complete: isValidEmail(email),
        },
        {
          id: "registration-password",
          label: `设置至少 ${passwordMinLength} 位密码`,
          complete: password.length >= passwordMinLength,
        },
        {
          id: "registration-password-confirmation",
          label: "两次密码保持一致",
          complete: Boolean(confirmation) && password === confirmation,
        },
        {
          id: "registration-terms",
          label: "同意用户协议",
          complete: termsAccepted,
        },
        {
          id: "registration-privacy",
          label: "同意隐私政策",
          complete: privacyAccepted,
        },
      ]
    : [];
  const incompleteRegistrationRequirements = registrationRequirements.filter(
    (requirement) => !requirement.complete,
  );

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (isRegister && incompleteRegistrationRequirements.length > 0) {
      const first = incompleteRegistrationRequirements[0];
      setError(`请先完成：${first.label}。`);
      window.requestAnimationFrame(() => {
        document.getElementById(first.id)?.focus();
      });
      return;
    }
    if (isRegister && (!termsAccepted || !privacyAccepted || !legalVersions)) {
      setError("请阅读并同意当前版本的用户协议和隐私政策。");
      return;
    }
    setSubmitting(true);
    try {
      if (isRegister) {
        await api.register(email.trim(), password, invitationCode.trim(), [
          {
            document_type: "terms_of_service",
            document_version: legalVersions!.terms_of_service,
          },
          {
            document_type: "privacy_policy",
            document_version: legalVersions!.privacy_policy,
          },
        ]);
      } else {
        await api.login(email.trim(), password);
      }
      const next = search.get("next");
      router.push(
        next && next.startsWith("/")
          ? next
          : isRegister
            ? "/verify-email"
            : "/watchlist",
      );
      router.refresh();
    } catch (caught) {
      setError(authenticationErrorMessage(caught, isRegister));
      if (
        isRegister &&
        caught instanceof ApiError &&
        caught.message === "registration_closed"
      ) {
        setRegistrationState("closed");
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (!isRegister) {
    return (
      <AuthShell>
        <AuthBrand />
        <p className="font-data text-blue mt-8 text-[10px] uppercase tracking-[0.18em]">
          安全可信的研究工作台
        </p>
        <h1 className="font-display mt-2 text-3xl font-semibold">
          继续你的研究
        </h1>
        <p className="text-slate mt-2 text-sm leading-6">
          登录后查看你的持久化自选股，不影响公开行情和研究页面。
        </p>
        <form className="mt-7 space-y-4" onSubmit={submit}>
          <EmailField value={email} onChange={setEmail} />
          <PasswordField
            id="login-password"
            value={password}
            onChange={setPassword}
            autoComplete="current-password"
          />
          {error && <ErrorNotice message={error} />}
          <PrimaryButton submitting={submitting}>安全登录</PrimaryButton>
        </form>
        <p className="text-slate mt-5 text-center text-sm">
          还没有账户？{" "}
          <Link className="text-blue font-medium" href="/register">
            受邀注册
          </Link>
        </p>
        <p className="mt-3 text-center text-sm">
          <Link className="text-blue font-medium" href="/forgot-password">
            忘记密码？
          </Link>
        </p>
        <ResearchDisclaimer />
      </AuthShell>
    );
  }

  return (
    <main className="bg-mist grid min-h-screen place-items-center p-4 sm:p-6">
      <section className="border-ink/10 bg-paper shadow-card grid w-full max-w-4xl overflow-hidden rounded-3xl border lg:grid-cols-[0.82fr_1.18fr]">
        <aside className="bg-ink relative overflow-hidden p-7 text-white sm:p-9">
          <div className="bg-blue/35 absolute -right-16 -top-20 size-56 rounded-full blur-3xl" />
          <div className="relative">
            <AuthBrand inverse />
            <p className="font-data mt-12 text-[10px] uppercase tracking-[0.2em] text-white/55">
              Invitation route
            </p>
            <h1 className="font-display mt-3 text-3xl font-semibold leading-tight">
              从邀请到研究工作台，
              <br />
              只需三步。
            </h1>
            <ol className="mt-9 space-y-1" aria-label="注册步骤">
              {registrationSteps.map((step, index) => {
                const Icon = step.icon;
                return (
                  <li
                    key={step.label}
                    className="relative flex gap-4 pb-6 last:pb-0"
                  >
                    {index < registrationSteps.length - 1 && (
                      <span className="absolute left-[17px] top-9 h-[calc(100%-1.6rem)] w-px bg-white/15" />
                    )}
                    <span className="bg-white/8 grid size-9 shrink-0 place-items-center rounded-full border border-white/15">
                      <Icon className="size-4" />
                    </span>
                    <span>
                      <span className="block text-sm font-medium">
                        {step.label}
                      </span>
                      <span className="mt-1 block text-xs leading-5 text-white/55">
                        {step.detail}
                      </span>
                    </span>
                  </li>
                );
              })}
            </ol>
            <p className="mt-10 border-t border-white/10 pt-5 text-xs leading-5 text-white/45">
              邀请码为一次性凭证。账户创建后仍需完成邮箱验证。
            </p>
          </div>
        </aside>

        <div className="p-7 sm:p-9 lg:p-11">
          <p className="font-data text-blue text-[10px] uppercase tracking-[0.18em]">
            受邀注册
          </p>
          <h2 className="font-display mt-2 text-3xl font-semibold">
            创建研究账户
          </h2>
          <p className="text-slate mt-2 text-sm leading-6">
            使用邀请邮件中的信息注册。我们会在提交前检查必要条件。
          </p>

          {registrationState === "loading" && (
            <RegistrationStateNotice
              icon={LoaderCircle}
              iconClassName="animate-spin"
              title="正在确认注册状态"
              description="同时加载当前协议和账户安全要求。"
            />
          )}

          {registrationState === "closed" && (
            <div className="border-amber/25 bg-amber/5 mt-8 rounded-2xl border p-5">
              <span className="bg-amber/10 text-amber grid size-10 place-items-center rounded-xl">
                <LockKeyhole className="size-5" />
              </span>
              <h3 className="mt-4 font-semibold">邀请注册当前未开放</h3>
              <p className="text-slate mt-2 text-sm leading-6">
                系统目前暂停创建新账户。邀请码仍按邀请邮件标注的有效期计算；开放后可返回本页继续。
              </p>
              <div className="mt-5 flex flex-wrap gap-3">
                <button
                  type="button"
                  className="border-ink/10 inline-flex min-h-11 items-center gap-2 rounded-xl border bg-white px-4 text-sm font-medium"
                  onClick={reloadRegistrationStatus}
                >
                  <RefreshCw className="size-4" /> 重新检查
                </button>
                <Link
                  href="/login"
                  className="text-blue inline-flex min-h-11 items-center gap-2 px-2 text-sm font-medium"
                >
                  已有账户，前往登录 <ArrowRight className="size-4" />
                </Link>
              </div>
            </div>
          )}

          {registrationState === "error" && (
            <div className="border-risk/25 bg-risk/5 mt-8 rounded-2xl border p-5">
              <h3 className="text-risk font-semibold">暂时无法确认注册状态</h3>
              <p className="text-slate mt-2 text-sm leading-6">
                网络或服务暂时不可用。为避免邀请码被误用，请先重新检查再填写。
              </p>
              <button
                type="button"
                className="border-risk/25 text-risk mt-5 inline-flex min-h-11 items-center gap-2 rounded-xl border bg-white px-4 text-sm font-medium"
                onClick={reloadRegistrationStatus}
              >
                <RefreshCw className="size-4" /> 重新检查
              </button>
            </div>
          )}

          {registrationState === "open" && (
            <form className="mt-7 space-y-5" onSubmit={submit} noValidate>
              <label className="block text-sm font-medium">
                邀请码
                <input
                  id="registration-invitation-code"
                  type="text"
                  className={`${inputClass} font-data uppercase tracking-wide`}
                  placeholder="INV-XXXX-XXXX-…"
                  value={invitationCode}
                  onChange={(event) =>
                    updateField(() =>
                      setInvitationCode(event.target.value.toUpperCase()),
                    )
                  }
                  autoComplete="one-time-code"
                  aria-label="邀请码"
                  aria-describedby="registration-invitation-code-hint"
                  spellCheck={false}
                  required
                />
                <span
                  id="registration-invitation-code-hint"
                  className="text-slate mt-1.5 block text-xs leading-5"
                >
                  可直接粘贴，大小写、空格和连字符不会影响识别。
                </span>
              </label>

              <EmailField
                value={email}
                onChange={(value) => updateField(() => setEmail(value))}
                readOnly={Boolean(invitedEmail)}
                helper={
                  invitedEmail
                    ? "此邀请已绑定该邮箱，不可修改。"
                    : "若邀请邮件指定了邮箱，请填写同一地址。"
                }
              />

              <div className="grid gap-4 sm:grid-cols-2">
                <PasswordField
                  id="registration-password"
                  value={password}
                  onChange={(value) => updateField(() => setPassword(value))}
                  autoComplete="new-password"
                  label="设置密码"
                  helper={`至少 ${passwordMinLength} 位字符`}
                  minLength={passwordMinLength}
                />
                <PasswordField
                  id="registration-password-confirmation"
                  value={confirmation}
                  onChange={(value) =>
                    updateField(() => setConfirmation(value))
                  }
                  autoComplete="new-password"
                  label="确认密码"
                  helper={
                    confirmation && password !== confirmation
                      ? "两次输入不一致"
                      : confirmation
                        ? "两次输入一致"
                        : "再次输入密码"
                  }
                  invalid={Boolean(confirmation && password !== confirmation)}
                  minLength={passwordMinLength}
                />
              </div>

              <div className="border-ink/8 bg-mist space-y-3 rounded-2xl border p-4 text-sm">
                <LegalAcceptance
                  id="registration-terms"
                  checked={termsAccepted}
                  onChange={(checked) =>
                    updateField(() => setTermsAccepted(checked))
                  }
                  href="/legal/terms"
                  label="用户协议"
                />
                <LegalAcceptance
                  id="registration-privacy"
                  checked={privacyAccepted}
                  onChange={(checked) =>
                    updateField(() => setPrivacyAccepted(checked))
                  }
                  href="/legal/privacy"
                  label="隐私政策"
                />
              </div>

              <div
                className="border-ink/8 rounded-2xl border bg-white p-4"
                aria-live="polite"
              >
                <p className="text-sm font-medium">
                  {incompleteRegistrationRequirements.length === 0
                    ? "注册信息已完整，可以创建账户"
                    : `还需完成 ${incompleteRegistrationRequirements.length} 项`}
                </p>
                <ul className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
                  {registrationRequirements.map((requirement) => (
                    <li
                      key={requirement.id}
                      className={
                        requirement.complete ? "text-emerald-700" : "text-slate"
                      }
                    >
                      <span className="inline-flex items-center gap-1.5">
                        <span
                          aria-hidden="true"
                          className={`grid size-4 place-items-center rounded-full border ${
                            requirement.complete
                              ? "border-emerald-600 bg-emerald-50"
                              : "border-ink/20"
                          }`}
                        >
                          {requirement.complete && <Check className="size-3" />}
                        </span>
                        {requirement.label}
                      </span>
                    </li>
                  ))}
                </ul>
                {incompleteRegistrationRequirements.length > 0 && (
                  <p className="text-slate mt-3 text-xs leading-5">
                    点击下方按钮会提示并定位到第一项未完成内容。
                  </p>
                )}
              </div>

              {error && <ErrorNotice message={error} />}

              <PrimaryButton submitting={submitting}>
                创建账户并发送验证邮件
              </PrimaryButton>
              <p className="text-slate text-center text-xs leading-5">
                已有账户？{" "}
                <Link className="text-blue font-medium" href="/login">
                  直接登录
                </Link>
              </p>
            </form>
          )}
          <ResearchDisclaimer />
        </div>
      </section>
    </main>
  );
}

const inputClass =
  "border-ink/15 focus:border-blue mt-2 min-h-12 w-full rounded-xl border bg-white px-4 py-3 font-normal outline-none transition focus:ring-3 focus:ring-blue/10 read-only:bg-mist read-only:text-slate";

function authenticationErrorMessage(error: unknown, isRegister: boolean) {
  if (!(error instanceof ApiError)) {
    return "暂时无法连接服务，请检查网络后重试。";
  }
  const messages: Record<string, string> = {
    registration_closed:
      "邀请注册刚刚暂停，本次没有创建账户。请在开放后重新尝试。",
    invalid_or_unavailable_invitation:
      "邀请码无效、已过期、已使用，或与当前邮箱不匹配。请从邀请邮件重新打开注册链接。",
    email_already_registered: "该邮箱已有账户，请直接登录或使用密码找回。",
    beta_capacity_reached:
      "本轮体验名额已满，邀请码尚未被本次操作使用。请联系邀请方确认后续安排。",
    registration_temporarily_unavailable:
      "尝试次数较多，注册已临时暂停。请稍后再试。",
    password_too_short: "密码未达到当前安全长度要求。",
    password_too_long: "密码不能超过 128 位字符。",
    required_legal_acceptance_missing:
      "协议版本已经更新，请刷新页面后重新确认。",
    invalid_credentials: "邮箱或密码不正确。",
  };
  if (messages[error.message]) return messages[error.message];
  if (error.status === 429)
    return messages.registration_temporarily_unavailable;
  if (error.status === 401) return messages.invalid_credentials;
  if (error.status === 422) {
    return isRegister
      ? "注册信息未通过校验，请检查邀请码、邮箱和密码后重试。"
      : "请检查邮箱格式和密码。";
  }
  return "服务暂时无法完成本次操作，请稍后重试。";
}

function AuthShell({ children }: { children: React.ReactNode }) {
  return (
    <main className="bg-mist grid min-h-screen place-items-center p-4">
      <section className="border-ink/10 bg-paper shadow-card w-full max-w-md rounded-2xl border p-7 sm:p-9">
        {children}
      </section>
    </main>
  );
}

function AuthBrand({ inverse = false }: { inverse?: boolean }) {
  return (
    <Link
      href="/"
      className={`font-display inline-flex items-center gap-2 text-lg font-semibold ${inverse ? "text-white" : "text-ink"}`}
    >
      <span
        className={`grid size-9 place-items-center rounded-xl ${inverse ? "text-ink bg-white" : "bg-ink text-white"}`}
      >
        <Telescope className="size-4" />
      </span>
      知牛研究
    </Link>
  );
}

function EmailField({
  value,
  onChange,
  readOnly = false,
  helper,
}: {
  value: string;
  onChange: (value: string) => void;
  readOnly?: boolean;
  helper?: string;
}) {
  const helperId = helper ? "auth-email-hint" : undefined;

  return (
    <div className="block text-sm font-medium">
      <label htmlFor="auth-email">邮箱</label>
      <input
        id="auth-email"
        type="email"
        className={inputClass}
        placeholder="name@example.com"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        readOnly={readOnly}
        autoComplete="email"
        aria-describedby={helperId}
        required
      />
      {helper && (
        <span
          id={helperId}
          className="text-slate mt-1.5 block text-xs leading-5"
        >
          {helper}
        </span>
      )}
    </div>
  );
}

function PasswordField({
  id,
  value,
  onChange,
  autoComplete,
  label = "密码",
  helper,
  invalid = false,
  minLength,
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete: "new-password" | "current-password";
  label?: string;
  helper?: string;
  invalid?: boolean;
  minLength?: number;
}) {
  const helperId = helper ? `${id}-hint` : undefined;

  return (
    <div className="block text-sm font-medium">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        type="password"
        className={`${inputClass} ${invalid ? "border-risk focus:border-risk focus:ring-risk/10" : ""}`}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        autoComplete={autoComplete}
        minLength={minLength}
        aria-invalid={invalid}
        aria-describedby={helperId}
        required
      />
      {helper && (
        <span
          id={helperId}
          className={`mt-1.5 flex items-center gap-1.5 text-xs ${invalid ? "text-risk" : "text-slate"}`}
        >
          {value && !invalid && <Check className="size-3.5" />}
          {helper}
        </span>
      )}
    </div>
  );
}

function LegalAcceptance({
  id,
  checked,
  onChange,
  href,
  label,
}: {
  id: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  href: string;
  label: string;
}) {
  return (
    <label className="flex items-start gap-3">
      <input
        id={id}
        type="checkbox"
        className="accent-blue mt-0.5 size-4"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        required
      />
      <span>
        我已阅读并同意
        <Link
          className="text-blue mx-1 font-medium underline-offset-4 hover:underline"
          href={href}
          target="_blank"
          rel="noreferrer"
        >
          {label}
        </Link>
        <span className="text-slate">（新窗口打开）</span>
      </span>
    </label>
  );
}

function isValidEmail(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}

function RegistrationStateNotice({
  icon: Icon,
  iconClassName = "",
  title,
  description,
}: {
  icon: typeof LoaderCircle;
  iconClassName?: string;
  title: string;
  description: string;
}) {
  return (
    <div
      role="status"
      className="border-ink/8 bg-mist mt-8 flex gap-3 rounded-2xl border p-4"
    >
      <Icon className={`text-blue mt-0.5 size-5 shrink-0 ${iconClassName}`} />
      <span>
        <span className="block text-sm font-medium">{title}</span>
        <span className="text-slate mt-1 block text-xs leading-5">
          {description}
        </span>
      </span>
    </div>
  );
}

function ErrorNotice({ message }: { message: string }) {
  return (
    <p
      role="alert"
      className="border-risk/25 bg-risk/5 text-risk rounded-xl border px-3.5 py-3 text-sm leading-6"
    >
      {message}
    </p>
  );
}

function PrimaryButton({
  children,
  submitting,
  disabled = false,
}: {
  children: React.ReactNode;
  submitting: boolean;
  disabled?: boolean;
}) {
  return (
    <button
      type="submit"
      className="bg-blue flex min-h-12 w-full items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-medium text-white transition hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-55"
      disabled={submitting || disabled}
    >
      {submitting && <LoaderCircle className="size-4 animate-spin" />}
      {children}
    </button>
  );
}

function ResearchDisclaimer() {
  return (
    <p className="border-ink/8 text-slate mt-7 border-t pt-5 text-center text-xs leading-5">
      研究工具不构成投资建议，请独立核对数据与证据。
    </p>
  );
}
