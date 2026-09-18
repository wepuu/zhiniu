from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError
from zhaoniu_api.config import Settings
from zhaoniu_api.operations_console.service import CAPABILITIES
from zhaoniu_api.production_release.models import ProductionReleaseCandidateCreate
from zhaoniu_api.production_release.service import (
    ProductionReleaseConflict,
    ProductionReleaseService,
    approval_role_allowed,
    automation_gate_checks,
    evidence_fingerprint,
    reliability_observation_eligible,
)


def _candidate(**overrides: object) -> ProductionReleaseCandidateCreate:
    values: dict[str, object] = {
        "commit_sha": "a" * 40,
        "migration_head": "20260826_0027",
        "api_image_digest": f"sha256:{'b' * 64}",
        "web_image_digest": f"sha256:{'c' * 64}",
        "configuration_fingerprint": "d" * 64,
        "sbom_sha256": "e" * 64,
        "backup_sha256": "f" * 64,
        "restore_verified_at": datetime.now(UTC),
        "quality_gate_status": "passed",
        "e2e_status": "passed",
        "security_scan_status": "passed",
    }
    values.update(overrides)
    return ProductionReleaseCandidateCreate.model_validate(values)


def test_candidate_evidence_normalizes_immutable_digests() -> None:
    candidate = _candidate(commit_sha="A" * 40, api_image_digest=f"sha256:{'B' * 64}")

    assert candidate.commit_sha == "a" * 40
    assert candidate.api_image_digest == f"sha256:{'b' * 64}"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("commit_sha", "main"),
        ("configuration_fingerprint", "x" * 64),
        ("api_image_digest", "b" * 64),
    ],
)
def test_candidate_rejects_unverifiable_artifact_identity(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        _candidate(**{field: value})


def test_evidence_fingerprint_is_order_independent() -> None:
    assert evidence_fingerprint({"a": 1, "b": 2}) == evidence_fingerprint({"b": 2, "a": 1})


def test_approval_roles_require_independent_operator_duties() -> None:
    assert approval_role_allowed("security_admin", "engineering")
    assert approval_role_allowed("security_admin", "data_compliance")
    assert not approval_role_allowed("security_admin", "product_operations")
    assert approval_role_allowed("operations", "product_operations")
    assert not approval_role_allowed("operations", "engineering")


def test_deployment_state_machine_is_fail_closed() -> None:
    ProductionReleaseService._assert_event_transition("ready_closed", "deployed")
    ProductionReleaseService._assert_event_transition("ready_invites", "released")
    ProductionReleaseService._assert_event_transition("released", "rolled_back")

    with pytest.raises(ProductionReleaseConflict, match="invalid_transition"):
        ProductionReleaseService._assert_event_transition("blocked", "deployed")
    with pytest.raises(ProductionReleaseConflict, match="invalid_transition"):
        ProductionReleaseService._assert_event_transition("deployed_observing", "released")


def test_operator_capabilities_expose_release_actions_by_role() -> None:
    assert "releases.read" in CAPABILITIES["viewer"]
    assert "releases.manage" not in CAPABILITIES["viewer"]
    assert "releases.approve" in CAPABILITIES["operations"]
    assert "releases.record" in CAPABILITIES["security_admin"]


def test_candidate_forbids_unknown_evidence_fields() -> None:
    with pytest.raises(ValidationError):
        ProductionReleaseCandidateCreate.model_validate(
            {**_candidate().model_dump(), "raw_secret": str(uuid4())}
        )


def test_candidate_requires_timezone_aware_restore_evidence() -> None:
    with pytest.raises(ValidationError, match="must_include_timezone"):
        _candidate(restore_verified_at=datetime.now())


def test_closed_deployment_keeps_automation_hard_disabled() -> None:
    checks = automation_gate_checks(
        Settings(automation_hard_disabled=True, watchlist_preparation_enabled=True),
        "closed_deployment",
    )

    assert [(check.key, check.passed, check.reason_code) for check in checks] == [
        ("automation.hard_disabled", True, None)
    ]


@pytest.mark.parametrize(
    ("hard_disabled", "watchlist_enabled", "expected"),
    [
        (
            True,
            True,
            {"automation.emergency_stop": False, "automation.watchlist_preparation": True},
        ),
        (
            False,
            False,
            {"automation.emergency_stop": True, "automation.watchlist_preparation": False},
        ),
        (
            False,
            True,
            {"automation.emergency_stop": True, "automation.watchlist_preparation": True},
        ),
    ],
)
def test_invite_activation_requires_scoped_watchlist_automation(
    hard_disabled: bool,
    watchlist_enabled: bool,
    expected: dict[str, bool],
) -> None:
    checks = automation_gate_checks(
        Settings(
            automation_hard_disabled=hard_disabled,
            watchlist_preparation_enabled=watchlist_enabled,
        ),
        "invite_activation",
    )

    assert {check.key: check.passed for check in checks} == expected


@pytest.mark.parametrize(
    ("status", "window_hours", "age_hours", "expected"),
    [
        ("passed", 48, 0, (True, True, True)),
        ("failed", 48, 0, (False, True, True)),
        ("passed", 24, 0, (False, True, False)),
        ("passed", 48, 25, (False, False, True)),
        ("passed", 48, -1, (False, False, True)),
    ],
)
def test_reliability_observation_requires_passed_fresh_48_hour_evidence(
    status: str,
    window_hours: int,
    age_hours: int,
    expected: tuple[bool, bool, bool],
) -> None:
    now = datetime.now(UTC)
    window_ended_at = now - timedelta(hours=age_hours)
    observation = SimpleNamespace(
        status=status,
        window_started_at=window_ended_at - timedelta(hours=window_hours),
        window_ended_at=window_ended_at,
    )

    assert reliability_observation_eligible(observation, now=now) == expected


def test_missing_reliability_observation_is_ineligible() -> None:
    assert reliability_observation_eligible(None, now=datetime.now(UTC)) == (
        False,
        False,
        False,
    )
