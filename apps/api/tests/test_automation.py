from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError
from zhaoniu_api.ai_research.models import AIResearchBuildResult
from zhaoniu_api.automation.models import AutomationPolicyConfiguration
from zhaoniu_api.automation.service import (
    ai_step_result,
    attempted_step_status,
    build_automation_slo_snapshot,
    due_slot,
    is_reporting_window,
    persisted_step_status,
    stable_hash,
)
from zhaoniu_api.db import AutomationRunRecord, AutomationRunStepRecord
from zhaoniu_api.operations_console.models import OperatorContext
from zhaoniu_api.operations_console.service import (
    CAPABILITIES,
    OperatorAuthorizationError,
    OperatorService,
)


def test_due_slot_uses_fixed_shanghai_timezone() -> None:
    before = datetime(2026, 8, 21, 10, 0, tzinfo=UTC)
    due, next_due = due_slot(before, "19:30")
    assert due is None
    assert next_due == datetime(2026, 8, 21, 11, 30, tzinfo=UTC)

    after = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
    due, next_due = due_slot(after, "19:30")
    assert due == datetime(2026, 8, 21, 11, 30, tzinfo=UTC)
    assert next_due == datetime(2026, 8, 22, 11, 30, tzinfo=UTC)


def test_policy_configuration_rejects_free_form_time_and_caps() -> None:
    assert AutomationPolicyConfiguration(daily_time="9:05").daily_time == "09:05"
    with pytest.raises(ValidationError):
        AutomationPolicyConfiguration(daily_time="25:00")
    with pytest.raises(ValidationError):
        AutomationPolicyConfiguration(max_universe_size=501)


def test_reporting_window_and_hash_are_deterministic() -> None:
    assert is_reporting_window(date(2026, 4, 30))
    assert not is_reporting_window(date(2026, 6, 30))
    assert stable_hash({"b": 2, "a": 1}) == stable_hash({"a": 1, "b": 2})


def test_successful_step_without_artifact_change_remains_succeeded() -> None:
    assert persisted_step_status("succeeded", changed=False) == "succeeded"
    assert persisted_step_status("skipped", changed=False) == "skipped"


@pytest.mark.parametrize("status", ["succeeded", "skipped"])
def test_invoked_service_without_new_artifact_is_succeeded(status: str) -> None:
    assert attempted_step_status(status) == "succeeded"
    assert attempted_step_status("not_applicable") == "skipped"
    assert attempted_step_status("failed") == "failed"


@pytest.mark.parametrize(
    ("build_status", "step_status", "error_code"),
    [
        ("skipped", "succeeded", "ai_research_output_current"),
        ("failed", "failed", "ai_generation_failed"),
        ("disabled", "skipped", "automation_ai_disabled"),
        ("not_built", "skipped", "deterministic_snapshot_missing"),
        ("unsupported", "skipped", "unsupported_issuer_type"),
    ],
)
def test_ai_build_status_maps_to_explicit_automation_outcome(
    build_status: str, step_status: str, error_code: str
) -> None:
    mapped = ai_step_result(AIResearchBuildResult(build_status, None, None, None))
    assert mapped.status == step_status
    assert mapped.error_code == error_code


def test_automation_capabilities_are_read_only_for_viewer() -> None:
    viewer = OperatorContext(
        role="viewer",
        capabilities=sorted(CAPABILITIES["viewer"]),
    )
    OperatorService.require(viewer, "automation.read")
    with pytest.raises(OperatorAuthorizationError, match="operator_capability_required"):
        OperatorService.require(viewer, "automation.run")

    operations = OperatorContext(
        role="operations",
        capabilities=sorted(CAPABILITIES["operations"]),
        elevated=True,
    )
    OperatorService.require(operations, "automation.manage", elevated=True)


def test_watchlist_slo_snapshot_projects_retained_run_facts() -> None:
    now = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)
    successful_id = uuid4()
    running_id = uuid4()
    failed_id = uuid4()
    runs = [
        AutomationRunRecord(
            id=successful_id,
            trigger_kind="watchlist",
            status="succeeded_with_warnings",
            created_at=now - timedelta(minutes=5),
            started_at=now - timedelta(minutes=4, seconds=58),
        ),
        AutomationRunRecord(
            id=running_id,
            trigger_kind="watchlist",
            status="running",
            created_at=now - timedelta(minutes=30),
            started_at=now - timedelta(minutes=29, seconds=45),
        ),
        AutomationRunRecord(
            id=failed_id,
            trigger_kind="watchlist",
            status="failed",
            error_code="automation_run_failed",
            created_at=now - timedelta(minutes=40),
            started_at=now - timedelta(minutes=39, seconds=57),
        ),
    ]
    steps = [
        AutomationRunStepRecord(
            run_id=successful_id,
            step_key="market_sync",
            status="succeeded",
            finished_at=now - timedelta(minutes=4, seconds=30),
        ),
        AutomationRunStepRecord(
            run_id=successful_id,
            step_key="research_build",
            status="skipped",
            error_code="research_input_unchanged",
            finished_at=now,
        ),
        AutomationRunStepRecord(
            run_id=successful_id,
            step_key="ai_research",
            status="failed",
            error_code="ai_generation_failed",
            finished_at=now,
        ),
        AutomationRunStepRecord(
            run_id=failed_id,
            step_key="market_sync",
            status="failed",
            error_code="provider_connection_failed",
            finished_at=now - timedelta(minutes=39),
        ),
    ]

    snapshot = build_automation_slo_snapshot(
        runs,
        steps,
        generated_at=now,
        window_hours=24,
    )
    metrics = {item.key: item for item in snapshot.metrics}

    assert snapshot.total_watchlist_runs == 3
    assert snapshot.terminal_runs == 2
    assert snapshot.acceptable_terminal_runs == 1
    assert snapshot.acceptable_terminal_rate_percent == 50.0
    assert snapshot.running_runs == 1
    assert snapshot.stale_active_runs == 1
    assert metrics["queue_start"].sample_count == 3
    assert metrics["queue_start"].p95_ms == 15_000
    assert metrics["queue_start"].met is False
    assert metrics["market_ready"].p95_ms == 30_000
    assert metrics["market_ready"].met is True
    assert metrics["deterministic_ready"].p95_ms == 300_000
    assert metrics["ai_terminal"].p95_ms == 300_000
    assert snapshot.failure_reasons == {
        "ai_generation_failed": 1,
        "automation_run_failed": 1,
        "provider_connection_failed": 1,
    }


def test_watchlist_slo_snapshot_has_unknown_metrics_without_samples() -> None:
    now = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)
    snapshot = build_automation_slo_snapshot(
        [],
        [],
        generated_at=now,
        window_hours=24,
    )

    assert snapshot.acceptable_terminal_rate_percent is None
    assert all(item.sample_count == 0 for item in snapshot.metrics)
    assert all(item.p95_ms is None and item.met is None for item in snapshot.metrics)
