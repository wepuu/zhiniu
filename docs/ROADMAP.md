# Product Roadmap

本文件记录能力演进，不代表发布批准。Phase 0-18 的实现均已进入仓库；受控 Beta 和生产
发布仍必须分别通过工程、数据授权、法律、Provider 与运营门禁。

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

## Phase 14 - Operations Console & Production Provider Readiness (implemented)

Internal role-based operations console, password-confirmed high-risk actions, immutable operator
audit, exact account support lookup, coverage and AI job dispatch, provider health diagnostics,
Resend background delivery/webhook lifecycle, and explicit DeepSeek structured-output capability
modes. The console is not a general admin CRUD system and does not expose provider secrets,
passwords, tokens, raw prompts, private screening text, or unrestricted database access.

## Phase 15 - Automated Research Operations & Scheduling (implemented)

Database-owned automation policies and immutable revisions, a single Celery Beat tick, frozen
priority-universe runs, allow-listed symbol/industry/run steps, change-aware downstream rebuilds,
leases and resumable failures, automatic signal and in-app alert projection, an optional bounded AI
lane, and a desktop-first operations workspace. Full-market screening schedules, free-form cron,
user schedules, exchange-calendar semantics and automated marketing email remain deferred.

## Phase 16 - Company Research Timeline & Event Engine V2 (implemented)

A company-level, point-in-time research timeline over retained fundamental, peer and corporate-event
signals; stable frozen cursors; separately hydrated upcoming events and event threads; explicit
historical alert safety; and deterministic shareholder-change and litigation/arbitration event
families. Timeline facts remain global projections with one upstream artifact. News, LLM fact
extraction, event scoring, cross-domain event ratios and additional event families remain deferred.

## Phase 17 - DeepSeek Production Enablement & Evidence-Grounded Research Assistant (implemented)

A bounded DeepSeek production profile and four evidence-grounded research questions inside the
existing AI interpretation experience. User-owned request wrappers, atomic daily entitlements,
shared run/output deduplication, strict structured validation, explicit retry, provider diagnostics
and desktop/mobile evidence navigation are included. Free-form chat, tools, streaming, price
questions, automated full-market generation and personalized advice remain out of scope.

## Phase 18 - Evidence-Grounded Pairwise Company Comparison (implemented; readiness hardening pending)

User-owned comparison requests over global immutable pair snapshots, strict point-in-time metric
comparability, explicit cross-industry and missing-data limits, recent research-signal context,
saved comparison definitions, and an independently gated DeepSeek explanation after deterministic
facts. Desktop uses a two-column ledger and mobile uses dimension cards with the same evidence
identities. Rankings, winners, scores, segment inference, LLM calculations, scheduling, exports and
multi-company comparison remain out of scope.

## Phase 19 - Launch Baseline & Core Loop Stabilization (internal baseline accepted)

ORM and migration metadata alignment, deterministic stock search by code or Chinese name, shared
global/watchlist stock selection, company-timeline latest-version projection, and independent
desktop/mobile Chromium acceptance. The controlled non-production Resend lifecycle and a current
backup/restore drill are implemented. Container build/startup and the restore drill pass locally;
the Resend draft is configured for `info@zhiniu.cc` but its real delivery loop was explicitly
deferred on 2026-08-25 until a verified public domain is available. The internal engineering and
core-research baseline is accepted with that exception. Transactional email remains a fail-closed
invited-Beta and production-release gate.

## Phase 20 - Provider & Beta Data Acceptance (implemented, baseline blocked)

The operator console and CLI now create immutable acceptance runs for `600519`, `300750`,
`300376`, and `000001`. Each run retains per-dataset counts, freshness, reason codes, bounded
manifests, and evidence fingerprints. Mandatory retained-data failures determine the technical
status; source-usage policy independently determines Beta eligibility. The first local baseline is
correctly blocked by incomplete `600519` daily-bar history and the development-only AKShare usage
scope. Missing `300376` industry lineage and structured DeepSeek workload evidence remain visible
non-mandatory gaps. Transactional email remains deferred and outside Phase 20 execution.

## Phase 21 - Invite Beta Operational Loop (implemented, launch blocked)

Email-bound cohorts, fail-closed approval and dispatch gates, one-time invitation registration,
delivery/registration/verification/first-value funnel facts, operator pause/close controls, and a
fact-backed user onboarding checklist are implemented. The current environment must not send an
external invitation until a passing Beta-eligible Phase 20 run and a published, healthy real
Resend configuration exist. Draft creation and gate inspection remain available for internal
acceptance without simulating approval.

## Phase 22 - Production Release Gate (implemented, release not executed)

Immutable release candidates bind commit, migration, image digests, configuration fingerprint,
SBOM, backup/restore and continuous quality evidence. Separate closed-deployment and
invite-activation gates retain append-only item results, enforce independent engineering,
data-compliance and product-operations approvals, recheck live evidence before deployment/release
events, and preserve rollback history. The operations UI is desktop-action/mobile-read-only and
does not hold deployment credentials or deploy infrastructure. A real production candidate has not
been released by this implementation; missing production Provider and Resend evidence remains
fail-closed.

## Phase 23 - Hong Kong Staging & GitHub Delivery (staging online, acceptance pending)

The deployment layer now supports protected-PR CI, immutable linux/amd64 images in GHCR, SBOM and
vulnerability gates, serialized main-branch delivery to a dedicated Ubuntu host, BT Nginx over
loopback-only application ports, bounded container resources, encrypted off-host PostgreSQL backup,
one-shot migrations, health-based image rollback and exact release metadata. No public API or
database contract changed.

The Hong Kong staging host is now online at `app.zhiniu.cc` with closed registration, a verified
`security_admin`, real Resend verification delivery, encrypted daily PostgreSQL backups transferred
to the isolated receiver, 14-daily/8-weekly receiver retention, and a successful isolated restore
drill. The active Web Gateway uses the internal Compose `api` alias while public API and application
ports remain behind BT Nginx.

Phase 23 remains unsigned until Resend credentials are moved from the bootstrap environment into
the encrypted Provider vault, the four fixed A-share samples complete Provider/data acceptance,
GitHub SSH deployment is enabled and rehearsed, and the 24–48 hour stability window is recorded.
Staging is not a Phase 22 production event and its accounts and data remain disposable.

## Future - Factor / Backtest

Versioned factor definitions and research simulations remain a future phase. They require
backtest-grade point-in-time datasets and survivorship-bias controls before product work starts.
