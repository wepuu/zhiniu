"use client";

import {
  ApiError,
  createZhaoniuClient,
  type StockReadinessResponse,
  type StockResponse,
  type WatchlistResponse,
} from "@zhaoniu/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  LoaderCircle,
  LogIn,
  Plus,
  RefreshCw,
  Trash2,
  TriangleAlert,
} from "lucide-react";
import Link from "next/link";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { PageHeading } from "@/components/page-heading";
import { StockSearchDialog } from "@/components/stock-search-dialog";
import { Card } from "@/components/ui/card";

const api = createZhaoniuClient();

export default function WatchlistPage() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recentlyAdded, setRecentlyAdded] = useState<StockResponse | null>(
    null,
  );
  const preparationStartedAt = useRef(0);
  const watchlists = useQuery({
    queryKey: ["watchlists"],
    queryFn: () => api.getWatchlists(),
    retry: false,
  });
  const symbols = useMemo(
    () =>
      Array.from(
        new Set(
          watchlists.data?.flatMap((list) =>
            list.items.map((item) => item.symbol),
          ) ?? [],
        ),
      ),
    [watchlists.data],
  );
  const readiness = useQuery({
    queryKey: ["stock-readiness", symbols],
    queryFn: () => api.getStockReadiness(symbols),
    enabled: symbols.length > 0,
    retry: false,
    refetchInterval: (query) => {
      if (typeof document !== "undefined" && document.hidden) return false;
      const active = query.state.data?.items.some((item) =>
        ["queued", "preparing"].includes(item.overall_status),
      );
      if (!active) return false;
      return Date.now() - preparationStartedAt.current < 60_000
        ? 5_000
        : 15_000;
    },
  });
  useEffect(() => {
    const active = readiness.data?.items.some((item) =>
      ["queued", "preparing"].includes(item.overall_status),
    );
    if (active && preparationStartedAt.current === 0)
      preparationStartedAt.current = Date.now();
    if (!active) preparationStartedAt.current = 0;
  }, [readiness.data]);
  const readinessBySymbol = useMemo(
    () =>
      new Map(
        readiness.data?.items.map((item) => [item.canonical_symbol, item]) ??
          [],
      ),
    [readiness.data],
  );

  const createList = useMutation({
    mutationFn: (value: string) => api.createWatchlist(value),
    onSuccess: async () => {
      setName("");
      setError(null);
      await queryClient.invalidateQueries({ queryKey: ["watchlists"] });
    },
    onError: (caught) => setError(formatWatchlistError(caught)),
  });

  const addItem = useMutation({
    mutationFn: ({
      watchlistId,
      value,
    }: {
      watchlistId: string;
      value: string;
    }) => api.addWatchlistItem(watchlistId, value.toUpperCase()),
    onSuccess: async () => {
      setError(null);
      await queryClient.invalidateQueries({ queryKey: ["watchlists"] });
      await queryClient.invalidateQueries({ queryKey: ["stock-readiness"] });
    },
    onError: (caught) => setError(formatWatchlistError(caught)),
  });

  const removeItem = useMutation({
    mutationFn: ({
      watchlistId,
      value,
    }: {
      watchlistId: string;
      value: string;
    }) => api.removeWatchlistItem(watchlistId, value),
    onSuccess: async () => {
      setError(null);
      await queryClient.invalidateQueries({ queryKey: ["watchlists"] });
    },
    onError: (caught) => setError(formatWatchlistError(caught)),
  });

  const defaultList = watchlists.data?.[0];
  const totalItems =
    watchlists.data?.reduce((sum, item) => sum + item.item_count, 0) ?? 0;

  function submitCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = name.trim();
    if (trimmed) createList.mutate(trimmed);
  }

  return (
    <AppShell>
      <PageHeading
        eyebrow="个人自选研究"
        title="我的自选股"
        description="围绕关注公司组织研究，不重复存储公共市场数据。"
      />
      {watchlists.isPending && (
        <Card
          className="mt-6 grid min-h-56 place-items-center p-8"
          role="status"
        >
          <div className="text-center">
            <LoaderCircle className="text-blue mx-auto size-5 animate-spin" />
            <p className="mt-3 font-medium">正在读取自选股</p>
          </div>
        </Card>
      )}
      {watchlists.isError && isUnauthorized(watchlists.error) && (
        <Card className="mt-6 p-6">
          <LogIn className="text-blue size-5" />
          <h2 className="font-display mt-4 text-2xl font-semibold">
            登录后保存你的自选股
          </h2>
          <p className="text-slate mt-2 text-sm leading-6">
            行情和公开研究仍可匿名查看；自选股分组属于你的个人工作区，需要账户会话。
          </p>
          <Link
            href="/login?next=/watchlist"
            className="bg-blue mt-5 inline-flex rounded-xl px-4 py-2 text-sm font-medium text-white"
          >
            登录账户
          </Link>
        </Card>
      )}
      {watchlists.isError && !isUnauthorized(watchlists.error) && (
        <Card className="border-risk/30 mt-6 p-6" role="alert">
          <TriangleAlert className="text-risk size-5" />
          <p className="mt-3 font-medium">自选股暂时不可用</p>
          <p className="text-slate mt-1 text-sm">请检查应用服务后重试。</p>
          <button
            className="bg-ink mt-4 inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm text-white"
            type="button"
            onClick={() => void watchlists.refetch()}
          >
            <RefreshCw className="size-4" />
            重新读取
          </button>
        </Card>
      )}
      {watchlists.data && (
        <>
          <div className="mt-6 grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
            <Card className="p-5">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <p className="text-slate text-xs">内测额度</p>
                  <p className="mt-1 text-sm">
                    {watchlists.data.length}/5 个分组，{totalItems}/30 只股票
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setSearchOpen(true)}
                  className="bg-blue inline-flex min-h-10 items-center gap-2 rounded-xl px-4 text-sm font-medium text-white disabled:opacity-50"
                  disabled={!defaultList || addItem.isPending}
                >
                  <Plus className="size-4" />
                  搜索并添加股票
                </button>
              </div>
              {error && (
                <p className="border-risk/20 bg-risk/5 text-risk mt-4 rounded-xl border px-3 py-2 text-sm">
                  {error}
                </p>
              )}
              {recentlyAdded && !addItem.isPending && !error && (
                <div className="border-blue/20 bg-blue/5 mt-4 rounded-xl border px-3 py-3 text-sm">
                  <p className="font-medium">已添加，正在准备研究数据</p>
                  <Link
                    className="text-blue mt-1 inline-block"
                    href={`/stock/${recentlyAdded.canonical_symbol}`}
                  >
                    查看 {recentlyAdded.name} 进度
                  </Link>
                </div>
              )}
            </Card>
            <Card className="p-5">
              <p className="text-sm font-medium">新建分组</p>
              <form className="mt-3 flex gap-2" onSubmit={submitCreate}>
                <input
                  className="border-ink/15 focus:border-blue min-h-10 min-w-0 flex-1 rounded-xl border bg-white px-3 text-sm outline-none"
                  placeholder="例如：白酒观察"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                />
                <button
                  type="submit"
                  className="bg-ink min-h-10 rounded-xl px-4 text-sm font-medium text-white disabled:opacity-50"
                  disabled={createList.isPending}
                >
                  创建
                </button>
              </form>
            </Card>
          </div>
          {watchlists.data.length === 0 ? (
            <Card className="mt-4 p-8 text-center">
              <p className="font-medium">还没有自选分组</p>
              <p className="text-slate mt-1 text-sm">
                创建一个分组后开始添加股票。
              </p>
            </Card>
          ) : (
            <div className="mt-4 grid gap-4 xl:grid-cols-2">
              {watchlists.data.map((item) => (
                <WatchlistGroup
                  key={item.id}
                  watchlist={item}
                  readiness={readinessBySymbol}
                  removing={removeItem.isPending}
                  onRemove={(value) =>
                    removeItem.mutate({ watchlistId: item.id, value })
                  }
                />
              ))}
            </div>
          )}
        </>
      )}
      <StockSearchDialog
        open={searchOpen}
        onOpenChange={setSearchOpen}
        title="添加到默认自选分组"
        description="按代码、中文名称、全拼或首字母查找，选择后直接添加"
        onSelect={(stock) => {
          if (defaultList) {
            setRecentlyAdded(stock);
            addItem.mutate({
              watchlistId: defaultList.id,
              value: stock.canonical_symbol,
            });
          }
        }}
      />
    </AppShell>
  );
}

function WatchlistGroup({
  watchlist,
  readiness,
  removing,
  onRemove,
}: {
  watchlist: WatchlistResponse;
  readiness: Map<string, StockReadinessResponse>;
  removing: boolean;
  onRemove: (symbol: string) => void;
}) {
  return (
    <Card className="overflow-hidden">
      <div className="border-ink/8 flex items-center justify-between gap-3 border-b px-5 py-4">
        <div>
          <h2 className="font-display text-xl font-semibold">
            {watchlist.name}
          </h2>
          <p className="text-slate mt-1 text-xs">
            {watchlist.is_default ? "默认分组" : "自定义分组"} ·{" "}
            {watchlist.item_count} 只股票
          </p>
        </div>
      </div>
      {watchlist.items.length === 0 ? (
        <div className="text-slate p-5 text-sm">这个分组还没有股票。</div>
      ) : (
        <div className="divide-ink/8 divide-y">
          {watchlist.items.map((item) => {
            const state = readiness.get(item.symbol);
            return (
              <div
                key={item.symbol}
                className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 px-5 py-4"
              >
                <Link href={`/stock/${item.symbol}`} className="min-w-0">
                  <span className="font-data block text-sm font-semibold">
                    {state?.name ?? item.symbol}
                  </span>
                  <span className="text-slate mt-1 block text-xs">
                    添加于 {new Date(item.added_at).toLocaleDateString("zh-CN")}
                  </span>
                  <span className="text-blue mt-1 block text-xs">
                    {item.symbol} · {readinessLabel(state)}
                  </span>
                  {state?.latest_trade_date && (
                    <span className="text-slate mt-1 block text-xs">
                      行情更新至 {state.latest_trade_date}
                    </span>
                  )}
                </Link>
                <button
                  type="button"
                  aria-label={`移除 ${item.symbol}`}
                  className="border-ink/10 hover:border-risk/40 hover:text-risk grid size-9 place-items-center rounded-xl border transition disabled:opacity-50"
                  disabled={removing}
                  onClick={() => onRemove(item.symbol)}
                >
                  <Trash2 className="size-4" />
                </button>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}

function isUnauthorized(error: unknown) {
  return error instanceof ApiError && error.status === 401;
}

function readinessLabel(state?: StockReadinessResponse) {
  if (!state) return "正在读取准备状态";
  return {
    queued: "已排队",
    preparing: `准备中 ${state.progress}%`,
    ready: "研究已就绪",
    partial: "部分研究可用",
    failed: "准备失败，可重试",
    paused: "自动准备已暂停",
    unsupported: "部分研究不适用",
  }[state.overall_status];
}

function formatWatchlistError(error: unknown) {
  if (error instanceof ApiError && error.status === 404) {
    return "没有找到这只股票，或你没有访问该分组的权限。";
  }
  if (error instanceof ApiError && error.status === 409) {
    return "已达到当前内测阶段的自选股额度。";
  }
  if (error instanceof ApiError && error.status === 422) {
    return "请输入 6 位 A 股代码，例如 600519。";
  }
  if (error instanceof ApiError && error.status === 401) {
    return "请先登录。";
  }
  return "操作暂时失败，请稍后再试。";
}
