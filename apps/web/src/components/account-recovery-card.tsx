"use client";

import { ApiError, createZhaoniuClient } from "@zhaoniu/api-client";
import {
  CheckCircle2,
  KeyRound,
  LoaderCircle,
  MailCheck,
  Telescope,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

const api = createZhaoniuClient();

export function AccountRecoveryCard({
  mode,
}: {
  mode: "verify" | "forgot" | "reset";
}) {
  const search = useSearchParams();
  const token = search.get("token") ?? "";
  const isRegistration = search.get("registration") === "1";
  const [email, setEmail] = useState("");
  const [verificationCode, setVerificationCode] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [verified, setVerified] = useState(false);
  const [state, setState] = useState<"idle" | "loading" | "success" | "error">(
    mode === "verify" && token ? "loading" : "idle",
  );
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (mode !== "verify" || !token) return;
    void api
      .verifyEmail(token)
      .then((result) => {
        setVerified(true);
        setState("success");
        setMessage(
          result.status === "already_verified"
            ? "这个邮箱已经完成验证。"
            : "邮箱验证完成，你的账户恢复能力已启用。",
        );
      })
      .catch(() => {
        setState("error");
        setMessage("验证链接无效或已经过期，请登录后重新发送。 ");
      });
  }, [mode, token]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setState("loading");
    setMessage(null);
    try {
      if (mode === "forgot") {
        await api.requestPasswordReset(email);
        setMessage("如果该邮箱对应账户存在，我们将发送密码重置邮件。");
      } else if (mode === "reset") {
        if (!token) throw new Error("missing token");
        if (password.length < 8 || password !== confirmation) {
          setState("error");
          setMessage("密码至少 8 位，且两次输入必须一致。");
          return;
        }
        await api.confirmPasswordReset(token, password);
        setMessage("密码已重置，所有旧登录会话均已退出。请重新登录。");
      } else {
        if (verificationCode.length !== 8) {
          setState("error");
          setMessage("请输入邮件中的八位验证码。");
          return;
        }
        const result = await api.verifyEmailCode(verificationCode);
        setVerified(true);
        setMessage(
          result.status === "already_verified"
            ? "这个邮箱已经完成验证。"
            : "注册完成，邮箱验证成功。",
        );
      }
      setState("success");
    } catch (error) {
      setState("error");
      setMessage(emailVerificationErrorMessage(error, mode));
    }
  }

  async function resendVerification() {
    setState("loading");
    setMessage(null);
    try {
      const result = await api.resendEmailVerification();
      setState("idle");
      setMessage(
        result.status === "delivery_unavailable"
          ? "邮件服务暂时不可用，请稍后重试。"
          : result.status === "already_verified"
            ? "邮箱已经完成验证。"
            : "新的八位验证码已发送，请查看注册邮箱。",
      );
      if (result.status === "already_verified") {
        setVerified(true);
        setState("success");
      }
    } catch (error) {
      setState("error");
      setMessage(emailVerificationErrorMessage(error, "verify"));
    }
  }

  const title =
    mode === "verify"
      ? "验证你的邮箱"
      : mode === "forgot"
        ? "找回账户"
        : "设置新密码";
  const description =
    mode === "verify"
      ? isRegistration
        ? "验证码已发送到注册邮箱。输入八位数字即可完成注册。"
        : "输入邮件中的八位验证码，完成邮箱验证。"
      : mode === "forgot"
        ? "输入注册邮箱。为保护账户，无论邮箱是否存在都会显示相同结果。"
        : "新密码生效后，其他设备上的登录会话会全部退出。";
  const Icon = mode === "verify" ? MailCheck : KeyRound;

  return (
    <main className="bg-mist grid min-h-screen place-items-center p-4">
      <section className="border-ink/10 bg-paper shadow-card w-full max-w-md rounded-2xl border p-7 sm:p-9">
        <Link
          href="/"
          className="font-display inline-flex items-center gap-2 text-lg font-semibold"
        >
          <span className="bg-ink grid size-9 place-items-center rounded-xl text-white">
            <Telescope className="size-4" />
          </span>
          知牛研究
        </Link>
        <div className="bg-blue/8 text-blue mt-8 grid size-12 place-items-center rounded-2xl">
          <Icon className="size-5" />
        </div>
        <h1 className="font-display mt-4 text-3xl font-semibold">{title}</h1>
        <p className="text-slate mt-2 text-sm leading-6">{description}</p>

        {mode === "verify" && token && state === "loading" ? (
          <p className="text-slate mt-7 flex items-center gap-2 text-sm">
            <LoaderCircle className="size-4 animate-spin" /> 正在验证链接
          </p>
        ) : (
          <form className="mt-7 space-y-4" onSubmit={submit}>
            {mode === "forgot" && (
              <label className="block text-sm font-medium">
                注册邮箱
                <input
                  type="email"
                  className="border-ink/15 focus:border-blue mt-2 w-full rounded-xl border bg-white px-4 py-3 outline-none"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  autoComplete="email"
                  required
                />
              </label>
            )}
            {mode === "reset" && (
              <>
                <PasswordField
                  label="新密码"
                  value={password}
                  onChange={setPassword}
                />
                <PasswordField
                  label="确认新密码"
                  value={confirmation}
                  onChange={setConfirmation}
                />
              </>
            )}
            {mode === "verify" && !token && !verified && (
              <label className="block text-sm font-medium">
                邮箱验证码
                <input
                  type="text"
                  className="border-ink/15 focus:border-blue font-data mt-2 w-full rounded-xl border bg-white px-4 py-3 text-center text-xl tracking-[0.22em] outline-none"
                  value={formatVerificationCode(verificationCode)}
                  onChange={(event) =>
                    setVerificationCode(
                      event.target.value.replace(/\D/g, "").slice(0, 8),
                    )
                  }
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  maxLength={9}
                  placeholder="XXXX-XXXX"
                  aria-label="邮箱验证码"
                  required
                />
                <span className="text-slate mt-1.5 block text-xs leading-5">
                  输入数字时会自动显示为 XXXX-XXXX，无需手动输入连字符。
                </span>
              </label>
            )}
            {((mode !== "verify" && state !== "success") ||
              (mode === "verify" && !token && !verified)) && (
              <button
                className="bg-blue flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-medium text-white disabled:opacity-60"
                disabled={
                  state === "loading" ||
                  (mode === "verify" && verificationCode.length !== 8)
                }
              >
                {state === "loading" && (
                  <LoaderCircle className="size-4 animate-spin" />
                )}
                {mode === "verify"
                  ? "验证并完成注册"
                  : mode === "forgot"
                    ? "发送重置邮件"
                    : "确认重置密码"}
              </button>
            )}
            {mode === "verify" && !token && !verified && (
              <button
                type="button"
                className="border-ink/10 flex min-h-11 w-full items-center justify-center rounded-xl border bg-white px-4 text-sm font-medium disabled:opacity-60"
                disabled={state === "loading"}
                onClick={() => void resendVerification()}
              >
                重新发送验证码
              </button>
            )}
          </form>
        )}

        {message && (
          <div
            role="status"
            className={`mt-6 flex gap-3 rounded-xl border px-3.5 py-3 text-sm leading-6 ${state === "error" ? "border-risk/25 bg-risk/5 text-risk" : "border-blue/20 bg-blue/5"}`}
          >
            {state === "success" && (
              <CheckCircle2 className="mt-0.5 size-4 shrink-0" />
            )}
            {message}
          </div>
        )}
        {state === "success" && (
          <Link
            href={mode === "verify" && verified ? "/watchlist" : "/login"}
            className="border-ink/10 mt-5 flex min-h-11 items-center justify-center rounded-xl border text-sm font-medium"
          >
            {mode === "verify" && verified ? "进入研究工作台" : "返回登录"}
          </Link>
        )}
      </section>
    </main>
  );
}

function PasswordField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block text-sm font-medium">
      {label}
      <input
        type="password"
        className="border-ink/15 focus:border-blue mt-2 w-full rounded-xl border bg-white px-4 py-3 outline-none"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        autoComplete="new-password"
        minLength={8}
        required
      />
    </label>
  );
}

function formatVerificationCode(value: string) {
  return value.length > 4 ? `${value.slice(0, 4)}-${value.slice(4)}` : value;
}

function emailVerificationErrorMessage(
  error: unknown,
  mode: "verify" | "forgot" | "reset",
) {
  if (error instanceof ApiError) {
    if (error.status === 401) return "当前注册会话已失效，请返回登录后重试。";
    if (error.status === 429) return "尝试次数较多，请稍后再试。";
    if (error.message === "email_verification_expired") {
      return "验证码已过期，请重新发送后再试。";
    }
    if (error.message === "email_verification_invalid") {
      return "验证码不正确，请核对邮件后重新输入。";
    }
  }
  return mode === "verify"
    ? "邮箱验证没有完成，请检查验证码或稍后重试。"
    : "本次操作没有完成，请检查链接或稍后重试。";
}
