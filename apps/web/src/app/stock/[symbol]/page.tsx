import { AppShell } from "@/components/app-shell";
import { MetricCard } from "@/components/metric-card";
import { PageHeading } from "@/components/page-heading";
import { Card } from "@/components/ui/card";

export default async function StockPage({
  params,
}: {
  params: Promise<{ symbol: string }>;
}) {
  const { symbol } = await params;
  return (
    <AppShell>
      <PageHeading
        eyebrow={`Stock · ${symbol}`}
        title="公司研究概览"
        description="当前为 Phase 0 页面骨架。行情、财务与证据将通过统一 API 和 Provider 管线接入。"
      />
      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        <MetricCard label="Price" value="—" note="等待规范化行情" />
        <MetricCard label="Data version" value="v0" note="Mock 数据" />
        <MetricCard label="Evidence" value="00" note="暂无证据" />
      </div>
      <Card className="mt-6 min-h-72 p-6">
        <h2 className="font-display text-xl font-semibold">研究维度</h2>
        <p className="text-slate mt-3 text-sm">
          公司画像、成长、盈利、财务质量、估值与风险将在后续阶段逐步开放。
        </p>
      </Card>
    </AppShell>
  );
}
