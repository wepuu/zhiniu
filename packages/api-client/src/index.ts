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
export type ResearchSnapshotEnvelope =
  components["schemas"]["ResearchSnapshotEnvelope"];
export type ResearchSnapshotDocument =
  components["schemas"]["ResearchSnapshotDocument"];
export type ResearchObservation = components["schemas"]["ResearchObservation"];
export type ObservationList = components["schemas"]["ObservationList"];
export type AIResearchEnvelope = components["schemas"]["AIResearchEnvelope"];
export type AIResearchOutputDocument =
  components["schemas"]["AIResearchOutputDocument"];
export type StockHealthResearchV1 =
  components["schemas"]["StockHealthResearchV1"];
export type EvidenceIndexEntry = components["schemas"]["EvidenceIndexEntry"];
export type CitedText = components["schemas"]["CitedText"];
export type AuthResponse = components["schemas"]["AuthResponse"];
export type MeResponse = components["schemas"]["MeResponse"];
export type SessionListResponse = components["schemas"]["SessionListResponse"];
export type WatchlistResponse = components["schemas"]["WatchlistResponse"];
export type WatchlistMembershipResponse =
  components["schemas"]["WatchlistMembershipResponse"];

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

  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await fetcher(`${baseUrl}${path}`, {
      ...init,
      credentials: "include",
      headers: {
        Accept: "application/json",
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...init.headers,
      },
    });
    if (!response.ok) {
      throw new ApiError(
        response.status,
        `API request failed with status ${response.status}`,
      );
    }
    if (response.status === 204) {
      return undefined as T;
    }
    return (await response.json()) as T;
  }

  function jsonRequest<T>(path: string, method: string, body: unknown) {
    return request<T>(path, {
      method,
      body: JSON.stringify(body),
    });
  }

  return {
    register(email: string, password: string) {
      return jsonRequest<AuthResponse>("/api/v1/auth/register", "POST", {
        email,
        password,
      });
    },
    login(email: string, password: string) {
      return jsonRequest<AuthResponse>("/api/v1/auth/login", "POST", {
        email,
        password,
      });
    },
    logout() {
      return request<void>("/api/v1/auth/logout", { method: "POST" });
    },
    getMe() {
      return request<MeResponse>("/api/v1/me");
    },
    getSessions() {
      return request<SessionListResponse>("/api/v1/me/sessions");
    },
    revokeSession(sessionId: string) {
      return request<void>(
        `/api/v1/me/sessions/${encodeURIComponent(sessionId)}`,
        { method: "DELETE" },
      );
    },
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
    getResearchSnapshot(symbol: string) {
      return request<ResearchSnapshotEnvelope>(
        `/api/v1/stocks/${encodeURIComponent(symbol)}/research/snapshot`,
      );
    },
    getResearchObservations(symbol: string, limit = 50) {
      const query = new URLSearchParams({ limit: String(limit) });
      return request<ObservationList>(
        `/api/v1/stocks/${encodeURIComponent(symbol)}/research/observations?${query}`,
      );
    },
    getResearchObservation(symbol: string, observationId: string) {
      return request<ResearchObservation>(
        `/api/v1/stocks/${encodeURIComponent(symbol)}/research/observations/${encodeURIComponent(observationId)}`,
      );
    },
    getAIResearch(symbol: string) {
      return request<AIResearchEnvelope>(
        `/api/v1/stocks/${encodeURIComponent(symbol)}/ai-research`,
      );
    },
    getWatchlists() {
      return request<WatchlistResponse[]>("/api/v1/watchlists");
    },
    createWatchlist(name: string) {
      return jsonRequest<WatchlistResponse>("/api/v1/watchlists", "POST", {
        name,
      });
    },
    addWatchlistItem(watchlistId: string, symbol: string) {
      return jsonRequest<WatchlistResponse>(
        `/api/v1/watchlists/${encodeURIComponent(watchlistId)}/items`,
        "POST",
        { symbol },
      );
    },
    removeWatchlistItem(watchlistId: string, symbol: string) {
      return request<WatchlistResponse>(
        `/api/v1/watchlists/${encodeURIComponent(watchlistId)}/items/${encodeURIComponent(symbol)}`,
        { method: "DELETE" },
      );
    },
    getWatchlistMembership(symbol: string) {
      return request<WatchlistMembershipResponse>(
        `/api/v1/watchlists/membership/${encodeURIComponent(symbol)}`,
      );
    },
  };
}

export type ZhaoniuClient = ReturnType<typeof createZhaoniuClient>;
