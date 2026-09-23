from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from zhaoniu_api.config import Settings
from zhaoniu_api.invite_beta.models import BetaCohortCreate, BetaRecipientsAdd
from zhaoniu_api.invite_beta.security import recipient_email_hmac, validate_recipient_email
from zhaoniu_api.invite_beta.service import (
    invitation_program_for_settings,
    program_gate_reasons,
)
from zhaoniu_api.operations_console.models import OperatorContext
from zhaoniu_api.operations_console.service import CAPABILITIES, OperatorService


def test_recipient_email_is_normalized_and_bound_by_digest() -> None:
    assert validate_recipient_email(" Beta.User@Example.COM ") == "beta.user@example.com"
    assert recipient_email_hmac("Beta.User@Example.COM", "secret") == recipient_email_hmac(
        "beta.user@example.com", "secret"
    )


@pytest.mark.parametrize("value", ["missing-at", "a@localhost", "a b@example.com"])
def test_invalid_recipient_email_is_rejected(value: str) -> None:
    with pytest.raises(ValueError, match="invalid_recipient_email"):
        validate_recipient_email(value)


def test_recipient_batch_rejects_duplicates_after_normalization() -> None:
    with pytest.raises(ValidationError, match="duplicate_recipient_email"):
        BetaRecipientsAdd(emails=["beta@example.com", "BETA@example.com"])


def test_private_evaluation_is_the_small_cohort_default() -> None:
    cohort = BetaCohortCreate(name="研究体验组")

    assert cohort.program_kind == "private_evaluation"
    assert cohort.target_size == 5
    assert cohort.expires_in_days == 7


def test_private_evaluation_rejects_large_cohort() -> None:
    with pytest.raises(ValidationError, match="private_evaluation_target_exceeded"):
        BetaCohortCreate(name="过大体验组", target_size=11)


def test_controlled_beta_keeps_larger_cohort_contract() -> None:
    cohort = BetaCohortCreate(
        name="受控 Beta",
        program_kind="controlled_beta",
        target_size=20,
    )

    assert cohort.target_size == 20


def test_private_evaluation_gate_does_not_require_provider_acceptance() -> None:
    settings = Settings(
        coverage_usage_scope="development_evaluation",
        automation_hard_disabled=False,
        watchlist_preparation_enabled=True,
    )

    assert (
        program_gate_reasons(
            settings,
            "private_evaluation",
            None,
            now=datetime.now(UTC),
        )
        == []
    )


def test_invitation_program_follows_configured_usage_scope() -> None:
    assert (
        invitation_program_for_settings(
            Settings(coverage_usage_scope="development_evaluation")
        )
        == "private_evaluation"
    )
    assert (
        invitation_program_for_settings(Settings(coverage_usage_scope="production"))
        == "controlled_beta"
    )

def test_controlled_beta_gate_remains_fail_closed_without_acceptance() -> None:
    settings = Settings(coverage_usage_scope="production")

    assert "provider_acceptance_missing" in program_gate_reasons(
        settings,
        "controlled_beta",
        None,
        now=datetime.now(UTC),
    )


def test_beta_cohort_changes_require_elevated_authorized_operator() -> None:
    context = OperatorContext(
        role="support",
        capabilities=sorted(CAPABILITIES["support"]),
        elevated=True,
    )
    OperatorService.require(
        context,
        "beta.cohorts.manage",
        elevated=True,
    )
