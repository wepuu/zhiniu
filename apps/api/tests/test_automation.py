from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError
from zhaoniu_api.automation.models import AutomationPolicyConfiguration
from zhaoniu_api.automation.service import due_slot, is_reporting_window, stable_hash
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
