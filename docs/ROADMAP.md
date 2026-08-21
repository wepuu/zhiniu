# Product Roadmap

## Phase 0 - Foundation

Monorepo, responsive design system, versioned API, auth seam, repository/provider/LLM contracts,
database migration, Celery foundation, quality commands, Docker services, and architecture docs.

## Phase 1 - Real A-share Market Data

Canonical stock master, symbol resolver, AKShare development adapter, unadjusted daily bars,
provenance, idempotent sync, PostgreSQL repositories, generated OpenAPI types, and real stock page.

## Phase 2 - Financial Data & Fundamental Research

Immutable financial-report revisions, disclosure-aware availability, typed statement facts,
deterministic fundamental metrics, historical valuation observations, applicability states,
research APIs, and separately composed desktop/mobile financial workspaces.

## Phase 3 - Change Engine, Evidence & Research Snapshots

Historical metric points, versioned deterministic change rules, evidence references, immutable
research snapshots, queryable build runs, stock research APIs, and desktop/mobile evidence flows.

## Phase 4 - Multi-provider AI Stock Health Research

Evidence-bound structured stock-health interpretation, deterministic context selection, stable
citations, LiteLLM SDK routing, automatic failover, immutable outputs, call audit, and separately
composed desktop/mobile AI research states. LLMs never calculate or restate financial numbers.

## Phase 5 - Multi-user Watchlist & Auth

Email/password sessions, HttpOnly cookie authentication, ownership enforcement, persisted watchlist
groups, minimal internal-beta quotas, session listing/revocation, and desktop/mobile watchlist UX.
Personalized research feeds, production account lifecycle, email verification, password reset, paid
plans and public launch compliance remain deferred.

## Phase 6 - Industry & Peer Benchmark Research

Industry taxonomy as a first-class domain, deterministic peer universe resolution, cross-sectional
benchmark snapshots, company peer metric positions, peer evidence, read-only peer APIs, and
desktop/mobile peer-position cards. Personalized feeds, event radar, bank/financial templates,
report-specific AI interpretation and stock-picking workflows remain deferred.

## Phase 7 - Corporate Disclosure & Event Radar

Disclosure metadata ingestion, deterministic four-family taxonomy, staged structured facts,
immutable event versions, point-in-time radar snapshots, neutral attention rules, evidence APIs and
separately verified desktop/mobile event-radar flows. News, source-conflict fusion and expanded event
families remain deferred.

## Phase 8 - Personalized Research Feed & In-App Research Alerts

Global deterministic research-signal projection from Phase 3, 6 and 7 artifacts; watchlist-scoped
14-day research feed with anchored cursor ordering; per-source coverage; CSRF-protected alert
preferences; and idempotent in-app delivery only for signals known after watchlist membership.
Email, digest schedules, quiet hours and push channels remain deferred.

## Phase 9 - Deterministic Research Screening

Versioned allow-listed query DSL, immutable point-in-time screening snapshots, user-owned
idempotent executions, evidence-linked results, background tasks and separately composed
desktop/mobile discovery workflows.

## Phase 10 - Natural Language Research Screening & Saved Research

Policy-gated natural-language-to-DSL candidate parsing, deterministic grounding and explicit
confirmation, truthful per-query coverage, user-owned saved screens, rerunnable provenance and
desktop/mobile research workspaces. OR/NOT groups, shared screen templates, alerts from saved
screens, company comparison, report export and broader professional workspace expansion remain
deferred.

## Phase 11 - Invitation Access & Advanced Feature Activation

Invitation-only registration, immutable plan versions, backend-resolved feature access,
operator-issued user-bound activation codes, calendar validity, production approval gates and
desktop/mobile account-access states. Payment, checkout, public pricing, orders, refunds, webhooks,
The product deliberately has no payment, price, order or checkout surface.

## Phase 12 - Controlled Beta Production Readiness

Email verification, password recovery with global session revocation, versioned legal acceptance,
production-safe configuration, liveness/readiness probes, structured request logging, container
packaging, backup/restore drills and an explicit controlled-Beta release gate. Automated data-rights
workflows and public launch remain deferred.

## Phase 13 - Beta Learning & Research Coverage Operations

Immutable priority-universe and research-coverage snapshots, explicit availability/freshness/source
health axes, deterministic allow-listed gap planning, operator-triggered bounded backfill with
leases and auditable item outcomes, structured in-product Beta feedback, and aggregate 7/30-day
learning reports with small-cell suppression. There is no scheduled full-market backfill, automatic
AI generation, behavioral telemetry, research score, or public launch expansion.

## Phase 14 - Operations Console & Production Provider Readiness

Internal role-based operations console, password-confirmed high-risk actions, immutable operator
audit, exact account support lookup, coverage and AI job dispatch, provider health diagnostics,
Resend background delivery/webhook lifecycle, and explicit DeepSeek structured-output capability
modes. The console is not a general admin CRUD system and does not expose provider secrets,
passwords, tokens, raw prompts, private screening text, or unrestricted database access.

## Phase 15 - Automated Research Operations & Scheduling (current)

Database-owned automation policies and immutable revisions, a single Celery Beat tick, frozen
priority-universe runs, allow-listed symbol/industry/run steps, change-aware downstream rebuilds,
leases and resumable failures, automatic signal and in-app alert projection, an optional bounded AI
lane, and a desktop-first operations workspace. Full-market screening schedules, free-form cron,
user schedules, exchange-calendar semantics and automated marketing email remain deferred.

## Future - Factor / Backtest

Versioned factor definitions and research simulations remain a future phase. They require
backtest-grade point-in-time datasets and survivorship-bias controls before product work starts.
