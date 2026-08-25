import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "./app-shell";

vi.mock("next/navigation", () => ({
  usePathname: () => "/watchlist",
  useRouter: () => ({ push: vi.fn() }),
}));
afterEach(cleanup);

function renderShell(children: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <AppShell>{children}</AppShell>
    </QueryClientProvider>,
  );
}

describe("AppShell", () => {
  it("renders the application smoke content", () => {
    renderShell(<h1>研究工作区</h1>);
    expect(
      screen.getByRole("heading", { name: "研究工作区" }),
    ).toBeInTheDocument();
  });

  it("keeps independent desktop and mobile navigation compositions", () => {
    renderShell(<span>content</span>);
    expect(screen.getByTestId("desktop-sidebar")).toHaveClass(
      "hidden",
      "md:block",
    );
    expect(screen.getByTestId("mobile-navigation")).toHaveClass("md:hidden");
    expect(
      screen.getByRole("navigation", { name: "移动端主导航" }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("link", { current: "page" })).toHaveLength(2);
    expect(screen.getAllByRole("link", { name: "提醒" })).toHaveLength(2);
    expect(document.querySelectorAll('a[href="/research"]')).toHaveLength(0);
  });

  it("opens the real stock search from the keyboard and mobile entry", () => {
    renderShell(<span>content</span>);
    fireEvent.keyDown(window, { key: "k", ctrlKey: true });
    expect(
      screen.getByRole("dialog", { name: "搜索 A 股公司" }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "关闭股票搜索" }));
    fireEvent.click(screen.getByRole("button", { name: "搜索股票" }));
    expect(screen.getByRole("combobox")).toBeInTheDocument();
  });
});
