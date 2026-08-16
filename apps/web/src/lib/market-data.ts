import type {
  DailyBarListResponse,
  DailyBarResponse,
} from "@zhaoniu/api-client";
import type { CandlestickData, Time } from "lightweight-charts";

const decimalPattern = /^-?[0-9]+(?:\.[0-9]+)?$/;

export function parseFiniteDecimal(value: string, field: string): number {
  if (!decimalPattern.test(value)) {
    throw new TypeError(`${field} is not a decimal string`);
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    throw new TypeError(`${field} is outside the finite chart range`);
  }
  return parsed;
}

function validateDate(value: string): Time {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    throw new TypeError("trade_date is not an ISO date");
  }
  return value as Time;
}

export function toCandles(items: DailyBarResponse[]): CandlestickData<Time>[] {
  return items.map((item) => ({
    time: validateDate(item.trade_date),
    open: parseFiniteDecimal(item.open, "open"),
    high: parseFiniteDecimal(item.high, "high"),
    low: parseFiniteDecimal(item.low, "low"),
    close: parseFiniteDecimal(item.close, "close"),
  }));
}

export function assertDailyBars(
  value: DailyBarListResponse,
): DailyBarListResponse {
  if (value.adjust !== "none" || value.total !== value.items.length) {
    throw new TypeError("daily-bar response metadata is inconsistent");
  }
  toCandles(value.items);
  return value;
}
