# Phase 25K — Private Evaluation Cohort

Phase 25K supports a private, non-commercial evaluation for a small invited group while preserving
the stricter commercial controlled-Beta path. It does not approve a public launch, a paid product or
commercial use of AKShare/Sina data.

## Program boundary

| Program              | Usage scope              | Default / maximum | Provider acceptance |
| -------------------- | ------------------------ | ----------------- | ------------------- |
| `private_evaluation` | `development_evaluation` | 5 / 10            | Not required        |
| `controlled_beta`    | `production`             | 10 / 100          | Current pass needed |

Both programs remain invitation-only and require approved legal/data-use policy, healthy Resend
delivery and available account capacity. Private evaluation additionally requires automation to be
enabled and watchlist preparation to be available. The emergency automation stop therefore pauses
new private-evaluation admission instead of creating participants who cannot reach research value.

Existing cohorts are migrated to `controlled_beta`/`production`; their admission semantics do not
change. New cohorts created in the operations console default to private evaluation and carry the
versioned `private-evaluation-v1` notice.

## First-value contract

The cohort funnel and the signed-in participant checklist derive these milestones from retained
facts:

1. invitation email submitted and delivered;
2. account registered and email verified;
3. first watchlist item retained under the participant's `user_id`;
4. shared market artifact ready;
5. shared deterministic research artifact ready;
6. AI research reaches `ready`, `failed`, `paused` or `unsupported`;
7. participant feedback retained.

An AI failure is a terminal fact, not a successful result. The UI presents it as an honest outcome
so an evaluation cannot remain on a permanent spinner. Stock data and research outputs remain global
and deduplicated; the cohort stores no per-user copy.

## Acceptance and rollout

Before sending a private-evaluation cohort:

- deploy migration head `20260923_0031` and verify API/Web health;
- confirm `REGISTRATION_MODE=invite_only`, `COVERAGE_USAGE_SCOPE=development_evaluation`,
  `AUTOMATION_HARD_DISABLED=false`, and `WATCHLIST_PREPARATION_ENABLED=true`;
- verify the active Resend revision and its diagnostic;
- create a draft cohort with no more than five initial recipients;
- inspect the gate reasons, approve, then dispatch;
- validate desktop and mobile paths for registration, verification, watchlist addition, readiness,
  company research, AI terminal state and feedback;
- exercise `600519`, `300750`, `300376` and `000001` so ready, partial and unsupported states remain
  explicit.

Do not expand the cohort while unexplained stale preparation runs, sustained queue growth, OOM
restarts or failed backup/restore evidence exists. A private-evaluation pass cannot be reused as a
commercial controlled-Beta approval.
