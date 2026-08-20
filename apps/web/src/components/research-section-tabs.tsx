"use client";

import { Binoculars, Newspaper } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const tabs = [
  { href: "/", label: "自选研究", icon: Newspaper },
  { href: "/screens", label: "股票筛选", icon: Binoculars },
] as const;

export function ResearchSectionTabs() {
  const pathname = usePathname() ?? "/";
  return (
    <nav
      aria-label="研究工作区"
      className="border-ink/10 bg-paper mb-6 inline-flex rounded-2xl border p-1 shadow-sm"
    >
      {tabs.map(({ href, label, icon: Icon }) => {
        const active =
          href === "/" ? pathname === "/" : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={
              "inline-flex min-h-10 items-center gap-2 rounded-xl px-4 text-sm transition " +
              (active ? "bg-ink text-white" : "text-slate hover:text-ink")
            }
          >
            <Icon className="size-4" />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
