from zhaoniu_api.provider_acceptance.models import ProviderAcceptanceItem
from zhaoniu_api.provider_acceptance.service import summarize_acceptance


def _item(requirement: str, status: str) -> ProviderAcceptanceItem:
    return ProviderAcceptanceItem.model_validate(
        {
            "provider": "fixture",
            "dataset": "daily_bars",
            "scenario": "acceptance",
            "requirement": requirement,
            "status": status,
            "evidence_fingerprint": "a" * 64,
        }
    )


def test_mandatory_failure_fails_technical_acceptance() -> None:
    status, eligible, counts = summarize_acceptance(
        [_item("mandatory", "failed"), _item("optional", "passed")],
        policy_ok=True,
    )

    assert status == "failed"
    assert eligible is False
    assert counts == {
        "mandatory": 1,
        "passed": 1,
        "failed": 1,
        "blocked": 0,
        "unsupported": 0,
    }


def test_development_policy_blocks_beta_without_failing_technical_data() -> None:
    status, eligible, counts = summarize_acceptance(
        [_item("mandatory", "passed"), _item("conditional", "blocked")],
        policy_ok=False,
    )

    assert status == "passed"
    assert eligible is False
    assert counts["blocked"] == 1
