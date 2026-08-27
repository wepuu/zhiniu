from datetime import UTC, date, datetime
from typing import Annotated, Literal
from uuid import UUID

from celery import Celery  # type: ignore[import-untyped]
from fastapi import APIRouter, Cookie, HTTPException, Query, Request, Response, status

from zhaoniu_api.access_control.rate_limit import (
    AccessRateLimitExceeded,
    enforce_access_rate_limit,
)
from zhaoniu_api.ai_research.models import AIResearchEnvelope
from zhaoniu_api.auth.service import AuthenticationError
from zhaoniu_api.config import get_settings
from zhaoniu_api.dependencies import (
    AccessControlServiceDependency,
    AIResearchServiceDependency,
    AuthServiceDependency,
    AutomationServiceDependency,
    CSRFSafe,
    CurrentUser,
    CurrentUserId,
    DailyBarRepo,
    FundamentalService,
    PeerResearchServiceDependency,
    ResearchService,
    StockReadinessServiceDependency,
    StockRepo,
    WatchlistRepo,
)
from zhaoniu_api.domain.models import Watchlist, resolve_symbol
from zhaoniu_api.legal import LEGAL_DOCUMENTS
from zhaoniu_api.peer_research.models import (
    PeerComparisonEnvelope,
    PeerUniverseResponse,
)
from zhaoniu_api.research.models import (
    ObservationList,
    ResearchObservation,
    ResearchSnapshotEnvelope,
)
from zhaoniu_api.schemas import (
    AddWatchlistItemRequest,
    AuthRequest,
    AuthResponse,
    CreateWatchlistRequest,
    DailyBarListResponse,
    DailyBarResponse,
    EmailVerificationRequest,
    EmailVerificationResponse,
    EntitlementsResponse,
    FinancialPeriodListResponse,
    FinancialPeriodResponse,
    FundamentalDimensionResponse,
    FundamentalMetricResponse,
    FundamentalResearchResponse,
    HealthResponse,
    LegalAcceptanceBatchRequest,
    LegalAcceptanceStatusResponse,
    LegalDocumentListResponse,
    LegalDocumentResponse,
    MeResponse,
    OperationAcceptedResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RegistrationRequest,
    SessionListResponse,
    SessionResponse,
    StockPreparationResponse,
    StockReadinessListResponse,
    StockResponse,
    StockSearchResponse,
    UserResponse,
    ValuationCoverageResponse,
    ValuationListResponse,
    ValuationObservationResponse,
    WatchlistMembershipResponse,
    WatchlistResponse,
)

_DIMENSIONS = {
    "growth": "成长",
    "profitability": "盈利能力",
    "quality": "经营质量",
    "balance": "资产负债",
    "valuation": "估值",
}
_VALUATION_CODES = {"pe_ttm", "pb", "pcf", "market_cap"}
router = APIRouter(prefix="/api/v1")


def _dispatch_automation_run(run_id: UUID) -> None:
    settings = get_settings()
    Celery(
        "zhaoniu-watchlist-preparation",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
    ).send_task("automation.execute_run", args=[str(run_id)])


@router.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="zhaoniu-api", version="0.1.0")


@router.post(
    "/auth/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["auth"],
)
async def register(
    payload: RegistrationRequest,
    request: Request,
    response: Response,
    auth: AuthServiceDependency,
    access: AccessControlServiceDependency,
) -> AuthResponse:
    settings = get_settings()
    client_host = request.client.host if request.client else "unknown"
    registration_identity = f"{client_host}:{payload.email.strip().lower()}"
    try:
        await enforce_access_rate_limit(
            settings,
            scope="register",
            identity=registration_identity,
        )
    except AccessRateLimitExceeded as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="registration_temporarily_unavailable",
        ) from error
    try:
        session = await auth.register(
            email=payload.email,
            password=payload.password,
            invitation_code=payload.invitation_code,
            legal_acceptances={
                item.document_type: item.document_version for item in payload.legal_acceptances
            },
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    except AuthenticationError as error:
        code = str(error)
        if code in {"email_already_registered", "beta_capacity_reached"}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=code) from error
        if code == "invalid_or_unavailable_invitation":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=code
            ) from error
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=code,
        ) from error
    set_session_cookies(response, session.token, session.csrf_token, auth.session_max_age_seconds)
    return AuthResponse(
        user=UserResponse.from_domain(session.user),
        entitlements=EntitlementsResponse.model_validate(
            (await access.effective_entitlements(session.user.id)).model_dump()
        ),
    )


@router.post("/auth/login", response_model=AuthResponse, tags=["auth"])
async def login(
    payload: AuthRequest,
    request: Request,
    response: Response,
    auth: AuthServiceDependency,
    access: AccessControlServiceDependency,
) -> AuthResponse:
    try:
        session = await auth.login(
            email=payload.email,
            password=payload.password,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    except AuthenticationError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_credentials",
        ) from error
    set_session_cookies(response, session.token, session.csrf_token, auth.session_max_age_seconds)
    return AuthResponse(
        user=UserResponse.from_domain(session.user),
        entitlements=EntitlementsResponse.model_validate(
            (await access.effective_entitlements(session.user.id)).model_dump()
        ),
    )


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT, tags=["auth"])
async def logout(
    response: Response,
    auth: AuthServiceDependency,
    _csrf: CSRFSafe,
    token: Annotated[str | None, Cookie(alias="zhaoniu_session")] = None,
) -> Response:
    await auth.logout(token)
    clear_session_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=MeResponse, tags=["auth"])
async def get_me(
    user: CurrentUser,
    access: AccessControlServiceDependency,
    auth: AuthServiceDependency,
) -> MeResponse:
    return MeResponse(
        user=UserResponse.from_domain(user),
        entitlements=EntitlementsResponse.model_validate(
            (await access.effective_entitlements(user.id)).model_dump()
        ),
        required_legal_acceptances=await auth.required_legal_acceptances(user.id),
    )


@router.post(
    "/auth/email-verification/verify",
    response_model=EmailVerificationResponse,
    tags=["auth"],
)
async def verify_email(
    payload: EmailVerificationRequest, auth: AuthServiceDependency
) -> EmailVerificationResponse:
    try:
        result = await auth.verify_email(payload.token)
        return EmailVerificationResponse(status=result)  # type: ignore[arg-type]
    except AuthenticationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error


@router.post(
    "/auth/email-verification/resend",
    response_model=EmailVerificationResponse,
    tags=["auth"],
)
async def resend_email_verification(
    request: Request,
    _csrf: CSRFSafe,
    user_id: CurrentUserId,
    auth: AuthServiceDependency,
) -> EmailVerificationResponse:
    try:
        await enforce_access_rate_limit(
            get_settings(),
            scope="email_verification",
            identity=f"{user_id}:{request.client.host if request.client else 'unknown'}",
            limit=3,
            window_seconds=900,
        )
        result = await auth.resend_verification(user_id)
        return EmailVerificationResponse(status=result)  # type: ignore[arg-type]
    except AccessRateLimitExceeded as error:
        raise HTTPException(status_code=429, detail="email_verification_rate_limited") from error


@router.post(
    "/auth/password-reset/request",
    response_model=OperationAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["auth"],
)
async def request_password_reset(
    payload: PasswordResetRequest, request: Request, auth: AuthServiceDependency
) -> OperationAcceptedResponse:
    client_host = request.client.host if request.client else "unknown"
    try:
        await enforce_access_rate_limit(
            get_settings(),
            scope="password_reset_request",
            identity=f"{client_host}:{payload.email.lower()}",
            limit=3,
            window_seconds=900,
        )
    except AccessRateLimitExceeded:
        return OperationAcceptedResponse(status="accepted")
    await auth.request_password_reset(payload.email)
    return OperationAcceptedResponse(status="accepted")


@router.post(
    "/auth/password-reset/confirm",
    response_model=OperationAcceptedResponse,
    tags=["auth"],
)
async def confirm_password_reset(
    payload: PasswordResetConfirmRequest, auth: AuthServiceDependency
) -> OperationAcceptedResponse:
    try:
        await auth.confirm_password_reset(payload.token, payload.new_password)
    except AuthenticationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error
    return OperationAcceptedResponse(status="completed")


@router.get("/legal/current", response_model=LegalDocumentListResponse, tags=["legal"])
async def current_legal_documents() -> LegalDocumentListResponse:
    return LegalDocumentListResponse(
        items=[
            LegalDocumentResponse(
                document_type=item.document_type,
                version=item.version,
                title=item.title,
                path=item.path,
                content_hash=item.content_hash,
                required_at_registration=item.required_at_registration,
            )
            for item in LEGAL_DOCUMENTS
        ]
    )


@router.post(
    "/me/legal-acceptances",
    response_model=LegalAcceptanceStatusResponse,
    tags=["legal"],
)
async def accept_legal_documents(
    payload: LegalAcceptanceBatchRequest,
    _csrf: CSRFSafe,
    user_id: CurrentUserId,
    auth: AuthServiceDependency,
) -> LegalAcceptanceStatusResponse:
    try:
        remaining = await auth.accept_legal_documents(
            user_id,
            {item.document_type: item.document_version for item in payload.items},
        )
    except AuthenticationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error
    return LegalAcceptanceStatusResponse(required_document_types=remaining)


@router.get("/me/sessions", response_model=SessionListResponse, tags=["auth"])
async def list_sessions(
    user: CurrentUser,
    auth: AuthServiceDependency,
    token: Annotated[str | None, Cookie(alias="zhaoniu_session")] = None,
) -> SessionListResponse:
    sessions = await auth.list_sessions(user.id, token)
    items = [SessionResponse.from_domain(item) for item in sessions]
    return SessionListResponse(items=items, total=len(items))


@router.delete(
    "/me/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["auth"],
)
async def revoke_session(
    session_id: UUID,
    _csrf: CSRFSafe,
    user_id: CurrentUserId,
    auth: AuthServiceDependency,
) -> Response:
    revoked = await auth.revoke_session(user_id, session_id)
    if not revoked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/stocks/search", response_model=StockSearchResponse, tags=["stocks"])
async def search_stocks(
    repository: StockRepo,
    q: Annotated[str, Query(min_length=1, max_length=40)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> StockSearchResponse:
    stocks = await repository.search(q, limit)
    items = [StockResponse.from_domain(stock) for stock in stocks]
    return StockSearchResponse(items=items, total=len(items))


@router.get(
    "/stocks/readiness",
    response_model=StockReadinessListResponse,
    tags=["stocks"],
)
async def get_stock_readiness(
    symbols: Annotated[str, Query(min_length=1, max_length=600)],
    _user_id: CurrentUserId,
    service: StockReadinessServiceDependency,
) -> StockReadinessListResponse:
    requested = [item.strip() for item in symbols.split(",") if item.strip()]
    if not requested or len(requested) > 30:
        raise HTTPException(status_code=422, detail="stock_readiness_symbol_limit")
    try:
        return StockReadinessListResponse(items=await service.get_many(requested))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post(
    "/stocks/{symbol}/preparation",
    response_model=StockPreparationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["stocks"],
)
async def request_stock_preparation(
    symbol: str,
    _csrf: CSRFSafe,
    user_id: CurrentUserId,
    watchlists: WatchlistRepo,
    automation: AutomationServiceDependency,
) -> StockPreparationResponse:
    canonical = resolve_symbol(symbol).canonical
    owned_lists = await watchlists.list_for_user(user_id)
    if not any(item.symbol == canonical for group in owned_lists for item in group.items):
        raise HTTPException(status_code=403, detail="stock_not_in_watchlist")
    settings = get_settings()
    if settings.automation_hard_disabled or not settings.watchlist_preparation_enabled:
        return StockPreparationResponse(
            symbol=canonical.split(".", 1)[0],
            canonical_symbol=canonical,
            status="paused",
            reason_code="preparation_disabled",
        )
    try:
        await enforce_access_rate_limit(
            settings,
            scope="watchlist-preparation-retry",
            identity=f"{user_id}:{canonical}",
            limit=1,
            window_seconds=1800,
        )
        await enforce_access_rate_limit(
            settings,
            scope="watchlist-preparation-daily",
            identity=str(user_id),
            limit=settings.watchlist_preparation_daily_limit,
            window_seconds=86400,
        )
    except AccessRateLimitExceeded as error:
        raise HTTPException(status_code=429, detail="stock_preparation_rate_limited") from error
    preparation_status, result = await automation.request_watchlist_preparation(canonical)
    if result is not None and result.status == "accepted":
        try:
            _dispatch_automation_run(result.run_id)
        except Exception:
            pass
    return StockPreparationResponse(
        symbol=canonical.split(".", 1)[0],
        canonical_symbol=canonical,
        status=preparation_status,
        run_id=result.run_id if result is not None else None,
        reason_code="preparation_disabled" if preparation_status == "paused" else None,
    )


@router.get("/stocks/{symbol}", response_model=StockResponse, tags=["stocks"])
async def get_stock(symbol: str, repository: StockRepo) -> StockResponse:
    stock = await repository.get(symbol)
    if stock is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")
    return StockResponse.from_domain(stock)


@router.get("/stocks/{symbol}/daily-bars", response_model=DailyBarListResponse, tags=["stocks"])
async def get_daily_bars(
    symbol: str,
    stocks: StockRepo,
    bars: DailyBarRepo,
    start: date | None = None,
    end: date | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 120,
    adjust: Literal["none"] = "none",
) -> DailyBarListResponse:
    stock = await stocks.get(symbol)
    if stock is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")
    resolved = resolve_symbol(symbol)
    records = await bars.list_for_symbol(resolved.canonical, start=start, end=end, limit=limit)
    items = [
        DailyBarResponse(
            trade_date=bar.trade_date,
            adjust_type=bar.adjust_type,
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            pre_close=bar.pre_close,
            volume=bar.volume,
            amount=bar.amount,
            pct_change=bar.pct_change,
            source=bar.source,
            collected_at=bar.collected_at,
        )
        for bar in records
    ]
    return DailyBarListResponse(
        symbol=resolved.ticker,
        canonical_symbol=resolved.canonical,
        adjust=adjust,
        items=items,
        total=len(items),
    )


@router.get(
    "/stocks/{symbol}/research/fundamentals",
    response_model=FundamentalResearchResponse,
    tags=["fundamentals"],
)
async def get_fundamental_research(
    symbol: str,
    stocks: StockRepo,
    service: FundamentalService,
    as_of: datetime | None = None,
) -> FundamentalResearchResponse:
    stock = await stocks.get(symbol)
    if stock is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")
    effective_as_of = as_of or datetime.now(UTC)
    if effective_as_of.tzinfo is None:
        effective_as_of = effective_as_of.replace(tzinfo=UTC)
    reports = await service.list_reports(symbol, as_of=effective_as_of, limit=64)
    snapshot = await service.get_snapshot(symbol, as_of=as_of)
    latest = max(reports, key=lambda item: item.period_end, default=None)
    grouped: dict[str, list[FundamentalMetricResponse]] = {code: [] for code in _DIMENSIONS}
    for metric in snapshot.metrics:
        response = FundamentalMetricResponse.from_domain(metric)
        grouped[response.dimension].append(response)
    freshness = "unavailable"
    if latest is not None:
        freshness = (
            "stale" if (effective_as_of.date() - latest.period_end).days > 240 else "current"
        )
    return FundamentalResearchResponse(
        symbol=stock.symbol,
        canonical_symbol=stock.canonical_symbol or resolve_symbol(stock.symbol).canonical,
        as_of=effective_as_of,
        latest_report_period=latest.period_end if latest else None,
        latest_report_published_at=latest.published_at if latest else None,
        published_at_precision=latest.published_at_precision if latest else None,
        issuer_type=latest.issuer_type if latest else stock.issuer_type,
        provider=latest.provider if latest else None,
        data_version=snapshot.data_version,
        metric_definition_version=snapshot.metric_version,
        freshness=freshness,
        dimensions=[
            FundamentalDimensionResponse(code=code, display_name=name, items=grouped[code])
            for code, name in _DIMENSIONS.items()
        ],
    )


@router.get(
    "/stocks/{symbol}/research/snapshot",
    response_model=ResearchSnapshotEnvelope,
    tags=["research"],
)
async def get_research_snapshot(
    symbol: str,
    stocks: StockRepo,
    service: ResearchService,
) -> ResearchSnapshotEnvelope:
    if await stocks.get(symbol) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")
    snapshot = await service.latest_snapshot(symbol)
    return ResearchSnapshotEnvelope(
        status="ready" if snapshot else "not_built",
        snapshot=snapshot,
    )


@router.get(
    "/stocks/{symbol}/ai-research",
    response_model=AIResearchEnvelope,
    tags=["ai-research"],
)
async def get_ai_research(
    symbol: str,
    stocks: StockRepo,
    service: AIResearchServiceDependency,
) -> AIResearchEnvelope:
    if await stocks.get(symbol) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")
    return await service.get_stock_health(symbol)


@router.get(
    "/stocks/{symbol}/peers",
    response_model=PeerUniverseResponse,
    tags=["peer-research"],
)
async def get_stock_peers(
    symbol: str,
    stocks: StockRepo,
    service: PeerResearchServiceDependency,
    as_of: datetime | None = None,
) -> PeerUniverseResponse:
    if await stocks.get(symbol) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")
    return await service.get_peers(symbol, as_of=as_of)


@router.get(
    "/stocks/{symbol}/peer-comparisons",
    response_model=PeerComparisonEnvelope,
    tags=["peer-research"],
)
async def get_stock_peer_comparisons(
    symbol: str,
    stocks: StockRepo,
    service: PeerResearchServiceDependency,
    dimension: Literal["growth", "profitability", "quality", "balance", "valuation"] | None = None,
) -> PeerComparisonEnvelope:
    if await stocks.get(symbol) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")
    return await service.get_peer_comparisons(symbol, dimension=dimension)


@router.get(
    "/stocks/{symbol}/research/observations",
    response_model=ObservationList,
    tags=["research"],
)
async def list_research_observations(
    symbol: str,
    stocks: StockRepo,
    service: ResearchService,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ObservationList:
    if await stocks.get(symbol) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")
    return await service.list_observations(symbol, limit=limit)


@router.get(
    "/stocks/{symbol}/research/observations/{observation_id}",
    response_model=ResearchObservation,
    tags=["research"],
)
async def get_research_observation(
    symbol: str,
    observation_id: UUID,
    stocks: StockRepo,
    service: ResearchService,
) -> ResearchObservation:
    if await stocks.get(symbol) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")
    observation = await service.get_observation(symbol, observation_id)
    if observation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research observation not found",
        )
    return observation


@router.get(
    "/stocks/{symbol}/financials/periods",
    response_model=FinancialPeriodListResponse,
    tags=["fundamentals"],
)
async def get_financial_periods(
    symbol: str,
    stocks: StockRepo,
    service: FundamentalService,
    as_of: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=40)] = 12,
) -> FinancialPeriodListResponse:
    stock = await stocks.get(symbol)
    if stock is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")
    effective_as_of = as_of
    if effective_as_of is not None and effective_as_of.tzinfo is None:
        effective_as_of = effective_as_of.replace(tzinfo=UTC)
    reports = await service.list_reports(symbol, as_of=effective_as_of, limit=limit)
    items = [FinancialPeriodResponse.from_domain(item) for item in reports]
    return FinancialPeriodListResponse(
        symbol=stock.symbol,
        canonical_symbol=stock.canonical_symbol or resolve_symbol(stock.symbol).canonical,
        items=items,
        total=len(items),
    )


@router.get(
    "/stocks/{symbol}/valuations",
    response_model=ValuationListResponse,
    tags=["fundamentals"],
)
async def get_valuations(
    symbol: str,
    stocks: StockRepo,
    service: FundamentalService,
    start: date | None = None,
    end: date | None = None,
    metrics: str | None = None,
    limit: Annotated[int, Query(ge=1, le=10000)] = 4000,
) -> ValuationListResponse:
    stock = await stocks.get(symbol)
    if stock is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")
    requested_codes = (
        tuple(item.strip() for item in metrics.split(",") if item.strip()) if metrics else None
    )
    if requested_codes and not set(requested_codes).issubset(_VALUATION_CODES):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported valuation metric",
        )
    observations = await service.list_valuations(
        symbol,
        start=start,
        end=end,
        metric_codes=requested_codes,
        limit=limit,
    )
    dates = [item.trade_date for item in observations]
    return ValuationListResponse(
        symbol=stock.symbol,
        canonical_symbol=stock.canonical_symbol or resolve_symbol(stock.symbol).canonical,
        items=[ValuationObservationResponse.from_domain(item) for item in observations],
        total=len(observations),
        coverage=ValuationCoverageResponse(
            start=min(dates, default=None),
            end=max(dates, default=None),
            sample_count=len(observations),
            metric_codes=sorted({item.metric_code for item in observations}),
        ),
    )


@router.get("/watchlists", response_model=list[WatchlistResponse], tags=["watchlists"])
async def list_watchlists(
    user_id: CurrentUserId, repository: WatchlistRepo
) -> list[WatchlistResponse]:
    return [WatchlistResponse.from_domain(item) for item in await repository.list_for_user(user_id)]


@router.post(
    "/watchlists",
    response_model=WatchlistResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["watchlists"],
)
async def create_watchlist(
    payload: CreateWatchlistRequest,
    _csrf: CSRFSafe,
    user_id: CurrentUserId,
    repository: WatchlistRepo,
    access: AccessControlServiceDependency,
) -> WatchlistResponse:
    lists = await repository.list_for_user(user_id)
    entitlements = await access.effective_entitlements(user_id)
    if len(lists) >= entitlements.limits["watchlist_groups"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="watchlist_group_limit_reached",
        )
    item = await repository.create(Watchlist(user_id=user_id, name=payload.name))
    return WatchlistResponse.from_domain(item)


@router.post(
    "/watchlists/{watchlist_id}/items",
    response_model=WatchlistResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["watchlists"],
)
async def add_watchlist_item(
    watchlist_id: UUID,
    payload: AddWatchlistItemRequest,
    _csrf: CSRFSafe,
    user_id: CurrentUserId,
    stocks: StockRepo,
    repository: WatchlistRepo,
    access: AccessControlServiceDependency,
    automation: AutomationServiceDependency,
) -> WatchlistResponse:
    stock = await stocks.get(payload.symbol)
    if stock is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")
    await enforce_watchlist_membership_limit(
        repository,
        user_id,
        payload.symbol,
        (await access.effective_entitlements(user_id)).limits["watchlist_memberships_total"],
    )
    item = await repository.get_owned(watchlist_id, user_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Watchlist not found")
    item.add(resolve_symbol(payload.symbol).canonical)
    saved = await repository.save(item)
    try:
        preparation_status, preparation = await automation.request_watchlist_preparation(
            resolve_symbol(payload.symbol).canonical
        )
        if preparation_status == "queued" and preparation is not None:
            _dispatch_automation_run(preparation.run_id)
    except Exception:
        # Membership persistence is authoritative; the database tick recovers pending work.
        pass
    return WatchlistResponse.from_domain(saved)


@router.delete(
    "/watchlists/{watchlist_id}/items/{symbol}",
    response_model=WatchlistResponse,
    tags=["watchlists"],
)
async def remove_watchlist_item(
    watchlist_id: UUID,
    symbol: str,
    _csrf: CSRFSafe,
    user_id: CurrentUserId,
    repository: WatchlistRepo,
) -> WatchlistResponse:
    item = await repository.get_owned(watchlist_id, user_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Watchlist not found")
    try:
        resolved = resolve_symbol(symbol).canonical
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid symbol",
        ) from error
    item.remove(resolved)
    return WatchlistResponse.from_domain(await repository.save(item))


@router.get(
    "/watchlists/membership/{symbol}",
    response_model=WatchlistMembershipResponse,
    tags=["watchlists"],
)
async def get_watchlist_membership(
    symbol: str,
    user_id: CurrentUserId,
    repository: WatchlistRepo,
) -> WatchlistMembershipResponse:
    try:
        canonical = resolve_symbol(symbol).canonical
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid symbol",
        ) from error
    lists = await repository.list_for_user(user_id)
    watchlist_ids = [
        item.id for item in lists if any(child.symbol == canonical for child in item.items)
    ]
    return WatchlistMembershipResponse(
        symbol=canonical,
        watchlist_ids=watchlist_ids,
        is_member=bool(watchlist_ids),
    )


def set_session_cookies(response: Response, token: str, csrf_token: str, max_age: int) -> None:
    settings = get_settings()
    response.set_cookie(
        settings.auth_cookie_name,
        token,
        max_age=max_age,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        settings.auth_csrf_cookie_name,
        csrf_token,
        max_age=max_age,
        httponly=False,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(settings.auth_cookie_name, path="/")
    response.delete_cookie(settings.auth_csrf_cookie_name, path="/")


async def enforce_watchlist_membership_limit(
    repository: WatchlistRepo, user_id: UUID, symbol: str, limit: int
) -> None:
    resolved = resolve_symbol(symbol).canonical
    lists = await repository.list_for_user(user_id)
    if any(child.symbol == resolved for item in lists for child in item.items):
        return
    total_memberships = sum(len(item.items) for item in lists)
    if total_memberships >= limit:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="watchlist_membership_limit_reached",
        )
