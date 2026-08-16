"use client";

import * as echarts from "echarts";
import { useEffect, useRef } from "react";

import type { valuationSeries } from "@/lib/fundamentals";

const labels: Record<string, string> = {
  pe_ttm: "PE-TTM",
  pb: "PB",
  pcf: "PCF",
};

export function ValuationChart({
  series,
  compact = false,
}: {
  series: ReturnType<typeof valuationSeries>;
  compact?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current, undefined, { renderer: "canvas" });
    chart.setOption({
      animationDuration: 280,
      color: ["#295f8f", "#b7791f", "#687383"],
      grid: { left: 44, right: 18, top: 42, bottom: 34 },
      legend: {
        top: 6,
        right: 12,
        itemWidth: 14,
        textStyle: { color: "#687383", fontSize: 11 },
      },
      tooltip: {
        trigger: "axis",
        valueFormatter: (value: unknown) => `${Number(value).toFixed(2)}×`,
      },
      xAxis: {
        type: "time",
        axisLine: { lineStyle: { color: "#dfe4e8" } },
        axisLabel: { color: "#687383", fontSize: 10 },
        splitLine: { show: false },
      },
      yAxis: {
        type: "value",
        scale: true,
        axisLabel: { color: "#687383", fontSize: 10 },
        splitLine: { lineStyle: { color: "#edf0f2" } },
      },
      series: series.map((item) => ({
        name: labels[item.code] ?? item.code,
        type: "line",
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 1.8 },
        emphasis: { focus: "series" },
        data: item.items.map((point) => [point.date, point.value]),
      })),
    });
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(ref.current);
    return () => {
      observer.disconnect();
      chart.dispose();
    };
  }, [series]);

  return (
    <div
      ref={ref}
      role="img"
      aria-label="历史估值倍数折线图"
      className={compact ? "h-64 w-full" : "h-[380px] w-full"}
    />
  );
}
