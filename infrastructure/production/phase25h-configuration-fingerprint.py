#!/usr/bin/env python3
"""Build a deterministic, secret-free fingerprint of release-affecting settings."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

SCHEMA_VERSION = "phase25h-configuration-fingerprint-v1"
KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")

# Keep credentials, connection strings, recipient addresses and HMAC material out of
# the fingerprint input. The release identity already binds code and image digests;
# this list binds only behavior that can change a Beta admission decision.
FINGERPRINT_KEYS = (
    "ACCESS_ACTIVATION_ENABLED",
    "AI_EXPLANATION_ENABLED",
    "AI_EXPLANATION_MAX_ATTEMPTS",
    "AI_EXPLANATION_MAX_OUTPUT_TOKENS",
    "AI_EXPLANATION_MODEL_CHAIN",
    "AI_EXPLANATION_RUN_DEADLINE_SECONDS",
    "AI_EXPLANATION_TIMEOUT_SECONDS",
    "AKSHARE_MAX_ATTEMPTS",
    "AKSHARE_RETRY_BACKOFF_SECONDS",
    "ALLOWED_ORIGINS",
    "APP_ENV",
    "AUTH_COOKIE_SECURE",
    "AUTOMATION_AI_CONCURRENCY",
    "AUTOMATION_AI_ENABLED",
    "AUTOMATION_AI_MAX_CALLS_PER_RUN",
    "AUTOMATION_CATCHUP_WINDOW_MINUTES",
    "AUTOMATION_HARD_DISABLED",
    "AUTOMATION_LEASE_MINUTES",
    "AUTOMATION_MAX_CONCURRENCY",
    "AUTOMATION_MAX_UNIVERSE_SIZE",
    "AUTOMATION_TICK_SECONDS",
    "BETA_MAX_ACTIVE_USERS",
    "BETA_FEEDBACK_RATE_LIMIT",
    "BETA_LEARNING_MIN_GROUP_SIZE",
    "BETA_MODE",
    "COMMERCIALIZATION_STATUS",
    "COVERAGE_ACCEPTANCE_SYMBOLS",
    "COVERAGE_BACKFILL_BATCH_SIZE",
    "COVERAGE_BACKFILL_MAX_CONCURRENCY",
    "COVERAGE_OPERATOR_PINNED_SYMBOLS",
    "COVERAGE_POLICY_VERSION",
    "COVERAGE_PROVIDER_RATE_LIMIT",
    "COVERAGE_USAGE_SCOPE",
    "DATA_USE_STATUS",
    "EMAIL_DELIVERY_MODE",
    "DISCLOSURE_PROVIDER",
    "LEGAL_REVIEW_STATUS",
    "LLM_ENABLED",
    "LLM_MAX_ATTEMPTS",
    "LLM_MODEL_CHAIN",
    "LLM_PER_MODEL_TIMEOUT_SECONDS",
    "LLM_PROVIDER_DAILY_CALL_LIMIT",
    "LLM_PROVIDER_MAX_CONCURRENCY",
    "LLM_RUN_DEADLINE_SECONDS",
    "LLM_STRUCTURED_OUTPUT_MODE",
    "MANAGED_PROVIDERS_HARD_DISABLED",
    "MARKET_DATA_PROVIDER",
    "PROVIDER_ACCEPTANCE_MAX_AGE_HOURS",
    "PUBLIC_BASE_URL",
    "REGISTRATION_MODE",
    "TRUSTED_HOSTS",
    "WATCHLIST_PREPARATION_DAILY_LIMIT",
    "WATCHLIST_PREPARATION_ENABLED",
)


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or not KEY_PATTERN.fullmatch(key):
            raise ValueError(f"invalid environment entry at line {line_number}")
        if key in values:
            raise ValueError(f"duplicate environment key: {key}")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def fingerprint_payload(values: dict[str, str]) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "settings": {key: values[key] for key in FINGERPRINT_KEYS if key in values},
    }


def configuration_fingerprint(values: dict[str, str]) -> str:
    canonical = json.dumps(
        fingerprint_payload(values),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compute a deterministic secret-free ZhiNiu configuration fingerprint."
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path("/etc/zhiniu/staging.env"),
    )
    parser.add_argument(
        "--metadata",
        action="store_true",
        help="Print safe metadata instead of only the fingerprint.",
    )
    args = parser.parse_args()
    values = parse_env_file(args.env_file)
    result = configuration_fingerprint(values)
    if args.metadata:
        print(
            json.dumps(
                {
                    "schema_version": SCHEMA_VERSION,
                    "configuration_fingerprint": result,
                    "included_keys": [key for key in FINGERPRINT_KEYS if key in values],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    else:
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
