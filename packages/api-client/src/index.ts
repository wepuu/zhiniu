import type { components } from "./schema";

export type StockResponse = components["schemas"]["StockResponse"];
export type DailyBarResponse = components["schemas"]["DailyBarResponse"];
export type DailyBarListResponse =
  components["schemas"]["DailyBarListResponse"];

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
  const baseUrl = (options.baseUrl ?? "http://localhost:8000").replace(
    /\/$/,
    "",
  );
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
  };
}

export type ZhaoniuClient = ReturnType<typeof createZhaoniuClient>;
