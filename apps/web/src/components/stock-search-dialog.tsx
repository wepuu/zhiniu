"use client";

import { createZhaoniuClient, type StockResponse } from "@zhaoniu/api-client";
import { useQuery } from "@tanstack/react-query";
import { LoaderCircle, Search, TriangleAlert, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

const api = createZhaoniuClient();

export function StockSearchDialog({
  open,
  onOpenChange,
  onSelect,
  title = "搜索 A 股公司",
  description = "支持 6 位股票代码或中文公司名称",
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelect: (stock: StockResponse) => void;
  title?: string;
  description?: string;
}) {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    previousFocus.current = document.activeElement as HTMLElement | null;
    inputRef.current?.focus();
    return () => previousFocus.current?.focus();
  }, [open]);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query.trim()), 200);
    return () => window.clearTimeout(timer);
  }, [query]);

  const search = useQuery({
    queryKey: ["stock-search", debouncedQuery],
    queryFn: () => api.searchStocks(debouncedQuery, 10),
    enabled: open && debouncedQuery.length >= 2,
    retry: false,
    staleTime: 60_000,
  });
  const items = useMemo(() => search.data?.items ?? [], [search.data?.items]);
  const safeActiveIndex = items.length
    ? Math.min(activeIndex, items.length - 1)
    : 0;

  function close() {
    setQuery("");
    setDebouncedQuery("");
    setActiveIndex(0);
    onOpenChange(false);
  }

  function select(stock: StockResponse) {
    onSelect(stock);
    close();
  }

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 bg-black/35 px-4 pt-[10vh] backdrop-blur-sm"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) close();
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="stock-search-title"
        aria-describedby="stock-search-description"
        className="bg-paper border-ink/10 mx-auto w-full max-w-xl overflow-hidden rounded-3xl border shadow-2xl"
      >
        <div className="border-ink/8 flex items-start justify-between gap-4 border-b px-5 py-4 sm:px-6">
          <div>
            <h2
              id="stock-search-title"
              className="font-display text-xl font-semibold"
            >
              {title}
            </h2>
            <p
              id="stock-search-description"
              className="text-slate mt-1 text-xs"
            >
              {description}
            </p>
          </div>
          <button
            type="button"
            aria-label="关闭股票搜索"
            onClick={close}
            className="hover:bg-mist grid size-9 shrink-0 place-items-center rounded-full"
          >
            <X className="size-4" />
          </button>
        </div>

        <div className="p-4 sm:p-5">
          <label className="border-ink/15 focus-within:border-blue flex min-h-12 items-center gap-3 rounded-2xl border bg-white px-4">
            <Search className="text-slate size-4 shrink-0" />
            <span className="sr-only">股票代码或中文名称</span>
            <input
              ref={inputRef}
              role="combobox"
              aria-autocomplete="list"
              aria-expanded={items.length > 0}
              aria-controls="stock-search-results"
              aria-activedescendant={
                items[safeActiveIndex]
                  ? `stock-search-option-${items[safeActiveIndex].canonical_symbol}`
                  : undefined
              }
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setActiveIndex(0);
              }}
              onKeyDown={(event) => {
                if (event.key === "Escape") close();
                if (event.key === "ArrowDown" && items.length) {
                  event.preventDefault();
                  setActiveIndex((value) => (value + 1) % items.length);
                }
                if (event.key === "ArrowUp" && items.length) {
                  event.preventDefault();
                  setActiveIndex(
                    (value) => (value - 1 + items.length) % items.length,
                  );
                }
                if (event.key === "Enter" && items[safeActiveIndex]) {
                  event.preventDefault();
                  select(items[safeActiveIndex]);
                }
              }}
              placeholder="例如：600519 或 贵州茅台"
              className="min-w-0 flex-1 bg-transparent text-sm outline-none"
            />
            {search.isFetching && (
              <LoaderCircle className="text-blue size-4 animate-spin" />
            )}
          </label>

          <div
            id="stock-search-results"
            role="listbox"
            className="mt-3 min-h-28"
          >
            {debouncedQuery.length < 2 && (
              <p className="text-slate px-3 py-8 text-center text-sm">
                输入至少 2 个字符开始搜索。
              </p>
            )}
            {debouncedQuery.length >= 2 && search.isError && (
              <div
                className="text-risk flex items-center justify-center gap-2 px-3 py-8 text-sm"
                role="alert"
              >
                <TriangleAlert className="size-4" />{" "}
                股票搜索暂时不可用，请稍后重试。
              </div>
            )}
            {debouncedQuery.length >= 2 &&
              search.isSuccess &&
              items.length === 0 && (
                <p className="text-slate px-3 py-8 text-center text-sm">
                  没有找到匹配的 A 股公司。
                </p>
              )}
            {items.map((stock, index) => (
              <button
                id={`stock-search-option-${stock.canonical_symbol}`}
                key={stock.canonical_symbol}
                type="button"
                role="option"
                aria-selected={index === safeActiveIndex}
                onMouseEnter={() => setActiveIndex(index)}
                onClick={() => select(stock)}
                className={`flex w-full items-center justify-between gap-4 rounded-2xl px-3 py-3 text-left ${index === safeActiveIndex ? "bg-blue/8" : "hover:bg-mist"}`}
              >
                <span className="min-w-0">
                  <span className="block truncate text-sm font-medium">
                    {stock.name}
                  </span>
                  <span className="text-slate font-data mt-1 block text-xs">
                    {stock.symbol} · {stock.exchange}
                  </span>
                </span>
                {stock.industry && (
                  <span className="text-slate max-w-32 truncate text-xs">
                    {stock.industry}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
