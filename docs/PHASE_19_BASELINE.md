# Phase 19 internal baseline

Status: **INTERNAL BASELINE ACCEPTED - EMAIL DEFERRED**

Phase 19 creates an internal testing candidate. It does not approve invited Beta or production
release. On 2026-08-25 the product owner explicitly deferred the real transactional-email loop
because no production-like public domain is available. This scope exception accepts the engineering
and core-research baseline only; it does not convert skipped email evidence into a pass.

## Candidate identity

- Implementation base commit: `5d273cc2e5317b8c5e75cf34f42ea57f1d40c411`
- Candidate commit: pending
- Database current/head: `20260823_0023`
- Environment: development, Docker Desktop 4.87.0, local PostgreSQL and Redis
- Acceptance symbols: `600519`, `300750`, `300376`, `000001`

## Completed evidence

- `alembic check`: no new upgrade operations detected.
- `/readyz`: PostgreSQL, migration and Redis healthy at migration head `20260823_0023`.
- Frontend gates passed consecutively: lint, format check, typecheck, 51 unit tests, production
  build and generated API contract check.
- Backend gates passed: Ruff, MyPy (122 source files), Pytest (132 passed, 8 skipped) and Alembic.
- Desktop Chromium 1440 x 900: public code/name search and deduplicated 600519 timeline passed.
- Mobile Chromium 390 x 844: the same public flow passed independently.
- Playwright result: 2 public-flow tests passed; 4 real-account/email tests were explicitly skipped
  and deferred by product decision.
- ORM metadata contains the existing migrations 0021/0022 check constraints and AI explanation index.
- API/Worker/Beat and Web container images built successfully. Temporary API and Web containers
  returned `/readyz` status `ready` and HTTP 200; PostgreSQL, migration and Redis were healthy.
- The rebuilt Worker returned a successful Celery ping and Beat remained running.
- Backup `zhaoniu-phase19.dump` was created at migration head `20260823_0023` with SHA-256
  `e51027ce60fbeb949b8e004a52c273bd245d08c8fd50986078d3c032042fc71b` and restored into
  `zhaoniu_restore_phase19`. Source/restored counts matched for users (11), stocks (5547),
  research signals (48) and provider configurations (2).
- Legal review and financial-data use approval were accepted for this environment on 2026-08-24.
- Resend draft revision 6 uses encrypted candidate credentials, sender `info@zhiniu.cc`, sending
  domain `zhiniu.cc` and an encrypted webhook signing secret. Its latest diagnostic returned the
  redacted reason `provider_auth`; it remains unpublished.

## Deferred release gate

- Transactional email: `check-beta-readiness` still reports `transactional_email_disabled`.
- Resend diagnosis, publication, webhook delivery evidence and real registration/recovery
  Playwright lanes are intentionally deferred until a verified sending domain and public HTTPS
  callback are available.
- The Resend active revision remains unset and `EMAIL_DELIVERY_MODE` remains disabled. Invited Beta
  and production release remain fail-closed.

## Deferred email completion procedure

1. Verify a sending domain in Resend and expose the callback through public HTTPS.
2. Diagnose and publish the exact controlled non-production Resend revision without recording
   secrets.
3. Run `pnpm e2e` with one-time account and received-link environment values; no email/account test
   may be skipped for Beta evidence.
4. Set `EMAIL_DELIVERY_MODE=resend`, restart API/Worker/Beat and re-run `check-beta-readiness`.
