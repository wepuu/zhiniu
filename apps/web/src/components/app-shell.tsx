"use client";

import { createZhaoniuClient } from "@zhaoniu/api-client";
import { useQuery } from "@tanstack/react-query";
import {
  Bell,
  Bookmark,
  House,
  Search,
  Settings,
  Telescope,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

const navigation = [
  { href: "/", label: "研究", icon: House },
  { href: "/watchlist", label: "自选", icon: Bookmark },
  { href: "/alerts", label: "提醒", icon: Bell },
  { href: "/settings", label: "设置", icon: Settings },
];
const api = createZhaoniuClient({ baseUrl: process.env.NEXT_PUBLIC_API_URL });

function isActive(pathname: string, href: string) {
  return href === "/"
    ? pathname === "/" ||
        pathname.startsWith("/screens") ||
        pathname.startsWith("/saved-screens")
    : pathname.startsWith(href);
}

function useAlertSummary() {
  return useQuery({
    queryKey: ["research-alert-summary"],
    queryFn: () => api.getResearchAlertSummary(),
    retry: false,
    staleTime: 30_000,
  });
}

function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <Link href="/" className="flex items-center gap-2.5">
      <span className="bg-ink text-paper grid size-9 place-items-center rounded-xl">
        <Telescope className="size-4" />
      </span>
      {!compact && (
        <span>
          <span className="font-display block text-lg font-semibold leading-none">
            知牛研究
          </span>
          <span className="font-data text-slate mt-1 block text-[9px] uppercase tracking-[0.2em]">
            Zhaoniu Research
          </span>
        </span>
      )}
    </Link>
  );
}

export function Header() {
  return (
    <header className="border-ink/8 bg-mist/90 sticky top-0 z-20 flex h-16 items-center border-b px-4 backdrop-blur md:px-8">
      <div className="flex w-full items-center gap-3">
        <div className="md:hidden">
          <Brand compact />
        </div>
        <div className="border-ink/10 bg-paper text-slate hidden min-w-72 items-center gap-2 rounded-full border px-4 py-2 text-sm md:flex">
          <Search className="size-4" />
          搜索股票、行业或研究记录
          <kbd className="font-data ml-auto text-xs">Ctrl K</kbd>
        </div>
        <p className="text-slate ml-auto hidden text-xs sm:block">
          研究工具，不构成投资建议
        </p>
      </div>
    </header>
  );
}

export function DesktopSidebar() {
  const pathname = usePathname();
  const summary = useAlertSummary();
  return (
    <aside
      data-testid="desktop-sidebar"
      className="border-ink/8 bg-paper fixed inset-y-0 left-0 z-30 hidden w-60 border-r p-5 md:block"
    >
      <Brand />
      <nav className="mt-10 space-y-1" aria-label="桌面主导航">
        {navigation.map(({ href, label, icon: Icon }) => {
          const active = isActive(pathname, href);
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm ${active ? "bg-blue text-white shadow-sm" : "text-slate hover:bg-mist hover:text-ink"}`}
            >
              <Icon className="size-4" />
              {label}
              {href === "/alerts" && !!summary.data?.unread_count && (
                <span className="ml-auto rounded-full bg-white/15 px-2 py-0.5 text-[10px]">
                  {summary.data.unread_count > 99
                    ? "99+"
                    : summary.data.unread_count}
                </span>
              )}
            </Link>
          );
        })}
      </nav>
      <div className="border-ink/8 absolute bottom-6 left-5 right-5 border-t pt-5">
        <p className="text-slate text-xs leading-5">
          研究证据优先
          <br />
          结论可回溯至数据源
        </p>
      </div>
    </aside>
  );
}

export function MobileBottomNav() {
  const pathname = usePathname();
  const summary = useAlertSummary();
  return (
    <nav
      data-testid="mobile-navigation"
      aria-label="移动端主导航"
      className="border-ink/10 bg-ink/95 fixed bottom-3 left-3 right-3 z-30 grid grid-cols-4 rounded-2xl border p-1.5 text-white shadow-2xl backdrop-blur md:hidden"
    >
      {navigation.map(({ href, label, icon: Icon }) => {
        const active = isActive(pathname, href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={`flex min-h-12 flex-col items-center justify-center gap-1 rounded-xl text-[10px] ${active ? "bg-white/12" : "text-white/60"}`}
          >
            <span className="relative">
              <Icon className="size-4" />
              {href === "/alerts" && !!summary.data?.unread_count && (
                <i className="bg-risk absolute -right-1.5 -top-1.5 size-2 rounded-full" />
              )}
            </span>
            {label}
          </Link>
        );
      })}
    </nav>
  );
}

export function Container({ children }: { children: ReactNode }) {
  return (
    <main className="mx-auto w-full max-w-[1440px] px-4 py-6 pb-24 sm:px-6 md:px-8 md:py-8 md:pb-10">
      {children}
    </main>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="bg-mist text-ink min-h-screen">
      <DesktopSidebar />
      <div className="md:pl-60">
        <Header />
        <Container>{children}</Container>
      </div>
      <MobileBottomNav />
    </div>
  );
}
