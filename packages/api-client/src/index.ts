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
export type PeerComparisonEnvelope =
  components["schemas"]["PeerComparisonEnvelope"];
export type PeerMetricComparisonResponse =
  components["schemas"]["PeerMetricComparisonResponse"];
export type PeerUniverseResponse =
  components["schemas"]["PeerUniverseResponse"];
export type AIResearchOutputDocument =
  components["schemas"]["AIResearchOutputDocument"];
export type StockHealthResearchV1 =
  components["schemas"]["StockHealthResearchV1"];
export type EvidenceIndexEntry = components["schemas"]["EvidenceIndexEntry"];
export type CitedText = components["schemas"]["CitedText"];
export type AuthResponse = components["schemas"]["AuthResponse"];
export type MeResponse = components["schemas"]["MeResponse"];
export type AccessEnvelope = components["schemas"]["AccessEnvelope"];
export type AccessActivationResponse =
  components["schemas"]["AccessActivationResponse"];
export type SessionListResponse = components["schemas"]["SessionListResponse"];
export type WatchlistResponse = components["schemas"]["WatchlistResponse"];
export type WatchlistMembershipResponse =
  components["schemas"]["WatchlistMembershipResponse"];
export type CorporateEventResponse =
  components["schemas"]["CorporateEventResponse"];
export type CorporateEventListResponse =
  components["schemas"]["CorporateEventListResponse"];
export type EventRadarEnvelope = components["schemas"]["EventRadarEnvelope"];
export type EventRadarItemResponse =
  components["schemas"]["EventRadarItemResponse"];
export type ResearchFeedResponse =
  components["schemas"]["ResearchFeedResponse"];
export type FeedSignalResponse = components["schemas"]["FeedSignalResponse"];
export type WatchlistCoverageResponse =
  components["schemas"]["WatchlistCoverageResponse"];
export type AlertListResponse = components["schemas"]["AlertListResponse"];
export type AlertSummaryResponse =
  components["schemas"]["AlertSummaryResponse"];
export type AlertSettingsResponse =
  components["schemas"]["AlertSettingsResponse"];
export type AlertSettingsUpdate = components["schemas"]["AlertSettingsUpdate"];
export type ScreenCatalogResponse =
  components["schemas"]["ScreenCatalogResponse"];
export type ScreenCoverageResponse =
  components["schemas"]["ScreenCoverageResponse"];
export type ScreenCoverageEstimateResponse =
  components["schemas"]["ScreenCoverageEstimateResponse"];
export type ScreenQuery = components["schemas"]["ScreenQuery-Input"];
export type ScreenValidationResponse =
  components["schemas"]["ScreenValidationResponse"];
export type ScreenExecutionResponse =
  components["schemas"]["ScreenExecutionResponse"];
export type ScreenResultListResponse =
  components["schemas"]["ScreenResultListResponse"];
export type ScreenResultItem = components["schemas"]["ScreenResultItem"];
export type NaturalLanguageParseResponse =
  components["schemas"]["NaturalLanguageParseResponse"];
export type NaturalLanguageScreenParseResultV1 =
  components["schemas"]["NaturalLanguageScreenParseResultV1"];
export type SavedScreenResponse = components["schemas"]["SavedScreenResponse"];
export type SavedScreenListResponse =
  components["schemas"]["SavedScreenListResponse"];
export type ScreenExecutionListResponse =
  components["schemas"]["ScreenExecutionListResponse"];

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
  const defaultBaseUrl =
    typeof window === "undefined" ? "http://127.0.0.1:8000" : "";
  const baseUrl = (options.baseUrl ?? defaultBaseUrl)
    .replace(/\/$/, "")
    .replace(/\/api\/v1$/, "");
  const fetcher =
    options.fetcher ??
    ((...arguments_: Parameters<typeof fetch>) => fetch(...arguments_));

  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const csrfToken =
      typeof document === "undefined"
        ? undefined
        : document.cookie
            .split("; ")
            .find((entry) => entry.startsWith("zhaoniu_csrf="))
            ?.split("=")
            .slice(1)
            .join("=");
    const method = (init.method ?? "GET").toUpperCase();
    const mutation = !["GET", "HEAD", "OPTIONS"].includes(method);
    const response = await fetcher(`${baseUrl}${path}`, {
      ...init,
      credentials: "include",
      headers: {
        Accept: "application/json",
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...(mutation && csrfToken
          ? { "X-CSRF-Token": decodeURIComponent(csrfToken) }
          : {}),
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
    register(email: string, password: string, invitationCode: string) {
      return jsonRequest<AuthResponse>("/api/v1/auth/register", "POST", {
        email,
        password,
        invitation_code: invitationCode,
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
    getAccess() {
      return request<AccessEnvelope>("/api/v1/me/access");
    },
    activateAccess(activationCode: string) {
      return jsonRequest<AccessActivationResponse>(
        "/api/v1/me/access/activate",
        "POST",
        { activation_code: activationCode },
      );
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
    getPeers(symbol: string) {
      return request<PeerUniverseResponse>(
        `/api/v1/stocks/${encodeURIComponent(symbol)}/peers`,
      );
    },
    getPeerComparisons(symbol: string, dimension?: string) {
      const query = new URLSearchParams();
      if (dimension) query.set("dimension", dimension);
      const suffix = query.size ? `?${query}` : "";
      return request<PeerComparisonEnvelope>(
        `/api/v1/stocks/${encodeURIComponent(symbol)}/peer-comparisons${suffix}`,
      );
    },
    getEvents(symbol: string, limit = 100) {
      const query = new URLSearchParams({ limit: String(limit) });
      return request<CorporateEventListResponse>(
        `/api/v1/stocks/${encodeURIComponent(symbol)}/events?${query}`,
      );
    },
    getEvent(symbol: string, eventId: string) {
      return request<CorporateEventResponse>(
        `/api/v1/stocks/${encodeURIComponent(symbol)}/events/${encodeURIComponent(eventId)}`,
      );
    },
    getEventRadar(symbol: string) {
      return request<EventRadarEnvelope>(
        `/api/v1/stocks/${encodeURIComponent(symbol)}/event-radar`,
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
    getResearchFeed(
      options: {
        cursor?: string;
        limit?: number;
        sourceKind?: "fundamental" | "peer" | "corporate_event";
        minimumAttention?: "info" | "notice" | "important";
      } = {},
    ) {
      const query = new URLSearchParams({ limit: String(options.limit ?? 40) });
      if (options.cursor) query.set("cursor", options.cursor);
      if (options.sourceKind) query.set("source_kind", options.sourceKind);
      if (options.minimumAttention)
        query.set("minimum_attention", options.minimumAttention);
      return request<ResearchFeedResponse>(`/api/v1/me/research-feed?${query}`);
    },
    getResearchCoverage() {
      return request<WatchlistCoverageResponse>("/api/v1/me/research-coverage");
    },
    getResearchAlerts(limit = 50) {
      return request<AlertListResponse>(
        `/api/v1/me/research-alerts?limit=${limit}`,
      );
    },
    getResearchAlertSummary() {
      return request<AlertSummaryResponse>(
        "/api/v1/me/research-alerts/summary",
      );
    },
    markResearchAlertRead(deliveryId: string) {
      return request<void>(
        `/api/v1/me/research-alerts/${encodeURIComponent(deliveryId)}/read`,
        { method: "POST" },
      );
    },
    markAllResearchAlertsRead() {
      return request<void>("/api/v1/me/research-alerts/read-all", {
        method: "POST",
      });
    },
    getResearchAlertSettings() {
      return request<AlertSettingsResponse>(
        "/api/v1/me/research-alert-settings",
      );
    },
    updateResearchAlertSettings(payload: AlertSettingsUpdate) {
      return jsonRequest<AlertSettingsResponse>(
        "/api/v1/me/research-alert-settings",
        "PUT",
        payload,
      );
    },
    getScreenCatalog() {
      return request<ScreenCatalogResponse>("/api/v1/screens/catalog");
    },
    getScreenCoverage() {
      return request<ScreenCoverageResponse>("/api/v1/screens/coverage");
    },
    estimateScreenCoverage(query: ScreenQuery) {
      return jsonRequest<ScreenCoverageEstimateResponse>(
        "/api/v1/screens/coverage/estimate",
        "POST",
        query,
      );
    },
    validateScreen(query: ScreenQuery) {
      return jsonRequest<ScreenValidationResponse>(
        "/api/v1/screens/validate",
        "POST",
        query,
      );
    },
    createScreenExecution(
      query: ScreenQuery,
      options: { savedScreenId?: string; confirmedParseRunId?: string } = {},
    ) {
      return jsonRequest<ScreenExecutionResponse>(
        "/api/v1/screens/executions",
        "POST",
        {
          query,
          saved_screen_id: options.savedScreenId,
          confirmed_parse_run_id: options.confirmedParseRunId,
        },
      );
    },
    getScreenExecutions(limit = 20) {
      return request<ScreenExecutionListResponse>(
        `/api/v1/screens/executions?limit=${limit}`,
      );
    },
    getScreenExecution(executionId: string) {
      return request<ScreenExecutionResponse>(
        `/api/v1/screens/executions/${encodeURIComponent(executionId)}`,
      );
    },
    getScreenResults(executionId: string, cursor?: string, limit = 40) {
      const query = new URLSearchParams({ limit: String(limit) });
      if (cursor) query.set("cursor", cursor);
      return request<ScreenResultListResponse>(
        `/api/v1/screens/executions/${encodeURIComponent(executionId)}/results?${query}`,
      );
    },
    createNaturalLanguageScreenParse(text: string) {
      return jsonRequest<NaturalLanguageParseResponse>(
        "/api/v1/screens/natural-language/parses",
        "POST",
        { text },
      );
    },
    getNaturalLanguageScreenParse(parseRunId: string) {
      return request<NaturalLanguageParseResponse>(
        `/api/v1/screens/natural-language/parses/${encodeURIComponent(parseRunId)}`,
      );
    },
    getSavedScreens() {
      return request<SavedScreenListResponse>("/api/v1/screens/saved");
    },
    createSavedScreen(payload: {
      name: string;
      description?: string;
      query: ScreenQuery;
      sourceParseRunId?: string;
      originalText?: string;
    }) {
      return jsonRequest<SavedScreenResponse>("/api/v1/screens/saved", "POST", {
        name: payload.name,
        description: payload.description,
        query: payload.query,
        source_parse_run_id: payload.sourceParseRunId,
        original_text: payload.originalText,
      });
    },
    updateSavedScreen(
      savedScreenId: string,
      payload: { name?: string; description?: string; query?: ScreenQuery },
    ) {
      return jsonRequest<SavedScreenResponse>(
        `/api/v1/screens/saved/${encodeURIComponent(savedScreenId)}`,
        "PATCH",
        payload,
      );
    },
    deleteSavedScreen(savedScreenId: string) {
      return request<void>(
        `/api/v1/screens/saved/${encodeURIComponent(savedScreenId)}`,
        { method: "DELETE" },
      );
    },
  };
}

export type ZhaoniuClient = ReturnType<typeof createZhaoniuClient>;
