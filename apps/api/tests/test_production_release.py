from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError
from zhaoniu_api.operations_console.service import CAPABILITIES
from zhaoniu_api.production_release.models import ProductionReleaseCandidateCreate
from zhaoniu_api.production_release.service import (
    ProductionReleaseConflict,
    ProductionReleaseService,
    approval_role_allowed,
    evidence_fingerprint,
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
