import Link from "next/link";
import { ArrowRight, CircleDotDashed } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { MetricCard } from "@/components/metric-card";
import { ResearchCard } from "@/components/research-card";
import { Card } from "@/components/ui/card";
import { researchNotes, watchlist } from "@/lib/mock-data";

export default function Home() {
  return (
    <AppShell>
      <section className="border-ink/10 flex flex-col gap-3 border-b pb-6 sm:flex-row sm:items-end">
        <div>
          <p className="font-data text-blue text-[11px] uppercase tracking-[0.18em]">
            Research workspace · 16 Aug
          </p>
          <h1 className="font-display mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
            今天值得复核的变化
          </h1>
          <p className="text-slate mt-2 max-w-2xl text-sm leading-6">
            把自选股的公告、财务与事件线索集中到一条可验证的研究轨道。
          </p>
        </div>
        <Link
          href="/watchlist"
          className="text-blue mt-3 flex items-center gap-2 text-sm font-medium sm:ml-auto sm:mt-0"
        >
          管理自选股 <ArrowRight className="size-4" />
        </Link>
      </section>
      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        <MetricCard label="Tracked" value="18" note="自选公司" />
        <MetricCard label="Changed" value="03" note="24 小时内有新线索" />
        <MetricCard label="Evidence" value="27" note="待复核证据条目" />
      </div>
      <div className="mt-8 grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <section>
          <div className="mb-4 flex items-center">
            <h2 className="font-display text-xl font-semibold">研究信息流</h2>
            <span className="font-data text-slate ml-3 flex items-center gap-1 text-[10px]">
              <CircleDotDashed className="size-3" />
              更新于 09:12
            </span>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            {researchNotes.map((note) => (
              <ResearchCard key={note.symbol} note={note} />
            ))}
          </div>
        </section>
        <aside>
          <div className="mb-4 flex items-center justify-between gap-3">
            <h2 className="font-display text-xl font-semibold">市场切片</h2>
            <span className="bg-amber/10 text-amber rounded-full px-2.5 py-1 text-[10px]">
              演示行情
            </span>
          </div>
          <Card className="overflow-hidden">
            <div className="border-ink/8 font-data text-slate grid grid-cols-[1fr_auto_auto] gap-3 border-b px-4 py-3 text-[10px] uppercase tracking-wider">
              <span>Stock</span>
              <span>Price</span>
              <span>Chg.</span>
            </div>
            {watchlist.map((stock) => (
              <Link
                href={`/stock/${stock.symbol}`}
                key={stock.symbol}
                className="border-ink/6 hover:bg-mist grid grid-cols-[1fr_auto_auto] items-center gap-3 border-b px-4 py-4 last:border-0"
              >
                <span>
                  <strong className="block text-sm">{stock.name}</strong>
                  <span className="font-data text-slate text-[10px]">
                    {stock.symbol}
                  </span>
                </span>
                <span className="font-data text-sm">{stock.price}</span>
                <span
                  className={`font-data text-xs ${stock.tone === "up" ? "text-risk" : "text-blue"}`}
                >
                  {stock.change}
                </span>
              </Link>
            ))}
          </Card>
        </aside>
      </div>
    </AppShell>
  );
}
