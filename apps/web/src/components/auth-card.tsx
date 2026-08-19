"use client";

import { createZhaoniuClient, ApiError } from "@zhaoniu/api-client";
import { LoaderCircle, Telescope } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useState } from "react";

const api = createZhaoniuClient({
  baseUrl: process.env.NEXT_PUBLIC_API_BASE_URL,
});

export function AuthCard({ mode }: { mode: "login" | "register" }) {
  const register = mode === "register";
  const router = useRouter();
  const search = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (register && password.length < 15) {
      setError("密码至少需要 15 位。");
      return;
    }
    setSubmitting(true);
    try {
      if (register) {
        await api.register(email, password);
      } else {
        await api.login(email, password);
      }
      const next = search.get("next");
      router.push(next && next.startsWith("/") ? next : "/watchlist");
      router.refresh();
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 409) {
        setError("这个邮箱已经注册，请直接登录。");
      } else if (caught instanceof ApiError && caught.status === 401) {
        setError("邮箱或密码不正确。");
      } else if (caught instanceof ApiError && caught.status === 422) {
        setError("请检查邮箱格式和密码长度。");
      } else {
        setError("暂时无法完成认证，请稍后再试。");
      }
    } finally {
      setSubmitting(false);
    }
  }

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
          找牛研究
        </Link>
        <p className="font-data text-blue mt-8 text-[10px] uppercase tracking-[0.18em]">
          Secure research workspace
        </p>
        <h1 className="font-display mt-2 text-3xl font-semibold">
          {register ? "创建研究账户" : "继续你的研究"}
        </h1>
        <p className="text-slate mt-2 text-sm leading-6">
          {register
            ? "用于保存自选股分组和研究工作区状态。当前为内部 beta，不提供公开生产级账户服务。"
            : "登录后查看你的持久化自选股，不影响公开行情和研究页面。"}
        </p>
        <form className="mt-7 space-y-4" onSubmit={submit}>
          <label className="block text-sm font-medium">
            邮箱
            <input
              type="email"
              className="border-ink/15 focus:border-blue mt-2 w-full rounded-xl border bg-white px-4 py-3 font-normal outline-none transition"
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
              className="border-ink/15 focus:border-blue mt-2 w-full rounded-xl border bg-white px-4 py-3 font-normal outline-none transition"
              placeholder="至少 15 位字符"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete={register ? "new-password" : "current-password"}
              required
            />
          </label>
          {error && (
            <p className="border-risk/25 bg-risk/5 text-risk rounded-xl border px-3 py-2 text-sm">
              {error}
            </p>
          )}
          <button
            type="submit"
            className="bg-blue flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
            disabled={submitting}
          >
            {submitting && <LoaderCircle className="size-4 animate-spin" />}
            {register ? "创建账户" : "安全登录"}
          </button>
        </form>
        <p className="text-slate mt-5 text-center text-sm">
          {register ? "已有账户？" : "还没有账户？"}{" "}
          <Link
            className="text-blue font-medium"
            href={register ? "/login" : "/register"}
          >
            {register ? "登录" : "注册"}
          </Link>
        </p>
        <p className="border-ink/8 text-slate mt-7 border-t pt-5 text-center text-xs leading-5">
          研究工具不构成投资建议。请勿把任何输出理解为买卖建议、目标价或收益承诺。
        </p>
      </section>
    </main>
  );
}
