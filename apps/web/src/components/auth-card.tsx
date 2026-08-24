"use client";

import { ApiError, createZhaoniuClient } from "@zhaoniu/api-client";
import { LoaderCircle, Telescope } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

const api = createZhaoniuClient();

export function AuthCard({ mode }: { mode: "login" | "register" }) {
  const isRegister = mode === "register";
  const router = useRouter();
  const search = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [invitationCode, setInvitationCode] = useState(
    isRegister ? (search.get("invite") ?? "") : "",
  );
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [privacyAccepted, setPrivacyAccepted] = useState(false);
  const [legalVersions, setLegalVersions] = useState<{
    terms_of_service: string;
    privacy_policy: string;
  } | null>(null);

  useEffect(() => {
    if (!isRegister) return;
    void api
      .getCurrentLegalDocuments()
      .then((response) => {
        const terms = response.items.find(
          (item) => item.document_type === "terms_of_service",
        );
        const privacy = response.items.find(
          (item) => item.document_type === "privacy_policy",
        );
        if (terms && privacy) {
          setLegalVersions({
            terms_of_service: terms.version,
            privacy_policy: privacy.version,
          });
        }
      })
      .catch(() => setError("暂时无法读取注册协议，请稍后再试。"));
  }, [isRegister]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (isRegister && password.length < 15) {
      setError("密码至少需要 15 位。");
      return;
    }
    if (isRegister && password !== confirmation) {
      setError("两次输入的密码不一致。");
      return;
    }
    if (isRegister && (!termsAccepted || !privacyAccepted || !legalVersions)) {
      setError("请阅读并同意当前版本的用户协议和隐私政策。");
      return;
    }
    setSubmitting(true);
    try {
      if (isRegister) {
        await api.register(email, password, invitationCode, [
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
        await api.login(email, password);
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
      if (caught instanceof ApiError && caught.status === 409) {
        setError("邮箱已注册，或受控体验名额暂时已满。请尝试登录或联系客服。");
      } else if (caught instanceof ApiError && caught.status === 401) {
        setError("邮箱或密码不正确。");
      } else if (caught instanceof ApiError && caught.status === 422) {
        setError(
          isRegister
            ? "邀请码不可用，或注册信息未通过校验。"
            : "请检查邮箱格式和密码长度。",
        );
      } else {
        setError("暂时无法完成认证，请稍后再试。");
      }
    } finally {
      setSubmitting(false);
    }
  }

  const inputClass =
    "border-ink/15 focus:border-blue mt-2 w-full rounded-xl border bg-white px-4 py-3 font-normal outline-none transition";

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
        <p className="font-data text-blue mt-8 text-[10px] uppercase tracking-[0.18em]">
          安全可信的研究工作台
        </p>
        <h1 className="font-display mt-2 text-3xl font-semibold">
          {isRegister ? "创建研究账户" : "继续你的研究"}
        </h1>
        <p className="text-slate mt-2 text-sm leading-6">
          {isRegister
            ? "目前仅限受邀用户。注册后可保存自选股和研究工作区状态。"
            : "登录后查看你的持久化自选股，不影响公开行情和研究页面。"}
        </p>
        <form className="mt-7 space-y-4" onSubmit={submit}>
          {isRegister && (
            <label className="block text-sm font-medium">
              邀请码
              <input
                type="text"
                className={`${inputClass} font-data uppercase`}
                placeholder="INV-..."
                value={invitationCode}
                onChange={(event) => setInvitationCode(event.target.value)}
                autoComplete="off"
                required
              />
            </label>
          )}
          {isRegister && (
            <div className="border-ink/8 bg-mist space-y-3 rounded-xl border p-3.5 text-sm">
              <label className="flex items-start gap-3">
                <input
                  type="checkbox"
                  className="accent-blue mt-0.5 size-4"
                  checked={termsAccepted}
                  onChange={(event) => setTermsAccepted(event.target.checked)}
                  required
                />
                <span>
                  我已阅读并同意
                  <Link
                    className="text-blue mx-1 font-medium"
                    href="/legal/terms"
                  >
                    用户协议
                  </Link>
                </span>
              </label>
              <label className="flex items-start gap-3">
                <input
                  type="checkbox"
                  className="accent-blue mt-0.5 size-4"
                  checked={privacyAccepted}
                  onChange={(event) => setPrivacyAccepted(event.target.checked)}
                  required
                />
                <span>
                  我已阅读并同意
                  <Link
                    className="text-blue mx-1 font-medium"
                    href="/legal/privacy"
                  >
                    隐私政策
                  </Link>
                </span>
              </label>
            </div>
          )}
          <label className="block text-sm font-medium">
            邮箱
            <input
              type="email"
              className={inputClass}
              placeholder="name@example.com"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              required
            />
          </label>
          <label className="block text-sm font-medium">
            密码
            <input
              type="password"
              className={inputClass}
              placeholder={isRegister ? "至少 15 位字符" : "输入密码"}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete={isRegister ? "new-password" : "current-password"}
              required
            />
          </label>
          {isRegister && (
            <label className="block text-sm font-medium">
              确认密码
              <input
                type="password"
                className={inputClass}
                placeholder="再次输入密码"
                value={confirmation}
                onChange={(event) => setConfirmation(event.target.value)}
                autoComplete="new-password"
                required
              />
            </label>
          )}
          {error && (
            <p className="border-risk/25 bg-risk/5 text-risk rounded-xl border px-3 py-2 text-sm">
              {error}
            </p>
          )}
          <button
            type="submit"
            className="bg-blue flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
            disabled={submitting || (isRegister && !legalVersions)}
          >
            {submitting && <LoaderCircle className="size-4 animate-spin" />}
            {isRegister ? "创建账户" : "安全登录"}
          </button>
        </form>
        <p className="text-slate mt-5 text-center text-sm">
          {isRegister ? "已有账户？" : "还没有账户？"}{" "}
          <Link
            className="text-blue font-medium"
            href={isRegister ? "/login" : "/register"}
          >
            {isRegister ? "登录" : "受邀注册"}
          </Link>
        </p>
        {!isRegister && (
          <p className="mt-3 text-center text-sm">
            <Link className="text-blue font-medium" href="/forgot-password">
              忘记密码？
            </Link>
          </p>
        )}
        <p className="border-ink/8 text-slate mt-7 border-t pt-5 text-center text-xs leading-5">
          研究工具不构成投资建议，请独立核对数据与证据。
        </p>
      </section>
    </main>
  );
}
