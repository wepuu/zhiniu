"use client";

import {
  CandlestickSeries,
  ColorType,
  createChart,
  type CandlestickData,
  type IChartApi,
  type Time,
} from "lightweight-charts";
import { useEffect, useRef } from "react";

export function StockChart({ data }: { data: CandlestickData<Time>[] }) {
  const container = useRef<HTMLDivElement>(null);
  const chart = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!container.current) return;
    const instance = createChart(container.current, {
      height: 380,
      layout: {
        background: { type: ColorType.Solid, color: "#fbfcfc" },
        textColor: "#687383",
        fontFamily: '"SFMono-Regular", Consolas, monospace',
      },
      grid: {
        vertLines: { color: "rgba(24,32,43,0.05)" },
        horzLines: { color: "rgba(24,32,43,0.07)" },
      },
      rightPriceScale: { borderColor: "rgba(24,32,43,0.12)" },
      timeScale: { borderColor: "rgba(24,32,43,0.12)", timeVisible: false },
      crosshair: {
        vertLine: { color: "#295f8f" },
        horzLine: { color: "#295f8f" },
      },
    });
    const series = instance.addSeries(CandlestickSeries, {
      upColor: "#b54b4b",
      downColor: "#295f8f",
      wickUpColor: "#b54b4b",
      wickDownColor: "#295f8f",
      borderVisible: false,
    });
    series.setData(data);
    instance.timeScale().fitContent();
    chart.current = instance;
    const observer = new ResizeObserver(([entry]) => {
      instance.applyOptions({ width: entry.contentRect.width });
    });
    observer.observe(container.current);
    return () => {
      observer.disconnect();
      instance.remove();
      chart.current = null;
    };
  }, [data]);

  return (
    <div
      ref={container}
      className="h-[380px] w-full"
      aria-label="未复权日 K 蜡烛图"
    />
  );
}
