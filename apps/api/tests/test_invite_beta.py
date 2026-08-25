import pytest
from pydantic import ValidationError
from zhaoniu_api.invite_beta.models import BetaRecipientsAdd
from zhaoniu_api.invite_beta.security import recipient_email_hmac, validate_recipient_email
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
