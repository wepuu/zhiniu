import Link from "next/link";
import { Plus } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { PageHeading } from "@/components/page-heading";
import { Card } from "@/components/ui/card";
import { watchlist } from "@/lib/mock-data";

export default function WatchlistPage() {
  return (
    <AppShell>
      <PageHeading
        eyebrow="Watchlist"
        title="我的自选"
        description="围绕关注公司组织研究，不重复存储公共市场数据。"
      />
      <div className="mt-6 flex items-center justify-between">
        <p className="text-slate text-sm">
          核心观察 · {watchlist.length} 家公司
        </p>
        <button
          className="bg-blue flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium text-white"
          type="button"
        >
          <Plus className="size-4" />
          添加股票
        </button>
      </div>
      <Card className="mt-4 overflow-hidden">
        {watchlist.map((stock) => (
          <Link
            href={`/stock/${stock.symbol}`}
            key={stock.symbol}
            className="border-ink/8 hover:bg-mist grid grid-cols-[1fr_auto] items-center border-b p-4 last:border-0 sm:grid-cols-[1fr_140px_100px]"
          >
            <span>
              <strong>{stock.name}</strong>
              <small className="font-data text-slate ml-2">
                {stock.symbol}
              </small>
            </span>
            <span className="font-data hidden sm:block">{stock.price}</span>
            <span
              className={`font-data text-right text-sm ${stock.tone === "up" ? "text-risk" : "text-blue"}`}
            >
              {stock.change}
            </span>
          </Link>
        ))}
      </Card>
    </AppShell>
  );
}
