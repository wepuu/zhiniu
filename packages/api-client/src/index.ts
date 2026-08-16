import type { components } from "./schema";

export type StockResponse = components["schemas"]["StockResponse"];
export type DailyBarResponse = components["schemas"]["DailyBarResponse"];
export type DailyBarListResponse =
  components["schemas"]["DailyBarListResponse"];
export type FundamentalResearchResponse =
  components["schemas"]["FundamentalResearchResponse"];
export type FundamentalMetricResponse =
  components["schemas"]["FundamentalMetricResponse"];
export type FinancialPeriodListResponse =
  components["schemas"]["FinancialPeriodListResponse"];
export type ValuationListResponse =
  components["schemas"]["ValuationListResponse"];
export type ValuationObservationResponse =
  components["schemas"]["ValuationObservationResponse"];

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export interface ZhaoniuClientOptions {
  baseUrl?: string;
  fetcher?: typeof fetch;
}

export function createZhaoniuClient(options: ZhaoniuClientOptions = {}) {
  const baseUrl = (options.baseUrl ?? "http://localhost:8000")
    .replace(/\/$/, "")
    .replace(/\/api\/v1$/, "");
  const fetcher =
    options.fetcher ??
    ((...arguments_: Parameters<typeof fetch>) => fetch(...arguments_));

  async function request<T>(path: string): Promise<T> {
    const response = await fetcher(`${baseUrl}${path}`, {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      throw new ApiError(
        response.status,
        `API request failed with status ${response.status}`,
      );
    }
    return (await response.json()) as T;
  }

  return {
    getStock(symbol: string) {
      return request<StockResponse>(
        `/api/v1/stocks/${encodeURIComponent(symbol)}`,
      );
    },
    getDailyBars(symbol: string, limit = 120) {
      const query = new URLSearchParams({
        adjust: "none",
        limit: String(limit),
      });
      return request<DailyBarListResponse>(
        `/api/v1/stocks/${encodeURIComponent(symbol)}/daily-bars?${query}`,
      );
    },
    getFundamentals(symbol: string, asOf?: string) {
      const query = new URLSearchParams();
      if (asOf) query.set("as_of", asOf);
      const suffix = query.size ? `?${query}` : "";
      return request<FundamentalResearchResponse>(
        `/api/v1/stocks/${encodeURIComponent(symbol)}/research/fundamentals${suffix}`,
      );
    },
    getFinancialPeriods(symbol: string, limit = 12, asOf?: string) {
      const query = new URLSearchParams({ limit: String(limit) });
      if (asOf) query.set("as_of", asOf);
      return request<FinancialPeriodListResponse>(
        `/api/v1/stocks/${encodeURIComponent(symbol)}/financials/periods?${query}`,
      );
    },
    getValuations(symbol: string, metrics = "pe_ttm,pb,pcf,market_cap") {
      const query = new URLSearchParams({ metrics, limit: "4000" });
      return request<ValuationListResponse>(
        `/api/v1/stocks/${encodeURIComponent(symbol)}/valuations?${query}`,
      );
    },
  };
}

export type ZhaoniuClient = ReturnType<typeof createZhaoniuClient>;
