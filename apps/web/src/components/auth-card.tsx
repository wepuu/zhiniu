import Link from "next/link";
import { Telescope } from "lucide-react";

export function AuthCard({ mode }: { mode: "login" | "register" }) {
  const register = mode === "register";
  return (
    <main className="bg-mist grid min-h-screen place-items-center p-4">
      <section className="border-ink/10 bg-paper shadow-card w-full max-w-md rounded-3xl border p-7 sm:p-9">
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
          {register ? "建立研究账户" : "继续你的研究"}
        </h1>
        <p className="text-slate mt-2 text-sm">
          {register
            ? "使用邮箱创建账户，后续可管理自选与研究偏好。"
            : "登录后查看你的自选股研究轨道。"}
        </p>
        <form className="mt-7 space-y-4">
          <label className="block text-sm font-medium">
            邮箱
            <input
              type="email"
              className="border-ink/15 mt-2 w-full rounded-xl border bg-white px-4 py-3 font-normal"
              placeholder="name@example.com"
            />
          </label>
          <label className="block text-sm font-medium">
            密码
            <input
              type="password"
              className="border-ink/15 mt-2 w-full rounded-xl border bg-white px-4 py-3 font-normal"
              placeholder="至少 12 位字符"
            />
          </label>
          <button
            type="button"
            className="bg-blue w-full rounded-xl px-4 py-3 text-sm font-medium text-white"
          >
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
          研究工具不构成投资建议。认证表单在 Phase 0 仅验证界面边界。
        </p>
      </section>
    </main>
  );
}
